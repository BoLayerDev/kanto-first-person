local Flora = {}
Flora.__index = Flora

function Flora.new(deps)
  deps = deps or {}
  if not deps.util then error("Flora needs util", 2) end
  return setmetatable({ id = "flora", order = 210, critical = false, util = deps.util }, Flora)
end

local function instance(buffer, key, material, prototype, item)
  buffer:addBatchItem("opaque_after_terrain", "instances", key, {
    owner = "flora",
    material = material,
    prototype = prototype,
    sortKey = "flora:" .. key,
  }, item)
end

local function billboard(buffer, key, material, item)
  buffer:addBatchItem("translucent_after_actors", "billboards", key, {
    owner = "flora",
    material = material,
    sortKey = "flora:" .. key,
    animated = true,
  }, item)
end

function Flora:compile(context, buffer)
  local U = self.util
  local world, config, quality = context.world, context.config, context.quality
  if U.hasTag(world, "interior") then return end
  local canopyDensity = math.min(1,
    math.max(0, (tonumber(quality.density) or 1) * (8 / 9)))

  for index, cell in ipairs(world.cells or {}) do
    local x, y, z, size = U.cellPosition(world, cell)
    local seed = U.hash(world.id, cell.x, cell.z, "flora")

    if U.option(config, "grass_height", "SUBTLE") ~= "OFF"
        and U.hasTag(cell, "grass") and U.keep(quality.density, seed, "grass") then
      instance(buffer, "grass", "flora:grass",
        -- KFP 1.60 used 7-unit crossed blades inside a 16-unit cell. A
        -- cell-wide card becomes a foreground wall in both current hosts.
        { primitive = "grass_clump", width = size * (7 / 16),
          wind = U.option(config, "wind", "BREEZE") },
        { x = x, y = y, z = z, seed = seed })
    end
    if U.option(config, "forest_canopy", true)
        and U.hasTag(world, "forest") and U.hasTag(cell, "forest")
        and U.keep(canopyDensity, seed, "canopy") then
      -- The preserved canopy varied from 40 through 62 units above a
      -- 16-unit cell. Keep that overhead range instead of the old v2
      -- 24-unit foreground slab.
      local canopyY = y + size * (2.5 + U.unit(seed, "canopy_height") * 1.375)
      instance(buffer, "canopy", U.material(cell, "flora:canopy"),
        { primitive = "canopy", width = size, cutaway = true },
        { x = x, y = canopyY, z = z, seed = seed,
          cellX = cell.x, cellZ = cell.z })
    end
    if U.option(config, "hanging_vines", true) and U.hasTag(cell, "vine")
        and U.keep(quality.density, seed, "vine") then
      instance(buffer, "vines", "flora:vine",
        { primitive = "vine", animated = true },
        { x = x, y = y + size, z = z, seed = seed })
    end
    if U.option(config, "particles", true) then
      if U.hasTag(cell, "forest") and U.keep(quality.density * 0.35, seed, "leaf") then
        billboard(buffer, "leaves", "flora:leaf", { x = x, y = y + size, z = z, seed = seed })
      end
      if U.hasTag(cell, "shore") and U.keep(quality.density * 0.4, seed, "foam") then
        billboard(buffer, "foam", "water:foam", { x = x, y = y + 0.1, z = z, seed = seed })
      end
      if U.hasTag(cell, "chimney") then
        billboard(buffer, "smoke", "flora:smoke", { x = x, y = y + size * 2, z = z, seed = seed })
      end
      if U.hasTag(world, "night") and U.keep(quality.density * 0.2, seed, "firefly") then
        billboard(buffer, "fireflies", "flora:firefly", { x = x, y = y + size * 0.5, z = z, seed = seed })
      end
    end
    if U.option(config, "sun_shafts", true) and U.hasTag(cell, "sun_shaft") then
      billboard(buffer, "sun_shafts", "light:sun_shaft",
        { x = x, y = y + size, z = z, seed = seed, height = size * 4 })
    end
    U.checkpoint(context, index, 32)
  end
end

return Flora
