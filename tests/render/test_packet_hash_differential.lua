return function(T)
  local PacketHash = assert(loadfile(T.root .. "/src/render/PacketHash.lua"))()
  local MOD = 65521
  local COMMAND_DOMAIN_PREFIX = "t2{s6:domain;s14:kfp-command-v1;s5:value;"
  local TABLE_SUFFIX = "};"
  local RUNTIME_FIELDS = {
    cacheKey = true,
    schemaVersion = true,
    sequence = true,
    texture = true,
    mesh = true,
    resource = true,
    model = true,
  }

  local function finite(value)
    return type(value) == "number" and value == value
      and value ~= math.huge and value ~= -math.huge
  end

  local function keyOrder(a, b)
    local ta, tb = type(a), type(b)
    if ta ~= tb then return ta < tb end
    if ta == "number" then return a < b end
    return tostring(a) < tostring(b)
  end

  local function referenceBytes(value, limits)
    limits = limits or {}
    local maxDepth = tonumber(limits.maxDepth) or 32
    local maxNodes = tonumber(limits.maxNodes) or 100000
    local active, nodes, parts = {}, 0, {}

    local function feed(text) parts[#parts + 1] = text end
    local encode
    encode = function(item, depth)
      local kind = type(item)
      if kind == "nil" then feed("n;"); return end
      if kind == "boolean" then feed(item and "b1;" or "b0;"); return end
      if kind == "number" then
        if not finite(item) then
          error("packet hash rejects non-finite numbers", 3)
        end
        if item == 0 then item = 0 end
        local number = string.format("%.17g", item)
        feed("d" .. #number .. ":" .. number .. ";")
        return
      end
      if kind == "string" then
        feed("s" .. #item .. ":" .. item .. ";")
        return
      end
      if kind ~= "table" then error("packet hash rejects " .. kind, 3) end
      if getmetatable(item) ~= nil then
        error("packet hash rejects metatables", 3)
      end
      if depth >= maxDepth then error("packet hash depth limit", 3) end
      if active[item] then error("packet hash rejects cycles", 3) end

      active[item] = true
      local keys = {}
      for key in pairs(item) do
        if type(key) ~= "string" and type(key) ~= "number" then
          active[item] = nil
          error("packet hash rejects non-string and non-number keys", 3)
        end
        keys[#keys + 1] = key
        nodes = nodes + 1
        if nodes > maxNodes then
          active[item] = nil
          error("packet hash node limit", 3)
        end
      end
      table.sort(keys, keyOrder)
      feed("t" .. #keys .. "{")
      for _, key in ipairs(keys) do
        encode(key, depth + 1)
        encode(item[key], depth + 1)
      end
      feed(TABLE_SUFFIX)
      active[item] = nil
    end

    encode(value, 0)
    return table.concat(parts)
  end

  local function referenceAdler(text)
    local a, b = 1, 0
    for index = 1, #text do
      a = (a + text:byte(index)) % MOD
      b = (b + a) % MOD
    end
    return string.format("%08x", b * 65536 + a)
  end

  local function referenceCommandHash(command)
    if type(command) ~= "table" then error("command hash needs a table", 2) end
    local declarative = {}
    for key, value in pairs(command) do
      if not RUNTIME_FIELDS[key] then declarative[key] = value end
    end
    local payload = referenceBytes(declarative, {
      maxDepth = 16,
      maxNodes = 65536,
    })
    return referenceAdler(payload)
      .. referenceAdler(COMMAND_DOMAIN_PREFIX .. payload .. TABLE_SUFFIX)
  end

  local function finish(job, units)
    local done, result, steps = false, nil, 0
    while not done do
      done, result = job:step(units)
      steps = steps + 1
      if steps > 200000 then error("incremental hash did not finish") end
    end
    return result, steps
  end

  T.test("command hash composition matches the byte-fed reference", function()
    local longText = string.rep("payload:", 40) .. "\0tail"
    local mixed = {
      kind = "instances",
      owner = "differential",
      phase = "opaque_after_terrain",
      sequence = 91,
      cacheKey = "ignored",
      schemaVersion = 999,
      texture = function() end,
      payload = {
        [-7] = "negative",
        [0.5] = "fraction",
        [1] = "integer",
        ["1"] = "string",
        enabled = false,
        empty = {},
        long = longText,
        nested = {
          alpha = { true, false, 0, -0, 1 / 3 },
          beta = { z = "last", a = "first" },
        },
      },
    }
    local wide = {
      kind = "mesh",
      owner = "differential",
      phase = "background",
      geometry = {},
    }
    for index = 1, 96 do
      wide.geometry[("key:%03d"):format(97 - index)] = index
    end
    local wrappedLength = {
      kind = "mesh",
      owner = "differential",
      phase = "background",
      geometry = { label = string.rep("x", MOD + 129) },
    }

    for _, command in ipairs({ mixed, wide, wrappedLength }) do
      local expected = referenceCommandHash(command)
      T.equal(PacketHash.hashCommand(command), expected)
      for _, units in ipairs({ 1, 11, 101 }) do
        local actual, steps = finish(PacketHash.newCommandHashJob(command), units)
        T.equal(actual, expected)
        if units < 101 then T.truthy(steps > 1) end
      end
    end
  end)

  T.test("command hash composition preserves reference rejection limits", function()
    local tooDeep = { kind = "mesh" }
    local cursor = tooDeep
    for _ = 1, 20 do
      cursor.child = {}
      cursor = cursor.child
    end
    T.raises(function() referenceCommandHash(tooDeep) end, "depth limit")
    T.raises(function() PacketHash.hashCommand(tooDeep) end, "depth limit")
    T.raises(function()
      finish(PacketHash.newCommandHashJob(tooDeep), 101)
    end, "depth limit")

    local tooWide = { kind = "instances", items = {} }
    for index = 1, 65536 do tooWide.items[index] = true end
    T.raises(function() referenceCommandHash(tooWide) end, "node limit")
    T.raises(function() PacketHash.hashCommand(tooWide) end, "node limit")
    T.raises(function()
      finish(PacketHash.newCommandHashJob(tooWide), 101)
    end, "node limit")
  end)

  T.test("command hash composition preserves non-finite rejection", function()
    for _, value in ipairs({ 0 / 0, math.huge, -math.huge }) do
      local command = { kind = "mesh", geometry = { width = value } }
      T.raises(function() referenceCommandHash(command) end, "non%-finite")
      T.raises(function() PacketHash.hashCommand(command) end, "non%-finite")
      T.raises(function()
        finish(PacketHash.newCommandHashJob(command), 11)
      end, "non%-finite")
    end
  end)
end
