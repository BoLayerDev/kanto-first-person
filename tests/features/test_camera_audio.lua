return function(T)
  local function load(path) return assert(loadfile(T.root .. "/" .. path))() end
  local Util = load("src/features/Util.lua")
  local Camera = load("src/features/Camera.lua")
  local Audio = load("src/features/Audio.lua")

  T.test("camera update is time-based and modify is read-only", function()
    local config = {
      head_bob = true, jump_feel = "SUBTLE",
      first_person_fov = "WIDE", doorway_step = true,
    }
    local a = Camera.new({ util = Util })
    local b = Camera.new({ util = Util })
    for _ = 1, 60 do a:update({ dt = 1 / 60, playerSpeed = 2 }, config) end
    for _ = 1, 30 do b:update({ dt = 1 / 30, playerSpeed = 2 }, config) end
    local da = a:modify({ mode = "first_person" })
    local db = b:modify({ mode = "first_person" })
    T.near(da.positionDelta.y, db.positionDelta.y, 0.08)
    T.near(da.fovDelta, math.rad(10), 1e-12)
    local again = a:modify({ mode = "first_person" })
    T.equal(again.positionDelta.y, da.positionDelta.y)
  end)

  T.test("camera uses additive zero result outside first person", function()
    local camera = Camera.new({ util = Util })
    local delta = camera:modify({ mode = "third_person" })
    T.deepEqual(delta, {
      positionDelta = { x = 0, y = 0, z = 0 },
      rotationDelta = { yaw = 0, pitch = 0, roll = 0 },
      fovDelta = 0,
    })
  end)

  T.test("audio selects snapshot tags without terrain scans and crossfades", function()
    local events = {}
    local facade = {
      playStream = function(_, key, path, volume)
        events[#events + 1] = { "play", key, path, volume }
        return true
      end,
      setVolume = function(_, key, volume) events[#events + 1] = { "volume", key, volume } end,
      stop = function(_, key) events[#events + 1] = { "stop", key } end,
      playOneShot = function(_, key, path, volume)
        events[#events + 1] = { "one", key, path, volume }
        return true
      end,
    }
    local audio = Audio.new({ util = Util, facade = facade })
    local world = { weather = "clear", tags = { forest = true } }
    local config = { ambient_sound = "MID", grass_steps = true }
    for _ = 1, 20 do audio:update({ dt = 0.1 }, world, config) end
    T.equal(events[1][1], "play")
    T.equal(events[1][2], "forest")
    T.truthy(audio:oneShot("grass", config))
    T.equal(events[#events][1], "one")
  end)

  T.test("all KFP ambient and named one-shots use independent gain products", function()
    local events = {}
    local facade = {
      playStream = function(_, key, path, volume)
        events[#events + 1] = { "play", key, path, volume }
        return true
      end,
      setVolume = function(_, key, volume)
        events[#events + 1] = { "volume", key, volume }
        return true
      end,
      stop = function(_, key) events[#events + 1] = { "stop", key } end,
      playOneShot = function(_, key, path, volume)
        events[#events + 1] = { "one", key, path, volume }
        return true
      end,
    }
    local audio = Audio.new({ util = Util, facade = facade })
    local config = {
      ambient_sound = "MID",
      grass_steps = true,
      footsteps = true,
      door_sound = true,
      kfp_master_volume = 50,
      kfp_ambient_volume = 25,
      kfp_sfx_volume = 20,
    }
    local world = { weather = "clear", tags = { forest = true } }
    for _ = 1, 20 do audio:update({ dt = 0.1 }, world, config) end
    local ambient = events[#events]
    T.equal(ambient[1], "volume")
    T.equal(ambient[2], "forest")
    T.near(ambient[3], 0.4 * 0.5 * 0.25, 1e-12)

    local cases = {
      { "grass", "grass1", 0.5 },
      { "grass", "grass2", 0.5 },
      { "cave", "cave_step", 0.45 },
      { "wood", "wood_step", 0.45 },
      { "door", "door", 0.55 },
      { "shop_door", "shop_door", 0.55 },
    }
    for _, case in ipairs(cases) do
      T.truthy(audio:oneShot(case[1], config), case[1])
      local shot = events[#events]
      T.equal(shot[1], "one")
      T.equal(shot[2], case[2])
      T.near(shot[4], case[3] * 0.5 * 0.2, 1e-12, case[2])
    end
  end)

  T.test("KFP gain boundaries clamp and OFF category toggles stay exact", function()
    local events = {}
    local facade = {
      playStream = function(_, key, path, volume)
        events[#events + 1] = { "play", key, path, volume }
        return true
      end,
      setVolume = function(_, key, volume)
        events[#events + 1] = { "volume", key, volume }
        return true
      end,
      stop = function(_, key) events[#events + 1] = { "stop", key } end,
      playOneShot = function(_, key, path, volume)
        events[#events + 1] = { "one", key, path, volume }
        return true
      end,
    }
    local world = { weather = "clear", tags = { town = true } }
    local audio = Audio.new({ util = Util, facade = facade })
    local loud = {
      ambient_sound = "HIGH", door_sound = true,
      kfp_master_volume = 200,
      kfp_ambient_volume = 200,
      kfp_sfx_volume = 200,
    }
    for _ = 1, 20 do audio:update({ dt = 0.1 }, world, loud) end
    T.near(events[#events][3], 0.65, 1e-12)
    T.truthy(audio:oneShot("door", loud))
    T.near(events[#events][4], 0.55, 1e-12)

    local muted = {
      ambient_sound = "MID", door_sound = true,
      kfp_master_volume = 0,
      kfp_ambient_volume = 100,
      kfp_sfx_volume = 100,
    }
    audio:update({ dt = 0.1 }, world, muted)
    T.equal(events[#events][3], 0)
    T.truthy(audio:oneShot("door", muted))
    T.equal(events[#events][4], 0)

    local invalid = {
      ambient_sound = "MID", door_sound = true,
      kfp_master_volume = "invalid",
      kfp_ambient_volume = 0 / 0,
      kfp_sfx_volume = {},
    }
    audio:update({ dt = 0.1 }, world, invalid)
    T.near(events[#events][3], 0.4, 1e-12)
    T.truthy(audio:oneShot("door", invalid))
    T.near(events[#events][4], 0.55, 1e-12)

    local offEvents = {}
    local off = Audio.new({
      util = Util,
      facade = {
        playStream = function() offEvents[#offEvents + 1] = "stream"; return true end,
        playOneShot = function() offEvents[#offEvents + 1] = "shot"; return true end,
      },
    })
    T.truthy(off:update({ dt = 0.1 }, world, { ambient_sound = "OFF" }))
    T.falsy(off:oneShot("grass", { grass_steps = false }))
    T.falsy(off:oneShot("cave", { footsteps = false }))
    T.falsy(off:oneShot("wood", { footsteps = false }))
    T.falsy(off:oneShot("door", { door_sound = false }))
    T.falsy(off:oneShot("shop_door", { door_sound = false }))
    T.equal(#offEvents, 0)
  end)

  T.test("audio never reports success when its owned backend cannot play", function()
    local attempts = 0
    local unavailable = Audio.new({
      util = Util,
      facade = {
        available = function() return false end,
        playStream = function() attempts = attempts + 1; return true end,
        playOneShot = function() attempts = attempts + 1; return true end,
      },
    })
    local world = { weather = "clear", tags = { town = true } }
    T.falsy(unavailable:update({ dt = 0.1 }, world, { ambient_sound = "MID" }))
    T.falsy(unavailable:oneShot("grass", { grass_steps = true }))
    T.equal(attempts, 0)

    local failed = Audio.new({
      util = Util,
      facade = {
        available = function() return true end,
        playStream = function() attempts = attempts + 1; return nil, "failed" end,
        playOneShot = function() attempts = attempts + 1; return nil, "failed" end,
      },
    })
    T.falsy(failed:update({ dt = 0.1 }, world, { ambient_sound = "MID" }))
    T.falsy(failed:oneShot("grass", { grass_steps = true }))
    T.equal(attempts, 2)
    T.falsy(failed:update({ dt = 0.1 }, world, { ambient_sound = "MID" }))
    T.equal(attempts, 2)
    T.truthy(failed:invalidate())
    T.falsy(failed:update({ dt = 0.1 }, world, { ambient_sound = "MID" }))
    T.equal(attempts, 3)
  end)
end
