local Battle = {}
Battle.__index = Battle

function Battle.new(deps)
  deps = deps or {}
  if not deps.util then error("Battle needs util", 2) end
  return setmetatable({ id = "battle", order = 130, critical = false, util = deps.util }, Battle)
end

function Battle:compile(context, buffer)
  local U = self.util
  if not U.capability(context, "battle_pass") then return end
  local world, config = context.world, context.config
  if world.mode ~= "battle" and not U.worldHas(world, "battle") then return end
  for index, cell in ipairs(world.cells or {}) do
    if U.hasTag(cell, "tree") or U.hasTag(cell, "boulder_tree")
        or U.hasTag(cell, "battle_prop") then
      local x, y, z = U.cellPosition(world, cell)
      local primitive = U.hasTag(cell, "boulder_tree") and "hood"
        or (U.hasTag(cell, "tree") and "canopy" or "box")
      local prototype
      if primitive == "hood" then
        prototype = { primitive = "hood", role = "boulder_tree",
          shadow = U.option(config, "object_shadows", true) }
      elseif primitive == "canopy" then
        prototype = { primitive = "canopy", width = world.cellSize, cutaway = false }
      else
        prototype = { primitive = "box", role = "battle_prop",
          width = world.cellSize * 0.8, height = world.cellSize,
          depth = world.cellSize * 0.8 }
      end
      buffer:addBatchItem("battle_opaque", "instances", "battle_props:" .. primitive, {
        owner = self.id,
        material = U.material(cell, "battle:prop"),
        prototype = prototype,
        sortKey = "battle:props",
      }, { x = x, y = y, z = z, kind = cell.kind,
        seed = U.hash(world.id, cell.x, cell.z, "battle") })
    end
    U.checkpoint(context, index, 48)
  end
end

return Battle
