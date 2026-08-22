local BenchmarkStats = {}
BenchmarkStats.DESKTOP_READINESS_LIMIT_MS = 250

local function finite(value)
  return type(value) == "number" and value == value
    and value ~= math.huge and value ~= -math.huge
end

local function percentile(sorted, fraction)
  return sorted[math.max(1, math.ceil(#sorted * fraction))]
end

function BenchmarkStats.statistics(values)
  if type(values) ~= "table" or #values < 1 then
    error("benchmark statistics need samples", 2)
  end
  local sorted = {}
  for index, value in ipairs(values) do
    if not finite(value) then error("benchmark samples must be finite", 2) end
    sorted[index] = value
  end
  table.sort(sorted)
  return {
    p50 = percentile(sorted, 0.50),
    p95 = percentile(sorted, 0.95),
    p99 = percentile(sorted, 0.99),
    maximum = sorted[#sorted],
  }
end

function BenchmarkStats.assertSliceBudget(values, budgetMs, toleranceMs, label)
  budgetMs = tonumber(budgetMs)
  toleranceMs = tonumber(toleranceMs)
  if not finite(budgetMs) or budgetMs <= 0
      or not finite(toleranceMs) or toleranceMs < 0 then
    error("slice budget and tolerance must be finite", 2)
  end
  local stats = BenchmarkStats.statistics(values)
  local limit = budgetMs + toleranceMs
  if stats.maximum > limit + 0.000001 then
    error(("%s seal slice %.3f ms exceeds %.3f ms limit"):format(
      tostring(label or "scene"), stats.maximum, limit), 2)
  end
  return stats
end

function BenchmarkStats.frameReadiness(
    updateCount, frameMs, requestMs, finalSliceMs)
  if not finite(updateCount) or updateCount ~= math.floor(updateCount)
      or updateCount < 1 or not finite(frameMs) or frameMs <= 0
      or not finite(requestMs) or requestMs < 0
      or not finite(finalSliceMs) or finalSliceMs < 0 then
    error("frame readiness inputs are invalid", 2)
  end
  return updateCount * frameMs + requestMs + finalSliceMs
end

function BenchmarkStats.assertDesktopReadiness(values, label)
  local stats = BenchmarkStats.statistics(values)
  local limit = BenchmarkStats.DESKTOP_READINESS_LIMIT_MS
  if stats.p95 > limit + 0.000001 then
    error(("%s dense scene readiness %.3f ms exceeds %.3f ms limit"):format(
      tostring(label or "scene"), stats.p95, limit), 2)
  end
  return stats
end

return BenchmarkStats
