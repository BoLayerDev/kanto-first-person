return function(T)
  local function load(path) return assert(loadfile(T.root .. "/" .. path))() end

  local CommandBuffer = load("src/render/CommandBuffer.lua")
  local PacketHash = load("src/render/PacketHash.lua")
  local Util = load("src/features/Util.lua")
  local Weather = load("src/features/Weather.lua")

  -- Frozen local reference for the implementation at parent b964789. This is
  -- intentionally test-local so production code has one Weather path.
  local LegacyWeather = {}
  LegacyWeather.__index = LegacyWeather

  function LegacyWeather.new(deps)
    deps = deps or {}
    if not deps.util then error("Weather needs util", 2) end
    return setmetatable({
      id = "weather", order = 220, critical = false, util = deps.util,
    }, LegacyWeather)
  end

  local function legacyRainEnabled(value, weather)
    value = type(value) == "string" and value:upper()
      or (value and "SOMETIMES" or "OFF")
    if value == "OFF" or value == "NEVER" then return false end
    if value == "ALWAYS" then return true end
    return weather == "rain" or weather == "storm"
  end

  function LegacyWeather:compile(context, buffer)
    local U = self.util
    local world, config, quality = context.world, context.config, context.quality
    if U.hasTag(world, "interior") or U.hasTag(world, "cave") then return end
    local raining = legacyRainEnabled(
      U.option(config, "rain", "SOMETIMES"), world.weather)

    if raining then
      local count = math.max(24, math.floor(130 * quality.density))
      for index = 1, count do
        local unitX = U.unit(world.id, "rain", index, "x")
        local unitZ = U.unit(world.id, "rain", index, "z")
        buffer:addBatchItem("translucent_after_actors", "billboards", "rain", {
          owner = self.id,
          material = "weather:rain",
          sortKey = "weather:rain",
          animated = true,
        }, {
          x = unitX * world.width * world.cellSize,
          y = world.cellSize * (2 + U.unit(world.id, "rain", index, "y") * 4),
          z = unitZ * world.height * world.cellSize,
          seed = U.hash(world.id, "rain", index),
        })
        U.checkpoint(context, index, 48)
      end
    end

    for index, cell in ipairs(world.cells or {}) do
      local x, y, z, size = U.cellPosition(world, cell)
      local seed = U.hash(world.id, cell.x, cell.z, "weather")
      if raining and U.option(config, "puddles", true) and cell.walkable
          and U.keep(quality.density * 0.25, seed, "puddle") then
        buffer:addBatchItem("translucent_after_actors", "instances", "puddles", {
          owner = self.id,
          material = "weather:puddle",
          prototype = {
            primitive = "plane", width = size * 0.6, depth = size * 0.4,
          },
          sortKey = "weather:puddles",
        }, { x = x, y = y + 0.04, z = z, seed = seed })
      end
      U.checkpoint(context, index, 64)
    end

    if raining and U.option(config, "npc_umbrellas", true) then
      for index, actor in ipairs(world.actors or {}) do
        local pose = actor.pose
        buffer:addBatchItem("translucent_after_actors", "instances", "umbrellas", {
          owner = self.id,
          material = "weather:umbrella",
          prototype = { primitive = "umbrella" },
          sortKey = "weather:umbrellas",
        }, {
          x = pose.x, y = pose.y + world.cellSize, z = pose.z,
          seed = U.hash(world.id, actor.id, "umbrella"),
        })
        U.checkpoint(context, index, 32)
      end
    end

    if U.option(config, "rainbows", true) and world.weather == "clearing" then
      buffer:add("background", {
        kind = "mesh",
        owner = self.id,
        material = "weather:rainbow",
        sortKey = "weather:rainbow",
        geometry = {
          primitive = "rainbow", seed = U.hash(world.id, "rainbow"),
        },
      })
    end
  end

  local function compile(implementation, sample, maxBatchItems)
    local checkpoints = {}
    local context = {
      world = sample.world,
      config = sample.config,
      quality = sample.quality,
      services = sample.services,
      checkpoint = function(units)
        checkpoints[#checkpoints + 1] = units
      end,
    }
    local buffer = CommandBuffer.new({
      maxCommands = 8192,
      maxBatchItems = maxBatchItems,
      hashCommand = PacketHash.hashCommand,
    })
    implementation.new({ util = Util }):compile(context, buffer)
    return buffer:seal({ key = sample.world.key, generation = 9 }), checkpoints
  end

  local function copyTree(value)
    if type(value) ~= "table" then return value end
    local copy = {}
    for key, item in pairs(value) do copy[copyTree(key)] = copyTree(item) end
    return copy
  end

  local randomState = 104729
  local function nextInteger(maximum)
    randomState = (randomState * 48271) % 2147483647
    return randomState % maximum
  end

  local function pick(values)
    return values[nextInteger(#values) + 1]
  end

  local function randomSample(index)
    local width, height = nextInteger(12) + 1, nextInteger(12) + 1
    local night = nextInteger(2) == 0
    local tags = {
      outdoor = true,
      day = not night,
      night = night,
    }
    if index % 17 == 0 then tags.interior = true end
    if index % 29 == 0 then tags.cave = true end

    local cells = {}
    for z = 0, height - 1 do
      for x = 0, width - 1 do
        cells[#cells + 1] = {
          x = x,
          y = nextInteger(3) * 0.5,
          z = z,
          walkable = nextInteger(4) ~= 0,
          tags = nextInteger(2) == 0 and { grass = true } or {},
        }
      end
    end

    local actors = {}
    for actorIndex = 1, nextInteger(14) do
      actors[#actors + 1] = {
        id = "actor-" .. index .. "-" .. actorIndex,
        pose = {
          x = nextInteger(width * 16 + 1),
          y = nextInteger(5) * 0.25,
          z = nextInteger(height * 16 + 1),
        },
      }
    end

    local values = {
      rain = pick({ "OFF", "NEVER", "ALWAYS", "SOMETIMES", true, false }),
      puddles = nextInteger(3) ~= 0,
      npc_umbrellas = nextInteger(3) ~= 0,
      rainbows = nextInteger(3) ~= 0,
    }
    local config = nextInteger(2) == 0 and values or { values = values }
    local capabilities
    if index % 5 ~= 0 then
      capabilities = index % 3 == 0 and {}
        or { mesh = 1, instances = true, billboards = 1 }
    end

    return {
      world = {
        id = "WEATHER_DIFF_" .. index,
        key = "yellow:WEATHER_DIFF_" .. index .. ":1",
        width = width,
        height = height,
        cellSize = 16,
        weather = pick({ "clear", "rain", "storm", "clearing", "snow" }),
        tags = tags,
        cells = cells,
        actors = actors,
      },
      config = config,
      quality = {
        density = pick({ 1, 0.6, 0.3 }),
        resolved = pick({ "HIGH", "BALANCED", "LOW" }),
      },
      services = capabilities and { capabilities = capabilities } or nil,
    }
  end

  T.test("Weather hoists invariant reads and templates", function()
    local cells = {}
    for index = 0, 127 do
      cells[#cells + 1] = {
        x = index % 16, y = 0, z = math.floor(index / 16), walkable = true,
      }
    end
    local actors = {}
    for index = 1, 64 do
      actors[index] = { id = "actor-" .. index, pose = { x = index, y = 0, z = index } }
    end
    local world = {
      id = "WEATHER_INVARIANTS",
      key = "yellow:WEATHER_INVARIANTS:1",
      width = 16,
      height = 8,
      cellSize = 16,
      weather = "storm",
      tags = { outdoor = true, night = true },
      cells = cells,
      actors = actors,
    }
    local optionCalls, worldTagCalls = {}, {}
    local cellPositionCalls = 0
    local countingUtil = setmetatable({}, { __index = Util })
    function countingUtil.option(config, key, default)
      optionCalls[key] = (optionCalls[key] or 0) + 1
      return Util.option(config, key, default)
    end
    function countingUtil.hasTag(subject, tag)
      if subject == world then
        worldTagCalls[tag] = (worldTagCalls[tag] or 0) + 1
      end
      return Util.hasTag(subject, tag)
    end
    function countingUtil.cellPosition(subject, cell)
      cellPositionCalls = cellPositionCalls + 1
      return Util.cellPosition(subject, cell)
    end

    local firstTemplates, templateReferences = {}, {}
    local buffer = {}
    function buffer:addBatchItem(_, _, key, template)
      firstTemplates[key] = firstTemplates[key] or copyTree(template)
      local references = templateReferences[key] or {}
      templateReferences[key] = references
      references[template] = true
    end
    function buffer:add() error("storm must not emit a rainbow", 2) end

    local checkpoints = {}
    Weather.new({ util = countingUtil }):compile({
      world = world,
      config = {
        rain = "ALWAYS", puddles = true, npc_umbrellas = true, rainbows = true,
      },
      quality = { density = 1, resolved = "HIGH" },
      services = {},
      checkpoint = function(units) checkpoints[#checkpoints + 1] = units end,
    }, buffer)

    for _, key in ipairs({ "rain", "puddles", "umbrellas" }) do
      local count = 0
      for _ in pairs(templateReferences[key] or {}) do count = count + 1 end
      T.equal(count, 1, key .. " allocated more than one invariant template")
    end
    T.deepEqual(firstTemplates.rain, {
      owner = "weather", material = "weather:rain",
      sortKey = "weather:rain", animated = true,
    })
    T.deepEqual(firstTemplates.puddles, {
      owner = "weather", material = "weather:puddle",
      prototype = { primitive = "plane", width = 9.6, depth = 6.4 },
      sortKey = "weather:puddles",
    })
    T.deepEqual(firstTemplates.umbrellas, {
      owner = "weather", material = "weather:umbrella",
      prototype = { primitive = "umbrella" },
      sortKey = "weather:umbrellas",
    })
    for _, key in ipairs({ "rain", "puddles", "npc_umbrellas", "rainbows" }) do
      T.equal(optionCalls[key], 1, key)
    end
    T.equal(worldTagCalls.interior, 1)
    T.equal(worldTagCalls.cave, 1)
    T.equal(cellPositionCalls, 128)
    T.deepEqual(checkpoints, { 48, 48, 64, 64, 32, 32 })
  end)

  T.test("Weather hot path matches legacy packets and checkpoints", function()
    local boundaries = { 1, 2, 7, 23, 2048 }
    for index = 1, 120 do
      local sample = randomSample(index)
      local maxBatchItems = boundaries[(index - 1) % #boundaries + 1]
      local expected, expectedCheckpoints = compile(
        LegacyWeather, sample, maxBatchItems)
      local actual, actualCheckpoints = compile(Weather, sample, maxBatchItems)
      T.deepEqual(copyTree(actual), copyTree(expected),
        "Weather packet changed for randomized sample " .. index)
      T.deepEqual(actualCheckpoints, expectedCheckpoints,
        "Weather checkpoints changed for randomized sample " .. index)
      T.equal(PacketHash.hash(actual), PacketHash.hash(expected),
        "Weather packet hash changed for randomized sample " .. index)
    end
  end)

  T.test("Weather first templates remain exact across batch boundaries", function()
    local sample = randomSample(1001)
    sample.world.weather = "storm"
    sample.world.tags = { outdoor = true, night = true }
    sample.config = {
      rain = "ALWAYS", puddles = true, npc_umbrellas = true, rainbows = true,
    }
    sample.quality = { density = 1, resolved = "HIGH" }
    for _, maxBatchItems in ipairs({ 1, 2, 3, 7, 31 }) do
      local expected, expectedCheckpoints = compile(
        LegacyWeather, sample, maxBatchItems)
      local actual, actualCheckpoints = compile(Weather, sample, maxBatchItems)
      T.deepEqual(copyTree(actual), copyTree(expected),
        "Weather batch template changed at boundary " .. maxBatchItems)
      T.deepEqual(actualCheckpoints, expectedCheckpoints,
        "Weather batch checkpoint changed at boundary " .. maxBatchItems)
    end
  end)
end
