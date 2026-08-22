return function(T)
  local Config = assert(loadfile(T.root .. "/src/config/Config.lua"))()

  local function makeReader(values, explicit, counts)
    values, explicit, counts = values or {}, explicit or {}, counts or {}
    return function(key)
      counts[key] = (counts[key] or 0) + 1
      return values[key], explicit[key]
    end, counts
  end

  local function diagnostics()
    local sink = { entries = {} }
    function sink:emit(level, code, message, fields)
      self.entries[#self.entries + 1] = {
        level = level, code = code, message = message, fields = fields,
      }
    end
    return sink
  end

  local function hasDiagnostic(sink, code, key)
    for _, entry in ipairs(sink.entries) do
      if entry.code == code and (key == nil or entry.fields.key == key) then return true end
    end
    return false
  end

  local function storage(records)
    local service = { records = records or {}, reads = 0, writes = 0 }
    function service:read(key)
      self.reads = self.reads + 1
      return self.records[key]
    end
    function service:write(key, value)
      self.writes = self.writes + 1
      self.records[key] = value
      return true
    end
    return service
  end

  T.test("config validates its injected interfaces", function()
    T.raises(function() Config.new() end, "read%(key%)")
    T.raises(function() Config.new({ read = function() end, storage = true }) end,
      "storage must be a table")
    T.raises(function()
      Config.new({ read = function() end, storage = { read = true } })
    end, "storage.read")
  end)

  T.test("option schema is unique and retires unsafe legacy rows", function()
    local rows, seen, vines = Config.optionSchema(), {}, 0
    for _, row in ipairs(rows) do
      T.falsy(seen[row.key], "duplicate option key: " .. row.key)
      seen[row.key] = true
      if row.key == "vines" then vines = vines + 1 end
    end
    T.equal(vines, 1)
    T.falsy(seen.shadows)
    T.falsy(seen.fastchunks)
    T.falsy(seen.remove)
    T.truthy(seen.contact_shadows)
    T.truthy(seen.object_shadows)
    T.truthy(seen.ledge_leap)
    local defaults = {}
    for _, row in ipairs(rows) do defaults[row.key] = row.default end
    T.equal(defaults.quality, "AUTO")
    T.equal(defaults.object_shadows, true)
    T.equal(defaults.ledge_leap, false)
  end)

  T.test("pinned 1.60 evidence accounts for all 53 unique release keys", function()
    local evidence = assert(loadfile(
      T.root .. "/tests/fixtures/kfp_1_60_options.lua"))()
    T.equal(#evidence.rows, evidence.source.rowCount)
    T.equal(#evidence.source.mainLuaSha256, 64)

    local counts, unique = {}, 0
    for _, key in ipairs(evidence.rows) do counts[key] = (counts[key] or 0) + 1 end
    for _ in pairs(counts) do unique = unique + 1 end
    T.equal(unique, evidence.source.uniqueCount)
    T.equal(counts.shadows, 2)
    T.equal(counts.vines, 1)

    local accounted = {}
    for _, row in ipairs(Config.optionSchema()) do accounted[row.key] = true end
    for _, key in ipairs(Config.legacyKeys()) do accounted[key] = true end
    for key in pairs(counts) do T.truthy(accounted[key], key) end
  end)

  T.test("available options are visible and unavailable alpha options stay hidden", function()
    local ledge, rows = nil, {}
    for _, row in ipairs(Config.optionSchema()) do
      rows[row.key] = row
      if row.key == "ledge_leap" then ledge = row end
    end
    T.truthy(ledge)
    T.equal(ledge.group, "GAMEPLAY")
    T.falsy(ledge.default)
    T.truthy(ledge.label:find("GAMEPLAY", 1, true))
    T.truthy(ledge.description:find("movement", 1, true))
    for _, key in ipairs({
      "birds", "groundflock", "lights",
      "ledge_leap", "jumpkey", "jumppad", "debug",
    }) do
      T.equal(rows[key].visible_if.key, "__kfp_alpha_feature_ready", key)
      T.equal(rows[key].visible_if.equals, true, key)
    end
    T.falsy(rows.third.visible_if)
    T.falsy(rows.ceildetail.visible_if)
  end)

  T.test("schema and policy accessors return defensive copies", function()
    local first = Config.optionSchema()
    first[1].key = "damaged"
    first[1].choices[1][1] = "damaged"
    local second = Config.optionSchema()
    T.equal(second[1].key, "quality")
    T.equal(second[1].choices[1][1], "AUTO")

    local policies = Config.qualityPolicies()
    policies.HIGH.cacheBytes = 1
    T.equal(Config.qualityPolicies().HIGH.cacheBytes, 128 * 1024 * 1024)
  end)

  T.test("quality policies match the locked render budgets", function()
    local policies = Config.qualityPolicies()
    T.equal(policies.HIGH.buildBudgetMs, 2.0)
    T.equal(policies.HIGH.drawCallTarget, 48)
    T.equal(policies.HIGH.panoramaWidth, 4096)
    T.equal(policies.BALANCED.cacheBytes, 64 * 1024 * 1024)
    T.equal(policies.BALANCED.density, 0.6)
    T.equal(policies.LOW.buildBudgetMs, 0.5)
    T.equal(policies.LOW.drawCallTarget, 20)
    T.equal(policies.LOW.panoramaWidth, 1024)
    T.truthy(policies.AUTO.adaptive)
    T.equal(policies.AUTO.buildBudgetMs, nil)
  end)

  T.test("config and renderer expose the same hard quality policies", function()
    local Quality = assert(loadfile(T.root .. "/src/render/Quality.lua"))()
    local configPolicies, renderPolicies = Config.qualityPolicies(), Quality.all()
    for _, tier in ipairs({ "HIGH", "BALANCED", "LOW" }) do
      T.deepEqual(configPolicies[tier], renderPolicies[tier], tier)
    end
  end)

  T.test("default snapshot is stable and reads only on refresh", function()
    local read, counts = makeReader()
    local config = Config.new({ read = read })
    local snapshot = config:snapshot()
    T.equal(snapshot.schema_version, 2)
    T.equal(snapshot.generation, 1)
    T.equal(snapshot.quality, "AUTO")
    T.equal(snapshot.quality_policy.name, "AUTO")
    T.equal(snapshot.headroom, "AIRY")
    T.equal(snapshot.headroom_pixels, 32)
    T.equal(snapshot.depth_blur_passes, 0)
    T.equal(snapshot.ledge_leap, false)
    T.equal(snapshot.object_shadows, true)
    T.equal(snapshot.values.backdrop, true)
    T.equal(snapshot.values.shadows, snapshot.contact_shadows)
    T.equal(snapshot.values.object_shadows, snapshot.object_shadows)
    T.equal(snapshot.values.grasssteps, snapshot.grass_steps)
    T.equal(snapshot.values.footsteps, snapshot.footsteps)
    T.equal(snapshot.values.doorsounds, snapshot.door_sound)
    T.equal(snapshot, config:snapshot())
    for key, count in pairs(counts) do T.equal(count, 1, key .. " was read more than once") end

    local same, invalidated, fields = config:refresh("poll")
    T.equal(same, snapshot)
    T.equal(same.generation, 1)
    T.equal(next(invalidated), nil)
    T.equal(#fields, 0)
  end)

  T.test("initial snapshot invalidates every declared group", function()
    local config = Config.new({ read = makeReader({}) })
    local snapshot, invalidated = config:refresh("initial")
    local expected = { "quality", "geometry", "lighting", "sky", "weather",
      "flora", "particles", "audio", "camera", "gameplay", "streaming",
      "diagnostics" }
    for _, group in ipairs(expected) do
      T.truthy(invalidated[group], group)
      T.equal(snapshot.group_generation[group], 1, group)
    end
  end)

  T.test("legacy shadows migrate only to Contact Shadows", function()
    local read = makeReader({ shadows = false, contact_shadows = true,
      object_shadows = true })
    local snapshot = Config.new({ read = read }):snapshot()
    T.equal(snapshot.contact_shadows, false)
    T.equal(snapshot.object_shadows, true)

    local explicitRead = makeReader({ shadows = false, contact_shadows = true },
      { contact_shadows = true })
    local explicit = Config.new({ read = explicitRead }):snapshot()
    T.equal(explicit.contact_shadows, true)
  end)

  T.test("fastchunks maps to locked quality values", function()
    T.equal(Config.new({ read = makeReader({ fastchunks = false }) }):snapshot().quality,
      "LOW")
    T.equal(Config.new({ read = makeReader({ fastchunks = true }) }):snapshot().quality,
      "AUTO")
    T.equal(Config.new({ read = makeReader({}) }):snapshot().quality, "AUTO")
    local read = makeReader({ quality = "HIGH", fastchunks = false }, { quality = true })
    T.equal(Config.new({ read = read }):snapshot().quality, "HIGH")
  end)

  T.test("array-shaped Vine data normalizes defensively", function()
    local diag = diagnostics()
    local snapshot = Config.new({
      read = makeReader({ vines = { true, false, false } }), diagnostics = diag,
    }):snapshot()
    T.equal(snapshot.hanging_vines, false)
    T.truthy(hasDiagnostic(diag, "CONFIG.VINES_LIST_NORMALIZED"))
  end)

  T.test("retired remove and failed feature options are inert", function()
    local diag = diagnostics()
    local raw = { remove = true, dark = true, backs = true, mountains = true,
      windowlight = true, sunbloom = true }
    local snapshot = Config.new({ read = makeReader(raw), diagnostics = diag }):snapshot()
    T.equal(snapshot.remove, nil)
    T.equal(snapshot.dark, nil)
    for key in pairs(raw) do
      T.truthy(hasDiagnostic(diag, "CONFIG.RETIRED_OPTION_IGNORED", key), key)
    end
    T.equal(snapshot.ceiling, true)
  end)

  T.test("legacy jump bindings remain but never enable Ledge Leap", function()
    local snapshot = Config.new({
      read = makeReader({ jumpkey = "j", jumppad = "x" }),
    }):snapshot()
    T.equal(snapshot.ledge_key, "j")
    T.equal(snapshot.ledge_pad, "x")
    T.equal(snapshot.ledge_leap, false)

    local diag = diagnostics()
    local enabled = Config.new({
      read = makeReader({ ledge_leap = true }, { ledge_leap = true }),
      diagnostics = diag,
    }):snapshot()
    T.equal(enabled.ledge_leap, false)
    T.truthy(hasDiagnostic(diag, "CONFIG.LEDGE_LEAP_UNAVAILABLE"))
  end)

  T.test("all supported v1 option keys map to clear snapshot fields", function()
    local raw = {
      ceiling = false, headroom = "SNUG", cutaway = false, third = "FULL",
      rails = false, spill = false, fittings = false, ceildetail = false,
      windows = false, rock = false, pools = false, sconces = false, bats = false,
      apron = false, talltrees = false, peaks = false, bouldertrees = true,
      headbob = true, backdrop = false, horizonart = "CITY", clouds = false,
      stars = false, birds = false, groundflock = false, aircraft = false,
      rainbows = false, rain = "ALWAYS", lightning = false, umbrellas = false,
      puddles = false, lights = false, fog = false, canopy = false, vines = false,
      shafts = false, grass = "WILD", wind = "GUSTY", insects = false,
      particles = false, ambience = "HIGH", grasssfx = false, stepsfx = false,
      doorsfx = false, fpfov = "ULTRA", dof = "3", jump = "BIG",
      doorstep = false, jumpkey = "lctrl", jumppad = "off", debug = true,
    }
    local expected = {
      ceiling = false, headroom = "SNUG", cutaway = false,
      third_person_ceiling = "FULL", rails = false, doorway_light = false,
      ceiling_lamps = false, ceiling_detail = false, windows = false,
      cave_rock = false, cave_pools = false, cave_torches = false, bats = false,
      world_apron = false, tall_trees = false, mountain_peaks = false,
      boulder_trees = true, head_bob = true, horizon = false, horizon_art = "CITY",
      clouds = false, night_sky = false, birds = false, ground_flock = false,
      aircraft = false, rainbows = false, rain = "ALWAYS", lightning = false,
      npc_umbrellas = false, puddles = false, lamplight = false,
      lavender_fog = false, forest_canopy = false, hanging_vines = false,
      sun_shafts = false, grass_height = "WILD", wind = "GUSTY", insects = false,
      particles = false, ambient_sound = "HIGH", grass_steps = false,
      footsteps = false, door_sound = false, first_person_fov = "ULTRA",
      depth_blur = "3", jump_feel = "BIG", doorway_step = false,
      ledge_key = "lctrl", ledge_pad = "off", debug_hud = true,
    }
    local snapshot = Config.new({ read = makeReader(raw) }):snapshot()
    for field, value in pairs(expected) do T.equal(snapshot[field], value, field) end
    T.equal(snapshot.headroom_pixels, 16)
    T.equal(snapshot.depth_blur_passes, 3)
  end)

  T.test("legacy scalar forms normalize without leaking invalid values", function()
    local diag = diagnostics()
    local snapshot = Config.new({
      read = makeReader({ ceiling = "off", headroom = 24, ambience = false,
        grass = true, jump = false, quality = "medium", dof = "99" }),
      diagnostics = diag,
    }):snapshot()
    T.equal(snapshot.ceiling, false)
    T.equal(snapshot.headroom, "MID")
    T.equal(snapshot.headroom_pixels, 24)
    T.equal(snapshot.ambient_sound, "OFF")
    T.equal(snapshot.grass_height, "SUBTLE")
    T.equal(snapshot.jump_feel, "OFF")
    T.equal(snapshot.quality, "BALANCED")
    T.equal(snapshot.depth_blur, "OFF")
    T.truthy(hasDiagnostic(diag, "CONFIG.INVALID_OPTION", "dof"))
  end)

  T.test("storage makes ambiguous legacy migration stable across boots", function()
    local records = storage()
    local values = { shadows = false, contact_shadows = true, fastchunks = false,
      quality = "AUTO" }
    local first = Config.new({ read = makeReader(values), storage = records })
    T.equal(first:snapshot().contact_shadows, false)
    T.equal(first:snapshot().quality, "LOW")
    T.equal(records.writes, 1)
    first:refresh("unchanged")
    T.equal(records.writes, 1)

    local second = Config.new({ read = makeReader(values), storage = records })
    T.equal(second:snapshot().contact_shadows, false)
    T.equal(second:snapshot().quality, "LOW")
    T.equal(records.writes, 1, "unchanged stored config must not rewrite at boot")

    local changed = second:refresh("option_changed:contact_shadows")
    T.equal(changed.contact_shadows, true)
    T.equal(changed.generation, 2)
    T.equal(records.writes, 2)
  end)

  T.test("feature changes increment only their invalidation groups", function()
    local values = {}
    local config = Config.new({ read = makeReader(values) })
    local first = config:snapshot()
    values.birds = false
    local second, invalidated, fields = config:refresh("option_changed:birds")
    T.equal(second.generation, 2)
    T.equal(fields[1], "birds")
    T.truthy(invalidated.sky)
    T.truthy(invalidated.particles)
    T.equal(invalidated.geometry, nil)
    T.equal(second.group_generation.sky, 2)
    T.equal(second.group_generation.particles, 2)
    T.equal(second.group_generation.geometry, 1)
    T.equal(first.birds, true, "old snapshots must stay stable")
    T.deepEqual(config:groupsChangedSince(first), { sky = true, particles = true })
  end)

  T.test("quality changes invalidate every quality-controlled group", function()
    local values = { quality = "LOW" }
    local config = Config.new({ read = makeReader(values) })
    config:snapshot()
    values.quality = "HIGH"
    local snapshot, invalidated = config:refresh("option_changed:quality")
    T.equal(snapshot.quality, "HIGH")
    for _, group in ipairs({ "quality", "geometry", "lighting", "sky", "weather",
      "flora", "particles", "audio", "camera", "streaming" }) do
      T.truthy(invalidated[group], group)
      T.equal(snapshot.group_generation[group], 2, group)
    end
    T.equal(invalidated.gameplay, nil)
    T.equal(invalidated.diagnostics, nil)
  end)

  T.test("read and storage faults fail closed with diagnostics", function()
    local diag = diagnostics()
    local badStorage = {}
    function badStorage:read() error("read boom") end
    function badStorage:write() error("write boom") end
    local config = Config.new({
      read = function(key)
        if key == "ceiling" then error("option boom") end
        return nil
      end,
      storage = badStorage,
      diagnostics = diag,
    })
    local snapshot = config:snapshot()
    T.equal(snapshot.ceiling, true)
    T.truthy(hasDiagnostic(diag, "CONFIG.STORAGE_READ_FAILED"))
    T.truthy(hasDiagnostic(diag, "CONFIG.STORAGE_WRITE_FAILED"))
    T.truthy(hasDiagnostic(diag, "CONFIG.OPTION_READ_FAILED", "ceiling"))
  end)

  T.test("a transient storage write failure retries on the next refresh", function()
    local service = { attempts = 0, record = nil }
    function service:read() return self.record end
    function service:write(_, record)
      self.attempts = self.attempts + 1
      if self.attempts == 1 then return false, "busy" end
      self.record = record
      return true
    end
    local config = Config.new({ read = makeReader({ shadows = false }), storage = service })
    T.equal(config:snapshot().contact_shadows, false)
    T.equal(service.attempts, 1)
    config:refresh("retry")
    T.equal(service.attempts, 2)
    T.equal(service.record.schema_version, 2)
    config:refresh("settled")
    T.equal(service.attempts, 2)
  end)

  T.test("invalid live input keeps the last safe stored option", function()
    local values, diag, records = { ceiling = false }, diagnostics(), storage()
    local config = Config.new({
      read = makeReader(values), diagnostics = diag, storage = records,
    })
    local first = config:snapshot()
    values.ceiling = "not-a-toggle"
    local second = config:refresh("option_changed:ceiling")
    T.equal(second, first)
    T.equal(second.ceiling, false)
    T.truthy(hasDiagnostic(diag, "CONFIG.INVALID_OPTION", "ceiling"))
  end)

  T.test("invalid stored records are ignored and replaced safely", function()
    local diag, records = diagnostics(), storage({
      [Config.STORAGE_KEY] = { schema_version = 1, values = "bad" },
    })
    local snapshot = Config.new({
      read = makeReader({}), storage = records, diagnostics = diag,
    }):snapshot()
    T.equal(snapshot.quality, "AUTO")
    T.truthy(hasDiagnostic(diag, "CONFIG.STORAGE_RECORD_INVALID"))
    T.equal(records.records[Config.STORAGE_KEY].schema_version, 2)
  end)
end
