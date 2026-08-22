return function(T)
  local WorldSnapshot = assert(loadfile(T.root .. "/src/companion/WorldSnapshot.lua"))()

  local function valid()
    return {
      id = "PALLET_TOWN",
      revision = 3,
      game = "red",
      width = 4,
      height = 3,
      mode = "first_person",
      paletteRevision = 9,
      tilesetRevision = "overworld",
      player = { cellX = 1, cellZ = 2, facing = "north" },
      cells = {
        { x = 1, z = 2, kind = "grass", material = "atlas:1", tags = { "outdoor" } },
      },
      actors = { { id = "oak", x = 2, z = 2 } },
      neighbors = { { id = "ROUTE_1", offsetZ = -1, atlas = "overworld" } },
    }
  end

  T.test("world snapshot copies normalized plain data", function()
    local raw = valid()
    local snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(err)
    T.equal(snapshot.id, "PALLET_TOWN")
    T.equal(snapshot.game, "red")
    T.equal(snapshot.player.facing, "north")
    T.truthy(snapshot.cells[1].tags.outdoor)
    T.equal(snapshot.neighbors[1].id, "ROUTE_1")
    raw.cells[1].kind = "changed"
    T.equal(snapshot.cells[1].kind, "grass")
  end)

  T.test("world snapshot canonicalizes cell order by coordinate", function()
    local first = valid()
    first.width, first.height = 3, 2
    first.cells = {
      { x = 2, z = 1, kind = "last", tags = { object = true } },
      { x = 1, z = 0, kind = "middle", tags = { tree_support = true } },
      { x = 0, z = 0, kind = "first", tags = { mountain_support = true } },
    }
    local second = valid()
    second.width, second.height = first.width, first.height
    second.cells = { first.cells[3], first.cells[1], first.cells[2] }

    local a = assert(WorldSnapshot.capture(first))
    local b = assert(WorldSnapshot.capture(second))
    T.deepEqual(a.cells, b.cells)
    T.equal(a.cells[1].kind, "first")
    T.equal(a.cells[2].kind, "middle")
    T.equal(a.cells[3].kind, "last")
  end)

  T.test("published snapshot limits are defensive and cannot be expanded", function()
    local first = WorldSnapshot.limits()
    T.equal(first.cells, 65536)
    T.equal(first.aggregateMetadataBytes, 2 * 1024 * 1024)
    first.cells = 1
    T.equal(WorldSnapshot.limits().cells, 65536)

    local raw = valid()
    raw.width, raw.height = 1024, 65
    local snapshot, err = WorldSnapshot.capture(raw, { cells = 999999999 })
    T.falsy(snapshot)
    T.truthy(err:find("dimensions", 1, true))
  end)

  T.test("world snapshot rejects unsupported games and invalid bounds", function()
    local raw = valid()
    raw.game = "gold"
    local snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(snapshot)
    T.truthy(err:find("unsupported", 1, true))
    raw = valid()
    raw.cells[1].x = 99
    snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(snapshot)
    T.truthy(err:find("outside", 1, true))
  end)

  T.test("world snapshot rejects sparse duplicate oversized and unbounded input", function()
    local raw = valid()
    raw.cells = { [2] = raw.cells[1] }
    local snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(snapshot)
    T.truthy(err:find("dense", 1, true))

    raw = valid()
    raw.cells[2] = { x = 1, z = 2 }
    snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(snapshot)
    T.truthy(err:find("duplicate", 1, true))

    raw = valid()
    raw.cellSize = 0
    snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(snapshot)
    T.truthy(err:find("cell size", 1, true))

    raw = valid()
    raw.id = string.rep("x", 257)
    snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(snapshot)
    T.truthy(err:find("map id", 1, true))

    raw = valid()
    raw.width, raw.height = 1024, 1024
    snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(snapshot)
    T.truthy(err:find("dimensions", 1, true))
  end)

  T.test("world snapshot rejects excess cells before it reads cell contents", function()
    local raw = valid()
    raw.width, raw.height = 1, 3
    raw.cells = {}
    for index = 1, 4 do
      raw.cells[index] = setmetatable({}, {
        __index = function() error("cell content was read") end,
      })
    end
    local snapshot, err = WorldSnapshot.capture(raw, { cells = 3 })
    T.falsy(snapshot)
    T.truthy(err:find("cell limit", 1, true))
    T.falsy(err:find("cell content", 1, true))
  end)

  T.test("whole snapshot tag metadata node and work budgets fail closed", function()
    local raw = valid()
    raw.cells[1].tags = { first = true, second = true }
    local snapshot, err = WorldSnapshot.capture(raw, { aggregateTags = 1 })
    T.falsy(snapshot)
    T.truthy(err:find("aggregate tag", 1, true))

    raw = valid()
    raw.width = 2
    raw.cells = {
      { x = 0, z = 0, metadata = { note = "abcdef" } },
      { x = 1, z = 0, metadata = { note = "abcdef" } },
    }
    snapshot, err = WorldSnapshot.capture(raw, { aggregateMetadataBytes = 12 })
    T.falsy(snapshot)
    T.truthy(err:find("metadata byte", 1, true))

    raw = valid()
    raw.cells[1].tags = { first = true, second = true }
    snapshot, err = WorldSnapshot.capture(raw, { aggregateNodes = 2 })
    T.falsy(snapshot)
    T.truthy(err:find("node limit", 1, true))

    raw = valid()
    raw.tags = { a = false, b = false, c = false, d = false }
    snapshot, err = WorldSnapshot.capture(raw, { workItems = 4 })
    T.falsy(snapshot)
    T.truthy(err:find("work limit", 1, true))
  end)

  T.test("oversized enum inputs never bypass text or work budgets", function()
    local oversized = string.rep("X", 1024 * 1024)
    local raw = valid()
    raw.id = "M"
    raw.game = oversized
    local snapshot, err = WorldSnapshot.capture(raw, { text = 8 })
    T.falsy(snapshot)
    T.equal(err, "unsupported game")

    raw = valid()
    raw.mode = oversized
    raw.player.facing = oversized
    raw.actors = {}
    for index = 1, 32 do
      raw.actors[index] = { id = index, facing = oversized }
    end
    snapshot, err = WorldSnapshot.capture(raw, {
      text = 16,
      aggregateTextBytes = 1024,
    })
    T.falsy(err)
    T.equal(snapshot.mode, "first_person")
    T.equal(snapshot.player.facing, "down")
    for _, actor in ipairs(snapshot.actors) do
      T.equal(actor.pose.facing, "down")
    end
  end)

  T.test("numeric fields do not convert large or short text", function()
    local raw = valid()
    raw.width = "4"
    local snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(snapshot)
    T.truthy(err:find("dimensions", 1, true))

    local oversized = string.rep("0", 1024 * 1024) .. "7"
    raw = valid()
    raw.cells[1].worldY = oversized
    raw.cells[1].height = oversized
    raw.player.cellX = oversized
    raw.player.cellZ = oversized
    raw.actors[1].cellX = oversized
    raw.actors[1].cellZ = oversized
    raw.neighbors[1].offsetX = oversized
    raw.neighbors[1].offsetZ = oversized
    snapshot, err = WorldSnapshot.capture(raw)
    T.falsy(err)
    T.equal(snapshot.cells[1].y, 0)
    T.equal(snapshot.cells[1].height, 0)
    T.equal(snapshot.player.cellX, 0)
    T.equal(snapshot.player.cellZ, 0)
    T.equal(snapshot.actors[1].pose.cellX, 0)
    T.equal(snapshot.actors[1].pose.cellZ, 0)
    T.equal(snapshot.neighbors[1].offsetX, 0)
    T.equal(snapshot.neighbors[1].offsetZ, 0)
  end)

  T.test("all copied coordinates use the coordinate limit", function()
    local raw = valid()
    raw.cellSize = 1
    raw.cells[1].worldY = 1e308
    raw.cells[1].height = -1e308
    raw.player.cellX = 1e308
    raw.player.cellZ = -1e308
    raw.actors[1].cellX = 1e308
    raw.actors[1].cellZ = -1e308
    raw.neighbors[1].offsetX = 1e308
    raw.neighbors[1].offsetZ = -1e308
    local snapshot = assert(WorldSnapshot.capture(raw, { coordinate = 8 }))
    T.equal(snapshot.cells[1].y, 0)
    T.equal(snapshot.cells[1].height, 0)
    T.equal(snapshot.player.cellX, 0)
    T.equal(snapshot.player.cellZ, 0)
    T.equal(snapshot.actors[1].pose.cellX, 0)
    T.equal(snapshot.actors[1].pose.cellZ, 0)
    T.equal(snapshot.neighbors[1].offsetX, 0)
    T.equal(snapshot.neighbors[1].offsetZ, 0)

    raw.cells[1].worldY = 8
    raw.cells[1].height = -8
    raw.player.cellX = 8
    raw.player.cellZ = -8
    raw.actors[1].cellX = 8
    raw.actors[1].cellZ = -8
    raw.neighbors[1].offsetX = 8
    raw.neighbors[1].offsetZ = -8
    snapshot = assert(WorldSnapshot.capture(raw, { coordinate = 8 }))
    T.equal(snapshot.cells[1].y, 8)
    T.equal(snapshot.cells[1].height, -8)
    T.equal(snapshot.player.cellX, 8)
    T.equal(snapshot.player.cellZ, -8)
    T.equal(snapshot.actors[1].pose.cellX, 8)
    T.equal(snapshot.actors[1].pose.cellZ, -8)
    T.equal(snapshot.neighbors[1].offsetX, 8)
    T.equal(snapshot.neighbors[1].offsetZ, -8)
  end)

  T.test("world snapshot builds stable keys and cell indexes", function()
    local snapshot = assert(WorldSnapshot.capture(valid()))
    local index = WorldSnapshot.index(snapshot)
    T.equal(WorldSnapshot.cell(snapshot, index, 1, 2).kind, "grass")
    T.falsy(WorldSnapshot.cell(snapshot, index, 9, 9))
    T.truthy(snapshot.key:match(
      "^red:PALLET_TOWN:3:9:overworld:0:first_person:clear:tags=%x%x%x%x%x%x%x%x:neighbors=%x%x%x%x%x%x%x%x$"))
  end)

  T.test("neighbor revisions and tags are deterministic cache-key inputs", function()
    local first = valid()
    first.neighbors = {
      { id = "B", revision = 2, tags = { forest = true } },
      { id = "A", revision = 1, tags = { shore = true } },
    }
    local second = valid()
    second.neighbors = { first.neighbors[2], first.neighbors[1] }
    local a = assert(WorldSnapshot.capture(first))
    local b = assert(WorldSnapshot.capture(second))
    T.equal(a.key, b.key)
    second.neighbors[1].revision = 9
    local changed = assert(WorldSnapshot.capture(second))
    T.notEqual(a.key, changed.key)
  end)

  T.test("current map tags are bounded cache-key inputs", function()
    local raw = valid()
    raw.tags = { forest = true }
    local first = assert(WorldSnapshot.capture(raw))
    raw.tags = { shore = true }
    local second = assert(WorldSnapshot.capture(raw))
    T.notEqual(first.key, second.key)
    T.truthy(#first.key < 160)
  end)

  T.test("world snapshot strips functions and cycles from metadata", function()
    local raw = valid()
    raw.cells[1].metadata = { safe = "yes", unsafe = function() end }
    raw.cells[1].metadata.oversized = string.rep("x", 257)
    raw.cells[1].metadata.loop = raw.cells[1].metadata
    local snapshot = assert(WorldSnapshot.capture(raw))
    T.equal(snapshot.cells[1].metadata.safe, "yes")
    T.falsy(snapshot.cells[1].metadata.unsafe)
    T.falsy(snapshot.cells[1].metadata.oversized)
    T.falsy(snapshot.cells[1].metadata.loop)
  end)

  T.test("ledge facts are copied without retaining host objects", function()
    local raw = {
      fresh_for_input = true,
      map = { id = "ROUTE_1", tileset = "OVERWORLD", standing_tile = 44 },
      player = { cell_x = 1, cell_y = 2, facing = "down", moving = false },
      ledges = { { facing = "down", standing_tile = 44, ledge_tile = 55 } },
      unsafe = function() end,
    }
    local copied = WorldSnapshot.copyLedge(raw)
    raw.player.cell_x = 99
    T.equal(copied.player.cell_x, 1)
    T.falsy(copied.unsafe)
    T.truthy(copied.fresh_for_input)
  end)
end
