return function(T)
  local CommandBuffer = assert(loadfile(T.root .. "/src/render/CommandBuffer.lua"))()
  local PacketHash = assert(loadfile(T.root .. "/src/render/PacketHash.lua"))()

  local function newBuffer(options)
    options = options or {}
    options.hashCommand = PacketHash.hashCommand
    return CommandBuffer.new(options)
  end

  T.test("command buffer sorts deterministically", function()
    local buffer = newBuffer()
    buffer:add("background", { kind = "mesh", owner = "b", sortKey = "z" })
    buffer:add("background", { kind = "mesh", owner = "a", sortKey = "a" })
    buffer:add("background", { kind = "mesh", owner = "c", sortKey = "a" })
    local packet = buffer:seal({ key = "map" })
    T.equal(packet.phases.background[1].owner, "a")
    T.equal(packet.phases.background[2].owner, "c")
    T.equal(packet.phases.background[3].owner, "b")
    T.equal(packet.drawCalls, 3)
    T.equal(packet.metadata.key, "map")
    T.equal(packet.metadata.schemaVersion, 1)
    local seen = {}
    for _, command in ipairs(packet.phases.background) do
      T.equal(command.schemaVersion, 1)
      T.truthy(command.cacheKey:match(
        "^kfp1:[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]:0:1:%d+:[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]$"))
      T.truthy(#command.cacheKey <= 64)
      T.falsy(seen[command.cacheKey])
      seen[command.cacheKey] = true
    end
  end)

  T.test("wire cache keys are deterministic per scene generation", function()
    local function build(key, generation)
      local buffer = newBuffer()
      buffer:add("background", {
        kind = "mesh", owner = "test", cacheKey = "untrusted",
      })
      return buffer:seal({ key = key, generation = generation })
        .phases.background[1].cacheKey
    end
    local first = build("red:PALLET_TOWN", 7)
    T.equal(first, build("red:PALLET_TOWN", 7))
    T.notEqual(first, build("red:PALLET_TOWN", 8))
    T.notEqual(first, build("red:ROUTE_1", 7))
    T.falsy(first:find("untrusted", 1, true))
  end)

  T.test("command buffer batches compatible items and segments capacity", function()
    local buffer = newBuffer({ maxBatchItems = 2 })
    local template = { owner = "rain", material = "rain", sortKey = "rain" }
    buffer:addBatchItem("translucent_after_actors", "billboards", "rain", template, { x = 1 })
    buffer:addBatchItem("translucent_after_actors", "billboards", "rain", template, { x = 2 })
    buffer:addBatchItem("translucent_after_actors", "billboards", "rain", template, { x = 3 })
    local packet = buffer:seal()
    T.equal(#packet.phases.translucent_after_actors, 2)
    T.equal(#packet.phases.translucent_after_actors[1].items, 2)
    T.equal(#packet.phases.translucent_after_actors[2].items, 1)
  end)

  T.test("sealed and bounded buffers reject writes", function()
    local buffer = newBuffer({ maxCommands = 1 })
    buffer:add("background", { kind = "mesh" })
    T.raises(function() buffer:add("background", { kind = "mesh" }) end)
    buffer:seal()
    T.raises(function() buffer:add("background", { kind = "mesh" }) end)
  end)

  T.test("unknown phases and command kinds fail closed", function()
    local buffer = newBuffer()
    T.raises(function() buffer:add("unknown", { kind = "mesh" }) end)
    T.raises(function() buffer:add("background", { kind = "filesystem" }) end)
  end)

  T.test("command buffers require an explicit canonical hash", function()
    T.raises(function() CommandBuffer.new() end, "needs hashCommand")
    local buffer = CommandBuffer.new({ hashCommand = function() return "0123abcd" end })
    buffer:add("background", { kind = "mesh" })
    T.raises(function() buffer:seal() end, "exactly 16")
  end)

  T.test("command and batch limits are finite integers", function()
    for _, options in ipairs({
      { maxCommands = 0 },
      { maxCommands = 8193 },
      { maxCommands = 1.5 },
      { maxBatchItems = 0 },
      { maxBatchItems = 8193 },
      { maxBatchItems = 1.5 },
    }) do
      options.hashCommand = PacketHash.hashCommand
      T.raises(function() CommandBuffer.new(options) end, "integer from 1 through")
    end
  end)

  T.test("scene generation is bounded before wire keys are assigned", function()
    for _, generation in ipairs({ -1, 1.5, 2147483648 }) do
      local buffer = newBuffer()
      buffer:add("background", { kind = "mesh" })
      T.raises(function() buffer:seal({ generation = generation }) end,
        "scene generation")
    end
  end)

  T.test("incremental sealing preserves synchronous packet semantics", function()
    local function populate(buffer)
      buffer:add("background", {
        kind = "mesh", owner = "later", sortKey = "z",
        geometry = { primitive = "box", width = 2 },
      })
      buffer:add("background", {
        kind = "mesh", owner = "first", sortKey = "a",
        geometry = { primitive = "box", width = 1 },
      })
      for index = 1, 40 do
        buffer:add("shadow_casters", {
          kind = "mesh",
          owner = "shadow:" .. index,
          sortKey = ("shadow:%02d"):format(41 - index),
          geometry = { primitive = "box", width = index },
        })
      end
      for index = 1, 5 do
        buffer:addBatchItem("opaque_after_terrain", "instances", "trees", {
          owner = "trees", material = "trees", sortKey = "trees",
        }, { x = index, z = 6 - index })
      end
      return buffer
    end

    local metadata = { key = "red:ROUTE_1", generation = 12 }
    local expected = populate(newBuffer({ maxBatchItems = 2 })):seal(metadata)
    local incremental = populate(newBuffer({
      maxBatchItems = 2,
      newHashCommandJob = PacketHash.newCommandHashJob,
    }))
    local job = incremental:beginSeal(metadata)
    local done, actual, steps = false, nil, 0
    while not done do
      done, actual = job:step(3)
      steps = steps + 1
      if steps > 10000 then error("incremental seal did not finish") end
    end
    T.truthy(steps > 1)
    T.deepEqual(actual, expected)
    T.raises(function() incremental:add("background", { kind = "mesh" }) end,
      "sealed")
  end)

  T.test("incremental sealing requires an incremental command hasher", function()
    T.raises(function()
      newBuffer({ newHashCommandJob = true })
    end, "must be a function")
    local buffer = newBuffer()
    buffer:add("background", { kind = "mesh" })
    T.raises(function() buffer:beginSeal() end, "newHashCommandJob")
  end)

  T.test("incremental sealing rejects malformed command hash jobs once", function()
    for _, case in ipairs({
      { name = "nil", make = function() return nil end },
      { name = "table without step", make = function() return {} end },
      { name = "non-callable step", make = function() return { step = true } end },
    }) do
      local calls = 0
      local buffer = newBuffer({
        newHashCommandJob = function()
          calls = calls + 1
          return case.make()
        end,
      })
      buffer:add("background", { kind = "mesh", owner = case.name })
      local job = buffer:beginSeal({ key = "malformed:" .. case.name })
      T.raises(function()
        for _ = 1, 32 do job:step(1) end
      end, "callable step")
      T.equal(calls, 1)
    end
  end)

  T.test("incremental sealing rejects non-finite work units", function()
    for _, units in ipairs({ math.huge, -math.huge, 0 / 0 }) do
      local buffer = newBuffer({
        newHashCommandJob = PacketHash.newCommandHashJob,
      })
      local job = buffer:beginSeal({ key = "units" })
      T.raises(function() job:step(units) end, "positive integer")
    end
  end)
end
