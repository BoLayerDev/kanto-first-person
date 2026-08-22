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

local function legacyTreeLift(cell)
  local step = ((tonumber(cell.x) or 0) * 73856093
    + (tonumber(cell.z) or 0) * 19349663) % 3
  return 8 + step * 6
end

function WorldGeometry:compile(context, buffer)
  local U = self.util
  local world, config, quality = context.world, context.config, context.quality
  if U.hasTag(world, "interior") or U.hasTag(world, "cave") then return end
  local size = world.cellSize or 16
  local policy = U.placementPolicy(world, quality)
  local worldApron = U.option(config, "world_apron", true)
  local tallTrees = U.option(config, "tall_trees", true)
  local mountainPeaks = U.option(config, "mountain_peaks", true)
  local boulderTrees = U.option(config, "boulder_trees", false)
  local objectShadows = U.option(config, "object_shadows", true)
  local treeAnchors = {}
  if tallTrees or objectShadows then
    treeAnchors = U.clusterAnchors(world, policy.tree, "tree_support",
      function(cell) return U.isSemanticSupport(cell, "tree_support") end,
      nil, context)
  end
  local mountainAnchors = {}
  if mountainPeaks or objectShadows then
    local cellIndex = U.indexCells(world, context)
    mountainAnchors = U.clusterAnchors(world, policy.mountain, "mountain_peak",
      function(cell)
        return U.isMountainClusterMember(world, cellIndex, cell)
      end,
      function(cell) return U.hasTag(cell, "mountain_seed") and 1 or 0 end,
      context)
  end
  local boulderAnchors = {}
  if boulderTrees or objectShadows then
    boulderAnchors = U.clusterAnchors(world, policy.tree, "boulder_tree",
      function(cell) return U.isSemanticSupport(cell, "boulder_tree") end,
      nil, context)
  end
  local objectAnchors = {}
  if objectShadows then
    objectAnchors = U.clusterAnchors(world, policy.object, "object_shadow",
      function(cell)
        return U.isSemanticSupport(cell, "object")
          and not U.hasTag(cell, "tree_support")
          and not U.hasTag(cell, "mountain_support")
          and not U.hasTag(cell, "boulder_tree")
      end, nil, context)
  end

  if worldApron then
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
    local selectedTree = U.isAnchor(treeAnchors, cell)
    local selectedMountain = U.isAnchor(mountainAnchors, cell)
    local selectedBoulder = U.isAnchor(boulderAnchors, cell)
    local selectedObject = U.isAnchor(objectAnchors, cell)
    if tallTrees and selectedTree then
      local lift = legacyTreeLift(cell)
      local trunkHeight = lift + 3
      instance(buffer, "opaque_after_terrain",
        "tall_tree_trunks_" .. tostring(trunkHeight), self.id,
        U.material(cell, "world:tree"),
        { primitive = "box", role = "tree_trunk", width = size * 0.24,
          height = trunkHeight, depth = size * 0.24 },
        { x = x, y = y + trunkHeight * 0.5, z = z, seed = seed,
          lift = lift })
      instance(buffer, "opaque_after_terrain", "tall_tree_canopies", self.id,
        U.material(cell, "world:tree"),
        { primitive = "canopy", width = size, cutaway = true },
        { x = x, y = y + lift + size * 0.225, z = z, seed = seed,
          lift = lift,
          cellX = cell.x, cellZ = cell.z })
    end
    if mountainPeaks and selectedMountain then
      instance(buffer, "opaque_after_terrain", "mountains", self.id,
        U.material(cell, "world:stone"),
        { primitive = "mountain", role = "mountain", shadow = true },
        { x = x, y = y, z = z, seed = seed,
          summit = U.hasTag(cell, "mountain_seed") })
    end
    if boulderTrees and selectedBoulder then
      instance(buffer, "opaque_after_terrain", "boulder_tree_hoods", self.id,
        U.material(cell, "world:boulder_tree"),
        { primitive = "hood", role = "boulder_tree", shadow = true },
        { x = x, y = y, z = z, seed = seed })
    end
    local selectedShadow = selectedTree or selectedMountain or selectedBoulder
      or selectedObject
    if objectShadows and selectedShadow then
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
