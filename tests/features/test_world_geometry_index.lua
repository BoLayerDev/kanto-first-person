return function(T)
  local function load(path) return assert(loadfile(T.root .. "/" .. path))() end

  local App = load("src/bootstrap/App.lua")
  local CommandBuffer = load("src/render/CommandBuffer.lua")
  local PacketHash = load("src/render/PacketHash.lua")
  local Quality = load("src/render/Quality.lua")
  local Util = load("src/features/Util.lua")
  local WorldGeometry = load("src/features/WorldGeometry.lua")
  local WorldSnapshot = load("src/companion/WorldSnapshot.lua")

  local function newBuffer()
    return CommandBuffer.new({
      maxCommands = 4096,
      maxBatchItems = 2048,
      hashCommand = PacketHash.hashCommand,
    })
  end

  local function binding(world, cells)
    return {
      world = world,
      cells = cells or WorldSnapshot.index(world),
      width = world.width,
      height = world.height,
      cellCount = #(world.cells or {}),
    }
  end

  local function context(world, config, quality, worldIndex, checkpoint)
    return {
      world = world,
      config = config,
      quality = quality,
      services = {
        capabilities = { shadow_pass = 1 },
        worldIndex = worldIndex,
      },
      checkpoint = checkpoint or function() end,
    }
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

  -- Frozen local reference for the pre-optimization algorithm. Keep this
  -- independent of WorldGeometry so differential tests catch selection,
  -- ordering, template, and first-item changes.
  local function compileReference(U, compileContext, buffer)
    local world = compileContext.world
    local config = compileContext.config
    local quality = compileContext.quality
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
        nil, compileContext)
    end
    local mountainAnchors = {}
    if mountainPeaks or objectShadows then
      local cellIndex = U.indexCells(world, compileContext)
      mountainAnchors = U.clusterAnchors(world, policy.mountain, "mountain_peak",
        function(cell)
          return U.isMountainClusterMember(world, cellIndex, cell)
        end,
        function(cell) return U.hasTag(cell, "mountain_seed") and 1 or 0 end,
        compileContext)
    end
    local boulderAnchors = {}
    if boulderTrees or objectShadows then
      boulderAnchors = U.clusterAnchors(world, policy.tree, "boulder_tree",
        function(cell) return U.isSemanticSupport(cell, "boulder_tree") end,
        nil, compileContext)
    end
    local objectAnchors = {}
    if objectShadows then
      objectAnchors = U.clusterAnchors(world, policy.object, "object_shadow",
        function(cell)
          return U.isSemanticSupport(cell, "object")
            and not U.hasTag(cell, "tree_support")
            and not U.hasTag(cell, "mountain_support")
            and not U.hasTag(cell, "boulder_tree")
        end, nil, compileContext)
    end

    if worldApron then
      buffer:add("opaque_after_terrain", {
        kind = "mesh",
        owner = "world_geometry",
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
          "tall_tree_trunks_" .. tostring(trunkHeight), "world_geometry",
          U.material(cell, "world:tree"),
          { primitive = "box", role = "tree_trunk", width = size * 0.24,
            height = trunkHeight, depth = size * 0.24 },
          { x = x, y = y + trunkHeight * 0.5, z = z, seed = seed,
            lift = lift })
        instance(buffer, "opaque_after_terrain", "tall_tree_canopies",
          "world_geometry", U.material(cell, "world:tree"),
          { primitive = "canopy", width = size, cutaway = true },
          { x = x, y = y + lift + size * 0.225, z = z, seed = seed,
            lift = lift, cellX = cell.x, cellZ = cell.z })
      end
      if mountainPeaks and selectedMountain then
        instance(buffer, "opaque_after_terrain", "mountains", "world_geometry",
          U.material(cell, "world:stone"),
          { primitive = "mountain", role = "mountain", shadow = true },
          { x = x, y = y, z = z, seed = seed,
            summit = U.hasTag(cell, "mountain_seed") })
      end
      if boulderTrees and selectedBoulder then
        instance(buffer, "opaque_after_terrain", "boulder_tree_hoods",
          "world_geometry", U.material(cell, "world:boulder_tree"),
          { primitive = "hood", role = "boulder_tree", shadow = true },
          { x = x, y = y, z = z, seed = seed })
      end
      local selectedShadow = selectedTree or selectedMountain or selectedBoulder
        or selectedObject
      if objectShadows and selectedShadow then
        instance(buffer, "opaque_after_terrain", "object_shadows",
          "world_geometry", "shadow:object",
          { primitive = "plane", role = "object_shadow", alphaCutoff = 0.1 },
          { x = x, y = y + 0.03, z = z, seed = seed })
        if U.capability(compileContext, "shadow_pass") then
          instance(buffer, "shadow_casters", "world_shadow_casters",
            "world_geometry", U.material(cell, "world:object"),
            { primitive = "box", role = "shadow_caster", width = size * 0.8,
              height = size * 1.5, depth = size * 0.8 },
            { x = x, y = y + size * 0.75, z = z, seed = seed })
        end
      end
      U.checkpoint(compileContext, index, 32)
    end
  end

  local function compilePair(world, config, quality, customUtil, worldIndex)
    local U = customUtil or Util
    local referenceBuffer, optimizedBuffer = newBuffer(), newBuffer()
    compileReference(Util, context(world, config, quality, nil), referenceBuffer)
    local optimizedIndex = worldIndex
    if optimizedIndex == nil then optimizedIndex = binding(world) end
    if optimizedIndex == false then optimizedIndex = nil end
    WorldGeometry.new({ util = U }):compile(
      context(world, config, quality, optimizedIndex),
      optimizedBuffer)
    local metadata = { key = "world-geometry-differential", generation = 1 }
    return referenceBuffer:seal(metadata), optimizedBuffer:seal(metadata)
  end

  local function assertEquivalent(label, world, config, quality, customUtil, index)
    local reference, optimized = compilePair(
      world, config, quality, customUtil, index)
    T.deepEqual(optimized, reference)
    T.equal(PacketHash.hash(optimized), PacketHash.hash(reference),
      label .. " packet hash")
    return optimized
  end

  local function rawWorld(id, width, height, cells, mapTag)
    return {
      id = id,
      revision = 1,
      game = "yellow",
      width = width,
      height = height,
      cellSize = 16,
      mode = "first_person",
      tags = { outdoor = true, [mapTag or "route"] = true },
      cells = cells,
      actors = {},
      neighbors = {},
      player = {},
      weather = "clear",
    }
  end

  local function normalized(raw)
    local world, err = WorldSnapshot.capture(raw)
    T.truthy(world, tostring(err))
    return world
  end

  local function generator(seed)
    return function(limit)
      seed = (seed * 48271) % 2147483647
      return seed % limit
    end
  end

  local function randomCells(width, height, seed)
    local nextValue = generator(seed)
    local cells = {}
    for z = 0, height - 1 do
      for x = 0, width - 1 do
        local kind = nextValue(11)
        local cell = { x = x, z = z, kind = "ground", material = "ground",
          walkable = true, solid = false, tags = {} }
        if kind == 1 or kind == 2 then
          cell.kind, cell.material = "tree", "tree:" .. tostring((x + z) % 3)
          cell.solid, cell.walkable = true, false
          cell.tags = { tree_support = true, object = true }
        elseif kind == 3 or kind == 4 then
          cell.kind, cell.material = "cliff", "stone:" .. tostring(x % 2)
          cell.solid, cell.walkable = true, false
          cell.tags = { mountain_support = true, object = true,
            mountain_seed = nextValue(5) == 0 }
        elseif kind == 5 then
          cell.kind, cell.material = "boulder", "boulder"
          cell.solid, cell.walkable = true, false
          cell.tags = { boulder_tree = true, object = true }
        elseif kind == 6 or kind == 7 then
          cell.kind, cell.material = "sign", "object:" .. tostring(z % 2)
          cell.solid, cell.walkable = true, false
          cell.tags = { object = true }
        elseif kind == 8 then
          cell.tags = { tree_support = true, object = true }
        elseif kind == 9 then
          cell.solid, cell.walkable = true, false
          cell.tags = { object = true, mountain_support = true }
        end
        cells[#cells + 1] = cell
      end
    end
    return cells
  end

  T.test("App passes its captured snapshot index through compiler services", function()
    local requested
    local app = App.new({ mod = {}, loader = {}, diagnostics = {} })
    app.world = { key = "yellow:test:1", width = 2, height = 1,
      cells = { { x = 0, z = 0 }, { x = 1, z = 0 } } }
    app.worldIndex = { app.world.cells[1], app.world.cells[2] }
    app.config = { group_generation = {} }
    app.quality = { resolved = "HIGH" }
    app.hostId, app.hostVersion = "DRAMALESS_SHAPE", "test"
    app.hostCapabilities = {}
    app.textureCatalog = {}
    app.compiler = {
      active = function() return nil end,
      request = function(_, value) requested = value; return 1, false end,
    }
    app.metrics = {
      sceneRequested = function() end,
      sceneReady = function() end,
    }

    T.truthy(app:_requestScene())
    T.truthy(requested)
    T.equal(requested.services.worldIndex.world, app.world)
    T.equal(requested.services.worldIndex.cells, app.worldIndex)
    T.equal(requested.services.worldIndex.width, 2)
    T.equal(requested.services.worldIndex.height, 1)
    T.equal(requested.services.worldIndex.cellCount, 2)
  end)

  T.test("valid snapshot indexes remove rebuilds and keep bounded checkpoints", function()
    local world = normalized(rawWorld(
      "INDEX_REUSE", 8, 8, randomCells(8, 8, 17)))
    local calls, charged = 0, 0
    local countingUtil = setmetatable({}, { __index = Util })
    function countingUtil.indexCells(value, compileContext)
      calls = calls + 1
      return Util.indexCells(value, compileContext)
    end
    local buffer = newBuffer()
    WorldGeometry.new({ util = countingUtil }):compile(context(
      world,
      { tall_trees = true, mountain_peaks = true, boulder_trees = true,
        object_shadows = true },
      Quality.policy("HIGH", "AUTO", "windows"),
      binding(world),
      function(cost) charged = charged + cost end
    ), buffer)
    buffer:seal()
    T.equal(calls, 0)
    T.equal(charged, 256)
  end)

  T.test("missing and every malformed index shape rebuild before output", function()
    local world = normalized(rawWorld(
      "INDEX_FALLBACK", 8, 8, randomCells(8, 8, 29)))
    local config = { world_apron = true, tall_trees = true,
      mountain_peaks = true, boulder_trees = true, object_shadows = true }
    local quality = Quality.policy("HIGH", "AUTO", "windows")
    local rebuilds = 0
    local countingUtil = setmetatable({}, { __index = Util })
    function countingUtil.indexCells(value, compileContext)
      rebuilds = rebuilds + 1
      return Util.indexCells(value, compileContext)
    end

    assertEquivalent("missing index", world, config, quality, countingUtil, false)
    T.equal(rebuilds, 1)

    rebuilds = 0
    local indexTouched = false
    local hostile = setmetatable({}, { __index = function()
      indexTouched = true
      error("hostile index was inspected")
    end })
    assertEquivalent("hostile index", world, config, quality, countingUtil,
      binding(world, hostile))
    T.equal(rebuilds, 1)
    T.falsy(indexTouched)

    local hostileValueTouched = false
    local variants = {
      { name = "hole", mutate = function(index) index[64] = nil end },
      { name = "duplicate reference", mutate = function(index)
        index[64] = index[63]
      end },
      { name = "fractional key", mutate = function(index)
        index[1.5] = index[1]
      end },
      { name = "out of bounds key", mutate = function(index)
        index[65] = index[1]
      end },
      { name = "unexpected value", mutate = function(index)
        index[64] = false
      end },
      { name = "hostile value", mutate = function(index)
        index[64] = setmetatable({}, { __index = function()
          hostileValueTouched = true
          error("hostile value was inspected")
        end })
      end },
      { name = "string key and hostile extra", mutate = function(index)
        index.hostile = setmetatable({}, { __index = function()
          hostileValueTouched = true
          error("hostile extra was inspected")
        end })
      end },
    }
    for _, variant in ipairs(variants) do
      rebuilds = 0
      local damaged = binding(world)
      variant.mutate(damaged.cells)
      assertEquivalent(variant.name, world, config, quality, countingUtil, damaged)
      T.equal(rebuilds, 1, variant.name)
    end
    T.falsy(hostileValueTouched)
  end)

  T.test("a forged sparse-hole mountain neighbor cannot change output", function()
    local world = normalized(rawWorld("SPARSE_MOUNTAIN_HOLE", 3, 1, {
      { x = 0, z = 0, kind = "cliff", material = "stone", solid = true,
        walkable = false, tags = { mountain_support = true } },
      { x = 2, z = 0, kind = "cliff", material = "stone", solid = true,
        walkable = false, tags = { mountain_support = true } },
    }))
    local forged = binding(world)
    forged.cells[2] = {
      x = 1, z = 0, kind = "cliff", material = "forged", solid = true,
      walkable = false, tags = { mountain_support = true },
    }
    local rebuilds = 0
    local countingUtil = setmetatable({}, { __index = Util })
    function countingUtil.indexCells(value, compileContext)
      rebuilds = rebuilds + 1
      return Util.indexCells(value, compileContext)
    end
    local packet = assertEquivalent("forged sparse neighbor", world, {
      world_apron = false,
      tall_trees = false,
      mountain_peaks = true,
      boulder_trees = false,
      object_shadows = false,
    }, Quality.policy("HIGH", "AUTO", "windows"), countingUtil, forged)
    T.equal(rebuilds, 1)
    for _, command in ipairs(packet.phases.opaque_after_terrain) do
      T.notEqual(command.key, "mountains")
    end
  end)

  T.test("hostile equality values are rejected without metamethod calls", function()
    local available, ffi = pcall(require, "ffi")
    if not available then return end
    pcall(ffi.cdef, [[
      typedef struct { int value; } kfp_world_index_hostile_eq_value;
    ]])
    local touched = false
    local Hostile = ffi.metatype("kfp_world_index_hostile_eq_value", {
      __eq = function()
        touched = true
        error("hostile equality metamethod ran")
      end,
    })
    local hostile = Hostile(7)
    local world = normalized(rawWorld(
      "HOSTILE_INDEX_EQUALITY", 8, 8, randomCells(8, 8, 43)))
    local config = { world_apron = true, tall_trees = true,
      mountain_peaks = true, boulder_trees = true, object_shadows = true }
    local quality = Quality.policy("HIGH", "AUTO", "windows")
    local rebuilds = 0
    local countingUtil = setmetatable({}, { __index = Util })
    function countingUtil.indexCells(value, compileContext)
      rebuilds = rebuilds + 1
      return Util.indexCells(value, compileContext)
    end

    local hostileWidth = binding(world)
    hostileWidth.width = hostile
    assertEquivalent("hostile header equality", world, config, quality,
      countingUtil, hostileWidth)
    T.equal(rebuilds, 1)
    T.falsy(touched)

    rebuilds = 0
    local hostileCoordinate = binding(world)
    hostileCoordinate.cells[64] = {
      x = hostile,
      z = 7,
      kind = "forged",
      material = "forged",
      solid = true,
      walkable = false,
      tags = { mountain_support = true },
    }
    assertEquivalent("hostile coordinate equality", world, config, quality,
      countingUtil, hostileCoordinate)
    T.equal(rebuilds, 1)
    T.falsy(touched)
  end)

  T.test("the all-disabled mask keeps only the parent emission scan", function()
    local world = normalized(rawWorld(
      "NO_WORLD_ANCHORS", 8, 8, randomCells(8, 8, 37)))
    local calls, charged, touched = 0, 0, false
    local countingUtil = setmetatable({}, { __index = Util })
    function countingUtil.indexCells()
      calls = calls + 1
      error("disabled anchors rebuilt an index")
    end
    function countingUtil.isSemanticSupport()
      error("disabled anchors ran semantic preprocessing")
    end
    function countingUtil.isMountainClusterMember()
      error("disabled anchors read the index")
    end
    local hostile = setmetatable({}, { __index = function()
      touched = true
      error("disabled anchors inspected the injected index")
    end })
    local config = { world_apron = true, tall_trees = false,
      mountain_peaks = false, boulder_trees = false, object_shadows = false }
    assertEquivalent("all anchors disabled", world, config,
      Quality.policy("HIGH", "AUTO", "windows"), countingUtil, hostile)

    local buffer = newBuffer()
    WorldGeometry.new({ util = countingUtil }):compile(context(
      world, config, Quality.policy("HIGH", "AUTO", "windows"), hostile,
      function(cost) charged = charged + cost end
    ), buffer)
    buffer:seal()
    T.equal(calls, 0)
    T.falsy(touched)
    T.equal(charged, 64)
  end)

  T.test("optimized anchors match the legacy algorithm for all policies and options", function()
    local cells = randomCells(12, 9, 41)
    local tiers = { "HIGH", "BALANCED", "LOW" }
    local mapTags = { "route", "town", "city" }
    for _, mapTag in ipairs(mapTags) do
      local world = normalized(rawWorld(
        "POLICY_" .. mapTag:upper(), 12, 9, cells, mapTag))
      for _, tier in ipairs(tiers) do
        local quality = Quality.policy(tier, "AUTO", "windows")
        for mask = 0, 31 do
          local config = {
            world_apron = mask % 2 == 1,
            tall_trees = math.floor(mask / 2) % 2 == 1,
            mountain_peaks = math.floor(mask / 4) % 2 == 1,
            boulder_trees = math.floor(mask / 8) % 2 == 1,
            object_shadows = math.floor(mask / 16) % 2 == 1,
          }
          assertEquivalent(mapTag .. "/" .. tier .. "/" .. mask,
            world, config, quality)
        end
      end
    end
  end)

  T.test("random normalized and reversed worlds preserve exact packets", function()
    local config = { world_apron = true, tall_trees = true,
      mountain_peaks = true, boulder_trees = true, object_shadows = true }
    local quality = Quality.policy("HIGH", "AUTO", "windows")
    for seed = 1, 24 do
      local cells = randomCells(13, 11, seed * 101)
      local forward = normalized(rawWorld(
        "RANDOM_" .. seed, 13, 11, cells, seed % 2 == 0 and "city" or "route"))
      local reversedCells = {}
      for index = #cells, 1, -1 do reversedCells[#reversedCells + 1] = cells[index] end
      local reversed = normalized(rawWorld(
        "RANDOM_" .. seed, 13, 11, reversedCells,
        seed % 2 == 0 and "city" or "route"))
      local forwardPacket = assertEquivalent(
        "random forward " .. seed, forward, config, quality)
      local reversedPacket = assertEquivalent(
        "random reversed " .. seed, reversed, config, quality)
      T.equal(PacketHash.hash(reversedPacket), PacketHash.hash(forwardPacket),
        "host cell order changed packet " .. seed)
      T.deepEqual(reversedPacket, forwardPacket,
        "host cell order changed command bytes " .. seed)
    end
  end)

  T.test("mountain seed rank and coordinate ties remain exact", function()
    local cells = {}
    for x = 0, 11 do
      cells[#cells + 1] = { x = x, z = 0, kind = "cliff", material = "stone",
        solid = true, walkable = false,
        tags = { mountain_support = true, mountain_seed = x == 3 } }
    end
    local world = normalized(rawWorld("MOUNTAIN_TIES", 12, 1, cells))
    local originalHash = Util.hash
    function Util.hash(...)
      local count = select("#", ...)
      if count == 4 and select(4, ...) == "mountain_peak" then return 7 end
      return originalHash(...)
    end
    local ok, packet = pcall(assertEquivalent, "mountain ties", world, {
        world_apron = false,
        tall_trees = false,
        mountain_peaks = true,
        boulder_trees = false,
        object_shadows = false,
      }, Quality.policy("LOW", "AUTO", "windows"))
    Util.hash = originalHash
    if not ok then error(packet, 0) end
    local mountain
    for _, command in ipairs(packet.phases.opaque_after_terrain) do
      if command.key == "mountains" then mountain = command end
    end
    T.truthy(mountain)
    T.equal(mountain.items[1].x, 56)
    T.truthy(mountain.items[1].summit)
    T.equal(mountain.items[2].x, 72)
    T.falsy(mountain.items[2].summit)
    T.equal(mountain.items[3].x, 168)
  end)

  T.test("maximum 65536-cell snapshots remain bounded and output-identical", function()
    local cells = {}
    for z = 0, 255 do
      for x = 0, 255 do
        local cell = { x = x, z = z, kind = "ground", material = "ground",
          walkable = true, solid = false }
        if x % 32 == 4 and z % 32 == 4 then
          cell.kind, cell.material = "tree", "tree"
          cell.walkable, cell.solid = false, true
          cell.tags = { tree_support = true, object = true }
        elseif x % 32 == 12 and (z % 32 == 12 or z % 32 == 13) then
          cell.kind, cell.material = "cliff", "stone"
          cell.walkable, cell.solid = false, true
          cell.tags = { mountain_support = true,
            mountain_seed = z % 32 == 12, object = true }
        elseif x % 32 == 20 and z % 32 == 20 then
          cell.kind, cell.material = "boulder", "boulder"
          cell.walkable, cell.solid = false, true
          cell.tags = { boulder_tree = true, object = true }
        elseif x % 32 == 28 and z % 32 == 28 then
          cell.kind, cell.material = "sign", "sign"
          cell.walkable, cell.solid = false, true
          cell.tags = { object = true }
        end
        cells[#cells + 1] = cell
      end
    end
    local world = normalized(rawWorld("MAXIMUM_GRID", 256, 256, cells))
    T.equal(#world.cells, 65536)
    local charged = 0
    local index = binding(world)
    local reference, optimized = compilePair(world, {
      world_apron = true,
      tall_trees = true,
      mountain_peaks = true,
      boulder_trees = true,
      object_shadows = true,
    }, Quality.policy("HIGH", "AUTO", "windows"), nil, index)
    T.equal(PacketHash.hash(optimized), PacketHash.hash(reference))
    T.deepEqual(optimized, reference)

    local buffer = newBuffer()
    WorldGeometry.new({ util = Util }):compile(context(
      world,
      { world_apron = false, tall_trees = true, mountain_peaks = true,
        boulder_trees = true, object_shadows = true },
      Quality.policy("HIGH", "AUTO", "windows"),
      index,
      function(cost) charged = charged + cost end
    ), buffer)
    buffer:seal()
    T.equal(charged, 262144)
  end)
end
