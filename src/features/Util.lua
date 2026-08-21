local Util = {}

local UINT32 = 4294967296

function Util.option(config, key, default)
  if type(config) ~= "table" then return default end
  local value = config[key]
  if value == nil and type(config.values) == "table" then
    value = config.values[key]
  end
  if value == nil then return default end
  return value
end

function Util.hasTag(subject, tag)
  if type(subject) ~= "table" or type(subject.tags) ~= "table" then return false end
  if subject.tags[tag] == true then return true end
  for _, value in ipairs(subject.tags) do
    if value == tag then return true end
  end
  return false
end

function Util.worldHas(world, tag)
  if Util.hasTag(world, tag) then return true end
  for _, cell in ipairs(world and world.cells or {}) do
    if Util.hasTag(cell, tag) then return true end
  end
  return false
end

function Util.capability(context, name)
  local services = type(context) == "table" and context.services or nil
  local capabilities = type(services) == "table" and services.capabilities or nil
  local value = type(capabilities) == "table" and capabilities[name] or nil
  return value == true or tonumber(value) == 1
end

function Util.hash(...)
  local hash = 2166136261
  for index = 1, select("#", ...) do
    local text = tostring(select(index, ...))
    for i = 1, #text do
      hash = (hash * 16777619 + text:byte(i)) % UINT32
    end
    hash = (hash + 374761393) % UINT32
  end
  return hash
end

function Util.unit(...)
  return Util.hash(...) / (UINT32 - 1)
end

function Util.keep(density, ...)
  density = tonumber(density) or 1
  if density >= 1 then return true end
  if density <= 0 then return false end
  return Util.unit(...) < density
end

function Util.cellPosition(world, cell)
  local size = tonumber(world and world.cellSize) or 16
  return (cell.x + 0.5) * size, tonumber(cell.y) or 0, (cell.z + 0.5) * size, size
end

function Util.material(cell, fallback)
  if type(cell) == "table" and type(cell.material) == "string" and cell.material ~= "" then
    return cell.material
  end
  return fallback or "terrain"
end

function Util.headroom(value)
  value = type(value) == "string" and value:upper() or "AIRY"
  if value == "SNUG" then return 16 end
  if value == "MID" then return 24 end
  if value == "AIRY" then return 32 end
  -- Read-only compatibility with pre-v2 scene fixtures.
  if value == "COZY" then return 24 end
  if value == "OPEN" then return 48 end
  return 32
end

function Util.checkpoint(context, index, interval)
  interval = interval or 32
  if index % interval == 0 and context and context.checkpoint then
    context.checkpoint(interval)
  end
end

function Util.indexCells(world)
  local index = {}
  local width = world.width
  for _, cell in ipairs(world.cells or {}) do
    index[cell.z * width + cell.x + 1] = cell
  end
  return index
end

function Util.cellAt(world, index, x, z)
  if x < 0 or z < 0 or x >= world.width or z >= world.height then return nil end
  return index[z * world.width + x + 1]
end

function Util.facingVector(facing)
  facing = type(facing) == "string" and facing:lower() or "down"
  if facing == "up" or facing == "north" then return 0, -1 end
  if facing == "left" or facing == "west" then return -1, 0 end
  if facing == "right" or facing == "east" then return 1, 0 end
  return 0, 1
end

return Util
