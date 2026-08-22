-- ROM-free synthetic maps for deterministic scene-packet regression tests.
-- These tables are authored test data. They contain no extracted game data.

local function cell(x, z, tags, material, walkable)
  return {
    x = x,
    z = z,
    y = 0,
    walkable = walkable ~= false,
    material = material or "synthetic",
    tags = tags or {},
  }
end

local function world(id, width, height, tags, cells, extra)
  local value = {
    id = id,
    key = "synthetic:" .. id .. ":1",
    revision = 1,
    width = width,
    height = height,
    cellSize = 16,
    mode = "first_person",
    weather = "clear",
    tags = tags or {},
    actors = {},
    cells = cells or {},
  }
  for key, item in pairs(extra or {}) do value[key] = item end
  return value
end

local BASE_CONFIG = {
  ceiling = true,
  cutaway = true,
  windows = true,
  contact_shadows = true,
  object_shadows = true,
  rails = true,
  ceiling_lamps = true,
  doorway_light = true,
  cave_rock = true,
  cave_pools = true,
  cave_torches = true,
  bats = true,
  world_apron = true,
  tall_trees = true,
  mountain_peaks = true,
  boulder_trees = true,
  horizon = true,
  horizon_art = "KANTO",
  clouds = true,
  night_sky = true,
  lavender_fog = true,
  grass_height = "SUBTLE",
  wind = "BREEZE",
  forest_canopy = true,
  hanging_vines = true,
  particles = true,
  sun_shafts = true,
  rain = "SOMETIMES",
  puddles = true,
  npc_umbrellas = true,
  lightning = true,
  rainbows = true,
  aircraft = true,
  insects = true,
}

local function config(overrides)
  local out = {}
  for key, value in pairs(BASE_CONFIG) do out[key] = value end
  for key, value in pairs(overrides or {}) do out[key] = value end
  return out
end

local outdoorCaps = {
  draw_lights = 1,
  draw_postprocess = 1,
  shadow_pass = 1,
}

local cases = {
  {
    id = "indoor",
    world = world("SYNTHETIC_INTERIOR", 3, 2, { interior = true }, {
      cell(0, 0, { room = true, door = true }, "synthetic:room"),
      cell(1, 0, { room = true, window = true, rail = true }, "synthetic:room"),
      cell(2, 0, { room = true, light_fixture = true }, "synthetic:center"),
      cell(0, 1, { room = true, poster = true }, "synthetic:room"),
      cell(1, 1, { room = true, double_door = true, door = true }, "synthetic:room"),
      cell(2, 1, { outside = true }, "synthetic:outside", false),
    }),
    config = config(),
    capabilities = { draw_lights = 1 },
    expect = {
      { phase = "opaque_after_terrain", owner = "interior", kind = "instances" },
      { phase = "opaque_after_terrain", material = "shadow:contact" },
      { phase = "opaque_after_terrain", kind = "lights" },
    },
  },
  {
    id = "cave",
    world = world("SYNTHETIC_CAVE", 3, 2, { cave = true }, {
      cell(0, 0, { cave = true, pool = true }, "synthetic:cave"),
      cell(1, 0, { cave = true, sconce = true }, "synthetic:cave"),
      cell(2, 0, { cave = true }, "synthetic:cave"),
      cell(0, 1, { cave = true, grass = true }, "synthetic:cave"),
      cell(1, 1, { cave = true, vine = true }, "synthetic:cave"),
      cell(2, 1, { cave = true, pool = true, sconce = true }, "synthetic:cave"),
    }),
    config = config(),
    capabilities = {},
    expect = {
      { phase = "opaque_after_terrain", owner = "cave", material = "cave:water" },
      { phase = "opaque_after_terrain", owner = "cave", material = "cave:sconce" },
      { phase = "translucent_after_actors", owner = "cave", kind = "billboards" },
    },
  },
  {
    id = "forest",
    qualitySweep = true,
    world = world("SYNTHETIC_FOREST", 4, 4, { forest = true }, {
      cell(0, 0, { forest = true, tree = true, grass = true, vine = true }, "synthetic:forest"),
      cell(1, 0, { forest = true, grass = true, sun_shaft = true }, "synthetic:forest"),
      cell(2, 0, { forest = true, tree = true, vine = true }, "synthetic:forest"),
      cell(3, 0, { forest = true, grass = true }, "synthetic:forest"),
      cell(0, 1, { forest = true, grass = true, vine = true }, "synthetic:forest"),
      cell(1, 1, { forest = true, tree = true, sun_shaft = true }, "synthetic:forest"),
      cell(2, 1, { forest = true, grass = true }, "synthetic:forest"),
      cell(3, 1, { forest = true, vine = true }, "synthetic:forest"),
      cell(0, 2, { forest = true, tree = true, grass = true }, "synthetic:forest"),
      cell(1, 2, { forest = true, grass = true, vine = true }, "synthetic:forest"),
      cell(2, 2, { forest = true, sun_shaft = true }, "synthetic:forest"),
      cell(3, 2, { forest = true, tree = true, grass = true }, "synthetic:forest"),
      cell(0, 3, { forest = true, grass = true }, "synthetic:forest"),
      cell(1, 3, { forest = true, vine = true }, "synthetic:forest"),
      cell(2, 3, { forest = true, tree = true, grass = true }, "synthetic:forest"),
      cell(3, 3, { forest = true, grass = true, sun_shaft = true }, "synthetic:forest"),
    }),
    config = config(),
    capabilities = outdoorCaps,
    expect = {
      { phase = "opaque_after_terrain", owner = "flora", material = "flora:grass" },
      { phase = "opaque_after_terrain", owner = "flora", material = "synthetic:forest" },
      { phase = "translucent_after_actors", owner = "flora", material = "light:sun_shaft" },
    },
  },
  {
    id = "city_lavender",
    world = world("SYNTHETIC_LAVENDER", 3, 2, { city = true, lavender = true }, {
      cell(0, 0, { object = true, chimney = true }, "synthetic:building"),
      cell(1, 0, { grass = true }, "synthetic:city"),
      cell(2, 0, { object = true }, "synthetic:building"),
      cell(0, 1, {}, "synthetic:road"),
      cell(1, 1, { tree = true }, "synthetic:city"),
      cell(2, 1, {}, "synthetic:road"),
    }),
    config = config({ horizon_art = "CITY" }),
    capabilities = outdoorCaps,
    expect = {
      { phase = "background", owner = "atmosphere", material = "horizon:city" },
      { phase = "translucent_after_actors", owner = "atmosphere", kind = "postprocess" },
    },
  },
  {
    id = "route_neighbor_edge",
    world = world("SYNTHETIC_ROUTE_EDGE", 3, 2, { route = true }, {
      cell(0, 0, { tree = true }, "synthetic:grass"),
      cell(1, 0, { grass = true }, "synthetic:grass"),
      cell(2, 0, { connection_edge = true }, "synthetic:path"),
      cell(0, 1, { object = true }, "synthetic:path"),
      cell(1, 1, { grass = true }, "synthetic:grass"),
      cell(2, 1, { connection_edge = true }, "synthetic:path"),
    }, {
      neighbors = {
        east = {
          id = "SYNTHETIC_NEIGHBOR",
          revision = 2,
          tilesetRevision = 4,
          cells = { cell(0, 0, { grass = true }, "synthetic:neighbor") },
        },
      },
    }),
    config = config({ horizon_art = "VALLEY" }),
    capabilities = outdoorCaps,
    expect = {
      { phase = "opaque_after_terrain", owner = "world_geometry", kind = "mesh",
        material = "world:apron" },
      { phase = "opaque_after_terrain", owner = "world_geometry",
        material = "shadow:object" },
    },
  },
  {
    id = "shore",
    world = world("SYNTHETIC_SHORE", 3, 2, { shore = true }, {
      cell(0, 0, { shore = true, grass = true }, "synthetic:shore"),
      cell(1, 0, { shore = true }, "synthetic:water"),
      cell(2, 0, { shore = true }, "synthetic:water"),
      cell(0, 1, { grass = true }, "synthetic:grass"),
      cell(1, 1, { shore = true }, "synthetic:shore"),
      cell(2, 1, { shore = true, sun_shaft = true }, "synthetic:shore"),
    }),
    config = config(),
    capabilities = outdoorCaps,
    expect = {
      { phase = "translucent_after_actors", owner = "flora", material = "water:foam" },
      { phase = "opaque_after_terrain", owner = "world_geometry", material = "world:apron" },
    },
  },
  {
    id = "mountain",
    world = world("SYNTHETIC_MOUNTAIN", 3, 2, { mountain = true }, {
      cell(0, 0, { mountain = true, object = true }, "synthetic:stone"),
      cell(1, 0, { mountain = true, summit = true }, "synthetic:stone"),
      cell(2, 0, { boulder_tree = true, object = true }, "synthetic:stone"),
      cell(0, 1, { tree = true }, "synthetic:tree"),
      cell(1, 1, { mountain = true }, "synthetic:stone"),
      cell(2, 1, {}, "synthetic:path"),
    }),
    config = config(),
    capabilities = outdoorCaps,
    expect = {
      { phase = "opaque_after_terrain", owner = "world_geometry", material = "synthetic:stone" },
      { phase = "shadow_casters", owner = "world_geometry", kind = "instances" },
    },
  },
  {
    id = "day",
    world = world("SYNTHETIC_DAY", 2, 2, { route = true }, {
      cell(0, 0, { grass = true }, "synthetic:grass"),
      cell(1, 0, {}, "synthetic:path"),
      cell(0, 1, { tree = true }, "synthetic:tree"),
      cell(1, 1, {}, "synthetic:path"),
    }),
    config = config({ horizon_art = "FUJI" }),
    capabilities = outdoorCaps,
    expect = {
      { phase = "background", owner = "atmosphere", material = "horizon:fuji" },
      { phase = "background", owner = "atmosphere", material = "sky:clouds:1" },
    },
  },
  {
    id = "night",
    world = world("SYNTHETIC_NIGHT", 2, 2, { route = true, night = true }, {
      cell(0, 0, { grass = true }, "synthetic:grass"),
      cell(1, 0, { tree = true }, "synthetic:tree"),
      cell(0, 1, {}, "synthetic:path"),
      cell(1, 1, { grass = true }, "synthetic:grass"),
    }),
    config = config(),
    capabilities = outdoorCaps,
    expect = {
      { phase = "background", owner = "atmosphere", material = "sky:stars" },
      { phase = "translucent_after_actors", owner = "flora", material = "flora:firefly" },
    },
  },
  {
    id = "rain",
    world = world("SYNTHETIC_RAIN", 2, 2, { city = true }, {
      cell(0, 0, {}, "synthetic:road"),
      cell(1, 0, { grass = true }, "synthetic:grass"),
      cell(0, 1, {}, "synthetic:road"),
      cell(1, 1, {}, "synthetic:road"),
    }, {
      weather = "rain",
      actors = { { id = "synthetic_npc", pose = { x = 8, y = 0, z = 8 } } },
    }),
    config = config(),
    capabilities = outdoorCaps,
    expect = {
      { phase = "translucent_after_actors", owner = "weather", material = "weather:rain" },
      { phase = "translucent_after_actors", owner = "weather", material = "weather:umbrella" },
    },
  },
  {
    id = "storm",
    world = world("SYNTHETIC_STORM", 2, 2, { route = true }, {
      cell(0, 0, {}, "synthetic:path"),
      cell(1, 0, { grass = true }, "synthetic:grass"),
      cell(0, 1, { object = true }, "synthetic:stone"),
      cell(1, 1, {}, "synthetic:path"),
    }, { weather = "storm" }),
    config = config(),
    capabilities = outdoorCaps,
    expect = {
      { phase = "translucent_after_actors", owner = "weather", kind = "lights" },
      { phase = "translucent_after_actors", owner = "weather", kind = "postprocess" },
    },
  },
  {
    id = "battle_supported",
    world = world("SYNTHETIC_BATTLE", 3, 1, { battle = true }, {
      cell(0, 0, { tree = true }, "synthetic:battle_tree"),
      cell(1, 0, { boulder_tree = true }, "synthetic:battle_rock"),
      cell(2, 0, { battle_prop = true }, "synthetic:battle_prop"),
    }, { mode = "battle" }),
    config = config(),
    capabilities = { battle_pass = 1 },
    expect = {
      { phase = "battle_opaque", owner = "battle", kind = "instances" },
    },
  },
  {
    id = "battle_unsupported",
    world = world("SYNTHETIC_BATTLE_UNSUPPORTED", 3, 1, { battle = true }, {
      cell(0, 0, { tree = true }, "synthetic:battle_tree"),
      cell(1, 0, { boulder_tree = true }, "synthetic:battle_rock"),
      cell(2, 0, { battle_prop = true }, "synthetic:battle_prop"),
    }, { mode = "battle" }),
    config = config(),
    capabilities = {},
    expect = {},
    expectEmptyPhase = "battle_opaque",
  },
}

return {
  cases = cases,
  fixtureKind = "authored-rom-free-synthetic-v1",
}
