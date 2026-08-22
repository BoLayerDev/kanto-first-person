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
    T.equal(PacketHash.hash(first), "4b031cf1")
  end)

  T.test("numeric frames are exact across runtimes and VM number tags", function()
    local minimumSubnormal = math.ldexp(1, -1074)
    local maximumSubnormal = math.ldexp(1, -1022) - minimumSubnormal
    local minimumNormal = math.ldexp(1, -1022)
    local maximumFinite = math.ldexp(2 - math.ldexp(1, -52), 1023)
    local previousBelowOne = 1 - math.ldexp(1, -53)
    local nextAboveOne = 1 + math.ldexp(1, -52)

    -- These goldens come from independent IEEE-754 bit fields, with no
    -- decimal formatter. They cover every boundary used by the binary frame.
    local vectors = {
      { "positive zero", 0.0, "065f01c1" },
      { "negative zero", -0.0, "065f01c1" },
      { "minimum subnormal", minimumSubnormal, "140001a7" },
      { "maximum subnormal", maximumSubnormal, "340807d9" },
      { "minimum normal", minimumNormal, "160801db" },
      { "maximum finite", maximumFinite, "344e07e0" },
      { "one tenth", 0.1, "23d004da" },
      { "one third", 1 / 3, "201003db" },
      { "previous below one", previousBelowOne, "342207dc" },
      { "one", 1, "162001dd" },
      { "next above one", nextAboveOne, "162201de" },
      { "negative one", -1, "1ba0025d" },
      { "positive int32 limit", 2147483647, "2f6105be" },
      { "negative int32 limit", -2147483648, "1cd6027c" },
      { "2^53 minus one", 9007199254740991, "36340811" },
      { "2^53", 9007199254740992, "18320212" },
      { "next double above 2^53", 9007199254740994, "18340213" },
      { "weather rounding tie", 638.746246337890625, "224c0375" },
      { "wildlife rounding tie", 273.620147705078125, "1c2d02ae" },
      { "negative wildlife tie", -273.620147705078125, "21ad032e" },
    }
    local hashes = {}
    for _, vector in ipairs(vectors) do
      local name, value, expected = vector[1], vector[2], vector[3]
      local actual = PacketHash.hash(value)
      T.equal(actual, expected, name)
      T.equal(#actual, 8, name)
      T.truthy(actual:match("^[0-9a-f]+$"), name)
      T.equal(finish(PacketHash.newJob(value), 1), expected, name)
      hashes[name] = actual
    end

    T.equal(PacketHash.hash(1), PacketHash.hash(1.0))
    T.equal(PacketHash.hash(1), PacketHash.hash(tonumber("1")))
    T.equal(PacketHash.hash(2147483647), PacketHash.hash(2147483647.0))
    T.equal(PacketHash.hash(2147483647),
      PacketHash.hash(tonumber("2147483647")))
    T.equal(PacketHash.hash(-2147483648), PacketHash.hash(-2147483648.0))
    T.equal(PacketHash.hash(-2147483648),
      PacketHash.hash(tonumber("-2147483648")))
    T.notEqual(hashes["previous below one"], hashes.one)
    T.notEqual(hashes.one, hashes["next above one"])
    T.notEqual(hashes["2^53 minus one"], hashes["2^53"])
    T.notEqual(hashes["2^53"], hashes["next double above 2^53"])

    local numericKeys = {
      [-2147483648] = "min",
      [0.1] = "tenth",
      [638.746246337890625] = "weather",
      [9007199254740991] = "exact",
    }
    T.equal(PacketHash.hash(numericKeys), "13f52194")
    T.equal(finish(PacketHash.newJob(numericKeys), 1), "13f52194")

    local prefixSafe = {
      booleanFalse = false,
      booleanTrue = true,
      numberOne = 1,
      numberZero = -0.0,
      stringFrame = "f",
      stringZero = "z;",
    }
    T.equal(PacketHash.hash(prefixSafe), "bba82bcd")
    T.notEqual(PacketHash.hash(false), PacketHash.hash(0))
    T.notEqual(PacketHash.hash(true), PacketHash.hash(1))
    T.notEqual(PacketHash.hash("f"), PacketHash.hash(1))
    T.notEqual(PacketHash.hash("z;"), PacketHash.hash(0))
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
    T.equal(PacketHash.hashCommand(first), "00ba338a899442a2")
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
