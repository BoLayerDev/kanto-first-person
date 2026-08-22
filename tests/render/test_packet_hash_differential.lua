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

  local function referenceHash(value, limits)
    return referenceAdler(referenceBytes(value, limits))
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

  local function assertPacketMatchesReference(value, limits)
    local expected = referenceHash(value, limits)
    T.equal(PacketHash.hash(value, limits), expected)
    for _, units in ipairs({ 1, 11, 101 }) do
      local actual = finish(PacketHash.newJob(value, limits), units)
      T.equal(actual, expected)
    end
    return expected
  end

  local function assertCommandMatchesReference(command)
    local expected = referenceCommandHash(command)
    T.equal(PacketHash.hashCommand(command), expected)
    for _, units in ipairs({ 1, 11, 101 }) do
      local actual = finish(PacketHash.newCommandHashJob(command), units)
      T.equal(actual, expected)
    end
    return expected
  end

  local function newRandom(seed)
    return function(limit)
      seed = seed * 48271 % 2147483647
      return seed % limit + 1
    end
  end

  local function shuffledCopy(source, random)
    local result = {}
    for index = 1, #source do result[index] = source[index] end
    for index = #result, 2, -1 do
      local other = random(index)
      result[index], result[other] = result[other], result[index]
    end
    return result
  end

  T.test("packet hashing matches the legacy reference for mixed random shapes", function()
    local random = newRandom(99173)
    local shapes = {
      { "x", "y", "z", "kind" },
      { "alpha", "blue", "green", "red", "visible" },
      { "depth", "height", "material", "primitive", "width" },
      { "count", "phase", "radius", "seed", "speed", "strength" },
    }
    local records = {}
    for recordIndex = 1, 320 do
      local shape = shapes[random(#shapes)]
      local record = {}
      for _, key in ipairs(shuffledCopy(shape, random)) do
        local choice = random(5)
        if choice == 1 then
          record[key] = recordIndex % 2 == 0
        elseif choice == 2 then
          record[key] = (random(2001) - 1001) / 17
        elseif choice == 3 then
          record[key] = "value:" .. tostring(random(23))
        elseif choice == 4 then
          record[key] = { random(9), false, "nested:" .. tostring(random(7)) }
        else
          record[key] = { left = random(31), right = random(31) }
        end
      end
      records[recordIndex] = record
    end

    local value = {
      records = records,
      dense = { true, false, 0, -0, 1 / 3, "", "nul\0tail" },
      mixed = {
        [-9] = "negative",
        [0.25] = "fraction",
        [2] = "number",
        ["2"] = "string",
      },
      stringBoundaries = {
        string.rep("a", 63), string.rep("b", 64), string.rep("c", 65),
      },
    }
    assertPacketMatchesReference(value)
  end)

  T.test("verified layout reuse rejects absent extra and adversarial keys", function()
    local records = {}
    for index = 1, 192 do
      local record = { stable = index, enabled = index % 2 == 0 }
      for keyIndex = 1, 6 do
        record[("shape_%03d_%d"):format(index, keyIndex)] = keyIndex
      end
      records[#records + 1] = record
    end
    for index = 1, 128 do
      records[#records + 1] = index % 3 == 0
        and { alpha = index, beta = false, delta = "replacement" }
        or index % 3 == 1
        and { alpha = index, beta = false, gamma = "expected" }
        or { alpha = index, beta = false, gamma = "expected", extra = true }
    end

    local value = { records = records }
    local expected = assertPacketMatchesReference(value)
    records[#records].extra = false
    T.notEqual(assertPacketMatchesReference(value), expected)
  end)

  T.test("hash jobs release source tables after completion", function()
    local weak = setmetatable({}, { __mode = "k" })
    local value = { rows = {} }
    for index = 1, 256 do
      value.rows[index] = { kind = "row", x = index, enabled = index % 2 == 0 }
    end
    weak[value] = true
    local job = PacketHash.newJob(value)
    value = nil
    finish(job, 11)
    T.equal(job.thread, nil)
    collectgarbage("collect")
    collectgarbage("collect")
    T.equal(next(weak), nil)
  end)

  T.test("raw traversal does not invoke hostile table callbacks", function()
    local callbackCount = 0
    local hostile = setmetatable({ width = 16 }, {
      __index = function()
        callbackCount = callbackCount + 1
        error("hostile index callback ran")
      end,
      __pairs = function()
        callbackCount = callbackCount + 1
        error("hostile pairs callback ran")
      end,
      __metatable = "locked",
    })
    T.raises(function()
      PacketHash.hash({ geometry = hostile })
    end, "metatables")
    T.equal(callbackCount, 0)

    local hostileKey = setmetatable({}, {
      __tostring = function()
        callbackCount = callbackCount + 1
        error("hostile tostring callback ran")
      end,
    })
    T.raises(function()
      PacketHash.hash({ [hostileKey] = true })
    end, "non%-string and non%-number keys")
    T.equal(callbackCount, 0)
  end)

  T.test("two MiB strings preserve sync and incremental reference hashes", function()
    local payload = string.rep("0123456789abcdef", 131072)
    T.equal(#payload, 2 * 1024 * 1024)
    assertPacketMatchesReference({ kind = "payload", value = payload })
  end)

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

  T.test("all runtime-only command fields remain excluded", function()
    local first = {
      kind = "instances",
      owner = "runtime-exclusions",
      phase = "opaque_after_terrain",
      items = { { x = 1, y = 2, z = 3 } },
      cacheKey = "first",
      schemaVersion = 1,
      sequence = 2,
      texture = function() end,
      mesh = setmetatable({}, {}),
      resource = coroutine.create(function() end),
      model = function() end,
    }
    local second = {
      kind = first.kind,
      owner = first.owner,
      phase = first.phase,
      items = first.items,
      cacheKey = "second",
      schemaVersion = 999,
      sequence = 777,
      texture = {},
      mesh = function() end,
      resource = {},
      model = setmetatable({}, {}),
    }
    local expected = assertCommandMatchesReference(first)
    T.equal(assertCommandMatchesReference(second), expected)
    second.items = { { x = 2, y = 2, z = 3 } }
    T.notEqual(assertCommandMatchesReference(second), expected)
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

    local packetDepth = {}
    local packetCursor = packetDepth
    for _ = 1, 33 do
      packetCursor.child = {}
      packetCursor = packetCursor.child
    end
    T.raises(function() PacketHash.hash(packetDepth) end, "depth limit")
    T.raises(function()
      finish(PacketHash.newJob(packetDepth), 1)
    end, "depth limit")

    local packetWidth = {}
    for index = 1, 64 do packetWidth[index] = true end
    T.raises(function()
      PacketHash.hash(packetWidth, { maxNodes = 63 })
    end, "node limit")
    T.raises(function()
      finish(PacketHash.newJob(packetWidth, { maxNodes = 63 }), 1)
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
