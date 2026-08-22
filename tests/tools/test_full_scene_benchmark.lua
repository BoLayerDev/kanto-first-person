return function(T)
  local Clocks = assert(loadfile(T.root
    .. "/tools/benchmark_clocks.lua"))()
  local FullScene = assert(loadfile(T.root
    .. "/tools/full_scene_benchmark.lua"))()
  local ffi = assert(require("ffi"))
  local testCpuClock = Clocks.processCpuClock()

  local idleWait
  if ffi.os == "Windows" then
    ffi.cdef([[void Sleep(unsigned long milliseconds);]])
    idleWait = function(milliseconds) ffi.C.Sleep(milliseconds) end
  else
    ffi.cdef([[
      struct kfp_benchmark_test_timespec { long tv_sec; long tv_nsec; };
      int nanosleep(
        const struct kfp_benchmark_test_timespec *requested,
        struct kfp_benchmark_test_timespec *remaining
      );
    ]])
    idleWait = function(milliseconds)
      local requested = ffi.new("struct kfp_benchmark_test_timespec[1]")
      local remaining = ffi.new("struct kfp_benchmark_test_timespec[1]")
      requested[0].tv_sec = math.floor(milliseconds / 1000)
      requested[0].tv_nsec = (milliseconds % 1000) * 1000000
      for _ = 1, 4 do
        if ffi.C.nanosleep(requested, remaining) == 0 then return end
        requested[0].tv_sec = remaining[0].tv_sec
        requested[0].tv_nsec = remaining[0].tv_nsec
      end
      error("benchmark clock test idle wait was interrupted repeatedly")
    end
  end

  local authoredIds = {
    "indoor",
    "cave",
    "forest",
    "city_lavender",
    "route_neighbor_edge",
    "shore",
    "mountain",
    "day",
    "night",
    "rain",
    "storm",
    "battle_supported",
    "battle_unsupported",
  }

  local function featureProfile(result, id)
    for _, feature in ipairs(result.profile and result.profile.features or {}) do
      if feature.id == id then return feature end
    end
    error("missing full-scene feature profile: " .. tostring(id), 2)
  end

  T.test("platform process CPU clock excludes idle wall wait", function()
    local wallClock = Clocks.monotonicWallClock()
    local cpuClock, info = Clocks.processCpuClock()
    T.equal(info.scope, "process")
    T.equal(info.unit, "seconds")
    T.equal(info.idleWaitIncluded, false)
    if ffi.os == "Windows" then
      T.equal(info.source, "GetProcessTimes")
      T.equal(info.components, "kernel+user")
    else
      T.equal(info.source, "clock_gettime(CLOCK_PROCESS_CPUTIME_ID)")
      T.equal(info.components, "all-thread CPU")
    end

    local wallStarted = wallClock()
    local cpuStarted = cpuClock()
    idleWait(250)
    local cpuElapsed = cpuClock() - cpuStarted
    local wallElapsed = wallClock() - wallStarted
    T.truthy(cpuElapsed >= 0)
    T.truthy(wallElapsed > 0)
    T.truthy(wallElapsed > cpuElapsed * 3,
      ("idle wait wall/CPU %.6f/%.6f"):format(wallElapsed, cpuElapsed))
  end)

  T.test("full-scene workload is normalized, bounded, and portable", function()
    local world = FullScene.buildWorld(16)
    T.equal(world.width, 16)
    T.equal(world.height, 16)
    T.equal(#world.cells, 256)
    T.equal(world.game, "yellow")
    T.truthy(world.tags.forest)
    T.equal(FullScene.featurePrototypeCount(), 9)

    local result = FullScene.run({
      clock = os.clock,
      cpuClock = testCpuClock,
      tier = "LOW",
      world = world,
      run = "test",
    })
    T.truthy(result.updates > 0)
    T.truthy(#result.slices == result.updates)
    T.truthy(#result.cpuSlices == result.updates)
    T.truthy(result.commands > 0)
    T.truthy(result.items > 0)
    T.truthy(result.contentFingerprint:match("^[0-9a-f]+$"))
    T.equal(#result.contentFingerprint, 8)
    T.equal(result.quality.resolved, "LOW")
    T.truthy(result.key:find("attempt=test", 1, true))
  end)

  T.test("64x64 stress uses the exact snapshot index and fixed work fingerprints", function()
    local expected = {
      LOW = { commands = 26, items = 4367, content = "64f9db93" },
      BALANCED = { commands = 28, items = 7782, content = "252c129b" },
      HIGH = { commands = 28, items = 12270, content = "bb821318" },
    }
    for _, tier in ipairs({ "LOW", "BALANCED", "HIGH" }) do
      local result = FullScene.run({
        clock = os.clock,
        cpuClock = testCpuClock,
        profile = true,
        tier = tier,
        run = "fingerprint-" .. tier,
      })
      T.truthy(result.profile.worldIndexBindingObserved, tier)
      T.truthy(result.profile.worldIndexBindingExact, tier)
      T.equal(featureProfile(result, "world_geometry").checkpoints, 512, tier)
      T.equal(result.commands, expected[tier].commands, tier)
      T.equal(result.items, expected[tier].items, tier)
      T.equal(result.contentFingerprint, expected[tier].content, tier)
      T.equal(result.fingerprintCommands, result.commands, tier)
      T.equal(result.excludedFingerprintCommands, 0, tier)
    end
  end)

  T.test("profile attempt reports feature and compiler operation CPU", function()
    local result = FullScene.run({
      clock = os.clock,
      cpuClock = testCpuClock,
      profile = true,
      size = 16,
      tier = "HIGH",
      run = "profile-test",
    })
    T.truthy(result.profile)
    T.equal(#result.profile.features, 9)
    T.truthy(result.profile.featureCpuMs >= 0)
    T.truthy(result.profile.operationCpuMs >= 0)
    T.truthy(result.profile.coordinatorCpuMs >= 0)
    T.truthy(result.profile.worldIndexBindingObserved)
    T.truthy(result.profile.worldIndexBindingExact)
    T.equal(featureProfile(result, "world_geometry").checkpoints, 32)
    T.equal(result.profile.operations.begin_seal.calls, 1)
    T.truthy(result.profile.operations.seal.calls > 0)
    T.truthy(result.profile.operations.validate.calls > 0)
    T.truthy(result.profile.operations.cost.calls > 0)
    T.equal(result.profile.operations.commit.calls, 1)
    for _, feature in ipairs(result.profile.features) do
      T.equal(feature.compiles, 1, feature.id)
      T.truthy(feature.cpuMs >= 0, feature.id)
    end
  end)

  T.test("13 authored scenes form a separate deterministic structure corpus", function()
    T.equal(FullScene.AUTHORED_FIXTURE_KIND,
      "authored-rom-free-synthetic-v1")
    local actualIds = FullScene.authoredCaseIds()
    T.equal(#actualIds, #authoredIds)
    for index, expectedId in ipairs(authoredIds) do
      T.equal(actualIds[index], expectedId)
      local first = FullScene.runAuthoredCase({
        clock = os.clock,
        cpuClock = testCpuClock,
        tier = "HIGH",
        caseId = expectedId,
        run = "structure-a",
      })
      local second = FullScene.runAuthoredCase({
        clock = os.clock,
        cpuClock = testCpuClock,
        tier = "HIGH",
        caseId = expectedId,
        run = "structure-b",
      })
      T.equal(first.caseId, expectedId)
      T.notEqual(first.key, second.key)
      T.equal(first.commands, second.commands, expectedId)
      T.equal(first.items, second.items, expectedId)
      T.equal(first.contentFingerprint, second.contentFingerprint, expectedId)
      T.equal(first.fingerprintCommands + first.excludedFingerprintCommands,
        first.commands, expectedId)
      T.truthy(first.readinessMs > 0, expectedId)
    end
  end)

  T.test("full-scene workload rejects unsafe dimensions and unknown cases", function()
    for _, size in ipairs({ 0, 7, 129, 8.5 }) do
      T.raises(function() FullScene.buildWorld(size) end, "scene size")
    end
    T.raises(function()
      FullScene.runAuthoredCase({
        clock = os.clock,
        caseId = "not-a-case",
      })
    end, "unknown authored benchmark case")
    T.raises(function()
      FullScene.run({ clock = os.clock, size = 8 })
    end, "needs a CPU clock")
  end)
end
