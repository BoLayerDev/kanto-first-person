return function(T)
  local Client = assert(loadfile(T.root .. "/src/companion/Client.lua"))()

  local function provider(id, capabilities)
    local handle = { disposed = 0, invalidated = 0 }
    function handle:dispose() self.disposed = self.disposed + 1 end
    function handle:invalidate() self.invalidated = self.invalidated + 1 end
    local api = {
      api = 1,
      host = { id = id, version = "1.0.0" },
      capabilities = capabilities or {
        world_snapshot = 1,
        camera_delta = 1,
        render_phases = 1,
        quality_tier = 1,
      },
      register = function() return handle end,
    }
    return { exports = { voxel_companion = api } }, handle
  end

  T.test("client selects exactly one capability-compatible host", function()
    local mod, handle = provider("DRAMALESS_SHAPE")
    local client = Client.new({
      find = function(id) if id == "DRAMALESS_SHAPE" then return mod end end,
      spec = { id = "ds_fp_ceiling" },
    })
    T.truthy(client:resolve())
    T.equal(client:status().hostId, "DRAMALESS_SHAPE")
    T.equal(client:attach(), handle)
    client:invalidate("map")
    T.equal(handle.invalidated, 1)
    client:detach()
    T.equal(handle.disposed, 1)
  end)

  T.test("client refuses zero and multiple compatible hosts", function()
    local none = Client.new({ find = function() end, spec = {} })
    local match, err = none:resolve()
    T.falsy(match)
    T.equal(err, "no compatible voxel host")

    local a = provider("BATTLE_ART_VOXEL_FORK")
    local b = provider("DRAMALESS_SHAPE")
    local many = Client.new({
      find = function(id)
        if id == "BATTLE_ART_VOXEL_FORK" then return a end
        if id == "DRAMALESS_SHAPE" then return b end
      end,
      spec = {},
    })
    match, err = many:resolve()
    T.falsy(match)
    T.equal(err, "multiple compatible voxel hosts")
  end)

  T.test("client rejects missing required capabilities", function()
    local mod = provider("BATTLE_ART_VOXEL_FORK", { world_snapshot = 1 })
    local client = Client.new({
      find = function() return mod end,
      spec = {},
    })
    local match = client:resolve()
    T.falsy(match)
    T.equal(client:status().state, "inactive")
  end)

  T.test("client accepts only the exact API v1 capability set", function()
    for _, capabilities in ipairs({
      {
        world_snapshot = 1, camera_delta = 1, render_phases = 1,
        quality_tier = 1, draw_lights = 1,
      },
      {
        world_snapshot = 1, camera_delta = 1, render_phases = 1,
        quality_tier = "1",
      },
    }) do
      local mod = provider("BATTLE_ART_VOXEL_FORK", capabilities)
      local client = Client.new({
        find = function() return mod end,
        spec = {},
      })
      T.falsy(client:resolve())
      T.equal(client:status().state, "inactive")
    end

    T.raises(function()
      Client.new({
        find = function() end,
        spec = {},
        requiredCapabilities = { "render_phases", "draw_postprocess" },
      })
    end, "non%-standard API v1 capability")
  end)

  T.test("client rejects a provider whose descriptor names another host", function()
    local mod = provider("DRAMALESS_SHAPE")
    local client = Client.new({
      hostIds = { "BATTLE_ART_VOXEL_FORK" },
      find = function() return mod end,
      spec = {},
    })
    T.falsy(client:resolve())
    T.equal(client:status().state, "inactive")
  end)

  T.test("client isolates malformed candidates and resolves a later host", function()
    local conversion_calls = 0
    local hostile_error = setmetatable({}, {
      __tostring = function()
        conversion_calls = conversion_calls + 1
        error("host error conversion ran")
      end,
    })
    local broken_exports = {
      exports = setmetatable({}, {
        __index = function() error(hostile_error) end,
      }),
    }
    local broken_host = provider("BROKEN_HOST")
    broken_host.exports.voxel_companion.host = setmetatable({}, {
      __index = function() error(hostile_error) end,
    })
    local good = provider("GOOD_HOST")
    local client = Client.new({
      hostIds = { "BROKEN_EXPORTS", "BROKEN_HOST", "GOOD_HOST" },
      find = function(id)
        if id == "BROKEN_EXPORTS" then return broken_exports end
        if id == "BROKEN_HOST" then return broken_host end
        if id == "GOOD_HOST" then return good end
      end,
      spec = {},
    })

    local selected, err = client:resolve()
    T.truthy(selected, err)
    T.equal(client:status().hostId, "GOOD_HOST")
    T.equal(conversion_calls, 0)
  end)

  T.test("client captures the validated host register function", function()
    local mod, handle = provider("BATTLE_ART_VOXEL_FORK")
    local client = Client.new({
      find = function(id) if id == "BATTLE_ART_VOXEL_FORK" then return mod end end,
      spec = {},
    })
    T.truthy(client:resolve())
    mod.exports.voxel_companion.register = function()
      error("mutated provider register ran")
    end
    T.equal(client:attach(), handle)
  end)

  T.test("client gives the spec factory a copied validated descriptor", function()
    local mod, handle = provider("BATTLE_ART_VOXEL_FORK")
    local raw = mod.exports.voxel_companion
    raw.capabilities.shadow_pass = 1
    local descriptor
    local client = Client.new({
      find = function(id) if id == "BATTLE_ART_VOXEL_FORK" then return mod end end,
      spec = function(selected)
        descriptor = selected
        return { id = "ds_fp_ceiling" }
      end,
    })
    local selection = client:resolve()
    T.truthy(selection)
    selection.descriptor.host.id = "MUTATED_SELECTION"
    selection.descriptor.capabilities.shadow_pass = nil
    raw.host.id = "MUTATED_HOST"
    raw.host.version = "99.0.0"
    raw.capabilities.shadow_pass = nil
    raw.capabilities.draw_lights = 1
    T.equal(client:attach(), handle)
    T.notEqual(descriptor, raw)
    T.notEqual(descriptor.host, raw.host)
    T.notEqual(descriptor.capabilities, raw.capabilities)
    T.equal(descriptor.host.id, "BATTLE_ART_VOXEL_FORK")
    T.equal(descriptor.host.version, "1.0.0")
    T.equal(descriptor.capabilities.shadow_pass, 1)
    T.equal(descriptor.capabilities.draw_lights, nil)
  end)

  T.test("client validates registration handles", function()
    local mod = provider("BATTLE_ART_VOXEL_FORK")
    mod.exports.voxel_companion.register = function() return {} end
    local client = Client.new({
      find = function(id) if id == "BATTLE_ART_VOXEL_FORK" then return mod end end,
      spec = {},
    })
    local handle, err = client:attach()
    T.falsy(handle)
    T.truthy(err)
    T.equal(client:status().state, "failed")

    mod.exports.voxel_companion.register = function()
      return setmetatable({}, {
        __index = function() error("handle inspection failed") end,
      })
    end
    local guarded = Client.new({
      find = function(id) if id == "BATTLE_ART_VOXEL_FORK" then return mod end end,
      spec = {},
    })
    local ok, guardedHandle, guardedError = pcall(guarded.attach, guarded)
    T.truthy(ok)
    T.falsy(guardedHandle)
    T.truthy(guardedError)
  end)

  T.test("client captures validated handle lifecycle functions", function()
    local mod, handle = provider("BATTLE_ART_VOXEL_FORK")
    local client = Client.new({
      find = function(id) if id == "BATTLE_ART_VOXEL_FORK" then return mod end end,
      spec = {},
    })
    T.equal(client:attach(), handle)
    handle.invalidate = function() error("mutated invalidate ran") end
    handle.dispose = function() error("mutated dispose ran") end
    client:invalidate("map")
    client:detach()
    T.equal(handle.invalidated, 1)
    T.equal(handle.disposed, 1)
  end)

  T.test("client builds a host-specific registration descriptor", function()
    local mod, handle = provider("BATTLE_ART_VOXEL_FORK")
    mod.exports.voxel_companion.capabilities.shadow_pass = 1
    local registered
    mod.exports.voxel_companion.register = function(spec)
      registered = spec
      return handle
    end
    local client = Client.new({
      find = function(id) if id == "BATTLE_ART_VOXEL_FORK" then return mod end end,
      spec = function(selected)
        return {
          id = "ds_fp_ceiling",
          shadow = selected.capabilities.shadow_pass == 1,
        }
      end,
    })
    T.equal(client:attach(), handle)
    T.truthy(registered.shadow)
  end)
end
