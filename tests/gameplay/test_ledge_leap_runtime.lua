return function(T)
  local Runtime = assert(loadfile(T.root .. "/src/gameplay/LedgeLeapRuntime.lua"))()

  local function allowed()
    return {
      allowed = true, action = "ledge_leap", reason = "allowed",
      direction = "down", distance = 2, arc_frames = 32,
      sound = "Ledge", rule_index = 1,
    }
  end

  local function diagnostics()
    local sink = { entries = {} }
    function sink:emit(level, code, message, fields)
      self.entries[#self.entries + 1] = {
        level = level, code = code, message = message, fields = fields,
      }
    end
    return sink
  end

  T.test("runtime requires injected policy and queue interfaces", function()
    T.raises(function() Runtime.new() end, "decide%(request%)")
    T.raises(function() Runtime.new({ decide = function() end }) end, "queue_script")
    T.raises(function()
      Runtime.new({ decide = function() end, queue_script = function() end,
        arc_command = "" })
    end, "arc_command")
  end)

  T.test("denied policy decisions never queue scripts", function()
    local calls = 0
    local runtime = Runtime.new({
      decide = function() return { allowed = false, action = "none", reason = "disabled" } end,
      queue_script = function() calls = calls + 1 end,
    })
    local decision, queued = runtime:attempt({})
    T.equal(decision.reason, "disabled")
    T.falsy(queued)
    T.equal(calls, 0)
  end)

  T.test("allowed decisions become one bounded stock script", function()
    local captured
    local runtime = Runtime.new({
      policy = { decide = function() return allowed() end },
      queue_script = function(script) captured = script; return true end,
    })
    local decision, queued = runtime:attempt({})
    T.equal(decision.direction, "down")
    T.truthy(queued)
    T.deepEqual(captured, {
      { "kfp_ledge_arc", 32 },
      { "play_sound", "Ledge" },
      { "move_player", "down", 2 },
    })
  end)

  T.test("custom command names and script builders stay injected", function()
    local first
    Runtime.new({
      decide = function() return allowed() end,
      queue_script = function(script) first = script end,
      arc_command = "custom_arc",
    }):attempt({})
    T.equal(first[1][1], "custom_arc")

    local second
    Runtime.new({
      decide = function() return allowed() end,
      queue_script = function(script) second = script end,
      build_script = function(decision) return { { "safe_jump", decision.rule_index } } end,
    }):attempt({})
    T.deepEqual(second, { { "safe_jump", 1 } })
  end)

  T.test("forged or malformed allowed decisions fail closed", function()
    local mutations = {
      function(d) d.action = "teleport" end,
      function(d) d.direction = "diagonal" end,
      function(d) d.distance = 3 end,
      function(d) d.arc_frames = 1 end,
      function(d) d.arc_frames = 65 end,
      function(d) d.arc_frames = 3.5 end,
      function(d) d.sound = "Other" end,
      function(d) d.rule_index = nil end,
      function(d) d.rule_index = 0 end,
      function(d) d.rule_index = 1.5 end,
      function(d) d.rule_index = 257 end,
    }
    for _, mutate in ipairs(mutations) do
      local decision, queues = allowed(), 0
      mutate(decision)
      local runtime = Runtime.new({
        decide = function() return decision end,
        queue_script = function() queues = queues + 1 end,
      })
      local result, queued = runtime:attempt({})
      T.equal(result.reason, "invalid_decision")
      T.falsy(queued)
      T.equal(queues, 0)
    end
  end)

  T.test("policy failures are isolated and diagnosed", function()
    local diag, calls = diagnostics(), 0
    local runtime = Runtime.new({
      decide = function() error("policy boom") end,
      queue_script = function() calls = calls + 1 end,
      diagnostics = diag,
    })
    local decision, queued, err = runtime:attempt({})
    T.equal(decision.reason, "policy_failed")
    T.falsy(queued)
    T.truthy(err:find("policy boom", 1, true))
    T.equal(calls, 0)
    T.equal(diag.entries[1].code, "GAMEPLAY.LEDGE_POLICY_FAILED")
  end)

  T.test("script build failures never reach the queue", function()
    for _, builder in ipairs({
      function() error("build boom") end,
      function() return "not a script" end,
      function() return {} end,
      function() return { "not a row" } end,
    }) do
      local diag, calls = diagnostics(), 0
      local runtime = Runtime.new({
        decide = function() return allowed() end,
        build_script = builder,
        queue_script = function() calls = calls + 1 end,
        diagnostics = diag,
      })
      local _, queued = runtime:attempt({})
      T.falsy(queued)
      T.equal(calls, 0)
      T.equal(diag.entries[1].code, "GAMEPLAY.LEDGE_SCRIPT_BUILD_FAILED")
    end
  end)

  T.test("queue rejection and queue exceptions remain visible", function()
    for _, queue in ipairs({
      function() return false, "busy" end,
      function() error("queue boom") end,
    }) do
      local diag = diagnostics()
      local runtime = Runtime.new({
        decide = function() return allowed() end,
        queue_script = queue,
        diagnostics = diag,
      })
      local _, queued, err = runtime:attempt({})
      T.falsy(queued)
      T.truthy(type(err) == "string")
      T.equal(diag.entries[1].code, "GAMEPLAY.LEDGE_QUEUE_FAILED")
    end
  end)

  T.test("nil queue return is accepted for engine adapters with no result", function()
    local calls = 0
    local runtime = Runtime.new({
      decide = function() return allowed() end,
      queue_script = function() calls = calls + 1 end,
    })
    local _, queued = runtime:attempt({})
    T.truthy(queued)
    T.equal(calls, 1)
  end)
end
