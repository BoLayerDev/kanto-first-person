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
local Quality = load("src/render/Quality.lua")
local SceneCompiler = load("src/render/SceneCompiler.lua")

local function monotonicWallClock()
  local ok, ffi = pcall(require, "ffi")
  if not ok then
    error("packet-seal timing requires LuaJIT FFI")
  end
  if ffi.os == "Windows" then
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
  ffi.cdef([[
    struct kfp_benchmark_timespec {
      long tv_sec;
      long tv_nsec;
    };
    int clock_gettime(int clock_id, struct kfp_benchmark_timespec *value);
  ]])
  local clockId = ffi.os == "OSX" and 6 or 1
  local value = ffi.new("struct kfp_benchmark_timespec[1]")
  return function()
    assert(ffi.C.clock_gettime(clockId, value) == 0,
      "clock_gettime failed")
    return tonumber(value[0].tv_sec) + tonumber(value[0].tv_nsec) / 1000000000
  end
end

local benchmarkClock = monotonicWallClock()
local timingMode = BenchmarkStats.timingMode(
  arg,
  os.getenv("KFP_BENCHMARK_MODE")
)

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

local FULL_DENSE_ITEMS = 64 * 64
local MAX_BATCH_ITEMS = 2048

local function denseSceneBuffer(itemCount)
  local buffer = CommandBuffer.new({
    maxCommands = 4096,
    maxBatchItems = MAX_BATCH_ITEMS,
    hashCommand = PacketHash.hashCommand,
    newHashCommandJob = PacketHash.newCommandHashJob,
  })
  for index = 1, itemCount do
    local x = (index - 1) % 64 + 1
    local z = math.floor((index - 1) / 64) + 1
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
  return buffer
end

local function validateDensePacket(packet, itemCount)
  local expectedCommands = math.ceil(itemCount / MAX_BATCH_ITEMS)
  assert(packet.commandCount == expectedCommands,
    "dense scene must use the expected protocol-valid batches")
  local commands = packet.phases.opaque_after_terrain
  assert(#commands == expectedCommands,
    "dense scene packet command count is inconsistent")
  local remaining = itemCount
  for _, command in ipairs(commands) do
    local expectedItems = math.min(remaining, MAX_BATCH_ITEMS)
    assert(#command.items == expectedItems,
      "dense scene batches must stay within the 2,048-item protocol limit")
    remaining = remaining - expectedItems
  end
  assert(remaining == 0, "dense scene packet lost benchmark items")
  for _, phaseCommands in pairs(packet.phases) do
    for _, command in ipairs(phaseCommands) do
      local ok, err = API.validate_draw_command(command, command.kind)
      assert(ok, "dense scene command failed API v1 validation: " .. tostring(err))
    end
  end
end

local FRAME_MS = 1000 / 60

local function benchmarkDenseSeal(budgetMs, itemCount, label)
  local buffer = denseSceneBuffer(itemCount)
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

  local slices, totalWallMs = {}, 0
  local updates = 0
  while not compiler:active() do
    local started = benchmarkClock()
    compiler:step(budgetMs)
    local elapsedMs = (benchmarkClock() - started) * 1000
    slices[#slices + 1] = elapsedMs
    totalWallMs = totalWallMs + elapsedMs
    updates = updates + 1
    if updates > 10000 then error("dense scene seal did not finish") end
  end

  local packet = compiler:active()
  validateDensePacket(packet, itemCount)
  return {
    updates = updates,
    slices = slices,
    requestCpuMs = requestCpuMs,
    totalWallMs = totalWallMs,
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

local qualityPolicies = Quality.all()
local tiers = {
  { name = "low", policy = qualityPolicies.LOW },
  { name = "balanced", policy = qualityPolicies.BALANCED },
  { name = "high", policy = qualityPolicies.HIGH },
}
for _, tier in ipairs(tiers) do
  tier.budget = tier.policy.buildBudgetMs
  tier.itemCount = BenchmarkStats.scaledItemCount(
    FULL_DENSE_ITEMS,
    tier.policy.density
  )
end

io.write(("packet_seal_timing      mode %s | monotonic wall observations"
  .. " | prebuilt buffer | not full-scene evidence\n"):format(timingMode))

-- Warm the LuaJIT traces with the complete High-tier corpus before the five
-- measured 60 Hz request cycles for each production density policy.
benchmarkDenseSeal(
  qualityPolicies.HIGH.buildBudgetMs,
  FULL_DENSE_ITEMS,
  "warmup"
)
for _, tier in ipairs(tiers) do
  local sliceSamples, readinessSamples = {}, {}
  local updateSamples, wallSamples, requestSamples = {}, {}, {}
  for attempt = 1, 5 do
    local result = benchmarkDenseSeal(
      tier.budget,
      tier.itemCount,
      tier.name .. ":" .. attempt
    )
    for _, elapsedMs in ipairs(result.slices) do
      sliceSamples[#sliceSamples + 1] = elapsedMs
    end
    readinessSamples[#readinessSamples + 1] = result.readinessMs
    updateSamples[#updateSamples + 1] = result.updates
    wallSamples[#wallSamples + 1] = result.totalWallMs
    requestSamples[#requestSamples + 1] = result.requestCpuMs
  end

  local sliceStats, readinessStats = BenchmarkStats.evaluatePacketSeal(
    sliceSamples,
    readinessSamples,
    tier.budget,
    tier.name .. " packet seal",
    timingMode
  )
  local updateStats = BenchmarkStats.statistics(updateSamples)
  local wallStats = BenchmarkStats.statistics(wallSamples)
  local requestStats = BenchmarkStats.statistics(requestSamples)
  io.write(("%-24s 5 runs | items %d | updates p50/p95/p99 %d/%d/%d"
    .. " | ready ms %.3f/%.3f/%.3f | slice ms %.3f/%.3f/%.3f max %.3f"
    .. " | wall ms %.3f | request wall ms %.3f\n"):format(
    "packet_seal_" .. tier.name,
    tier.itemCount,
    updateStats.p50, updateStats.p95, updateStats.p99,
    readinessStats.p50, readinessStats.p95, readinessStats.p99,
    sliceStats.p50, sliceStats.p95, sliceStats.p99, sliceStats.maximum,
    wallStats.p50,
    requestStats.p50
  ))
end
