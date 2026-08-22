local SceneCompiler = {}
SceneCompiler.__index = SceneCompiler

local PACKET_PHASES = {
  "background",
  "opaque_after_terrain",
  "translucent_after_actors",
  "shadow_casters",
  "battle_opaque",
}

local PACKET_PHASE_SET = {}
for _, phase in ipairs(PACKET_PHASES) do PACKET_PHASE_SET[phase] = true end

local SEAL_UNITS_PER_OPERATION = 1
local VALIDATION_ENTRIES_PER_OPERATION = 32
local COST_COMMANDS_PER_OPERATION = 32
local MAX_PACKET_COMMANDS = 8192
local MAX_COMMAND_ITEMS = 8192
local BUDGET_GUARD_MS = 0.025

local function defaultClock()
  return os.clock()
end

local function stableFeatureOrder(a, b)
  local ao, bo = tonumber(a.order) or 0, tonumber(b.order) or 0
  if ao ~= bo then return ao < bo end
  return tostring(a.id) < tostring(b.id)
end

local function emitDiagnostic(diagnostics, level, code, message, fields)
  if diagnostics and diagnostics.emit then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

local function estimatePacketCost(packet)
  local cost = 1024
  for _, commands in pairs(packet and packet.phases or {}) do
    for _, command in ipairs(commands) do
      cost = cost + 256
      if type(command.items) == "table" then
        cost = cost + #command.items * 96
      end
    end
  end
  return cost
end

local function defaultReleasePacket(packet, reason)
  if type(packet) == "table" and type(packet.release) == "function" then
    return packet:release(reason or "packet_released")
  end
  return true
end

local function validateBuffer(buffer)
  if type(buffer) ~= "table" or type(buffer.beginSeal) ~= "function" then
    error("SceneCompiler newBuffer must return a buffer with beginSeal", 3)
  end
  return buffer
end

local function isNonNegativeInteger(value)
  return type(value) == "number" and value == value
    and value ~= math.huge and value ~= -math.huge
    and value == math.floor(value) and value >= 0
end

local function beginPacketValidation(build, packet)
  if type(packet) ~= "table" or getmetatable(packet) ~= nil then
    return nil, "completed scene packet must be a plain table"
  end
  if type(packet.phases) ~= "table" or getmetatable(packet.phases) ~= nil then
    return nil, "completed scene packet phases must be a plain table"
  end
  if type(packet.metadata) ~= "table" or getmetatable(packet.metadata) ~= nil then
    return nil, "completed scene packet metadata must be a plain table"
  end
  if packet.metadata.key ~= build.key
      or packet.metadata.generation ~= build.generation then
    return nil, "completed scene packet metadata does not match the active build"
  end
  if not isNonNegativeInteger(packet.commandCount)
      or packet.commandCount > MAX_PACKET_COMMANDS then
    return nil, "completed scene packet commandCount is invalid"
  end
  if not isNonNegativeInteger(packet.drawCalls)
      or packet.drawCalls > MAX_PACKET_COMMANDS then
    return nil, "completed scene packet drawCalls is invalid"
  end
  build.packet = packet
  build.validation = {
    stage = "phase_keys",
    phaseKey = nil,
    phaseIndex = 1,
    commands = nil,
    commandKey = nil,
    commandCount = 0,
    maxCommandIndex = 0,
    items = nil,
    itemKey = nil,
    itemCount = 0,
    maxItemIndex = 0,
    total = 0,
  }
  build.stage = "validate"
  return true
end

function SceneCompiler.new(options)
  options = options or {}
  if type(options.newBuffer) ~= "function" then
    error("SceneCompiler needs newBuffer", 2)
  end
  local features = {}
  for i, feature in ipairs(options.features or {}) do
    if type(feature) ~= "table" or type(feature.id) ~= "string"
        or type(feature.compile) ~= "function" then
      error("invalid feature at index " .. i, 2)
    end
    features[#features + 1] = feature
  end
  table.sort(features, stableFeatureOrder)

  return setmetatable({
    _newBuffer = options.newBuffer,
    _clock = options.clock or defaultClock,
    _diagnostics = options.diagnostics,
    _releasePacket = options.releasePacket or defaultReleasePacket,
    _cache = options.cache,
    _clearCacheOnDispose = options.clearCacheOnDispose ~= false,
    _features = features,
    _generation = 0,
    _building = nil,
    _active = nil,
    _lastError = nil,
    _maxResumes = tonumber(options.maxResumes) or 4096,
    _maxOperations = tonumber(options.maxOperations) or 4096,
  }, SceneCompiler)
end

function SceneCompiler:_release(packet, reason)
  local ok, err = pcall(self._releasePacket, packet, reason)
  if not ok then
    emitDiagnostic(self._diagnostics, "error", "RENDER.PACKET_RELEASE_FAILED",
      "A scene packet release failed.", { error = tostring(err), reason = reason })
  end
end

function SceneCompiler:_cancelBuild(reason)
  local build = self._building
  self._building = nil
  if build and build.assetScope and type(build.assetScope.release) == "function" then
    local ok, err = pcall(build.assetScope.release, build.assetScope,
      reason or "build_cancelled")
    if not ok then
      emitDiagnostic(self._diagnostics, "error", "ASSET.BUILD_SCOPE_RELEASE_FAILED",
        "A cancelled scene build could not release its asset leases.", {
          error = tostring(err),
          reason = tostring(reason),
        })
    end
  end
end

function SceneCompiler:_cachePacket(packet, reason)
  if not packet then return end
  if packet.metadata and packet.metadata.cacheable == false then
    self:_release(packet, reason or "uncacheable")
    return
  end
  local key = packet.metadata and packet.metadata.key
  if not self._cache or type(key) ~= "string" then
    self:_release(packet, reason)
    return
  end
  local cost = packet.metadata.costBytes or estimatePacketCost(packet)
  local ok, stored = pcall(self._cache.put, self._cache, key, packet, cost)
  if not ok then
    self:_release(packet, "cache_error")
    emitDiagnostic(self._diagnostics, "error", "RENDER.CACHE_PUT_FAILED",
      "A scene packet could not enter the cache.", { key = key, error = tostring(stored) })
  elseif not stored then
    -- The cache owns and releases an entry that exceeds its limits.
    emitDiagnostic(self._diagnostics, "warn", "RENDER.CACHE_ENTRY_REJECTED",
      "A scene packet exceeds the active cache policy.", { key = key, cost = cost })
  end
end

local function newTask(feature, context, buffer)
  local thread = coroutine.create(function()
    local compileContext = {
      world = context.world,
      config = context.config,
      quality = context.quality,
      services = context.services,
      generation = context.generation,
      checkpoint = function(cost)
        coroutine.yield(tonumber(cost) or 1)
      end,
    }
    return feature:compile(compileContext, buffer)
  end)
  return {
    feature = feature,
    thread = thread,
    done = false,
  }
end

function SceneCompiler:request(context)
  if type(context) ~= "table" or type(context.key) ~= "string" then
    error("compile request needs a string key", 2)
  end
  if self._building and self._building.key == context.key then
    return self._building.generation
  end
  if self._active and self._active.metadata
      and self._active.metadata.key == context.key then
    return self._active.metadata.generation
  end

  if self._building then self:_cancelBuild("superseded") end

  if self._cache and type(self._cache.take) == "function" then
    local ok, cached = pcall(self._cache.take, self._cache, context.key)
    if ok and cached then
      self._generation = self._generation + 1
      self._building = nil
      local previous = self._active
      self._active = cached
      if previous then self:_cachePacket(previous, "cache_swap") end
      return cached.metadata and cached.metadata.generation or self._generation, true
    elseif not ok then
      emitDiagnostic(self._diagnostics, "error", "RENDER.CACHE_TAKE_FAILED",
        "A cached scene packet could not be restored.", {
          key = context.key,
          error = tostring(cached),
        })
    end
  end

  self._generation = self._generation + 1
  local generation = self._generation
  -- Reject a synchronous-only buffer before opening an asset scope. The
  -- current packet remains active, so the host can keep rendering it.
  local buffer = validateBuffer(self._newBuffer(context.quality))
  local services = {}
  for name, value in pairs(context.services or {}) do services[name] = value end
  local assetScope
  if type(services.assets) == "table" and type(services.assets.scope) == "function" then
    assetScope = services.assets:scope()
    services.assets = assetScope
  end
  local build = {
    generation = generation,
    key = context.key,
    context = {
      world = context.world,
      config = context.config,
      quality = context.quality,
      services = services,
      generation = generation,
    },
    buffer = buffer,
    tasks = {},
    index = 1,
    startedAt = self._clock(),
    optionalErrors = {},
    assetScope = assetScope,
    stage = "features",
  }
  for _, feature in ipairs(self._features) do
    build.tasks[#build.tasks + 1] = newTask(feature, build.context, buffer)
  end
  self._building = build
  return generation
end

function SceneCompiler:_failBuild(task, err)
  local build = self._building
  local feature = task.feature
  local message = tostring(err)
  if feature.critical == false then
    build.optionalErrors[feature.id] = message
    task.done = true
    build.index = build.index + 1
    emitDiagnostic(self._diagnostics, "error", "RENDER.FEATURE_COMPILE_FAILED",
      "Optional feature compilation failed", {
        feature = feature.id,
        error = message,
        generation = build.generation,
      })
    return true
  end

  self._lastError = {
    feature = feature.id,
    error = message,
    generation = build.generation,
  }
  emitDiagnostic(self._diagnostics, "error", "RENDER.SCENE_COMPILE_FAILED",
    "Critical scene compilation failed", self._lastError)
  self:_cancelBuild("critical_feature_failed")
  return false
end

function SceneCompiler:_sealFailure(err)
  self:_cancelBuild("packet_seal_failed")
  error(err, 0)
end

function SceneCompiler:_beginSeal(build)
  local ok, sealJob = pcall(build.buffer.beginSeal, build.buffer, {
    key = build.key,
    generation = build.generation,
    startedAt = build.startedAt,
    completedAt = self._clock(),
    optionalErrors = build.optionalErrors,
  })
  if not ok then return self:_sealFailure(sealJob) end
  if type(sealJob) ~= "table" or type(sealJob.step) ~= "function" then
    return self:_sealFailure(
      "scene buffer beginSeal must return a seal job with step"
    )
  end
  build.sealJob = sealJob
  build.stage = "seal"
end

function SceneCompiler:_stepSeal(build)
  local ok, done, packet = pcall(
    build.sealJob.step,
    build.sealJob,
    SEAL_UNITS_PER_OPERATION
  )
  if not ok then return self:_sealFailure(done) end
  if type(done) ~= "boolean" then
    return self:_sealFailure(
      "scene seal step must return a Boolean completion flag"
    )
  end
  if not done then
    if packet ~= nil then
      return self:_sealFailure(
        "incomplete scene seal step must not return a packet"
      )
    end
    return false
  end
  local valid, err = beginPacketValidation(build, packet)
  if not valid then return self:_sealFailure(err) end
  build.sealJob = nil
  return true
end

function SceneCompiler:_stepValidation(build)
  local validation = build.validation
  for _ = 1, VALIDATION_ENTRIES_PER_OPERATION do
    if validation.stage == "phase_keys" then
      local phase = next(build.packet.phases, validation.phaseKey)
      if phase == nil then
        validation.stage = "commands"
      else
        validation.phaseKey = phase
        if not PACKET_PHASE_SET[phase] then
          return self:_sealFailure(
            "completed scene packet contains an unknown phase"
          )
        end
      end
    elseif validation.items ~= nil then
      local index, item = next(validation.items, validation.itemKey)
      if index == nil then
        if validation.itemCount < 1 then
          return self:_sealFailure(
            "completed scene packet command items must not be empty"
          )
        end
        if validation.maxItemIndex ~= validation.itemCount then
          return self:_sealFailure(
            "completed scene packet command items must be dense"
          )
        end
        validation.items = nil
      else
        validation.itemKey = index
        if type(index) ~= "number" or index ~= index
            or index == math.huge or index == -math.huge
            or index ~= math.floor(index) or index < 1 then
          return self:_sealFailure(
            "completed scene packet item keys must be positive integers"
          )
        end
        if type(item) ~= "table" or getmetatable(item) ~= nil then
          return self:_sealFailure(
            "completed scene packet items must be plain tables"
          )
        end
        validation.itemCount = validation.itemCount + 1
        if validation.itemCount > MAX_COMMAND_ITEMS then
          return self:_sealFailure(
            "completed scene packet command item limit exceeded"
          )
        end
        if index > validation.maxItemIndex then
          validation.maxItemIndex = index
        end
      end
    elseif validation.commands == nil then
      local phase = PACKET_PHASES[validation.phaseIndex]
      if not phase then
        if build.packet.commandCount ~= validation.total then
          return self:_sealFailure(
            "completed scene packet commandCount is invalid"
          )
        end
        if build.packet.drawCalls ~= validation.total then
          return self:_sealFailure(
            "completed scene packet drawCalls is invalid"
          )
        end
        build.validation = nil
        build.cost = 1024
        build.costPhase = 1
        build.costCommand = 1
        build.stage = "cost"
        return true
      end
      local commands = build.packet.phases[phase]
      if type(commands) ~= "table" or getmetatable(commands) ~= nil then
        return self:_sealFailure(
          "completed scene packet is missing a plain phase array: " .. phase
        )
      end
      validation.commands = commands
      validation.commandKey = nil
      validation.commandCount = 0
      validation.maxCommandIndex = 0
    else
      local index, command = next(
        validation.commands,
        validation.commandKey
      )
      if index == nil then
        if validation.maxCommandIndex ~= validation.commandCount then
          return self:_sealFailure(
            "completed scene packet phase arrays must be dense"
          )
        end
        validation.total = validation.total + validation.commandCount
        validation.phaseIndex = validation.phaseIndex + 1
        validation.commands = nil
      else
        validation.commandKey = index
        if type(index) ~= "number" or index ~= math.floor(index)
            or index < 1 or index == math.huge then
          return self:_sealFailure(
            "completed scene packet phase keys must be positive integers"
          )
        end
        if type(command) ~= "table" or getmetatable(command) ~= nil then
          return self:_sealFailure(
            "completed scene packet commands must be plain tables"
          )
        end
        if command.items ~= nil and (type(command.items) ~= "table"
            or getmetatable(command.items) ~= nil) then
          return self:_sealFailure(
            "completed scene packet command items must be plain tables"
          )
        end
        validation.commandCount = validation.commandCount + 1
        if validation.total + validation.commandCount > MAX_PACKET_COMMANDS then
          return self:_sealFailure(
            "completed scene packet command limit exceeded"
          )
        end
        if index > validation.maxCommandIndex then
          validation.maxCommandIndex = index
        end
        if command.items ~= nil then
          validation.items = command.items
          validation.itemKey = nil
          validation.itemCount = 0
          validation.maxItemIndex = 0
        end
      end
    end
  end
  return false
end

function SceneCompiler:_stepCost(build)
  for _ = 1, COST_COMMANDS_PER_OPERATION do
    local phase = PACKET_PHASES[build.costPhase]
    if not phase then
      build.packet.metadata.costBytes = build.cost
      build.stage = "commit"
      return true
    end
    local commands = build.packet.phases[phase] or {}
    local command = commands[build.costCommand]
    if not command then
      build.costPhase = build.costPhase + 1
      build.costCommand = 1
    else
      build.cost = build.cost + 256
      if type(command.items) == "table" then
        build.cost = build.cost + #command.items * 96
      end
      build.costCommand = build.costCommand + 1
    end
  end
  return false
end

function SceneCompiler:_commitPacket(build)
  local packet = build.packet
  local assetScope = build.assetScope
  if assetScope and type(assetScope.used) == "function" and assetScope:used() then
    packet.metadata.cacheable = false
    local released = false
    packet.release = function(_, reason)
      if released then return true end
      released = true
      return assetScope:release(reason or "packet_released")
    end
  elseif assetScope and type(assetScope.release) == "function" then
    assetScope:release("unused_asset_scope")
  end
  local previous = self._active
  self._active = packet
  self._building = nil
  if previous then self:_cachePacket(previous, "replaced") end
  return packet
end

function SceneCompiler:step(budgetMs)
  local build = self._building
  if not build then return false, "idle" end
  budgetMs = tonumber(budgetMs) or 0
  if budgetMs <= 0 then return false, "budget" end
  -- Keep clock, loop-exit, coroutine, and GC-tail overhead inside the public
  -- slice. Small caller budgets retain at least 75% for useful work.
  local guardMs = math.min(BUDGET_GUARD_MS, budgetMs * 0.25)
  local deadline = self._clock() + (budgetMs - guardMs) / 1000
  local resumes = 0
  local operations = 0

  while self._building == build and self._clock() < deadline do
    operations = operations + 1
    if operations > self._maxOperations then return false, "building" end

    if build.stage == "features" then
      local task = build.tasks[build.index]
      if not task then
        self:_beginSeal(build)
      else
        resumes = resumes + 1
        if resumes > self._maxResumes then return false, "resume_limit" end

        local ok, result = coroutine.resume(task.thread)
        if not ok then
          if not self:_failBuild(task, result) then return false, "failed" end
        elseif coroutine.status(task.thread) == "dead" then
          task.done = true
          task.result = result
          build.index = build.index + 1
        end
      end
    elseif build.stage == "seal" then
      self:_stepSeal(build)
    elseif build.stage == "validate" then
      self:_stepValidation(build)
    elseif build.stage == "cost" then
      self:_stepCost(build)
    elseif build.stage == "commit" then
      return true, self:_commitPacket(build)
    else
      error("invalid scene build stage", 2)
    end
  end

  return false, "building"
end

function SceneCompiler:active()
  return self._active
end

local function summarizeCommands(packet)
  if type(packet) ~= "table" or type(packet.phases) ~= "table" then return nil end
  local summary = { commands = 0, batchItems = 0, phases = {}, kinds = {}, owners = {} }
  for phase, commands in pairs(packet.phases) do
    if type(phase) == "string" and type(commands) == "table" then
      for _, command in ipairs(commands) do
        if type(command) == "table" then
          summary.commands = summary.commands + 1
          summary.phases[phase] = (summary.phases[phase] or 0) + 1
          if type(command.kind) == "string" then
            summary.kinds[command.kind] = (summary.kinds[command.kind] or 0) + 1
          end
          if type(command.owner) == "string" then
            summary.owners[command.owner] = (summary.owners[command.owner] or 0) + 1
          end
          if type(command.items) == "table" then
            summary.batchItems = summary.batchItems + #command.items
          end
        end
      end
    end
  end
  return summary
end

function SceneCompiler:status()
  local build = self._building
  local activeMetadata = self._active and self._active.metadata or nil
  local cache
  if self._cache and type(self._cache.stats) == "function" then
    local ok, value = pcall(self._cache.stats, self._cache)
    if ok then cache = value end
  end
  return {
    generation = self._generation,
    activeKey = activeMetadata and activeMetadata.key or nil,
    activeGeneration = activeMetadata and activeMetadata.generation or nil,
    activeDrawCalls = self._active and self._active.drawCalls or nil,
    activeCommands = summarizeCommands(self._active),
    buildingKey = build and build.key or nil,
    buildingStage = build and build.stage or nil,
    buildingFeature = build and build.tasks[build.index]
      and build.tasks[build.index].feature.id or nil,
    lastError = self._lastError,
    cache = cache,
  }
end

function SceneCompiler:invalidate(reason, releaseActive)
  self._generation = self._generation + 1
  self:_cancelBuild(reason or "invalidated")
  if releaseActive and self._active then
    self:_release(self._active, reason or "invalidated")
    self._active = nil
  end
end

function SceneCompiler:dispose()
  self:invalidate("disposed", true)
  if self._cache and self._clearCacheOnDispose and type(self._cache.clear) == "function" then
    local ok, err = pcall(self._cache.clear, self._cache, "compiler_disposed")
    if not ok then
      emitDiagnostic(self._diagnostics, "error", "RENDER.CACHE_CLEAR_FAILED",
        "The scene cache did not clear during disposal.", { error = tostring(err) })
    end
  end
end

SceneCompiler.estimatePacketCost = estimatePacketCost

return SceneCompiler
