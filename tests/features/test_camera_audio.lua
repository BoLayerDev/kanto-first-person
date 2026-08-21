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
      playOneShot = function(_, key, path)
        events[#events + 1] = { "one", key, path }
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
