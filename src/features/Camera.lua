local Camera = {}
Camera.__index = Camera

local DEGREES_TO_RADIANS = math.pi / 180
local FOV_DELTA = {
  NARROW = -8 * DEGREES_TO_RADIANS,
  NORMAL = 0,
  WIDE = 10 * DEGREES_TO_RADIANS,
  ULTRA = 18 * DEGREES_TO_RADIANS,
}

function Camera.new(deps)
  deps = deps or {}
  if not deps.util then error("Camera needs util", 2) end
  return setmetatable({
    id = "camera",
    order = 300,
    critical = false,
    util = deps.util,
    _time = 0,
    _bobPhase = 0,
    _speed = 0,
    _jumpY = 0,
    _jumpVelocity = 0,
    _doorY = 0,
    _config = {},
  }, Camera)
end

function Camera:compile(context, buffer)
  local dof = tostring(self.util.option(context.config, "depth_blur", "OFF")):upper()
  if self.util.capability(context, "draw_postprocess")
      and dof ~= "OFF" and context.quality.resolved ~= "LOW" then
    buffer:add("translucent_after_actors", {
      kind = "postprocess",
      owner = self.id,
      material = "camera:dof",
      sortKey = "99:camera_dof",
      effect = { kind = "depth_of_field", strength = dof },
    })
  end
end

function Camera:update(frame, config)
  frame = frame or {}
  self._config = config or self._config
  local dt = tonumber(frame.dt) or 0
  if dt < 0 then dt = 0 elseif dt > 0.1 then dt = 0.1 end
  self._time = self._time + dt
  local targetSpeed = math.max(0, tonumber(frame.playerSpeed) or 0)
  local blend = math.min(1, dt * 12)
  self._speed = self._speed + (targetSpeed - self._speed) * blend
  self._bobPhase = self._bobPhase + dt * (4 + self._speed * 0.35)

  if frame.jumpStarted then self:impulse("jump") end
  if frame.doorwayStep then self:impulse("doorway") end

  local spring = 42
  local damping = 11
  self._jumpVelocity = self._jumpVelocity + (-spring * self._jumpY - damping * self._jumpVelocity) * dt
  self._jumpY = self._jumpY + self._jumpVelocity * dt
  self._doorY = self._doorY * math.max(0, 1 - dt * 8)
end

function Camera:impulse(kind)
  if kind == "jump" then
    self._jumpVelocity = self._jumpVelocity + 8
  elseif kind == "land" then
    self._jumpVelocity = self._jumpVelocity - 4
  elseif kind == "doorway" then
    self._doorY = 1.2
  end
end

function Camera:modify(cameraContext)
  cameraContext = cameraContext or {}
  local U, config = self.util, self._config
  local mode = cameraContext.mode or "first_person"
  if mode ~= "first_person" then
    return {
      positionDelta = { x = 0, y = 0, z = 0 },
      rotationDelta = { yaw = 0, pitch = 0, roll = 0 },
      fovDelta = 0,
    }
  end
  local bob = 0
  local sway = 0
  if U.option(config, "head_bob", false) then
    local amplitude = math.min(0.65, self._speed * 0.08)
    bob = math.sin(self._bobPhase * 2) * amplitude
    sway = math.sin(self._bobPhase) * amplitude * 0.35
  end
  local jumpMode = tostring(U.option(config, "jump_feel", "SUBTLE")):upper()
  local jumpScale = jumpMode == "OFF" and 0 or (jumpMode == "BIG" and 1.4 or 0.8)
  local doorway = U.option(config, "doorway_step", true) and self._doorY or 0
  local fov = tostring(U.option(config, "first_person_fov", "NORMAL")):upper()
  return {
    positionDelta = {
      x = sway,
      y = bob + self._jumpY * jumpScale + doorway,
      z = 0,
    },
    rotationDelta = {
      yaw = sway * 0.0035,
      pitch = bob * 0.0025 + self._jumpY * jumpScale * 0.002,
      roll = 0,
    },
    fovDelta = FOV_DELTA[fov] or 0,
  }
end

function Camera:dispose()
  self._jumpY, self._jumpVelocity, self._doorY = 0, 0, 0
end

return Camera
