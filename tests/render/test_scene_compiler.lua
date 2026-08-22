return function(T)
  local CommandBuffer = assert(loadfile(T.root .. "/src/render/CommandBuffer.lua"))()
  local SceneCompiler = assert(loadfile(T.root .. "/src/render/SceneCompiler.lua"))()
  local LRU = assert(loadfile(T.root .. "/src/core/LRU.lua"))()
  local PacketHash = assert(loadfile(T.root .. "/src/render/PacketHash.lua"))()

  local function newBuffer()
    return CommandBuffer.new({ hashCommand = PacketHash.hashCommand })
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
end
