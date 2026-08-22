local Util = {}

local UINT32 = 4294967296
local HASH_MULTIPLIER = 65599
local CARDINAL_DELTAS = {
  { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 },
}
local PLACEMENT_SPACING = {
  HIGH = { tree = 2, mountain = 2, object = 2 },
  BALANCED = { tree = 3, mountain = 3, object = 3 },
  LOW = { tree = 4, mountain = 4, object = 4 },
}

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

local function hashText(hash, text)
  for index = 1, #text do
    -- This is the exact multiplier used by core/RNG.lua. The largest
    -- intermediate stays below 2^53, so Lua numbers do not lose bits.
    hash = (hash * HASH_MULTIPLIER + text:byte(index)) % UINT32
  end
  return hash
end

function Util.hash(...)
  local hash = 2166136261
  for index = 1, select("#", ...) do
    local text = tostring(select(index, ...))
    -- Length-prefix every part so, for example, ("a", "bc") cannot collide
    -- with ("ab", "c"). The 255 byte terminates the complete frame.
    hash = hashText(hash, tostring(#text) .. ":")
    hash = hashText(hash, text)
    hash = (hash * HASH_MULTIPLIER + 255) % UINT32
  end
  return hash
end

function Util.unit(...)
  return Util.hash(...) / UINT32
end

function Util.keep(density, ...)
  density = tonumber(density) or 1
  if density >= 1 then return true end
  if density <= 0 then return false end
  return Util.unit(...) < density
end

local function coordinateKey(cell)
  return tostring(cell and cell.x or 0) .. "|" .. tostring(cell and cell.z or 0)
end

-- Select one stable representative from each spatial bucket. This turns
-- broad host classifications such as a multi-cell tree crown into bounded
-- feature anchors without a global random stream or render-time map scan.
function Util.clusterAnchors(world, spacing, salt, predicate, priority, context)
  spacing = math.max(1, math.floor(tonumber(spacing) or 1))
  salt = tostring(salt or "feature")
  local buckets = {}
  for index, cell in ipairs(world and world.cells or {}) do
    if not predicate or predicate(cell) then
      local bx = math.floor((tonumber(cell.x) or 0) / spacing)
      local bz = math.floor((tonumber(cell.z) or 0) / spacing)
      local bucketKey = bx .. "|" .. bz
      local rank = tonumber(priority and priority(cell)) or 0
      local score = Util.hash(world and world.id or "world", cell.x, cell.z, salt)
      local chosen = buckets[bucketKey]
      if not chosen or rank > chosen.rank
          or (rank == chosen.rank and score < chosen.score)
          or (rank == chosen.rank and score == chosen.score
            and coordinateKey(cell) < coordinateKey(chosen.cell)) then
        buckets[bucketKey] = { cell = cell, rank = rank, score = score }
      end
    end
    Util.checkpoint(context, index, 32)
  end
  local anchors = {}
  for _, chosen in pairs(buckets) do
    anchors[coordinateKey(chosen.cell)] = true
  end
  return anchors
end

function Util.isAnchor(anchors, cell)
  return type(anchors) == "table" and anchors[coordinateKey(cell)] == true
end

function Util.placementPolicy(world, quality)
  local tier = type(quality) == "table" and quality.resolved or nil
  tier = type(tier) == "string" and tier:upper() or nil
  if not PLACEMENT_SPACING[tier] then
    local density = tonumber(type(quality) == "table" and quality.density) or 1
    tier = density <= 0.35 and "LOW"
      or (density <= 0.7 and "BALANCED" or "HIGH")
  end
  local source = PLACEMENT_SPACING[tier]
  local policy = {
    tree = source.tree,
    mountain = source.mountain,
    object = source.object,
  }
  -- Town and city maps need more open foreground placement than routes and
  -- forests. The semantic support facts still come only from the host.
  if Util.hasTag(world, "town") or Util.hasTag(world, "city") then
    policy.tree = policy.tree + 1
    policy.object = policy.object + 1
  end
  return policy
end

function Util.isSemanticSupport(cell, role)
  return type(cell) == "table" and cell.solid == true
    and cell.walkable == false and Util.hasTag(cell, role)
end

-- A mountain support cell is eligible only when it has another cardinal
-- mountain support. This is the one host-neutral minimum cluster rule used
-- by world and battle placement; isolated seeds remain adapter facts only.
function Util.isMountainClusterMember(world, index, cell)
  if not Util.isSemanticSupport(cell, "mountain_support") then return false end
  for _, delta in ipairs(CARDINAL_DELTAS) do
    local neighbor = Util.cellAt(world, index,
      cell.x + delta[1], cell.z + delta[2])
    if Util.isSemanticSupport(neighbor, "mountain_support") then return true end
  end
  return false
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

function Util.indexCells(world, context)
  local index = {}
  local width = world.width
  for cellIndex, cell in ipairs(world.cells or {}) do
    index[cell.z * width + cell.x + 1] = cell
    Util.checkpoint(context, cellIndex, 32)
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
