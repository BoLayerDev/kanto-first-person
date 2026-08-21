-- Pure, fail-closed policy for the optional Ledge Leap button.
--
-- The adapter must copy current world facts into the request. This module
-- never reads or changes engine state. It permits only the same one-way
-- standing-tile, ledge-tile, facing, and input rule used by Gen1recomp.

local LedgeLeapPolicy = {}
local MAX_LEDGE_RULES = 256

local DELTA = {
  up = { 0, -1 },
  down = { 0, 1 },
  left = { -1, 0 },
  right = { 1, 0 },
}

local function deny(reason)
  return { allowed = false, action = "none", reason = reason }
end

local function integer(value)
  return type(value) == "number" and value == value
    and value > -math.huge and value < math.huge
    and value == math.floor(value)
end

local function coordinatePair(record)
  if type(record) ~= "table" then return nil end
  local x, y = record.x, record.y
  if not integer(x) or not integer(y) then return nil end
  return x, y
end

local function rowStandingTile(row)
  if type(row) ~= "table" then return nil end
  if row.standing_tile ~= nil then return row.standing_tile end
  return row.standingTile
end

local function rowLedgeTile(row)
  if type(row) ~= "table" then return nil end
  if row.ledge_tile ~= nil then return row.ledge_tile end
  return row.ledgeTile
end

local function matchingRule(rows, tileset, direction, standingTile, ledgeTile)
  if type(rows) ~= "table" then return nil end
  if #rows > MAX_LEDGE_RULES then return nil, "ledge_rule_limit" end
  for index = 1, #rows do
    local row = rows[index]
    if type(row) == "table"
        and (row.tileset or "OVERWORLD") == tileset
        and row.facing == direction
        and row.input == direction
        and rowStandingTile(row) == standingTile
        and rowLedgeTile(row) == ledgeTile then
      return index
    end
  end
  return nil
end

local function arcFrames(player)
  local frames = player.step_frames_current or player.step_frames or 16
  frames = tonumber(frames) or 16
  if frames ~= frames or frames == math.huge or frames == -math.huge then frames = 16 end
  frames = math.max(1, math.min(32, math.floor(frames)))
  return frames * 2
end

function LedgeLeapPolicy.decide(request)
  if type(request) ~= "table" then return deny("invalid_request") end
  if request.enabled ~= true then return deny("disabled") end
  if request.mode ~= "free_roam" then return deny("not_free_roam") end
  if request.script_running ~= false then
    return deny(request.script_running == true and "script_running" or "script_state_unknown")
  end
  if request.input_locked ~= false then
    return deny(request.input_locked == true and "input_locked" or "input_lock_unknown")
  end

  local player = request.player
  if type(player) ~= "table" then return deny("missing_player") end
  if player.moving ~= false then
    return deny(player.moving == true and "player_moving" or "movement_state_unknown")
  end
  if player.surfing ~= false then
    return deny(player.surfing == true and "player_surfing" or "surf_state_unknown")
  end
  if type(player.hop_frames) ~= "number" or player.hop_frames ~= player.hop_frames then
    return deny("hop_state_invalid")
  end
  if player.hop_frames > 0 then return deny("hop_in_progress") end
  if not integer(player.cell_x) or not integer(player.cell_y) then
    return deny("invalid_player_cell")
  end

  local direction = request.direction or player.facing
  local delta = DELTA[direction]
  if not delta then return deny("invalid_direction") end
  if player.facing ~= direction then return deny("facing_mismatch") end

  local map = request.map
  if type(map) ~= "table" or type(map.tileset) ~= "string"
      or map.tileset == "" or not integer(map.standing_tile)
      or map.standing_tile < 0 then
    return deny("invalid_map_facts")
  end

  local front = request.front
  local frontX, frontY = coordinatePair(front)
  if not frontX then return deny("invalid_front_cell") end
  if frontX ~= player.cell_x + delta[1] or frontY ~= player.cell_y + delta[2] then
    return deny("front_cell_mismatch")
  end
  if front.in_bounds ~= true then return deny("front_out_of_bounds") end
  if not integer(front.tile) or front.tile < 0 then return deny("missing_front_tile") end
  if front.occupied ~= false then return deny("front_occupied") end

  local landing = request.landing
  local landingX, landingY = coordinatePair(landing)
  if not landingX then return deny("invalid_landing_cell") end
  if landingX ~= frontX + delta[1] or landingY ~= frontY + delta[2] then
    return deny("landing_cell_mismatch")
  end
  -- Scripted two-cell movement does not own connection transitions. Reject a
  -- seam hop here; normal directional input remains with the engine and can
  -- use its connectionLanding/checkEdgeExit path safely.
  if landing.in_bounds ~= true then return deny("landing_out_of_bounds") end
  if landing.walkable ~= true then return deny("landing_not_walkable") end
  if landing.occupied ~= false then return deny("landing_occupied") end

  local ruleIndex, ruleError = matchingRule(request.ledges, map.tileset, direction,
    map.standing_tile, front.tile)
  if ruleError then return deny(ruleError) end
  if not ruleIndex then return deny("not_one_way_ledge") end

  return {
    allowed = true,
    action = "ledge_leap",
    reason = "allowed",
    direction = direction,
    distance = 2,
    arc_frames = arcFrames(player),
    sound = "Ledge",
    rule_index = ruleIndex,
    from = { x = player.cell_x, y = player.cell_y },
    over = { x = frontX, y = frontY },
    landing = { x = landingX, y = landingY },
  }
end

return LedgeLeapPolicy
