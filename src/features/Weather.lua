local Weather = {}
Weather.__index = Weather

function Weather.new(deps)
  deps = deps or {}
  if not deps.util then error("Weather needs util", 2) end
  return setmetatable({ id = "weather", order = 220, critical = false, util = deps.util }, Weather)
end

local function rainEnabled(value, weather)
  value = type(value) == "string" and value:upper() or (value and "SOMETIMES" or "OFF")
  if value == "OFF" or value == "NEVER" then return false end
  if value == "ALWAYS" then return true end
  return weather == "rain" or weather == "storm"
end

function Weather:compile(context, buffer)
  local U = self.util
  local world, config, quality = context.world, context.config, context.quality
  local hasTag, option = U.hasTag, U.option
  if hasTag(world, "interior") or hasTag(world, "cave") then return end

  local add, addBatchItem = buffer.add, buffer.addBatchItem
  local cellPosition = U.cellPosition
  local checkpoint, hash, keep, unit = U.checkpoint, U.hash, U.keep, U.unit
  local worldId, cellSize = world.id, world.cellSize
  local weather = world.weather
  local density = quality.density
  local owner = self.id
  local raining = rainEnabled(option(config, "rain", "SOMETIMES"), weather)

  if raining then
    local count = math.max(24, math.floor(130 * density))
    local rainTemplate = {
      owner = owner,
      material = "weather:rain",
      sortKey = "weather:rain",
      animated = true,
    }
    local worldWidth, worldHeight = world.width, world.height
    for index = 1, count do
      local unitX = unit(worldId, "rain", index, "x")
      local unitZ = unit(worldId, "rain", index, "z")
      addBatchItem(buffer, "translucent_after_actors", "billboards", "rain",
        rainTemplate, {
        x = unitX * worldWidth * cellSize,
        y = cellSize * (2 + unit(worldId, "rain", index, "y") * 4),
        z = unitZ * worldHeight * cellSize,
        seed = hash(worldId, "rain", index),
      })
      checkpoint(context, index, 48)
    end
  end

  local puddles = raining and option(config, "puddles", true)
  local puddleDensity = puddles and density * 0.25 or nil
  local puddleTemplate
  local cells = world.cells or {}
  for index, cell in ipairs(cells) do
    if puddles and cell.walkable then
      local x, y, z, size = cellPosition(world, cell)
      local seed = hash(worldId, cell.x, cell.z, "weather")
      if keep(puddleDensity, seed, "puddle") then
        if not puddleTemplate then
          puddleTemplate = {
            owner = owner,
            material = "weather:puddle",
            prototype = {
              primitive = "plane",
              width = size * 0.6,
              depth = size * 0.4,
            },
            sortKey = "weather:puddles",
          }
        end
        addBatchItem(buffer, "translucent_after_actors", "instances", "puddles",
          puddleTemplate, { x = x, y = y + 0.04, z = z, seed = seed })
      end
    end
    checkpoint(context, index, 64)
  end

  if raining and option(config, "npc_umbrellas", true) then
    local umbrellaTemplate = {
      owner = owner,
      material = "weather:umbrella",
      prototype = { primitive = "umbrella" },
      sortKey = "weather:umbrellas",
    }
    local actors = world.actors or {}
    for index, actor in ipairs(actors) do
      local pose = actor.pose
      addBatchItem(buffer, "translucent_after_actors", "instances", "umbrellas",
        umbrellaTemplate, {
        x = pose.x, y = pose.y + cellSize, z = pose.z,
        seed = hash(worldId, actor.id, "umbrella"),
      })
      checkpoint(context, index, 32)
    end
  end

  if option(config, "rainbows", true) and weather == "clearing" then
    add(buffer, "background", {
      kind = "mesh",
      owner = owner,
      material = "weather:rainbow",
      sortKey = "weather:rainbow",
      geometry = { primitive = "rainbow", seed = hash(worldId, "rainbow") },
    })
  end
end

return Weather
