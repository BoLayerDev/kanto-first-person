return function(T)
  local function load(path) return assert(loadfile(T.root .. "/" .. path))() end

  local API = load("companion/api_v1.lua")
  local CommandBuffer = load("src/render/CommandBuffer.lua")
  local PacketHash = load("src/render/PacketHash.lua")
  local Quality = load("src/render/Quality.lua")
  local Util = load("src/features/Util.lua")
  local WorldSnapshot = load("src/companion/WorldSnapshot.lua")
  local fixture = load("tests/fixtures/synthetic_kfp/cases.lua")

  local featurePaths = {
    "src/features/Interior.lua",
    "src/features/Cave.lua",
    "src/features/WorldGeometry.lua",
    "src/features/Battle.lua",
    "src/features/Atmosphere.lua",
    "src/features/Flora.lua",
    "src/features/Weather.lua",
    "src/features/Wildlife.lua",
  }

  local phaseOrder = CommandBuffer.phases()
  local allowedKinds = {
    mesh = true,
    instances = true,
    billboards = true,
    lights = true,
    postprocess = true,
  }
  local goldenHashes = {
    -- A changed hash requires a deliberate review of the declarative command
    -- diff. These hashes do not represent pixel output.
    indoor = "f4a72cb4",
    cave = "56288537",
    forest = "6f68303c",
    city_lavender = "53a4bc70",
    route_neighbor_edge = "fb85dae6",
    shore = "fb9928b2",
    mountain = "e2bcb2a0",
    day = "2825a5bd",
    night = "7f4231b4",
    rain = "c2b9fc1b",
    storm = "48b41755",
    battle_supported = "3a664439",
    battle_unsupported = "ccbbe2b2",
  }
  local qualityHashes = {
    HIGH = "6f68303c",
    BALANCED = "df3f3170",
    LOW = "593d9419",
  }

  local syntheticTexture = { syntheticOwnedResource = true }
  local assets = {
    image = function(_, path)
      T.truthy(path:match("^assets/legacy/"))
      return syntheticTexture
    end,
  }

  local function compile(case, tier)
    local world, snapshotError = WorldSnapshot.capture(case.world)
    T.truthy(world, case.id .. ": " .. tostring(snapshotError))
    local quality = Quality.policy(tier or "HIGH", "AUTO", "windows")
    local buffer = CommandBuffer.new({
      maxCommands = 4096,
      maxBatchItems = 2048,
      hashCommand = PacketHash.hashCommand,
    })
    local context = {
      world = world,
      config = case.config,
      quality = quality,
      services = { capabilities = case.capabilities, assets = assets },
      checkpoint = function() end,
    }
    for _, path in ipairs(featurePaths) do
      load(path).new({ util = Util }):compile(context, buffer)
    end
    local packet = buffer:seal({
      key = world.key .. "|quality=" .. quality.resolved,
      generation = 1,
    })
    return packet, quality
  end

  local function hasExpected(packet, expected)
    for _, command in ipairs(packet.phases[expected.phase] or {}) do
      if (expected.owner == nil or command.owner == expected.owner)
          and (expected.kind == nil or command.kind == expected.kind)
          and (expected.material == nil or command.material == expected.material)
          and (expected.key == nil or command.key == expected.key) then
        return true
      end
    end
    return false
  end

  local function collectTables(value, out)
    if type(value) ~= "table" or out[value] then return out end
    out[value] = true
    for key, item in pairs(value) do
      collectTables(key, out)
      collectTables(item, out)
    end
    return out
  end

  local function referencesAny(value, targets, active)
    if type(value) ~= "table" then return false end
    if targets[value] then return true end
    active = active or {}
    if active[value] then return false end
    active[value] = true
    for key, item in pairs(value) do
      if referencesAny(key, targets, active) or referencesAny(item, targets, active) then
        active[value] = nil
        return true
      end
    end
    active[value] = nil
    return false
  end

  local function noLocatorStrings(value, active)
    local kind = type(value)
    if kind == "string" then
      T.falsy(value:find("assets/", 1, true), value)
      T.falsy(value:find("\\", 1, true), value)
      T.falsy(value:find("://", 1, true), value)
      T.falsy(value:lower():match("%.png$"), value)
      return
    end
    if kind ~= "table" then return end
    active = active or {}
    if active[value] then return end
    active[value] = true
    for key, item in pairs(value) do
      if key ~= "texture" and key ~= "mesh" and key ~= "resource" and key ~= "model" then
        noLocatorStrings(key, active)
        noLocatorStrings(item, active)
      end
    end
    active[value] = nil
  end

  local function validatePacket(case, packet, quality)
    T.equal(packet.commandCount, packet.drawCalls)
    T.truthy(packet.drawCalls <= quality.drawCallTarget,
      case.id .. " exceeds " .. quality.resolved .. " draw target")
    local borrowed = collectTables(case.world, {})
    collectTables(case.config, borrowed)
    collectTables(case.capabilities, borrowed)
    T.falsy(referencesAny(packet, borrowed), case.id .. " retained a borrowed host table")
    noLocatorStrings(packet)

    for phase, commands in pairs(packet.phases) do
      T.truthy(phaseOrder[phase] ~= nil, "unknown phase " .. tostring(phase))
      for _, command in ipairs(commands) do
        T.equal(command.phase, phase)
        T.truthy(allowedKinds[command.kind], "unknown kind " .. tostring(command.kind))
        T.truthy(type(command.owner) == "string" and command.owner ~= "")
        if command.material ~= nil then
          T.truthy(type(command.material) == "string" and command.material ~= "")
        end
        if command.items ~= nil then
          T.truthy(#command.items > 0)
          T.truthy(#command.items <= 2048, case.id .. " batch exceeds 2048 items")
        end
        if command.kind == "mesh" or command.kind == "instances"
            or command.kind == "billboards" then
          local ok, err = API.validate_draw_command(command, command.kind)
          T.truthy(ok, case.id .. ": " .. tostring(err))
        end
      end
    end

    for _, expected in ipairs(case.expect) do
      T.truthy(hasExpected(packet, expected), case.id .. " missing expected command")
    end
    if case.expectEmptyPhase then
      T.equal(#packet.phases[case.expectEmptyPhase], 0)
    end
  end

  T.test("ROM-free synthetic scenes match reviewed declarative packet goldens", function()
    T.equal(fixture.fixtureKind, "authored-rom-free-synthetic-v1")
    T.equal(#fixture.cases, 13)
    local changed = {}
    for _, case in ipairs(fixture.cases) do
      local packet, quality = compile(case, "HIGH")
      validatePacket(case, packet, quality)
      local hash = PacketHash.hash(packet)
      if hash ~= goldenHashes[case.id] then
        changed[#changed + 1] = case.id .. "=" .. hash
      end
    end
    T.equal(#changed, 0, "packet hash changes: " .. table.concat(changed, ", "))
  end)

  T.test("quality tiers produce bounded and distinct synthetic packets", function()
    local forest
    for _, case in ipairs(fixture.cases) do
      if case.qualitySweep then forest = case end
    end
    T.truthy(forest)

    local hashes, starCounts, changed = {}, {}, {}
    for _, tier in ipairs({ "HIGH", "BALANCED", "LOW" }) do
      local packet, quality = compile(forest, tier)
      validatePacket(forest, packet, quality)
      hashes[tier] = PacketHash.hash(packet)
      for _, command in ipairs(packet.phases.background) do
        if command.material == "sky:stars" then
          starCounts[tier] = command.procedural.count
        end
      end
      if hashes[tier] ~= qualityHashes[tier] then
        changed[#changed + 1] = tier .. "=" .. hashes[tier]
      end
    end
    T.equal(#changed, 0, "quality packet hash changes: " .. table.concat(changed, ", "))
    T.notEqual(hashes.HIGH, hashes.BALANCED)
    T.notEqual(hashes.BALANCED, hashes.LOW)
    T.truthy(starCounts.HIGH > starCounts.BALANCED)
    T.truthy(starCounts.BALANCED > starCounts.LOW)
  end)
end
