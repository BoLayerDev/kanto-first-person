local WorldGeometry = {}
WorldGeometry.__index = WorldGeometry

local MAX_INDEX_ENTRIES = 65536

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

local function coordinateKey(cell)
  return tostring(cell and cell.x or 0) .. "|" .. tostring(cell and cell.z or 0)
end

local function selectBucket(U, buckets, world, spacing, salt, cell, rank)
  local bx = math.floor((tonumber(cell.x) or 0) / spacing)
  local bz = math.floor((tonumber(cell.z) or 0) / spacing)
  local bucketKey = bx .. "|" .. bz
  local score = U.hash(world and world.id or "world", cell.x, cell.z, salt)
  local chosen = buckets[bucketKey]
  rank = tonumber(rank) or 0
  if not chosen or rank > chosen.rank
      or (rank == chosen.rank and score < chosen.score)
      or (rank == chosen.rank and score == chosen.score
        and coordinateKey(cell) < coordinateKey(chosen.cell)) then
    buckets[bucketKey] = { cell = cell, rank = rank, score = score }
  end
end

local function anchorSet(buckets)
  local anchors = {}
  for _, chosen in pairs(buckets) do
    anchors[coordinateKey(chosen.cell)] = true
  end
  return anchors
end

local function validateIndex(U, world, binding, context)
  local services = type(context) == "table" and context.services or nil
  if binding == nil then
    binding = type(services) == "table" and services.worldIndex or nil
  end
  if type(binding) ~= "table" or getmetatable(binding) ~= nil then
    return nil
  end
  local boundWorld = rawget(binding, "world")
  local boundWidth = rawget(binding, "width")
  local boundHeight = rawget(binding, "height")
  local boundCount = rawget(binding, "cellCount")
  local cells = rawget(binding, "cells")
  if not rawequal(boundWorld, world)
      or type(boundWidth) ~= "number" or boundWidth ~= world.width
      or type(boundHeight) ~= "number" or boundHeight ~= world.height
      or type(boundCount) ~= "number"
      or boundCount ~= #(world.cells or {})
      or type(cells) ~= "table" or getmetatable(cells) ~= nil then
    return nil
  end

  local expectedCount = #(world.cells or {})
  local maximumKey = world.width * world.height
  local seen, count, key = {}, 0, nil
  while true do
    local value
    key, value = next(cells, key)
    if key == nil then break end
    count = count + 1
    if count > MAX_INDEX_ENTRIES or type(key) ~= "number"
        or key ~= key or key == math.huge or key == -math.huge
        or key ~= math.floor(key) or key < 1 or key > maximumKey
        or type(value) ~= "table" or getmetatable(value) ~= nil
        or seen[value] then
      return nil
    end
    local coordinate = key - 1
    local cellX, cellZ = rawget(value, "x"), rawget(value, "z")
    if type(cellX) ~= "number" or cellX ~= coordinate % world.width
        or type(cellZ) ~= "number"
        or cellZ ~= math.floor(coordinate / world.width) then
      return nil
    end
    seen[value] = true
    U.checkpoint(context, count, 32)
  end
  if count ~= expectedCount then return nil end

  for index = 1, expectedCount do
    local cell = rawget(world.cells, index)
    if type(cell) ~= "table" or getmetatable(cell) ~= nil then return nil end
    local cellX, cellZ = rawget(cell, "x"), rawget(cell, "z")
    if type(cellX) ~= "number" or type(cellZ) ~= "number" then return nil end
    local coordinate = cellZ * world.width + cellX + 1
    if not rawequal(rawget(cells, coordinate), cell) or not seen[cell] then
      return nil
    end
    U.checkpoint(context, index, 32)
  end
  return cells
end

-- Select every world-geometry anchor in one deterministic cell pass. The
-- supplied index is never accepted unless every visited coordinate maps back
-- to the exact normalized cell. A mismatch has no buffer side effect, so the
-- caller can rebuild the index and restart this local preprocessing safely.
local function collectAnchors(U, world, policy, enabled, cellIndex, context)
  local treeBuckets, mountainBuckets, boulderBuckets, objectBuckets = {}, {}, {}, {}
  for index, cell in ipairs(world.cells or {}) do
    if enabled.tree and U.isSemanticSupport(cell, "tree_support") then
      selectBucket(U, treeBuckets, world, policy.tree, "tree_support", cell, 0)
    end
    if enabled.mountain and U.isMountainClusterMember(world, cellIndex, cell) then
      selectBucket(U, mountainBuckets, world, policy.mountain, "mountain_peak",
        cell, U.hasTag(cell, "mountain_seed") and 1 or 0)
    end
    if enabled.boulder and U.isSemanticSupport(cell, "boulder_tree") then
      selectBucket(U, boulderBuckets, world, policy.tree, "boulder_tree", cell, 0)
    end
    if enabled.object and U.isSemanticSupport(cell, "object")
        and not U.hasTag(cell, "tree_support")
        and not U.hasTag(cell, "mountain_support")
        and not U.hasTag(cell, "boulder_tree") then
      selectBucket(U, objectBuckets, world, policy.object, "object_shadow", cell, 0)
    end
    U.checkpoint(context, index, 32)
  end
  return {
    tree = anchorSet(treeBuckets),
    mountain = anchorSet(mountainBuckets),
    boulder = anchorSet(boulderBuckets),
    object = anchorSet(objectBuckets),
  }
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
  local enabled = {
    tree = tallTrees or objectShadows,
    mountain = mountainPeaks or objectShadows,
    boulder = boulderTrees or objectShadows,
    object = objectShadows,
  }
  local anchors = { tree = {}, mountain = {}, boulder = {}, object = {} }
  local anyAnchors = tallTrees or mountainPeaks or boulderTrees or objectShadows
  if anyAnchors then
    local cellIndex
    if enabled.mountain then
      cellIndex = validateIndex(U, world, nil, context)
      if not cellIndex then
        -- Direct feature tests and older internal callers do not have App's
        -- snapshot binding. Rebuild from normalized cells and validate the
        -- complete key set before any semantic lookup.
        local rebuilt = U.indexCells(world, context)
        cellIndex = assert(validateIndex(U, world, {
          world = world,
          cells = rebuilt,
          width = world.width,
          height = world.height,
          cellCount = #(world.cells or {}),
        }, context), "rebuilt world index is invalid")
      end
    end
    anchors = assert(collectAnchors(
      U, world, policy, enabled, cellIndex, context
    ))
  end
  local treeAnchors = anchors.tree
  local mountainAnchors = anchors.mountain
  local boulderAnchors = anchors.boulder
  local objectAnchors = anchors.object

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
