-- Run the exact KFP package through a checked-out Gen1recomp Loader.
--
-- Usage: luajit tools/test_engine_migration.lua <gen1recomp-root>
--
-- The filesystem is in memory. Host source is invented test data. No ROM,
-- installed mod, live profile, or host checkout is read or changed.

local function normalize(path)
  return (tostring(path):gsub("\\", "/"):gsub("/+", "/"))
end

local function quote(path)
  if package.config:sub(1, 1) == "\\" then
    return '"' .. tostring(path):gsub('"', '""') .. '"'
  end
  return "'" .. tostring(path):gsub("'", "'\\''") .. "'"
end

local source = normalize(debug.getinfo(1, "S").source:gsub("^@", ""))
local toolsDir = assert(source:match("^(.*)/[^/]+$"), "cannot resolve tools path")
local projectRoot = toolsDir:match("^(.*)/tools$") or "."
local engineRoot = normalize(assert(arg[1], "Gen1recomp root is required"))

local function readFile(path)
  local file, err = io.open(path, "rb")
  assert(file, ("cannot read %s: %s"):format(path, tostring(err)))
  local body = file:read("*a")
  file:close()
  return body
end

local function copy(value, seen)
  if type(value) ~= "table" then return value end
  seen = seen or {}
  if seen[value] then return seen[value] end
  local out = {}
  seen[value] = out
  for key, item in pairs(value) do out[copy(key, seen)] = copy(item, seen) end
  return out
end

local function equal(left, right, seen)
  if left == right then return true end
  if type(left) ~= "table" or type(right) ~= "table" then return false end
  seen = seen or {}
  if seen[left] then return seen[left] == right end
  seen[left] = right
  for key, value in pairs(left) do
    if not equal(value, right[key], seen) then return false end
  end
  for key in pairs(right) do
    if left[key] == nil then return false end
  end
  return true
end

local function check(condition, message)
  if not condition then error(message, 2) end
end

package.path = engineRoot .. "/?.lua;" .. engineRoot .. "/?/init.lua;"
  .. package.path

local Loader = assert(loadfile(engineRoot .. "/src/mods/Loader.lua"))()
local loadChunk = loadstring or load

local function trackedRuntimeFiles()
  local command = "git -C " .. quote(projectRoot)
    .. " ls-files -- main.lua manifest.json transform_birds.lua src"
  local pipe = assert(io.popen(command, "r"), "cannot list KFP runtime files")
  local files = {}
  for line in pipe:lines() do
    local relative = normalize(line)
    if relative ~= "" then files[#files + 1] = relative end
  end
  check(pipe:close(), "cannot finish KFP runtime file list")
  table.sort(files)
  check(#files > 20, "KFP runtime file list is unexpectedly small")
  return files
end

local RUNTIME_FILES = trackedRuntimeFiles()
local KFP_ID = "ds_fp_ceiling"
local HOST_ID = "DRAMALESS_SHAPE"

local HOST_MANIFEST = [[{
  "id":"DRAMALESS_SHAPE",
  "name":"Synthetic Dramaless Host",
  "version":"2.0.3",
  "entry":"main.lua",
  "api":2,
  "profile":"overhaul",
  "games":["gen1"],
  "priority":100,
  "permissions":[]
}]]

local HOST_ENTRY = [=[
local function module(mod, path)
  local source = assert(mod:read(path))
  return assert(load(source, "@" .. path))()
end

return function(mod)
  local API = module(mod, "api_v1.lua")
  local paths = { "ChunkMesher.lua", "Structures.lua" }
  local markers = {
    "KFP_LEGACY_SPLICE_BEGIN", "payload_backdrop", "payload_ceiling",
    "payload_flora", "payload_jump", "payload_sky",
  }
  local scans = 0
  local function integrity()
    scans = scans + 1
    local matches = {}
    for _, path in ipairs(paths) do
      local source = mod:read(path)
      for _, marker in ipairs(markers) do
        if source and source:find(marker, 1, true) then
          matches[#matches + 1] = { path = path, marker = marker }
        end
      end
    end
    return {
      clean = #matches == 0,
      legacyMarkers = #matches > 0,
      matches = matches,
    }
  end

  local dispatcher = API.new({
    host_id = mod.id,
    host_version = mod.version,
    capabilities = {
      "world_snapshot", "camera_delta", "render_phases", "quality_tier",
      "integrity_status",
    },
  })
  local provider = dispatcher:provider()
  local register = provider.register
  provider.register = function(spec, runningContext)
    local status = integrity()
    if __REFUSE_LEGACY__ and status.legacyMarkers then
      return nil, "legacy KFP splice markers detected; reinstall the voxel host"
    end
    return register(spec, runningContext)
  end
  mod.exports.voxel_companion = provider
  mod.exports.migration_test = {
    status = function() return dispatcher:status() end,
    errors = function() return dispatcher:errors() end,
    scans = function() return scans end,
  }

  local snapshot = {
    game = "red", id = "MIGRATION_TEST_ROOM", revision = 1,
    width = 1, height = 1, cellSize = 16, mode = "first_person",
    tags = { interior = true },
    player = { cellX = 0, cellZ = 0, facing = "down" },
    cells = {
      { x = 0, z = 0, walkable = true, material = "room",
        tags = { interior = true, room = true } },
    },
  }
  local services = {
    world = { snapshot = function() return snapshot end },
    quality = { tier = "HIGH", platform = "headless" },
    integrity = { status = integrity },
    materials = {},
    draw = {
      mesh = function() return true end,
      instances = function() return true end,
      billboards = function() return true end,
    },
  }
  mod.events:on("mods.loaded", function()
    dispatcher:attach(services)
    dispatcher:start({ world = snapshot })
  end, -100)
end
]=]

local function optionsSource(kfpEnabled)
  return ([=[return {
  mods = { DRAMALESS_SHAPE = true, ds_fp_ceiling = %s },
  modOptions = {
    ds_fp_ceiling = {
      ceiling = false,
      shadows = false,
      fastchunks = false,
      remove = true,
      jumpkey = "j",
      jumppad = "x",
      vines = true,
    },
  },
}
]=]):format(kfpEnabled and "true" or "false")
end

local function makeFiles(options)
  options = options or {}
  local files = {
    ["options.lua"] = optionsSource(options.enabled ~= false),
    ["mods/DRAMALESS_SHAPE/manifest.json"] = HOST_MANIFEST,
    ["mods/DRAMALESS_SHAPE/main.lua"] = HOST_ENTRY:gsub(
      "__REFUSE_LEGACY__", options.refuseLegacy == false and "false" or "true"
    ),
    ["mods/DRAMALESS_SHAPE/api_v1.lua"] = readFile(
      projectRoot .. "/companion/api_v1.lua"
    ),
    ["mods/DRAMALESS_SHAPE/ChunkMesher.lua"] = options.legacy
      and "return { payload_sky = true }\n"
      or "return { mesher = 'synthetic-clean' }\n",
    ["mods/DRAMALESS_SHAPE/Structures.lua"] = options.legacy
      and "-- KFP_LEGACY_SPLICE_BEGIN\nreturn { payload_ceiling = true }\n"
      or "return { structures = 'synthetic-clean' }\n",
  }
  if options.installed ~= false then
    for _, relative in ipairs(RUNTIME_FILES) do
      files["mods/" .. KFP_ID .. "/" .. relative] = readFile(
        projectRoot .. "/" .. relative
      )
    end
  end
  return files
end

local function hostSnapshot(files)
  local out = {}
  local prefix = "mods/" .. HOST_ID .. "/"
  for path, body in pairs(files) do
    if path:sub(1, #prefix) == prefix then out[path] = body end
  end
  return out
end

local function memoryFs(files)
  local audit = { writes = {}, hostWrites = 0 }
  local fs = {}
  function fs.read(path) return files[path] end
  function fs.write(path, body)
    audit.writes[#audit.writes + 1] = path
    if path:match("^mods/" .. HOST_ID .. "/") then
      audit.hostWrites = audit.hostWrites + 1
      error("write into synthetic host: " .. path)
    end
    if path:match("^mods/" .. KFP_ID .. "/") then
      error("write into KFP package: " .. path)
    end
    files[path] = body
    return true
  end
  function fs.getInfo(path)
    if files[path] ~= nil then
      return { type = "file", size = #tostring(files[path]) }
    end
    local prefix = path .. "/"
    for candidate in pairs(files) do
      if candidate:sub(1, #prefix) == prefix then return { type = "directory" } end
    end
    return nil
  end
  function fs.load(path)
    local body = files[path]
    if body == nil then return nil, "no file: " .. path end
    return loadChunk(body, "@" .. path)
  end
  function fs.getDirectoryItems(path)
    local prefix = path == "" and "" or (path .. "/")
    local seen, items = {}, {}
    for candidate in pairs(files) do
      if candidate:sub(1, #prefix) == prefix then
        local child = candidate:sub(#prefix + 1):match("^[^/]+")
        if child and not seen[child] then
          seen[child] = true
          items[#items + 1] = child
        end
      end
    end
    table.sort(items)
    return items
  end
  function fs.createDirectory() return true end
  return fs, audit
end

local function ownerCount(collection, owner)
  local count = 0
  for _, entries in pairs(collection or {}) do
    for _, entry in ipairs(entries) do
      if entry.owner == owner then count = count + 1 end
    end
  end
  return count
end

local function storedOptions(files)
  local chunk, err = loadChunk(files["options.lua"], "@options.lua")
  check(chunk ~= nil, "cannot decode stored options: " .. tostring(err))
  local ok, options = pcall(chunk)
  check(ok and type(options) == "table", "stored options are invalid")
  return options
end

local function boot(options, storedRecord)
  local files = makeFiles(options)
  local hostBefore = hostSnapshot(files)
  local fs, audit = memoryFs(files)
  local loader = Loader.new({ fs = fs, generation = 1 })
  if storedRecord then
    loader.modSave[KFP_ID] = { ["config/v2"] = storedRecord }
  end
  local ok = loader:load({})
  check(equal(hostSnapshot(files), hostBefore), "host source changed during boot")
  check(audit.hostWrites == 0, "host source received a write")
  return {
    audit = audit,
    files = files,
    loader = loader,
    ok = ok,
  }
end

local clean = boot({ enabled = true })
check(clean.ok == true, "clean KFP Loader boot failed")
check(clean.loader.mods[KFP_ID].state == "loaded", "KFP did not load")
local kfp = assert(clean.loader.exports[KFP_ID]).kfp
check(kfp.status().host.state == "attached", "KFP did not attach to clean host")
check(kfp.available() == true, "clean synthetic world did not become available")
check(kfp.status().quality == "LOW", "legacy fastchunks did not select LOW")
local record = assert(clean.loader.modSave[KFP_ID])["config/v2"]
check(type(record) == "table" and record.schema_version == 2,
  "KFP migration record is missing")
check(record.values.ceiling == false, "ceiling option was not preserved")
check(record.values.contact_shadows == false, "shadow option was not migrated")
check(record.values.object_shadows == true, "object shadow default is wrong")
check(record.values.quality == "LOW", "quality migration is wrong")
check(record.values.ledge_key == "j" and record.values.ledge_pad == "x",
  "jump preferences were not preserved")
check(record.values.ledge_leap == false, "Ledge Leap was not forced off")
check(record.values.remove == nil, "retired remove option entered v2 state")
local legacyStored = storedOptions(clean.files).modOptions[KFP_ID]
check(legacyStored.remove == true, "Loader or KFP deleted retired option data")
check(legacyStored.shadows == false and legacyStored.fastchunks == false,
  "Loader or KFP changed legacy option data")
check(legacyStored.jumpkey == "j" and legacyStored.jumppad == "x",
  "Loader or KFP changed saved bindings")

check(clean.loader.hooks:call("core.quit_to_launcher", function() return true end),
  "quit hook did not return the engine result")
check(kfp.status().state == "disposed", "KFP did not dispose on quit")
check(kfp.status().resources.disposed == true, "KFP resources stayed live")
check(#clean.loader.exports[HOST_ID].migration_test.status().extensions == 0,
  "KFP companion registration survived quit")
check(ownerCount(clean.loader.events.listeners, KFP_ID) == 0,
  "KFP event subscription survived quit")
check(ownerCount(clean.loader.hooks.chains, KFP_ID) == 0,
  "KFP hook subscription survived quit")

local disabled = boot({ enabled = false })
check(disabled.ok == true, "disabled KFP Loader boot failed")
check(disabled.loader.mods[KFP_ID].state == "disabled", "KFP is not disabled")
check(disabled.loader.exports[KFP_ID] == nil, "disabled KFP entry ran")
check(disabled.loader.modSave[KFP_ID] == nil, "disabled KFP wrote save state")
check(disabled.loader.optionSchemas[KFP_ID] == nil,
  "disabled KFP defined option rows")

local removed = boot({ installed = false, enabled = false })
check(removed.ok == true, "removed KFP Loader boot failed")
check(removed.loader.mods[KFP_ID] == nil, "removed KFP was discovered")
check(removed.loader.exports[KFP_ID] == nil, "removed KFP entry ran")
check(removed.loader.modSave[KFP_ID] == nil, "removed KFP wrote save state")

local persisted = copy(record)
local reenabled = boot({ enabled = true }, persisted)
check(reenabled.ok == true, "re-enabled KFP Loader boot failed")
check(reenabled.loader.modSave[KFP_ID]["config/v2"] == persisted,
  "stable migration record was rewritten")
check(equal(reenabled.loader.modSave[KFP_ID]["config/v2"], record),
  "re-enabled migration record changed")
check(reenabled.loader.exports[KFP_ID].kfp.status().quality == "LOW",
  "re-enabled KFP lost migrated quality")
reenabled.loader.hooks:call("core.quit_to_launcher", function() return true end)

local refused = boot({ enabled = true, legacy = true })
check(refused.ok == true, "legacy-refusal Loader boot failed")
local refusedKfp = refused.loader.exports[KFP_ID].kfp.status()
check(refusedKfp.host.state == "failed", "legacy host was not refused")
check(refusedKfp.host.error:find("legacy KFP splice markers", 1, true),
  "legacy refusal message is missing")
check(#refused.loader.exports[HOST_ID].migration_test.status().extensions == 0,
  "refused KFP registered with the host")
refused.loader.hooks:call("core.quit_to_launcher", function() return true end)

local defended = boot({ enabled = true, legacy = true, refuseLegacy = false })
check(defended.ok == true, "fail-closed Loader boot failed")
local defendedKfp = defended.loader.exports[KFP_ID].kfp
local hostTest = defended.loader.exports[HOST_ID].migration_test
local hostStatus = hostTest.status()
check(defendedKfp.status().state == "waiting_for_host",
  "KFP did not return to the safe no-host state")
check(defendedKfp.status().host.state == "inactive",
  "faulted KFP kept a host active")
check(defendedKfp.status().resources.active == 0
    and defendedKfp.status().resources.disposed == false,
  "faulted KFP did not release its host scope")
check(hostStatus.errorCount == 1 and hostStatus.extensions[1].faulted == true,
  "companion dispatcher did not record the integrity fault")
check(hostTest.errors()[1].message:find("legacy KFP splice markers", 1, true),
  "integrity fault message is missing")
defended.loader.hooks:call("core.quit_to_launcher", function() return true end)
check(defendedKfp.status().state == "disposed",
  "faulted KFP runtime did not dispose on quit")
check(defendedKfp.status().resources.disposed == true,
  "faulted KFP runtime resources stayed live on quit")
check(#hostTest.status().extensions == 0,
  "faulted KFP registration survived quit")

io.write("engine Loader migration safety passed\n")
