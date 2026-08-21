return function(T)
  local Renderer = assert(loadfile(T.root .. "/src/render/Renderer.lua"))()

  T.test("renderer submits supported commands", function()
    local seen = {}
    local draw = {
      mesh = function(command) seen[#seen + 1] = command.owner; return true end,
      instances = function(command) seen[#seen + 1] = command.owner; return true end,
    }
    local packet = { phases = { background = {
      { kind = "mesh", owner = "sky" },
      { kind = "instances", owner = "stars" },
    } } }
    local renderer = Renderer.new()
    T.equal(renderer:renderPhase(packet, "background", { draw = draw }), 2)
    T.deepEqual(seen, { "sky", "stars" })
  end)

  T.test("renderer isolates a failed owner", function()
    local calls = 0
    local draw = {
      mesh = function(command)
        calls = calls + 1
        if command.owner == "bad" then error("draw failed") end
        return true
      end,
    }
    local packet = { phases = { background = {
      { kind = "mesh", owner = "bad" },
      { kind = "mesh", owner = "good" },
      { kind = "mesh", owner = "bad" },
    } } }
    local renderer = Renderer.new()
    T.equal(renderer:renderPhase(packet, "background", { draw = draw }), 1)
    T.equal(calls, 2)
    T.deepEqual(renderer:status().disabledOwners, { "bad" })
  end)

  T.test("renderer treats false and nil host results as visible failures", function()
    local packet = { phases = { background = {
      { kind = "mesh", owner = "false_result" },
      { kind = "mesh", owner = "nil_result" },
    } } }
    local draw = {
      mesh = function(command)
        if command.owner == "false_result" then return false, "unsupported" end
        return nil
      end,
    }
    local renderer = Renderer.new()
    T.equal(renderer:renderPhase(packet, "background", { draw = draw }), 0)
    T.deepEqual(renderer:status().disabledOwners, { "false_result", "nil_result" })
  end)
end
