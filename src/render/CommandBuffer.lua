local CommandBuffer = {}
CommandBuffer.__index = CommandBuffer

local SCHEMA_VERSION = 1

local PHASES = {
  background = 1,
  opaque_after_terrain = 2,
  translucent_after_actors = 3,
  shadow_casters = 4,
  battle_opaque = 5,
}

local PHASE_ORDER = {
  "background",
  "opaque_after_terrain",
  "translucent_after_actors",
  "shadow_casters",
  "battle_opaque",
}

local DRAW_KINDS = {
  mesh = true,
  instances = true,
  billboards = true,
}

local MAX_COMMANDS = 8192
local MAX_BATCH_ITEMS = 8192
local DIGEST_CHUNK_BYTES = 64
local SMALL_SORT_COMMANDS = 32
local HASH_UNITS_PER_SEAL_STEP = 64

local SealJob = {}
SealJob.__index = SealJob

local function text(value, name)
  if type(value) ~= "string" or value == "" then
    error(name .. " must be a non-empty string", 3)
  end
  return value
end

local function shallowCopy(source)
  local out = {}
  for key, value in pairs(source or {}) do out[key] = value end
  return out
end

local function boundedInteger(value, fallback, maximum, name)
  value = tonumber(value == nil and fallback or value)
  if not value or value ~= math.floor(value) or value < 1 or value > maximum then
    error((name or "value") .. " must be an integer from 1 through " .. maximum, 3)
  end
  return value
end

local function less(a, b)
  if a.sortKey ~= b.sortKey then return a.sortKey < b.sortKey end
  return a.sequence < b.sequence
end

local function digest(value)
  local hash = 5381
  value = tostring(value or "")
  for index = 1, #value do
    hash = (hash * 33 + value:byte(index)) % 4294967296
  end
  return string.format("%08x", hash)
end

local function validateContentHash(contentHash)
  if type(contentHash) ~= "string" or not contentHash:match("^[0-9a-f]+$")
      or #contentHash ~= 16 then
    error("hashCommand must return exactly 16 lowercase hexadecimal characters", 3)
  end
  return contentHash
end

local function assignWireIdentity(command, phase, metadata, contentHash, keyDigest)
  validateContentHash(contentHash)
  command.schemaVersion = SCHEMA_VERSION
  local cacheKey = table.concat({
    "kfp1",
    keyDigest or digest(metadata.key),
    tostring(metadata.generation or 0),
    tostring(PHASES[phase]),
    tostring(command.sequence),
    contentHash,
  }, ":")
  if #cacheKey > 64 then error("KFP draw cache key exceeds 64 bytes", 3) end
  command.cacheKey = cacheKey
end

local function normalizedMetadata(metadata)
  metadata = shallowCopy(metadata)
  local generation = metadata.generation
  if generation == nil then generation = 0 end
  if type(generation) ~= "number" or generation ~= math.floor(generation)
      or generation < 0 or generation > 2147483647 then
    error("scene generation must be an integer from 0 through 2147483647", 3)
  end
  metadata.generation = generation
  metadata.schemaVersion = SCHEMA_VERSION
  return metadata
end

local function boundedUnits(value)
  value = tonumber(value) or 1
  if value ~= value or value == math.huge or value == -math.huge
      or value ~= math.floor(value) or value < 1 then
    error("seal step units must be a positive integer", 3)
  end
  return value
end

local function validateHashJob(hashJob)
  if type(hashJob) ~= "table" or type(hashJob.step) ~= "function" then
    error("newHashCommandJob must return a table with callable step", 3)
  end
  return hashJob
end

local function newSort(list)
  if #list <= SMALL_SORT_COMMANDS then
    table.sort(list, less)
    return { count = #list, width = #list, source = list }
  end
  return {
    count = #list,
    width = 1,
    left = 1,
    source = list,
    target = {},
    merging = false,
  }
end

local function sortStep(sort)
  if sort.count <= 1 or sort.width >= sort.count then
    return true, sort.source
  end

  if not sort.merging then
    if sort.left > sort.count then
      sort.source, sort.target = sort.target, sort.source
      sort.width = sort.width * 2
      sort.left = 1
      return false
    end
    sort.i = sort.left
    sort.middle = math.min(sort.left + sort.width - 1, sort.count)
    sort.j = sort.middle + 1
    sort.right = math.min(sort.left + sort.width * 2 - 1, sort.count)
    sort.k = sort.left
    sort.merging = true
    return false
  end

  if sort.k > sort.right then
    sort.left = sort.left + sort.width * 2
    sort.merging = false
    return false
  end

  local takeLeft = sort.j > sort.right
    or (sort.i <= sort.middle and less(sort.source[sort.i], sort.source[sort.j]))
  if takeLeft then
    sort.target[sort.k] = sort.source[sort.i]
    sort.i = sort.i + 1
  else
    sort.target[sort.k] = sort.source[sort.j]
    sort.j = sort.j + 1
  end
  sort.k = sort.k + 1
  return false
end

function CommandBuffer.new(options)
  options = options or {}
  local maxCommands = boundedInteger(options.maxCommands, 4096, MAX_COMMANDS, "maxCommands")
  local maxBatchItems = boundedInteger(
    options.maxBatchItems,
    2048,
    MAX_BATCH_ITEMS,
    "maxBatchItems"
  )
  if type(options.hashCommand) ~= "function" then
    error("CommandBuffer needs hashCommand", 2)
  end
  if options.newHashCommandJob ~= nil
      and type(options.newHashCommandJob) ~= "function" then
    error("newHashCommandJob must be a function", 2)
  end

  local phases = {}
  local batchTails = {}
  for phase in pairs(PHASES) do
    phases[phase] = {}
    batchTails[phase] = {}
  end

  return setmetatable({
    _phases = phases,
    _batchTails = batchTails,
    _maxCommands = maxCommands,
    _maxBatchItems = maxBatchItems,
    _count = 0,
    _sequence = 0,
    _sealed = false,
    _hashCommand = options.hashCommand,
    _newHashCommandJob = options.newHashCommandJob,
  }, CommandBuffer)
end

function CommandBuffer:_assertOpen()
  if self._sealed then error("command buffer is sealed", 3) end
end

function CommandBuffer:_phase(name)
  local list = self._phases[name]
  if not list then error("unknown render phase: " .. tostring(name), 3) end
  return list
end

function CommandBuffer:_append(phase, command)
  self:_assertOpen()
  if self._count >= self._maxCommands then
    error("command buffer limit reached", 3)
  end
  local list = self:_phase(phase)
  self._count = self._count + 1
  self._sequence = self._sequence + 1
  command.sequence = self._sequence
  command.phase = phase
  command.owner = text(command.owner or "core", "owner")
  command.sortKey = tostring(command.sortKey or command.material or command.kind or "")
  list[#list + 1] = command
  return command
end

function CommandBuffer:add(phase, command)
  if type(command) ~= "table" then error("command must be a table", 2) end
  local copy = shallowCopy(command)
  copy.kind = text(copy.kind, "command kind")
  if not DRAW_KINDS[copy.kind] then
    error("unsupported draw kind: " .. copy.kind, 2)
  end
  return self:_append(phase, copy)
end

function CommandBuffer:addBatchItem(phase, kind, key, template, item)
  self:_assertOpen()
  if kind ~= "instances" and kind ~= "billboards" then
    error("batch kind must be instances or billboards", 2)
  end
  key = text(key, "batch key")
  template = template or {}
  if type(template) ~= "table" or type(item) ~= "table" then
    error("batch template and item must be tables", 2)
  end
  local owner = text(template.owner or "core", "owner")
  local phaseTails = self._batchTails[phase]
  if not phaseTails then error("unknown render phase: " .. tostring(phase), 2) end

  local kindTails = phaseTails[kind]
  if not kindTails then
    kindTails = {}
    phaseTails[kind] = kindTails
  end
  local ownerTails = kindTails[owner]
  if not ownerTails then
    ownerTails = {}
    kindTails[owner] = ownerTails
  end
  local batch = ownerTails[key]
  if not batch or #batch.items >= self._maxBatchItems then
    batch = shallowCopy(template)
    batch.kind = kind
    batch.key = key
    batch.items = {}
    batch.owner = owner
    batch.sortKey = tostring(template.sortKey or template.material or key)
    ownerTails[key] = batch
    self:_append(phase, batch)
  end
  batch.items[#batch.items + 1] = item
  return batch
end

function CommandBuffer:seal(metadata)
  self:_assertOpen()
  self._sealed = true
  metadata = normalizedMetadata(metadata)
  local output = {}
  local drawCalls = 0
  for phase, list in pairs(self._phases) do
    table.sort(list, less)
    for _, command in ipairs(list) do
      assignWireIdentity(command, phase, metadata, self._hashCommand(command))
    end
    output[phase] = list
    drawCalls = drawCalls + #list
  end
  return {
    phases = output,
    commandCount = self._count,
    drawCalls = drawCalls,
    metadata = metadata,
  }
end

local function digestStep(job)
  local textValue = job.digestText
  local last = math.min(#textValue, job.digestIndex + DIGEST_CHUNK_BYTES - 1)
  for index = job.digestIndex, last do
    job.digestHash = (job.digestHash * 33 + textValue:byte(index)) % 4294967296
  end
  job.digestIndex = last + 1
  if job.digestIndex > #textValue then
    job.keyDigest = string.format("%08x", job.digestHash)
    job.stage = "phase"
  end
end

local function sealStep(job)
  if job.stage == "digest" then
    digestStep(job)
    return
  end

  if job.stage == "phase" then
    local phase = PHASE_ORDER[job.phaseIndex]
    if not phase then
      job.packet = {
        phases = job.output,
        commandCount = job.buffer._count,
        drawCalls = job.drawCalls,
        metadata = job.metadata,
      }
      job.done = true
      job.stage = "done"
      return
    end
    job.phase = phase
    job.list = job.buffer._phases[phase]
    job.sort = newSort(job.list)
    job.stage = "sort"
    return
  end

  if job.stage == "sort" then
    local done, sorted = sortStep(job.sort)
    if done then
      job.buffer._phases[job.phase] = sorted
      job.list = sorted
      job.output[job.phase] = sorted
      job.drawCalls = job.drawCalls + #sorted
      job.commandIndex = 1
      job.sort = nil
      job.stage = "hash"
    end
    return
  end

  if job.stage == "hash" then
    local command = job.list[job.commandIndex]
    if not command then
      job.phaseIndex = job.phaseIndex + 1
      job.phase = nil
      job.list = nil
      job.commandIndex = nil
      job.stage = "phase"
      return
    end
    if not job.hashJob then
      job.hashJob = validateHashJob(
        job.buffer._newHashCommandJob(command)
      )
      return
    end
    local done, contentHash = job.hashJob:step(HASH_UNITS_PER_SEAL_STEP)
    if type(done) ~= "boolean" then
      error("command hash job step must return a Boolean completion flag", 2)
    end
    if not done and contentHash ~= nil then
      error("incomplete command hash job must not return a hash", 2)
    end
    if done then
      assignWireIdentity(command, job.phase, job.metadata, contentHash, job.keyDigest)
      job.hashJob = nil
      job.commandIndex = job.commandIndex + 1
    end
    return
  end

  error("invalid command buffer seal state", 2)
end

function CommandBuffer:beginSeal(metadata)
  self:_assertOpen()
  self._sealed = true
  if type(self._newHashCommandJob) ~= "function" then
    error("incremental seal needs newHashCommandJob", 2)
  end
  metadata = normalizedMetadata(metadata)
  return setmetatable({
    buffer = self,
    metadata = metadata,
    output = {},
    drawCalls = 0,
    phaseIndex = 1,
    digestText = tostring(metadata.key or ""),
    digestHash = 5381,
    digestIndex = 1,
    keyDigest = nil,
    stage = "digest",
    done = false,
    packet = nil,
  }, SealJob)
end

function SealJob:step(maxUnits)
  if self.done then return true, self.packet end
  maxUnits = boundedUnits(maxUnits)
  for _ = 1, maxUnits do
    sealStep(self)
    if self.done then break end
  end
  return self.done, self.packet
end

CommandBuffer.SCHEMA_VERSION = SCHEMA_VERSION

function CommandBuffer:count()
  return self._count
end

function CommandBuffer.phases()
  local out = {}
  for phase, order in pairs(PHASES) do out[phase] = order end
  return out
end

return CommandBuffer
