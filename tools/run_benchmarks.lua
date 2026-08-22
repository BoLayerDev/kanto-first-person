-- ROM-free microbenchmarks. These detect large regressions but do not replace
-- the host, GPU, device, or 30-minute release performance gates.

local Bootstrap = assert(loadfile("tools/test_bootstrap.lua"))()

local function load(relative)
  return assert(loadfile(Bootstrap.path(relative)))()
end

local Config = load("src/config/Config.lua")
local BenchmarkStats = load("tools/benchmark_stats.lua")
local CommandBuffer = load("src/render/CommandBuffer.lua")
local API = load("companion/api_v1.lua")
local LRU = load("src/core/LRU.lua")
local LedgeLeapPolicy = load("src/gameplay/LedgeLeapPolicy.lua")
local PacketHash = load("src/render/PacketHash.lua")
local SceneCompiler = load("src/render/SceneCompiler.lua")

local function highResolutionClock()
  local ok, ffi = pcall(require, "ffi")
  if ok and ffi.os == "Windows" then
    ffi.cdef([[
      int QueryPerformanceCounter(int64_t *value);
      int QueryPerformanceFrequency(int64_t *value);
    ]])
    local value = ffi.new("int64_t[1]")
    local frequency = ffi.new("int64_t[1]")
    assert(ffi.C.QueryPerformanceFrequency(frequency) ~= 0,
      "QueryPerformanceFrequency failed")
    local unitsPerSecond = tonumber(frequency[0])
    return function()
      assert(ffi.C.QueryPerformanceCounter(value) ~= 0,
        "QueryPerformanceCounter failed")
      return tonumber(value[0]) / unitsPerSecond
    end
  end
  return os.clock
end

local benchmarkClock = highResolutionClock()

local optionValues = {}
for _, row in ipairs(Config.optionSchema()) do optionValues[row.key] = row.default end
local config = Config.new({ read = function(key) return optionValues[key] end })

local ledgeRequest = {
  enabled = true,
  mode = "free_roam",
  script_running = false,
  input_locked = false,
  direction = "down",
  player = {
    cell_x = 10, cell_y = 20, facing = "down", moving = false,
    surfing = false, hop_frames = 0, step_frames = 16,
  },
  map = { tileset = "OVERWORLD", standing_tile = 44 },
  front = { x = 10, y = 21, in_bounds = true, tile = 55, occupied = false },
  landing = { x = 10, y = 22, in_bounds = true, walkable = true, occupied = false },
  ledges = {
    { facing = "down", input = "down", standingTile = 44, ledgeTile = 55 },
  },
}

local cache = LRU.new({ maxCost = 1024, release = function() end })
for index = 1, 128 do cache:put("key:" .. index, { index = index }, 1) end

local cases = {
  {
    name = "config_snapshot_cached",
    iterations = 1000000,
    run = function() return config:snapshot() end,
  },
  {
    name = "lru_hot_get",
    iterations = 1000000,
    run = function(index) return cache:get("key:" .. ((index - 1) % 128 + 1)) end,
  },
  {
    name = "ledge_policy_valid",
    iterations = 250000,
    run = function() return LedgeLeapPolicy.decide(ledgeRequest) end,
  },
}

collectgarbage("collect")
local retained
for _, case in ipairs(cases) do
  local started = os.clock()
  for index = 1, case.iterations do retained = case.run(index) end
  local elapsed = os.clock() - started
  io.write(("%-24s %9d iterations %9.3f ms %9.1f ns/op\n"):format(
    case.name,
    case.iterations,
    elapsed * 1000,
    elapsed * 1000000000 / case.iterations
  ))
end

if retained == nil then error("benchmark result was unexpectedly nil") end

local function denseSceneBuffer()
  local buffer = CommandBuffer.new({
    maxCommands = 4096,
    maxBatchItems = 2048,
    hashCommand = PacketHash.hashCommand,
    newHashCommandJob = PacketHash.newCommandHashJob,
  })
  for z = 1, 64 do
    for x = 1, 64 do
      buffer:addBatchItem("opaque_after_terrain", "instances", "dense", {
        owner = "benchmark", material = "trees", sortKey = "trees",
        prototype = {
          primitive = "box",
          width = 1,
          height = 2,
          depth = 1,
          role = "terrain",
        },
      }, {
        x = x,
        y = (x + z) % 7,
        z = z,
      })
    end
  end
  return buffer
end

local function validateDensePacket(packet)
  assert(packet.commandCount == 2,
    "dense scene must use two protocol-valid batches")
  local commands = packet.phases.opaque_after_terrain
  assert(#commands == 2 and #commands[1].items == 2048
      and #commands[2].items == 2048,
    "dense scene batches must stay within the 2,048-item protocol limit")
  for _, phaseCommands in pairs(packet.phases) do
    for _, command in ipairs(phaseCommands) do
      local ok, err = API.validate_draw_command(command, command.kind)
      assert(ok, "dense scene command failed API v1 validation: " .. tostring(err))
    end
  end
end

local FRAME_MS = 1000 / 60

local function benchmarkDenseSeal(budgetMs, label)
  local buffer = denseSceneBuffer()
  collectgarbage("collect")
  local compiler = SceneCompiler.new({
    features = {},
    clock = benchmarkClock,
    newBuffer = function() return buffer end,
  })
  local requestStarted = benchmarkClock()
  compiler:request({
    key = "benchmark:64x64:" .. label,
    world = {}, config = {}, quality = {},
  })
  local requestCpuMs = (benchmarkClock() - requestStarted) * 1000

  local slices, totalCpuMs = {}, 0
  local updates = 0
  while not compiler:active() do
    local started = benchmarkClock()
    compiler:step(budgetMs)
    local elapsedMs = (benchmarkClock() - started) * 1000
    slices[#slices + 1] = elapsedMs
    totalCpuMs = totalCpuMs + elapsedMs
    updates = updates + 1
    if updates > 10000 then error("dense scene seal did not finish") end
  end

  local packet = compiler:active()
  validateDensePacket(packet)
  assert(updates > 1, "dense scene seal completed in one unbounded slice")
  return {
    updates = updates,
    slices = slices,
    requestCpuMs = requestCpuMs,
    totalCpuMs = totalCpuMs,
    -- The request is issued immediately after an update. Each compiler step
    -- then runs once on the next 60 Hz update. Readiness also includes the
    -- final compiler slice that produces the packet.
    readinessMs = BenchmarkStats.frameReadiness(
      updates,
      FRAME_MS,
      requestCpuMs,
      slices[#slices]
    ),
  }
end

-- Warm the LuaJIT traces before the five measured 60 Hz request cycles.
benchmarkDenseSeal(2.0, "warmup")
for _, tier in ipairs({
  { name = "low", budget = 0.5 },
  { name = "balanced", budget = 1.0 },
  { name = "high", budget = 2.0 },
}) do
  local sliceSamples, readinessSamples = {}, {}
  local updateSamples, cpuSamples, requestSamples = {}, {}, {}
  for attempt = 1, 5 do
    local result = benchmarkDenseSeal(tier.budget, tier.name .. ":" .. attempt)
    for _, elapsedMs in ipairs(result.slices) do
      sliceSamples[#sliceSamples + 1] = elapsedMs
    end
    readinessSamples[#readinessSamples + 1] = result.readinessMs
    updateSamples[#updateSamples + 1] = result.updates
    cpuSamples[#cpuSamples + 1] = result.totalCpuMs
    requestSamples[#requestSamples + 1] = result.requestCpuMs
  end

  local sliceStats = BenchmarkStats.assertSliceBudget(
    sliceSamples,
    tier.budget,
    0.25,
    tier.name
  )
  local readinessStats = BenchmarkStats.assertDesktopReadiness(
    readinessSamples,
    tier.name
  )
  local updateStats = BenchmarkStats.statistics(updateSamples)
  local cpuStats = BenchmarkStats.statistics(cpuSamples)
  local requestStats = BenchmarkStats.statistics(requestSamples)
  io.write(("%-24s 5 runs | updates p50/p95/p99 %d/%d/%d"
    .. " | ready ms %.3f/%.3f/%.3f | slice ms %.3f/%.3f/%.3f max %.3f"
    .. " | CPU ms %.3f | request ms %.3f\n"):format(
    "scene_seal_" .. tier.name,
    updateStats.p50, updateStats.p95, updateStats.p99,
    readinessStats.p50, readinessStats.p95, readinessStats.p99,
    sliceStats.p50, sliceStats.p95, sliceStats.p99, sliceStats.maximum,
    cpuStats.p50,
    requestStats.p50
  ))
end
