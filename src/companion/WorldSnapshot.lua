local WorldSnapshot = {}

local DEFAULT_LIMITS = {
  width = 1024,
  height = 1024,
  cells = 65536,
  actors = 2048,
  neighbors = 8,
  tags = 256,
  text = 256,
  metadataBytes = 65536,
  metadataDepth = 5,
  metadataItems = 1024,
  aggregateTags = 65536,
  aggregateTextBytes = 8 * 1024 * 1024,
  aggregateMetadataBytes = 2 * 1024 * 1024,
  aggregateMetadataItems = 32768,
  aggregateNodes = 262144,
  workItems = 1024 * 1024,
  coordinate = 65536,
  cellSize = 1024,
}

local GAME_IDS = { red = true, blue = true, yellow = true }
local MODES = { first_person = true, third_person = true, diorama = true, battle = true }
local FACING = { up = true, down = true, left = true, right = true, north = true,
  south = true, east = true, west = true }

local function finite(value, default)
  if type(value) ~= "number" or value ~= value
      or value == math.huge or value == -math.huge then
    return default
  end
  return value
end

local function mergedLimits(custom)
  local limits = {}
  for key, value in pairs(DEFAULT_LIMITS) do limits[key] = value end
  for key, value in pairs(custom or {}) do
    local number = finite(value, nil)
    if limits[key] and number and number > 0 then
      limits[key] = math.min(limits[key], math.floor(number))
    end
  end
  return limits
end

local function integer(value, default)
  value = finite(value, default)
  if value == nil then return nil end
  return math.floor(value)
end

local function newBudget(limits)
  return {
    limits = limits,
    tags = 0,
    textBytes = 0,
    metadataBytes = 0,
    metadataItems = 0,
    nodes = 0,
    work = 0,
    error = nil,
  }
end

local function charge(budget, field, amount, limit, message)
  if budget.error then return false end
  local nextValue = budget[field] + (amount or 1)
  if nextValue > budget.limits[limit] then
    budget.error = message
    return false
  end
  budget[field] = nextValue
  return true
end

local function work(budget, amount)
  return charge(budget, "work", amount, "workItems",
    "world snapshot work limit exceeded")
end

local function node(budget, amount)
  return charge(budget, "nodes", amount, "aggregateNodes",
    "world snapshot node limit exceeded")
end

local function textBudget(budget, value)
  return charge(budget, "textBytes", #value, "aggregateTextBytes",
    "world snapshot text limit exceeded")
end

local function requiredText(value, name, limits, budget)
  if type(value) ~= "string" or value == "" or #value > limits.text then
    return nil, name .. " must be a non-empty string"
  end
  if not textBudget(budget, value) then return nil, budget.error end
  return value
end

local function optionalText(value, limits, budget)
  local maxBytes = limits.text or 256
  local text
  if type(value) == "string" and value ~= "" and #value <= maxBytes then
    text = value
  end
  if type(value) == "number" then
    local converted = tostring(value)
    if #converted <= maxBytes then text = converted end
  end
  if text and textBudget(budget, text) then return text end
  return nil
end

local function enumText(value, allowed, fallback, limits, budget)
  if not work(budget, 1) then return nil end
  local normalized = fallback
  if type(value) == "string" and #value <= limits.text then
    local lowered = value:lower()
    if allowed[lowered] then normalized = lowered end
  end
  if normalized and not textBudget(budget, normalized) then return nil end
  return normalized
end

local function copyPlain(value, limits, depth, state, budget)
  local kind = type(value)
  if kind == "nil" or kind == "boolean" then return value end
  if kind == "string" then
    if #value > limits.text or state.bytes + #value > limits.metadataBytes then
      return nil
    end
    if not charge(budget, "metadataBytes", #value, "aggregateMetadataBytes",
        "world snapshot metadata byte limit exceeded") then return nil end
    state.bytes = state.bytes + #value
    return value
  end
  if kind == "number" then
    return finite(value, nil)
  end
  if kind ~= "table" then return nil end
  if depth > limits.metadataDepth then return nil end
  if state.seen[value] then return nil end
  if state.items >= limits.metadataItems then return nil end
  state.seen[value] = true
  local out = {}
  for key, item in pairs(value) do
    if not work(budget, 1) then break end
    if state.items >= limits.metadataItems then break end
    local keyKind = type(key)
    local keyBytes = keyKind == "string" and #key or 0
    if ((keyKind == "string" and keyBytes <= limits.text)
        or keyKind == "number")
        and state.bytes + keyBytes <= limits.metadataBytes then
      if keyBytes > 0 and not charge(budget, "metadataBytes", keyBytes,
          "aggregateMetadataBytes",
          "world snapshot metadata byte limit exceeded") then break end
      state.bytes = state.bytes + keyBytes
      local copied = copyPlain(item, limits, depth + 1, state, budget)
      if copied ~= nil then
        if not charge(budget, "metadataItems", 1, "aggregateMetadataItems",
            "world snapshot metadata item limit exceeded")
            or not node(budget, 1) then break end
        out[key] = copied
        state.items = state.items + 1
      end
    end
  end
  state.seen[value] = nil
  return out
end

local function copyTags(source, limits, budget)
  local tags, count = {}, 0
  if type(source) ~= "table" then return tags end
  for key, value in pairs(source) do
    if not work(budget, 1) then break end
    local tag
    if type(key) == "number" then tag = optionalText(value, limits, budget)
    elseif value == true then tag = optionalText(key, limits, budget) end
    if tag and not tags[tag] then
      count = count + 1
      if count > limits.tags then
        budget.error = "world snapshot per-record tag limit exceeded"
        break
      end
      if not charge(budget, "tags", 1, "aggregateTags",
          "world snapshot aggregate tag limit exceeded")
          or not node(budget, 1) then break end
      tags[tag] = true
    end
  end
  return tags
end

local function boundedCoordinate(value, limits)
  value = finite(value, 0)
  if math.abs(value) > limits.coordinate then return 0 end
  return value
end

local function copyPose(source, limits, budget)
  source = type(source) == "table" and source or {}
  if not node(budget, 1) then return nil, budget.error end
  local facing = enumText(source.facing, FACING, "down", limits, budget)
  if not facing then return nil, budget.error end
  return {
    x = boundedCoordinate(source.x or source.worldX, limits),
    y = boundedCoordinate(source.y or source.worldY, limits),
    z = boundedCoordinate(source.z or source.worldZ, limits),
    cellX = integer(boundedCoordinate(source.cellX, limits), 0),
    cellZ = integer(boundedCoordinate(source.cellZ or source.cellY, limits), 0),
    facing = facing,
  }
end

local function copyCell(source, limits, budget)
  if type(source) ~= "table" then return nil, "cell must be a table" end
  if not node(budget, 1) or not work(budget, 1) then return nil, budget.error end
  local x = integer(source.x or source.cellX, nil)
  local z = integer(source.z or source.cellZ or source.y, nil)
  if x == nil or z == nil then return nil, "cell needs x and z" end
  local kind = optionalText(source.kind, limits, budget) or "ground"
  local material = optionalText(source.material, limits, budget) or "terrain"
  local atlas = optionalText(source.atlas, limits, budget)
  local tags = copyTags(source.tags, limits, budget)
  local metadata = copyPlain(source.metadata, limits, 1,
    { seen = {}, items = 0, bytes = 0 }, budget)
  if budget.error then return nil, budget.error end
  return {
    x = x,
    z = z,
    y = boundedCoordinate(source.worldY or source.heightBase, limits),
    height = boundedCoordinate(source.height, limits),
    kind = kind,
    material = material,
    atlas = atlas,
    solid = source.solid == true,
    walkable = source.walkable ~= false,
    tags = tags,
    metadata = metadata,
  }
end

local function denseArrayLength(source, limit, name, budget)
  if type(source) ~= "table" then return 0 end
  local count, maximum = 0, 0
  for key in pairs(source) do
    if not work(budget, 1) then return nil, budget.error end
    if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then
      return nil, name .. " must be a dense array"
    end
    count = count + 1
    if count > limit then return nil, name .. " limit exceeded" end
    if key > maximum then maximum = key end
  end
  if count ~= maximum then return nil, name .. " must be a dense array" end
  return count
end

local function copyActors(source, limits, budget)
  local out = {}
  if type(source) ~= "table" then return out end
  local count, err = denseArrayLength(source, limits.actors, "actor", budget)
  if not count then return nil, err end
  for index = 1, count do
    local actor = source[index]
    if type(actor) == "table" then
      if not node(budget, 1) or not work(budget, 1) then return nil, budget.error end
      local id = optionalText(actor.id, limits, budget) or tostring(index)
      local kind = optionalText(actor.kind, limits, budget) or "npc"
      local tags = copyTags(actor.tags, limits, budget)
      if budget.error then return nil, budget.error end
      local pose, poseError = copyPose(actor.pose or actor, limits, budget)
      if not pose then return nil, poseError end
      out[#out + 1] = {
        id = id,
        kind = kind,
        pose = pose,
        tags = tags,
      }
    end
  end
  return out
end

local function copyNeighbors(source, limits, budget)
  local out = {}
  if type(source) ~= "table" then return out end
  local count, err = denseArrayLength(source, limits.neighbors, "neighbor", budget)
  if not count then return nil, err end
  for index = 1, count do
    local neighbor = source[index]
    if type(neighbor) == "table" then
      if not node(budget, 1) or not work(budget, 1) then return nil, budget.error end
      local id = optionalText(neighbor.id or neighbor.mapId, limits, budget)
      if id then
        local atlas = optionalText(neighbor.atlas, limits, budget)
        local tilesetRevision = optionalText(
          neighbor.tilesetRevision, limits, budget)
        local tags = copyTags(neighbor.tags, limits, budget)
        if budget.error then return nil, budget.error end
        out[#out + 1] = {
          id = id,
          revision = integer(neighbor.revision, 0),
          offsetX = boundedCoordinate(neighbor.offsetX, limits),
          offsetZ = boundedCoordinate(neighbor.offsetZ, limits),
          atlas = atlas,
          tilesetRevision = tilesetRevision,
          tags = tags,
        }
      end
    end
  end
  return out
end

local function keyAtom(value)
  local text = tostring(value == nil and "" or value)
  return tostring(#text) .. "#" .. text
end

local function tagKey(tags)
  local names = {}
  for name, enabled in pairs(type(tags) == "table" and tags or {}) do
    if enabled == true then names[#names + 1] = tostring(name) end
  end
  table.sort(names)
  for index, name in ipairs(names) do names[index] = keyAtom(name) end
  return table.concat(names, ",")
end

local function neighborKey(neighbors)
  local records = {}
  for _, neighbor in ipairs(neighbors or {}) do
    records[#records + 1] = table.concat({
      keyAtom(neighbor.id),
      keyAtom(neighbor.revision),
      keyAtom(neighbor.offsetX),
      keyAtom(neighbor.offsetZ),
      keyAtom(neighbor.atlas),
      keyAtom(neighbor.tilesetRevision),
      keyAtom(tagKey(neighbor.tags)),
    }, "/")
  end
  table.sort(records)
  return table.concat(records, ";")
end

local function digest(value)
  local hash = 5381
  value = tostring(value or "")
  for index = 1, #value do
    hash = (hash * 33 + value:byte(index)) % 4294967296
  end
  return string.format("%08x", hash)
end

function WorldSnapshot.copyLedge(source, customLimits)
  if type(source) ~= "table" then return nil end
  local limits = mergedLimits(customLimits)
  local budget = newBudget(limits)
  local copied = copyPlain(source, limits, 1,
    { seen = {}, items = 0, bytes = 0 }, budget)
  if budget.error or type(copied) ~= "table" then return nil end
  return copied
end

function WorldSnapshot.capture(source, customLimits)
  if type(source) ~= "table" then return nil, "world snapshot must be a table" end
  local limits = mergedLimits(customLimits)

  local budget = newBudget(limits)
  local id, err = requiredText(source.id or source.mapId, "map id", limits, budget)
  if not id then return nil, err end
  local game = enumText(source.game, GAME_IDS, nil, limits, budget)
  if budget.error then return nil, budget.error end
  if not game then return nil, "unsupported game" end
  local width = integer(source.width, nil)
  local height = integer(source.height, nil)
  if not width or not height or width < 1 or height < 1
      or width > limits.width or height > limits.height
      or width * height > limits.cells then
    return nil, "invalid world dimensions"
  end
  local cellSize = finite(source.cellSize, 16)
  if cellSize <= 0 or cellSize > limits.cellSize
      or width * cellSize > limits.coordinate
      or height * cellSize > limits.coordinate then
    return nil, "invalid world cell size"
  end
  local mode = enumText(source.mode, MODES, "first_person", limits, budget)
  if not mode then return nil, budget.error end

  local cells = {}
  local rawCells = type(source.cells) == "table" and source.cells or {}
  local rawCount, countError = denseArrayLength(rawCells, limits.cells, "cell", budget)
  if not rawCount then return nil, countError end
  local cellsByCoordinate = {}
  for index, rawCell in ipairs(rawCells) do
    local cell, cellErr = copyCell(rawCell, limits, budget)
    if not cell then return nil, "cell " .. index .. ": " .. cellErr end
    if cell.x < 0 or cell.x >= width or cell.z < 0 or cell.z >= height then
      return nil, "cell " .. index .. " is outside world bounds"
    end
    local coordinateKey = cell.z * width + cell.x
    if cellsByCoordinate[coordinateKey] then return nil, "duplicate cell coordinate" end
    cellsByCoordinate[coordinateKey] = cell
  end
  -- Cells are coordinate-addressed facts. Canonical z-major order makes every
  -- downstream packet independent of host enumeration order without an
  -- unbounded comparison sort.
  for coordinateKey = 0, width * height - 1 do
    if not work(budget, 1) then return nil, budget.error end
    local cell = cellsByCoordinate[coordinateKey]
    if cell then cells[#cells + 1] = cell end
  end

  local tags = copyTags(source.tags, limits, budget)
  local player, playerError = copyPose(source.player, limits, budget)
  if not player then return nil, playerError end
  local actors, actorError = copyActors(source.actors, limits, budget)
  if not actors then return nil, actorError end
  local neighbors, neighborError = copyNeighbors(source.neighbors, limits, budget)
  if not neighbors then return nil, neighborError end
  local paletteRevision = optionalText(source.paletteRevision, limits, budget) or "0"
  local tilesetRevision = optionalText(source.tilesetRevision, limits, budget) or "0"
  local atlasRevision = optionalText(source.atlasRevision, limits, budget) or "0"
  local weather = optionalText(source.weather, limits, budget) or "clear"
  if budget.error then return nil, budget.error end

  local snapshot = {
    id = id,
    revision = integer(source.revision, 0),
    game = game,
    width = width,
    height = height,
    cellSize = cellSize,
    paletteRevision = paletteRevision,
    tilesetRevision = tilesetRevision,
    atlasRevision = atlasRevision,
    mode = mode,
    tags = tags,
    player = player,
    actors = actors,
    neighbors = neighbors,
    cells = cells,
    time = finite(source.time, 0),
    weather = weather,
  }
  snapshot.key = WorldSnapshot.key(snapshot)
  return snapshot
end

function WorldSnapshot.key(snapshot)
  return table.concat({
    tostring(snapshot.game),
    tostring(snapshot.id),
    tostring(snapshot.revision or 0),
    tostring(snapshot.paletteRevision or 0),
    tostring(snapshot.tilesetRevision or 0),
    tostring(snapshot.atlasRevision or 0),
    tostring(snapshot.mode or "first_person"),
    tostring(snapshot.weather or "clear"),
    "tags=" .. digest(tagKey(snapshot.tags)),
    "neighbors=" .. digest(neighborKey(snapshot.neighbors)),
  }, ":")
end

function WorldSnapshot.index(snapshot)
  local out = {}
  for _, cell in ipairs(snapshot and snapshot.cells or {}) do
    out[cell.z * snapshot.width + cell.x + 1] = cell
  end
  return out
end

function WorldSnapshot.cell(snapshot, index, x, z)
  if not snapshot then return nil end
  index = index or WorldSnapshot.index(snapshot)
  if x < 0 or z < 0 or x >= snapshot.width or z >= snapshot.height then return nil end
  return index[z * snapshot.width + x + 1]
end

function WorldSnapshot.limits()
  return mergedLimits()
end

return WorldSnapshot
