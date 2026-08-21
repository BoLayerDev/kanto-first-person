local Audio = {}
Audio.__index = Audio

local AMBIENT = {
  cave = "assets/legacy/audio/ambient/amb-cave.mp3",
  forest = "assets/legacy/audio/ambient/amb-forest.mp3",
  night = "assets/legacy/audio/ambient/amb-night.mp3",
  rain = "assets/legacy/audio/ambient/amb-rain.mp3",
  route = "assets/legacy/audio/ambient/amb-route.mp3",
  town = "assets/legacy/audio/ambient/amb-town.mp3",
  water = "assets/legacy/audio/ambient/amb-water.mp3",
}

local SFX = {
  cave_step = "assets/legacy/audio/sfx/sfx-cavestep.mp3",
  door = "assets/legacy/audio/sfx/sfx-door.mp3",
  grass1 = "assets/legacy/audio/sfx/sfx-grass1.mp3",
  grass2 = "assets/legacy/audio/sfx/sfx-grass2.mp3",
  shop_door = "assets/legacy/audio/sfx/sfx-shopdoor.mp3",
  wood_step = "assets/legacy/audio/sfx/sfx-woodstep.mp3",
}

function Audio.new(deps)
  deps = deps or {}
  if not deps.util then error("Audio needs util", 2) end
  return setmetatable({
    id = "audio",
    util = deps.util,
    facade = deps.facade,
    _current = nil,
    _target = nil,
    _volume = 0,
    _step = 0,
    _failedTarget = nil,
  }, Audio)
end

local function facadeAvailable(facade)
  if type(facade) ~= "table" then return false end
  if type(facade.available) ~= "function" then return true end
  local ok, available = pcall(facade.available, facade)
  return ok and available == true
end

local function targetFor(util, world)
  if world.weather == "rain" or world.weather == "storm" then return "rain" end
  if util.hasTag(world, "cave") then return "cave" end
  if util.hasTag(world, "forest") then return "forest" end
  if util.hasTag(world, "shore") or util.hasTag(world, "water") then return "water" end
  if util.hasTag(world, "town") or util.hasTag(world, "city") then return "town" end
  if util.hasTag(world, "night") then return "night" end
  return "route"
end

local function volumeFor(value)
  value = type(value) == "string" and value:upper() or "MID"
  if value == "OFF" then return 0 end
  if value == "LOW" then return 0.2 end
  if value == "HIGH" then return 0.65 end
  return 0.4
end

function Audio:update(frame, world, config)
  if not facadeAvailable(self.facade) or not world then return false end
  local dt = math.max(0, math.min(0.1, tonumber(frame and frame.dt) or 0))
  local targetVolume = volumeFor(self.util.option(config, "ambient_sound", "MID"))
  local target = targetVolume > 0 and targetFor(self.util, world) or nil
  if target ~= self._target then
    self._target = target
    self._failedTarget = nil
  end

  if self._current ~= self._target then
    self._volume = math.max(0, self._volume - dt * 1.5)
    if self._current and self.facade.setVolume then
      self.facade:setVolume(self._current, self._volume)
    end
    if self._volume <= 0.001 then
      if self._current and self.facade.stop then self.facade:stop(self._current) end
      self._current = nil
      if self._target and self._failedTarget ~= self._target
          and self.facade.playStream then
        local started = self.facade:playStream(
          self._target, AMBIENT[self._target], 0)
        if started == true then
          self._current = self._target
        else
          self._failedTarget = self._target
          return false
        end
      end
      if self._target and self._failedTarget == self._target then return false end
    end
  elseif self._current then
    self._volume = math.min(targetVolume, self._volume + dt * 0.8)
    if self.facade.setVolume then self.facade:setVolume(self._current, self._volume) end
  end
  return true
end

function Audio:oneShot(kind, config)
  if not facadeAvailable(self.facade) or not self.facade.playOneShot then return false end
  if kind == "grass" and self.util.option(config, "grass_steps", true) then
    local nextStep = self._step + 1
    local key = nextStep % 2 == 0 and "grass2" or "grass1"
    local played = self.facade:playOneShot(key, SFX[key], 0.5)
    if played == true then self._step = nextStep end
    return played == true
  end
  if kind == "cave" and self.util.option(config, "footsteps", true) then
    return self.facade:playOneShot("cave_step", SFX.cave_step, 0.45) == true
  end
  if kind == "wood" and self.util.option(config, "footsteps", true) then
    return self.facade:playOneShot("wood_step", SFX.wood_step, 0.45) == true
  end
  if (kind == "door" or kind == "shop_door")
      and self.util.option(config, "door_sound", true) then
    return self.facade:playOneShot(kind, SFX[kind], 0.55) == true
  end
  return false
end

function Audio:invalidate()
  self._failedTarget = nil
  return true
end

function Audio:dispose()
  if self._current and self.facade and self.facade.stop then self.facade:stop(self._current) end
  self._current, self._target, self._volume, self._failedTarget = nil, nil, 0, nil
end

return Audio
