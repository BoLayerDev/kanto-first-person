return function(T)
  local LRU = T.loadCore("LRU")

  T.test("evicts least-recently-used entries by total cost", function()
    local released = {}
    local cache = LRU.new({ maxCost = 3,
      release = function(value) released[#released + 1] = value.id end })
    local a, b, c = { id = "a" }, { id = "b" }, { id = "c" }
    assert(cache:put("a", a, 1))
    assert(cache:put("b", b, 1))
    assert(cache:get("a"))
    assert(cache:put("c", c, 2))
    T.deepEqual(cache:keys(), { "c", "a" })
    T.deepEqual(released, { "b" })
    T.equal(cache:stats().cost, 3)
  end)

  T.test("shared values release exactly once after the last key", function()
    local releases = 0
    local value = {}
    local cache = LRU.new({ release = function(v)
      T.equal(v, value)
      releases = releases + 1
    end })
    cache:put("first", value, 1)
    cache:put("second", value, 1)
    cache:remove("first")
    T.equal(releases, 0)
    cache:remove("second")
    T.equal(releases, 1)
    cache:clear()
    T.equal(releases, 1)
  end)

  T.test("replace and oversize rejection transfer release exactly once", function()
    local counts = {}
    local cache = LRU.new({ maxCost = 2, release = function(value)
      counts[value] = (counts[value] or 0) + 1
    end })
    local old, replacement, huge = {}, {}, {}
    cache:put("key", old, 1)
    cache:put("key", replacement, 1)
    local ok, err = cache:put("huge", huge, 3)
    T.falsy(ok)
    T.equal(err, "entry_exceeds_limits")
    cache:clear()
    T.equal(counts[old], 1)
    T.equal(counts[replacement], 1)
    T.equal(counts[huge], 1)
  end)

  T.test("take transfers ownership without release", function()
    local releases = 0
    local cache = LRU.new({ release = function() releases = releases + 1 end })
    local value = {}
    cache:put("key", value, 7)
    local taken, cost = cache:take("key")
    T.equal(taken, value)
    T.equal(cost, 7)
    T.equal(releases, 0)
    T.equal(cache:stats().count, 0)
  end)

  T.test("release failure is recorded and never retried", function()
    local calls = 0
    local cache = LRU.new({ release = function()
      calls = calls + 1
      error("release failed")
    end })
    cache:put("key", {}, 1)
    cache:clear()
    cache:clear()
    T.equal(calls, 1)
    T.equal(cache:stats().releaseErrors, 1)
  end)

  T.test("limit changes validate transactionally", function()
    local cache = LRU.new({ maxCost = 10, maxEntries = 2 })
    T.raises(function() cache:setLimits(5, -1) end, "invalid LRU maxEntries")
    local stats = cache:stats()
    T.equal(stats.maxCost, 10)
    T.equal(stats.maxEntries, 2)
    local nan = 0 / 0
    T.falsy(select(2, cache:get(nan)))
    T.raises(function() cache:put("bad", nan) end,
      "valid ownership key")
  end)
end
