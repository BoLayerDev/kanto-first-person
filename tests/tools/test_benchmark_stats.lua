return function(T)
  local Stats = assert(loadfile(T.root .. "/tools/benchmark_stats.lua"))()

  T.test("slice gate rejects one over-budget outlier", function()
    local samples = {}
    for index = 1, 99 do samples[index] = 0.5 end
    samples[100] = 0.751
    T.raises(function()
      Stats.assertSliceBudget(samples, 0.5, 0.25, "low")
    end, "exceeds")
  end)

  T.test("slice gate reports percentiles and observed maximum", function()
    local stats = Stats.assertSliceBudget({ 0.25, 0.5, 0.75 }, 0.5, 0.25, "low")
    T.equal(stats.p50, 0.5)
    T.equal(stats.p95, 0.75)
    T.equal(stats.p99, 0.75)
    T.equal(stats.maximum, 0.75)
  end)

  T.test("dense workload follows the production quality density", function()
    T.equal(Stats.scaledItemCount(4096, 1.0), 4096)
    T.equal(Stats.scaledItemCount(4096, 0.6), 2457)
    T.equal(Stats.scaledItemCount(4096, 0.3), 1228)
    T.equal(Stats.scaledItemCount(1, 0.3), 1)
  end)

  T.test("dense workload rejects invalid counts and densities", function()
    for _, values in ipairs({
      { 0, 1 }, { 1.5, 1 }, { 4096, 0 }, { 4096, 1.01 },
      { 4096, 0 / 0 },
    }) do
      T.raises(function()
        Stats.scaledItemCount(values[1], values[2])
      end, "inputs are invalid")
    end
  end)

  T.test("benchmark timing mode defaults strict and CI is explicit", function()
    T.equal(Stats.timingMode({}, nil), "strict")
    T.equal(Stats.timingMode({}, "strict"), "strict")
    T.equal(Stats.timingMode({}, "shared-ci"), "shared-ci")
    T.raises(function()
      Stats.timingMode({ "--relax-timing" }, "strict")
    end, "unknown benchmark option")
    T.raises(function()
      Stats.timingMode({}, "relaxed")
    end, "invalid KFP_BENCHMARK_MODE")
  end)

  T.test("shared CI reports timing while strict mode enforces it", function()
    local slices = { 0.5, 4.0 }
    local readiness = { 100, 400 }
    local sliceStats, readinessStats = Stats.evaluatePacketSeal(
      slices, readiness, 0.5, "low packet seal", "shared-ci")
    T.equal(sliceStats.maximum, 4.0)
    T.equal(readinessStats.p95, 400)
    T.raises(function()
      Stats.evaluatePacketSeal(
        slices, readiness, 0.5, "low packet seal", "strict")
    end, "exceeds")
    T.raises(function()
      Stats.evaluatePacketSeal(
        slices, readiness, 0.5, "low packet seal", "relaxed")
    end, "mode is invalid")
  end)

  T.test("desktop readiness includes the final compiler slice", function()
    local frameMs = 1000 / 60
    local readiness = Stats.frameReadiness(14, frameMs, 0.1, 0.4)
    local expected = 14 * frameMs + 0.1 + 0.4
    T.truthy(math.abs(readiness - expected) < 0.000001)
    T.truthy(readiness > 14 * frameMs + 0.1)
  end)

  T.test("desktop readiness limit is 250 ms for every tier", function()
    T.equal(Stats.DESKTOP_READINESS_LIMIT_MS, 250)
    for _, tier in ipairs({ "low", "balanced", "high" }) do
      local readiness = Stats.frameReadiness(15, 1000 / 60, 0, 0.01)
      T.raises(function()
        Stats.assertDesktopReadiness({ readiness }, tier)
      end, "250%.000 ms limit")
    end
  end)
end
