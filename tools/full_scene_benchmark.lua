-- ROM-free compiler workloads for the controlled reference benchmark.
-- Feature module prototypes are loaded once. Every attempt creates fresh
-- feature instances, compiler, command buffer, asset service, and request key.

local Bootstrap = assert(loadfile("tools/test_bootstrap.lua"))()

local function load(relative)
  return assert(loadfile(Bootstrap.path(relative)))()
end

local API = load("companion/api_v1.lua")
local AuthoredFixture = load("tests/fixtures/synthetic_kfp/cases.lua")
local CommandBuffer = load("src/render/CommandBuffer.lua")
local Config = load("src/config/Config.lua")
local PacketHash = load("src/render/PacketHash.lua")
local Quality = load("src/render/Quality.lua")
local SceneCompiler = load("src/render/SceneCompiler.lua")
local Util = load("src/features/Util.lua")
local WorldSnapshot = load("src/companion/WorldSnapshot.lua")

local FEATURE_PATHS = {
  "src/features/Interior.lua",
  "src/features/Cave.lua",
  "src/features/WorldGeometry.lua",
  "src/features/Battle.lua",
  "src/features/Atmosphere.lua",
  "src/features/Flora.lua",
  "src/features/Weather.lua",
  "src/features/Wildlife.lua",
  "src/features/Camera.lua",
}

local FEATURE_MODULES = {}
for index, path in ipairs(FEATURE_PATHS) do
  local prototype = load(path)
  if type(prototype) ~= "table" or type(prototype.new) ~= "function" then
    error("full-scene feature module has no constructor: " .. path)
  end
  FEATURE_MODULES[index] = { path = path, prototype = prototype }
end

local PHASE_ORDER = CommandBuffer.phases()
local PHASES = {}
for phase in pairs(PHASE_ORDER) do PHASES[#PHASES + 1] = phase end
table.sort(PHASES, function(a, b) return PHASE_ORDER[a] < PHASE_ORDER[b] end)

-- These optional kinds are not part of the API v1 baseline. Do not make them
-- part of new benchmark goldens.
local FINGERPRINT_EXCLUDED_KINDS = {
  lights = true,
  postprocess = true,
}

local PROFILE_OPERATIONS = {
  { name = "begin_seal", method = "_beginSeal" },
  { name = "seal", method = "_stepSeal" },
  { name = "validate", method = "_stepValidation" },
  { name = "cost", method = "_stepCost" },
  { name = "commit", method = "_commitPacket" },
}

local FullScene = {
  AUTHORED_FIXTURE_KIND = AuthoredFixture.fixtureKind,
  DEFAULT_SIZE = 64,
  FRAME_MS = 1000 / 60,
}

local function integer(value, minimum, maximum, name)
  value = tonumber(value)
  if not value or value ~= math.floor(value)
      or value < minimum or value > maximum then
    error((name or "value") .. " is outside its supported integer range", 3)
  end
  return value
end

local function milliseconds(clock, started)
  return (clock() - started) * 1000
end

local function cellRecord(x, z)
  local tags = { forest = true }
  local kind, material = "ground", "synthetic:forest_floor"
  local solid, walkable, height = false, true, 0
  local mx, mz = x % 16, z % 16

  if mz == 4 and (mx == 4 or mx == 5) then
    kind, material = "cliff", "synthetic:mountain"
    solid, walkable, height = true, false, 16
    tags.mountain = true
    tags.mountain_support = true
    tags.object = true
    if mx == 4 then tags.mountain_seed = true end
  elseif x % 8 == 2 and z % 8 == 2 then
    kind, material = "tree", "synthetic:tree"
    solid, walkable, height = true, false, 16
    tags.tree = true
    tags.tree_support = true
    tags.object = true
  elseif mx == 10 and mz == 10 then
    kind, material = "cylinder", "synthetic:boulder"
    solid, walkable, height = true, false, 16
    tags.boulder = true
    tags.boulder_tree = true
    tags.object = true
  elseif (x * 3 + z * 5) % 29 == 0 then
    kind, material = "wall", "synthetic:object"
    solid, walkable, height = true, false, 16
    tags.object = true
    if (x + z) % 2 == 0 then tags.chimney = true end
  else
    tags.grass = true
    if (x + z * 3) % 7 == 0 then tags.vine = true end
    if (x * 5 + z) % 31 == 0 then tags.sun_shaft = true end
    if (x * 7 + z * 11) % 43 == 0 then tags.shore = true end
  end

  return {
    x = x,
    z = z,
    worldY = 0,
    height = height,
    kind = kind,
    material = material,
    solid = solid,
    walkable = walkable,
    tags = tags,
    metadata = {},
  }
end

function FullScene.buildWorld(size)
  size = integer(size or FullScene.DEFAULT_SIZE, 8, 128, "scene size")
  local cells = {}
  for z = 0, size - 1 do
    for x = 0, size - 1 do
      cells[#cells + 1] = cellRecord(x, z)
    end
  end

  local actors = {}
  for index = 1, math.min(64, size) do
    actors[index] = {
      id = "synthetic_actor_" .. index,
      kind = "npc",
      pose = {
        x = ((index * 13) % size) * 16 + 8,
        y = 0,
        z = ((index * 29) % size) * 16 + 8,
        facing = "down",
      },
      tags = {},
    }
  end

  local world, err = WorldSnapshot.capture({
    id = "SYNTHETIC_FULL_SCENE_" .. size,
    key = "synthetic:full-scene:" .. size .. ":1",
    revision = 1,
    game = "yellow",
    width = size,
    height = size,
    cellSize = 16,
    paletteRevision = "synthetic",
    tilesetRevision = "synthetic",
    atlasRevision = "synthetic",
    mode = "first_person",
    weather = "storm",
    tags = {
      outdoor = true,
      route = true,
      forest = true,
      mountain = true,
      night = true,
    },
    player = {
      x = size * 8,
      y = 0,
      z = size * 8,
      cellX = math.floor(size / 2),
      cellZ = math.floor(size / 2),
      facing = "down",
    },
    actors = actors,
    neighbors = {
      { id = "SYNTHETIC_NORTH", offsetX = 0, offsetZ = -size * 16,
        revision = 1, tilesetRevision = 1, tags = { route = true } },
      { id = "SYNTHETIC_SOUTH", offsetX = 0, offsetZ = size * 16,
        revision = 1, tilesetRevision = 1, tags = { route = true } },
    },
    cells = cells,
  })
  if not world then error("synthetic full scene is invalid: " .. tostring(err), 2) end
  return world
end

function FullScene.defaultConfig()
  local values = {}
  for _, row in ipairs(Config.optionSchema()) do values[row.key] = row.default end
  values.rain = "ALWAYS"
  values.bouldertrees = true
  local service = Config.new({
    read = function(key) return values[key], true end,
  })
  return service:snapshot()
end

function FullScene.featurePrototypeCount()
  return #FEATURE_MODULES
end

function FullScene.authoredCaseIds()
  local ids = {}
  for index, case in ipairs(AuthoredFixture.cases) do ids[index] = case.id end
  return ids
end

local function findAuthoredCase(id)
  for _, case in ipairs(AuthoredFixture.cases) do
    if case.id == id then return case end
  end
  error("unknown authored benchmark case: " .. tostring(id), 3)
end

local function newProfiler(cpuClock)
  local profiler = {
    clock = cpuClock,
    features = {},
    operations = {},
  }
  for _, operation in ipairs(PROFILE_OPERATIONS) do
    profiler.operations[operation.name] = { calls = 0, cpuMs = 0 }
  end
  return profiler
end

local function newProfiledFeature(source, profiler)
  local record = { id = source.id, checkpoints = 0, compiles = 0, cpuMs = 0 }
  profiler.features[#profiler.features + 1] = record
  return {
    id = source.id,
    order = source.order,
    critical = source.critical,
    compile = function(_, context, buffer)
      record.compiles = record.compiles + 1
      local profiledContext = {}
      for key, value in pairs(context) do profiledContext[key] = value end
      local segmentStarted = profiler.clock()
      profiledContext.checkpoint = function(cost)
        record.cpuMs = record.cpuMs + milliseconds(profiler.clock, segmentStarted)
        record.checkpoints = record.checkpoints + 1
        context.checkpoint(cost)
        segmentStarted = profiler.clock()
      end
      local result = source:compile(profiledContext, buffer)
      record.cpuMs = record.cpuMs + milliseconds(profiler.clock, segmentStarted)
      return result
    end,
  }
end

local function newFeatures(profiler)
  local features = {}
  for index, module in ipairs(FEATURE_MODULES) do
    local source = module.prototype.new({ util = Util })
    features[index] = profiler and newProfiledFeature(source, profiler) or source
  end
  return features
end

local function instrumentCompiler(compiler, profiler)
  for _, operation in ipairs(PROFILE_OPERATIONS) do
    local original = compiler[operation.method]
    local record = profiler.operations[operation.name]
    compiler[operation.method] = function(self, ...)
      local started = profiler.clock()
      record.calls = record.calls + 1
      local results = { original(self, ...) }
      record.cpuMs = record.cpuMs + milliseconds(profiler.clock, started)
      return unpack(results)
    end
  end
end

local function newAssets()
  local handles = {}
  return {
    image = function(_, path)
      if type(path) ~= "string" or not path:match("^assets/legacy/") then
        error("benchmark requested an unexpected asset", 2)
      end
      handles[path] = handles[path] or { benchmarkTexture = path }
      return handles[path]
    end,
  }
end

local function packetSummary(packet)
  local commands, items = 0, 0
  local fingerprintCommands, excludedCommands = {}, 0
  for _, phase in ipairs(PHASES) do
    for _, command in ipairs(packet.phases[phase] or {}) do
      commands = commands + 1
      if type(command.items) == "table" then items = items + #command.items end
      if FINGERPRINT_EXCLUDED_KINDS[command.kind] then
        excludedCommands = excludedCommands + 1
      else
        local ok, err = API.validate_draw_command(command, command.kind)
        if not ok then
          error("full scene emitted a non-portable command: " .. tostring(err), 3)
        end
        local contentHash = type(command.cacheKey) == "string"
          and command.cacheKey:match(":([0-9a-f]+)$") or nil
        if type(contentHash) ~= "string" or #contentHash ~= 16 then
          error("full scene command has no sealed content hash", 3)
        end
        fingerprintCommands[#fingerprintCommands + 1] = {
          phase = phase,
          contentHash = contentHash,
        }
      end
    end
  end
  if commands ~= packet.commandCount or commands ~= packet.drawCalls then
    error("full scene packet command counts are inconsistent", 3)
  end
  if commands < 1 or items < 1 then
    error("full scene packet did not exercise batched production features", 3)
  end
  return {
    commands = commands,
    items = items,
    contentFingerprint = PacketHash.hash({
      schema = "kfp-benchmark-content-hashes-v1",
      commands = fingerprintCommands,
    }),
    fingerprintCommands = #fingerprintCommands,
    excludedFingerprintCommands = excludedCommands,
  }
end

local function profileSummary(profiler, compileCpuMs)
  if not profiler then return nil end
  local featureCpuMs, operationCpuMs = 0, 0
  for _, record in ipairs(profiler.features) do
    featureCpuMs = featureCpuMs + record.cpuMs
  end
  for _, record in pairs(profiler.operations) do
    operationCpuMs = operationCpuMs + record.cpuMs
  end
  return {
    features = profiler.features,
    operations = profiler.operations,
    featureCpuMs = featureCpuMs,
    operationCpuMs = operationCpuMs,
    coordinatorCpuMs = math.max(0, compileCpuMs - featureCpuMs - operationCpuMs),
  }
end

local function runCompiled(options)
  local wallClock = options.clock
  local cpuClock = options.cpuClock
  if type(wallClock) ~= "function" then error("full scene needs a clock", 3) end
  if type(cpuClock) ~= "function" then error("full scene needs a CPU clock", 3) end

  local quality = Quality.policy(options.tier or "HIGH", "AUTO", "windows")
  local profiler = options.profile and newProfiler(cpuClock) or nil
  local setupStarted = cpuClock()
  local bufferCount = 0
  local compiler = SceneCompiler.new({
    clock = wallClock,
    features = newFeatures(profiler),
    newBuffer = function()
      bufferCount = bufferCount + 1
      return CommandBuffer.new({
        maxCommands = 4096,
        maxBatchItems = 2048,
        hashCommand = PacketHash.hashCommand,
        newHashCommandJob = PacketHash.newCommandHashJob,
      })
    end,
  })
  if profiler then instrumentCompiler(compiler, profiler) end
  local setupCpuMs = milliseconds(cpuClock, setupStarted)

  local key = table.concat({
    options.world.key,
    "quality=" .. quality.resolved,
    "workload=" .. tostring(options.workloadId),
    "attempt=" .. tostring(options.run or 1),
  }, "|")
  local requestWallStarted = wallClock()
  local requestCpuStarted = cpuClock()
  compiler:request({
    key = key,
    world = options.world,
    config = options.config,
    quality = quality,
    services = {
      capabilities = options.capabilities or {},
      assets = newAssets(),
    },
  })
  local requestCpuMs = milliseconds(cpuClock, requestCpuStarted)
  local requestMs = milliseconds(wallClock, requestWallStarted)
  if bufferCount ~= 1 then error("full scene attempt did not create one buffer", 3) end

  local slices, cpuSlices, totalWallMs, compileCpuMs, updates = {}, {}, 0, 0, 0
  while not compiler:active() do
    local wallStarted = wallClock()
    local cpuStarted = cpuClock()
    compiler:step(quality.buildBudgetMs)
    local cpuElapsedMs = milliseconds(cpuClock, cpuStarted)
    local elapsedMs = milliseconds(wallClock, wallStarted)
    slices[#slices + 1] = elapsedMs
    cpuSlices[#cpuSlices + 1] = cpuElapsedMs
    totalWallMs = totalWallMs + elapsedMs
    compileCpuMs = compileCpuMs + cpuElapsedMs
    updates = updates + 1
    if updates > 10000 then error("full scene did not finish", 3) end
  end

  local inspectStarted = cpuClock()
  local packet = compiler:active()
  local summary = packetSummary(packet)
  compiler:dispose()
  local inspectCpuMs = milliseconds(cpuClock, inspectStarted)
  local readinessMs = updates * FullScene.FRAME_MS
    + requestMs + slices[#slices]
  return {
    key = key,
    quality = quality,
    updates = updates,
    slices = slices,
    cpuSlices = cpuSlices,
    requestMs = requestMs,
    totalWallMs = totalWallMs,
    readinessMs = readinessMs,
    setupCpuMs = setupCpuMs,
    requestCpuMs = requestCpuMs,
    compileCpuMs = compileCpuMs,
    inspectCpuMs = inspectCpuMs,
    totalCpuMs = setupCpuMs + requestCpuMs + compileCpuMs + inspectCpuMs,
    commands = summary.commands,
    items = summary.items,
    contentFingerprint = summary.contentFingerprint,
    fingerprintCommands = summary.fingerprintCommands,
    excludedFingerprintCommands = summary.excludedFingerprintCommands,
    profile = profileSummary(profiler, compileCpuMs),
  }
end

function FullScene.run(options)
  options = options or {}
  local world = options.world or FullScene.buildWorld(options.size)
  return runCompiled({
    clock = options.clock,
    cpuClock = options.cpuClock,
    profile = options.profile == true,
    tier = options.tier,
    run = options.run,
    workloadId = ("dense-outdoor-%dx%d"):format(world.width, world.height),
    world = world,
    config = options.config or FullScene.defaultConfig(),
    capabilities = { shadow_pass = 1 },
  })
end

function FullScene.runAuthoredCase(options)
  options = options or {}
  local case = findAuthoredCase(options.caseId)
  local world, err = WorldSnapshot.capture(case.world)
  if not world then
    error("authored benchmark case is invalid: " .. tostring(err), 2)
  end
  local result = runCompiled({
    clock = options.clock,
    cpuClock = options.cpuClock,
    profile = options.profile == true,
    tier = options.tier,
    run = options.run,
    workloadId = "authored-" .. case.id,
    world = world,
    config = case.config,
    capabilities = case.capabilities,
  })
  result.caseId = case.id
  return result
end

return FullScene
