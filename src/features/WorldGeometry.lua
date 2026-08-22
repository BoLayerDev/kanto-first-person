local WorldGeometry = {}
WorldGeometry.__index = WorldGeometry

function WorldGeometry.new(deps)
  deps = deps or {}
  if not deps.util then error("WorldGeometry needs util", 2) end
  return setmetatable({ id = "world_geometry", order = 120, critical = true, util = deps.util }, WorldGeometry)
end

local function instance(buffer, phase, key, owner, material, prototype, item)
  buffer:addBatchItem(phase, "instances", key, {
    owner = owner,
    material = material,
    prototype = prototype,
    sortKey = owner .. ":" .. key,
  }, item)
end

function WorldGeometry:compile(context, buffer)
  local U = self.util
  local world, config = context.world, context.config
  if U.hasTag(world, "interior") or U.hasTag(world, "cave") then return end
  local size = world.cellSize or 16

  if U.option(config, "world_apron", true) then
    buffer:add("opaque_after_terrain", {
      kind = "mesh",
      owner = self.id,
      material = "world:apron",
      sortKey = "world:apron",
      geometry = {
        primitive = "world_apron",
        width = world.width * size,
        depth = world.height * size,
        skirtDepth = size * 8,
      },
    })
  end

  for index, cell in ipairs(world.cells or {}) do
    local x, y, z = U.cellPosition(world, cell)
    local seed = U.hash(world.id, cell.x, cell.z, "world")
    if U.option(config, "tall_trees", true) and U.hasTag(cell, "tree") then
      instance(buffer, "opaque_after_terrain", "tall_tree_trunks", self.id,
        U.material(cell, "world:tree"),
        { primitive = "box", role = "tree_trunk", width = size * 0.24,
          height = size * 1.5, depth = size * 0.24 },
        { x = x, y = y + size * 0.75, z = z, seed = seed })
      instance(buffer, "opaque_after_terrain", "tall_tree_canopies", self.id,
        U.material(cell, "world:tree"),
        { primitive = "canopy", width = size * 1.25, cutaway = true },
        { x = x, y = y + size * 1.5, z = z, seed = seed,
          cellX = cell.x, cellZ = cell.z })
    end
    if U.option(config, "mountain_peaks", true)
        and (U.hasTag(cell, "mountain") or U.hasTag(cell, "summit")) then
      instance(buffer, "opaque_after_terrain", "mountains", self.id,
        U.material(cell, "world:stone"),
        { primitive = "mountain", role = "mountain", shadow = true },
        { x = x, y = y, z = z, seed = seed,
          summit = U.hasTag(cell, "summit") })
    end
    if U.option(config, "boulder_trees", false) and U.hasTag(cell, "boulder_tree") then
      instance(buffer, "opaque_after_terrain", "boulder_tree_hoods", self.id,
        U.material(cell, "world:boulder_tree"),
        { primitive = "hood", role = "boulder_tree", shadow = true },
        { x = x, y = y, z = z, seed = seed })
    end
    if U.option(config, "object_shadows", true)
        and (U.hasTag(cell, "tree") or U.hasTag(cell, "mountain")
          or U.hasTag(cell, "object")) then
      instance(buffer, "opaque_after_terrain", "object_shadows", self.id,
        "shadow:object",
        { primitive = "plane", role = "object_shadow", alphaCutoff = 0.1 },
        { x = x, y = y + 0.03, z = z, seed = seed })
      if U.capability(context, "shadow_pass") then
        instance(buffer, "shadow_casters", "world_shadow_casters", self.id,
          U.material(cell, "world:object"),
          { primitive = "box", role = "shadow_caster", width = size * 0.8,
            height = size * 1.5, depth = size * 0.8 },
          { x = x, y = y + size * 0.75, z = z, seed = seed })
      end
    end
    U.checkpoint(context, index, 32)
  end
end

return WorldGeometry
