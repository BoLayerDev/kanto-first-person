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

local DS_ID = "DRAMATIC_SHAPE"
local STATE_FILE = "ds_fp_ceiling_state"
local MARK = "Ceiling.draw"   -- present in VoxelScene.lua only when patched

-- ------- the splices, anchored on exact 1.5.x text

local REQ_ANCHOR = 'local Water = V.require("Water")'
local REQ_ADD = REQ_ANCHOR .. '\nlocal Ceiling = V.require("Ceiling")'
                          .. '\nlocal Backdrop = V.require("Backdrop")'

local SCENE_ANCHOR = [[  Voxel3D.draw(terrain, atlasFor(state.map), nil)
  for i, nb in ipairs(state.neighbors or {}) do
    Voxel3D.draw(nbMesh[i], atlasFor(nb.map),
                 Mat4.translate(nb.ox, 0, nb.oy))
  end]]
local SCENE_ADD = [[  -- the distant horizon (lib/Backdrop.lua): before the terrain and with
  -- depth writes off, so every real surface draws over the painting
  pcall(Backdrop.draw, state)

]] .. SCENE_ANCHOR .. [[


  -- the interior ceiling, first person only (lib/Ceiling.lua): drawn with
  -- the terrain so the depth buffer settles walls-vs-lid before any card
  -- or grass fight; a VR frame runs this per eye like everything else here
  pcall(Ceiling.draw, state, atlasFor)]]

-- The jump lives in the first-person rig: one term added to the eye's
-- height expression, and the require that reaches it.
local FP_REQ_ANCHOR = 'local Voxel3D = V.require("Voxel3D")'
local FP_REQ_ADD = FP_REQ_ANCHOR .. '\nlocal Jump = V.require("Jump")'
local FP_EYE_ANCHOR = "(me.gh or 0) + (me.lift or 0) + FirstPerson.EYE_HEIGHT"
local FP_EYE_ADD = FP_EYE_ANCHOR .. " + Jump.eyeOffset(me)"

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
    { key = "backdrop", label = "HORIZON", type = "toggle", default = true },
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
      backdrop = opt("backdrop", true) ~= false,
      jump = opt("jump", "SUBTLE"),
    }
  end
  _G.__ds_ceiling_config = readConfig
  mod.exports.config = readConfig

  local fs = love and love.filesystem
  if not fs then return end
  -- Windows builds show no console, so "say" keeps every line for the
  -- on-screen panel and the boot log as well as printing it
  local report = {}
  local function say(msg)
    report[#report + 1] = msg
    print("[ds_fp_ceiling] " .. msg)
  end

  local function read(path)
    local ok, data = pcall(fs.read, path)
    if ok and type(data) == "string" then return data end
    return nil
  end
  local function write(path, data)
    local ok, done = pcall(fs.write, path, data)
    return ok and done
  end
  local function remove(path) pcall(fs.remove, path) end
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

  -- ------- find Dramatic Shape and its version
  local function findDS()
    local ok, names = pcall(fs.getDirectoryItems, "mods")
    if not ok or not names then return nil end
    for _, name in ipairs(names) do
      local manifest = read("mods/" .. name .. "/manifest.json")
      if manifest and manifest:find('"id"%s*:%s*"' .. DS_ID .. '"') then
        local version = manifest:match('"version"%s*:%s*"([^"]+)"') or "?"
        return "mods/" .. name, version
      end
    end
    return nil
  end

  -- ------- apply the patch to an unpatched Dramatic Shape
  local function apply(base, ver, vs)
    local vsPatched = splice(vs, REQ_ANCHOR, REQ_ADD)
    vsPatched = vsPatched and splice(vsPatched, SCENE_ANCHOR, SCENE_ADD)
    if not vsPatched then
      say(("Dramatic Shape %s is not a version this patch recognises; ")
          :format(ver) .. "nothing was changed. Check for a ds_fp_ceiling "
          .. "update.")
      return
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
    if not (write(base .. "/lib/Ceiling.lua", payload)
            and write(vsPath, vsPatched)) then
      say("could not write the patch (filesystem refused); nothing changed.")
      return
    end
    -- the horizon: module plus painting, both optional -- a failure here
    -- costs the backdrop, never the ceiling
    -- the jump: module plus the rig splice, both optional
    local jump = mod:read("payload_jump.lua")
    local fpPath = base .. "/lib/FirstPerson.lua"
    local fpSrc = read(fpPath)
    if jump and fpSrc and not fpSrc:find("Jump.eyeOffset", 1, true) then
      local fp2 = splice(fpSrc, FP_REQ_ANCHOR, FP_REQ_ADD)
      fp2 = fp2 and splice(fp2, FP_EYE_ANCHOR, FP_EYE_ADD)
      if fp2 then
        if inPlace then
          local pre = fpPath .. ".pre-ceiling"
          if not read(pre) then write(pre, fpSrc) end
        end
        if write(base .. "/lib/Jump.lua", jump) then write(fpPath, fp2) end
      else
        say("jump anchors not found; ledge hops keep their stock arc.")
      end
    end
    if backdrop then write(base .. "/lib/Backdrop.lua", backdrop) end
    if artwork then write(base .. "/lib/backdrop.png", artwork) end
    _G.__ds_backdrop_path = base .. "/lib/backdrop.png"
    -- the options row is a nicety: without it the ceiling is simply ON
    local mainSrc = read(mainPath)
    local mainPatched = mainSrc and splice(mainSrc, REQ_ANCHOR, REQ_ADD)
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
    say(("ceiling patch applied to Dramatic Shape %s. If no ceiling ")
        :format(ver) .. "appears indoors in first person, restart the game "
        .. "once.")
  end

  -- ------- back the patch out
  local function unpatch(base)
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
                           base .. "/lib/backdrop.png" }) do
        if inSave(p) then remove(p) end
      end
      remove(STATE_FILE)
      say("ceiling patch removed (shadow copies cleared). Restart the game.")
      return
    end
    local preVs = read(vsPath .. ".pre-ceiling")
    if preVs and not preVs:find(MARK, 1, true) then
      write(vsPath, preVs)
      local preMain = read(mainPath .. ".pre-ceiling")
      if preMain then write(mainPath, preMain) end
      local fpPre = read(base .. "/lib/FirstPerson.lua.pre-ceiling")
      if fpPre then
        write(base .. "/lib/FirstPerson.lua", fpPre)
        remove(base .. "/lib/FirstPerson.lua.pre-ceiling")
      end
      remove(base .. "/lib/Jump.lua")
      remove(vsPath .. ".pre-ceiling")
      remove(mainPath .. ".pre-ceiling")
      remove(ceilPath)
      remove(STATE_FILE)
      say("ceiling patch removed (originals restored). Restart the game.")
    else
      say("no clean backup to restore; reinstall Dramatic Shape to remove "
          .. "the patch.")
    end
  end

  -- ------- decide, once, at load
  local function manage(depth)
    local base, ver = findDS()
    if not base then
      say("Dramatic Shape is not installed; nothing to do.")
      return
    end
    local vsPath = base .. "/lib/VoxelScene.lua"
    local vs = read(vsPath)
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
      local fpNow = read(fpPath2)
      if jumpSrc and fpNow then
        if read(base .. "/lib/Jump.lua") ~= jumpSrc then
          write(base .. "/lib/Jump.lua", jumpSrc)
        end
        if not fpNow:find("Jump.eyeOffset", 1, true) then
          local fp2 = splice(fpNow, FP_REQ_ANCHOR, FP_REQ_ADD)
          fp2 = fp2 and splice(fp2, FP_EYE_ANCHOR, FP_EYE_ADD)
          if fp2 and write(fpPath2, fp2) then
            say("jump spliced into the first-person rig. "
                .. "Restart the game once to feel it.")
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
          say("horizon spliced into an existing patch. "
              .. "Restart the game once to see it.")
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
        write(base .. "/lib/Backdrop.lua", bd)
        say("horizon module refreshed.")
      end
      if not read(base .. "/lib/backdrop.png") then
        local art = mod:read("backdrop.png")
        if art then write(base .. "/lib/backdrop.png", art) end
      end
      _G.__ds_backdrop_path = base .. "/lib/backdrop.png"
      if myV > theirV then
        if write(base .. "/lib/Ceiling.lua", mine) then
          say(("ceiling module updated v%d -> v%d (Dramatic Shape %s). ")
              :format(theirV, myV, ver)
              .. "Restart the game once to load it.")
        else
          say("ceiling module update failed to write.")
        end
      else
        say("ceiling patch active (Dramatic Shape " .. ver .. ").")
      end
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
  mod.hooks:wrap("render.hud", function(next, game, viewport)
    next(game, viewport)
    -- off unless deliberately switched on: the panel is a diagnostic,
    -- not part of the view
    local okOpt, on = pcall(function() return mod.options:get("debug") end)
    if not (okOpt and on == true) then return end
    pcall(function()
      local lines = {
        "CEIL: " .. (report[#report] or "no status"),
        "LIVE: " .. (_G.__ds_ceiling_status
                     or "Ceiling module not loaded this session"
                     .. " -- restart the game once"),
        "HRZN: " .. (_G.__ds_backdrop_status or "Backdrop not loaded"),
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
