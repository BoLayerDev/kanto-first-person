-- Structured, bounded, rate-limited diagnostics.

local Diagnostics = {}
Diagnostics.__index = Diagnostics

local LEVELS = { debug = 10, info = 20, warn = 30, error = 40 }
local DEFAULT_MAX_MESSAGE_BYTES = 2048
local DEFAULT_MAX_FIELD_BYTES = 256
local DEFAULT_MAX_FIELDS = 16
local DEFAULT_MAX_KEY_BYTES = 128

local function finiteNumber(value)
  return type(value) == "number" and value == value
    and value > -math.huge and value < math.huge
end

local function trim(value, limit)
  if #value <= limit then return value, false end
  if limit <= 3 then return value:sub(1, limit), true end
  return value:sub(1, limit - 3) .. "...", true
end

local function copyFields(fields, maxFields, maxBytes)
  if fields == nil then return {} end
  assert(type(fields) == "table", "diagnostic fields must be a table")
  local out, visited, truncated = {}, 0, false
  for key, value in pairs(fields) do
    if visited >= maxFields then
      truncated = true
      break
    end
    visited = visited + 1
    local keyType = type(key)
    if keyType == "string" or keyType == "number" or keyType == "boolean" then
      local label, keyTruncated = trim(tostring(key), maxBytes)
      truncated = truncated or keyTruncated
      local kind = type(value)
      if kind == "string" then
        local valueTruncated
        value, valueTruncated = trim(value, maxBytes)
        truncated = truncated or valueTruncated
      elseif kind == "number" then
        if not finiteNumber(value) then value = tostring(value) end
      elseif kind ~= "boolean" and value ~= nil then
        value = "<" .. kind .. ">"
      end
      if value ~= nil then
        out[label] = value
      end
    else
      truncated = true
    end
  end
  return out, truncated
end

local function cloneEntry(entry)
  local out = {}
  for key, value in pairs(entry) do
    if key ~= "fields" then out[key] = value end
  end
  out.fields = {}
  for key, value in pairs(entry.fields) do out.fields[key] = value end
  return out
end

local function validCode(code)
  if type(code) ~= "string" or code == "" or #code > 96
      or not code:find(".", 1, true)
      or code:sub(1, 1) == "." or code:sub(-1) == "."
      or code:find("..", 1, true) or code:find("[^A-Z0-9_%.]") then
    return false
  end
  for segment in code:gmatch("[^.]+") do
    if not segment:match("^[A-Z][A-Z0-9_]*$") then return false end
  end
  return true
end

function Diagnostics.new(opts)
  opts = opts or {}
  local capacity = math.floor(tonumber(opts.capacity) or 128)
  local rate = tonumber(opts.rate)
  if rate == nil then rate = 2 end
  local burst = math.floor(tonumber(opts.burst) or 5)
  local maxKeys = math.floor(tonumber(opts.maxKeys) or 128)
  local maxMessageBytes = math.floor(tonumber(opts.maxMessageBytes)
    or DEFAULT_MAX_MESSAGE_BYTES)
  local maxFieldBytes = math.floor(tonumber(opts.maxFieldBytes)
    or DEFAULT_MAX_FIELD_BYTES)
  local maxFields = math.floor(tonumber(opts.maxFields) or DEFAULT_MAX_FIELDS)
  local maxKeyBytes = math.floor(tonumber(opts.maxKeyBytes)
    or DEFAULT_MAX_KEY_BYTES)
  assert(capacity > 0, "Diagnostics capacity must be positive")
  assert(finiteNumber(rate) and rate >= 0, "Diagnostics rate must be nonnegative")
  assert(burst > 0, "Diagnostics burst must be positive")
  assert(maxKeys > 0, "Diagnostics maxKeys must be positive")
  assert(maxMessageBytes > 0, "Diagnostics maxMessageBytes must be positive")
  assert(maxFieldBytes > 0, "Diagnostics maxFieldBytes must be positive")
  assert(maxFields > 0, "Diagnostics maxFields must be positive")
  assert(maxKeyBytes > 0, "Diagnostics maxKeyBytes must be positive")
  assert(opts.sink == nil or type(opts.sink) == "function",
    "Diagnostics sink must be a function")
  local clock = opts.clock or (os and os.clock)
  assert(type(clock) == "function", "Diagnostics needs a clock")

  return setmetatable({
    capacity = capacity,
    rate = rate,
    burst = burst,
    maxKeys = maxKeys,
    maxMessageBytes = maxMessageBytes,
    maxFieldBytes = maxFieldBytes,
    maxFields = maxFields,
    maxKeyBytes = maxKeyBytes,
    clock = clock,
    sink = opts.sink,
    entries = {},
    start = 1,
    size = 0,
    sequence = 0,
    buckets = {},
    bucketCount = 0,
    totals = { emitted = 0, suppressed = 0, sinkErrors = 0 },
  }, Diagnostics)
end

function Diagnostics:_push(entry)
  local index
  if self.size < self.capacity then
    index = ((self.start - 1 + self.size) % self.capacity) + 1
    self.size = self.size + 1
  else
    index = self.start
    self.start = (self.start % self.capacity) + 1
  end
  self.entries[index] = entry
  self.totals.emitted = self.totals.emitted + 1
  if self.sink then
    local ok = pcall(self.sink, cloneEntry(entry))
    if not ok then self.totals.sinkErrors = self.totals.sinkErrors + 1 end
  end
end

function Diagnostics:_bucket(key, now)
  local bucket = self.buckets[key]
  if bucket then return bucket end
  if self.bucketCount >= self.maxKeys then
    local oldestKey, oldestTime
    for candidate, value in pairs(self.buckets) do
      if oldestTime == nil or value.touched < oldestTime
          or (value.touched == oldestTime and candidate < oldestKey) then
        oldestKey, oldestTime = candidate, value.touched
      end
    end
    if oldestKey then
      self.buckets[oldestKey] = nil
      self.bucketCount = self.bucketCount - 1
    end
  end
  bucket = { tokens = self.burst, at = now, touched = now, suppressed = 0 }
  self.buckets[key] = bucket
  self.bucketCount = self.bucketCount + 1
  return bucket
end

function Diagnostics:emit(level, code, message, fields, opts)
  assert(LEVELS[level], "unknown diagnostic level: " .. tostring(level))
  assert(validCode(code), "invalid diagnostic code: " .. tostring(code))
  assert(type(message) == "string", "diagnostic message must be a string")
  opts = opts or {}

  local now = tonumber(self.clock()) or 0
  local key = opts.key or (level .. ":" .. code)
  assert(type(key) == "string" and key ~= "" and #key <= self.maxKeyBytes,
    "diagnostic rate-limit key must be a bounded string")
  local bucket = self:_bucket(key, now)
  local elapsed = math.max(0, now - bucket.at)
  bucket.tokens = math.min(self.burst, bucket.tokens + elapsed * self.rate)
  bucket.at, bucket.touched = now, now

  if not opts.force and bucket.tokens < 1 then
    bucket.suppressed = bucket.suppressed + 1
    self.totals.suppressed = self.totals.suppressed + 1
    return nil, "rate_limited"
  end
  if not opts.force then bucket.tokens = bucket.tokens - 1 end

  self.sequence = self.sequence + 1
  local boundedMessage, messageTruncated = trim(message, self.maxMessageBytes)
  local boundedFields, fieldsTruncated = copyFields(fields, self.maxFields,
    self.maxFieldBytes)
  local entry = {
    sequence = self.sequence,
    time = now,
    level = level,
    severity = LEVELS[level],
    code = code,
    message = boundedMessage,
    fields = boundedFields,
  }
  if messageTruncated then entry.messageTruncated = true end
  if fieldsTruncated then entry.fieldsTruncated = true end
  if bucket.suppressed > 0 then
    entry.suppressed = bucket.suppressed
    bucket.suppressed = 0
  end
  self:_push(entry)
  return cloneEntry(entry)
end

for level in pairs(LEVELS) do
  local captured = level
  Diagnostics[level] = function(self, code, message, fields, opts)
    return self:emit(captured, code, message, fields, opts)
  end
end

function Diagnostics:snapshot(minLevel)
  local threshold = minLevel and assert(LEVELS[minLevel], "unknown minimum level") or 0
  local out = {}
  for offset = 0, self.size - 1 do
    local index = ((self.start + offset - 1) % self.capacity) + 1
    local entry = self.entries[index]
    if entry and entry.severity >= threshold then
      out[#out + 1] = cloneEntry(entry)
    end
  end
  return out
end

function Diagnostics:clear()
  self.entries, self.start, self.size = {}, 1, 0
end

function Diagnostics:stats()
  return {
    emitted = self.totals.emitted,
    suppressed = self.totals.suppressed,
    sinkErrors = self.totals.sinkErrors,
    retained = self.size,
    capacity = self.capacity,
    keys = self.bucketCount,
    maxMessageBytes = self.maxMessageBytes,
    maxFields = self.maxFields,
  }
end

Diagnostics.LEVELS = LEVELS
Diagnostics.validCode = validCode

return Diagnostics
