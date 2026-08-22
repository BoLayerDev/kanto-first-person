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
  local world, config, quality = context.world, context.config, context.quality
  if world.mode ~= "battle" and not U.worldHas(world, "battle") then return end
  local policy = U.placementPolicy(world, quality)
  local treeAnchors = U.clusterAnchors(world, policy.tree, "tree_support",
    function(cell) return U.isSemanticSupport(cell, "tree_support") end,
    nil, context)
  local mountainIndex = U.indexCells(world, context)
  local mountainAnchors = U.clusterAnchors(world, policy.mountain,
    "mountain_peak", function(cell)
      return U.isMountainClusterMember(world, mountainIndex, cell)
    end, function(cell)
      return U.hasTag(cell, "mountain_seed") and 1 or 0
    end, context)
  local boulderAnchors = U.clusterAnchors(world, policy.tree, "boulder_tree",
    function(cell) return U.isSemanticSupport(cell, "boulder_tree") end,
    nil, context)
  local propAnchors = U.clusterAnchors(world, policy.object, "battle_prop",
    function(cell) return U.hasTag(cell, "battle_prop") end, nil, context)
  local tallTrees = U.option(config, "tall_trees", true)
  local mountainPeaks = U.option(config, "mountain_peaks", true)
  local boulderTrees = U.option(config, "boulder_trees", false)
  local shadows = U.option(config, "object_shadows", true)
  for index, cell in ipairs(world.cells or {}) do
    local tree = tallTrees and U.isAnchor(treeAnchors, cell)
    local mountain = mountainPeaks and U.isAnchor(mountainAnchors, cell)
    local boulder = boulderTrees and U.isAnchor(boulderAnchors, cell)
    local prop = U.isAnchor(propAnchors, cell)
    if tree or mountain or boulder or prop then
      local x, y, z = U.cellPosition(world, cell)
      local primitive = boulder and "hood"
        or (tree and "canopy" or (mountain and "mountain" or "box"))
      local prototype
      if primitive == "hood" then
        prototype = { primitive = "hood", role = "boulder_tree",
          shadow = shadows }
      elseif primitive == "canopy" then
        prototype = { primitive = "canopy", width = world.cellSize, cutaway = false }
      elseif primitive == "mountain" then
        prototype = { primitive = "mountain", role = "mountain",
          shadow = shadows }
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
        summit = mountain and U.hasTag(cell, "mountain_seed") or nil,
        seed = U.hash(world.id, cell.x, cell.z, "battle") })
    end
    U.checkpoint(context, index, 48)
  end
end

return Battle
