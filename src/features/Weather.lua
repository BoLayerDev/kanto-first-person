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
  if U.hasTag(world, "interior") or U.hasTag(world, "cave") then return end
  local raining = rainEnabled(U.option(config, "rain", "SOMETIMES"), world.weather)

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
        prototype = { primitive = "plane", width = size * 0.6, depth = size * 0.4 },
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
      }, { x = pose.x, y = pose.y + world.cellSize, z = pose.z,
        seed = U.hash(world.id, actor.id, "umbrella") })
      U.checkpoint(context, index, 32)
    end
  end

  if U.capability(context, "draw_lights")
      and world.weather == "storm" and U.option(config, "lightning", true) then
    buffer:add("translucent_after_actors", {
      kind = "lights",
      owner = self.id,
      sortKey = "weather:lightning",
      lights = "lightning",
      seed = U.hash(world.id, "lightning"),
      safety = true,
    })
  end
  if U.option(config, "rainbows", true) and world.weather == "clearing" then
    buffer:add("background", {
      kind = "mesh",
      owner = self.id,
      material = "weather:rainbow",
      sortKey = "weather:rainbow",
      geometry = { primitive = "rainbow", seed = U.hash(world.id, "rainbow") },
    })
  end
  if U.capability(context, "draw_postprocess")
      and U.option(config, "lavender_fog", true)
      and (world.weather == "fog" or world.weather == "storm") then
    buffer:add("translucent_after_actors", {
      kind = "postprocess",
      owner = self.id,
      material = "weather:fog",
      sortKey = "weather:fog",
      effect = { kind = "depth_fog", density = world.weather == "storm" and 0.35 or 0.2 },
    })
  end
end

return Weather
