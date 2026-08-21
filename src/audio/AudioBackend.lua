-- Bounded, extension-owned LÖVE audio backend.
--
-- The composition root injects source creation and a ResourceOwner. This
-- module never reads a path, global, or host facade. It keeps at most one
-- streaming bed and a fixed one-shot pool.

local AudioBackend = {}
AudioBackend.__index = AudioBackend

local function emit(self, level, code, message, fields)
  local diagnostics = self._diagnostics
  if diagnostics and type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

local function validAsset(path)
  return type(path) == "string" and path:match("^assets/") ~= nil
    and not path:find("..", 1, true)
    and not path:find("\\", 1, true)
end

local function volume(value)
  value = tonumber(value) or 0
  if value ~= value then return 0 end
  return math.max(0, math.min(1, value))
end

local function call(source, name, ...)
  local ok, method = pcall(function() return source and source[name] end)
  if not ok or type(method) ~= "function" then return nil, "method_unavailable" end
  local called, first, second = pcall(method, source, ...)
  if not called then return nil, tostring(first) end
  return first == nil and true or first, second
end

local function stopped(source)
  local playing, err = call(source, "isPlaying")
  if playing == nil and err == "method_unavailable" then return true end
  return playing ~= true
end

function AudioBackend.new(options)
  options = options or {}
  if type(options.owner) ~= "table" or type(options.owner.own) ~= "function"
      or type(options.owner.release) ~= "function" then
    error("AudioBackend needs a ResourceOwner", 2)
  end
  local maxOneShots = math.floor(tonumber(options.maxOneShots) or 8)
  if maxOneShots < 1 or maxOneShots > 32 then
    error("AudioBackend maxOneShots must be 1..32", 2)
  end
  return setmetatable({
    _owner = options.owner,
    _newSource = type(options.newSource) == "function" and options.newSource or nil,
    _diagnostics = options.diagnostics,
    _maxOneShots = maxOneShots,
    _stream = nil,
    _oneShots = {},
    _sequence = 0,
    _disposed = false,
    _created = 0,
    _dropped = 0,
  }, AudioBackend)
end

function AudioBackend:_release(record, reason)
  if not record or record.released then return true end
  record.released = true
  local released, err = self._owner:release(record.source, reason or "audio_release")
  if not released and err ~= "not_owned" then
    emit(self, "error", "AUDIO.RELEASE_FAILED", "An audio source could not be released.", {
      error = tostring(err),
      path = record.path,
    })
    return false, err
  end
  return true
end

function AudioBackend:_create(path, sourceType)
  if self._disposed then return nil, "audio_backend_disposed" end
  if not validAsset(path) then return nil, "invalid_asset_path" end
  if not self._newSource then return nil, "audio_unavailable" end
  local ok, source, err = pcall(self._newSource, path, sourceType)
  if not ok or source == nil then
    local problem = ok and err or source
    emit(self, "warn", "AUDIO.SOURCE_CREATE_FAILED", "An audio source could not be created.", {
      path = path,
      sourceType = sourceType,
      error = tostring(problem),
    })
    return nil, tostring(problem or "source_create_failed")
  end
  local owned, ownError = self._owner:own(source, function(value)
    call(value, "stop")
    call(value, "release")
  end, "audio:" .. path)
  if not owned then return nil, tostring(ownError) end
  self._created = self._created + 1
  return { source = source, path = path, released = false, last = 0 }
end

function AudioBackend:available()
  return not self._disposed and self._newSource ~= nil
end

function AudioBackend:playStream(key, path, initialVolume)
  if type(key) ~= "string" or key == "" then return nil, "invalid_stream_key" end
  local record = self._stream
  if record and (record.key ~= key or record.path ~= path) then
    self:_release(record, "stream_replaced")
    self._stream = nil
    record = nil
  end
  if not record then
    local created, err = self:_create(path, "stream")
    if not created then return nil, err end
    record = created
    record.key = key
    self._stream = record
    call(record.source, "setLooping", true)
  end
  local ok, err = call(record.source, "setVolume", volume(initialVolume))
  if not ok then return nil, err end
  ok, err = call(record.source, "play")
  if not ok then return nil, err end
  return true
end

function AudioBackend:setVolume(key, value)
  local record = self._stream
  if not record or record.key ~= key then return nil, "stream_not_found" end
  return call(record.source, "setVolume", volume(value))
end

function AudioBackend:stop(key)
  local record = self._stream
  if not record or (key ~= nil and record.key ~= key) then return nil, "stream_not_found" end
  self._stream = nil
  return self:_release(record, "stream_stopped")
end

local function removeRecord(records, target)
  for index = #records, 1, -1 do
    if records[index] == target then
      table.remove(records, index)
      return true
    end
  end
  return false
end

function AudioBackend:playOneShot(key, path, shotVolume)
  if type(key) ~= "string" or key == "" then return nil, "invalid_one_shot_key" end
  if not validAsset(path) then return nil, "invalid_asset_path" end
  local record
  for _, candidate in ipairs(self._oneShots) do
    if candidate.path == path and stopped(candidate.source) then
      record = candidate
      break
    end
  end
  if not record and #self._oneShots >= self._maxOneShots then
    for _, candidate in ipairs(self._oneShots) do
      if stopped(candidate.source) and (not record or candidate.last < record.last) then
        record = candidate
      end
    end
    if record then
      removeRecord(self._oneShots, record)
      self:_release(record, "one_shot_evicted")
      record = nil
    else
      self._dropped = self._dropped + 1
      emit(self, "warn", "AUDIO.ONE_SHOT_POOL_BUSY",
        "The bounded one-shot pool is busy; one sound was dropped.", {
          key = key,
          capacity = self._maxOneShots,
        })
      return nil, "one_shot_pool_busy"
    end
  end
  if not record then
    local created, err = self:_create(path, "static")
    if not created then return nil, err end
    record = created
    self._oneShots[#self._oneShots + 1] = record
    call(record.source, "setLooping", false)
  end
  self._sequence = self._sequence + 1
  record.key, record.last = key, self._sequence
  call(record.source, "stop")
  local ok, err = call(record.source, "setVolume", volume(shotVolume))
  if not ok then return nil, err end
  ok, err = call(record.source, "play")
  if not ok then return nil, err end
  return true
end

function AudioBackend:dispose(reason)
  if self._disposed then return true end
  self._disposed = true
  if self._stream then self:_release(self._stream, reason or "audio_disposed") end
  self._stream = nil
  for _, record in ipairs(self._oneShots) do
    self:_release(record, reason or "audio_disposed")
  end
  self._oneShots = {}
  return true
end

function AudioBackend:status()
  return {
    available = self:available(),
    stream = self._stream and self._stream.key or nil,
    oneShots = #self._oneShots,
    capacity = self._maxOneShots,
    created = self._created,
    dropped = self._dropped,
    disposed = self._disposed,
  }
end

return AudioBackend
