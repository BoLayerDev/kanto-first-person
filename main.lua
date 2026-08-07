-- FP Ceiling for Dramatic Shape --------------------------------------------
-- A companion mod: it ships no renderer of its own.  What it ships is the
-- CEILING PATCH for the Dramatic Shape Voxel Mod -- lib/Ceiling.lua plus
-- two splices into Dramatic Shape's own files -- and the machinery to
-- apply, re-apply and remove that patch safely from alongside.
--
-- Why a patcher rather than a renderer: the engine draws ONE world
-- pipeline per frame, and Dramatic Shape keeps its modules in a private
-- namespace with no exports, so there is no seam a second mod could draw
-- through into its depth-buffered scene.  The ceiling has to live inside
-- Dramatic Shape's own scene pass; this mod is how it gets there and
-- stays there across updates.
--
-- HOW IT WRITES.  Everything goes through love.filesystem, whose save
-- directory SHADOWS the game folder: when Dramatic Shape is installed in
-- the game folder, the patched copies land in the save directory and
-- override the originals without touching them -- removing the shadows is
-- a complete undo.  When Dramatic Shape is installed in the save
-- directory itself, the originals are backed up (*.pre-ceiling) before
-- being replaced, and restore is the undo.  The mod tells the two apart
-- with love.filesystem.getRealDirectory and never deletes a file it
-- cannot bring back.
--
-- UPDATES.  A version stamp is kept; when Dramatic Shape updates, stale
-- shadow copies of the OLD patched files are cleared and the NEW files
-- are patched fresh.  If a future version moves the anchor text, the
-- patch refuses cleanly and says so on the console rather than guessing.
--
-- The CEILING PATCH row (this mod's options) is the master switch: OFF at
-- boot backs the patch out.  Dramatic Shape itself gains an FP CEILING
-- row for the runtime toggle.

-- The original author deleted the upstream; absol89's fork carries the
-- torch and renamed its id at 1.7.6. Either identity is Dramatic Shape
-- to this patch.
local DS_IDS = { "DRAMATIC_SHAPE", "BATTLE_ART_VOXEL_FORK" }
local DS_ID = "DRAMATIC_SHAPE"   -- kept for messages
local STATE_FILE = "ds_fp_ceiling_state"
local MARK = "Ceiling.draw"   -- present in VoxelScene.lua only when patched

-- ------- the splices, anchored on exact 1.5.x text

-- Anchors, most specific first.  Dramatic Shape has forks -- absol89's
-- battle-art build is from 1.3.0 and has no Water module at all -- so the
-- require splice tries a list rather than assuming one line exists.  The
-- Voxel3D require is present in every version seen so far and is the
-- reliable fallback.
local REQ_ANCHORS = {
  'local Water = V.require("Water")',
  'local ChunkMesher = V.require("ChunkMesher")',
  'local Voxel3D = V.require("Voxel3D")',
}

local function firstAnchor(src, list)
  for _, a in ipairs(list) do
    if src and src:find(a, 1, true) then return a end
  end
  return nil
end

local REQ_ANCHOR = REQ_ANCHORS[1]
local REQ_ADD = REQ_ANCHOR .. '\nlocal Ceiling = V.require("Ceiling")'
                          .. '\nlocal Backdrop = V.require("Backdrop")'
                          .. '\nlocal SkyLayer = V.require("SkyLayer")'
                          .. '\nlocal Flora = V.require("Flora")'

local SCENE_ANCHOR = [[  Voxel3D.draw(terrain, atlasFor(state.map), nil)
  for i, nb in ipairs(state.neighbors or {}) do
    Voxel3D.draw(nbMesh[i], atlasFor(nb.map),
                 Mat4.translate(nb.ox, 0, nb.oy))
  end]]
local SCENE_ADD = [[  -- the distant horizon (lib/Backdrop.lua): before the terrain and with
  -- depth writes off, so every real surface draws over the painting
  pcall(Backdrop.draw, state)

  -- clouds and birds (lib/SkyLayer.lua): with the backdrop, behind the
  -- world, depth writes off
  pcall(SkyLayer.draw, state)

]] .. SCENE_ANCHOR .. [[


  -- the interior ceiling, first person only (lib/Ceiling.lua): drawn with
  -- the terrain so the depth buffer settles walls-vs-lid before any card
  -- or grass fight; a VR frame runs this per eye like everything else here
  pcall(Ceiling.draw, state, atlasFor)

  -- grass tufts and particles (lib/Flora.lua): after the terrain so
  -- blades sit on ground that already exists
  pcall(Flora.draw, state, atlasFor)]]

-- The jump lives in the first-person rig: one term added to the eye's
-- height expression, and the require that reaches it.
local FP_REQ_ANCHOR = 'local Voxel3D = V.require("Voxel3D")'
local FP_REQ_ADD = FP_REQ_ANCHOR .. '\nlocal Jump = V.require("Jump")'
local FP_EYE_ANCHOR = "(me.gh or 0) + (me.lift or 0) + FirstPerson.EYE_HEIGHT"
local FP_EYE_ADD = FP_EYE_ANCHOR .. " + Jump.eyeOffset(me)"
-- the walk's lateral sway: added to the head's X and Z
local FP_SWAYX_ANCHOR = "head = { me.px + 8,"
local FP_SWAYX_ADD = "head = { me.px + 8 + Jump.swayX(me),"
local FP_SWAYZ_ANCHOR = "             me.py + 8 }"
local FP_SWAYZ_ADD = "             me.py + 8 + Jump.swayZ(me) }"

local ROW_ANCHOR = [[local SETTINGS = {
  { VoxelGrid.setting, "One-pixel wireframe along every voxel edge." },]]
local ROW_ADD = ROW_ANCHOR .. [[

  { Ceiling.setting,
    "A ceiling over every interior, in first person only. Rooms and caves "
    .. "close overhead at wall height instead of opening onto the void, "
    .. "and the walls you could see over become walls you cannot. The "
    .. "diorama rungs are untouched -- a dollhouse wants its roof off." },]]

return function(mod)
  mod.options:define({
    -- Removal is deliberate and opt-IN.  This used to be an ON/OFF
    -- "CEILING PATCH" row, which meant any stored false -- a manager
    -- rewrite, a stale value, a stray click -- silently uninstalled
    -- everything.  Patching is now the default action and cannot be
    -- switched off by accident; taking it out takes a decision.
    { key = "remove", label = "REMOVE PATCH", type = "toggle", default = false },
    { key = "ceiling", label = "CEILING", type = "toggle", default = true },
    { key = "headroom", label = "HEADROOM", type = "choice", default = "AIRY",
      choices = { { "AIRY", "AIRY" }, { "MID", "MID" }, { "SNUG", "SNUG" } } },
    { key = "cutaway", label = "SIMS CUTAWAY", type = "toggle", default = true },
    { key = "shadows", label = "CONTACT SHADOW", type = "toggle",
      default = true },
    { key = "rails", label = "RAIL AND SKIRTING", type = "toggle",
      default = true },
    { key = "spill", label = "DOORWAY LIGHT", type = "toggle",
      default = true },
    { key = "fittings", label = "CEILING LAMPS", type = "toggle",
      default = true },
    { key = "rock", label = "CAVE ROCK", type = "toggle", default = true },
    { key = "backs", label = "BUILDING BACKS", type = "toggle",
      default = true },
    { key = "apron", label = "WORLD APRON", type = "toggle",
      default = true },
    { key = "talltrees", label = "TALL TREES", type = "toggle",
      default = true },
    { key = "peaks", label = "MOUNTAIN PEAKS", type = "toggle",
      default = true },
    { key = "fastchunks", label = "FAST CHUNKS", type = "toggle",
      default = true },
    { key = "headbob", label = "HEAD BOB", type = "toggle",
      default = false },
    { key = "jumpkey", label = "JUMP KEY", type = "choice",
      default = "space",
      choices = { { "SPACE", "space" }, { "J", "j" },
                  { "L-CTRL", "lctrl" }, { "OFF", "off" } } },
    { key = "jumppad", label = "PAD BUTTON", type = "choice",
      default = "y",
      choices = { { "Y", "y" }, { "X", "x" }, { "OFF", "off" } } },
    { key = "pools", label = "CAVE POOLS", type = "toggle", default = true },
    { key = "sconces", label = "CAVE TORCHES", type = "toggle",
      default = true },
    { key = "bats", label = "BATS", type = "toggle", default = true },
    -- What a boomed-out third-person camera sees overhead, independent
    -- of what the diorama rungs get: nothing at all, the cutaway, or the
    -- sealed room as in first person.
    { key = "third", label = "3RD CEILING", type = "choice",
      default = "CUTAWAY",
      choices = { { "NONE", "NONE" }, { "CUTAWAY", "CUTAWAY" },
                  { "FULL", "FULL" } } },
    { key = "backdrop", label = "HORIZON", type = "toggle", default = true },
    -- Extra panoramas are ordinary files in this mod's folder --
    -- backdrop2.png, backdrop3.png, backdrop4.png -- and appear here as
    -- ALT 1..3.  A missing file falls back to the shipped one rather
    -- than leaving the sky empty.
    { key = "horizonart", label = "HORIZON ART", type = "choice",
      default = "VALLEY",
      choices = { { "KANTO", "KANTO" }, { "FUJI", "FUJI" },
                  { "VALLEY", "VALLEY" }, { "CITY", "CITY" } } },
    { key = "grass", label = "GRASS HEIGHT", type = "choice",
      default = "SUBTLE",
      choices = { { "OFF", "OFF" }, { "SUBTLE", "SUBTLE" },
                  { "WILD", "WILD" } } },
    { key = "particles", label = "PARTICLES", type = "toggle", default = true },
    { key = "rain", label = "RAIN", type = "choice", default = "SOMETIMES",
      choices = { { "OFF", "OFF" }, { "SOMETIMES", "SOMETIMES" },
                  { "ALWAYS", "ALWAYS" } } },
    { key = "umbrellas", label = "NPC UMBRELLAS", type = "toggle",
      default = true },
    { key = "puddles", label = "PUDDLES", type = "toggle", default = true },
    -- Flashing light is a photosensitivity risk. The storm's rain and
    -- thunderheads remain with this off; only the bolts and the screen
    -- brightening go.
    { key = "lightning", label = "LIGHTNING", type = "toggle",
      default = true },
    { key = "lights", label = "LAMPLIGHT", type = "toggle", default = true },
    { key = "shafts", label = "SUN SHAFTS", type = "toggle", default = true },
    { key = "canopy", label = "FOREST CANOPY", type = "toggle", default = true },
    { key = "vines", label = "HANGING VINES", type = "toggle", default = true },
    { key = "fog", label = "LAVENDER FOG", type = "toggle", default = true },
    { key = "doorstep", label = "DOORWAY STEP", type = "toggle", default = true },
    { key = "clouds", label = "CLOUDS", type = "toggle", default = true },
    { key = "stars", label = "NIGHT SKY", type = "toggle", default = true },
    { key = "birds", label = "BIRDS", type = "toggle", default = true },
    { key = "aircraft", label = "AIRCRAFT", type = "toggle", default = true },
    { key = "rainbows", label = "RAINBOWS", type = "toggle", default = true },
    { key = "insects", label = "INSECTS", type = "toggle", default = true },
    { key = "groundflock", label = "GROUND FLOCK", type = "toggle",
      default = true },
    { key = "wind", label = "WIND", type = "choice", default = "BREEZE",
      choices = { { "OFF", "OFF" }, { "BREEZE", "BREEZE" },
                  { "GUSTY", "GUSTY" } } },
    { key = "jump", label = "JUMP FEEL", type = "choice", default = "SUBTLE",
      choices = { { "OFF", "OFF" }, { "SUBTLE", "SUBTLE" }, { "BIG", "BIG" } } },
    { key = "debug", label = "DEBUG HUD", type = "toggle", default = false },
  })

  -- Live configuration for the Ceiling module running inside Dramatic
  -- Shape: it reads this through mod.find("ds_fp_ceiling").exports each
  -- frame, so every knob here takes effect without a restart.
  local HEADROOM = { AIRY = 32, MID = 24, SNUG = 16 }
  -- Published on the shared Lua state: Dramatic Shape's namespace has no
  -- mod-lookup, so this global IS the channel between the two mods.
  local function readConfig()
    local function opt(k, fb)
      local ok, v = pcall(function() return mod.options:get(k) end)
      if ok and v ~= nil then return v end
      return fb
    end
    return {
      ceiling = opt("ceiling", true) ~= false,
      headroom = HEADROOM[opt("headroom", "AIRY")] or 32,
      cutaway = opt("cutaway", true) ~= false,
      shadows = opt("shadows", true) ~= false,
      rails = opt("rails", true) ~= false,
      spill = opt("spill", true) ~= false,
      fittings = opt("fittings", true) ~= false,
      rock = opt("rock", true) ~= false,
      backs = opt("backs", true) ~= false,
      apron = opt("apron", true) ~= false,
      talltrees = opt("talltrees", true) ~= false,
      peaks = opt("peaks", true) ~= false,
      fastchunks = opt("fastchunks", true) ~= false,
      headbob = opt("headbob", false) == true,
      pools = opt("pools", true) ~= false,
      sconces = opt("sconces", true) ~= false,
      bats = opt("bats", true) ~= false,
      third = opt("third", "CUTAWAY"),
      backdrop = opt("backdrop", true) ~= false,
      horizonart = opt("horizonart", "KANTO"),
      jump = opt("jump", "SUBTLE"),
      grass = opt("grass", "SUBTLE"),
      particles = opt("particles", true) ~= false,
      rain = opt("rain", "SOMETIMES"),
      umbrellas = opt("umbrellas", true) ~= false,
      puddles = opt("puddles", true) ~= false,
      lightning = opt("lightning", true) ~= false,
      lights = opt("lights", true) ~= false,
      shafts = opt("shafts", true) ~= false,
      canopy = opt("canopy", true) ~= false,
      vines = opt("vines", true) ~= false,
      vines = opt("vines", true) ~= false,
      fog = opt("fog", true) ~= false,
      doorstep = opt("doorstep", true) ~= false,
      clouds = opt("clouds", true) ~= false,
      stars = opt("stars", true) ~= false,
      birds = opt("birds", true) ~= false,
      aircraft = opt("aircraft", true) ~= false,
      rainbows = opt("rainbows", true) ~= false,
      insects = opt("insects", true) ~= false,
      groundflock = opt("groundflock", true) ~= false,
      wind = opt("wind", "BREEZE"),
    }
  end
  _G.__ds_ceiling_config = readConfig
  mod.exports.config = readConfig

  local fs = love and love.filesystem
  if not fs then return end
  -- Windows builds show no console, so "say" keeps every line for the
  -- on-screen panel and the boot log as well as printing it
  local report = {}
  -- Did Dramatic Shape already load this session?  Its patched modules
  -- publish a status the moment they load, so the presence of one means
  -- we are too late to be picked up and a restart really is needed.  With
  -- the load order right (this mod's priority is below Dramatic Shape's,
  -- and it declares no dependency edge to it) this is false on a normal
  -- boot and the patch takes effect immediately.
  local tooLate = rawget(_G, "__ds_ceiling_status") ~= nil
  local function laterNote()
    return tooLate and " Restart the game once to load it."
                    or " Active from this boot."
  end

  -- A one-line census of every registered render pipeline: its level, and
  -- whether the engine still considers it eligible to run.
  local function pipelineReport()
    local ok, out = pcall(function()
      local Pipelines = require("src.render.Pipelines")
      local bits = {}
      for _, entry in ipairs(Pipelines.list() or {}) do
        local id = entry.id
        local lvl = Pipelines.level and Pipelines.level(id) or -1
        local elig = Pipelines.eligible and Pipelines.eligible(id)
        -- level above zero but not eligible means the engine has either
        -- gated it (available() said no) or RETIRED it after a throw
        local mark = elig and "ok" or (lvl > 0 and "DEAD?" or "off")
        bits[#bits + 1] = ("%s=%s"):format(id, mark)
      end
      return table.concat(bits, " ")
    end)
    return (ok and out ~= "" and out) or "no pipelines visible"
  end

  -- Which panorama the player asked for. This lived only in the
  -- already-patched branch, so a fresh install always got KANTO no
  -- matter what the option said.
  local ART = { KANTO = "backdrop.png", FUJI = "backdrop2.png",
                VALLEY = "backdrop3.png", CITY = "backdrop4.png" }
  local function chosenArt(base, read)
    local okA, choice = pcall(function()
      return mod.options:get("horizonart")
    end)
    local want = ART[(okA and choice) or "VALLEY"] or "backdrop3.png"
    if not read(base .. "/lib/" .. want) then want = "backdrop.png" end
    return base .. "/lib/" .. want
  end

  local function say(msg)
    report[#report + 1] = msg
    print("[ds_fp_ceiling] " .. msg)
  end

  local function read(path)
    local ok, data = pcall(fs.read, path)
    if ok and type(data) == "string" then return data end
    return nil
  end
  -- LOVE will not create intermediate directories, and the save
  -- directory starts empty: when Dramatic Shape lives in the GAME folder,
  -- "mods/DRAMATIC_SHAPE/lib" exists there but not in the save directory
  -- we shadow it from, so every write failed with "filesystem refused".
  -- Build the parent chain first, exactly as the engine's own CacheFs does.
  local function ensureDir(path)
    local parts, acc = {}, nil
    for seg in path:gmatch("[^/]+") do parts[#parts + 1] = seg end
    table.remove(parts)                     -- drop the filename
    for _, seg in ipairs(parts) do
      acc = acc and (acc .. "/" .. seg) or seg
      pcall(fs.createDirectory, acc)
    end
  end

  local function write(path, data)
    ensureDir(path)
    local ok, done = pcall(fs.write, path, data)
    if not (ok and done) then
      -- one retry after a directory pass: a first-run race on some
      -- platforms creates the folder just after the first attempt
      ensureDir(path)
      ok, done = pcall(fs.write, path, data)
    end
    return ok and done
  end
  local function remove(path) pcall(fs.remove, path) end

  -- Every file this mod writes into Dramatic Shape's folder is recorded
  -- here as it is written, and removal walks the LEDGER rather than a
  -- hardcoded list -- so it restores exactly what was done, including
  -- files added by other versions of this mod.
  local LEDGER = "ds_fp_ceiling_written.txt"
  local function recordWrite(path)
    local cur = read(LEDGER) or ""
    if not cur:find(path, 1, true) then
      write(LEDGER, cur .. path .. "\n")
    end
  end
  local function writeTracked(path, content)
    local ok = write(path, content)
    if ok then recordWrite(path) end
    return ok
  end


  local function inSave(path)
    local ok, real = pcall(fs.getRealDirectory, path)
    if not ok or not real then return false end
    local okS, save = pcall(fs.getSaveDirectory)
    return okS and real == save
  end

  -- splice `add` over the FIRST plain-text occurrence of `anchor`
  local function splice(src, anchor, add)
    local s, e = src:find(anchor, 1, true)
    if not s then return nil end
    return src:sub(1, s - 1) .. add .. src:sub(e + 1)
  end

  -- ------- reading engine sources: normalise line endings first.
  -- absol89's 1.7.6 mixes LF with Windows-pasted CRLF regions -- one of
  -- them exactly around the mesher's stamp expansion -- and an anchored
  -- find written with \n silently misses a line that ends \r\n.
  local function readSrc(p)
    local s2 = read(p)
    if s2 then s2 = s2:gsub("\r\n", "\n") end
    return s2
  end

  -- ------- find Dramatic Shape and its version
  local function findDS()
    local ok, names = pcall(fs.getDirectoryItems, "mods")
    if not ok or not names then return nil end
    for _, name in ipairs(names) do
      local manifest = read("mods/" .. name .. "/manifest.json")
      if manifest then
        for _, id in ipairs(DS_IDS) do
          if manifest:find('"id"%s*:%s*"' .. id .. '"') then
            local version = manifest:match('"version"%s*:%s*"([^"]+)"')
                            or "?"
            return "mods/" .. name, version
          end
        end
      end
    end
    return nil
  end

  -- ------- apply the patch to an unpatched Dramatic Shape
  -- Splice our draws around the terrain draw WITHOUT depending on the
  -- five lines that happen to surround it.  Matching that whole block
  -- was brittle: Dramatic Shape 1.63 reworded it and the patch refused
  -- outright.  All we actually need is the one line that draws the
  -- terrain -- everything of ours goes immediately before or after it.
  local function spliceScene(vs)
    -- exact block first: it keeps the tidy comment placement on builds we
    -- already know
    local exact = splice(vs, SCENE_ANCHOR, SCENE_ADD)
    if exact then return exact, "block" end

    -- otherwise find the terrain draw itself, whatever its arguments are
    local line = vs:match("[^\n]-Voxel3D%.draw%(%s*terrain[^\n]*")
    if not line then return nil end
    local before = "  -- the distant horizon and sky (lib/Backdrop.lua,"
      .. " lib/SkyLayer.lua):\n"
      .. "  -- before the terrain, depth writes off, so every real surface"
      .. " draws over them\n"
      .. "  pcall(Backdrop.draw, state)\n"
      .. "  pcall(SkyLayer.draw, state)\n\n"
    local after = "\n\n  -- interiors, then ground detail (lib/Ceiling.lua,"
      .. " lib/Flora.lua)\n"
      .. "  pcall(Ceiling.draw, state, atlasFor)\n"
      .. "  pcall(Flora.draw, state, atlasFor)"
    local s2, e2 = vs:find(line, 1, true)
    if not s2 then return nil end
    return vs:sub(1, s2 - 1) .. before .. line .. after .. vs:sub(e2 + 1),
           "terrain line"
  end

  -- ------- TALL TREES: two one-line splices, applied on EVERY boot.
  -- 1.43.0 ran this only inside the fresh apply() -- an install that was
  -- already patched took the "module updated" branch instead, so the
  -- splice never landed and the feature did nothing. Idempotent: each
  -- file is checked for its own marker before anything is written.
  local function spliceTallTrees(base)
      do
        local stPath = base .. "/lib/Structures.lua"
        local st = readSrc(stPath)
        -- UPGRADE an older edition of this same splice: 1.43.x injected
        -- a lift with no publish, and its marker made the idempotence
        -- check say "already done" -- so 1.45's registry stayed empty
        -- and every support vanished while the lifts lived on. A prior
        -- injected block is stripped back to the stock line first; the
        -- current one then applies as if fresh.
        if st and st:find("__ds_tree_lift", 1, true)
           and not st:find("__ds_round_key", 1, true) then
          -- the TOMBSTONE strips first: its block contains no `return`,
          -- so the lift pattern (which requires one) would overrun it
          -- and eat everything through the next site
          local stripped = st:gsub(
            ",\n%s+%-%- ds_fp_ceilings __ds_round_tomb.-end%)%(%) }",
            " }", 1)
          stripped = stripped:gsub(
            ",\n%s+%-%- ds_fp_ceilings.-return.-end%)%(%) }", " }", 1)
          if stripped ~= st and stripped:find("{ quads = tpl.quads,"
               .. " mx = cx %* 16 %+ 8, mz = cy %* 16 %+ 8 }") then
            st = stripped
            write(stPath, st)
          end
        end
        local stOld = "          S.roundStamps[#S.roundStamps + 1] =\n"
                      .. "            { quads = tpl.quads, mx = cx * 16 + 8,"
                      .. " mz = cy * 16 + 8 }"
        if st and st:find(stOld, 1, true) and not st:find("__ds_tree_lift") then
          local stNew = "          S.roundStamps[#S.roundStamps + 1] =\n"
          .. "            { quads = tpl.quads, mx = cx * 16 + 8,"
          .. " mz = cy * 16 + 8,\n"
          .. "              -- ds_fp_ceilings: trees stand on trunks; the\n"
          .. "              -- stamped cell is published so the companion\n"
          .. "              -- builds supports under REAL stamps only\n"
          .. "              lift = (function() local _c ="
          .. " rawget(_G, \"__ds_ceiling_config\")\n"
          .. "                _c = _c and _c()\n"
          .. "                if not (_c and _c.talltrees and s.class =="
          .. " \"cylinder\") then return 0 end\n"
          .. "                local _h = (cx * 73856093 + cy * 19349663)"
          .. " % 3\n"
          .. "                local _l = 8 + _h * 6\n"
          .. "                -- __ds_round_key: the engine REUSES one map\n"
          .. "                -- object across transitions, so entries are\n"
          .. "                -- keyed by the map's stable id string\n"
          .. "                local _r = rawget(_G, \"__ds_round_cells\")\n"
          .. "                local _k = map.id or (map.def and map.def.id)"
          .. " or tostring(map)\n"
          .. "                if _r then _r[_k] = _r[_k] or {}\n"
          .. "                  _r[_k][cx .. \"|\" .. cy] = _l end\n"
          .. "                _G.__ds_tree_lift = true\n"
          .. "                return _l end)() }"
        writeTracked(stPath, (st:gsub(stOld:gsub("%p", "%%%1"), function()
            return stNew
          end, 1)))
        end
        -- THE TOMBSTONE. Chunks that first mesh a 2x2 tree straddling
        -- their border take the SINGLE-cell path -- stamped, published,
        -- lifted -- and a later, fuller remesh forms the grouped big
        -- tree for those same cells, drawn grounded, singles never
        -- recreated. The registry never forgot, so supports stood
        -- beside the big trees with nothing above them. When the group
        -- site claims a 2x2, its four member cells are now DELETED from
        -- the registry. (The `_t` field evaluates the deletion and
        -- vanishes: a function call's nil result adds no field.)
        local st2 = readSrc(stPath)
        local tombOld = "              { quads = tpl.quads, mx = cx * 16"
                        .. " + 16, mz = cy * 16 + 16,\n"
                        .. "                r = 16 }"
        if st2 and st2:find(tombOld, 1, true)
           and not st2:find("__ds_round_tomb") then
          local tombNew = "              { quads = tpl.quads, mx = cx * 16"
            .. " + 16, mz = cy * 16 + 16,\n"
            .. "                r = 16,\n"
            .. "                -- ds_fp_ceilings __ds_round_tomb: a group\n"
            .. "                -- supersedes its four member cells\n"
            .. "                _t = (function()\n"
            .. "                  local _r = rawget(_G, \"__ds_round_cells\")\n"
            .. "                  local _k = map.id or (map.def and"
            .. " map.def.id) or tostring(map)\n"
            .. "                  if _r and _r[_k] then\n"
            .. "                    for _dy = 0, 1 do for _dx = 0, 1 do\n"
            .. "                      _r[_k][(cx + _dx) .. \"|\" ..\n"
            .. "                              (cy + _dy)] = nil\n"
            .. "                    end end\n"
            .. "                  end\n"
            .. "                end)() }"
          local applied = st2:gsub(tombOld:gsub("%p", "%%%1"),
                                   function() return tombNew end, 1)
          if applied ~= st2 then writeTracked(stPath, applied) end
        end
        local cmPath = base .. "/lib/ChunkMesher.lua"
        local cm = readSrc(cmPath)
        local cmOld = "          s2[2] = c[2]\n"
        -- upgrade an older mesher splice (lift only, no base publish):
        -- strip our line back to stock so the current edition applies
        if cm and cm:find("st.lift", 1, true)
           and not cm:find("__ds_round_base", 1, true) then
          cm = cm:gsub("s2%[2%] = c%[2%] %+ %(st%.lift or 0%)[^\n]*\n",
                       "s2[2] = c[2]\n", 1)
          write(cmPath, cm)
        end
        -- FAST CHUNKS: Dramatic Shape cooks chunk meshes inside a
        -- per-frame budget, and the 5ms idle slice is why geometry
        -- lands right in front of a walking player. With the option on
        -- the idle slice is doubled -- read from the config bridge at
        -- load, so an orphaned install reverts to stock.
        do
          local fcOld = "local IDLE_SLICE = 0.005\n"
          if cm and cm:find(fcOld, 1, true)
             and not cm:find("fastchunks", 1, true) then
            cm = cm:gsub("local IDLE_SLICE = 0%.005\n",
              "local IDLE_SLICE = 0.005 + ((function()\n"
              .. "  local _c = rawget(_G, \"__ds_ceiling_config\")\n"
              .. "  _c = _c and _c()\n"
              .. "  return (_c and _c.fastchunks) and 0.007 or 0\n"
              .. "end)()) -- ds_fp_ceilings fastchunks\n", 1)
            write(cmPath, cm)
          end
        end
        if cm and cm:find(cmOld, 1, true)
           and not cm:find("st.lift", 1, true) then
          local inPlaceCm = inSave(cmPath)
          if inPlaceCm and not read(cmPath .. ".pre-ceiling") then
            write(cmPath .. ".pre-ceiling", cm)
          end
          writeTracked(cmPath, (cm:gsub(
            "          s2%[2%] = c%[2%]\n",
            "          s2[2] = c[2] + (st.lift or 0)"
            .. " -- ds_fp_ceilings __ds_round_base\n"
            .. "          if st.lift and st.lift > 0 then\n"
            .. "            local _rb = rawget(_G, \"__ds_round_base\")\n"
            .. "            if _rb then\n"
            .. "              local _bk = st.mx .. \"|\" .. st.mz\n"
            .. "              if not _rb[_bk] or c[2] < _rb[_bk] then\n"
            .. "                _rb[_bk] = c[2]\n"
            .. "              end\n"
            .. "            end\n"
            .. "          end\n", 1)))
        end
      end

  end

  local function apply(base, ver, vs)
    local anchor = firstAnchor(vs, REQ_ANCHORS)
    if not anchor then
      say("this Dramatic Shape build has none of the require anchors this "
          .. "patch knows; nothing was changed.")
      return
    end
    local reqAdd = anchor .. '\nlocal Ceiling = V.require("Ceiling")'
                          .. '\nlocal Backdrop = V.require("Backdrop")'
                          .. '\nlocal SkyLayer = V.require("SkyLayer")'
                          .. '\nlocal Flora = V.require("Flora")'
    local vsPatched = splice(vs, anchor, reqAdd)
    local how = nil
    if vsPatched then vsPatched, how = spliceScene(vsPatched) end
    if not vsPatched then
      say(("Dramatic Shape %s draws its terrain in a way this patch does ")
          :format(ver) .. "not recognise; nothing was changed. Please "
          .. "report the version -- it needs a small update here.")
      return
    end
    if how ~= "block" then
      say(("Dramatic Shape %s is newer than this patch was built against; ")
          :format(ver) .. "spliced on the terrain draw itself, which should "
          .. "be fine. Report anything odd.")
    end
    local payload = mod:read("payload_ceiling.lua")
    if not payload then
      say("payload_ceiling.lua is missing -- reinstall this mod.")
      return
    end
    local backdrop = mod:read("payload_backdrop.lua")
    local artwork = mod:read("backdrop.png")
    local vsPath = base .. "/lib/VoxelScene.lua"
    local mainPath = base .. "/main.lua"
    local inPlace = inSave(base .. "/manifest.json")
    if inPlace then
      -- the originals are about to be replaced where they stand; keep them
      local pre = vsPath .. ".pre-ceiling"
      if not read(pre) then write(pre, vs) end
    end
    if not (writeTracked(base .. "/lib/Ceiling.lua", payload)
            and write(vsPath, vsPatched)) then
      say("could not write the patch: the save folder refused. Check that "
          .. "the game can write to its save directory (antivirus, a "
          .. "read-only drive, or running from a protected folder are the "
          .. "usual causes); nothing was changed.")
      return
    end
    -- the horizon: module plus painting, both optional -- a failure here
    -- costs the backdrop, never the ceiling
    -- the jump: module plus the rig splice, both optional
    local jump = mod:read("payload_jump.lua")
    local fpPath = base .. "/lib/FirstPerson.lua"
    local fpSrc = readSrc(fpPath)
    if jump and fpSrc and not fpSrc:find("Jump.eyeOffset", 1, true) then
      local fp2 = splice(fpSrc, FP_REQ_ANCHOR, FP_REQ_ADD)
      fp2 = fp2 and splice(fp2, FP_EYE_ANCHOR, FP_EYE_ADD)
      -- sway is optional: if these anchors ever move, the bob still works
      local fpS = fp2 and splice(fp2, FP_SWAYX_ANCHOR, FP_SWAYX_ADD)
      fpS = fpS and splice(fpS, FP_SWAYZ_ANCHOR, FP_SWAYZ_ADD)
      fp2 = fpS or fp2
      if fp2 then
        if inPlace then
          local pre = fpPath .. ".pre-ceiling"
          if not read(pre) then write(pre, fpSrc) end
        end
        if writeTracked(base .. "/lib/Jump.lua", jump) then write(fpPath, fp2) end
      else
        say("jump anchors not found; ledge hops keep their stock arc.")
      end
    end
    local sky = mod:read("payload_sky.lua")
    spliceTallTrees(base)
    if sky then writeTracked(base .. "/lib/SkyLayer.lua", sky) end
    local flora = mod:read("payload_flora.lua")
    if flora then writeTracked(base .. "/lib/Flora.lua", flora) end
    if backdrop then writeTracked(base .. "/lib/Backdrop.lua", backdrop) end
    if artwork then writeTracked(base .. "/lib/backdrop.png", artwork) end
    for _, extra in ipairs({ "backdrop2.png", "backdrop3.png",
                             "backdrop4.png", "posters.png",
                             "posters-pokecenter.png",
                             "posters-pokemart.png" }) do
      local blob = mod:read(extra)
      if blob then writeTracked(base.. "/lib/" .. extra, blob) end
    end
    _G.__ds_backdrop_path = chosenArt(base, read)
    _G.__ds_posters_dir = base .. "/lib/"
    -- the options row is a nicety: without it the ceiling is simply ON
    local mainSrc = read(mainPath)
    local mainAnchor = firstAnchor(mainSrc, REQ_ANCHORS)
    local mainPatched = mainSrc and mainAnchor
      and splice(mainSrc, mainAnchor,
                 mainAnchor .. '\nlocal Ceiling = V.require("Ceiling")')
    mainPatched = mainPatched and splice(mainPatched, ROW_ANCHOR, ROW_ADD)
    if mainPatched then
      if inPlace then
        local pre = mainPath .. ".pre-ceiling"
        if not read(pre) then write(pre, mainSrc) end
      end
      write(mainPath, mainPatched)
    else
      say("options row anchor not found; ceiling applied without the row "
          .. "(it defaults to ON).")
    end
    write(STATE_FILE, ver)
    say(("ceiling patch applied to Dramatic Shape %s."):format(ver)
        .. laterNote())
  end

  -- ------- back the patch out
  local function unpatch(base)
    -- the ledger first: everything we ever wrote, exactly
    local led = read(LEDGER)
    if led then
      for path in led:gmatch("[^\n]+") do
        local pre = path .. ".pre-ceiling"
        local orig = read(pre)
        if orig then
          write(path, orig)
          remove(pre)
        elseif inSave(path) then
          remove(path)
        end
      end
      remove(LEDGER)
    end
    local vsPath = base .. "/lib/VoxelScene.lua"
    local mainPath = base .. "/main.lua"
    local ceilPath = base .. "/lib/Ceiling.lua"
    local inPlace = inSave(base .. "/manifest.json")
    if not inPlace then
      -- shadow install: our save-directory copies ARE the patch
      for _, p in ipairs({ vsPath, mainPath, ceilPath,
                           base .. "/lib/FirstPerson.lua",
                           base .. "/lib/Jump.lua",
                           base .. "/lib/Backdrop.lua",
                           base .. "/lib/SkyLayer.lua",
                           base .. "/lib/Flora.lua",
                           base .. "/lib/backdrop.png" }) do
        if inSave(p) then remove(p) end
      end
      remove(STATE_FILE)
      say("ceiling patch removed (shadow copies cleared)." .. laterNote())
      return
    end
    local preVs = read(vsPath .. ".pre-ceiling")
    if preVs and not preVs:find(MARK, 1, true) then
      write(vsPath, preVs)
      local preMain = read(mainPath .. ".pre-ceiling")
      if preMain then write(mainPath, preMain) end
      local fpPre = read(base .. "/lib/FirstPerson.lua.pre-ceiling")
      if fpPre then
        writeTracked(base .. "/lib/FirstPerson.lua", fpPre)
        remove(base .. "/lib/FirstPerson.lua.pre-ceiling")
      end
      remove(base .. "/lib/Jump.lua")
      remove(vsPath .. ".pre-ceiling")
      remove(mainPath .. ".pre-ceiling")
      remove(ceilPath)
      remove(STATE_FILE)
      say("ceiling patch removed (originals restored)." .. laterNote())
    else
      say("no clean backup to restore; reinstall Dramatic Shape to remove "
          .. "the patch.")
    end
  end

  -- ------- decide, once, at load
  local function manage(depth)
    local base, ver = findDS()
    _G.__ds_patch_base = base

    -- TESTED VERSIONS ONLY. Splicing into an untested Dramatic Shape is
    -- how you break someone's game from inside a mod they trusted; on an
    -- unknown or newer version this now patches NOTHING, keeps whatever
    -- was already restored, and explains itself in the log.
    -- (1.3.0 is absol89's fork, which numbers itself independently)
    local TESTED = { ["1.3.0"] = true, ["1.5.4"] = true, ["1.5.5"] = true,
                     ["1.6.0"] = true, ["1.6.1"] = true, ["1.6.2"] = true,
                     ["1.7.0"] = true,
                     -- absol89's fork, the mainline since the deletion
                     ["1.7.6"] = true }
    if base and ver and not TESTED[ver] then
      say(("Dramatic Shape %s is a version this patch has not been "
           .. "tested against. NOT patching -- everything is left "
           .. "stock. An update of Kanto in First Person will follow.")
          :format(ver))
      unpatch(base)
      return
    end

    -- 1.6.2 DECLARES A CONFLICT with this mod, at the Dramatic Shape
    -- author's request. Respect it: if the manifest names us, leave
    -- everything stock and bow out. Fighting a conflict flag from inside
    -- the other mod's folder is not a relationship, it is an infestation.
    local dsManifest = base and read(base .. "/manifest.json")
    -- Matched on the OLD id deliberately. This mod's own id is
    -- `ds_fp_ceilings` now, which the launcher would no longer match
    -- against Dramatic Shape's `"conflicts": ["ds_fp_ceiling"]` -- so
    -- without this the rename would quietly become a way round a flag
    -- its author meant. The substring catches either spelling.
    if dsManifest and dsManifest:find("ds_fp_ceiling", 1, true) then
      say("Dramatic Shape has declared a conflict with this mod. "
          .. "Respecting it: nothing has been patched, and any earlier "
          .. "patch has been removed. See the release notes.")
      unpatch(base)
      return
    end
    if not base then
      say("Dramatic Shape is not installed; nothing to do.")
      return
    end
    local vsPath = base .. "/lib/VoxelScene.lua"
    local vs = readSrc(vsPath)
    if not vs then
      say("could not read " .. vsPath .. "; nothing changed.")
      return
    end
    local patched = vs:find(MARK, 1, true) ~= nil
    -- only an explicit true removes; nil, false or a missing schema all
    -- mean "keep the patch"
    local okRm, rm = pcall(function() return mod.options:get("remove") end)
    local wantOff = (okRm and rm == true)
    local wantOn = not wantOff
    local stateVer = read(STATE_FILE)

    if patched and wantOff then
      unpatch(base)
    elseif patched and stateVer and stateVer ~= ver
           and not inSave(base .. "/manifest.json") and inSave(vsPath) then
      -- Dramatic Shape updated underneath our shadow copies: the shadows
      -- still carry the OLD patched files.  Clear them and patch the new
      -- version fresh (once -- no loops on a refusal).
      say(("Dramatic Shape updated (%s -> %s); refreshing the patch...")
          :format(stateVer, ver))
      for _, p in ipairs({ vsPath, base .. "/main.lua",
                           base .. "/lib/Ceiling.lua" }) do
        if inSave(p) then remove(p) end
      end
      remove(STATE_FILE)
      if (depth or 0) < 1 then manage(1) end
    elseif patched then
      if stateVer ~= ver then write(STATE_FILE, ver) end
      -- The jump arrived after earlier patches shipped: splice the rig
      -- in place if it has not been done, idempotently.
      local jumpSrc = mod:read("payload_jump.lua")
      local fpPath2 = base .. "/lib/FirstPerson.lua"
      local fpNow = readSrc(fpPath2)
      if jumpSrc and fpNow then
        if read(base .. "/lib/Jump.lua") ~= jumpSrc then
          writeTracked(base .. "/lib/Jump.lua", jumpSrc)
        end
        if not fpNow:find("Jump.eyeOffset", 1, true) then
          local fp2 = splice(fpNow, FP_REQ_ANCHOR, FP_REQ_ADD)
          fp2 = fp2 and splice(fp2, FP_EYE_ANCHOR, FP_EYE_ADD)
          local fpS = fp2 and splice(fp2, FP_SWAYX_ANCHOR, FP_SWAYX_ADD)
          fpS = fpS and splice(fpS, FP_SWAYZ_ANCHOR, FP_SWAYZ_ADD)
          fp2 = fpS or fp2
          if fp2 and write(fpPath2, fp2) then
            fpNow = fp2
            say("jump spliced into the first-person rig." .. laterNote())
          end
        end
        -- the walk sway arrived after the hop: add it to a rig that has
        -- the eye term but not the lateral ones
        if fpNow:find("Jump.eyeOffset", 1, true)
           and not fpNow:find("Jump.swayX", 1, true) then
          local fpS = splice(fpNow, FP_SWAYX_ANCHOR, FP_SWAYX_ADD)
          fpS = fpS and splice(fpS, FP_SWAYZ_ANCHOR, FP_SWAYZ_ADD)
          if fpS and write(fpPath2, fpS) then
            say("walk sway spliced into the rig.")
          end
        end
      end

      -- Flora arrived after earlier patches: module plus two lines.
      local floraSrc = mod:read("payload_flora.lua")
      if floraSrc then
        if read(base .. "/lib/Flora.lua") ~= floraSrc then
          writeTracked(base .. "/lib/Flora.lua", floraSrc)
        end
        if not vs:find("Flora.draw", 1, true) then
          local vs4 = vs
          local rq = 'local SkyLayer = V.require("SkyLayer")'
          if vs4:find(rq, 1, true) then
            local s, e = vs4:find(rq, 1, true)
            vs4 = vs4:sub(1, e) .. '\nlocal Flora = V.require("Flora")'
                  .. vs4:sub(e + 1)
          end
          local cd = "pcall(Ceiling.draw, state, atlasFor)"
          if vs4:find(cd, 1, true) then
            local s2, e2 = vs4:find(cd, 1, true)
            vs4 = vs4:sub(1, e2)
                  .. "\n\n  -- grass tufts and particles (lib/Flora.lua)"
                  .. "\n  pcall(Flora.draw, state, atlasFor)"
                  .. vs4:sub(e2 + 1)
          end
          if vs4 ~= vs and write(vsPath, vs4) then
            vs = vs4
            say("flora spliced in." .. laterNote())
          end
        end
      end

      -- The sky layer arrived after earlier patches: add its module and
      -- its two lines to an existing scene, idempotently.
      local skySrc = mod:read("payload_sky.lua")
      if skySrc then
        if read(base .. "/lib/SkyLayer.lua") ~= skySrc then
          writeTracked(base .. "/lib/SkyLayer.lua", skySrc)
        end
        if not vs:find("SkyLayer.draw", 1, true) then
          local vs3 = vs
          local bdrq = 'local Backdrop = V.require("Backdrop")'
          if vs3:find(bdrq, 1, true) then
            local s, e = vs3:find(bdrq, 1, true)
            vs3 = vs3:sub(1, e) .. '\nlocal SkyLayer = V.require("SkyLayer")'
                  .. vs3:sub(e + 1)
          end
          local bdc = "pcall(Backdrop.draw, state)"
          if vs3:find(bdc, 1, true) then
            local s2, e2 = vs3:find(bdc, 1, true)
            vs3 = vs3:sub(1, e2)
                  .. "\n\n  -- clouds and birds (lib/SkyLayer.lua)"
                  .. "\n  pcall(SkyLayer.draw, state)"
                  .. vs3:sub(e2 + 1)
          end
          if vs3 ~= vs and write(vsPath, vs3) then
            vs = vs3
            say("sky layer spliced in." .. laterNote())
          end
        end
      end

      -- The horizon arrived after the first patch shipped, so an install
      -- patched by an older companion has the ceiling lines and none of
      -- the backdrop's.  Add them in place, idempotently.
      if not vs:find("Backdrop.draw", 1, true) then
        local vs2 = vs
        local rq = 'local Ceiling = V.require("Ceiling")'
        if vs2:find(rq, 1, true) and not vs2:find('V.require("Backdrop")', 1, true) then
          local s, e = vs2:find(rq, 1, true)
          vs2 = vs2:sub(1, e) .. '\nlocal Backdrop = V.require("Backdrop")'
                .. vs2:sub(e + 1)
        end
        local terr = "Voxel3D.draw(terrain, atlasFor(state.map), nil)"
        if vs2:find(terr, 1, true) then
          local s2 = vs2:find(terr, 1, true)
          vs2 = vs2:sub(1, s2 - 1)
            .. "-- the distant horizon (lib/Backdrop.lua): before the "
            .. "terrain,\n  -- depth writes off, so real surfaces always "
            .. "draw over it\n  pcall(Backdrop.draw, state)\n\n  "
            .. vs2:sub(s2)
        end
        if vs2 ~= vs and write(vsPath, vs2) then
          vs = vs2
          say("horizon spliced into an existing patch." .. laterNote())
        end
      end

      -- v3 hands the ceiling the terrain atlas: an older splice calls
      -- Ceiling.draw without it, so upgrade the call in place
      local OLD_CALL = "pcall(Ceiling.draw, state)"
      local NEW_CALL = "pcall(Ceiling.draw, state, atlasFor)"
      if vs:find(OLD_CALL, 1, true) then
        local s, e = vs:find(OLD_CALL, 1, true)
        local upgraded = vs:sub(1, s - 1) .. NEW_CALL .. vs:sub(e + 1)
        if write(vsPath, upgraded) then
          say("scene splice upgraded to pass the terrain atlas.")
        end
      end
      -- splices are in; is the shipped Ceiling module current?  A newer
      -- payload replaces lib/Ceiling.lua alone -- the anchored splices in
      -- VoxelScene/main are version-independent and stay as they are.
      local mine = mod:read("payload_ceiling.lua") or ""
      local myV = tonumber(mine:match("payload%-version:%s*(%d+)")) or 0
      local theirs = read(base .. "/lib/Ceiling.lua") or ""
      local theirV = tonumber(theirs:match("payload%-version:%s*(%d+)")) or 1
      -- keep the horizon module and its painting in step as well
      local bd = mod:read("payload_backdrop.lua")
      if bd and read(base .. "/lib/Backdrop.lua") ~= bd then
        writeTracked(base .. "/lib/Backdrop.lua", bd)
        say("horizon module refreshed.")
      end
      if not read(base .. "/lib/backdrop.png") then
        local art = mod:read("backdrop.png")
        if art then writeTracked(base .. "/lib/backdrop.png", art) end
      end
      -- extra panoramas and the poster sheet, refreshed whenever they
      -- differ so dropping new art in and rebooting is enough
      for _, extra in ipairs({ "backdrop2.png", "backdrop3.png",
                               "backdrop4.png", "posters.png",
                               "posters-pokecenter.png",
                               "posters-pokemart.png" }) do
        local blob = mod:read(extra)
        if blob and read(base .. "/lib/" .. extra) ~= blob then
          writeTracked(base.. "/lib/" .. extra, blob)
        end
      end
      _G.__ds_backdrop_path = chosenArt(base, read)
      _G.__ds_posters_dir = base .. "/lib/"
      if myV > theirV then
        if writeTracked(base .. "/lib/Ceiling.lua", mine) then
          say(("ceiling module updated v%d -> v%d (Dramatic Shape %s.")
              :format(theirV, myV, ver) .. ")" .. laterNote())
        else
          say("ceiling module update failed to write.")
        end
      else
        say("ceiling patch active (Dramatic Shape " .. ver .. ").")
      end
      spliceTallTrees(base)
    elseif wantOn then
      apply(base, ver, vs)
    else
      say("REMOVE PATCH is on; leaving Dramatic Shape unpatched. "
          .. "Turn it off to reinstall the ceiling and horizon.")
    end
  end

  local ok, err = pcall(manage)
  if not ok then say("unexpected error: " .. tostring(err)) end

  -- the boot log: everything said above, readable from the save folder
  -- (the same folder your save files live in): ds_fp_ceiling_log.txt
  pcall(fs.write, "ds_fp_ceiling_log.txt",
        os.date("!%Y-%m-%d %H:%M UTC") .. "\n"
        .. table.concat(report, "\n") .. "\n")

  -- The on-screen panel, through the engine's render.hud hook: drawn over
  -- every finished frame while DEBUG HUD is ON, so nothing about this
  -- mod's behaviour is ever invisible again.  Line one is what the
  -- patcher did at boot; line two is what the Ceiling module inside
  -- Dramatic Shape decided THIS frame (via a shared global), or the fact
  -- that it never loaded, which is its own diagnosis.
  -- the JUMP BUTTON (Ledge Leap 1.0.1, incorporated -- see
  -- jump_button.lua). pcall-guarded: if the engine lacks any of the
  -- documented surfaces it uses, the button quietly does not exist and
  -- the render patch is unaffected.
  pcall(function()
    local src = mod:read("jump_button.lua")
    local chunk = assert(load(src, "@jump_button.lua"))
    chunk()(mod)
  end)

  mod.hooks:wrap("render.hud", function(next, game, viewport)
    next(game, viewport)
    -- HORIZON ART, re-read each frame. It was resolved once at boot, so
    -- picking a different panorama did nothing until a restart.
    pcall(function()
      local base = rawget(_G, "__ds_patch_base")
      if base then _G.__ds_backdrop_path = chosenArt(base, read) end
    end)
    -- off unless deliberately switched on: the panel is a diagnostic,
    -- not part of the view
    local okOpt, on = pcall(function() return mod.options:get("debug") end)
    if not (okOpt and on == true) then return end
    pcall(function()
      local lines = {
        "CEIL: " .. (report[#report] or "no status"),
        "LIVE: " .. (_G.__ds_ceiling_status
                     or "Ceiling module not loaded this session"
                     .. " -- check the mod manager for errors"),
        "HRZN: " .. (_G.__ds_backdrop_status or "Backdrop not loaded"),
        "SKY:  " .. (_G.__ds_sky_status or "Sky layer not loaded"),
        "FLOR: " .. (_G.__ds_flora_status or "Flora not loaded"),
        -- Other mods' pipelines, and whether the engine has retired any.
        -- A pipeline is disabled for the WHOLE SESSION the moment one of
        -- its stages throws, and Wilds of Kanto runs its spawning and AI
        -- from a present stage -- so "registered but not eligible" is the
        -- difference between "switched off" and "died and stayed dead".
        "PIPE: " .. pipelineReport(),
      }
      local x = (viewport and viewport.gameX or 0) + 8
      local y = (viewport and viewport.gameY or 0) + 8
      local w = 0
      local font = love.graphics.getFont()
      for _, l in ipairs(lines) do
        w = math.max(w, font and font:getWidth(l) or #l * 8)
      end
      love.graphics.setColor(0, 0, 0, 0.7)
      love.graphics.rectangle("fill", x - 4, y - 4, w + 8, #lines * 16 + 8)
      love.graphics.setColor(1, 1, 0.3, 1)
      for i, l in ipairs(lines) do
        love.graphics.print(l, x, y + (i - 1) * 16)
      end
      love.graphics.setColor(1, 1, 1, 1)
    end)
  end)
end
