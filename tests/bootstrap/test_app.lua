return function(T)
  local function fakeMod(provider)
    local listeners, hooks, optionRows = {}, {}, {}
    local optionValues, saved, reads = {}, {}, {}
    local providers = {}
    if provider then providers[provider.host.id] = provider end
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
          local record = { callback = callback, active = true }
          listeners[name][#listeners[name] + 1] = record
          return function() record.active = false end
        end,
      },
      hooks = {
        wrap = function(_, name, callback)
          local record = { callback = callback }
          hooks[name] = record
          return function()
            if hooks[name] == record then hooks[name] = nil end
          end
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
      local selected = providers[id]
      if selected then
        return { id = id, version = selected.host.version,
          exports = { voxel_companion = selected } }
      end
      return nil
    end
    local control = {
      emit = function(name, payload)
        for _, record in ipairs(listeners[name] or {}) do
          if record.active then record.callback(payload) end
        end
      end,
      setProvider = function(nextProvider)
        providers = {}
        if nextProvider then providers[nextProvider.host.id] = nextProvider end
      end,
      addProvider = function(nextProvider)
        providers[nextProvider.host.id] = nextProvider
      end,
      removeProvider = function(id) providers[id] = nil end,
      listenerCount = function()
        local count = 0
        for _, records in pairs(listeners) do
          for _, record in ipairs(records) do
            if record.active then count = count + 1 end
          end
        end
        return count
      end,
      subscriptionCount = function()
        local count = 0
        for _, records in pairs(listeners) do
          for _, record in ipairs(records) do
            if record.active then count = count + 1 end
          end
        end
        for _ in pairs(hooks) do count = count + 1 end
        return count
      end,
      reads = reads,
      rows = function() return optionRows end,
      hook = function(name)
        local record = hooks[name or "input.step"]
        return record and record.callback or nil
      end,
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

  local function newHost(API, id, version)
    return API.new({
      host_id = id,
      host_version = version,
      capabilities = {
        "world_snapshot", "camera_delta", "render_phases", "quality_tier",
      },
    })
  end

  local function hostServices(snapshot, integrity)
    return {
      world = { snapshot = function() return snapshot end },
      quality = { tier = "HIGH", platform = "windows" },
      materials = {},
      draw = {
        mesh = function() return true end,
        instances = function() return true end,
        billboards = function() return true end,
        lights = function() return true end,
        postprocess = function() return true end,
      },
      integrity = integrity,
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
    T.equal(mod.exports.kfp.status().state, "waiting_for_host")
    T.equal(mod.exports.kfp.status().host.state, "inactive")
    T.equal(mod.exports.kfp.status().resources.active, 0)
    T.falsy(mod.exports.kfp.status().resources.disposed)
    T.truthy(control.hook("core.quit_to_launcher")(function() return true end))
    T.equal(mod.exports.kfp.status().state, "disposed")
    T.truthy(mod.exports.kfp.status().resources.disposed)
  end)

  T.test("entry owns packaged textures until the scene packet retires", function()
    local previousLove = love
    local ok, problem = pcall(function()
      local images, ticks = {}, 0
      love = {
        timer = { getTime = function() ticks = ticks + 1; return ticks / 100000 end },
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
      local captured, seenMaterials = nil, {}
      local draw = {
        mesh = function(command)
          seenMaterials[#seenMaterials + 1] = tostring(command.material)
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
      }), "host attach failed")
      T.truthy(dispatcher:start({ world = snapshot }), "host start failed")
      for _ = 1, 2000 do
        dispatcher:dispatch("update", { frame = { dt = 1 / 60 } })
        if mod.exports.kfp.status().scene.activeKey then break end
      end
      T.truthy(mod.exports.kfp.status().scene.activeKey,
        "incremental scene did not become ready")
      dispatcher:dispatch("background", {
        world = {}, camera = {}, frame = {}, materials = {}, draw = draw,
      })
      T.truthy(captured, "horizon draw was not submitted: "
        .. table.concat(seenMaterials, ","))
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
      T.truthy(dispatcher:dispose({}, "texture_test"), "host dispose failed")
      for _, image in ipairs(images) do T.equal(image.releases, 1) end
      T.equal(mod.exports.kfp.status().state, "waiting_for_host")
      T.equal(mod.exports.kfp.status().resources.active, 0)
      T.truthy(control.hook("core.quit_to_launcher")(function() return true end))
      for _, image in ipairs(images) do T.equal(image.releases, 1) end
    end)
    love = previousLove
    if not ok then error(problem, 0) end
  end)

  T.test("a live provider swap replaces one host without duplicate registration", function()
    local API = assert(loadfile(T.root .. "/companion/api_v1.lua"))()
    local first = newHost(API, "DRAMALESS_SHAPE", "2.0.3")
    local replacement = newHost(API, "DRAMALESS_SHAPE", "2.0.4")
    local mod, control = fakeMod(first:provider())
    loadEntry()(mod)
    control.emit("mods.loaded", {})
    local firstWorld = world()
    T.truthy(first:attach(hostServices(firstWorld)))
    T.truthy(first:start({ world = firstWorld }))
    T.equal(#first:status().extensions, 1)

    control.emit("game.ready", {})
    T.equal(#first:status().extensions, 1)
    T.equal(mod.exports.kfp.status().resources.releases, 0)

    control.setProvider(replacement:provider())
    control.emit("mods.loaded", {})
    local swapped = mod.exports.kfp.status()
    T.equal(swapped.state, "attached")
    T.equal(swapped.host.hostId, "DRAMALESS_SHAPE")
    T.equal(swapped.host.hostVersion, "2.0.4")
    T.equal(swapped.resources.active, 1)
    T.equal(swapped.resources.releases, 1)
    T.equal(#first:status().extensions, 0)
    T.equal(#replacement:status().extensions, 1)

    T.truthy(first:dispose({}, "stale_host_shutdown"))
    T.equal(mod.exports.kfp.status().state, "attached")
    T.equal(mod.exports.kfp.status().resources.active, 1)
    T.equal(mod.exports.kfp.status().resources.releases, 1)

    local secondWorld = world()
    secondWorld.revision = 2
    T.truthy(replacement:attach(hostServices(secondWorld)))
    T.truthy(replacement:start({ world = secondWorld }))
    T.truthy(mod.exports.kfp.available())
    T.truthy(control.hook("core.quit_to_launcher")(function() return true end))
    T.equal(mod.exports.kfp.status().state, "disposed")
    T.equal(mod.exports.kfp.status().resources.releases, 2)
  end)

  T.test("host disposal keeps the app alive for one later compatible host", function()
    local API = assert(loadfile(T.root .. "/companion/api_v1.lua"))()
    local first = newHost(API, "DRAMALESS_SHAPE", "2.0.3")
    local replacement = newHost(API, "BATTLE_ART_VOXEL_FORK", "3.1.0")
    local mod, control = fakeMod(first:provider())
    loadEntry()(mod)

    control.emit("mods.loaded", {})
    T.equal(mod.exports.kfp.status().state, "attached")
    local firstWorld = world()
    T.truthy(first:attach(hostServices(firstWorld)))
    T.truthy(first:start({ world = firstWorld }))
    T.truthy(mod.exports.kfp.available())
    T.equal(mod.exports.kfp.status().resources.active, 1)

    control.setProvider(nil)
    T.truthy(first:dispose({}, "host_reload"))
    T.truthy(first:dispose({}, "host_reload_again"))
    local waiting = mod.exports.kfp.status()
    T.equal(waiting.state, "waiting_for_host")
    T.equal(waiting.host.state, "inactive")
    T.falsy(waiting.worldKey)
    T.falsy(waiting.scene)
    T.equal(waiting.resources.active, 0)
    T.equal(waiting.resources.releases, 1)
    T.falsy(waiting.resources.disposed)
    T.equal(control.subscriptionCount(), 6)

    control.emit("mods.loaded", {})
    T.equal(mod.exports.kfp.status().host.error, "no compatible voxel host")
    control.setProvider(replacement:provider())
    control.emit("game.ready", {})
    local reconnected = mod.exports.kfp.status()
    T.equal(reconnected.state, "attached")
    T.equal(reconnected.host.hostId, "BATTLE_ART_VOXEL_FORK")
    T.equal(reconnected.resources.active, 1)
    T.equal(reconnected.resources.releases, 1)

    local secondWorld = world()
    secondWorld.game = "yellow"
    secondWorld.id = "REPLACEMENT_HOUSE"
    secondWorld.revision = 2
    T.truthy(replacement:attach(hostServices(secondWorld)))
    T.truthy(replacement:start({ world = secondWorld }))
    T.truthy(mod.exports.kfp.available())
    T.truthy(mod.exports.kfp.status().scene.buildingKey:find(
      "host=BATTLE_ART_VOXEL_FORK@3.1.0", 1, true))

    control.setProvider(nil)
    T.truthy(replacement:dispose({}, "replacement_removed"))
    T.equal(mod.exports.kfp.status().resources.active, 0)
    T.equal(mod.exports.kfp.status().resources.releases, 2)
    T.truthy(control.hook("core.quit_to_launcher")(function() return true end))
    local stopped = mod.exports.kfp.status()
    T.equal(stopped.state, "disposed")
    T.equal(stopped.resources.releases, 2)
    T.truthy(stopped.resources.disposed)
    T.equal(control.subscriptionCount(), 0)
  end)

  T.test("host overlap and callback fault fail closed before replacement", function()
    local API = assert(loadfile(T.root .. "/companion/api_v1.lua"))()
    local first = newHost(API, "DRAMALESS_SHAPE", "2.0.3")
    local faulting = newHost(API, "BATTLE_ART_VOXEL_FORK", "3.1.0")
    local mod, control = fakeMod(first:provider())
    loadEntry()(mod)
    control.emit("mods.loaded", {})
    T.equal(mod.exports.kfp.status().state, "attached")

    control.addProvider(faulting:provider())
    control.emit("mods.loaded", {})
    local overlap = mod.exports.kfp.status()
    T.equal(overlap.state, "waiting_for_host")
    T.equal(overlap.host.state, "inactive")
    T.equal(overlap.host.error, "multiple compatible voxel hosts")
    T.equal(overlap.resources.active, 0)
    T.equal(overlap.resources.releases, 1)
    T.equal(#first:status().extensions, 0)

    control.removeProvider("DRAMALESS_SHAPE")
    control.emit("game.ready", {})
    T.equal(mod.exports.kfp.status().state, "attached")
    local faultWorld = world()
    local faultReport = faulting:attach(hostServices(faultWorld, {
      status = function() return { clean = false, legacyMarkers = true } end,
    }))
    T.truthy(faultReport)
    T.equal(faultReport.failed, 1)
    local faulted = mod.exports.kfp.status()
    T.equal(faulted.state, "waiting_for_host")
    T.equal(faulted.host.state, "inactive")
    T.equal(faulted.resources.active, 0)
    T.equal(faulted.resources.releases, 2)
    T.falsy(faulted.worldKey)

    local good = newHost(API, "BATTLE_ART_VOXEL_FORK", "3.1.1")
    control.setProvider(good:provider())
    control.emit("mods.loaded", {})
    T.equal(mod.exports.kfp.status().state, "attached")
    local goodWorld = world()
    goodWorld.revision = 3
    T.truthy(good:attach(hostServices(goodWorld)))
    T.truthy(good:start({ world = goodWorld }))
    T.truthy(mod.exports.kfp.available())
    T.equal(mod.exports.kfp.status().resources.active, 1)

    control.setProvider(nil)
    T.truthy(good:dispose({}, "test_complete"))
    T.equal(mod.exports.kfp.status().resources.releases, 3)
    T.truthy(control.hook("core.quit_to_launcher")(function() return true end))
  end)

  T.test("one app survives 100 bounded host replacement cycles", function()
    local API = assert(loadfile(T.root .. "/companion/api_v1.lua"))()
    local mod, control = fakeMod(nil)
    loadEntry()(mod)
    control.emit("mods.loaded", {})
    T.equal(mod.exports.kfp.status().state, "waiting_for_host")

    for cycle = 1, 100 do
      local hostId = cycle % 2 == 0 and "DRAMALESS_SHAPE"
        or "BATTLE_ART_VOXEL_FORK"
      local dispatcher = newHost(API, hostId, "stress." .. tostring(cycle))
      control.setProvider(dispatcher:provider())
      control.emit("mods.loaded", {})
      local attached = mod.exports.kfp.status()
      T.equal(attached.state, "attached", "attach cycle " .. cycle)
      T.equal(attached.resources.active, 1, "owner cycle " .. cycle)
      T.equal(attached.resources.releases, cycle - 1,
        "release count before cycle " .. cycle)

      local snapshot = world()
      snapshot.id = "STRESS_HOUSE_" .. tostring(cycle)
      snapshot.revision = cycle
      T.truthy(dispatcher:attach(hostServices(snapshot)),
        "service attach cycle " .. cycle)
      T.truthy(dispatcher:start({ world = snapshot }),
        "start cycle " .. cycle)
      control.emit("map.entered", { via = "warp" })
      control.options.head_bob = cycle % 2 == 0
      control.emit("mod.options_changed", {
        mod = mod.id,
        key = "head_bob",
      })
      snapshot.revision = cycle + 1000
      T.truthy(dispatcher:world_changed(snapshot),
        "map change cycle " .. cycle)
      T.truthy(dispatcher:update({ dt = 1 / 60, playerSpeed = 1 }),
        "update cycle " .. cycle)

      control.setProvider(nil)
      T.truthy(dispatcher:dispose({}, "stress_remove"),
        "dispose cycle " .. cycle)
      T.truthy(dispatcher:dispose({}, "stress_remove_again"),
        "repeat dispose cycle " .. cycle)
      local removed = mod.exports.kfp.status()
      T.equal(removed.state, "waiting_for_host", "wait cycle " .. cycle)
      T.equal(removed.host.state, "inactive", "inactive cycle " .. cycle)
      T.equal(removed.resources.active, 0, "active leak cycle " .. cycle)
      T.equal(removed.resources.releases, cycle,
        "exact release cycle " .. cycle)
      T.falsy(removed.resources.disposed, "runtime ended at cycle " .. cycle)
      T.falsy(removed.worldKey, "world leak cycle " .. cycle)
      T.falsy(removed.scene, "scene leak cycle " .. cycle)
      T.equal(removed.metrics.capacity, 240)

      control.emit("map.entered", { via = "warp" })
      control.emit("world.stepped", {
        mapId = snapshot.id,
        x = 0,
        y = 0,
      })
      control.emit("mods.loaded", {})
      T.equal(mod.exports.kfp.status().host.error,
        "no compatible voxel host")
      T.equal(control.subscriptionCount(), 6)
    end

    T.truthy(control.hook("core.quit_to_launcher")(function() return true end))
    local stopped = mod.exports.kfp.status()
    T.equal(stopped.state, "disposed")
    T.equal(stopped.resources.active, 0)
    T.equal(stopped.resources.releases, 100)
    T.truthy(stopped.resources.disposed)
    T.equal(control.subscriptionCount(), 0)
  end)
end
