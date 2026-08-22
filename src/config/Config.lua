-- Immutable-by-convention option snapshots and KFP 1.x migration.
--
-- This module has no engine dependency. The composition root injects one
-- option reader and, when available, a small persistent storage adapter.

local Config = {}
Config.__index = Config

local SCHEMA_VERSION = 2
local STORAGE_KEY = "config/v2"

local GROUP_ORDER = {
  "quality", "geometry", "lighting", "sky", "weather", "flora",
  "particles", "audio", "camera", "gameplay", "streaming", "diagnostics",
}

local ALL_QUALITY_GROUPS = {
  "quality", "geometry", "lighting", "sky", "weather", "flora",
  "particles", "audio", "camera", "streaming",
}

local MIB = 1024 * 1024
local QUALITY_POLICIES = {
  HIGH = {
    name = "HIGH", buildBudgetMs = 2.0, cacheBytes = 128 * MIB,
    density = 1.0, drawCallTarget = 48, panoramaWidth = 4096,
  },
  BALANCED = {
    name = "BALANCED", buildBudgetMs = 1.0, cacheBytes = 64 * MIB,
    density = 0.6, drawCallTarget = 32, panoramaWidth = 2048,
  },
  LOW = {
    name = "LOW", buildBudgetMs = 0.5, cacheBytes = 32 * MIB,
    density = 0.3, drawCallTarget = 20, panoramaWidth = 1024,
  },
  -- AUTO is a request, not a fourth unbounded tier. The render quality
  -- service resolves it from the host tier and platform, then returns one of
  -- the three hard policies above.
  AUTO = { name = "AUTO", adaptive = true },
}

local function choices(...)
  local values = { ... }
  local out = {}
  for i = 1, #values do out[i] = { values[i], values[i] } end
  return out
end

-- Keys remain stable where v1 did not have a collision. Snapshot fields use
-- clear names, so feature code does not inherit the old abbreviations.
local SPECS = {
  { key = "quality", field = "quality", label = "QUALITY", type = "choice",
    default = "AUTO", choices = choices("AUTO", "HIGH", "BALANCED", "LOW"),
    groups = ALL_QUALITY_GROUPS },

  { key = "ceiling", field = "ceiling", label = "CEILING", type = "toggle",
    default = true, groups = { "geometry" } },
  { key = "headroom", field = "headroom", label = "HEADROOM", type = "choice",
    default = "AIRY", choices = choices("AIRY", "MID", "SNUG"),
    groups = { "geometry" } },
  { key = "cutaway", field = "cutaway", label = "SIMS CUTAWAY", type = "toggle",
    default = true, groups = { "geometry" } },
  { key = "third", field = "third_person_ceiling", label = "3RD CEILING",
    type = "choice", default = "CUTAWAY",
    choices = choices("NONE", "CUTAWAY", "FULL"),
    groups = { "geometry", "camera" } },
  { key = "contact_shadows", field = "contact_shadows",
    label = "CONTACT SHADOWS", type = "toggle", default = true,
    groups = { "geometry", "lighting" } },
  { key = "object_shadows", field = "object_shadows",
    label = "OBJECT SHADOWS", type = "toggle", default = true,
    groups = { "lighting" } },
  { key = "rails", field = "rails", label = "RAIL AND SKIRTING", type = "toggle",
    default = true, groups = { "geometry" } },
  { key = "spill", field = "doorway_light", label = "DOORWAY LIGHT", type = "toggle",
    default = true, groups = { "geometry", "lighting" }, hiddenAlpha = true },
  { key = "fittings", field = "ceiling_lamps", label = "CEILING LAMPS",
    type = "toggle", default = true, groups = { "geometry", "lighting" } },
  { key = "ceildetail", field = "ceiling_detail", label = "CEILING DETAIL",
    type = "toggle", default = true, groups = { "geometry" } },
  { key = "windows", field = "windows", label = "WINDOWS", type = "toggle",
    default = true, groups = { "geometry", "lighting" } },

  { key = "rock", field = "cave_rock", label = "CAVE ROCK", type = "toggle",
    default = true, groups = { "geometry" } },
  { key = "pools", field = "cave_pools", label = "CAVE POOLS", type = "toggle",
    default = true, groups = { "geometry", "lighting" } },
  { key = "sconces", field = "cave_torches", label = "CAVE TORCHES",
    type = "toggle", default = true,
    groups = { "geometry", "lighting", "particles" } },
  { key = "bats", field = "bats", label = "BATS", type = "toggle",
    default = true, groups = { "flora", "particles" } },

  { key = "apron", field = "world_apron", label = "WORLD APRON", type = "toggle",
    default = true, groups = { "geometry", "streaming" } },
  { key = "talltrees", field = "tall_trees", label = "TALL TREES", type = "toggle",
    default = true, groups = { "geometry", "flora" } },
  { key = "peaks", field = "mountain_peaks", label = "MOUNTAIN PEAKS",
    type = "toggle", default = true,
    groups = { "geometry", "streaming" } },
  { key = "bouldertrees", field = "boulder_trees", label = "BOULDER TREES",
    type = "toggle", default = false, groups = { "geometry", "flora" } },

  { key = "headbob", field = "head_bob", label = "HEAD BOB", type = "toggle",
    default = false, groups = { "camera" } },
  { key = "backdrop", field = "horizon", label = "HORIZON", type = "toggle",
    default = true, groups = { "sky" } },
  { key = "horizonart", field = "horizon_art", label = "HORIZON ART",
    type = "choice", default = "VALLEY",
    choices = choices("KANTO", "FUJI", "VALLEY", "CITY"), groups = { "sky" } },
  { key = "clouds", field = "clouds", label = "CLOUDS", type = "toggle",
    default = true, groups = { "sky" } },
  { key = "stars", field = "night_sky", label = "NIGHT SKY", type = "toggle",
    default = true, groups = { "sky" } },
  { key = "birds", field = "birds", label = "BIRDS", type = "toggle",
    default = true, groups = { "sky", "particles" }, hiddenAlpha = true },
  { key = "groundflock", field = "ground_flock", label = "GROUND FLOCK",
    type = "toggle", default = true, groups = { "flora", "particles" },
    hiddenAlpha = true },
  { key = "aircraft", field = "aircraft", label = "AIRCRAFT", type = "toggle",
    default = true, groups = { "sky", "particles" } },
  { key = "rainbows", field = "rainbows", label = "RAINBOWS", type = "toggle",
    default = true, groups = { "sky", "weather" } },

  { key = "rain", field = "rain", label = "RAIN", type = "choice",
    default = "SOMETIMES", choices = choices("OFF", "SOMETIMES", "ALWAYS"),
    groups = { "weather", "particles", "audio" } },
  { key = "lightning", field = "lightning", label = "LIGHTNING", type = "toggle",
    default = true, groups = { "weather", "lighting" }, hiddenAlpha = true },
  { key = "umbrellas", field = "npc_umbrellas", label = "NPC UMBRELLAS",
    type = "toggle", default = true, groups = { "weather", "geometry" } },
  { key = "puddles", field = "puddles", label = "PUDDLES", type = "toggle",
    default = true, groups = { "weather", "geometry" } },
  { key = "lights", field = "lamplight", label = "LAMPLIGHT", type = "toggle",
    default = true, groups = { "lighting" }, hiddenAlpha = true },
  { key = "fog", field = "lavender_fog", label = "LAVENDER FOG", type = "toggle",
    default = true, groups = { "weather", "particles" }, hiddenAlpha = true },

  { key = "canopy", field = "forest_canopy", label = "FOREST CANOPY",
    type = "toggle", default = true, groups = { "geometry", "flora" } },
  { key = "vines", field = "hanging_vines", label = "HANGING VINES",
    type = "toggle", default = true, groups = { "geometry", "flora" } },
  { key = "shafts", field = "sun_shafts", label = "SUN SHAFTS", type = "toggle",
    default = true, groups = { "lighting", "flora" } },
  { key = "grass", field = "grass_height", label = "GRASS HEIGHT", type = "choice",
    default = "SUBTLE", choices = choices("OFF", "SUBTLE", "WILD"),
    groups = { "geometry", "flora" } },
  { key = "wind", field = "wind", label = "WIND", type = "choice",
    default = "BREEZE", choices = choices("OFF", "BREEZE", "GUSTY"),
    groups = { "weather", "flora", "particles" } },
  { key = "insects", field = "insects", label = "INSECTS", type = "toggle",
    default = true, groups = { "flora", "particles" } },
  { key = "particles", field = "particles", label = "PARTICLES", type = "toggle",
    default = true, groups = { "particles" } },

  { key = "ambience", field = "ambient_sound", label = "AMBIENT SOUND",
    type = "choice", default = "MID", choices = choices("OFF", "LOW", "MID", "HIGH"),
    groups = { "audio" } },
  { key = "grasssfx", field = "grass_steps", label = "GRASS STEPS", type = "toggle",
    default = true, groups = { "audio" } },
  { key = "stepsfx", field = "footsteps", label = "FOOTSTEPS", type = "toggle",
    default = true, groups = { "audio" } },
  { key = "doorsfx", field = "door_sound", label = "DOOR SOUND", type = "toggle",
    default = true, groups = { "audio" } },

  { key = "fpfov", field = "first_person_fov", label = "FP FOV", type = "choice",
    default = "NORMAL", choices = choices("NARROW", "NORMAL", "WIDE", "ULTRA"),
    groups = { "camera" } },
  { key = "dof", field = "depth_blur", label = "DEPTH BLUR", type = "choice",
    default = "OFF", choices = choices("OFF", "1", "2", "3"),
    groups = { "camera" }, hiddenAlpha = true },
  { key = "jump", field = "jump_feel", label = "JUMP FEEL", type = "choice",
    default = "SUBTLE", choices = choices("OFF", "SUBTLE", "BIG"),
    groups = { "camera" } },
  { key = "doorstep", field = "doorway_step", label = "DOORWAY STEP",
    type = "toggle", default = true, groups = { "camera" } },

  { key = "ledge_leap", field = "ledge_leap", label = "LEDGE LEAP (GAMEPLAY)",
    type = "toggle", default = false, optionGroup = "GAMEPLAY",
    description = "Gameplay-changing movement is unavailable in this alpha.",
    groups = { "gameplay" }, hiddenAlpha = true },
  { key = "jumpkey", field = "ledge_key", label = "LEDGE KEY", type = "choice",
    default = "space", choices = {
      { "SPACE", "space" }, { "J", "j" }, { "L-CTRL", "lctrl" }, { "OFF", "off" },
    }, optionGroup = "GAMEPLAY", groups = { "gameplay" }, hiddenAlpha = true },
  { key = "jumppad", field = "ledge_pad", label = "LEDGE PAD BUTTON",
    type = "choice", default = "y",
    choices = { { "Y", "y" }, { "X", "x" }, { "OFF", "off" } },
    optionGroup = "GAMEPLAY", groups = { "gameplay" }, hiddenAlpha = true },

  { key = "debug", field = "debug_hud", label = "DEBUG HUD", type = "toggle",
    default = false, groups = { "diagnostics" }, hiddenAlpha = true },
}

local SPEC_BY_FIELD = {}
for i = 1, #SPECS do SPEC_BY_FIELD[SPECS[i].field] = SPECS[i] end

local RETIRED_KEYS = {
  "remove", "ceilingpatch", "ceiling_patch", "dark", "backs", "mountains",
  "windowlight", "window_light", "sunbloom", "sun_bloom", "bloom",
}

local HEADROOM_PIXELS = { AIRY = 32, MID = 24, SNUG = 16 }
local MISSING = {}

local function displayValue(value)
  local text = tostring(value)
  if #text > 96 then return text:sub(1, 93) .. "..." end
  return text
end

local function copyTable(source)
  local out = {}
  if type(source) ~= "table" then return out end
  for key, value in pairs(source) do
    if type(value) == "table" then
      local child = {}
      for childKey, childValue in pairs(value) do
        if type(childValue) == "table" then
          local leaf = {}
          for leafKey, leafValue in pairs(childValue) do leaf[leafKey] = leafValue end
          child[childKey] = leaf
        else
          child[childKey] = childValue
        end
      end
      out[key] = child
    else
      out[key] = value
    end
  end
  return out
end

local function copyPolicy(name)
  return copyTable(QUALITY_POLICIES[name] or QUALITY_POLICIES.AUTO)
end

local function emit(diagnostics, level, code, message, fields)
  if diagnostics == nil then return end
  if type(diagnostics) == "function" then
    pcall(diagnostics, level, code, message, fields)
  elseif type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

local function booleanValue(value)
  if type(value) == "boolean" then return value, true end
  if value == 1 then return true, true end
  if value == 0 then return false, true end
  if type(value) == "string" then
    if #value > 16 then return nil, false end
    local upper = value:upper()
    if upper == "TRUE" or upper == "ON" or upper == "YES" or upper == "1" then
      return true, true
    end
    if upper == "FALSE" or upper == "OFF" or upper == "NO" or upper == "0" then
      return false, true
    end
  end
  return nil, false
end

local function choiceValue(spec, value)
  if spec.field == "headroom" and type(value) == "number" then
    if value == 32 then return "AIRY", true end
    if value == 24 then return "MID", true end
    if value == 16 then return "SNUG", true end
  end
  if (spec.field == "ambient_sound" or spec.field == "grass_height"
      or spec.field == "jump_feel") and type(value) == "boolean" then
    if value == false then return "OFF", true end
    if spec.field == "ambient_sound" then return "MID", true end
    return "SUBTLE", true
  end

  local text = type(value) == "string" and value or tostring(value or "")
  if #text > 64 then return nil, false end
  local upper = text:upper()
  if spec.field == "quality" then
    if upper == "MEDIUM" or upper == "NORMAL" or upper == "DEFAULT" then
      upper = "BALANCED"
    end
  end
  for i = 1, #(spec.choices or {}) do
    local canonical = spec.choices[i][2]
    if text == canonical or upper == tostring(canonical):upper() then
      return canonical, true
    end
  end
  return nil, false
end

local function normalize(spec, value)
  if spec.type == "toggle" then return booleanValue(value) end
  return choiceValue(spec, value)
end

local function optionChangeKey(reason)
  if type(reason) == "table" then
    if reason.kind == "options_changed" or reason.kind == "option_changed" then
      return reason.key
    end
  elseif type(reason) == "string" then
    return reason:match("^options?_changed:(.+)$")
  end
  return nil
end

local function valuesEqual(left, right)
  if left == right then return true end
  if type(left) ~= "table" or type(right) ~= "table" then return false end
  for key, value in pairs(left) do
    if not valuesEqual(value, right[key]) then return false end
  end
  for key in pairs(right) do
    if left[key] == nil then return false end
  end
  return true
end

local function publicSchemaRow(spec)
  local row = {
    key = spec.key, label = spec.label, type = spec.type, default = spec.default,
  }
  if spec.optionGroup then row.group = spec.optionGroup end
  if spec.description then row.description = spec.description end
  if spec.hiddenAlpha then
    -- Gen1recomp retains hidden rows and their stored values. This keeps the
    -- migration contract without presenting controls that have no safe alpha
    -- runtime. No schema row defines this sentinel, so the condition is false.
    row.visible_if = { key = "__kfp_alpha_feature_ready", equals = true }
  end
  if spec.choices then
    row.choices = {}
    for i = 1, #spec.choices do
      row.choices[i] = { spec.choices[i][1], spec.choices[i][2] }
    end
  end
  return row
end

function Config.optionSchema()
  local rows = {}
  for i = 1, #SPECS do rows[i] = publicSchemaRow(SPECS[i]) end
  return rows
end

function Config.qualityPolicies()
  local out = {}
  for _, name in ipairs({ "AUTO", "HIGH", "BALANCED", "LOW" }) do
    out[name] = copyPolicy(name)
  end
  return out
end

function Config.legacyKeys()
  local out = { "shadows", "fastchunks" }
  for i = 1, #RETIRED_KEYS do out[#out + 1] = RETIRED_KEYS[i] end
  return out
end

function Config.new(opts)
  opts = opts or {}
  assert(type(opts.read) == "function", "Config needs a read(key) function")
  if opts.storage ~= nil then
    assert(type(opts.storage) == "table", "Config storage must be a table")
    assert(opts.storage.read == nil or type(opts.storage.read) == "function",
      "Config storage.read must be a function")
    assert(opts.storage.write == nil or type(opts.storage.write) == "function",
      "Config storage.write must be a function")
  end
  return setmetatable({
    read = opts.read,
    storage = opts.storage,
    diagnostics = opts.diagnostics,
    current = nil,
    stored = nil,
    storedLoaded = false,
    storageDirty = false,
    origins = {},
    reported = {},
  }, Config)
end

function Config:_diagnosticOnce(level, code, message, fields, key)
  key = key or code
  if self.reported[key] then return end
  self.reported[key] = true
  emit(self.diagnostics, level, code, message, fields)
end

function Config:_loadStored()
  if self.storedLoaded then return end
  self.storedLoaded = true
  local storage = self.storage
  if not (storage and type(storage.read) == "function") then return end
  local ok, record, readCode = pcall(storage.read, storage, STORAGE_KEY)
  if not ok then
    self:_diagnosticOnce("warn", "CONFIG.STORAGE_READ_FAILED",
      "The option migration record could not be read.", { error = tostring(record) })
    return
  end
  if record == nil then return end
  if type(record) ~= "table" or tonumber(record.schema_version) ~= SCHEMA_VERSION
      or type(record.values) ~= "table" then
    self:_diagnosticOnce("warn", "CONFIG.STORAGE_RECORD_INVALID",
      "The option migration record is invalid and was ignored.",
      { error = tostring(readCode or "invalid record") })
    return
  end
  self.stored = { schema_version = SCHEMA_VERSION, values = {}, origins = {} }
  for field, value in pairs(record.values) do
    if SPEC_BY_FIELD[field] and type(value) ~= "table" then
      self.stored.values[field] = value
    end
  end
  for field, origin in pairs(type(record.origins) == "table" and record.origins or {}) do
    if SPEC_BY_FIELD[field] and type(origin) == "string" then
      if #origin <= 64 and origin:match("^[%l_]+$") then
        self.stored.origins[field] = origin
      end
    end
  end
end

function Config:_persist(values, origins)
  self.stored = {
    schema_version = SCHEMA_VERSION,
    values = copyTable(values),
    origins = copyTable(origins),
  }
  local storage = self.storage
  if not (storage and type(storage.write) == "function") then
    self.storageDirty = false
    return true
  end
  local record = copyTable(self.stored)
  local ok, written, writeCode = pcall(storage.write, storage, STORAGE_KEY, record)
  if not ok or written == false then
    self.storageDirty = true
    self:_diagnosticOnce("warn", "CONFIG.STORAGE_WRITE_FAILED",
      "The option migration record could not be written.",
      { error = tostring(ok and writeCode or written) })
    return false
  end
  self.storageDirty = false
  return true
end

function Config:_reader()
  local cache = {}
  return function(key)
    local cached = cache[key]
    if cached then
      if cached == MISSING then return nil, false, false end
      return cached.value, true, cached.explicit
    end
    local ok, value, present = pcall(self.read, key)
    if not ok then
      cache[key] = MISSING
      self:_diagnosticOnce("warn", "CONFIG.OPTION_READ_FAILED",
        "An option could not be read; its safe default will be used.",
        { key = key, error = tostring(value) }, "read:" .. key)
      return nil, false, false
    end
    if present == false or value == nil then
      cache[key] = MISSING
      return nil, false, false
    end
    cache[key] = { value = value, explicit = present == true }
    return value, true, present == true
  end
end

local function lastDuplicateValue(raw)
  if type(raw) ~= "table" then return raw, false, false end
  local count, last, conflict = 0, nil, false
  for i = 1, #raw do
    if raw[i] ~= nil then
      count = count + 1
      if last ~= nil and raw[i] ~= last then conflict = true end
      last = raw[i]
    end
  end
  if count == 0 then return nil, true, false end
  return last, true, conflict
end

function Config:_initialCandidate(spec, readRaw)
  local raw, present, explicit = readRaw(spec.key)
  local origin = present and "canonical" or "default"

  if spec.field == "quality" and not explicit then
    local fast, fastPresent = readRaw("fastchunks")
    if fastPresent then
      local enabled, valid = booleanValue(fast)
      if valid then
        return enabled and "AUTO" or "LOW", "legacy_fastchunks", true
      end
    end
  elseif spec.field == "contact_shadows" and not explicit then
    local shadows, shadowsPresent = readRaw("shadows")
    if shadowsPresent then
      return shadows, "legacy_shadows", true
    end
  elseif spec.field == "object_shadows" then
    -- The v1.60 rows shared one key. That value cannot identify which row
    -- the user changed, so Object Shadows deliberately use the v2 default.
    if not explicit then return spec.default, "corrected_default", true end
  elseif spec.field == "hanging_vines" and present then
    local value, duplicate, conflict = lastDuplicateValue(raw)
    if duplicate then
      self:_diagnosticOnce("info", "CONFIG.VINES_LIST_NORMALIZED",
        "Array-shaped Vine data was normalized defensively into one option.",
        { conflict = conflict }, "duplicate:vines")
      return value, "legacy_vines_list", true
    end
  elseif spec.field == "ledge_leap" and not explicit
      and (not present or raw == spec.default) then
    -- Jump bindings are preferences. They never imply movement authority.
    return false, "safety_default", true
  end

  if present then return raw, origin, true end
  return spec.default, origin, false
end

function Config:_storedCandidate(spec, readRaw, changedKey)
  local storedValue = self.stored and self.stored.values[spec.field]
  local storedOrigin = self.stored and self.stored.origins[spec.field] or "stored"
  local raw, present, explicit = readRaw(spec.key)
  if not present then
    if storedValue ~= nil then return storedValue, storedOrigin, true end
    return spec.default, "default", false
  end

  local normalized, valid = normalize(spec, raw)
  if not valid then
    self:_diagnosticOnce("warn", "CONFIG.INVALID_OPTION",
      "An invalid option value was ignored; the last safe value was kept.",
        { key = spec.key, value = displayValue(raw), default = displayValue(spec.default) },
      "invalid:" .. spec.key .. ":" .. displayValue(raw))
    if storedValue ~= nil then return storedValue, storedOrigin, true end
    return raw, "invalid", true
  end
  if storedValue == nil then return normalized, "canonical", true end

  local storedNormalized, storedValid = normalize(spec, storedValue)
  if not storedValid then return normalized, "canonical", true end
  if explicit or changedKey == spec.key then return normalized, "canonical", true end
  if normalized == storedNormalized then return storedNormalized, storedOrigin, true end

  -- A legacy-derived value must survive the new row's automatic default.
  -- The options_changed reason (or read's explicit=true second result) makes
  -- an intentional reset to that default unambiguous.
  if storedOrigin:match("^legacy_") and normalized == spec.default then
    return storedNormalized, storedOrigin, true
  end
  return normalized, "canonical", true
end

function Config:_resolveValues(reason)
  self:_loadStored()
  local readRaw = self:_reader()
  local changedKey = optionChangeKey(reason)
  local values, origins = {}, {}
  local migrated = self.stored == nil
  local usedLegacy = false

  for i = 1, #SPECS do
    local spec = SPECS[i]
    local candidate, origin, hadValue
    if self.stored then
      candidate, origin, hadValue = self:_storedCandidate(spec, readRaw, changedKey)
    else
      candidate, origin, hadValue = self:_initialCandidate(spec, readRaw)
      if type(origin) == "string" and origin:match("^legacy_") then usedLegacy = true end
    end
    local normalized, valid = normalize(spec, candidate)
    if not valid then
      normalized = spec.default
      self:_diagnosticOnce("warn", "CONFIG.INVALID_OPTION",
        "An invalid option value was replaced with its safe default.",
        { key = spec.key, value = displayValue(candidate),
          default = displayValue(spec.default) },
        "invalid:" .. spec.key .. ":" .. displayValue(candidate))
      origin = "default"
    elseif not hadValue then
      origin = "default"
    end
    if spec.field == "ledge_leap" then
      if normalized == true then
        self:_diagnosticOnce("info", "CONFIG.LEDGE_LEAP_UNAVAILABLE",
          "Ledge Leap stays off until an atomic public engine API is available.",
          nil, "ledge_leap:unavailable")
      end
      normalized, origin = false, "unavailable_alpha"
    end
    values[spec.field], origins[spec.field] = normalized, origin
  end

  for i = 1, #RETIRED_KEYS do
    local key = RETIRED_KEYS[i]
    local value, present = readRaw(key)
    if present then
      usedLegacy = true
      self:_diagnosticOnce("info", "CONFIG.RETIRED_OPTION_IGNORED",
        "A retired v1 option was ignored. KFP never removes host files.",
        { key = key, value = displayValue(value) }, "retired:" .. key)
    end
  end

  if migrated and usedLegacy then
    self:_diagnosticOnce("info", "CONFIG.LEGACY_MIGRATED",
      "Legacy KFP options were normalized into the v2 configuration.",
      { schema_version = SCHEMA_VERSION })
  end
  return values, origins, migrated
end

local function buildSnapshot(values, generation, groupGeneration)
  local snapshot = {
    schema_version = SCHEMA_VERSION,
    generation = generation,
    group_generation = groupGeneration,
    values = {},
  }
  for key, value in pairs(values) do snapshot[key] = value end
  for i = 1, #SPECS do
    local spec = SPECS[i]
    snapshot.values[spec.key] = values[spec.field]
  end
  -- Feature modules use this stable view while their public names migrate.
  -- `shadows` means Contact Shadows here and never Object Shadows.
  snapshot.values.shadows = values.contact_shadows
  snapshot.values.grasssteps = values.grass_steps
  snapshot.values.footsteps = values.footsteps
  snapshot.values.doorsounds = values.door_sound

  snapshot.headroom_pixels = HEADROOM_PIXELS[snapshot.headroom] or 32
  snapshot.quality_policy = copyPolicy(snapshot.quality)
  local requestedDof = snapshot.depth_blur == "OFF" and 0
    or tonumber(snapshot.depth_blur) or 0
  snapshot.depth_blur_passes = requestedDof
  return snapshot
end

local function allGroupsInvalidated()
  local out = {}
  for i = 1, #GROUP_ORDER do out[GROUP_ORDER[i]] = true end
  return out
end

local function copyGroupGeneration(source)
  local out = {}
  for i = 1, #GROUP_ORDER do
    local group = GROUP_ORDER[i]
    out[group] = source and source[group] or 0
  end
  return out
end

function Config:refresh(reason)
  local values, origins, migrated = self:_resolveValues(reason)
  local old = self.current
  local shouldPersist = migrated
    or self.storageDirty
    or not valuesEqual(self.stored and self.stored.values, values)
    or not valuesEqual(self.stored and self.stored.origins, origins)
  local invalidated = old and {} or allGroupsInvalidated()
  local changedFields = {}

  if old then
    for i = 1, #SPECS do
      local spec = SPECS[i]
      if old[spec.field] ~= values[spec.field] then
        changedFields[#changedFields + 1] = spec.field
        for j = 1, #spec.groups do invalidated[spec.groups[j]] = true end
      end
    end
  else
    for i = 1, #SPECS do changedFields[i] = SPECS[i].field end
  end

  if old and #changedFields == 0 then
    self.origins = origins
    if shouldPersist then self:_persist(values, origins) end
    return old, invalidated, changedFields
  end

  local generation = old and (old.generation + 1) or 1
  local groupGeneration = copyGroupGeneration(old and old.group_generation)
  for group in pairs(invalidated) do
    groupGeneration[group] = groupGeneration[group] + 1
  end
  local snapshot = buildSnapshot(values, generation, groupGeneration)
  self.current = snapshot
  self.origins = origins
  if shouldPersist then self:_persist(values, origins) end
  return snapshot, invalidated, changedFields
end

function Config:snapshot()
  if not self.current then self:refresh("initial") end
  return self.current
end

function Config:groupsChangedSince(previous)
  local current = self:snapshot()
  local out = {}
  if type(previous) ~= "table" or type(previous.group_generation) ~= "table" then
    return allGroupsInvalidated()
  end
  for i = 1, #GROUP_ORDER do
    local group = GROUP_ORDER[i]
    if current.group_generation[group] ~= previous.group_generation[group] then
      out[group] = true
    end
  end
  return out
end

Config.SCHEMA_VERSION = SCHEMA_VERSION
Config.STORAGE_KEY = STORAGE_KEY

return Config
