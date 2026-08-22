local Atmosphere = {}
Atmosphere.__index = Atmosphere

local HORIZONS = {
  KANTO = {
    HIGH = { path = "assets/legacy/horizons/backdrop.png", width = 4096 },
    BALANCED = { path = "assets/legacy/horizons/backdrop-2048.png", width = 2048 },
    LOW = { path = "assets/legacy/horizons/backdrop-1024.png", width = 1024 },
  },
  FUJI = {
    HIGH = { path = "assets/legacy/horizons/backdrop2.png", width = 4096 },
    BALANCED = { path = "assets/legacy/horizons/backdrop2-2048.png", width = 2048 },
    LOW = { path = "assets/legacy/horizons/backdrop2-1024.png", width = 1024 },
  },
  VALLEY = {
    HIGH = { path = "assets/legacy/horizons/backdrop3.png", width = 4096 },
    BALANCED = { path = "assets/legacy/horizons/backdrop3-2048.png", width = 2048 },
    LOW = { path = "assets/legacy/horizons/backdrop3-1024.png", width = 1024 },
  },
  CITY = {
    HIGH = { path = "assets/legacy/horizons/backdrop4.png", width = 4096 },
    BALANCED = { path = "assets/legacy/horizons/backdrop4-2048.png", width = 2048 },
    LOW = { path = "assets/legacy/horizons/backdrop4-1024.png", width = 1024 },
  },
}

local CLOUD_TEXTURES = {
  "assets/legacy/sky/clouds-1.png",
  "assets/legacy/sky/clouds-2.png",
  "assets/legacy/sky/clouds-3.png",
}

local function packagedImage(context, path)
  local services = type(context) == "table" and context.services or nil
  local assets = type(services) == "table" and services.assets or nil
  if type(assets) ~= "table" or type(assets.image) ~= "function" then return nil end
  local ok, image = pcall(assets.image, assets, path)
  if not ok or not image then return nil end
  return image
end

function Atmosphere.new(deps)
  deps = deps or {}
  if not deps.util then error("Atmosphere needs util", 2) end
  return setmetatable({ id = "atmosphere", order = 200, critical = false, util = deps.util }, Atmosphere)
end

function Atmosphere:compile(context, buffer)
  local U = self.util
  local world, config, quality = context.world, context.config, context.quality
  if U.hasTag(world, "interior") or U.hasTag(world, "cave") then return end

  if U.option(config, "horizon", true) then
    local choice = tostring(U.option(config, "horizon_art", "VALLEY")):upper()
    if not HORIZONS[choice] then choice = "VALLEY" end
    local qualityName = tostring(quality.resolved or "HIGH"):upper()
    local variant = HORIZONS[choice][qualityName] or HORIZONS[choice].HIGH
    local texture = packagedImage(context, variant.path)
    if texture then
      buffer:add("background", {
        kind = "mesh",
        owner = self.id,
        material = "horizon:" .. choice:lower(),
        sortKey = "00:horizon",
        texture = texture,
        geometry = {
          primitive = "panorama",
          sourceWidth = variant.width,
          targetWidth = variant.width,
          deepSkirt = true,
          distanceHaze = true,
        },
      })
    end
  end

  if U.option(config, "clouds", true) then
    for layer = 1, 3 do
      local texture = packagedImage(context, CLOUD_TEXTURES[layer])
      if texture then
        buffer:add("background", {
          kind = "mesh",
          owner = self.id,
          material = "sky:clouds:" .. layer,
          sortKey = "10:clouds:" .. layer,
          texture = texture,
          geometry = {
            primitive = "cloud_layer",
            layer = layer,
            parallax = 0.08 + layer * 0.06,
            density = quality.density,
            seed = U.hash(world.id, "clouds", layer),
          },
        })
      end
    end
  end

  if U.option(config, "night_sky", true) then
    buffer:add("background", {
      kind = "billboards",
      owner = self.id,
      material = "sky:stars",
      sortKey = "20:stars",
      procedural = {
        kind = "stars",
        count = math.max(24, math.floor(180 * quality.density)),
        seed = U.hash(world.id, "stars"),
        twinkle = true,
        nebula = true,
        shootingStars = true,
      },
    })
  end

  if U.capability(context, "draw_postprocess")
      and U.option(config, "lavender_fog", true) and U.hasTag(world, "lavender") then
    buffer:add("translucent_after_actors", {
      kind = "postprocess",
      owner = self.id,
      material = "fog:lavender",
      sortKey = "90:lavender_veil",
      effect = { kind = "lavender_veil", passes = quality.resolved == "LOW" and 1 or 2 },
    })
  end
end

return Atmosphere
