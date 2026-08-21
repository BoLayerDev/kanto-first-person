return function(T)
  local RNG = T.loadCore("RNG")

  T.test("matches the xorshift32 golden sequence", function()
    local rng = RNG.new(1)
    T.deepEqual({ rng:nextU32(), rng:nextU32(), rng:nextU32(),
      rng:nextU32(), rng:nextU32() },
      { 270369, 67634689, 2647435461, 307599695, 2398689233 })
  end)

  T.test("clone, state, restore, and string seeds are deterministic", function()
    local first, second = RNG.new("PALLET_TOWN"), RNG.new("PALLET_TOWN")
    T.equal(first:nextU32(), second:nextU32())
    local state = first:state()
    local clone = first:clone()
    T.equal(first:nextU32(), clone:nextU32())
    first:restore(state)
    T.equal(first:state(), state)
  end)

  T.test("fork creates stable independent streams without advancing parent", function()
    local parent = RNG.new(99)
    local state = parent:state()
    local a, b = parent:fork("weather"), parent:fork("weather")
    local c = parent:fork("birds")
    T.equal(parent:state(), state)
    T.equal(a:nextU32(), b:nextU32())
    T.notEqual(a:nextU32(), c:nextU32())
  end)

  T.test("bounded integer, chance, choice, and shuffle stay in contract", function()
    local rng = RNG.new(12345)
    for _ = 1, 500 do
      local value = rng:integer(-3, 7)
      T.truthy(value >= -3 and value <= 7 and value % 1 == 0)
    end
    T.falsy(rng:chance(0))
    T.truthy(rng:chance(1))
    T.truthy(rng:choice({ "a", "b", "c" }))
    local values = { 1, 2, 3, 4, 5 }
    T.equal(rng:shuffle(values), values)
    table.sort(values)
    T.deepEqual(values, { 1, 2, 3, 4, 5 })
  end)

  T.test("zero seed is repaired and invalid ranges fail", function()
    T.notEqual(RNG.new(0):state(), 0)
    T.raises(function() RNG.new({}) end, "seed must")
    T.raises(function() RNG.new(1):integer(3, 2) end, "range is reversed")
  end)
end
