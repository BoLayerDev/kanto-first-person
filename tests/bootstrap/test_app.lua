return function(T)
  local function fakeMod(provider)
    local listeners, hooks, optionRows = {}, {}, {}
    local optionValues, saved, reads = {}, {}, {}
    local mod = {
      id = "ds_fp_ceiling",
      version = "2.0.0-alpha.1",
      exports = {},
      log = {
        info = function() end,
        warn = function() end,
        error = function() end,
      },
      options = {
        define = function(_, rows) optionRows = rows end,
        get = function(_, key)
          if optionValues[key] ~= nil then return optionValues[key] end
          for _, row in ipairs(optionRows) do
            if row.key == key then return row.default end
          end
          return nil
        end,
      },
      save = {
        get = function(_, key) return saved[key] end,
        set = function(_, key, value) saved[key] = value end,
      },
      assets = {
        path = function(_, relative)
          return "mods/ds_fp_ceiling/" .. relative
        end,
      },
      events = {
        on = function(_, name, callback)
          listeners[name] = listeners[name] or {}
          listeners[name][#listeners[name] + 1] = callback
          return function() end
        end,
      },
      hooks = {
        wrap = function(_, name, callback)
          hooks[name] = callback
          return function() end
        end,
      },
      world = {
        queueScript = function() return true end,
      },
    }
    function mod:read(path)
      T.truthy(not path:find("..", 1, true))
      reads[#reads + 1] = path
      return T.read(path)
    end
    mod.find = function(id)
      if provider and id == provider.host.id then
        return { id = id, version = provider.host.version,
          exports = { voxel_companion = provider } }
      end
      return nil
    end
    local control = {
      emit = function(name, payload)
        for _, callback in ipairs(listeners[name] or {}) do callback(payload) end
      end,
      reads = reads,
      rows = function() return optionRows end,
      hook = function(name) return hooks[name or "input.step"] end,
      options = optionValues,
      saved = saved,
    }
    return mod, control
  end

  local function loadEntry()
    return assert(loadfile(T.root .. "/main.lua"))()
  end

  local function world()
    return {
      game = "red",
      id = "TEST_HOUSE",
      revision = 1,
      width = 2,
      height = 1,
      cellSize = 16,
      mode = "first_person",
      tags = { interior = true },
      player = { cellX = 0, cellZ = 0, facing = "down" },
      cells = {
        { x = 0, z = 0, walkable = true, material = "room",
          tags = { interior = true, room = true, door = true } },
        { x = 1, z = 0, walkable = true, material = "room",
          tags = { interior = true, room = true, window = true } },
      },
    }
  end

  T.test("entry loads only mod-owned source and stays safe without a host", function()
    local mod, control = fakeMod(nil)
    loadEntry()(mod)
    T.equal(mod.exports.kfp.api, 1)
    T.falsy(mod.exports.kfp.available())
    T.truthy(#control.rows() > 40)
    T.falsy(control.hook(), "unsafe alpha gameplay hook must not be installed")
    T.truthy(control.hook("core.quit_to_launcher"))
    control.emit("mods.loaded", {})
    local status = mod.exports.kfp.status()
    T.equal(status.host.state, "inactive")
    T.equal(status.state, "waiting_for_host")
    T.equal(status.gameplay.ledgeLeap, "unavailable_alpha")
    T.equal(status.metrics.schema, 1)
    T.equal(status.metrics.capacity, 240)
    T.equal(status.metrics.submissions.callbacks, 0)
    T.equal(status.metrics.runtime.quality, "HIGH")
    for _, path in ipairs(control.reads) do
      T.truthy(path:match("^src/"))
      T.falsy(path:match("payload_"))
    end
    T.truthy(control.hook("core.quit_to_launcher")(function() return true end))
    T.equal(mod.exports.kfp.status().state, "disposed")
    T.truthy(mod.exports.kfp.status().resources.disposed)
  end)

  T.test("entry distinguishes stored v2 values from automatic row defaults", function()
    local mod, control = fakeMod(nil)
    control.options.shadows = false
    control.options.fastchunks = false
    control.options.contact_shadows = true
    control.options.quality = "HIGH"
    loadEntry()(mod)
    local record = control.saved["config/v2"]
    T.truthy(record)
    T.equal(record.values.contact_shadows, true)
    T.equal(record.values.quality, "HIGH")

    local legacyMod, legacyControl = fakeMod(nil)
    legacyControl.options.shadows = false
    legacyControl.options.fastchunks = false
    loadEntry()(legacyMod)
    local legacyRecord = legacyControl.saved["config/v2"]
    T.equal(legacyRecord.values.contact_shadows, false)
    T.equal(legacyRecord.values.quality, "LOW")
  end)

  T.test("entry attaches, compiles, renders, and disposes through API v1", function()
    local API = assert(loadfile(T.root .. "/companion/api_v1.lua"))()
    local dispatcher = API.new({
      host_id = "DRAMALESS_SHAPE",
      host_version = "2.0.3",
      capabilities = {
        "world_snapshot", "camera_delta", "render_phases", "quality_tier",
      },
    })
    local provider = dispatcher:provider()
    local mod, control = fakeMod(provider)
    loadEntry()(mod)
    control.emit("mods.loaded", {})
    T.equal(mod.exports.kfp.status().host.state, "attached")
    T.falsy(mod.exports.kfp.available())

    local submitted = { mesh = 0, instances = 0, billboards = 0,
      lights = 0, postprocess = 0 }
    local draw = {}
    for kind in pairs(submitted) do
      local captured = kind
      draw[captured] = function()
        submitted[captured] = submitted[captured] + 1
        return true
      end
    end
    local snapshot = world()
    T.truthy(dispatcher:attach({
      world = { snapshot = function() return snapshot end },
      quality = { tier = "HIGH", platform = "windows" },
      materials = {},
      draw = draw,
    }))
    T.truthy(dispatcher:start({ world = snapshot }))

    for _ = 1, 20 do
      dispatcher:dispatch("update", { frame = { dt = 1 / 60, playerSpeed = 1 } })
    end
    T.truthy(mod.exports.kfp.available())
    local context = {
      world = {},
      camera = { mode = "first_person" },
      frame = { dt = 1 / 60 },
      materials = {},
      draw = draw,
    }
    dispatcher:dispatch("opaque_after_terrain", context)
    T.truthy(submitted.instances > 0)
    local metrics = mod.exports.kfp.status().metrics
    T.equal(metrics.schema, 1)
    T.truthy(metrics.timing.update.total >= 1)
    T.truthy(metrics.timing.build.total >= 1)
    T.truthy(metrics.timing.render.total >= 1)
    T.truthy(metrics.scene.ready >= 1)
    T.truthy(metrics.submissions.callbacks >= 1)
    T.truthy(metrics.submissions.commands >= 1)
    T.equal(metrics.runtime.quality, "HIGH")
    T.truthy(type(metrics.runtime.cache.cost) == "number")
    local camera = dispatcher:dispatch_camera(context)
    T.truthy(type(camera.positionDelta.y) == "number")
    T.equal(mod.exports.kfp.status().scene.activeKey ~= nil, true)
    T.truthy(mod.exports.kfp.status().scene.activeKey:find(
      "host=DRAMALESS_SHAPE@2.0.3", 1, true))
    T.truthy(dispatcher:dispose({}, "test"))
    T.truthy(dispatcher:dispose({}, "again"))
    T.equal(mod.exports.kfp.status().state, "disposed")
    T.truthy(mod.exports.kfp.status().resources.disposed)
  end)

  T.test("entry owns packaged textures until the scene packet retires", function()
    local previousLove = love
    local ok, problem = pcall(function()
      local images, ticks = {}, 0
      love = {
        timer = { getTime = function() ticks = ticks + 1; return ticks / 1000 end },
        graphics = {
          newImage = function(path)
            local image = { path = path, releases = 0, filters = {}, wraps = {} }
            function image:release() self.releases = self.releases + 1 end
            function image:setFilter(minimum, maximum)
              self.filters = { minimum, maximum }
            end
            function image:setWrap(horizontal, vertical)
              self.wraps = { horizontal, vertical }
            end
            images[#images + 1] = image
            return image
          end,
        },
      }
      local API = assert(loadfile(T.root .. "/companion/api_v1.lua"))()
      local dispatcher = API.new({
        host_id = "DRAMALESS_SHAPE",
        host_version = "2.0.3",
        capabilities = {
          "world_snapshot", "camera_delta", "render_phases", "quality_tier",
        },
      })
      local mod, control = fakeMod(dispatcher:provider())
      loadEntry()(mod)
      control.emit("mods.loaded", {})
      local snapshot = {
        game = "red", id = "PALLET_TOWN", revision = 1,
        width = 1, height = 1, cellSize = 16, mode = "first_person",
        tags = {}, player = { cellX = 0, cellZ = 0, facing = "down" },
        cells = { { x = 0, z = 0, walkable = true, tags = {} } },
      }
      local captured
      local draw = {
        mesh = function(command)
          if command.material == "horizon:valley" then captured = command end
          return true
        end,
        instances = function() return true end,
        billboards = function() return true end,
      }
      T.truthy(dispatcher:attach({
        world = { snapshot = function() return snapshot end },
        quality = { tier = "HIGH", platform = "windows" },
        materials = {}, draw = draw,
      }))
      T.truthy(dispatcher:start({ world = snapshot }))
      for _ = 1, 20 do
        dispatcher:dispatch("update", { frame = { dt = 1 / 60 } })
      end
      dispatcher:dispatch("background", {
        world = {}, camera = {}, frame = {}, materials = {}, draw = draw,
      })
      T.truthy(captured)
      T.equal(#images, 4)
      T.equal(captured.texture, images[1])
      T.falsy(captured.geometry.asset)
      T.deepEqual(images[1].filters, { "nearest", "nearest" })
      T.deepEqual(images[1].wraps, { "repeat", "clamp" })
      for index = 2, 4 do
        T.deepEqual(images[index].filters, { "nearest", "nearest" })
        T.deepEqual(images[index].wraps, { "repeat", "repeat" })
      end
      for _, image in ipairs(images) do T.equal(image.releases, 0) end
      T.truthy(dispatcher:dispose({}, "texture_test"))
      for _, image in ipairs(images) do T.equal(image.releases, 1) end
    end)
    love = previousLove
    if not ok then error(problem, 0) end
  end)
end
