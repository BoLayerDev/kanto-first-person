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

local DRAW_KINDS = {
  mesh = true,
  instances = true,
  billboards = true,
  lights = true,
  postprocess = true,
}

local MAX_COMMANDS = 8192
local MAX_BATCH_ITEMS = 8192

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

local function assignWireIdentity(command, phase, metadata, hashCommand)
  local contentHash = hashCommand(command)
  if type(contentHash) ~= "string" or not contentHash:match("^[0-9a-f]+$")
      or #contentHash ~= 16 then
    error("hashCommand must return exactly 16 lowercase hexadecimal characters", 3)
  end
  command.schemaVersion = SCHEMA_VERSION
  local cacheKey = table.concat({
    "kfp1",
    digest(metadata.key),
    tostring(metadata.generation or 0),
    tostring(PHASES[phase]),
    tostring(command.sequence),
    contentHash,
  }, ":")
  if #cacheKey > 64 then error("KFP draw cache key exceeds 64 bytes", 3) end
  command.cacheKey = cacheKey
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

  local phases = {}
  local batches = {}
  for phase in pairs(PHASES) do
    phases[phase] = {}
    batches[phase] = {}
  end

  return setmetatable({
    _phases = phases,
    _batches = batches,
    _maxCommands = maxCommands,
    _maxBatchItems = maxBatchItems,
    _count = 0,
    _sequence = 0,
    _sealed = false,
    _hashCommand = options.hashCommand,
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

local function batchIdentity(kind, owner, key, segment)
  return table.concat({ kind, owner, key, tostring(segment) }, "\31")
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
  local phaseBatches = self._batches[phase]
  if not phaseBatches then error("unknown render phase: " .. tostring(phase), 2) end

  local segment = 1
  local identity = batchIdentity(kind, owner, key, segment)
  local batch = phaseBatches[identity]
  while batch and #batch.items >= self._maxBatchItems do
    segment = segment + 1
    identity = batchIdentity(kind, owner, key, segment)
    batch = phaseBatches[identity]
  end

  if not batch then
    batch = shallowCopy(template)
    batch.kind = kind
    batch.key = key
    batch.items = {}
    batch.owner = owner
    batch.sortKey = tostring(template.sortKey or template.material or key)
    phaseBatches[identity] = batch
    self:_append(phase, batch)
  end
  batch.items[#batch.items + 1] = item
  return batch
end

function CommandBuffer:seal(metadata)
  self:_assertOpen()
  self._sealed = true
  metadata = shallowCopy(metadata)
  local generation = metadata.generation
  if generation == nil then generation = 0 end
  if type(generation) ~= "number" or generation ~= math.floor(generation)
      or generation < 0 or generation > 2147483647 then
    error("scene generation must be an integer from 0 through 2147483647", 2)
  end
  metadata.generation = generation
  metadata.schemaVersion = SCHEMA_VERSION
  local output = {}
  local drawCalls = 0
  for phase, list in pairs(self._phases) do
    table.sort(list, less)
    for _, command in ipairs(list) do
      assignWireIdentity(command, phase, metadata, self._hashCommand)
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
