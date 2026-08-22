return function(T)
  local PacketHash = assert(loadfile(T.root .. "/src/render/PacketHash.lua"))()

  local function finish(job, units)
    local done, result, steps = false, nil, 0
    while not done do
      done, result = job:step(units)
      steps = steps + 1
      if steps > 100000 then error("incremental hash did not finish") end
    end
    return result, steps
  end

  T.test("packet hashes ignore table insertion order", function()
    local first = { phase = "opaque", geometry = { x = 1, y = 2, z = 3 } }
    local second = { geometry = {}, phase = "opaque" }
    second.geometry.z = 3
    second.geometry.x = 1
    second.geometry.y = 2
    T.equal(PacketHash.hash(first), PacketHash.hash(second))
  end)

  T.test("packet hashes detect declarative geometry changes", function()
    local first = { phases = { background = { { kind = "mesh", width = 16 } } } }
    local second = { phases = { background = { { kind = "mesh", width = 17 } } } }
    T.notEqual(PacketHash.hash(first), PacketHash.hash(second))
    T.equal(PacketHash.hash(first), "8fac1be2")
  end)

  T.test("packet hashes reject unsafe and unbounded data", function()
    local cyclic = {}
    cyclic.self = cyclic
    T.raises(function() PacketHash.hash(cyclic) end, "cycles")
    T.raises(function() PacketHash.hash({ value = 0 / 0 }) end, "non%-finite")
    T.raises(function() PacketHash.hash(setmetatable({}, {})) end, "metatables")
    T.raises(function() PacketHash.hash({ a = 1, b = 2 }, { maxNodes = 1 }) end,
      "node limit")
  end)

  T.test("command hashes exclude callback-only resources but cover geometry", function()
    local textureA, textureB = {}, {}
    local first = {
      kind = "mesh", owner = "test", phase = "background", sequence = 1,
      geometry = { primitive = "box", width = 16, height = 8, depth = 4 },
      texture = textureA,
    }
    local second = {
      kind = "mesh", owner = "test", phase = "background", sequence = 1,
      geometry = { primitive = "box", width = 16, height = 8, depth = 4 },
      texture = textureB, cacheKey = "old", schemaVersion = 99,
    }
    T.equal(PacketHash.hashCommand(first), PacketHash.hashCommand(second))
    T.equal(PacketHash.hashCommand(first), "011e31dfb9e840f6")
    second.geometry.width = 17
    T.notEqual(PacketHash.hashCommand(first), PacketHash.hashCommand(second))
    T.truthy(PacketHash.hashCommand(first):match("^[0-9a-f]+$"))
    T.equal(#PacketHash.hashCommand(first), 16)
  end)

  T.test("incremental packet and command hashes preserve canonical bytes", function()
    local value = {
      phase = "opaque_after_terrain",
      items = {},
      nested = { enabled = true, count = 64 },
    }
    for index = 1, 64 do
      value.items[index] = { x = index, z = 65 - index }
    end
    local expectedPacket = PacketHash.hash(value)
    for _, units in ipairs({ 1, 7, 97 }) do
      local actual, steps = finish(PacketHash.newJob(value), units)
      T.equal(actual, expectedPacket)
      T.truthy(steps > 1)
    end

    local command = {
      kind = "instances",
      owner = "test",
      phase = "opaque_after_terrain",
      sequence = 7,
      items = value.items,
    }
    local expectedCommand = PacketHash.hashCommand(command)
    for _, units in ipairs({ 1, 11, 101 }) do
      local actual, steps = finish(PacketHash.newCommandHashJob(command), units)
      T.equal(actual, expectedCommand)
      T.truthy(steps > 1)
    end
  end)

  T.test("incremental hashing preserves large mixed-key ordering", function()
    local value = { [-4] = "negative", [0.5] = "fraction" }
    for index = 1, 96 do
      value[("key:%03d"):format(97 - index)] = index
    end
    local expected = PacketHash.hash(value)
    for _, units in ipairs({ 1, 13, 64 }) do
      local actual, steps = finish(PacketHash.newJob(value), units)
      T.equal(actual, expected)
      T.truthy(steps > 1)
    end
  end)

  T.test("incremental hashing rejects non-finite work units", function()
    for _, units in ipairs({ math.huge, -math.huge, 0 / 0 }) do
      local job = PacketHash.newJob({ value = "bounded" })
      T.raises(function() job:step(units) end, "positive integer")
    end
  end)
end
