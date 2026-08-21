local Wildlife = {}
Wildlife.__index = Wildlife

function Wildlife.new(deps)
  deps = deps or {}
  if not deps.util then error("Wildlife needs util", 2) end
  return setmetatable({ id = "wildlife", order = 230, critical = false, util = deps.util }, Wildlife)
end

local function addBillboards(buffer, key, material, count, world, util, height, extra)
  for index = 1, count do
    buffer:addBatchItem("translucent_after_actors", "billboards", key, {
      owner = "wildlife",
      material = material,
      sortKey = "wildlife:" .. key,
      animated = true,
    }, {
      x = util.unit(world.id, key, index, "x") * world.width * world.cellSize,
      y = height + util.unit(world.id, key, index, "y") * world.cellSize,
      z = util.unit(world.id, key, index, "z") * world.height * world.cellSize,
      seed = util.hash(world.id, key, index),
      extra = extra,
    })
  end
end

function Wildlife:compile(context, buffer)
  local U = self.util
  local world, config, quality = context.world, context.config, context.quality
  if U.hasTag(world, "interior") or U.hasTag(world, "cave") then return end
  local size = world.cellSize

  -- transform_birds.lua can create player-owned images during import, but the
  -- current public runtime services expose no resolver for those derived files.
  -- Birds and the ground flock must stay absent until a versioned resolver is
  -- injected. Host-specific material names and map keys are not asset handles.
  if U.option(config, "aircraft", true) then
    addBillboards(buffer, "aircraft", "wildlife:aircraft",
      math.max(1, math.floor(3 * quality.density)), world, U, size * 7,
      { contrails = true })
  end
  if U.option(config, "insects", true) then
    addBillboards(buffer, "insects", "wildlife:insect",
      math.max(4, math.floor(24 * quality.density)), world, U, size * 0.5)
  end
end

return Wildlife
