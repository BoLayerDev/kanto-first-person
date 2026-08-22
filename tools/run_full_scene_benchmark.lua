-- Controlled-reference, ROM-free scene compiler benchmark.

local Bootstrap = assert(loadfile("tools/test_bootstrap.lua"))()
local Clocks = assert(loadfile(Bootstrap.path("tools/benchmark_clocks.lua")))()
local FullScene = assert(loadfile(Bootstrap.path(
  "tools/full_scene_benchmark.lua")))()
local Stats = assert(loadfile(Bootstrap.path("tools/benchmark_stats.lua")))()

local ATTEMPTS = 5

local function exactValue(values, label)
  local expected = values[1]
  for index = 2, #values do
    if values[index] ~= expected then
      error(label .. " changed between uncached attempts", 2)
    end
  end
  return expected
end

local function collectResult(samples, result)
  for _, elapsedMs in ipairs(result.slices) do
    samples.slices[#samples.slices + 1] = elapsedMs
  end
  for _, name in ipairs({
    "readinessMs", "updates", "requestMs", "totalWallMs", "totalCpuMs",
    "compileCpuMs", "commands", "items", "contentFingerprint",
    "fingerprintCommands", "excludedFingerprintCommands", "key",
  }) do
    samples[name][#samples[name] + 1] = result[name]
  end
end

local function newSamples()
  return {
    slices = {},
    readinessMs = {},
    updates = {},
    requestMs = {},
    totalWallMs = {},
    totalCpuMs = {},
    compileCpuMs = {},
    commands = {},
    items = {},
    contentFingerprint = {},
    fingerprintCommands = {},
    excludedFingerprintCommands = {},
    key = {},
  }
end

local function assertUniqueKeys(keys, label)
  local seen = {}
  for _, key in ipairs(keys) do
    if seen[key] then error(label .. " reused a measured request key", 2) end
    seen[key] = true
  end
end

local function printAuthoredCase(caseId, samples)
  assertUniqueKeys(samples.key, caseId)
  local updates = Stats.statistics(samples.updates)
  local readiness = Stats.statistics(samples.readinessMs)
  local cpu = Stats.statistics(samples.totalCpuMs)
  local commands = exactValue(samples.commands, caseId .. " commands")
  local items = exactValue(samples.items, caseId .. " items")
  local fingerprint = exactValue(
    samples.contentFingerprint, caseId .. " content fingerprint")
  local included = exactValue(
    samples.fingerprintCommands, caseId .. " fingerprint command count")
  local excluded = exactValue(
    samples.excludedFingerprintCommands, caseId .. " excluded command count")
  io.write(("%-28s %d runs | updates p50/p95 %d/%d"
    .. " | ready ms %.3f/%.3f | process CPU ms p50 %.3f"
    .. " | commands/items %d/%d | content %s (%d included, %d excluded)\n"):format(
    "authored_" .. caseId,
    ATTEMPTS,
    updates.p50, updates.p95,
    readiness.p50, readiness.p95,
    cpu.p50,
    commands, items,
    fingerprint, included, excluded
  ))
end

local function printProfile(tier, result)
  local profile = assert(result.profile, "profile attempt did not report stages")
  local operation = profile.operations
  io.write(("%-28s process CPU ms setup/request/features/begin-seal/seal/validate/cost/commit/coordinator/inspect"
    .. " %.3f/%.3f/%.3f/%.3f/%.3f/%.3f/%.3f/%.3f/%.3f/%.3f"
    .. " | operation calls %d/%d/%d/%d/%d\n"):format(
    "full_scene_profile_" .. tier:lower(),
    result.setupCpuMs, result.requestCpuMs, profile.featureCpuMs,
    operation.begin_seal.cpuMs, operation.seal.cpuMs,
    operation.validate.cpuMs, operation.cost.cpuMs, operation.commit.cpuMs,
    profile.coordinatorCpuMs, result.inspectCpuMs,
    operation.begin_seal.calls, operation.seal.calls,
    operation.validate.calls, operation.cost.calls, operation.commit.calls
  ))
  local fields = {}
  for _, feature in ipairs(profile.features) do
    fields[#fields + 1] = ("%s=%.3f/%d"):format(
      feature.id, feature.cpuMs, feature.checkpoints)
  end
  io.write(("%-28s process CPU ms/checkpoints | %s\n"):format(
    "full_scene_features_" .. tier:lower(), table.concat(fields, " | ")))
end

local wallClock = Clocks.monotonicWallClock()
local cpuClock, cpuClockInfo = Clocks.processCpuClock()
local mode = Stats.timingMode(arg, os.getenv("KFP_BENCHMARK_MODE"))
local tiers = { "LOW", "BALANCED", "HIGH" }

io.write(("full_scene_cpu_clock      diagnostic only | scope %s"
  .. " | components %s | source %s | idle wait excluded\n"):format(
  cpuClockInfo.scope, cpuClockInfo.components, cpuClockInfo.source))

-- Warm LuaJIT traces. No warm compiler, buffer, packet, service, or key is used
-- by a measured attempt.
FullScene.run({
  clock = wallClock,
  cpuClock = cpuClock,
  tier = "HIGH",
  run = "warmup",
})

local authoredIds = FullScene.authoredCaseIds()
io.write(("authored_scene_corpus      mode %s | %d authored ROM-free scenes"
  .. " | structural/readiness report only | never visual/device acceptance\n"):format(
  mode, #authoredIds))
for _, caseId in ipairs(authoredIds) do
  local samples = newSamples()
  for attempt = 1, ATTEMPTS do
    collectResult(samples, FullScene.runAuthoredCase({
      clock = wallClock,
      cpuClock = cpuClock,
      tier = "HIGH",
      caseId = caseId,
      run = attempt,
    }))
  end
  printAuthoredCase(caseId, samples)
end

io.write(("full_scene_stress_timing  mode %s | advisory 64x64 composite limit"
  .. " | all modules plus dense outdoor branches | uncached"
  .. " | never representative visual/device acceptance\n"):format(mode))

local strictRecords = {}
for _, tier in ipairs(tiers) do
  local samples = newSamples()
  local budget
  for attempt = 1, ATTEMPTS do
    local result = FullScene.run({
      clock = wallClock,
      cpuClock = cpuClock,
      tier = tier,
      run = attempt,
    })
    budget = result.quality.buildBudgetMs
    collectResult(samples, result)
  end
  assertUniqueKeys(samples.key, tier .. " stress")

  local sliceStats = Stats.statistics(samples.slices)
  local readinessStats = Stats.statistics(samples.readinessMs)
  local updateStats = Stats.statistics(samples.updates)
  local requestStats = Stats.statistics(samples.requestMs)
  local wallStats = Stats.statistics(samples.totalWallMs)
  local cpuStats = Stats.statistics(samples.totalCpuMs)
  local compileCpuStats = Stats.statistics(samples.compileCpuMs)
  local commands = exactValue(samples.commands, tier .. " stress commands")
  local items = exactValue(samples.items, tier .. " stress items")
  local fingerprint = exactValue(
    samples.contentFingerprint, tier .. " stress content fingerprint")
  local included = exactValue(
    samples.fingerprintCommands, tier .. " stress fingerprint command count")
  local excluded = exactValue(
    samples.excludedFingerprintCommands, tier .. " stress excluded command count")

  io.write(("%-28s %d runs | updates p50/p95/p99 %d/%d/%d"
    .. " | ready ms %.3f/%.3f/%.3f | slice ms %.3f/%.3f/%.3f max %.3f"
    .. " | request/work wall %.3f/%.3f ms | process CPU total/compile %.3f/%.3f ms"
    .. " | commands/items %d/%d | content %s (%d included, %d excluded)\n"):format(
    "full_scene_stress_" .. tier:lower(),
    ATTEMPTS,
    updateStats.p50, updateStats.p95, updateStats.p99,
    readinessStats.p50, readinessStats.p95, readinessStats.p99,
    sliceStats.p50, sliceStats.p95, sliceStats.p99, sliceStats.maximum,
    requestStats.p50, wallStats.p50,
    cpuStats.p50, compileCpuStats.p50,
    commands, items,
    fingerprint, included, excluded
  ))

  local profile = FullScene.run({
    clock = wallClock,
    cpuClock = cpuClock,
    profile = true,
    tier = tier,
    run = "profile",
  })
  if profile.commands ~= commands or profile.items ~= items
      or profile.contentFingerprint ~= fingerprint then
    error(tier .. " profile attempt changed stress output", 2)
  end
  printProfile(tier, profile)

  strictRecords[#strictRecords + 1] = {
    tier = tier,
    slices = samples.slices,
    readiness = samples.readinessMs,
    budget = budget,
  }
end

if mode == "strict" then
  io.write("full_scene_strict_check   unchanged 250 ms desktop limit; failures remain failures\n")
  io.flush()
  for _, record in ipairs(strictRecords) do
    Stats.evaluatePacketSeal(
      record.slices,
      record.readiness,
      record.budget,
      record.tier:lower() .. " 64x64 advisory stress",
      mode
    )
  end
else
  io.write("full_scene_shared_ci      observations only; no performance approval\n")
end
