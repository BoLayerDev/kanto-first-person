return function(T)
  local CommandBuffer = assert(loadfile(T.root .. "/src/render/CommandBuffer.lua"))()
  local SceneCompiler = assert(loadfile(T.root .. "/src/render/SceneCompiler.lua"))()
  local LRU = assert(loadfile(T.root .. "/src/core/LRU.lua"))()
  local PacketHash = assert(loadfile(T.root .. "/src/render/PacketHash.lua"))()
  local API = assert(loadfile(T.root .. "/companion/api_v1.lua"))()

  local function newBuffer()
    return CommandBuffer.new({
      hashCommand = PacketHash.hashCommand,
      newHashCommandJob = PacketHash.newCommandHashJob,
    })
  end

  T.test("scene compiler commits an atomic packet in feature order", function()
    local now = 0
    local features = {
      { id = "second", order = 20, compile = function(_, ctx, buffer)
          ctx.checkpoint()
          buffer:add("background", { kind = "mesh", owner = "second", sortKey = "b" })
        end },
      { id = "first", order = 10, compile = function(_, _, buffer)
          buffer:add("background", { kind = "mesh", owner = "first", sortKey = "a" })
        end },
    }
    local compiler = SceneCompiler.new({
      features = features,
      clock = function() now = now + 0.00001; return now end,
      newBuffer = newBuffer,
    })
    compiler:request({ key = "map:1", world = {}, config = {}, quality = {} })
    for _ = 1, 10 do compiler:step(2) end
    local packet = compiler:active()
    T.truthy(packet)
    T.equal(packet.metadata.key, "map:1")
    T.equal(packet.phases.background[1].owner, "first")
    T.equal(packet.phases.background[2].owner, "second")
    local status = compiler:status()
    T.equal(status.activeGeneration, packet.metadata.generation)
    T.equal(status.activeDrawCalls, 2)
    T.deepEqual(status.activeCommands, {
      commands = 2,
      batchItems = 0,
      phases = { background = 2 },
      kinds = { mesh = 2 },
      owners = { first = 1, second = 1 },
    })
    status.activeCommands.owners.first = 99
    T.equal(compiler:status().activeCommands.owners.first, 1)
  end)

  T.test("critical compilation failure preserves the active packet", function()
    local fail = false
    local feature = { id = "critical", compile = function(_, _, buffer)
      if fail then error("boom") end
      buffer:add("background", { kind = "mesh", owner = "critical" })
    end }
    local compiler = SceneCompiler.new({
      features = { feature },
      newBuffer = newBuffer,
    })
    compiler:request({ key = "good", world = {}, config = {}, quality = {} })
    compiler:step(2)
    compiler:step(2)
    local good = compiler:active()
    fail = true
    compiler:request({ key = "bad", world = {}, config = {}, quality = {} })
    compiler:step(2)
    T.equal(compiler:active(), good)
    T.equal(compiler:status().lastError.feature, "critical")
  end)

  T.test("optional compilation failure does not reject the scene", function()
    local features = {
      { id = "optional", critical = false, compile = function() error("optional") end },
      { id = "ok", compile = function(_, _, buffer)
          buffer:add("background", { kind = "mesh", owner = "ok" })
        end },
    }
    local compiler = SceneCompiler.new({
      features = features,
      newBuffer = newBuffer,
    })
    compiler:request({ key = "map", world = {}, config = {}, quality = {} })
    for _ = 1, 4 do compiler:step(2) end
    local packet = compiler:active()
    T.truthy(packet)
    T.truthy(packet.metadata.optionalErrors.optional)
  end)

  T.test("scene packets return from a bounded ownership cache", function()
    local compiled, released = 0, 0
    local function release() released = released + 1 end
    local cache = LRU.new({ maxCost = 1024 * 1024, maxEntries = 2,
      release = release })
    local compiler = SceneCompiler.new({
      cache = cache,
      releasePacket = release,
      features = { {
        id = "cached",
        compile = function(_, _, buffer)
          compiled = compiled + 1
          buffer:add("background", { kind = "mesh", owner = "cached" })
        end,
      } },
      newBuffer = newBuffer,
    })
    local function build(key)
      compiler:request({ key = key, world = {}, config = {}, quality = {} })
      for _ = 1, 3 do compiler:step(2) end
    end
    build("map:a")
    build("map:b")
    local _, cached = compiler:request({
      key = "map:a", world = {}, config = {}, quality = {},
    })
    T.truthy(cached)
    T.equal(compiled, 2)
    T.equal(compiler:active().metadata.key, "map:a")
    T.equal(compiler:status().cache.count, 1)
    compiler:dispose()
    T.equal(released, 2)
  end)

  T.test("asset-backed packets hold and release one explicit scope", function()
    local scopeCount, releaseCount = 0, 0
    local catalog = {}
    function catalog:scope()
      scopeCount = scopeCount + 1
      local used, released = false, false
      return {
        image = function(_, path)
          T.equal(path, "assets/legacy/horizons/backdrop.png")
          used = true
          return { name = path }
        end,
        used = function() return used end,
        release = function()
          if released then return true end
          released = true
          releaseCount = releaseCount + 1
          return true
        end,
      }
    end
    local compiler = SceneCompiler.new({
      features = { {
        id = "asset",
        compile = function(_, context, buffer)
          local image = assert(context.services.assets:image(
            "assets/legacy/horizons/backdrop.png"))
          buffer:add("background", {
            kind = "mesh", owner = "asset", texture = image,
          })
        end,
      } },
      newBuffer = newBuffer,
    })
    local function build(key)
      compiler:request({
        key = key, world = {}, config = {}, quality = {},
        services = { assets = catalog },
      })
      for _ = 1, 3 do compiler:step(2) end
    end
    build("asset:a")
    T.equal(compiler:active().metadata.cacheable, false)
    T.truthy(type(compiler:active().release) == "function")
    build("asset:b")
    T.equal(releaseCount, 1)
    compiler:dispose()
    T.equal(scopeCount, 2)
    T.equal(releaseCount, 2)
  end)

  T.test("superseded and disposed builds release unused asset scopes", function()
    local releases = 0
    local catalog = {}
    function catalog:scope()
      local released = false
      return {
        used = function() return false end,
        release = function()
          if not released then
            released = true
            releases = releases + 1
          end
          return true
        end,
      }
    end
    local compiler = SceneCompiler.new({
      features = { { id = "empty", compile = function() end } },
      newBuffer = newBuffer,
    })
    compiler:request({ key = "first", world = {}, config = {}, quality = {},
      services = { assets = catalog } })
    compiler:request({ key = "second", world = {}, config = {}, quality = {},
      services = { assets = catalog } })
    T.equal(releases, 1)
    compiler:dispose()
    T.equal(releases, 2)
  end)

  T.test("dense sealing is atomic and obeys deterministic slice budgets", function()
    local now = 0
    local buffer = CommandBuffer.new({
      hashCommand = PacketHash.hashCommand,
      newHashCommandJob = function(command)
        local inner = PacketHash.newCommandHashJob(command)
        return {
          step = function(_, units)
            now = now + units * 0.000001
            return inner:step(units)
          end,
        }
      end,
      maxBatchItems = 2048,
    })
    for z = 1, 64 do
      for x = 1, 64 do
        buffer:addBatchItem("opaque_after_terrain", "instances", "dense", {
          owner = "stress", material = "trees", sortKey = "trees",
          prototype = {
            primitive = "box",
            width = 1,
            height = 2,
            depth = 1,
            role = "terrain",
          },
        }, { x = x, y = (x + z) % 7, z = z })
      end
    end

    local compiler = SceneCompiler.new({
      features = {},
      newBuffer = function() return buffer end,
      clock = function() return now end,
    })
    compiler:request({ key = "stress:64x64", world = {}, config = {}, quality = {} })

    local completed, slices, maxSlice = false, 0, 0
    while not completed do
      local started = now
      completed = compiler:step(0.5)
      local elapsedMs = (now - started) * 1000
      maxSlice = math.max(maxSlice, elapsedMs)
      slices = slices + 1
      if not completed then T.equal(compiler:active(), nil) end
      if slices > 10000 then error("dense incremental seal did not finish") end
    end

    local packet = compiler:active()
    T.truthy(slices > 1)
    T.truthy(maxSlice <= 0.75, "seal slice exceeded Low tier tolerance")
    T.equal(packet.commandCount, 2)
    T.equal(#packet.phases.opaque_after_terrain, 2)
    T.equal(#packet.phases.opaque_after_terrain[1].items, 2048)
    T.equal(#packet.phases.opaque_after_terrain[2].items, 2048)
    for _, commands in pairs(packet.phases) do
      for _, command in ipairs(commands) do
        local ok, err = API.validate_draw_command(command, command.kind)
        T.truthy(ok, err)
      end
    end
    T.equal(packet.metadata.costBytes, 1024 + 2 * 256 + 4096 * 96)
  end)

  T.test("missing incremental seal surface preserves the active packet", function()
    local valid = true
    local compiler = SceneCompiler.new({
      features = { {
        id = "mesh",
        compile = function(_, _, buffer)
          buffer:add("background", { kind = "mesh", owner = "mesh" })
        end,
      } },
      newBuffer = function()
        if valid then return newBuffer() end
        return { seal = function() error("must not run synchronous seal") end }
      end,
    })
    compiler:request({ key = "good", world = {}, config = {}, quality = {} })
    for _ = 1, 10 do compiler:step(2) end
    local good = compiler:active()
    T.truthy(good)

    valid = false
    T.raises(function()
      compiler:request({ key = "bad", world = {}, config = {}, quality = {} })
    end, "beginSeal")
    T.equal(compiler:active(), good)
    T.equal(compiler:status().buildingKey, nil)
  end)

  T.test("malformed incremental seal job preserves the active packet", function()
    local valid = true
    local compiler = SceneCompiler.new({
      features = {},
      newBuffer = function()
        if valid then return newBuffer() end
        return { beginSeal = function() return {} end }
      end,
    })
    compiler:request({ key = "good", world = {}, config = {}, quality = {} })
    for _ = 1, 10 do compiler:step(2) end
    local good = compiler:active()
    T.truthy(good)

    valid = false
    compiler:request({ key = "bad", world = {}, config = {}, quality = {} })
    T.raises(function()
      compiler:step(2)
    end, "seal job with step")
    T.equal(compiler:active(), good)
    T.equal(compiler:status().buildingKey, nil)
  end)

  T.test("malformed completed packets release asset scopes exactly once", function()
    local function packetWithItems(items)
      return {
        phases = {
          background = {},
          opaque_after_terrain = { { items = items } },
          translucent_after_actors = {},
          shadow_casters = {},
          battle_opaque = {},
        },
        metadata = { key = "bad", generation = 2 },
        commandCount = 1,
        drawCalls = 1,
      }
    end
    for _, case in ipairs({
      {
        name = "nil packet",
        step = function() return true, nil end,
        error = "plain table",
      },
      {
        name = "invalid packet",
        step = function()
          return true, {
            phases = {},
            metadata = { key = "bad", generation = 2 },
            commandCount = 0,
            drawCalls = 0,
          }
        end,
        error = "missing a plain phase array",
      },
      {
        name = "non-Boolean completion",
        step = function() return 1, nil end,
        error = "Boolean completion flag",
      },
      {
        name = "early packet",
        step = function() return false, {} end,
        error = "must not return a packet",
      },
      {
        name = "empty items",
        step = function() return true, packetWithItems({}) end,
        error = "must not be empty",
      },
      {
        name = "sparse items",
        step = function()
          return true, packetWithItems({ [1] = {}, [3] = {} })
        end,
        error = "items must be dense",
      },
      {
        name = "nonnumeric item key",
        step = function() return true, packetWithItems({ item = {} }) end,
        error = "item keys must be positive integers",
      },
      {
        name = "negative item key",
        step = function() return true, packetWithItems({ [-1] = {} }) end,
        error = "item keys must be positive integers",
      },
      {
        name = "non-table item",
        step = function() return true, packetWithItems({ "invalid" }) end,
        error = "items must be plain tables",
      },
      {
        name = "metatable item",
        step = function()
          return true, packetWithItems({ setmetatable({}, {}) })
        end,
        error = "items must be plain tables",
      },
      {
        name = "item limit",
        step = function()
          local items = {}
          for index = 1, 8193 do items[index] = {} end
          return true, packetWithItems(items)
        end,
        error = "item limit exceeded",
      },
      {
        name = "packet command limit",
        step = function()
          return true, {
            phases = {
              background = {},
              opaque_after_terrain = {},
              translucent_after_actors = {},
              shadow_casters = {},
              battle_opaque = {},
            },
            metadata = { key = "bad", generation = 2 },
            commandCount = 8193,
            drawCalls = 8193,
          }
        end,
        error = "commandCount is invalid",
      },
    }) do
      local valid, releases = true, 0
      local catalog = {}
      function catalog:scope()
        return {
          used = function() return false end,
          release = function()
            releases = releases + 1
            return true
          end,
        }
      end
      local compiler = SceneCompiler.new({
        features = {},
        newBuffer = function()
          if valid then return newBuffer() end
          return {
            beginSeal = function()
              return { step = case.step }
            end,
          }
        end,
      })
      compiler:request({ key = "good", world = {}, config = {}, quality = {} })
      for _ = 1, 10 do compiler:step(2) end
      local good = compiler:active()
      T.truthy(good)

      valid = false
      compiler:request({
        key = "bad",
        world = {},
        config = {},
        quality = {},
        services = { assets = catalog },
      })
      T.raises(function()
        for _ = 1, 1024 do compiler:step(2) end
      end, case.error)
      T.equal(compiler:active(), good)
      T.equal(compiler:status().buildingKey, nil)
      T.equal(releases, 1)
      compiler:dispose()
      T.equal(releases, 1)
    end
  end)

  T.test("malformed hash jobs release asset scopes exactly once", function()
    for _, case in ipairs({
      { name = "nil", make = function() return nil end },
      { name = "missing step", make = function() return {} end },
      { name = "non-callable step", make = function() return { step = true } end },
    }) do
      local valid, factoryCalls, releases = true, 0, 0
      local catalog = {}
      function catalog:scope()
        return {
          used = function() return false end,
          release = function()
            releases = releases + 1
            return true
          end,
        }
      end
      local compiler = SceneCompiler.new({
        features = { {
          id = "mesh",
          compile = function(_, _, buffer)
            buffer:add("background", { kind = "mesh", owner = "mesh" })
          end,
        } },
        newBuffer = function()
          return CommandBuffer.new({
            hashCommand = PacketHash.hashCommand,
            newHashCommandJob = valid and PacketHash.newCommandHashJob or function()
              factoryCalls = factoryCalls + 1
              return case.make()
            end,
          })
        end,
      })
      compiler:request({ key = "good", world = {}, config = {}, quality = {} })
      for _ = 1, 10 do compiler:step(2) end
      local good = compiler:active()
      T.truthy(good)

      valid = false
      compiler:request({
        key = "bad",
        world = {},
        config = {},
        quality = {},
        services = { assets = catalog },
      })
      T.raises(function()
        for _ = 1, 32 do compiler:step(2) end
      end, "callable step")
      T.equal(factoryCalls, 1)
      T.equal(compiler:active(), good)
      T.equal(compiler:status().buildingKey, nil)
      T.equal(releases, 1)
      compiler:dispose()
      T.equal(releases, 1)
    end
  end)

  T.test("incremental seal faults preserve the active packet", function()
    local failHash = false
    local compiler = SceneCompiler.new({
      features = { {
        id = "mesh",
        compile = function(_, _, buffer)
          buffer:add("background", { kind = "mesh", owner = "mesh" })
        end,
      } },
      newBuffer = function()
        return CommandBuffer.new({
          hashCommand = PacketHash.hashCommand,
          newHashCommandJob = failHash and function()
            return { step = function() error("incremental hash boom") end }
          end or PacketHash.newCommandHashJob,
        })
      end,
    })
    compiler:request({ key = "good", world = {}, config = {}, quality = {} })
    for _ = 1, 10 do compiler:step(2) end
    local good = compiler:active()
    T.truthy(good)

    failHash = true
    compiler:request({ key = "bad", world = {}, config = {}, quality = {} })
    T.raises(function()
      for _ = 1, 10 do compiler:step(2) end
    end, "incremental hash boom")
    T.equal(compiler:active(), good)
    T.equal(compiler:status().buildingKey, nil)
  end)
end
