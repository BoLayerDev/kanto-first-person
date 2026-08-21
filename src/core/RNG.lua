-- Deterministic xorshift32 RNG. It never changes Lua's global random state.

local RNG = {}
RNG.__index = RNG

local bitlib = bit
assert(bitlib and bitlib.bxor and bitlib.lshift and bitlib.rshift,
  "RNG needs LuaJIT's bit library")

local U32 = 4294967296
local NONZERO_SEED = 1831565813 -- 0x6D2B79F5

local function unsigned(value)
  value = bitlib.tobit(value)
  if value < 0 then return value + U32 end
  return value
end

local function hashString(value)
  local hash = 2166136261
  for i = 1, #value do
    -- 65599 keeps the intermediate below 2^53, so Lua numbers remain exact.
    hash = (hash * 65599 + value:byte(i)) % U32
  end
  return hash
end

local function normalizeSeed(seed)
  local kind = type(seed)
  local value
  if kind == "string" then
    value = hashString(seed)
  elseif kind == "number" and seed == seed
      and seed > -math.huge and seed < math.huge then
    value = math.floor(seed) % U32
  else
    error("RNG seed must be a finite number or string", 3)
  end
  if value == 0 then value = NONZERO_SEED end
  return value
end

local function advance(value)
  local x = bitlib.tobit(value)
  x = bitlib.bxor(x, bitlib.lshift(x, 13))
  x = bitlib.bxor(x, bitlib.rshift(x, 17))
  x = bitlib.bxor(x, bitlib.lshift(x, 5))
  local result = unsigned(x)
  if result == 0 then result = NONZERO_SEED end
  return result
end

function RNG.new(seed)
  if seed == nil then seed = NONZERO_SEED end
  return setmetatable({ _state = normalizeSeed(seed) }, RNG)
end

function RNG:nextU32()
  self._state = advance(self._state)
  return self._state
end

function RNG:number()
  return self:nextU32() / U32
end

function RNG:integer(minimum, maximum)
  assert(type(minimum) == "number" and minimum % 1 == 0,
    "RNG integer minimum must be an integer")
  assert(type(maximum) == "number" and maximum % 1 == 0,
    "RNG integer maximum must be an integer")
  assert(maximum >= minimum, "RNG integer range is reversed")
  local span = maximum - minimum + 1
  assert(span <= U32, "RNG integer range is larger than 2^32")
  local limit = math.floor(U32 / span) * span
  local value
  repeat value = self:nextU32() until value < limit
  return minimum + (value % span)
end

function RNG:chance(probability)
  assert(type(probability) == "number" and probability >= 0 and probability <= 1,
    "RNG probability must be between 0 and 1")
  return self:number() < probability
end

function RNG:choice(values)
  assert(type(values) == "table" and #values > 0, "RNG choice needs a non-empty list")
  return values[self:integer(1, #values)]
end

function RNG:shuffle(values)
  assert(type(values) == "table", "RNG shuffle needs a table")
  for i = #values, 2, -1 do
    local j = self:integer(1, i)
    values[i], values[j] = values[j], values[i]
  end
  return values
end

function RNG:state()
  return self._state
end

function RNG:restore(state)
  self._state = normalizeSeed(state)
  return self
end

function RNG:clone()
  return RNG.new(self._state)
end

function RNG:fork(label)
  local salt = normalizeSeed(label == nil and "" or tostring(label))
  local mixed = unsigned(bitlib.bxor(bitlib.tobit(self._state), bitlib.tobit(salt)))
  return RNG.new(advance(mixed))
end

RNG.hash = hashString
RNG.U32 = U32

return RNG
