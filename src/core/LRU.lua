-- O(1) cost-aware LRU cache with explicit ownership and exactly-once release.

local LRU = {}
LRU.__index = LRU

local function finiteCost(value)
  return type(value) == "number" and value == value
    and value >= 0 and value < math.huge
end

local function validKey(value)
  return value ~= nil and not (type(value) == "number" and value ~= value)
end

local function defaultRelease(value)
  local kind = type(value)
  if kind ~= "table" and kind ~= "userdata" then return end
  local ok, release = pcall(function() return value.release end)
  if ok and type(release) == "function" then release(value) end
end

local function emit(diagnostics, level, code, message, fields)
  if diagnostics and type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

function LRU.new(opts)
  opts = opts or {}
  local maxCost = opts.maxCost
  if maxCost == nil then maxCost = math.huge end
  local maxEntries = opts.maxEntries
  if maxEntries == nil then maxEntries = math.huge end
  assert((maxCost == math.huge) or finiteCost(maxCost),
    "LRU maxCost must be nonnegative")
  assert((maxEntries == math.huge) or
    (type(maxEntries) == "number" and maxEntries >= 0 and maxEntries % 1 == 0),
    "LRU maxEntries must be a nonnegative integer")
  assert(opts.costOf == nil or type(opts.costOf) == "function",
    "LRU costOf must be a function")
  assert(opts.release == nil or type(opts.release) == "function",
    "LRU release must be a function")
  assert(opts.onEvict == nil or type(opts.onEvict) == "function",
    "LRU onEvict must be a function")
  return setmetatable({
    maxCost = maxCost,
    maxEntries = maxEntries,
    costOf = opts.costOf or function() return 1 end,
    release = opts.release or defaultRelease,
    onEvict = opts.onEvict,
    diagnostics = opts.diagnostics,
    entries = {},
    refs = {},
    head = nil,
    tail = nil,
    count = 0,
    cost = 0,
    counters = { hits = 0, misses = 0, puts = 0, evictions = 0,
                 releases = 0, releaseErrors = 0 },
  }, LRU)
end

function LRU:_detach(entry)
  if entry.previous then entry.previous.next = entry.next else self.head = entry.next end
  if entry.next then entry.next.previous = entry.previous else self.tail = entry.previous end
  entry.previous, entry.next = nil, nil
end

function LRU:_attachHead(entry)
  entry.previous = nil
  entry.next = self.head
  if self.head then self.head.previous = entry else self.tail = entry end
  self.head = entry
end

function LRU:_touch(entry)
  if self.head == entry then return end
  self:_detach(entry)
  self:_attachHead(entry)
end

function LRU:_retain(value)
  local ref = self.refs[value]
  if not ref then
    ref = { count = 0, released = false }
    self.refs[value] = ref
  end
  ref.count = ref.count + 1
end

function LRU:_releaseRef(value, reason, key)
  local ref = self.refs[value]
  if not ref then return true end
  ref.count = ref.count - 1
  if ref.count > 0 then return true end
  self.refs[value] = nil
  if ref.released then return true end
  ref.released = true -- Set before user code, including re-entrant code.
  self.counters.releases = self.counters.releases + 1
  local ok, err = pcall(self.release, value, reason, key)
  if not ok then
    self.counters.releaseErrors = self.counters.releaseErrors + 1
    emit(self.diagnostics, "error", "CORE.LRU_RELEASE_FAILED", tostring(err),
      { key = tostring(key), reason = tostring(reason) })
    return false, err
  end
  return true
end

function LRU:_removeEntry(entry, reason, releaseValue)
  if entry.removed then return false end
  entry.removed = true
  self:_detach(entry)
  self.entries[entry.key] = nil
  self.count = self.count - 1
  self.cost = self.cost - entry.cost
  if self.cost < 0 and self.cost > -1e-9 then self.cost = 0 end

  if releaseValue ~= false then self:_releaseRef(entry.value, reason, entry.key) end
  if type(self.onEvict) == "function" then
    local ok, err = pcall(self.onEvict, entry.key, entry.value, reason)
    if not ok then
      emit(self.diagnostics, "warn", "CORE.LRU_EVICT_CALLBACK_FAILED",
        tostring(err), { key = tostring(entry.key) })
    end
  end
  return true
end

function LRU:_trim(reason)
  local removed = 0
  while self.tail and (self.cost > self.maxCost or self.count > self.maxEntries) do
    local entry = self.tail
    self:_removeEntry(entry, reason or "capacity", true)
    self.counters.evictions = self.counters.evictions + 1
    removed = removed + 1
  end
  return removed
end

function LRU:put(key, value, cost)
  assert(validKey(key), "LRU key must be a valid table key")
  assert(validKey(value),
    "LRU value must be a valid ownership key")
  if cost == nil then cost = self.costOf(value, key) end
  assert(finiteCost(cost), "LRU entry cost must be finite and nonnegative")

  local entry = self.entries[key]
  if entry and entry.value == value then
    self.cost = self.cost - entry.cost + cost
    entry.cost = cost
    self:_touch(entry)
    self.counters.puts = self.counters.puts + 1
    self:_trim("capacity")
    return self.entries[key] == entry,
      self.entries[key] == entry and nil or "entry_exceeds_limits"
  end

  if entry then self:_removeEntry(entry, "replaced", true) end
  entry = { key = key, value = value, cost = cost, removed = false }
  self.entries[key] = entry
  self:_retain(value)
  self:_attachHead(entry)
  self.count = self.count + 1
  self.cost = self.cost + cost
  self.counters.puts = self.counters.puts + 1
  self:_trim("capacity")
  if self.entries[key] ~= entry then return false, "entry_exceeds_limits" end
  return true
end

function LRU:get(key)
  if not validKey(key) then return nil, false end
  local entry = self.entries[key]
  if not entry then
    self.counters.misses = self.counters.misses + 1
    return nil, false
  end
  self.counters.hits = self.counters.hits + 1
  self:_touch(entry)
  return entry.value, true
end

function LRU:peek(key)
  if not validKey(key) then return nil, false end
  local entry = self.entries[key]
  if not entry then return nil, false end
  return entry.value, true
end

function LRU:remove(key, reason)
  if not validKey(key) then return false, "invalid_key" end
  local entry = self.entries[key]
  if not entry then return false, "missing" end
  self:_removeEntry(entry, reason or "removed", true)
  return true
end

-- Transfer the only cache-held reference to the caller without releasing it.
function LRU:take(key)
  if not validKey(key) then return nil, "invalid_key" end
  local entry = self.entries[key]
  if not entry then return nil, "missing" end
  local ref = self.refs[entry.value]
  if not ref or ref.count ~= 1 then return nil, "shared_value" end
  self.refs[entry.value] = nil
  self:_removeEntry(entry, "taken", false)
  return entry.value, entry.cost
end

function LRU:setLimits(maxCost, maxEntries)
  local nextCost = maxCost == nil and self.maxCost or maxCost
  local nextEntries = maxEntries == nil and self.maxEntries or maxEntries
  assert(nextCost == math.huge or finiteCost(nextCost), "invalid LRU maxCost")
  assert(nextEntries == math.huge or
    (type(nextEntries) == "number" and nextEntries >= 0
      and nextEntries % 1 == 0), "invalid LRU maxEntries")
  self.maxCost, self.maxEntries = nextCost, nextEntries
  return self:_trim("limits_changed")
end

function LRU:clear(reason)
  local entry = self.head
  local removed = 0
  while entry do
    local nextEntry = entry.next
    self:_removeEntry(entry, reason or "cleared", true)
    removed = removed + 1
    entry = nextEntry
  end
  return removed
end

function LRU:keys()
  local out, entry = {}, self.head
  while entry do
    out[#out + 1] = entry.key
    entry = entry.next
  end
  return out
end

function LRU:stats()
  local out = {}
  for key, value in pairs(self.counters) do out[key] = value end
  out.count, out.cost = self.count, self.cost
  out.maxCost, out.maxEntries = self.maxCost, self.maxEntries
  return out
end

return LRU
