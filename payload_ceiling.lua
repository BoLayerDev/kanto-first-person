-- The interior CEILING and RISERS: the room's missing upper storey.
-- payload-version: 7
--
-- v1/v2 proved the concept: a flat lid at wall height (16) closed the
-- room in first person.  v3 is the liveable version:
--
--   HEADROOM   the ceiling rides at 32 by default (AIRY; MID 24 and SNUG
--              16 are options), so the eye at 13 stands in a room rather
--              than a crawlspace.
--
--   RISERS     walls rise to meet it.  Every wall-height cell grows side
--              faces from its own top up to the ceiling, textured with
--              the cell's OWN tile art repeated per 16px course -- so a
--              cave's risers are rock, a Mart's are Mart wall, a house's
--              are wallpaper, with nobody authoring anything: the map's
--              art answers for its own materials.
--
--   MATERIALS  the ceiling itself is textured with the room's dominant
--              wall tile, darkened -- rock overhead in caves, plaster in
--              houses -- with a subtle checker in the shade so the
--              surface reads as a surface.
--
--   CUTAWAY    in the DIORAMA rungs (third person), a Sims-style cut:
--              walls whose south side faces open floor -- the ones
--              between the camera and the room -- keep their low 16px
--              stubs, walls behind the room rise, and the ceiling opens
--              in a wide hole that follows the player.  The shipped
--              open-dollhouse look is one options toggle away.
--
-- Geometry is textured straight from the map's terrain atlas (the same
-- palette-baked image the mesher draws with), handed in by the scene as
-- `atlasFor`; without it (an old splice, a headless run) everything falls
-- back to shaded white and still stands.
--
-- Configuration comes from the companion mod (ds_fp_ceiling) through its
-- exports when it is installed, and from this module's own ModSettings
-- when it is not.  Purely presentational throughout: no collision, no
-- movement, no scripts.

local V = ...

local Voxel3D = V.require("Voxel3D")
local TileShape = V.require("TileShape")
local FirstPerson = V.require("FirstPerson")
local ModSetting = V.require("ModSetting")
-- Dramatic Shape's own answer for maps under leaves rather than a roof
local okDN, DayNight = pcall(V.require, "DayNight")

-- telemetry for the companion's on-screen panel; absence of the global
-- means this module never loaded this session
local function status(s) _G.__ds_ceiling_status = s end

local Ceiling = {}

-- fallback rows, governing only when the companion mod is absent
Ceiling.setting = ModSetting.new("fpceiling", "FP CEILING",
                                 { true, false }, { "ON", "OFF" })
Ceiling.headroom = ModSetting.new("fpheadroom", "HEADROOM",
                                  { 32, 24, 16 }, { "AIRY", "MID", "SNUG" })
Ceiling.cutaway = ModSetting.new("fpcutaway", "CUTAWAY",
                                 { true, false }, { "ON", "OFF" })

local WALL_H = 16          -- "wall is 16px for every interior in the game"
local HOLE_RADIUS = 4      -- cutaway ceiling hole, in cells around the player
local BLEND_GATE = 0.5

-- shade language: lit vs shaded riser flanks (matching the mesher's south/
-- east-lit sun), and the ceiling's checker pair
local RISER_SHADE = { pz = 0.85, nz = 0.62, px = 0.80, nx = 0.66 }
local CEIL_SHADE = { 0.42, 0.48 }

local cache = nil  -- { map, key, mesh, note }

status("loaded (v3); awaiting the first frame indoors")

-- ------- configuration: the companion's exports first, own rows second
local function config()
  -- The companion mod (ds_fp_ceiling) publishes a config reader on the
  -- shared Lua state.  Dramatic Shape's namespace has no mod-lookup of
  -- its own, and _G is demonstrably shared -- the debug HUD reads this
  -- module's status the same way -- so this is the channel that works.
  local pub = rawget(_G, "__ds_ceiling_config")
  if type(pub) == "function" then
    local okP, cfg = pcall(pub)
    if okP and type(cfg) == "table" then return cfg end
  end
  return {
    ceiling = Ceiling.setting:get() == true,
    headroom = Ceiling.headroom:get() or 32,
    cutaway = Ceiling.cutaway:get() == true,
  }
end

-- ------- indoors, by the engine's own answer where it has one
-- Open-air tilesets: warp-only maps that are nonetheless SKY.  Viridian
-- Forest, the Safari Zone areas, Route gatehouse yards and the Plateau
-- grounds all have no connections, so "warp-only" alone would roof them.
-- A ceiling over the forest is the one thing worse than no ceiling at all.
local OPEN_AIR_TILESETS = {
  OVERWORLD = true, FOREST = true, PLATEAU = true, SHIP_PORT = true,
}

local function isInterior(map)
  local def = map and map.def
  if not def then return false end

  -- 1. under leaves, not under a roof: Dramatic Shape's own classification
  if okDN and DayNight and DayNight.isCanopy then
    local okC, canopy = pcall(DayNight.isCanopy, map)
    if okC and canopy then return false end
  end

  -- 2. an open-air tileset is open air whatever its connections say
  local tid = def.tileset or (map.tileset and map.tileset.id)
  if tid and OPEN_AIR_TILESETS[tid] then return false end

  -- 3. the engine's own outdoor test where it has one
  local ok, outdoor = pcall(function()
    local Map = require("src.world.Map")
    return Map.isOutdoor and Map.isOutdoor(def)
  end)
  if ok and outdoor ~= nil then return not outdoor end

  -- 4. last resort: a map with neighbours is a map with sky
  local conns = def.connections
  return not (conns and next(conns) ~= nil)
end

-- ------- per-cell facts, by the same shapes the mesher used:
--   h      extrusion height (max of the four tiles)
--   wall   true when any tile classifies as wall/cliff -- furniture at
--          16px (props, plants, cutouts) is NOT a wall and gets no riser
--   void   true when every tile is border-block filler: the black beyond
--          a room's drawn area, which is "outside" for wall purposes
local RISER_CLASSES = { wall = true, cliff = true }

local function borderTiles(map)
  local set = {}
  local def = map.def
  local block = def and def.borderBlock
  local blocks = map.tileset and map.tileset.blocks
  local row = block and blocks and blocks[block + 1]
  for _, t in ipairs(row or {}) do set[t] = true end
  return set
end

local function cellFacts(map, shapes, border, cx, cy)
  local h, wall, voidTiles = 0, false, 0
  for dy = 0, 1 do
    for dx = 0, 1 do
      local tx, ty = cx * 2 + dx, cy * 2 + dy
      local tile = map:tileAt(tx, ty)
      if tile then
        if border[tile] then voidTiles = voidTiles + 1 end
        local s = TileShape.at(map, shapes, tile, tx, ty)
        local sh = s and s.h or 0
        if sh > h then h = sh end
        if s and RISER_CLASSES[s.class] then wall = true end
      end
    end
  end
  return h, wall, voidTiles == 4
end

-- ------- the atlas UV of one 8px tile (ChunkMesher's uvRect, inset half
-- a texel so the sampler never bleeds a neighbour's art)
local INSET = 0.5
local function uvFor(map, tile)
  local ts = map.tileset or {}
  local aw = ts.imageWidth or 128
  local ah = ts.imageHeight or 48
  local perRow = math.floor(aw / 8)
  local ax = (tile % perRow) * 8
  local ay = math.floor(tile / perRow) * 8
  return (ax + INSET) / aw, (ax + 8 - INSET) / aw,
         (ay + INSET) / ah, (ay + 8 - INSET) / ah
end

-- ------- mesh assembly helpers: push one textured quad
local function pushQuad(verts, indexMap, quads, c1, c2, c3, c4, uv, shade)
  local u0, u1, v0, v1 = uv[1], uv[2], uv[3], uv[4]
  verts[#verts + 1] = { c1[1], c1[2], c1[3], u0, v0, shade }
  verts[#verts + 1] = { c2[1], c2[2], c2[3], u1, v0, shade }
  verts[#verts + 1] = { c3[1], c3[2], c3[3], u1, v1, shade }
  verts[#verts + 1] = { c4[1], c4[2], c4[3], u0, v1, shade }
  Voxel3D.pushQuad(indexMap, quads)
  return quads + 1
end

-- A riser face on one side of cell (cx, cy), from y0 up to y1, split into
-- 8px sub-quads so each carries its own tile's art.  `dir` is which
-- neighbour the face looks at: "px", "nx", "pz", "nz".
local function pushRiserFace(verts, indexMap, quads, map, cx, cy, y0, y1, dir)
  local shade = RISER_SHADE[dir]
  local x0, z0 = cx * 16, cy * 16
  for course = y0, y1 - 8, 8 do
    for half = 0, 1 do
      -- the cell's own art, top tile row on the upper course of each
      -- 16px band, repeated up the riser
      local rowTy = cy * 2 + (((y1 - course) / 8) % 2 == 0 and 1 or 0)
      local tile = map:tileAt(cx * 2 + half, rowTy) or 0
      local uv = { uvFor(map, tile) }
      local yA, yB = course + 8, course
      local h0, h1 = half * 8, half * 8 + 8
      local c1, c2, c3, c4
      if dir == "pz" then
        local z = z0 + 16
        c1 = { x0 + h0, yA, z }; c2 = { x0 + h1, yA, z }
        c3 = { x0 + h1, yB, z }; c4 = { x0 + h0, yB, z }
      elseif dir == "nz" then
        c1 = { x0 + h1, yA, z0 }; c2 = { x0 + h0, yA, z0 }
        c3 = { x0 + h0, yB, z0 }; c4 = { x0 + h1, yB, z0 }
      elseif dir == "px" then
        local x = x0 + 16
        c1 = { x, yA, z0 + h1 }; c2 = { x, yA, z0 + h0 }
        c3 = { x, yB, z0 + h0 }; c4 = { x, yB, z0 + h1 }
      else -- nx
        c1 = { x0, yA, z0 + h0 }; c2 = { x0, yA, z0 + h1 }
        c3 = { x0, yB, z0 + h1 }; c4 = { x0, yB, z0 + h0 }
      end
      quads = pushQuad(verts, indexMap, quads, c1, c2, c3, c4, uv, shade)
    end
  end
  return quads
end

-- ------- the build.  `mode` is "fp" (full lid and risers) or "cutaway"
-- (Sims: south-facing walls stay stubs, the lid opens around the player).
local function build(map, H, mode, pcx, pcy)
  local okShapes, shapes = pcall(TileShape.forMap, map)
  if not (okShapes and shapes) then return nil, "TileShape refused" end
  local wc, hc = map.widthCells or 0, map.heightCells or 0
  if wc == 0 or hc == 0 then return nil, "map has no cells" end

  -- one pass of facts; everything below reads these
  local border = borderTiles(map)
  local h, isWall, isVoid = {}, {}, {}
  local walls = 0
  for cy = 0, hc - 1 do
    h[cy], isWall[cy], isVoid[cy] = {}, {}, {}
    for cx = 0, wc - 1 do
      local okF, hh, w, v = pcall(cellFacts, map, shapes, border, cx, cy)
      h[cy][cx] = okF and hh or 0
      isWall[cy][cx] = okF and w or false
      isVoid[cy][cx] = okF and v or false
      if isWall[cy][cx] then walls = walls + 1 end
    end
  end
  -- outside the map body counts as void: that is where the synthesized
  -- boundary walls stand
  local function outside(cx, cy)
    if cx < 0 or cy < 0 or cx >= wc or cy >= hc then return true end
    return isVoid[cy][cx]
  end
  local function heightAt(cx, cy)
    if outside(cx, cy) then return H end
    return h[cy][cx]
  end
  local function openAt(cx, cy)
    return not outside(cx, cy) and not isWall[cy][cx]
           and h[cy][cx] < WALL_H
  end

  -- Door cells: the engine's own collision answer where it has one
  -- (Map:isDoorTileCell, the pokered IsPlayerStandingOnDoorTile test),
  -- with the map's warp list as the fallback.  Gen 1 doors are commonly
  -- TWO cells wide -- a Mart's entrance, a Centre's double doors -- so
  -- these are grouped into runs below rather than treated one at a time.
  local warpAt = {}
  for _, wpt in ipairs((map.def and map.def.warps) or {}) do
    if wpt.x and wpt.y then warpAt[wpt.y * wc + wpt.x] = true end
  end
  local function isDoor(cx, cy)
    if cx < 0 or cy < 0 or cx >= wc or cy >= hc then return false end
    local ok, d = pcall(function() return map:isDoorTileCell(cx, cy) end)
    if ok and d then return true end
    return warpAt[cy * wc + cx] == true
  end

  -- The room's dominant wall tile -- what the ceiling and the synthesized
  -- boundary walls wear.  Border filler is disenfranchised: in a Mart the
  -- most common "wall" tile is the black beyond the shelves, and a black
  -- ceiling is not a material, it is a mistake.
  local tally, ceilTile = {}, nil
  for cy = 0, hc - 1 do
    for cx = 0, wc - 1 do
      if isWall[cy][cx] and not isVoid[cy][cx] then
        for dy = 0, 1 do
          for dx = 0, 1 do
            local t = map:tileAt(cx * 2 + dx, cy * 2 + dy)
            if t and not border[t] then
              tally[t] = (tally[t] or 0) + 1
              if not ceilTile or tally[t] > tally[ceilTile] then
                ceilTile = t
              end
            end
          end
        end
      end
    end
  end

  -- the accent pool: the room's MINORITY wall tiles (windows, pictures,
  -- clocks -- whatever the drawn wall carries besides its main tile),
  -- sprinkled through the synthesized walls so they read as decorated
  -- rather than extruded
  local accents = {}
  for t in pairs(tally) do
    if t ~= ceilTile then accents[#accents + 1] = t end
  end
  table.sort(accents)
  -- deterministic sparkle: stable per position, roughly one course-half
  -- in eight, so the pattern never shimmers between rebuilds
  local function accentFor(cx, cy, course, half)
    if #accents == 0 then return nil end
    local hsh = (cx * 73856093 + cy * 19349663
                 + course * 83492791 + half * 2654435761) % 8
    if hsh ~= 0 then return nil end
    local pick = (cx * 2654435761 + cy * 40503 + course * 65599) % #accents
    return accents[pick + 1]
  end

  local verts, indexMap, quads = {}, {}, 0
  local boundary = 0

  -- the melt: in cutaway, anything on the player's row or south of it
  -- drops to its stub so the camera sees in -- the cross-section follows
  -- the player around the room
  local function melted(cy)
    return mode == "cutaway" and pcy and cy >= pcy
  end

  -- One synthesized boundary face, floor to lid, wearing the far wall's
  -- art with the accent pool sprinkled through it.  The plane stands half
  -- a pixel BEYOND the cell edge so furniture parked against the map edge
  -- (a plant, a bookcase) can never z-fight its own backdrop.  A warp
  -- column fills to full height too, in a darker shade: a recessed
  -- doorway rather than a hole into the dark.
  local EPS = 0.5
  local DOOR_H = math.min(24, H)   -- a door is taller than a wall course

  -- Which way the run of doors extends from this cell, so a double door
  -- gets one frame around the pair with a seam up the middle instead of
  -- two single doors jammed together.  Returns the cell's index in its
  -- run and the run's length.
  local function doorRun(cx, cy, dir)
    local ax, ay = (dir == "pz" or dir == "nz") and 1 or 0,
                   (dir == "px" or dir == "nx") and 1 or 0
    local before = 0
    while isDoor(cx - ax * (before + 1), cy - ay * (before + 1)) do
      before = before + 1
    end
    local after = 0
    while isDoor(cx + ax * (after + 1), cy + ay * (after + 1)) do
      after = after + 1
    end
    return before, before + after + 1
  end

  -- One face of the door assembly at (cx, cy): the leaf itself, its
  -- panelling, the jambs at the run's ends and the lintel above.  The
  -- leaf wears the doorway's OWN art -- the mat, the sill, whatever the
  -- map draws there -- so each tileset's doors look like its doors.
  local function pushDoorFace(cx, cy, dir)
    local idx, runLen = doorRun(cx, cy, dir)
    local shade = RISER_SHADE[dir]
    local x0, z0 = cx * 16, cy * 16
    local leafTile = map:tileAt(cx * 2, cy * 2 + 1) or ceilTile

    -- plane placement helper: a quad on this cell's boundary face,
    -- spanning [u0, u1] across the cell and [y0, y1] up it, pushed out
    -- by `out` so panelling sits proud of the leaf
    local function face(u0, u1, y0, y1, tile, sh, out)
      local uv = { uvFor(map, tile) }
      local o = EPS + (out or 0)
      local c1, c2, c3, c4
      if dir == "pz" then
        local z = z0 + 16 + o
        c1 = { x0 + u0, y1, z }; c2 = { x0 + u1, y1, z }
        c3 = { x0 + u1, y0, z }; c4 = { x0 + u0, y0, z }
      elseif dir == "nz" then
        local z = z0 - o
        c1 = { x0 + u1, y1, z }; c2 = { x0 + u0, y1, z }
        c3 = { x0 + u0, y0, z }; c4 = { x0 + u1, y0, z }
      elseif dir == "px" then
        local x = x0 + 16 + o
        c1 = { x, y1, z0 + u1 }; c2 = { x, y1, z0 + u0 }
        c3 = { x, y0, z0 + u0 }; c4 = { x, y0, z0 + u1 }
      else
        local x = x0 - o
        c1 = { x, y1, z0 + u0 }; c2 = { x, y1, z0 + u1 }
        c3 = { x, y0, z0 + u1 }; c4 = { x, y0, z0 + u0 }
      end
      quads = pushQuad(verts, indexMap, quads, c1, c2, c3, c4, uv, sh)
      boundary = boundary + 1
    end

    -- jambs: a 2px frame only at the ENDS of the run, so a double door
    -- reads as one opening rather than two
    local jL = (idx == 0) and 2 or 0
    local jR = (idx == runLen - 1) and 2 or 0
    if jL > 0 then face(0, jL, 0, DOOR_H, ceilTile, shade) end
    if jR > 0 then face(16 - jR, 16, 0, DOOR_H, ceilTile, shade) end

    -- the leaf, recessed by shade; panelling proud of it in two courses
    face(jL, 16 - jR, 0, DOOR_H, leafTile, shade * 0.55)
    local pL, pR = jL + 3, 16 - jR - 3
    if pR > pL then
      face(pL, pR, 4, DOOR_H * 0.5 - 1, leafTile, shade * 0.78, 0.25)
      face(pL, pR, DOOR_H * 0.5 + 1, DOOR_H - 3, leafTile, shade * 0.78, 0.25)
    end

    -- the lintel: wall art from the door head up to the ceiling
    if H > DOOR_H then
      for course = DOOR_H, H - 8, 8 do
        local top = math.min(course + 8, H)
        face(0, 8, course, top, ceilTile, shade)
        face(8, 16, course, top, ceilTile, shade)
      end
    end
  end

  local function pushBoundary(cx, cy, dir)
    if not ceilTile then return end
    if melted(cy) then return end
    if isDoor(cx, cy) then return pushDoorFace(cx, cy, dir) end
    local shade = RISER_SHADE[dir]
    local x0, z0 = cx * 16, cy * 16
    for course = 0, H - 8, 8 do
      for half = 0, 1 do
        local uv = { uvFor(map, accentFor(cx, cy, course, half) or ceilTile) }
        local yA, yB = course + 8, course
        local h0, h1 = half * 8, half * 8 + 8
        local c1, c2, c3, c4
        if dir == "pz" then
          local z = z0 + 16 + EPS
          c1 = { x0 + h0, yA, z }; c2 = { x0 + h1, yA, z }
          c3 = { x0 + h1, yB, z }; c4 = { x0 + h0, yB, z }
        elseif dir == "nz" then
          local z = z0 - EPS
          c1 = { x0 + h1, yA, z }; c2 = { x0 + h0, yA, z }
          c3 = { x0 + h0, yB, z }; c4 = { x0 + h1, yB, z }
        elseif dir == "px" then
          local x = x0 + 16 + EPS
          c1 = { x, yA, z0 + h1 }; c2 = { x, yA, z0 + h0 }
          c3 = { x, yB, z0 + h0 }; c4 = { x, yB, z0 + h1 }
        else
          local x = x0 - EPS
          c1 = { x, yA, z0 + h0 }; c2 = { x, yA, z0 + h1 }
          c3 = { x, yB, z0 + h1 }; c4 = { x, yB, z0 + h0 }
        end
        quads = pushQuad(verts, indexMap, quads, c1, c2, c3, c4, uv, shade)
        boundary = boundary + 1
      end
    end
  end

  for cy = 0, hc - 1 do
    for cx = 0, wc - 1 do
      local ch = h[cy][cx]

      -- The synthesized walls: EVERY non-void cell that touches the void
      -- gets a full-height backdrop on that side -- open floor, and also
      -- furniture parked against the map edge (the plant, the bookcase),
      -- whose own bodies otherwise stand in front of naked dark.  Gen 1
      -- draws only the north wall; the other three "walls" are the map
      -- edge, so in 3D they have to be stood up here.
      if not isVoid[cy][cx] then
        if outside(cx, cy + 1) then pushBoundary(cx, cy, "pz") end
        if outside(cx, cy - 1) then pushBoundary(cx, cy, "nz") end
        if outside(cx + 1, cy) then pushBoundary(cx, cy, "px") end
        if outside(cx - 1, cy) then pushBoundary(cx, cy, "nx") end
      end

      -- the lid: over every non-void cell whose own column stops short,
      -- minus the cutaway's hole around the player
      local lid = ch < H and not isVoid[cy][cx]
      if lid and mode == "cutaway" and pcx then
        local d = math.max(math.abs(cx - pcx), math.abs(cy - pcy))
        if d <= HOLE_RADIUS then lid = false end
      end
      if lid then
        local x0, z0 = cx * 16, cy * 16
        local shade = CEIL_SHADE[(cx + cy) % 2 + 1]
        local uv = ceilTile and { uvFor(map, ceilTile) } or { 0, 0, 0, 0 }
        quads = pushQuad(verts, indexMap, quads,
                         { x0, H, z0 + 16 }, { x0 + 16, H, z0 + 16 },
                         { x0 + 16, H, z0 }, { x0, H, z0 }, uv, shade)
      end

      -- the risers: WALL-classed cells grow to the lid, one face per
      -- side that looks at open room.  Furniture that happens to stand
      -- 16px tall (props, plants, cutouts) is furniture, not wall, and
      -- keeps its own silhouette.  The cutaway melts these by row.
      if isWall[cy][cx] and not isVoid[cy][cx]
         and ch >= WALL_H and ch < H and not melted(cy) then
        do
          if heightAt(cx, cy + 1) < WALL_H then
            quads = pushRiserFace(verts, indexMap, quads, map,
                                  cx, cy, ch, H, "pz")
          end
          if heightAt(cx, cy - 1) < WALL_H then
            quads = pushRiserFace(verts, indexMap, quads, map,
                                  cx, cy, ch, H, "nz")
          end
          if heightAt(cx + 1, cy) < WALL_H then
            quads = pushRiserFace(verts, indexMap, quads, map,
                                  cx, cy, ch, H, "px")
          end
          if heightAt(cx - 1, cy) < WALL_H then
            quads = pushRiserFace(verts, indexMap, quads, map,
                                  cx, cy, ch, H, "nx")
          end
        end
      end
    end
  end

  local note = ("%d quads (%d boundary), %d wall cells of %dx%d, "
    .. "lid at %d, %s"):format(quads, boundary, walls, wc, hc, H, mode)
  -- accents belong in the note so a monotonous room can be diagnosed
  note = note .. (", %d accent tiles"):format(#accents)
  if quads == 0 then return nil, note .. " -- nothing to build" end
  local mesh = Voxel3D.newMesh(verts, indexMap)
  if not mesh then return nil, note .. " -- driver refused the mesh" end
  return mesh, note
end

-- ------- the draw, from inside the scene pass (depth live, camera placed)
function Ceiling.draw(state, atlasFor)
  local cfg = config()
  if not cfg.ceiling then
    status("ceiling switched off")
    return
  end
  local map = state and state.map
  if not map then
    status("scene ran with no map")
    return
  end
  local mapId = tostring((map.def and map.def.id)
                or (map.tileset and map.tileset.id) or "?")
  if not isInterior(map) then
    status(mapId .. ": outdoors -- untouched by design")
    return
  end
  local okBlend, blend = pcall(FirstPerson.blendEased)
  blend = okBlend and blend or 0
  local mode
  if blend > BLEND_GATE then
    mode = "fp"
  elseif cfg.cutaway then
    mode = "cutaway"
  else
    status(mapId .. ": diorama, CUTAWAY off -- open dollhouse as shipped")
    return
  end

  local H = cfg.headroom or 32
  local pcx, pcy
  if mode == "cutaway" then
    local p = state.player
    pcx = p and p.cellX or 0
    pcy = p and p.cellY or 0
  end
  local key = table.concat({ mode, H, pcx or "-", pcy or "-" }, ":")
  if not cache or cache.map ~= map or cache.key ~= key then
    if cache and cache.mesh then pcall(cache.mesh.release, cache.mesh) end
    local mesh, note = build(map, H, mode, pcx, pcy)
    cache = { map = map, key = key, mesh = mesh, note = tostring(note) }
  end
  if cache.mesh then
    local tex = nil
    if atlasFor then
      local okT, t = pcall(atlasFor, map)
      if okT then tex = t end
    end
    status(mapId .. ": DRAWING " .. cache.note
           .. (tex and ", textured" or ", untextured"))
    Voxel3D.draw(cache.mesh, tex, nil)
  else
    status(mapId .. ": no mesh (" .. cache.note .. ")")
  end
end

function Ceiling.invalidate()
  if cache and cache.mesh then pcall(cache.mesh.release, cache.mesh) end
  cache = nil
end

return Ceiling
