return function(T)
  local function load(path) return assert(loadfile(T.root .. "/" .. path))() end
  local Util = load("src/features/Util.lua")
  local CommandBuffer = load("src/render/CommandBuffer.lua")
  local PacketHash = load("src/render/PacketHash.lua")
  local Atmosphere = load("src/features/Atmosphere.lua")
  local Flora = load("src/features/Flora.lua")
  local Weather = load("src/features/Weather.lua")
  local Wildlife = load("src/features/Wildlife.lua")

  local function newBuffer()
    return CommandBuffer.new({ hashCommand = PacketHash.hashCommand })
  end

  local world = {
    id = "LAVENDER_TEST", key = "red:LAVENDER_TEST:1", width = 4, height = 4,
    cellSize = 16,
    weather = "storm", tags = { lavender = true, forest = true, night = true },
    actors = { { id = "npc", pose = { x = 8, y = 0, z = 8 } } },
    cells = {
      { x = 0, z = 0, walkable = true, tags = { grass = true, forest = true, vine = true } },
      { x = 1, z = 0, walkable = true, tags = { shore = true } },
      { x = 2, z = 0, walkable = true, tags = { chimney = true, sun_shaft = true } },
    },
  }
  local values = {
    horizon = true, horizon_art = "VALLEY", clouds = true,
    night_sky = true, lavender_fog = true,
    grass_height = "SUBTLE", wind = "BREEZE", forest_canopy = true,
    hanging_vines = true, particles = true, sun_shafts = true,
    rain = "ALWAYS", puddles = true, npc_umbrellas = true,
    lightning = true, birds = true, aircraft = true,
    insects = true, ground_flock = true,
  }
  local context = {
    world = world,
    config = values,
    quality = { density = 1, resolved = "HIGH", panoramaWidth = 4096 },
    services = { capabilities = {} },
    checkpoint = function() end,
  }

  T.test("dynamic feature families batch within the High draw target", function()
    local buffer = newBuffer()
    Atmosphere.new({ util = Util }):compile(context, buffer)
    Flora.new({ util = Util }):compile(context, buffer)
    Weather.new({ util = Util }):compile(context, buffer)
    Wildlife.new({ util = Util }):compile(context, buffer)
    local packet = buffer:seal()
    T.truthy(packet.drawCalls <= 48)
    local rain
    for _, command in ipairs(packet.phases.translucent_after_actors) do
      if command.key == "rain" then rain = command end
    end
    T.truthy(rain)
    T.equal(#rain.items, 130)
  end)

  T.test("derived birds and ground flock are omitted without a public resolver", function()
    local buffer = newBuffer()
    Wildlife.new({ util = Util }):compile(context, buffer)
    local packet = buffer:seal()
    local present = {}
    for _, command in ipairs(packet.phases.translucent_after_actors) do
      present[command.key] = true
    end
    T.falsy(present.birds)
    T.falsy(present.ground_flock)
    T.truthy(present.aircraft)
    T.truthy(present.insects)
  end)

  T.test("forest canopy packets carry explicit cutaway cell coordinates", function()
    local buffer = newBuffer()
    Flora.new({ util = Util }):compile(context, buffer)
    local packet = buffer:seal()
    local canopy
    for _, command in ipairs(packet.phases.opaque_after_terrain) do
      if command.key == "canopy" then canopy = command end
    end
    T.truthy(canopy)
    T.equal(canopy.prototype.cutaway, true)
    T.equal(canopy.prototype.width, 16)
    T.equal(canopy.items[1].cellX, 0)
    T.equal(canopy.items[1].cellZ, 0)
    T.truthy(canopy.items[1].y >= 40 and canopy.items[1].y <= 62)
    local grass
    for _, command in ipairs(packet.phases.opaque_after_terrain) do
      if command.key == "grass" then grass = command end
    end
    T.truthy(grass)
    T.equal(grass.prototype.width, 7)
  end)

  T.test("forest canopy density is deterministic and ordered by quality", function()
    local cells = {}
    for z = 0, 11 do
      for x = 0, 11 do
        cells[#cells + 1] = {
          x = x, z = z, walkable = true, tags = { forest = true },
        }
      end
    end
    local forest = {
      id = "VIRIDIAN_FOREST", width = 12, height = 12, cellSize = 16,
      tags = { forest = true, outdoor = true }, cells = cells,
    }

    local function compileCanopy(tier, density)
      local buffer = newBuffer()
      Flora.new({ util = Util }):compile({
        world = forest,
        config = { grass_height = "OFF", forest_canopy = true,
          hanging_vines = false, particles = false, sun_shafts = false },
        quality = { density = density, resolved = tier, panoramaWidth = 4096 },
        services = { capabilities = {} }, checkpoint = function() end,
      }, buffer)
      return buffer:seal()
    end

    local counts, hashes = {}, {}
    for _, row in ipairs({
      { "HIGH", 1 }, { "BALANCED", 0.6 }, { "LOW", 0.3 },
    }) do
      local packet = compileCanopy(row[1], row[2])
      counts[row[1]] = 0
      for _, command in ipairs(packet.phases.opaque_after_terrain) do
        if command.key == "canopy" then
          counts[row[1]] = counts[row[1]] + #command.items
          for _, item in ipairs(command.items) do
            T.truthy(item.y >= 40 and item.y <= 62)
          end
        end
      end
      hashes[row[1]] = PacketHash.hash(packet)
      T.equal(PacketHash.hash(compileCanopy(row[1], row[2])), hashes[row[1]])
    end
    T.truthy(counts.HIGH > counts.BALANCED)
    T.truthy(counts.BALANCED > counts.LOW)
    T.notEqual(hashes.HIGH, hashes.BALANCED)
    T.notEqual(hashes.BALANCED, hashes.LOW)
  end)

  T.test("deterministic emissions do not touch global random state", function()
    math.randomseed(1234)
    local expected = math.random()
    math.randomseed(1234)
    local buffer = newBuffer()
    Weather.new({ util = Util }):compile(context, buffer)
    local actual = math.random()
    T.equal(actual, expected)
  end)

  T.test("invented capability names cannot enable non-API-v1 commands", function()
    local limited = {
      world = world,
      config = values,
      quality = context.quality,
      services = { capabilities = { draw_lights = 1, draw_postprocess = 1 } },
      checkpoint = function() end,
    }
    local buffer = newBuffer()
    Atmosphere.new({ util = Util }):compile(limited, buffer)
    Weather.new({ util = Util }):compile(limited, buffer)
    local packet = buffer:seal()
    local allowed = { mesh = true, instances = true, billboards = true }
    for _, commands in pairs(packet.phases) do
      for _, command in ipairs(commands) do
        T.truthy(allowed[command.kind], command.kind)
      end
    end
  end)
end
