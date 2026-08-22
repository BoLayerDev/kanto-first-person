-- Deterministic ROM-free regression hash for declarative scene packets.

local PacketHash = {}
local MOD = 65521
local FEED_CHUNK_BYTES = 64
local SMALL_SORT_KEYS = 32
local MAX_CACHED_STRING_LENGTH = 64
local MAX_STRING_FRAMES = 256
local MAX_KEY_LAYOUTS = 64
local MAX_LAYOUTS_PER_COUNT = 8
local MAX_LAYOUT_KEYS = 16
local COMMAND_DOMAIN_PREFIX = "t2{s6:domain;s14:kfp-command-v1;s5:value;"
local TABLE_SUFFIX = "};"

local RUNTIME_FIELDS = {
  cacheKey = true,
  schemaVersion = true,
  sequence = true,
  texture = true,
  mesh = true,
  resource = true,
  model = true,
}

local function finite(value)
  return type(value) == "number" and value == value
    and value ~= math.huge and value ~= -math.huge
end

local function keyOrder(a, b)
  local ta, tb = type(a), type(b)
  if ta ~= tb then return ta < tb end
  if ta == "number" then return a < b end
  return tostring(a) < tostring(b)
end

local function boundedUnits(value)
  value = tonumber(value) or 1
  if value ~= value or value == math.huge or value == -math.huge
      or value ~= math.floor(value) or value < 1 then
    error("hash step units must be a positive integer", 3)
  end
  return value
end

local function feedState(state, text, checkpoint)
  local a, b = state.a, state.b
  local first = 1
  while first <= #text do
    local last = checkpoint
      and math.min(#text, first + FEED_CHUNK_BYTES - 1)
      or #text
    for index = first, last do
      a = (a + text:byte(index)) % MOD
      b = (b + a) % MOD
    end
    first = last + 1
    if checkpoint then checkpoint() end
  end
  state.a, state.b = a, b
end

local function stateDigest(state)
  return string.format("%08x", state.b * 65536 + state.a)
end

local function sortedKeys(keys, dense, maxIndex, checkpoint)
  if not checkpoint then
    table.sort(keys, keyOrder)
    return keys
  end

  local count = #keys
  if dense and maxIndex == count then
    -- A dense positive-integer key set is exactly 1..count. Rebuild it in
    -- deterministic order without an O(n log n) sort.
    for index = 1, count do
      keys[index] = index
      checkpoint()
    end
    return keys
  end
  if count <= SMALL_SORT_KEYS then
    table.sort(keys, keyOrder)
    checkpoint()
    return keys
  end

  local source, target = keys, {}
  local width = 1
  while width < count do
    local left = 1
    while left <= count do
      local middle = math.min(left + width - 1, count)
      local right = math.min(left + width * 2 - 1, count)
      local first, second = left, middle + 1
      for output = left, right do
        local takeFirst = second > right
          or (first <= middle and keyOrder(source[first], source[second]))
        if takeFirst then
          target[output] = source[first]
          first = first + 1
        else
          target[output] = source[second]
          second = second + 1
        end
        checkpoint()
      end
      left = left + width * 2
    end
    source, target = target, source
    width = width * 2
  end
  return source
end

local function hashValue(value, limits, checkpoint, captureState)
  limits = limits or {}
  local maxDepth = tonumber(limits.maxDepth) or 32
  local maxNodes = tonumber(limits.maxNodes) or 100000
  local a, b, nodes = 1, 0, 0
  local byteCount = 0
  local active = {}
  local keyPools = {}
  local stringFrames = {}
  local stringFrameCount = 0
  local keyLayouts = {}
  local keyLayoutCount = 0

  local function stringFrame(text)
    if #text <= MAX_CACHED_STRING_LENGTH then
      local cached = stringFrames[text]
      if cached then return cached end
      local frame = "s" .. #text .. ":" .. text .. ";"
      if stringFrameCount < MAX_STRING_FRAMES then
        stringFrames[text] = frame
        stringFrameCount = stringFrameCount + 1
      end
      return frame
    end
    return "s" .. #text .. ":" .. text .. ";"
  end

  local function cachedSortedKeys(item, keys, dense, maxIndex)
    local count = #keys
    local cacheable = not dense and count >= 2 and count <= MAX_LAYOUT_KEYS
    local layouts = cacheable and keyLayouts[count] or nil
    if layouts then
      for layoutIndex = 1, #layouts do
        local layout = layouts[layoutIndex]
        local matches = true
        for keyIndex = 1, count do
          -- Enrollment below guarantees that every cached key is a string.
          -- Equal count plus raw presence of every key proves the exact set.
          if rawget(item, layout[keyIndex]) == nil then matches = false end
          if not matches then break end
        end
        -- Layouts are capped at 16 keys, below the existing small-sort work
        -- bound, so one checkpoint keeps incremental work bounded.
        if checkpoint then checkpoint() end
        if matches then return layout end
      end
    end

    local sorted = sortedKeys(keys, dense, maxIndex, checkpoint)
    if not cacheable or keyLayoutCount >= MAX_KEY_LAYOUTS then return sorted end
    layouts = layouts or {}
    if #layouts >= MAX_LAYOUTS_PER_COUNT then return sorted end
    for index = 1, count do
      if type(sorted[index]) ~= "string" then return sorted end
    end
    local layout = {}
    for index = 1, count do layout[index] = sorted[index] end
    layouts[#layouts + 1] = layout
    keyLayouts[count] = layouts
    keyLayoutCount = keyLayoutCount + 1
    if checkpoint then checkpoint() end
    return sorted
  end

  local feed
  if captureState then
    feed = function(text)
      byteCount = (byteCount + #text) % MOD
      local first = 1
      while first <= #text do
        local last = checkpoint
          and math.min(#text, first + FEED_CHUNK_BYTES - 1)
          or #text
        for index = first, last do
          a = (a + text:byte(index)) % MOD
          b = (b + a) % MOD
        end
        first = last + 1
        if checkpoint then checkpoint() end
      end
    end
  else
    feed = function(text)
      local first = 1
      while first <= #text do
        local last = checkpoint
          and math.min(#text, first + FEED_CHUNK_BYTES - 1)
          or #text
        for index = first, last do
          a = (a + text:byte(index)) % MOD
          b = (b + a) % MOD
        end
        first = last + 1
        if checkpoint then checkpoint() end
      end
    end
  end

  local encode
  encode = function(item, depth)
    local kind = type(item)
    if kind == "nil" then feed("n;"); return end
    if kind == "boolean" then feed(item and "b1;" or "b0;"); return end
    if kind == "number" then
      if not finite(item) then error("packet hash rejects non-finite numbers", 3) end
      if item == 0 then item = 0 end
      local number = string.format("%.17g", item)
      feed("d" .. #number .. ":" .. number .. ";")
      return
    end
    if kind == "string" then feed(stringFrame(item)); return end
    if kind ~= "table" then error("packet hash rejects " .. kind, 3) end
    if getmetatable(item) ~= nil then error("packet hash rejects metatables", 3) end
    if depth >= maxDepth then error("packet hash depth limit", 3) end
    if active[item] then error("packet hash rejects cycles", 3) end
    active[item] = true
    local keys = keyPools[depth]
    if keys then
      for index = #keys, 1, -1 do keys[index] = nil end
    else
      keys = {}
      keyPools[depth] = keys
    end
    local dense, maxIndex = true, 0
    for key in next, item do
      if type(key) ~= "string" and type(key) ~= "number" then
        active[item] = nil
        error("packet hash rejects non-string and non-number keys", 3)
      end
      keys[#keys + 1] = key
      if type(key) ~= "number" or not finite(key) or key ~= math.floor(key)
          or key < 1 then
        dense = false
      elseif key > maxIndex then
        maxIndex = key
      end
      nodes = nodes + 1
      if nodes > maxNodes then
        active[item] = nil
        error("packet hash node limit", 3)
      end
      if checkpoint then checkpoint() end
    end
    keys = cachedSortedKeys(item, keys, dense, maxIndex)
    feed("t" .. #keys .. "{")
    for _, key in ipairs(keys) do
      encode(key, depth + 1)
      encode(rawget(item, key), depth + 1)
    end
    feed(TABLE_SUFFIX)
    active[item] = nil
  end

  encode(value, 0)
  local digest = string.format("%08x", b * 65536 + a)
  if captureState then return digest, a, b, byteCount end
  return digest
end

local function appendPrimaryState(state, primaryA, primaryB, byteCount)
  -- Adler composition for the same payload hashed from two initial states:
  -- A2 = A0 + (A1 - 1)
  -- B2 = B0 + B1 + length * (A0 - 1), all modulo 65521.
  -- byteCount is already reduced modulo MOD, which also keeps multiplication
  -- exactly representable under LuaJIT's number semantics.
  local initialA = state.a
  state.a = (initialA + primaryA - 1) % MOD
  state.b = (state.b + primaryB
    + byteCount * ((initialA - 1) % MOD)) % MOD
end

local function hashDeclarativeCommand(declarative, checkpoint)
  local second = { a = 1, b = 0 }
  feedState(second, COMMAND_DOMAIN_PREFIX, checkpoint)
  local first, primaryA, primaryB, byteCount = hashValue(declarative, {
    maxDepth = 16,
    maxNodes = 65536,
  }, checkpoint, true)
  appendPrimaryState(second, primaryA, primaryB, byteCount)
  feedState(second, TABLE_SUFFIX, checkpoint)
  return first .. stateDigest(second)
end

local IncrementalJob = {}
IncrementalJob.__index = IncrementalJob

local function newIncrementalJob(run)
  local thread = coroutine.create(function(initialUnits)
    local allowance = boundedUnits(initialUnits)
    local function checkpoint()
      allowance = allowance - 1
      if allowance <= 0 then
        allowance = boundedUnits(coroutine.yield())
      end
    end
    return run(checkpoint)
  end)
  return setmetatable({
    thread = thread,
    done = false,
    result = nil,
  }, IncrementalJob)
end

function IncrementalJob:step(maxUnits)
  if self.done then return true, self.result end
  maxUnits = boundedUnits(maxUnits)
  local ok, value = coroutine.resume(self.thread, maxUnits)
  if not ok then error(value, 2) end
  if coroutine.status(self.thread) == "dead" then
    self.done = true
    self.result = value
    self.thread = nil
  end
  return self.done, self.result
end

function PacketHash.newJob(value, limits)
  return newIncrementalJob(function(checkpoint)
    return hashValue(value, limits, checkpoint)
  end)
end

function PacketHash.hash(value, limits)
  return hashValue(value, limits, nil)
end

local function declarativeCommand(command, checkpoint)
  if type(command) ~= "table" then error("command hash needs a table", 2) end
  local declarative = {}
  for key, value in next, command do
    if not rawget(RUNTIME_FIELDS, key) then declarative[key] = value end
    if checkpoint then checkpoint() end
  end
  return declarative
end

function PacketHash.newCommandHashJob(command)
  if type(command) ~= "table" then error("command hash needs a table", 2) end
  return newIncrementalJob(function(checkpoint)
    local declarative = declarativeCommand(command, checkpoint)
    return hashDeclarativeCommand(declarative, checkpoint)
  end)
end

function PacketHash.hashCommand(command)
  local declarative = declarativeCommand(command, nil)
  return hashDeclarativeCommand(declarative, nil)
end

return PacketHash
