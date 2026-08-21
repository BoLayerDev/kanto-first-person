local Quality = {}

local MIB = 1024 * 1024

local POLICIES = {
  HIGH = {
    name = "HIGH",
    buildBudgetMs = 2.0,
    cacheBytes = 128 * MIB,
    density = 1.0,
    drawCallTarget = 48,
    panoramaWidth = 4096,
  },
  BALANCED = {
    name = "BALANCED",
    buildBudgetMs = 1.0,
    cacheBytes = 64 * MIB,
    density = 0.6,
    drawCallTarget = 32,
    panoramaWidth = 2048,
  },
  LOW = {
    name = "LOW",
    buildBudgetMs = 0.5,
    cacheBytes = 32 * MIB,
    density = 0.3,
    drawCallTarget = 20,
    panoramaWidth = 1024,
  },
}

local PLATFORM_DEFAULT = {
  android = "BALANCED",
  ios = "BALANCED",
  switch = "BALANCED",
  xbox = "BALANCED",
  portmaster = "LOW",
  anbernic = "LOW",
  linux_arm64 = "BALANCED",
}

local function copyPolicy(policy)
  local out = {}
  for key, value in pairs(policy) do out[key] = value end
  return out
end

function Quality.normalize(value)
  if type(value) ~= "string" then return "AUTO" end
  value = value:upper()
  if value == "MEDIUM" then value = "BALANCED" end
  if value == "AUTO" or POLICIES[value] then return value end
  return "AUTO"
end

function Quality.resolve(requested, hostTier, platform)
  requested = Quality.normalize(requested)
  if requested ~= "AUTO" then return requested end

  hostTier = Quality.normalize(hostTier)
  if hostTier ~= "AUTO" then return hostTier end

  platform = type(platform) == "string" and platform:lower() or ""
  return PLATFORM_DEFAULT[platform] or "HIGH"
end

function Quality.policy(requested, hostTier, platform)
  local resolved = Quality.resolve(requested, hostTier, platform)
  local out = copyPolicy(POLICIES[resolved])
  out.requested = Quality.normalize(requested)
  out.resolved = resolved
  return out
end

function Quality.all()
  return {
    HIGH = copyPolicy(POLICIES.HIGH),
    BALANCED = copyPolicy(POLICIES.BALANCED),
    LOW = copyPolicy(POLICIES.LOW),
  }
end

return Quality
