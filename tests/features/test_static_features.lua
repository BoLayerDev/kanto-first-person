return function(T)
  local function load(path) return assert(loadfile(T.root .. "/" .. path))() end
  local Util = load("src/features/Util.lua")
  local CommandBuffer = load("src/render/CommandBuffer.lua")
  local PacketHash = load("src/render/PacketHash.lua")
  local Interior = load("src/features/Interior.lua")
  local Cave = load("src/features/Cave.lua")
  local WorldGeometry = load("src/features/WorldGeometry.lua")
  local Battle = load("src/features/Battle.lua")
  local API = load("companion/api_v1.lua")

  local function newBuffer()
    return CommandBuffer.new({ hashCommand = PacketHash.hashCommand })
  end

  local function context(world, values, capabilities)
    return {
      world = world,
      config = values or {},
      quality = { density = 1, resolved = "HIGH", panoramaWidth = 4096 },
      services = { capabilities = capabilities or {} },
      checkpoint = function() end,
    }
  end

  local function validatePortable(packet)
    for _, commands in pairs(packet.phases) do
      for _, command in ipairs(commands) do
        local ok, err = API.validate_draw_command(command, command.kind)
        if not ok then error(tostring(err), 0) end
      end
    end
  end

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
      cells = { { x = 0, z = 0, walkable = false, material = "tree",
        tags = { tree = true, object = true } } },
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

  T.test("battle props use the separate battle phase", function()
    local world = {
      id = "BATTLE", width = 1, height = 1, cellSize = 16, mode = "battle", tags = {},
      cells = { { x = 0, z = 0, material = "tree", tags = { tree = true } } },
    }
    local buffer = newBuffer()
    Battle.new({ util = Util }):compile(context(world, { object_shadows = true }, {
      battle_pass = 1,
    }), buffer)
    local packet = buffer:seal()
    T.equal(#packet.phases.battle_opaque, 1)
    T.equal(packet.phases.battle_opaque[1].prototype.primitive, "canopy")
    validatePortable(packet)
  end)

  T.test("portable tall trees remain while optional passes need capabilities", function()
    local world = {
      id = "ROUTE_1", width = 1, height = 1, cellSize = 16,
      mode = "battle", tags = {}, neighbors = {},
      cells = { { x = 0, z = 0, material = "tree", tags = { tree = true } } },
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
    end
    T.truthy(present.tall_tree_trunks)
    T.truthy(present.tall_tree_canopies)
    T.falsy(present.raised_trees)
    validatePortable(packet)
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
