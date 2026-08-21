return function(T)
  local Lifecycle = T.loadCore("Lifecycle")

  T.test("runs ordered start and update with reverse invalidation and stop", function()
    local order = {}
    local function component(id)
      return {
        id = id,
        start = function() order[#order + 1] = "start:" .. id end,
        update = function() order[#order + 1] = "update:" .. id end,
        invalidate = function() order[#order + 1] = "invalidate:" .. id end,
        stop = function() order[#order + 1] = "stop:" .. id end,
      }
    end
    local lifecycle = Lifecycle.new({ component("a"), component("b") })
    T.truthy(lifecycle:start({}))
    T.truthy(lifecycle:update(1 / 60, {}))
    T.truthy(lifecycle:invalidate("resize", {}))
    T.truthy(lifecycle:stop("done", {}))
    T.deepEqual(order, { "start:a", "start:b", "update:a", "update:b",
      "invalidate:b", "invalidate:a", "stop:b", "stop:a" })
    T.equal(lifecycle:status().state, Lifecycle.STOPPED)
  end)

  T.test("start failure rolls back the failing component and predecessors", function()
    local order = {}
    local lifecycle = Lifecycle.new({
      { id = "a", start = function() order[#order + 1] = "start:a" end,
        stop = function() order[#order + 1] = "stop:a" end },
      { id = "b", start = function() order[#order + 1] = "start:b"; error("boom") end,
        stop = function() order[#order + 1] = "stop:b" end },
    })
    local ok, err = lifecycle:start()
    T.falsy(ok)
    T.truthy(err:find("b", 1, true))
    T.deepEqual(order, { "start:a", "start:b", "stop:b", "stop:a" })
    T.equal(lifecycle:status().state, Lifecycle.FAILED)
  end)

  T.test("update failure tears down all active components", function()
    local stops = {}
    local lifecycle = Lifecycle.new({
      { id = "a", update = function() return false, "bad frame" end,
        stop = function() stops[#stops + 1] = "a" end },
      { id = "b", stop = function() stops[#stops + 1] = "b" end },
    })
    lifecycle:start()
    local ok = lifecycle:update(0.1)
    T.falsy(ok)
    T.deepEqual(stops, { "b", "a" })
    T.equal(lifecycle:status().state, Lifecycle.FAILED)
  end)

  T.test("invalidation isolates errors and continues", function()
    local called = false
    local lifecycle = Lifecycle.new({
      { id = "a", invalidate = function() called = true end },
      { id = "b", invalidate = function() error("bad invalidate") end },
    })
    lifecycle:start()
    local ok, err = lifecycle:invalidate()
    T.falsy(ok)
    T.truthy(err:find("b", 1, true))
    T.truthy(called)
    T.equal(lifecycle:status().state, Lifecycle.RUNNING)
  end)

  T.test("once and safe helpers preserve fallback semantics", function()
    local calls = 0
    local once = Lifecycle.once(function(value)
      calls = calls + 1
      return value, nil, "tail"
    end)
    local a, b, c = once(7)
    T.equal(a, 7); T.equal(b, nil); T.equal(c, "tail")
    T.equal(once(9), 7)
    T.equal(calls, 1)
    local safe = Lifecycle.safe(function() error("broken") end, "fallback")
    T.equal(safe(), "fallback")
  end)
end
