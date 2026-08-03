-- The JUMP: what a ledge hop feels like from inside the head.
-- payload-version: 1
--
-- The engine already hops the player over a ledge, and Dramatic Shape's
-- first-person rig already carries the eye along that arc -- but the arc
-- was authored for a 16px sprite seen from outside, so from within the
-- head it reads as a polite shrug rather than a jump.
--
-- This adds three things to the eye, and nothing to the game:
--
--   BOOST    the existing hop arc, multiplied.  A vault instead of a
--            step, without touching where the player actually lands.
--   CROUCH   a dip just before the rise: the body loading the jump.
--   LAND     a damped settle on touchdown, two small bounces, so the
--            ground arrives with weight instead of stopping dead.
--
-- All of it is eye offset -- a number added to the camera's height.
-- Collision, ledge rules, where the hop ends and which cells are jumpable
-- are the engine's business and are not touched.  Nothing here can move
-- the player one pixel, which is exactly the point: a purely cosmetic
-- jump cannot desync a script, a save or a link battle.

local V = ...

local Jump = {}

-- how much of the engine's own arc to add on top of it, per setting
local BOOST = { OFF = 0, SUBTLE = 0.6, BIG = 1.6 }

local CROUCH_DEPTH = 1.6      -- pixels dipped while loading
local CROUCH_TIME = 0.10      -- seconds of load before the rise
local LAND_DEPTH = 2.4        -- pixels dipped on touchdown
local LAND_TIME = 0.26        -- seconds to settle
local LAND_BOUNCES = 2

local prevLift, landAt, riseAt = 0, nil, nil

local function now()
  local ok, t = pcall(function() return love.timer.getTime() end)
  return ok and t or 0
end

local function config()
  local pub = rawget(_G, "__ds_ceiling_config")
  if type(pub) == "function" then
    local ok, cfg = pcall(pub)
    if ok and type(cfg) == "table" then return cfg end
  end
  return {}
end

-- The eye offset for this frame, in world pixels.  Called from the rig's
-- head expression (lib/FirstPerson.lua) once per eye, so it must be cheap
-- and must never throw: a bad frame here would take the camera with it.
function Jump.eyeOffset(me)
  local ok, offset = pcall(function()
    local cfg = config()
    local mult = BOOST[cfg.jump or "SUBTLE"]
    if not mult or mult <= 0 then return 0 end

    local lift = (me and me.lift) or 0
    local t = now()

    -- edges of the hop
    if lift > 0 and prevLift <= 0 then riseAt = t end
    if lift <= 0 and prevLift > 0 then landAt = t end
    prevLift = lift

    local off = lift * mult

    -- the load: a dip in the moments before the arc starts lifting.
    -- The engine gives no warning of a hop, so this reads the first
    -- frames of the arc itself and dips against them -- brief, and it
    -- resolves into the rise rather than fighting it.
    if riseAt and lift > 0 then
      local age = t - riseAt
      if age < CROUCH_TIME then
        local k = 1 - age / CROUCH_TIME
        off = off - CROUCH_DEPTH * k * k
      end
    end

    -- the landing: a damped settle, decaying over LAND_TIME
    if landAt then
      local age = t - landAt
      if age < LAND_TIME then
        local k = 1 - age / LAND_TIME
        local osc = math.cos(age / LAND_TIME * math.pi * 2 * LAND_BOUNCES)
        off = off - LAND_DEPTH * k * k * osc * mult
      else
        landAt = nil
      end
    end

    return off
  end)
  return (ok and type(offset) == "number" and offset) or 0
end

return Jump
