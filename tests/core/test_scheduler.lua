return function(T)
  local Scheduler = T.loadCore("Scheduler")

  T.test("charges bounded slices and completes incrementally", function()
    local scheduler = Scheduler.new({ maxBudget = 8, quantum = 2 })
    local calls = 0
    assert(scheduler:spawn("mesh", function(slice)
      calls = calls + 1
      return calls == 3, slice
    end))
    local report = scheduler:step(5)
    T.equal(report.used, 5)
    T.equal(report.callbacks, 3)
    T.equal(report.completed, 1)
    T.equal(scheduler:size(), 0)
  end)

  T.test("round-robin order is deterministic", function()
    local scheduler = Scheduler.new({ maxBudget = 10, quantum = 1 })
    local order = {}
    scheduler:spawn("a", function() order[#order + 1] = "a"; return false, 1 end)
    scheduler:spawn("b", function() order[#order + 1] = "b"; return false, 1 end)
    scheduler:step(4)
    T.deepEqual(order, { "a", "b", "a", "b" })
    T.equal(scheduler:clear(), 2)
  end)

  T.test("callback and task limits cannot be bypassed", function()
    local scheduler = Scheduler.new({ maxTasks = 1, maxBudget = 100,
      maxCallbacks = 2, quantum = 1 })
    T.truthy(scheduler:spawn("one", function() return false, 0 end))
    local task, err = scheduler:spawn("two", function() end)
    T.equal(task, nil)
    T.equal(err, "task_limit")
    local report = scheduler:step(100)
    T.equal(report.callbacks, 2)
    T.equal(report.used, 2)
    T.equal(report.remainingTasks, 1)
  end)

  T.test("task failures are isolated and removed", function()
    local events = {}
    local diagnostics = { emit = function(_, level, code)
      events[#events + 1] = level .. ":" .. code
    end }
    local scheduler = Scheduler.new({ diagnostics = diagnostics })
    scheduler:spawn("bad", function() error("broken") end)
    local report = scheduler:step(1)
    T.equal(report.failed, 1)
    T.equal(scheduler:size(), 0)
    T.equal(events[1], "error:CORE.SCHEDULER_TASK_FAILED")
  end)

  T.test("self-cancellation does not requeue the task", function()
    local scheduler = Scheduler.new({ maxBudget = 4, quantum = 1 })
    scheduler:spawn("self", function()
      scheduler:cancel("self", "done")
      return false, 1
    end)
    scheduler:step(4)
    T.equal(scheduler:size(), 0)
  end)

  T.test("cancel and respawn cannot leave an unbounded or aliased queue", function()
    local scheduler = Scheduler.new({ maxTasks = 2, maxBudget = 8,
      quantum = 1 })
    for index = 1, 100 do
      T.truthy(scheduler:spawn("replaceable", function() return false, 1 end))
      T.truthy(scheduler:cancel("replaceable"))
    end
    T.truthy(scheduler:stats().queued <= 4)

    local calls = 0
    scheduler:spawn("replaceable", function()
      calls = calls + 1
      return calls == 1, 1
    end)
    local report = scheduler:step(8)
    T.equal(calls, 1)
    T.equal(report.completed, 1)
    T.equal(scheduler:size(), 0)
  end)
end
