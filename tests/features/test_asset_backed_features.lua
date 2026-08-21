return function(T)
  local function load(path) return assert(loadfile(T.root .. "/" .. path))() end
  local Util = load("src/features/Util.lua")
  local CommandBuffer = load("src/render/CommandBuffer.lua")
  local PacketHash = load("src/render/PacketHash.lua")
  local Atmosphere = load("src/features/Atmosphere.lua")
  local Interior = load("src/features/Interior.lua")

  local function newBuffer()
    return CommandBuffer.new({ hashCommand = PacketHash.hashCommand })
  end

  local function context(world, values, assets)
    return {
      world = world,
      config = values or {},
      quality = { density = 1, resolved = "HIGH", panoramaWidth = 4096 },
      services = { assets = assets, capabilities = {} },
      checkpoint = function() end,
    }
  end

  local function outdoor()
    return {
      id = "ROUTE_1", key = "red:ROUTE_1:1", width = 1, height = 1,
      cellSize = 16, tags = {}, cells = {},
    }
  end

  local function findCommand(commands, key)
    for _, command in ipairs(commands) do
      if command.key == key or command.material == key then return command end
    end
  end

  T.test("horizon uses an opaque packaged texture and no geometry asset path", function()
    local image = {}
    local requested = {}
    local assets = {
      image = function(_, path)
        requested[#requested + 1] = path
        return image
      end,
    }
    local buffer = newBuffer()
    Atmosphere.new({ util = Util }):compile(context(outdoor(), {
      horizon = true, horizon_art = "CITY", clouds = false, night_sky = false,
    }, assets), buffer)
    local packet = buffer:seal()
    local horizon = findCommand(packet.phases.background, "horizon:city")
    T.truthy(horizon)
    T.equal(horizon.texture, image)
    T.equal(requested[1], "assets/legacy/horizons/backdrop4.png")
    T.falsy(horizon.geometry.asset)
    T.falsy(horizon.geometry.path)
  end)

  T.test("horizon falls back to a packaged choice and omits unavailable images", function()
    local requested
    local assets = {
      image = function(_, path)
        requested = path
        return nil, "not_available"
      end,
    }
    local buffer = newBuffer()
    Atmosphere.new({ util = Util }):compile(context(outdoor(), {
      horizon = true, horizon_art = "../../foreign.png",
      clouds = false, night_sky = false,
    }, assets), buffer)
    local packet = buffer:seal()
    T.equal(requested, "assets/legacy/horizons/backdrop3.png")
    T.equal(#packet.phases.background, 0)
  end)

  T.test("horizon asset faults do not suppress other atmosphere commands", function()
    local assets = { image = function() error("decode failed") end }
    local buffer = newBuffer()
    Atmosphere.new({ util = Util }):compile(context(outdoor(), {
      horizon = true, clouds = true, night_sky = false,
    }, assets), buffer)
    local packet = buffer:seal()
    T.equal(#packet.phases.background, 3)
    for _, command in ipairs(packet.phases.background) do
      T.falsy(command.material:match("^horizon:"))
    end
  end)

  T.test("poster batches use authorized textures and split by texture choice", function()
    local paths = {
      ["assets/legacy/posters/posters.png"] = {},
      ["assets/legacy/posters/posters-pokecenter.png"] = {},
      ["assets/legacy/posters/posters-pokemart.png"] = {},
    }
    local requested = {}
    local assets = {
      image = function(_, path)
        requested[path] = (requested[path] or 0) + 1
        return paths[path]
      end,
    }
    local world = {
      id = "HOUSE", width = 3, height = 1, cellSize = 16,
      tags = { interior = true },
      cells = {
        { x = 0, z = 0, walkable = true, material = "room",
          tags = { room = true, poster = true }, metadata = { poster = "../../other.png" } },
        { x = 1, z = 0, walkable = true, material = "room",
          tags = { room = true, poster = true }, metadata = { poster = "pokemon-center" } },
        { x = 2, z = 0, walkable = true, material = "room",
          tags = { room = true, poster = true }, metadata = { poster = "poke_mart" } },
      },
    }
    local buffer = newBuffer()
    Interior.new({ util = Util }):compile(context(world, {
      ceiling = true, windows = false, contact_shadows = false,
      rails = false, ceiling_lamps = false, doorway_light = false,
    }, assets), buffer)
    local packet = buffer:seal()
    local expected = {
      ["posters:default"] = paths["assets/legacy/posters/posters.png"],
      ["posters:pokecenter"] = paths["assets/legacy/posters/posters-pokecenter.png"],
      ["posters:pokemart"] = paths["assets/legacy/posters/posters-pokemart.png"],
    }
    local found = 0
    for _, command in ipairs(packet.phases.opaque_after_terrain) do
      if expected[command.key] then
        found = found + 1
        T.equal(command.texture, expected[command.key])
        T.equal(#command.items, 1)
      end
    end
    T.equal(found, 3)
    for path in pairs(paths) do T.equal(requested[path], 1) end
    T.falsy(requested["../../other.png"])
  end)

  T.test("posters are omitted when packaged images are unavailable", function()
    local world = {
      id = "HOUSE", width = 1, height = 1, cellSize = 16,
      tags = { interior = true },
      cells = { { x = 0, z = 0, walkable = true, material = "room",
        tags = { room = true, poster = true } } },
    }
    local buffer = newBuffer()
    Interior.new({ util = Util }):compile(context(world, {
      ceiling = true, contact_shadows = false, doorway_light = false,
    }, { image = function() return nil end }), buffer)
    local packet = buffer:seal()
    for _, command in ipairs(packet.phases.opaque_after_terrain) do
      T.falsy(type(command.key) == "string" and command.key:match("^posters:"))
    end
  end)
end
