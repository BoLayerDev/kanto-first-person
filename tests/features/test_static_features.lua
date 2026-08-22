return function(T)
  local function load(path) return assert(loadfile(T.root .. "/" .. path))() end
  local Util = load("src/features/Util.lua")
  local CommandBuffer = load("src/render/CommandBuffer.lua")
  local PacketHash = load("src/render/PacketHash.lua")
  local Interior = load("src/features/Interior.lua")
  local Cave = load("src/features/Cave.lua")
  local WorldGeometry = load("src/features/WorldGeometry.lua")
  local Flora = load("src/features/Flora.lua")
  local Battle = load("src/features/Battle.lua")
  local WorldSnapshot = load("src/companion/WorldSnapshot.lua")
  local API = load("companion/api_v1.lua")
  local certifiedHosts = load(
    "tests/fixtures/synthetic_kfp/certified_host_cells.lua")

  local function newBuffer()
    return CommandBuffer.new({ hashCommand = PacketHash.hashCommand })
  end

  local function context(world, values, capabilities, quality)
    return {
      world = world,
      config = values or {},
      quality = quality or { density = 1, resolved = "HIGH", panoramaWidth = 4096 },
      services = { capabilities = capabilities or {} },
      checkpoint = function() end,
    }
  end

  local function itemCount(packet, predicate)
    local count = 0
    for _, commands in pairs(packet.phases) do
      for _, command in ipairs(commands) do
        if predicate(command) then count = count + #(command.items or {}) end
      end
    end
    return count
  end

  local function itemCoordinates(packet, predicate)
    local coordinates = {}
    for _, commands in pairs(packet.phases) do
      for _, command in ipairs(commands) do
        if predicate(command) then
          for _, item in ipairs(command.items or {}) do
            coordinates[#coordinates + 1] = tostring(item.x) .. "|" .. tostring(item.z)
          end
        end
      end
    end
    table.sort(coordinates)
    return coordinates
  end

  local function validatePortable(packet)
    for _, commands in pairs(packet.phases) do
      for _, command in ipairs(commands) do
        local ok, err = API.validate_draw_command(command, command.kind)
        if not ok then error(tostring(err), 0) end
      end
    end
  end

  T.test("feature hash framing matches the precomputed-prefix reference", function()
    local UINT32, MULTIPLIER = 4294967296, 65599
    local function hashText(hash, text)
      for index = 1, #text do
        hash = (hash * MULTIPLIER + text:byte(index)) % UINT32
      end
      return hash
    end
    local function referenceHash(...)
      local hash = 2166136261
      for index = 1, select("#", ...) do
        local text = tostring(select(index, ...))
        hash = hashText(hash, tostring(#text) .. ":")
        hash = hashText(hash, text)
        hash = (hash * MULTIPLIER + 255) % UINT32
      end
      return hash
    end

    local corpus = {
      {},
      { "" },
      { "a", "bc" },
      { "ab", "c" },
      { true, false, 0, -1, 1.25 },
      { "colon:frame", string.char(0, 255), "end" },
      { string.rep("x", 64) },
      { string.rep("y", 65) },
      { string.rep("z", 1024), "tail" },
    }
    for length = 0, 128 do corpus[#corpus + 1] = { string.rep("p", length) } end
    for index, parts in ipairs(corpus) do
      T.equal(Util.hash(unpack(parts)), referenceHash(unpack(parts)),
        "hash corpus item " .. index)
    end
  end)

  T.test("flora hoists invariants and preserves rollover template origins", function()
    local cells, x = {}, 0
    while #cells < 5 do
      local seed = Util.hash("FLORA_TEMPLATE_ROLLOVER", x, 0, "flora")
      if Util.keep(8 / 9, seed, "canopy") then
        local number = #cells + 1
        cells[number] = {
          x = x,
          z = 0,
          material = "canopy:" .. number,
          tags = { forest = true, grass = true },
        }
      end
      x = x + 1
    end
    local world = {
      id = "FLORA_TEMPLATE_ROLLOVER",
      width = x,
      height = 1,
      cellSize = 16,
      tags = { forest = true, night = true },
      cells = cells,
    }
    local optionCalls, worldTagCalls = {}, {}
    local countingUtil = setmetatable({}, { __index = Util })
    function countingUtil.option(config, key, default)
      optionCalls[key] = (optionCalls[key] or 0) + 1
      return Util.option(config, key, default)
    end
    function countingUtil.hasTag(subject, tag)
      if subject == world then worldTagCalls[tag] = (worldTagCalls[tag] or 0) + 1 end
      return Util.hasTag(subject, tag)
    end

    local buffer = CommandBuffer.new({
      maxBatchItems = 2,
      hashCommand = PacketHash.hashCommand,
    })
    Flora.new({ util = countingUtil }):compile(context(world, {
      grass_height = "SUBTLE",
      wind = "BREEZE",
      forest_canopy = true,
      hanging_vines = true,
      particles = true,
      sun_shafts = true,
    }), buffer)
    local commands = buffer:seal().phases.opaque_after_terrain
    local canopies = {}
    for _, command in ipairs(commands) do
      if command.key == "canopy" then canopies[#canopies + 1] = command end
    end
    T.equal(#canopies, 3)
    for index, command in ipairs(canopies) do
      T.equal(command.material, "canopy:" .. (index * 2 - 1))
      T.equal(command.prototype.primitive, "canopy")
      T.equal(command.prototype.width, 16)
      T.equal(#command.items, index < 3 and 2 or 1)
    end
    T.deepEqual({ canopies[1].items[1].cellX, canopies[1].items[2].cellX,
      canopies[2].items[1].cellX, canopies[2].items[2].cellX,
      canopies[3].items[1].cellX },
      { cells[1].x, cells[2].x, cells[3].x, cells[4].x, cells[5].x })
    for _, key in ipairs({ "grass_height", "wind", "forest_canopy",
      "hanging_vines", "particles", "sun_shafts" }) do
      T.equal(optionCalls[key], 1, key)
    end
    for _, tag in ipairs({ "interior", "forest", "night" }) do
      T.equal(worldTagCalls[tag], 1, tag)
    end
  end)

  T.test("spatial anchor preprocessing charges bounded build checkpoints", function()
    local cells = {}
    for z = 0, 7 do
      for x = 0, 7 do cells[#cells + 1] = { x = x, z = z } end
    end
    local world = { id = "CHECKPOINTS", width = 8, height = 8, cells = cells }
    local charged = 0
    local buildContext = {
      checkpoint = function(cost) charged = charged + cost end,
    }
    local anchors = Util.clusterAnchors(world, 2, "test", nil, nil, buildContext)
    local count = 0
    for _ in pairs(anchors) do count = count + 1 end
    T.equal(count, 16)
    T.equal(charged, 64)
    local index = Util.indexCells(world, buildContext)
    T.equal(index[64], cells[64])
    T.equal(charged, 128)
  end)

  T.test("feature hashes are unique and distributed across a 2D grid", function()
    local anchorSeen, rankedSeen, buckets = {}, {}, {}
    local anchorUnique, rankedUnique = 0, 0
    for bucket = 1, 16 do buckets[bucket] = 0 end
    for z = 0, 31 do
      for x = 0, 31 do
        local anchorHash = Util.hash("HASH_GRID", x, z, "tree_support")
        if not anchorSeen[anchorHash] then
          anchorSeen[anchorHash], anchorUnique = true, anchorUnique + 1
        end
        local seed = Util.hash("HASH_GRID", x, z, "flora")
        local rankedHash = Util.hash(seed, "canopy")
        if not rankedSeen[rankedHash] then
          rankedSeen[rankedHash], rankedUnique = true, rankedUnique + 1
        end
        local bucket = math.floor(Util.unit(seed, "canopy") * 16) + 1
        buckets[bucket] = buckets[bucket] + 1
      end
    end
    T.equal(anchorUnique, 1024)
    T.equal(rankedUnique, 1024)
    for bucket, count in ipairs(buckets) do
      T.truthy(count >= 40 and count <= 88,
        "hash bucket " .. bucket .. " has " .. count .. " values")
    end
  end)

  T.test("spatial anchors do not depend on world cell order", function()
    local forward, reversed = {}, {}
    for z = 0, 15 do
      for x = 0, 15 do
        forward[#forward + 1] = { x = x, z = z, rank = (x + z) % 3 }
      end
    end
    for index = #forward, 1, -1 do reversed[#reversed + 1] = forward[index] end

    local function keys(cells)
      local anchors = Util.clusterAnchors({
        id = "REORDER_GRID", width = 16, height = 16, cells = cells,
      }, 4, "reorder", nil, function(cell) return cell.rank end)
      local out = {}
      for key in pairs(anchors) do out[#out + 1] = key end
      table.sort(out)
      return out
    end

    T.deepEqual(keys(forward), keys(reversed))
  end)

  T.test("certified host cells select only solid tree and mountain supports", function()
    T.equal(certifiedHosts.fixtureKind,
      "authored-rom-free-certified-host-cells-v5")

    local function compile(raw, options)
      options = options or {}
      local world, err = WorldSnapshot.capture(raw)
      T.falsy(err)
      T.truthy(world)
      local buffer = newBuffer()
      local compileContext = context(world, {
        world_apron = false,
        tall_trees = true,
        mountain_peaks = true,
        boulder_trees = options.boulderTrees == true,
        object_shadows = true,
        grass_height = "OFF",
        forest_canopy = false,
        hanging_vines = false,
        particles = false,
        sun_shafts = false,
      }, {
        shadow_pass = 1,
        battle_pass = options.battlePass and 1 or nil,
      })
      WorldGeometry.new({ util = Util }):compile(compileContext, buffer)
      Flora.new({ util = Util }):compile(compileContext, buffer)
      if options.battlePass then
        Battle.new({ util = Util }):compile(compileContext, buffer)
      end
      return world, buffer:seal()
    end

    local function reverseCells(raw)
      local reversed = {}
      for key, value in pairs(raw) do reversed[key] = value end
      reversed.cells = {}
      for index = #raw.cells, 1, -1 do
        reversed.cells[#reversed.cells + 1] = raw.cells[index]
      end
      return reversed
    end

    local function battleMode(raw)
      local copied = {}
      for key, value in pairs(raw) do copied[key] = value end
      copied.mode = "battle"
      copied.tags = {}
      for key, value in pairs(raw.tags or {}) do copied.tags[key] = value end
      copied.tags.battle = true
      return copied
    end

    local battleWorld, battlePacket = compile(certifiedHosts.battle)
    local cellsByTile = {}
    for _, cell in ipairs(battleWorld.cells) do
      cellsByTile[cell.metadata.tile] = cell
    end
    for _, tile in ipairs({ 64, 65, 80, 81 }) do
      local cell = cellsByTile[tile]
      T.equal(cell.kind, "cylinder")
      T.truthy(cell.solid)
      T.falsy(cell.walkable)
      T.truthy(cell.tags.tree_support)
      T.truthy(cell.tags.tree)
      T.falsy(cell.tags.boulder_tree)
    end
    for _, tile in ipairs({ 42, 43, 58, 59 }) do
      local cell = cellsByTile[tile]
      T.equal(cell.kind, "cylinder")
      T.truthy(cell.solid)
      T.falsy(cell.walkable)
      T.truthy(cell.tags.boulder_tree)
      T.truthy(cell.tags.boulder)
      T.falsy(cell.tags.tree_support)
      T.falsy(cell.tags.tree)
    end
    T.equal(cellsByTile[2].kind, "wall")
    T.equal(cellsByTile[36].kind, "cliff")
    for _, tile in ipairs({ 2, 36 }) do
      T.truthy(cellsByTile[tile].tags.mountain_seed)
      T.truthy(cellsByTile[tile].tags.mountain_support)
    end
    T.equal(cellsByTile[3].kind, "cliff")
    T.equal(cellsByTile[37].kind, "wall")
    for _, tile in ipairs({ 3, 37 }) do
      T.truthy(cellsByTile[tile].tags.mountain_support)
      T.falsy(cellsByTile[tile].tags.mountain_seed)
    end
    T.truthy(cellsByTile[99].walkable)
    T.falsy(cellsByTile[99].tags.tree_support)
    T.falsy(cellsByTile[99].tags.boulder_tree)
    T.falsy(cellsByTile[99].tags.mountain_support)
    T.truthy(cellsByTile[40].walkable)
    T.falsy(cellsByTile[40].solid)
    T.truthy(cellsByTile[40].tags.object)
    T.falsy(cellsByTile[40].tags.mountain_support)
    T.equal(itemCount(battlePacket, function(command)
      return command.key and command.key:match("^tall_tree_trunks_") ~= nil
    end), 2)
    T.equal(itemCount(battlePacket, function(command)
      return command.key == "tall_tree_canopies"
    end), 2)
    T.equal(itemCount(battlePacket, function(command)
      return command.key == "mountains"
    end), 3)
    T.equal(itemCount(battlePacket, function(command)
      return command.key == "object_shadows"
    end), 7)
    T.equal(itemCount(battlePacket, function(command)
      return command.key == "world_shadow_casters"
    end), 7)
    local ghostCoordinate = "152|8"
    for _, coordinate in ipairs(itemCoordinates(battlePacket, function(command)
      return command.key == "object_shadows"
        or command.key == "world_shadow_casters"
    end)) do
      T.notEqual(coordinate, ghostCoordinate,
        "walkable object ghost must not cast or receive a shadow")
    end
    T.equal(itemCount(battlePacket, function(command)
      return command.key == "boulder_tree_hoods"
    end), 0)
    local _, battleBoulderPacket = compile(certifiedHosts.battle,
      { boulderTrees = true })
    T.equal(itemCount(battleBoulderPacket, function(command)
      return command.key == "boulder_tree_hoods"
    end), 2)
    T.equal(itemCount(battleBoulderPacket, function(command)
      return command.key and command.key:match("^tall_tree_trunks_") ~= nil
    end), 2)
    local _, reversedBattlePacket = compile(reverseCells(certifiedHosts.battle))
    T.deepEqual(battlePacket, reversedBattlePacket)
    T.equal(PacketHash.hash(battlePacket), PacketHash.hash(reversedBattlePacket))

    local battleScene = battleMode(certifiedHosts.battle)
    local _, battleScenePacket = compile(battleScene, {
      boulderTrees = true,
      battlePass = true,
    })
    T.equal(itemCount(battleScenePacket, function(command)
      return command.key == "battle_props:canopy"
    end), 2)
    T.equal(itemCount(battleScenePacket, function(command)
      return command.key == "battle_props:mountain"
    end), 3)
    T.equal(itemCount(battleScenePacket, function(command)
      return command.key == "battle_props:hood"
    end), 2)
    validatePortable(battlePacket)
    validatePortable(battleScenePacket)

    local dramalessWorld, dramalessPacket = compile(certifiedHosts.dramaless)
    local dramalessByX = {}
    for _, cell in ipairs(dramalessWorld.cells) do
      dramalessByX[cell.x] = cell
    end
    T.equal(dramalessByX[0].kind, "cylinder")
    T.equal(dramalessByX[0].metadata.tile, 64)
    T.truthy(dramalessByX[0].tags.tree_support)
    T.falsy(dramalessByX[0].tags.boulder_tree)
    T.equal(dramalessByX[1].kind, "cylinder")
    T.equal(dramalessByX[1].metadata.tile, 42)
    T.truthy(dramalessByX[1].tags.boulder_tree)
    T.falsy(dramalessByX[1].tags.tree_support)
    T.equal(dramalessByX[2].metadata.tile, 2)
    T.truthy(dramalessByX[2].tags.mountain_seed)
    T.truthy(dramalessByX[2].tags.mountain_support)
    for _, x in ipairs({ 3, 4 }) do
      T.truthy(dramalessByX[x].tags.mountain_support)
      T.falsy(dramalessByX[x].tags.mountain_seed)
    end
    T.falsy(dramalessByX[5].tags.mountain_support)
    T.equal(dramalessByX[7].metadata.tile, 36)
    T.truthy(dramalessByX[7].tags.mountain_seed)
    T.truthy(dramalessByX[7].tags.mountain_support)
    T.equal(dramalessByX[11].kind, "cylinder")
    T.equal(dramalessByX[11].height, 16)
    T.truthy(dramalessByX[11].walkable)
    T.falsy(dramalessByX[11].solid)
    T.falsy(dramalessByX[11].tags.tree_support)
    T.equal(itemCount(dramalessPacket, function(command)
      return command.key and command.key:match("^tall_tree_trunks_") ~= nil
    end), 1)
    T.equal(itemCount(dramalessPacket, function(command)
      return command.key == "tall_tree_canopies"
    end), 1)
    T.equal(itemCount(dramalessPacket, function(command)
      return command.key == "mountains"
    end), 2)
    T.equal(itemCount(dramalessPacket, function(command)
      return command.key == "object_shadows"
    end), 5)
    T.equal(itemCount(dramalessPacket, function(command)
      return command.key == "world_shadow_casters"
    end), 5)
    local _, dramalessBoulderPacket = compile(certifiedHosts.dramaless,
      { boulderTrees = true })
    T.equal(itemCount(dramalessBoulderPacket, function(command)
      return command.key == "boulder_tree_hoods"
    end), 1)
    local _, reversedDramalessPacket = compile(reverseCells(certifiedHosts.dramaless))
    T.deepEqual(dramalessPacket, reversedDramalessPacket)
    T.equal(PacketHash.hash(dramalessPacket),
      PacketHash.hash(reversedDramalessPacket))
    validatePortable(dramalessPacket)

    local roofWorld, roofPacket = compile(certifiedHosts.dramalessRoofVeto)
    T.equal(roofWorld.cells[1].kind, "cliff")
    T.equal(roofWorld.cells[1].height, 32)
    T.equal(roofWorld.cells[3].kind, "roof")
    T.equal(roofWorld.cells[3].height, 28)
    T.equal(roofWorld.cells[4].kind, "cylinder")
    for _, cell in ipairs(roofWorld.cells) do
      T.falsy(cell.tags.mountain_seed)
      T.falsy(cell.tags.mountain_support)
    end
    T.equal(itemCount(roofPacket, function(command)
      return command.key == "mountains"
    end), 0)
    validatePortable(roofPacket)
  end)

  T.test("interior builds batched ceiling, walls, fixtures, and shadows", function()
    local world = {
      id = "HOUSE", width = 2, height = 2, cellSize = 16,
      tags = { interior = true },
      cells = {
        { x = 0, z = 0, y = 0, walkable = true, material = "room", tags = { room = true, door = true } },
        { x = 1, z = 0, y = 0, walkable = true, material = "room", tags = { room = true, window = true } },
      },
    }
    local buffer = newBuffer()
    Interior.new({ util = Util }):compile(context(world, {
      ceiling = true, cutaway = true, windows = true, contact_shadows = true,
    }), buffer)
    local packet = buffer:seal()
    T.truthy(#packet.phases.opaque_after_terrain >= 4)
    local kinds = {}
    for _, command in ipairs(packet.phases.opaque_after_terrain) do kinds[command.key or command.kind] = true end
    T.truthy(kinds["ceiling:room"])
    T.truthy(kinds["wall:room"])
    T.truthy(kinds.doors)
    T.truthy(kinds.windows)
    T.truthy(kinds.contact_shadows)
  end)

  T.test("camera-mode ceiling policy and detail remain explicit", function()
    local function compile(mode, policy, detail, cutaway)
      local buffer = newBuffer()
      Interior.new({ util = Util }):compile(context({
        id = "HOUSE", width = 1, height = 1, cellSize = 16,
        mode = mode, tags = { interior = true },
        cells = { { x = 0, z = 0, y = 0, walkable = true,
          material = "room", tags = { room = true } } },
      }, {
        ceiling = true, cutaway = cutaway, third_person_ceiling = policy,
        ceiling_detail = detail, contact_shadows = false,
      }), buffer)
      return buffer:seal().phases.opaque_after_terrain
    end

    local function byKey(commands)
      local seen = {}
      for _, command in ipairs(commands) do seen[command.key] = command end
      return seen
    end

    local function assertCeiling(commands, expectedCutaway, expectedDetail)
      local seen = byKey(commands)
      local keys = { "ceiling:room" }
      if expectedDetail then
        keys[#keys + 1] = "ceiling_beam_x:room"
        keys[#keys + 1] = "ceiling_beam_z:room"
        keys[#keys + 1] = "ceiling_roses:room"
      end
      for _, key in ipairs(keys) do
        T.truthy(seen[key], key)
        T.equal(seen[key].prototype.role, "ceiling", key)
        T.equal(seen[key].prototype.cutaway, expectedCutaway, key)
      end
      if not expectedDetail then
        T.falsy(seen["ceiling_beam_x:room"])
        T.falsy(seen["ceiling_beam_z:room"])
        T.falsy(seen["ceiling_roses:room"])
      end
    end

    for _, mode in ipairs({ "third_person", "diorama" }) do
      local none = compile(mode, "NONE", true, true)
      for _, command in ipairs(none) do
        T.falsy(command.key:match("^ceiling"), mode)
      end

      assertCeiling(compile(mode, "CUTAWAY", true, false), true, true)
      assertCeiling(compile(mode, "FULL", true, true), false, true)
    end

    assertCeiling(compile("third_person", "FULL", false, true), false, false)
    assertCeiling(compile("first_person", "NONE", true, false), false, true)
  end)

  T.test("cave feature batches roofs pools sconces and bats", function()
    local world = {
      id = "ROCK_TUNNEL", width = 1, height = 1, cellSize = 16,
      tags = { cave = true },
      cells = { { x = 0, z = 0, walkable = true, material = "rock",
        tags = { cave = true, pool = true, sconce = true } } },
    }
    local buffer = newBuffer()
    Cave.new({ util = Util }):compile(context(world, {
      cave_rock = true, cave_pools = true, cave_torches = true, bats = true,
    }), buffer)
    local packet = buffer:seal()
    T.truthy(#packet.phases.opaque_after_terrain >= 3)
    T.equal(packet.phases.translucent_after_actors[1].key, "cave_bats")
  end)

  T.test("world geometry fixes object shadow alpha and supplies shadow casters", function()
    local world = {
      id = "ROUTE_1", width = 1, height = 1, cellSize = 16, tags = {}, neighbors = {},
      cells = { { x = 0, z = 0, kind = "tree", solid = true,
        walkable = false, material = "tree",
        tags = { tree = true, tree_support = true, object = true } } },
    }
    local buffer = newBuffer()
    WorldGeometry.new({ util = Util }):compile(context(world, {
      world_apron = true, tall_trees = true, object_shadows = true,
    }, { terrain_patch = 1, shadow_pass = 1 }), buffer)
    local packet = buffer:seal()
    local shadow
    for _, command in ipairs(packet.phases.opaque_after_terrain) do
      if command.key == "object_shadows" then shadow = command end
    end
    T.truthy(shadow)
    T.equal(shadow.prototype.alphaCutoff, 0.1)
    local legacyBlobMaxAlpha = 0.457
    T.falsy(legacyBlobMaxAlpha >= 0.5)
    T.truthy(legacyBlobMaxAlpha > shadow.prototype.alphaCutoff)
    T.equal(#packet.phases.shadow_casters, 1)
    validatePortable(packet)
  end)

  T.test("battle props use explicit semantic roles and bounded anchors", function()
    local world = {
      id = "BATTLE", width = 6, height = 1, cellSize = 16,
      mode = "battle", tags = { battle = true, outdoor = true },
      cells = {
        { x = 0, z = 0, kind = "cylinder", solid = true,
          walkable = false, material = "tree",
          tags = { tree = true, tree_support = true } },
        { x = 1, z = 0, kind = "tree", solid = true,
          walkable = false, material = "raw-tree",
          tags = { tree = true } },
        { x = 2, z = 0, kind = "rock", solid = true,
          walkable = false, material = "mountain",
          tags = { mountain_support = true, mountain_seed = true } },
        { x = 3, z = 0, kind = "wall", solid = true,
          walkable = false, material = "mountain",
          tags = { mountain_support = true } },
        { x = 4, z = 0, kind = "cylinder", solid = true,
          walkable = false, material = "boulder",
          tags = { boulder_tree = true } },
        { x = 5, z = 0, kind = "ground", solid = false,
          walkable = true, material = "prop",
          tags = { battle_prop = true } },
      },
    }
    local buffer = newBuffer()
    Battle.new({ util = Util }):compile(context(world, {
      object_shadows = true, boulder_trees = true,
    }, {
      battle_pass = 1,
    }), buffer)
    local packet = buffer:seal()
    local counts = {}
    for _, command in ipairs(packet.phases.battle_opaque) do
      counts[command.key] = #(command.items or {})
    end
    T.equal(counts["battle_props:canopy"], 1)
    T.equal(counts["battle_props:mountain"], 1)
    T.equal(counts["battle_props:hood"], 1)
    T.equal(counts["battle_props:box"], 1)
    validatePortable(packet)
  end)

  T.test("portable tall trees remain while optional passes need capabilities", function()
    local world = {
      id = "ROUTE_1", width = 1, height = 1, cellSize = 16,
      mode = "battle", tags = {}, neighbors = {},
      cells = { { x = 0, z = 0, kind = "tree", solid = true,
        walkable = false, material = "tree",
        tags = { tree = true, tree_support = true } } },
    }
    local buffer = newBuffer()
    WorldGeometry.new({ util = Util }):compile(context(world, {
      tall_trees = true, object_shadows = true,
    }), buffer)
    Battle.new({ util = Util }):compile(context(world, {}), buffer)
    local packet = buffer:seal()
    T.equal(#packet.phases.shadow_casters, 0)
    T.equal(#packet.phases.battle_opaque, 0)
    local present = {}
    for _, command in ipairs(packet.phases.opaque_after_terrain) do
      present[command.key or command.sortKey or command.kind] = true
      if command.key and command.key:match("^tall_tree_trunks_") then
        present.tall_tree_trunks = true
      end
    end
    T.truthy(present.tall_tree_trunks)
    T.truthy(present.tall_tree_canopies)
    T.falsy(present.raised_trees)
    for _, command in ipairs(packet.phases.opaque_after_terrain) do
      if command.key == "tall_tree_canopies" then
        T.equal(command.items[1].cellX, 0)
        T.equal(command.items[1].cellZ, 0)
      end
    end
    validatePortable(packet)
  end)

  T.test("quality and town tags bound explicit tree supports", function()
    local cells = {}
    for x = 0, 19 do
      cells[#cells + 1] = {
        x = x, z = 0, solid = true, walkable = false, kind = "tree",
        material = "tree",
        tags = { tree = true, tree_support = true, object = true },
      }
      cells[#cells + 1] = {
        x = x, z = 1, solid = true, walkable = false, kind = "canopy",
        material = "canopy",
        tags = { canopy = true, object = true },
      }
      cells[#cells + 1] = {
        x = x, z = 2, solid = true, walkable = false, kind = "roof",
        material = "roof",
        tags = { roof = true, object = true },
      }
    end
    local world = {
      id = "PALLET_TOWN", width = 20, height = 3, cellSize = 16,
      tags = { town = true, outdoor = true }, neighbors = {}, cells = cells,
    }

    local expectedTrees = { HIGH = 7, BALANCED = 5, LOW = 4 }
    for _, tier in ipairs({ "HIGH", "BALANCED", "LOW" }) do
      local density = tier == "HIGH" and 1 or (tier == "BALANCED" and 0.6 or 0.3)
      local buffer = newBuffer()
      WorldGeometry.new({ util = Util }):compile(context(world, {
        world_apron = false, tall_trees = true, mountain_peaks = true,
        object_shadows = false,
      }, {}, { density = density, resolved = tier, panoramaWidth = 4096 }), buffer)
      local packet = buffer:seal()
      local trunks = itemCount(packet, function(command)
        return command.key and command.key:match("^tall_tree_trunks_") ~= nil
      end)
      local canopies = itemCount(packet, function(command)
        return command.key == "tall_tree_canopies"
      end)
      local mountains = itemCount(packet, function(command)
        return command.key == "mountains"
      end)
      T.equal(trunks, expectedTrees[tier], tier .. " town tree anchors")
      T.equal(canopies, trunks, tier .. " tree support pairing")
      T.equal(mountains, 0, tier .. " roofs are not mountains")

      for _, command in ipairs(packet.phases.opaque_after_terrain) do
        if command.key and command.key:match("^tall_tree_trunks_") then
          T.truthy(command.prototype.height == 11
            or command.prototype.height == 17 or command.prototype.height == 23)
          T.equal(command.prototype.width, 3.84)
          T.equal(command.prototype.depth, 3.84)
          for _, item in ipairs(command.items) do
            T.truthy(item.lift == 8 or item.lift == 14 or item.lift == 20)
          end
        elseif command.key == "tall_tree_canopies" then
          T.equal(command.prototype.width, 16)
          for _, item in ipairs(command.items) do
            T.truthy(item.y - 3.6 >= item.lift)
          end
        end
      end
      validatePortable(packet)
    end
  end)

  T.test("mountain supports require cardinal clusters and prioritize seeds", function()
    local cells = {}
    for x = 0, 19 do
      cells[#cells + 1] = {
        x = x, z = 0, solid = true, walkable = false, kind = "cliff",
        material = "rock",
        tags = { mountain = true, mountain_support = true,
          mountain_seed = x == 8 },
      }
    end
    cells[#cells + 1] = {
      x = 0, z = 2, solid = true, walkable = false, kind = "rock",
      material = "isolated-rock",
      tags = { mountain = true, mountain_support = true,
        mountain_seed = true },
    }
    local world = {
      id = "ROUTE_10", width = 20, height = 3, cellSize = 16,
      tags = { route = true, outdoor = true }, neighbors = {}, cells = cells,
    }

    local expectedPeaks = { HIGH = 10, BALANCED = 7, LOW = 5 }
    for _, tier in ipairs({ "HIGH", "BALANCED", "LOW" }) do
      local buffer = newBuffer()
      WorldGeometry.new({ util = Util }):compile(context(world, {
        world_apron = false, tall_trees = false, mountain_peaks = true,
        object_shadows = false,
      }, {}, { density = 1, resolved = tier, panoramaWidth = 4096 }), buffer)
      local packet = buffer:seal()
      T.equal(itemCount(packet, function(command)
        return command.key == "mountains"
      end), expectedPeaks[tier], tier .. " mountain anchors")
      local hasSeed = false
      for _, command in ipairs(packet.phases.opaque_after_terrain) do
        if command.key == "mountains" then
          for _, item in ipairs(command.items) do
            T.falsy(item.z == 40, tier .. " rejects isolated mountain seed")
            if item.summit then hasSeed = true end
          end
        end
      end
      T.truthy(hasSeed, tier .. " preserves mountain seed priority")
      validatePortable(packet)
    end
  end)

  T.test("world apron packets do not retain normalized neighbor snapshots", function()
    local world = {
      id = "ROUTE_1", width = 2, height = 3, cellSize = 16, tags = {},
      neighbors = { { id = "PALLET_TOWN", revision = 7 } }, cells = {},
    }
    local buffer = newBuffer()
    WorldGeometry.new({ util = Util }):compile(context(world, {
      world_apron = true,
    }), buffer)
    local command = buffer:seal({ key = "route", generation = 1 })
      .phases.opaque_after_terrain[1]
    T.equal(command.geometry.width, 32)
    T.equal(command.geometry.depth, 48)
    T.falsy(command.geometry.neighbors)
  end)
end
