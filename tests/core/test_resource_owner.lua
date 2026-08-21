return function(T)
  local ResourceOwner = T.loadCore("ResourceOwner")

  T.test("disposes in LIFO order and only once", function()
    local order = {}
    local owner = ResourceOwner.new()
    owner:own({}, function() order[#order + 1] = "first" end)
    owner:own({}, function() order[#order + 1] = "second" end)
    T.truthy(owner:dispose("test"))
    T.deepEqual(order, { "second", "first" })
    T.falsy(owner:dispose("again"))
    T.deepEqual(order, { "second", "first" })
  end)

  T.test("early release and deferred cleanup are idempotent", function()
    local calls = 0
    local resource = {}
    local owner = ResourceOwner.new()
    owner:own(resource, function() calls = calls + 1 end)
    local token = owner:defer(function() calls = calls + 10 end)
    T.truthy(owner:release(resource))
    T.falsy(owner:release(resource))
    T.truthy(owner:release(token))
    owner:dispose()
    T.equal(calls, 11)
  end)

  T.test("transfer moves cleanup responsibility", function()
    local calls = 0
    local resource = {}
    local first, second = ResourceOwner.new(), ResourceOwner.new()
    first:own(resource, function() calls = calls + 1 end)
    T.truthy(first:transfer(resource, second))
    first:dispose()
    T.equal(calls, 0)
    second:dispose()
    T.equal(calls, 1)
  end)

  T.test("children dispose before earlier parent resources", function()
    local order = {}
    local parent = ResourceOwner.new()
    parent:own({}, function() order[#order + 1] = "parent" end)
    local child = assert(parent:child())
    child:own({}, function() order[#order + 1] = "child" end)
    parent:dispose()
    T.deepEqual(order, { "child", "parent" })
  end)

  T.test("cleanup errors do not skip remaining resources", function()
    local calls = 0
    local owner = ResourceOwner.new()
    owner:own({}, function() calls = calls + 1 end)
    owner:own({}, function() calls = calls + 1; error("bad release") end)
    local ok = owner:dispose()
    T.falsy(ok)
    T.equal(calls, 2)
    T.equal(owner:stats().errors, 1)
  end)

  T.test("released history stays bounded and self-transfer is a no-op", function()
    local owner = ResourceOwner.new()
    local kept = { release = function() end }
    owner:own(kept)
    T.truthy(owner:transfer(kept, owner))
    T.equal(owner:count(), 1)

    for _ = 1, 300 do
      local resource = { release = function() end }
      owner:own(resource)
      owner:release(resource)
    end
    T.truthy(owner:stats().orderSlots <= 66)
    T.truthy(owner:release(kept))
    T.equal(owner:count(), 0)
  end)
end
