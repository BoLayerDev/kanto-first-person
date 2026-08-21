return function(T)
  local Policy = assert(loadfile(T.root .. "/src/gameplay/LedgeLeapPolicy.lua"))()

  local function request(direction)
    direction = direction or "down"
    local delta = {
      up = { 0, -1 }, down = { 0, 1 }, left = { -1, 0 }, right = { 1, 0 },
    }
    local d = delta[direction]
    return {
      enabled = true,
      mode = "free_roam",
      script_running = false,
      input_locked = false,
      direction = direction,
      player = {
        cell_x = 10, cell_y = 20, facing = direction, moving = false,
        surfing = false, hop_frames = 0, step_frames = 16,
      },
      map = { tileset = "OVERWORLD", standing_tile = 44 },
      front = {
        x = 10 + d[1], y = 20 + d[2], in_bounds = true,
        tile = 55, occupied = false,
      },
      landing = {
        x = 10 + d[1] * 2, y = 20 + d[2] * 2, in_bounds = true,
        walkable = true, occupied = false,
      },
      ledges = {
        { facing = direction, input = direction, standingTile = 44, ledgeTile = 55 },
      },
    }
  end

  local function clone(value)
    if type(value) ~= "table" then return value end
    local out = {}
    for key, child in pairs(value) do out[key] = clone(child) end
    return out
  end

  T.test("valid one-way ledges produce declarative decisions in all directions", function()
    for _, direction in ipairs({ "up", "down", "left", "right" }) do
      local input = request(direction)
      local before = clone(input)
      local decision = Policy.decide(input)
      T.truthy(decision.allowed, direction)
      T.equal(decision.action, "ledge_leap")
      T.equal(decision.direction, direction)
      T.equal(decision.distance, 2)
      T.equal(decision.arc_frames, 32)
      T.equal(decision.sound, "Ledge")
      T.equal(decision.rule_index, 1)
      T.deepEqual(decision.from, { x = 10, y = 20 })
      T.deepEqual(decision.landing, { x = input.landing.x, y = input.landing.y })
      T.deepEqual(input, before, "policy mutated its input")
    end
  end)

  T.test("feature and world state gates fail closed", function()
    local cases = {
      { function(r) r.enabled = false end, "disabled" },
      { function(r) r.mode = "battle" end, "not_free_roam" },
      { function(r) r.script_running = true end, "script_running" },
      { function(r) r.input_locked = true end, "input_locked" },
      { function(r) r.script_running = nil end, "script_state_unknown" },
      { function(r) r.input_locked = nil end, "input_lock_unknown" },
      { function(r) r.player = nil end, "missing_player" },
      { function(r) r.player.moving = true end, "player_moving" },
      { function(r) r.player.moving = nil end, "movement_state_unknown" },
      { function(r) r.player.surfing = true end, "player_surfing" },
      { function(r) r.player.surfing = nil end, "surf_state_unknown" },
      { function(r) r.player.hop_frames = nil end, "hop_state_invalid" },
      { function(r) r.player.hop_frames = 0 / 0 end, "hop_state_invalid" },
      { function(r) r.player.hop_frames = 1 end, "hop_in_progress" },
      { function(r) r.player.cell_x = 1.5 end, "invalid_player_cell" },
    }
    T.equal(Policy.decide(nil).reason, "invalid_request")
    for _, case in ipairs(cases) do
      local input = request()
      case[1](input)
      local decision = Policy.decide(input)
      T.falsy(decision.allowed)
      T.equal(decision.reason, case[2])
    end
  end)

  T.test("direction and cell facts must describe the faced two-cell path", function()
    local cases = {
      { function(r) r.direction = "diagonal" end, "invalid_direction" },
      { function(r) r.player.facing = "up" end, "facing_mismatch" },
      { function(r) r.map.tileset = nil end, "invalid_map_facts" },
      { function(r) r.front.x = r.front.x + 1 end, "front_cell_mismatch" },
      { function(r) r.front.in_bounds = false end, "front_out_of_bounds" },
      { function(r) r.front.tile = nil end, "missing_front_tile" },
      { function(r) r.front.occupied = true end, "front_occupied" },
      { function(r) r.front.occupied = nil end, "front_occupied" },
      { function(r) r.landing.y = r.landing.y + 1 end, "landing_cell_mismatch" },
      { function(r) r.landing.in_bounds = false end, "landing_out_of_bounds" },
      { function(r) r.landing.walkable = false end, "landing_not_walkable" },
      { function(r) r.landing.occupied = true end, "landing_occupied" },
      { function(r) r.landing.occupied = nil end, "landing_occupied" },
    }
    for _, case in ipairs(cases) do
      local input = request()
      case[1](input)
      T.equal(Policy.decide(input).reason, case[2])
    end
  end)

  T.test("every Gen1recomp one-way rule field must match", function()
    local mutations = {
      function(row) row.tileset = "CAVERN" end,
      function(row) row.facing = "up" end,
      function(row) row.input = "up" end,
      function(row) row.standingTile = 57 end,
      function(row) row.ledgeTile = 54 end,
    }
    for _, mutate in ipairs(mutations) do
      local input = request()
      mutate(input.ledges[1])
      T.equal(Policy.decide(input).reason, "not_one_way_ledge")
    end

    local normalized = request()
    normalized.ledges[1] = {
      facing = "down", input = "down", standing_tile = 44, ledge_tile = 55,
    }
    T.truthy(Policy.decide(normalized).allowed)
  end)

  T.test("tileset omission means OVERWORLD only", function()
    local overworld = request()
    T.truthy(Policy.decide(overworld).allowed)
    local cave = request()
    cave.map.tileset = "CAVERN"
    T.equal(Policy.decide(cave).reason, "not_one_way_ledge")
    cave.ledges[1].tileset = "CAVERN"
    T.truthy(Policy.decide(cave).allowed)
  end)

  T.test("malformed rules are skipped and the matching index is retained", function()
    local input = request()
    input.ledges = { false, {}, { facing = "up" }, input.ledges[1] }
    local decision = Policy.decide(input)
    T.truthy(decision.allowed)
    T.equal(decision.rule_index, 4)
    input.ledges = nil
    T.equal(Policy.decide(input).reason, "not_one_way_ledge")

    input = request()
    input.ledges = {}
    for index = 1, 257 do input.ledges[index] = {} end
    T.equal(Policy.decide(input).reason, "ledge_rule_limit")
  end)

  T.test("seam hops are left to the engine connection path", function()
    local input = request()
    input.landing.in_bounds = false
    local decision = Policy.decide(input)
    T.falsy(decision.allowed)
    T.equal(decision.reason, "landing_out_of_bounds")
  end)

  T.test("arc duration is finite, integral, and bounded", function()
    local low = request()
    low.player.step_frames = 0
    T.equal(Policy.decide(low).arc_frames, 2)
    local high = request()
    high.player.step_frames_current = 1000
    T.equal(Policy.decide(high).arc_frames, 64)
    local fractional = request()
    fractional.player.step_frames = 7.9
    T.equal(Policy.decide(fractional).arc_frames, 14)
    local invalid = request()
    invalid.player.step_frames = 0 / 0
    T.equal(Policy.decide(invalid).arc_frames, 32)
  end)
end
