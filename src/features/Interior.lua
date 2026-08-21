local Interior = {}
Interior.__index = Interior

local POSTERS = {
  DEFAULT = "assets/legacy/posters/posters.png",
  POKECENTER = "assets/legacy/posters/posters-pokecenter.png",
  POKEMART = "assets/legacy/posters/posters-pokemart.png",
}

local function packagedImage(context, path)
  local services = type(context) == "table" and context.services or nil
  local assets = type(services) == "table" and services.assets or nil
  if type(assets) ~= "table" or type(assets.image) ~= "function" then return nil end
  local ok, image = pcall(assets.image, assets, path)
  if not ok or not image then return nil end
  return image
end

local function posterChoice(cell, util)
  if util.hasTag(cell, "pokemon_center") or util.hasTag(cell, "pokecenter") then
    return "POKECENTER"
  end
  if util.hasTag(cell, "pokemart") or util.hasTag(cell, "mart")
      or util.hasTag(cell, "shop") then
    return "POKEMART"
  end
  local metadata = type(cell) == "table" and cell.metadata or nil
  local value = type(metadata) == "table" and metadata.poster or nil
  local normalized = type(value) == "string" and value:upper():gsub("[^A-Z0-9]", "") or ""
  if normalized:find("POKECENTER", 1, true)
      or normalized:find("POKEMONCENTER", 1, true) then
    return "POKECENTER"
  end
  if normalized:find("POKEMART", 1, true)
      or normalized == "MART" or normalized == "SHOP" then
    return "POKEMART"
  end
  return "DEFAULT"
end

function Interior.new(deps)
  deps = deps or {}
  if not deps.util then error("Interior needs util", 2) end
  return setmetatable({
    id = "interior",
    order = 100,
    critical = true,
    util = deps.util,
  }, Interior)
end

local function addInstance(buffer, phase, key, material, prototype, item, owner, texture)
  buffer:addBatchItem(phase, "instances", key, {
    owner = owner,
    material = material,
    prototype = prototype,
    sortKey = material .. ":" .. key,
    texture = texture,
  }, item)
end

function Interior:compile(context, buffer)
  local U = self.util
  local world, config = context.world, context.config
  if not U.option(config, "ceiling", true) then return end
  if not U.worldHas(world, "interior") and not U.worldHas(world, "building") then return end

  local height = tonumber(config.headroom_pixels)
    or U.headroom(U.option(config, "headroom", "AIRY"))
  local cutaway = U.option(config, "cutaway", true)
  local index = U.indexCells(world)
  local posterTextures = {}

  local function posterTexture(choice)
    local cached = posterTextures[choice]
    if cached == false then return nil end
    if cached ~= nil then return cached end
    local image = packagedImage(context, POSTERS[choice])
    posterTextures[choice] = image or false
    return image
  end

  for cellIndex, cell in ipairs(world.cells or {}) do
    if cell.walkable and (U.hasTag(cell, "interior") or U.hasTag(cell, "room")
        or U.hasTag(world, "interior")) then
      local x, y, z, size = U.cellPosition(world, cell)
      local material = U.material(cell, "interior")
      addInstance(buffer, "opaque_after_terrain", "ceiling:" .. material, material,
        { primitive = "box", width = size, height = 1, depth = size,
          cutaway = cutaway, role = "ceiling" },
        { x = x, y = y + height, z = z, cellX = cell.x, cellZ = cell.z }, self.id)

      local directions = {
        { -1, 0, "west", 1, size }, { 1, 0, "east", 1, size },
        { 0, -1, "north", size, 1 }, { 0, 1, "south", size, 1 },
      }
      for _, direction in ipairs(directions) do
        local neighbor = U.cellAt(world, index, cell.x + direction[1], cell.z + direction[2])
        if not neighbor or neighbor.solid or U.hasTag(neighbor, "outside") then
          local offsetX = direction[1] * size * 0.5
          local offsetZ = direction[2] * size * 0.5
          addInstance(buffer, "opaque_after_terrain", "wall:" .. material, material,
            { primitive = "box", width = direction[4], height = height,
              depth = direction[5], cutaway = cutaway, role = "wall" },
            { x = x + offsetX, y = y + height * 0.5, z = z + offsetZ,
              side = direction[3], cellX = cell.x, cellZ = cell.z }, self.id)
        end
      end

      if U.hasTag(cell, "door") then
        addInstance(buffer, "opaque_after_terrain", "doors", material,
          { primitive = "door_frame", role = "door", double = U.hasTag(cell, "double_door") },
          { x = x, y = y, z = z, facing = cell.metadata and cell.metadata.facing }, self.id)
      end
      if U.option(config, "windows", true) and U.hasTag(cell, "window") then
        addInstance(buffer, "opaque_after_terrain", "windows", material,
          { primitive = "window", role = "window" },
          { x = x, y = y + height * 0.55, z = z }, self.id)
      end
      if U.hasTag(cell, "poster") then
        local choice = posterChoice(cell, U)
        local texture = posterTexture(choice)
        if texture then
          addInstance(buffer, "opaque_after_terrain", "posters:" .. choice:lower(),
            "legacy:posters:" .. choice:lower(),
            { primitive = "poster", role = "poster" },
            { x = x, y = y + height * 0.55, z = z }, self.id, texture)
        end
      end
      if U.option(config, "contact_shadows", true) then
        addInstance(buffer, "opaque_after_terrain", "contact_shadows", "shadow:contact",
          { primitive = "plane", width = size, depth = size, role = "contact_shadow" },
          { x = x, y = y + 0.02, z = z }, self.id)
      end
      if U.option(config, "rails", true) and U.hasTag(cell, "rail") then
        addInstance(buffer, "opaque_after_terrain", "rails", material,
          { primitive = "rail", role = "rail" }, { x = x, y = y, z = z }, self.id)
      end
      if U.option(config, "ceiling_lamps", true) and U.hasTag(cell, "light_fixture") then
        addInstance(buffer, "opaque_after_terrain", "ceiling_fittings", material,
          { primitive = "fixture", role = "light_fixture" },
          { x = x, y = y + height - 0.5, z = z }, self.id)
      end
    end
    U.checkpoint(context, cellIndex, 24)
  end

  if U.capability(context, "draw_lights")
      and U.option(config, "doorway_light", true) then
    buffer:add("opaque_after_terrain", {
      kind = "lights",
      owner = self.id,
      sortKey = "interior:door_spill",
      lights = "door_spill",
      cutaway = cutaway,
    })
  end
end

return Interior
