local Flora = {}
Flora.__index = Flora

function Flora.new(deps)
  deps = deps or {}
  if not deps.util then error("Flora needs util", 2) end
  return setmetatable({ id = "flora", order = 210, critical = false, util = deps.util }, Flora)
end

local function instance(buffer, key, template, item)
  buffer:addBatchItem("opaque_after_terrain", "instances", key, template, item)
end

local function billboard(buffer, key, template, item)
  buffer:addBatchItem("translucent_after_actors", "billboards", key, template, item)
end

local function instanceTemplate(key, material, prototype)
  return {
    owner = "flora",
    material = material,
    prototype = prototype,
    sortKey = "flora:" .. key,
  }
end

local function billboardTemplate(key, material)
  return {
    owner = "flora",
    material = material,
    sortKey = "flora:" .. key,
    animated = true,
  }
end

function Flora:compile(context, buffer)
  local U = self.util
  local world, config, quality = context.world, context.config, context.quality
  if U.hasTag(world, "interior") then return end
  local density = tonumber(quality.density) or 1
  local canopyDensity = math.min(1, math.max(0, density * (8 / 9)))
  local grassEnabled = U.option(config, "grass_height", "SUBTLE") ~= "OFF"
  local wind = grassEnabled and U.option(config, "wind", "BREEZE") or nil
  local canopyEnabled = U.option(config, "forest_canopy", true)
    and U.hasTag(world, "forest")
  local vinesEnabled = U.option(config, "hanging_vines", true)
  local particlesEnabled = U.option(config, "particles", true)
  local night = particlesEnabled and U.hasTag(world, "night")
  local sunShaftsEnabled = U.option(config, "sun_shafts", true)
  local vinesTemplate = instanceTemplate("vines", "flora:vine", {
    primitive = "vine",
    animated = true,
  })
  local billboardTemplates = {
    leaves = billboardTemplate("leaves", "flora:leaf"),
    foam = billboardTemplate("foam", "water:foam"),
    smoke = billboardTemplate("smoke", "flora:smoke"),
    fireflies = billboardTemplate("fireflies", "flora:firefly"),
    sun_shafts = billboardTemplate("sun_shafts", "light:sun_shaft"),
  }
  local grassTemplates, canopyTemplates = {}, {}

  for index, cell in ipairs(world.cells or {}) do
    local x, y, z, size = U.cellPosition(world, cell)
    local seed = U.hash(world.id, cell.x, cell.z, "flora")

    if grassEnabled and U.hasTag(cell, "grass")
        and U.keep(density, seed, "grass") then
      local template = grassTemplates[size]
      if not template then
        template = instanceTemplate("grass", "flora:grass", {
          -- KFP 1.60 used 7-unit crossed blades inside a 16-unit cell. A
          -- cell-wide card becomes a foreground wall in both current hosts.
          primitive = "grass_clump",
          width = size * (7 / 16),
          wind = wind,
        })
        grassTemplates[size] = template
      end
      instance(buffer, "grass", template,
        { x = x, y = y, z = z, seed = seed })
    end
    if canopyEnabled and U.hasTag(cell, "forest")
        and U.keep(canopyDensity, seed, "canopy") then
      -- The preserved canopy varied from 40 through 62 units above a
      -- 16-unit cell. Keep that overhead range instead of the old v2
      -- 24-unit foreground slab.
      local canopyY = y + size * (2.5 + U.unit(seed, "canopy_height") * 1.375)
      local material = U.material(cell, "flora:canopy")
      local materialTemplates = canopyTemplates[material]
      if not materialTemplates then
        materialTemplates = {}
        canopyTemplates[material] = materialTemplates
      end
      local template = materialTemplates[size]
      if not template then
        template = instanceTemplate("canopy", material,
          { primitive = "canopy", width = size, cutaway = true })
        materialTemplates[size] = template
      end
      instance(buffer, "canopy", template,
        { x = x, y = canopyY, z = z, seed = seed,
          cellX = cell.x, cellZ = cell.z })
    end
    if vinesEnabled and U.hasTag(cell, "vine")
        and U.keep(density, seed, "vine") then
      instance(buffer, "vines", vinesTemplate,
        { x = x, y = y + size, z = z, seed = seed })
    end
    if particlesEnabled then
      if U.hasTag(cell, "forest") and U.keep(density * 0.35, seed, "leaf") then
        billboard(buffer, "leaves", billboardTemplates.leaves,
          { x = x, y = y + size, z = z, seed = seed })
      end
      if U.hasTag(cell, "shore") and U.keep(density * 0.4, seed, "foam") then
        billboard(buffer, "foam", billboardTemplates.foam,
          { x = x, y = y + 0.1, z = z, seed = seed })
      end
      if U.hasTag(cell, "chimney") then
        billboard(buffer, "smoke", billboardTemplates.smoke,
          { x = x, y = y + size * 2, z = z, seed = seed })
      end
      if night and U.keep(density * 0.2, seed, "firefly") then
        billboard(buffer, "fireflies", billboardTemplates.fireflies,
          { x = x, y = y + size * 0.5, z = z, seed = seed })
      end
    end
    if sunShaftsEnabled and U.hasTag(cell, "sun_shaft") then
      billboard(buffer, "sun_shafts", billboardTemplates.sun_shafts,
        { x = x, y = y + size, z = z, seed = seed, height = size * 4 })
    end
    U.checkpoint(context, index, 32)
  end
end

return Flora
