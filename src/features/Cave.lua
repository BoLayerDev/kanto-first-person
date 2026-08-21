local Cave = {}
Cave.__index = Cave

function Cave.new(deps)
  deps = deps or {}
  if not deps.util then error("Cave needs util", 2) end
  return setmetatable({ id = "cave", order = 110, critical = false, util = deps.util }, Cave)
end

local function add(buffer, key, material, prototype, item)
  buffer:addBatchItem("opaque_after_terrain", "instances", key, {
    owner = "cave",
    material = material,
    prototype = prototype,
    sortKey = "cave:" .. key,
  }, item)
end

function Cave:compile(context, buffer)
  local U = self.util
  local world, config = context.world, context.config
  if not U.worldHas(world, "cave") then return end
  local roof = tonumber(config.headroom_pixels)
    or U.headroom(U.option(config, "headroom", "AIRY"))

  for index, cell in ipairs(world.cells or {}) do
    if U.hasTag(cell, "cave") or U.hasTag(world, "cave") then
      local x, y, z, size = U.cellPosition(world, cell)
      local seed = U.hash(world.id, cell.x, cell.z, "cave")
      if U.option(config, "cave_rock", true) then
        add(buffer, "roof", U.material(cell, "cave:rock"),
          { primitive = "cave_roof", width = size, depth = size, role = "cave_roof" },
          { x = x, y = y + roof + U.unit(seed, "roof") * 4, z = z, seed = seed })
      end
      if U.option(config, "cave_pools", true) and U.hasTag(cell, "pool") then
        add(buffer, "pools", "cave:water",
          { primitive = "plane", width = size * 0.9, depth = size * 0.9, role = "pool" },
          { x = x, y = y + 0.05, z = z, seed = seed })
      end
      if U.option(config, "cave_torches", true) and U.hasTag(cell, "sconce") then
        add(buffer, "sconces", "cave:sconce",
          { primitive = "sconce", role = "sconce" }, { x = x, y = y + roof * 0.55, z = z })
      end
      if U.option(config, "bats", true) and U.keep(context.quality.density, seed, "bat") then
        buffer:addBatchItem("translucent_after_actors", "billboards", "cave_bats", {
          owner = self.id,
          material = "cave:bat",
          sortKey = "cave:bats",
          animated = true,
        }, { x = x, y = y + roof * 0.75, z = z, seed = seed })
      end
    end
    U.checkpoint(context, index, 32)
  end
end

return Cave
