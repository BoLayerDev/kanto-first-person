local SceneCompiler = {}
SceneCompiler.__index = SceneCompiler

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
  local buffer = self._newBuffer(context.quality)
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

function SceneCompiler:_commit()
  local build = self._building
  local ok, packet = pcall(build.buffer.seal, build.buffer, {
    key = build.key,
    generation = build.generation,
    startedAt = build.startedAt,
    completedAt = self._clock(),
    optionalErrors = build.optionalErrors,
  })
  if not ok then
    self:_cancelBuild("packet_seal_failed")
    error(packet, 0)
  end
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
  packet.metadata.costBytes = estimatePacketCost(packet)
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
  local deadline = self._clock() + budgetMs / 1000
  local resumes = 0

  while self._building == build and self._clock() <= deadline do
    local task = build.tasks[build.index]
    if not task then
      return true, self:_commit()
    end
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

  return false, "building"
end

function SceneCompiler:active()
  return self._active
end

function SceneCompiler:status()
  local build = self._building
  local cache
  if self._cache and type(self._cache.stats) == "function" then
    local ok, value = pcall(self._cache.stats, self._cache)
    if ok then cache = value end
  end
  return {
    generation = self._generation,
    activeKey = self._active and self._active.metadata and self._active.metadata.key or nil,
    buildingKey = build and build.key or nil,
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
