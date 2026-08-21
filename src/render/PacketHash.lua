-- Deterministic ROM-free regression hash for declarative scene packets.

local PacketHash = {}
local MOD = 65521

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

function PacketHash.hash(value, limits)
  limits = limits or {}
  local maxDepth = tonumber(limits.maxDepth) or 32
  local maxNodes = tonumber(limits.maxNodes) or 100000
  local a, b, nodes = 1, 0, 0
  local active = {}

  local function feed(text)
    for index = 1, #text do
      a = (a + text:byte(index)) % MOD
      b = (b + a) % MOD
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
      local text = string.format("%.17g", item)
      feed("d" .. #text .. ":" .. text .. ";")
      return
    end
    if kind == "string" then feed("s" .. #item .. ":" .. item .. ";"); return end
    if kind ~= "table" then error("packet hash rejects " .. kind, 3) end
    if getmetatable(item) ~= nil then error("packet hash rejects metatables", 3) end
    if depth >= maxDepth then error("packet hash depth limit", 3) end
    if active[item] then error("packet hash rejects cycles", 3) end
    active[item] = true
    local keys = {}
    for key in pairs(item) do
      if type(key) ~= "string" and type(key) ~= "number" then
        active[item] = nil
        error("packet hash rejects non-string and non-number keys", 3)
      end
      keys[#keys + 1] = key
      nodes = nodes + 1
      if nodes > maxNodes then
        active[item] = nil
        error("packet hash node limit", 3)
      end
    end
    table.sort(keys, keyOrder)
    feed("t" .. #keys .. "{")
    for _, key in ipairs(keys) do
      encode(key, depth + 1)
      encode(item[key], depth + 1)
    end
    feed("};")
    active[item] = nil
  end

  encode(value, 0)
  return string.format("%08x", b * 65536 + a)
end

function PacketHash.hashCommand(command)
  if type(command) ~= "table" then error("command hash needs a table", 2) end
  local declarative = {}
  for key, value in pairs(command) do
    if not RUNTIME_FIELDS[key] then declarative[key] = value end
  end
  local first = PacketHash.hash(declarative, { maxDepth = 16, maxNodes = 65536 })
  local second = PacketHash.hash({ domain = "kfp-command-v1", value = declarative }, {
    maxDepth = 17,
    maxNodes = 65540,
  })
  return first .. second
end

return PacketHash
