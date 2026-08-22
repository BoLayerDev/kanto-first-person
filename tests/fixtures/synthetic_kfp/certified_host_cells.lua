-- Authored ROM-free records that match the two certified host adapters.
-- Tests pass these host-like tables through WorldSnapshot.capture before
-- compiling features, which matches the production normalization boundary.

local function baseWorld(id, width, tags, cells)
  return {
    id = id,
    revision = 1,
    game = "yellow",
    width = width,
    height = 1,
    cellSize = 16,
    paletteRevision = "synthetic",
    tilesetRevision = "synthetic",
    atlasRevision = "synthetic",
    mode = "first_person",
    weather = "clear",
    tags = tags,
    player = { x = 8, y = 0, z = 8, cellX = 0, cellZ = 0,
      facing = "down" },
    actors = {},
    neighbors = {},
    cells = cells,
  }
end

local function battleCell(x, kind, tile, solid, walkable, tags)
  return {
    x = x,
    z = 0,
    worldY = 0,
    height = kind == "ground" and 0 or 16,
    kind = kind,
    material = ("tileset:OVERWORLD:%s:%d"):format(kind, tile),
    solid = solid,
    walkable = walkable,
    tags = tags,
    metadata = { tile = tile, class = kind },
  }
end

local function battleTree(x, tile)
  return battleCell(x, "cylinder", tile, true, false, {
    cylinder = true, tree = true, tree_support = true, object = true,
  })
end

local function battleBoulder(x, tile)
  return battleCell(x, "cylinder", tile, true, false, {
    cylinder = true, boulder = true, boulder_tree = true, object = true,
  })
end

local battle = baseWorld("SYNTHETIC_BATTLE_ROUTE", 15,
  { outdoor = true }, {
    battleTree(0, 64),
    battleTree(1, 65),
    battleTree(2, 80),
    battleTree(3, 81),
    battleCell(4, "cylinder", 99, false, true, { cylinder = true }),
    battleCell(5, "wall", 2, true, false, {
      wall = true, object = true, mountain = true, mountain_support = true,
      mountain_seed = true,
    }),
    battleCell(6, "cliff", 3, true, false, {
      cliff = true, object = true, mountain = true, mountain_support = true,
    }),
    battleCell(7, "cliff", 36, true, false, {
      cliff = true, object = true, mountain = true, mountain_support = true,
      mountain_seed = true,
    }),
    battleCell(8, "wall", 37, true, false, {
      wall = true, object = true, mountain = true, mountain_support = true,
    }),
    -- Battle Art truthfully publishes `object` for a wall class before its
    -- stable-obstacle test. This adversarial walkable record proves KFP still
    -- fails closed when a broad tag survives on ghost geometry.
    battleCell(9, "wall", 40, false, true, {
      wall = true, object = true,
    }),
    battleBoulder(10, 42),
    battleBoulder(11, 43),
    battleBoulder(12, 58),
    battleBoulder(13, 59),
    battleCell(14, "ground", 6, false, true, {
      ground = true, grass = true,
    }),
  })

local function dramalessCell(x, kind, tile, solid, walkable, tags, height)
  return {
    x = x,
    z = 0,
    y = 0,
    worldY = 0,
    height = height or (kind == "ground" and 0 or 16),
    kind = kind,
    material = ("atlas:OVERWORLD:%d"):format(tile),
    atlas = "host:terrain",
    solid = solid,
    walkable = walkable,
    tags = tags,
    metadata = { tile = tile, tileset = "OVERWORLD", warp = false },
  }
end

local dramaless = baseWorld("SYNTHETIC_DRAMALESS_ROUTE", 13,
  { outdoor = true, route = true, mountain = true }, {
    -- Exact authored OVERWORLD semantic tiles from the certified adapter.
    dramalessCell(0, "cylinder", 64, true, false,
      { cylinder = true, tree = true, tree_support = true, object = true }),
    dramalessCell(1, "cylinder", 42, true, false,
      { cylinder = true, boulder_tree = true, object = true }),

    -- A valid seed plus the two cardinal support cells that the bounded host
    -- flood may publish. The next wall is outside the two-step reach.
    dramalessCell(2, "wall", 2, true, false,
      { mountain = true, mountain_support = true, mountain_seed = true,
        object = true }),
    dramalessCell(3, "wall", 10, true, false,
      { mountain = true, mountain_support = true, object = true }),
    dramalessCell(4, "wall", 10, true, false,
      { mountain = true, mountain_support = true, object = true }),
    dramalessCell(5, "wall", 10, true, false,
      { object = true }),
    dramalessCell(6, "ground", 0, false, true, {}),

    -- An isolated authored seed is a truthful host eligibility fact. KFP's
    -- common cardinal-cluster rule must still decline to render it.
    dramalessCell(7, "wall", 36, true, false,
      { mountain = true, mountain_support = true, mountain_seed = true,
        object = true }),
    dramalessCell(8, "ground", 0, false, true, {}),
    dramalessCell(9, "ground", 0, false, true, {}),
    dramalessCell(10, "ground", 0, false, true, {}),
    -- f757 preserves the authored cylinder's 16-unit shape height even when
    -- collision reports a walkable connection ghost.
    dramalessCell(11, "cylinder", 64, false, true,
      { cylinder = true }, 16),
    dramalessCell(12, "ground", 0, false, true, {}),
  })

-- Exact callback output from f757's ROM-free CUSTOM roof-veto conformance
-- profile. Keep this separate from the authored OVERWORLD facts above: the
-- roof suppresses the nearby seed/support before a public snapshot escapes.
local function dramalessCustomCell(x, kind, tile, height, tags)
  return {
    x = x,
    z = 0,
    y = 0,
    worldY = 0,
    height = height,
    kind = kind,
    material = ("atlas:CUSTOM:%d"):format(tile),
    atlas = "host:terrain",
    solid = true,
    walkable = false,
    tags = tags,
    metadata = { tile = tile, tileset = "CUSTOM", warp = false },
  }
end

local dramalessRoofVeto = baseWorld("SYNTHETIC_DRAMALESS_ROOF_VETO", 4,
  { outdoor = true }, {
    dramalessCustomCell(0, "cliff", 1, 32,
      { cliff = true, object = true }),
    dramalessCustomCell(1, "cliff", 2, 32,
      { cliff = true, object = true }),
    dramalessCustomCell(2, "roof", 3, 28,
      { roof = true, object = true }),
    dramalessCustomCell(3, "cylinder", 4, 16,
      { cylinder = true, object = true }),
  })

return {
  fixtureKind = "authored-rom-free-certified-host-cells-v5",
  battle = battle,
  dramaless = dramaless,
  dramalessRoofVeto = dramalessRoofVeto,
}
