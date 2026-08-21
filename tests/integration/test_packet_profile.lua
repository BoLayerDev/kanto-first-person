return function(T)
  local function load(path) return assert(loadfile(T.root .. "/" .. path))() end
  local API = load("companion/api_v1.lua")
  local CommandBuffer = load("src/render/CommandBuffer.lua")
  local PacketHash = load("src/render/PacketHash.lua")
  local Util = load("src/features/Util.lua")

  local function buffer()
    return CommandBuffer.new({ hashCommand = PacketHash.hashCommand })
  end

  local function context(world, config, assets)
    return {
      world = world,
      config = config,
      quality = { density = 1, resolved = "HIGH", panoramaWidth = 4096 },
      services = { capabilities = {}, assets = assets },
      checkpoint = function() end,
    }
  end

  local function validatePacket(packet)
    local total = 0
    local phaseIds = {
      background = 1,
      opaque_after_terrain = 2,
      translucent_after_actors = 3,
      shadow_casters = 4,
      battle_opaque = 5,
    }
    local seen = {}
    for phase, commands in pairs(packet.phases) do
      for _, command in ipairs(commands) do
        if command.kind == "mesh" or command.kind == "instances"
            or command.kind == "billboards" then
          local ok, err = API.validate_draw_command(command, command.kind)
          if not ok then error(command.owner .. ": " .. tostring(err), 0) end
          local prefix, scene, generation, phaseId, sequence, content =
            command.cacheKey:match(
              "^([A-Za-z0-9_]+):([0-9a-f]+):(%d+):(%d+):(%d+):([0-9a-f]+)$")
          T.equal(prefix, "kfp1")
          T.equal(#scene, 8)
          T.truthy(tonumber(generation) >= 0)
          T.equal(tonumber(phaseId), phaseIds[phase])
          T.equal(tonumber(sequence), command.sequence)
          T.equal(#content, 16)
          T.truthy(#command.cacheKey <= 64)
          T.falsy(seen[command.cacheKey])
          seen[command.cacheKey] = true
          total = total + 1
        end
      end
    end
    return total
  end

  T.test("all portable KFP feature commands conform to draw schema v1", function()
    local texture = { opaque = true }
    local assets = {
      image = function(_, path)
        T.truthy(path:match("^assets/legacy/"))
        return texture
      end,
    }
    local outdoor = {
      id = "ROUTE_1", key = "red:ROUTE_1:1", width = 3, height = 2,
      cellSize = 16, mode = "first_person", weather = "clearing",
      tags = { night = true },
      actors = { { id = "npc", pose = { x = 8, y = 0, z = 8 } } },
      cells = {
        { x = 0, z = 0, walkable = true, material = "grass",
          tags = { grass = true, forest = true, vine = true } },
        { x = 1, z = 0, walkable = false, material = "stone",
          tags = { mountain = true, object = true, summit = true } },
        { x = 2, z = 0, walkable = true, material = "shore",
          tags = { shore = true, chimney = true, sun_shaft = true } },
      },
    }
    local config = {
      world_apron = true, mountain_peaks = true, boulder_trees = true,
      object_shadows = true, horizon = true, horizon_art = "KANTO",
      clouds = true, night_sky = true, grass_height = "SUBTLE",
      wind = "BREEZE", forest_canopy = true, hanging_vines = true,
      particles = true, sun_shafts = true, rain = "OFF", rainbows = true,
      aircraft = true, insects = true,
    }
    local out = buffer()
    for _, path in ipairs({
      "src/features/WorldGeometry.lua",
      "src/features/Atmosphere.lua",
      "src/features/Flora.lua",
      "src/features/Weather.lua",
      "src/features/Wildlife.lua",
    }) do
      load(path).new({ util = Util }):compile(context(outdoor, config, assets), out)
    end
    T.truthy(validatePacket(out:seal({ key = outdoor.key, generation = 3 })) > 8)

    local interior = {
      id = "HOUSE", key = "red:HOUSE:1", width = 2, height = 1,
      cellSize = 16, mode = "first_person", tags = { interior = true },
      cells = {
        { x = 0, z = 0, walkable = true, material = "room",
          tags = { room = true, door = true, poster = true },
          metadata = { poster = "POKECENTER", facing = "north" } },
        { x = 1, z = 0, walkable = true, material = "room",
          tags = { room = true, window = true, rail = true, light_fixture = true } },
      },
    }
    out = buffer()
    load("src/features/Interior.lua").new({ util = Util }):compile(
      context(interior, {
        ceiling = true, cutaway = true, windows = true,
        contact_shadows = true, rails = true, ceiling_lamps = true,
      }, assets), out)
    T.truthy(validatePacket(out:seal({ key = interior.key, generation = 4 })) > 4)

    local cave = {
      id = "ROCK_TUNNEL", key = "red:ROCK_TUNNEL:1", width = 1, height = 1,
      cellSize = 16, mode = "first_person", tags = { cave = true },
      cells = { { x = 0, z = 0, walkable = true, material = "rock",
        tags = { cave = true, pool = true, sconce = true } } },
    }
    out = buffer()
    load("src/features/Cave.lua").new({ util = Util }):compile(context(cave, {
      cave_rock = true, cave_pools = true, cave_torches = true, bats = true,
    }), out)
    T.truthy(validatePacket(out:seal({ key = cave.key, generation = 5 })) >= 4)
  end)

  T.test("shared fixture covers the complete v1 draw baseline", function()
    local fixture = load("tests/fixtures/voxel_companion_draw_v1.lua")
    T.equal(fixture.commandCount, 23)
    T.equal(validatePacket(fixture), fixture.commandCount)

    local meshPrimitives, hasItems, hasProcedural = {}, false, false
    for _, commands in pairs(fixture.phases) do
      for _, command in ipairs(commands) do
        if command.kind == "mesh" then
          meshPrimitives[command.geometry.primitive] = true
        elseif command.kind == "billboards" then
          hasItems = hasItems or command.items ~= nil
          hasProcedural = hasProcedural or command.procedural ~= nil
        end
      end
    end
    for _, primitive in ipairs({
      "box", "plane", "world_apron", "panorama", "cloud_layer", "rainbow",
    }) do
      T.truthy(meshPrimitives[primitive], primitive)
    end
    T.equal(#fixture.instancePrimitives, 15)
    T.truthy(hasItems)
    T.truthy(hasProcedural)
  end)
end
