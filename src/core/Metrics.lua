-- Bounded runtime metrics for local performance evidence.
-- Recording reuses fixed-capacity numeric arrays. Snapshot allocation happens
-- only when a caller requests the read-only public status report.

local Metrics = {}
Metrics.__index = Metrics

local SERIES_NAMES = { "update", "build", "render", "sceneReadiness" }

local function defaultClock()
  return os.clock()
end

local function finite(value)
  return type(value) == "number" and value == value
    and value >= 0 and value < math.huge
end

local function newSeries(capacity)
  local values = {}
  for index = 1, capacity do values[index] = 0 end
  return {
    values = values,
    capacity = capacity,
    count = 0,
    cursor = 0,
    totalCount = 0,
    sum = 0,
    latest = 0,
  }
end

local function observe(series, value)
  if not finite(value) then return false, "invalid_value" end
  local cursor = series.cursor % series.capacity + 1
  if series.count == series.capacity then
    series.sum = series.sum - series.values[cursor]
  else
    series.count = series.count + 1
  end
  series.values[cursor] = value
  series.cursor = cursor
  series.totalCount = series.totalCount + 1
  series.sum = series.sum + value
  series.latest = value
  return true
end

local function percentile(series, fraction)
  if series.count == 0 then return 0 end
  local ordered = {}
  for index = 1, series.count do ordered[index] = series.values[index] end
  table.sort(ordered)
  local rank = math.ceil(series.count * fraction)
  if rank < 1 then rank = 1 end
  return ordered[rank]
end

local function seriesSnapshot(series)
  local maximum = 0
  for index = 1, series.count do
    if series.values[index] > maximum then maximum = series.values[index] end
  end
  return {
    retained = series.count,
    total = series.totalCount,
    latest = series.latest,
    mean = series.count > 0 and series.sum / series.count or 0,
    p95 = percentile(series, 0.95),
    p99 = percentile(series, 0.99),
    maximum = maximum,
  }
end

local function copyFields(source, names)
  if type(source) ~= "table" then return nil end
  local result = {}
  for index = 1, #names do
    local name = names[index]
    local value = source[name]
    local kind = type(value)
    if kind == "number" or kind == "string" or kind == "boolean" then
      result[name] = value
    end
  end
  return result
end

function Metrics.new(options)
  options = options or {}
  local capacity = tonumber(options.capacity) or 240
  assert(capacity >= 8 and capacity <= 4096 and capacity % 1 == 0,
    "Metrics capacity must be an integer from 8 through 4096")
  assert(options.clock == nil or type(options.clock) == "function",
    "Metrics clock must be a function")
  local series = {}
  for index = 1, #SERIES_NAMES do
    local name = SERIES_NAMES[index]
    series[name] = newSeries(capacity)
  end
  return setmetatable({
    _clock = options.clock or defaultClock,
    _capacity = capacity,
    _series = series,
    _sceneRequestedAt = nil,
    _sceneRequestedKey = nil,
    _sceneRequests = 0,
    _sceneReady = 0,
    _sceneCacheHits = 0,
    _sceneSuperseded = 0,
    _renderCallbacks = 0,
    _renderSubmissions = 0,
  }, Metrics)
end

function Metrics:now()
  local value = tonumber(self._clock())
  return finite(value) and value or 0
end

function Metrics:recordSeconds(name, seconds)
  local series = self._series[name]
  if not series then return false, "unknown_series" end
  return observe(series, (tonumber(seconds) or -1) * 1000)
end

function Metrics:sceneRequested(key)
  if type(key) ~= "string" or key == "" then return false, "invalid_key" end
  if self._sceneRequestedKey and self._sceneRequestedKey ~= key then
    self._sceneSuperseded = self._sceneSuperseded + 1
  end
  self._sceneRequests = self._sceneRequests + 1
  self._sceneRequestedKey = key
  self._sceneRequestedAt = self:now()
  return true
end

function Metrics:sceneReady(key, cached)
  if key ~= self._sceneRequestedKey or self._sceneRequestedAt == nil then
    return false, "not_pending"
  end
  observe(self._series.sceneReadiness,
    (self:now() - self._sceneRequestedAt) * 1000)
  self._sceneReady = self._sceneReady + 1
  if cached == true then self._sceneCacheHits = self._sceneCacheHits + 1 end
  self._sceneRequestedKey = nil
  self._sceneRequestedAt = nil
  return true
end

function Metrics:rendered(seconds, submissions)
  local ok, err = self:recordSeconds("render", seconds)
  if not ok then return false, err end
  self._renderCallbacks = self._renderCallbacks + 1
  submissions = tonumber(submissions) or 0
  if submissions > 0 then
    self._renderSubmissions = self._renderSubmissions + math.floor(submissions)
  end
  return true
end

function Metrics:snapshot(runtime)
  runtime = type(runtime) == "table" and runtime or {}
  return {
    schema = 1,
    units = { timing = "milliseconds", cacheCost = "bytes" },
    capacity = self._capacity,
    timing = {
      update = seriesSnapshot(self._series.update),
      build = seriesSnapshot(self._series.build),
      render = seriesSnapshot(self._series.render),
    },
    scene = {
      readiness = seriesSnapshot(self._series.sceneReadiness),
      requests = self._sceneRequests,
      ready = self._sceneReady,
      cacheHits = self._sceneCacheHits,
      superseded = self._sceneSuperseded,
      pending = self._sceneRequestedKey ~= nil,
    },
    submissions = {
      callbacks = self._renderCallbacks,
      commands = self._renderSubmissions,
    },
    runtime = {
      quality = type(runtime.quality) == "string" and runtime.quality or nil,
      cache = copyFields(runtime.cache, {
        "count", "cost", "maxCost", "maxEntries", "hits", "misses",
        "puts", "evictions", "releases", "releaseErrors",
      }),
      resources = copyFields(runtime.resources, {
        "active", "releases", "errors", "disposed", "orderSlots",
      }),
      textures = copyFields(runtime.textures, {
        "available", "entries", "references", "capacity", "created",
        "released", "disposed",
      }),
      audio = copyFields(runtime.audio, {
        "available", "stream", "oneShots", "capacity", "created", "dropped",
        "disposed",
      }),
    },
  }
end

return Metrics
