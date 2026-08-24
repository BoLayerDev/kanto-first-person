-- ROM-free proof for the KFP-owned part of v1-to-v2 migration and removal.
-- It executes the packaged entry and API v1 dispatcher against invented host
-- source strings. Actual host scanners and installed profiles remain manual
-- release evidence.

return function(T)
  local API = assert(loadfile(T.root .. "/companion/api_v1.lua"))()
  local ManifestPolicy = assert(loadfile(T.root .. "/tools/ManifestPolicy.lua"))()
  local fixtures = assert(loadfile(
    T.root .. "/tests/fixtures/migration_hosts.lua"
  ))()

  local function copy(value, seen)
    if type(value) ~= "table" then return value end
    seen = seen or {}
    if seen[value] then return seen[value] end
    local out = {}
    seen[value] = out
    for key, item in pairs(value) do out[copy(key, seen)] = copy(item, seen) end
    return out
  end

  local function scanHost(host, audit)
    local found = {}
    for _, path in ipairs(fixtures.paths) do
      audit.hostReads = audit.hostReads + 1
      local source = host.files[path]
      for _, marker in ipairs(fixtures.markers) do
        if source and source:find(marker, 1, true) then
          found[#found + 1] = { path = path, marker = marker }
        end
      end
    end
    return {
      clean = #found == 0,
      legacyMarkers = #found > 0,
      matches = found,
    }
  end

  local function strict(value, label, audit)
    return setmetatable({}, {
      __index = function(_, key)
        local item = value[key]
        if item ~= nil then return item end
        audit.unknownHostReads = audit.unknownHostReads + 1
        error(("unexpected %s field read: %s"):format(label, tostring(key)), 2)
      end,
      __newindex = function(_, key)
        audit.hostSurfaceWrites = audit.hostSurfaceWrites + 1
        error(("unexpected %s field write: %s"):format(label, tostring(key)), 2)
      end,
    })
  end

  local function makeHost(fixture, refuseLegacy)
    local host = copy(fixture)
    local before = copy(host.files)
    local audit = {
      hostReads = 0,
      hostSurfaceWrites = 0,
      unknownHostReads = 0,
      registrations = 0,
    }
    local dispatcher = API.new({
      host_id = host.id,
      host_version = host.version,
      capabilities = {
        "world_snapshot",
        "camera_delta",
        "render_phases",
        "quality_tier",
        "integrity_status",
      },
    })
    local exported = dispatcher:provider()
    local rawRegister = exported.register
    exported.register = function(spec, runningContext)
      audit.registrations = audit.registrations + 1
      local integrity = scanHost(host, audit)
      if refuseLegacy and integrity.legacyMarkers then
        return nil, "legacy KFP splice markers detected; reinstall the voxel host"
      end
      return rawRegister(spec, runningContext)
    end
    exported.host = strict(exported.host, "provider.host", audit)
    exported = strict(exported, "provider", audit)

    local handle = strict({
      id = host.id,
      version = host.version,
      exports = { voxel_companion = exported },
    }, "mod.find result", audit)

    return {
      audit = audit,
      before = before,
      dispatcher = dispatcher,
      findHandle = handle,
      host = host,
      integrity = function() return scanHost(host, audit) end,
    }
  end

  local function newState(legacyOptions)
    return {
      options = copy(legacyOptions or {}),
      saved = {},
    }
  end

  local function fakeMod(host, state)
    local rows = {}
    local listeners = {}
    local hooks = {}
    local audit = {
      entryRuns = 0,
      reads = {},
      saveReads = 0,
      saveWrites = 0,
    }
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
        define = function(_, schema) rows = schema end,
        get = function(_, key)
          if state.options[key] ~= nil then return state.options[key] end
          for _, row in ipairs(rows) do
            if row.key == key then return row.default end
          end
          return nil
        end,
      },
      save = {
        get = function(_, key)
          audit.saveReads = audit.saveReads + 1
          return state.saved[key]
        end,
        set = function(_, key, value)
          audit.saveWrites = audit.saveWrites + 1
          state.saved[key] = copy(value)
        end,
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
          local active = true
          return function()
            if not active then return end
            active = false
            for index, current in ipairs(listeners[name]) do
              if current == callback then table.remove(listeners[name], index); break end
            end
          end
        end,
      },
      hooks = {
        wrap = function(_, name, callback)
          hooks[name] = callback
          local active = true
          return function()
            if not active then return end
            active = false
            if hooks[name] == callback then hooks[name] = nil end
          end
        end,
      },
      world = { queueScript = function() return true end },
    }

    function mod:read(path)
      T.truthy(path:match("^src/"), "entry read outside KFP source: " .. path)
      T.falsy(path:find("..", 1, true), "entry used parent traversal")
      audit.reads[#audit.reads + 1] = path
      return T.read(path)
    end

    mod.find = function(id)
      if host and id == host.host.id then return host.findHandle end
      return nil
    end

    local control = {
      audit = audit,
      emit = function(name, payload)
        local callbacks = copy(listeners[name] or {})
        for _, callback in ipairs(callbacks) do callback(payload) end
      end,
      hook = function(name) return hooks[name] end,
      listenerCount = function()
        local count = 0
        for _, callbacks in pairs(listeners) do count = count + #callbacks end
        return count
      end,
      rowCount = function() return #rows end,
    }
    return mod, control
  end

  local function runEntry(mod, control)
    control.audit.entryRuns = control.audit.entryRuns + 1
    local entry = assert(loadfile(T.root .. "/main.lua"))()
    return entry(mod)
  end

  local function cleanServices(host)
    local snapshot = {
      game = "red",
      id = "MIGRATION_TEST_ROOM",
      revision = 1,
      width = 1,
      height = 1,
      cellSize = 16,
      mode = "first_person",
      tags = { interior = true },
      player = { cellX = 0, cellZ = 0, facing = "down" },
      cells = {
        { x = 0, z = 0, walkable = true, material = "room",
          tags = { interior = true, room = true } },
      },
    }
    return {
      snapshot = snapshot,
      services = {
        world = { snapshot = function() return snapshot end },
        quality = { tier = "HIGH", platform = "test" },
        integrity = { status = host.integrity },
        materials = {},
        draw = {
          mesh = function() return true end,
          instances = function() return true end,
          billboards = function() return true end,
        },
      },
    }
  end

  local function assertHostUnchanged(host)
    T.deepEqual(host.host.files, host.before, "synthetic host source changed")
    T.equal(host.audit.hostSurfaceWrites, 0)
    T.equal(host.audit.unknownHostReads, 0)
  end

  T.test("manifest keeps the no-permission migration boundary", function()
    local manifest, err = ManifestPolicy.decode(T.read("manifest.json"))
    T.truthy(manifest, err)
    T.equal(manifest.id, "ds_fp_ceiling")
    T.equal(#manifest.permissions, 0)
    T.deepEqual(manifest.optional_dependencies, {
      "BATTLE_ART_VOXEL_FORK",
      "DRAMALESS_SHAPE",
    })
  end)

  T.test("clean upgrade preserves options and host source through re-enable", function()
    local legacyOptions = {
      ceiling = false,
      shadows = false,
      fastchunks = false,
      remove = true,
      jumpkey = "j",
      jumppad = "x",
      vines = { true, false, true },
    }
    local rawBefore = copy(legacyOptions)
    local state = newState(legacyOptions)
    local host = makeHost(fixtures.clean, true)
    local mod, control = fakeMod(host, state)

    runEntry(mod, control)
    control.emit("mods.loaded", {})
    T.equal(mod.exports.kfp.status().host.state, "attached")
    T.equal(host.audit.registrations, 1)
    T.truthy(host.audit.hostReads > 0)

    local runtime = cleanServices(host)
    local attachReport = host.dispatcher:attach(runtime.services)
    T.equal(attachReport.failed, 0)
    local startReport = host.dispatcher:start({ world = runtime.snapshot })
    T.equal(startReport.failed, 0)

    local record = state.saved["config/v2"]
    T.truthy(record)
    T.equal(record.schema_version, 2)
    T.equal(record.values.ceiling, false)
    T.equal(record.values.contact_shadows, false)
    T.equal(record.values.object_shadows, true)
    T.equal(record.values.quality, "LOW")
    T.equal(record.values.ledge_key, "j")
    T.equal(record.values.ledge_pad, "x")
    T.equal(record.values.ledge_leap, false)
    T.equal(record.values.hanging_vines, true)
    T.equal(record.values.kfp_master_volume, 100)
    T.equal(record.values.kfp_ambient_volume, 100)
    T.equal(record.values.kfp_sfx_volume, 100)
    T.falsy(record.values.remove)
    T.equal(control.audit.saveWrites, 1)
    T.deepEqual(state.options, rawBefore, "legacy option storage changed")
    assertHostUnchanged(host)

    local savedBeforeDisable = copy(state.saved)
    local optionBeforeDisable = copy(state.options)
    local quit = control.hook("core.quit_to_launcher")
    T.truthy(quit)
    T.truthy(quit(function() return true end))
    T.equal(mod.exports.kfp.status().state, "disposed")
    T.truthy(mod.exports.kfp.status().resources.disposed)
    T.equal(control.listenerCount(), 0)
    T.falsy(control.hook("core.quit_to_launcher"))
    T.equal(#host.dispatcher:status().extensions, 0)
    T.deepEqual(state.saved, savedBeforeDisable)
    T.deepEqual(state.options, optionBeforeDisable)
    assertHostUnchanged(host)

    -- KFP-owned migration state remains stable after quit. The separate
    -- real-Loader test proves disabled and removed boot behavior.
    T.deepEqual(state.saved, savedBeforeDisable)
    T.deepEqual(state.options, optionBeforeDisable)

    local rebootHost = makeHost(fixtures.clean, true)
    local rebootMod, rebootControl = fakeMod(rebootHost, state)
    runEntry(rebootMod, rebootControl)
    rebootControl.emit("mods.loaded", {})
    T.equal(rebootMod.exports.kfp.status().host.state, "attached")
    T.equal(rebootControl.audit.saveWrites, 0,
      "stable migration record was rewritten")
    T.deepEqual(state.saved, savedBeforeDisable)
    T.deepEqual(state.options, optionBeforeDisable)
    T.truthy(rebootControl.hook("core.quit_to_launcher")(
      function() return true end
    ))
    assertHostUnchanged(rebootHost)
  end)

  T.test("synthetic host adapter refuses known legacy splice markers", function()
    local state = newState({ remove = true })
    local host = makeHost(fixtures.legacy, true)
    local mod, control = fakeMod(host, state)
    runEntry(mod, control)
    control.emit("mods.loaded", {})

    local status = mod.exports.kfp.status()
    T.equal(status.host.state, "failed")
    T.truthy(status.host.error:find("legacy KFP splice markers", 1, true))
    T.equal(#host.dispatcher:status().extensions, 0)
    T.equal(host.audit.registrations, 1)
    T.truthy(host.audit.hostReads > 0)
    T.equal(state.saved["config/v2"].schema_version, 2)
    T.falsy(state.saved["config/v2"].values.remove)
    T.deepEqual(state.options, { remove = true })
    assertHostUnchanged(host)

    T.truthy(control.hook("core.quit_to_launcher")(
      function() return true end
    ))
    T.equal(mod.exports.kfp.status().state, "disposed")
    T.truthy(mod.exports.kfp.status().resources.disposed)
    T.equal(control.listenerCount(), 0)
    assertHostUnchanged(host)
  end)

  T.test("KFP faults closed when integrity reports markers after registration", function()
    local state = newState({})
    local host = makeHost(fixtures.legacy, false)
    local mod, control = fakeMod(host, state)
    runEntry(mod, control)
    control.emit("mods.loaded", {})
    T.equal(mod.exports.kfp.status().host.state, "attached")

    local runtime = cleanServices(host)
    local report = host.dispatcher:attach(runtime.services)
    T.equal(report.failed, 1)
    T.equal(report.succeeded, 0)
    local dispatcherStatus = host.dispatcher:status()
    T.equal(dispatcherStatus.errorCount, 1)
    T.equal(dispatcherStatus.extensions[1].state, "faulted")
    T.truthy(dispatcherStatus.extensions[1].faulted)
    T.truthy(host.dispatcher:errors()[1].message:find(
      "legacy KFP splice markers detected", 1, true
    ))
    T.equal(mod.exports.kfp.status().state, "waiting_for_host")
    T.equal(mod.exports.kfp.status().host.state, "inactive")
    T.equal(mod.exports.kfp.status().resources.active, 0)
    T.falsy(mod.exports.kfp.status().resources.disposed)

    local startReport = host.dispatcher:start({ world = runtime.snapshot })
    T.equal(startReport.succeeded, 0)
    T.equal(startReport.failed, 0)
    T.equal(startReport.skipped, 0)
    local renderReport = host.dispatcher:render("opaque_after_terrain", {
      world = {}, camera = {}, frame = {}, materials = {}, draw = runtime.services.draw,
    })
    T.equal(renderReport.called, 0)
    assertHostUnchanged(host)

    T.truthy(control.hook("core.quit_to_launcher")(
      function() return true end
    ))
    T.equal(mod.exports.kfp.status().state, "disposed")
    T.truthy(mod.exports.kfp.status().resources.disposed)
    T.equal(control.listenerCount(), 0)
    T.equal(#host.dispatcher:status().extensions, 0)
    assertHostUnchanged(host)
  end)
end
