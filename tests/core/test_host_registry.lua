return function(T)
  local HostRegistry = T.loadCore("HostRegistry")

  local function registry()
    return HostRegistry.new({
      gen1recomp = {
        capabilities = { "render.pipeline", "world.snapshot", "optional" },
        version = function(host) return host.version end,
        probe = function(host)
          return host and host.kind == "gen1recomp", "wrong_host_kind"
        end,
        bind = function(host)
          return {
            ["render.pipeline"] = function(value) return host.prefix .. value end,
            ["world.snapshot"] = host.snapshot,
            undeclared = "must not escape",
          }
        end,
      },
    })
  end

  T.test("resolves only known hosts and declared capabilities", function()
    local hosts = registry()
    local handle = assert(hosts:resolve("gen1recomp", {
      kind = "gen1recomp", version = "0.2.17", prefix = "fp:", snapshot = {},
    }, { "render.pipeline", "world.snapshot" }))
    T.equal(handle.id, "gen1recomp")
    T.equal(handle.version, "0.2.17")
    T.equal(handle:call("render.pipeline", "draw"), "fp:draw")
    T.truthy(handle:has("world.snapshot"))
    T.falsy(handle:has("optional"))
    T.equal(handle:get("undeclared"), nil)
    T.deepEqual(handle:capabilities(), { "render.pipeline", "world.snapshot" })
  end)

  T.test("fails closed for unknown host and missing capability", function()
    local hosts = registry()
    local handle, err = hosts:resolve("unknown", {})
    T.equal(handle, nil)
    T.equal(err, "unknown_host")
    handle, err = hosts:resolve("gen1recomp", { kind = "other" })
    T.equal(handle, nil)
    T.equal(err, "wrong_host_kind")
    handle, err = hosts:resolve("gen1recomp", {
      kind = "gen1recomp", prefix = "", snapshot = {},
    }, { "optional" })
    T.equal(handle, nil)
    T.equal(err, "missing_capability: optional")
  end)

  T.test("registry is sealed and descriptors are copied", function()
    local definition = { capabilities = { "stable" }, providers = { stable = 1 } }
    local hosts = HostRegistry.new({ fixed = definition })
    definition.providers.stable = 2
    T.equal(assert(hosts:resolve("fixed", {})):require("stable"), 1)
    local ok, err = hosts:register("late", { capabilities = {} })
    T.falsy(ok)
    T.equal(err, "registry_sealed")
    T.deepEqual(hosts:ids(), { "fixed" })
  end)

  T.test("capability call refuses non-functions", function()
    local hosts = HostRegistry.new({ fixed = {
      capabilities = { "value" }, providers = { value = 9 },
    } })
    local value, err = assert(hosts:resolve("fixed", {})):call("value")
    T.equal(value, nil)
    T.equal(err, "capability_not_callable")
  end)

  T.test("version and required-capability faults fail closed", function()
    local hosts = HostRegistry.new({ fixed = {
      capabilities = { "stable" },
      version = function() error("version unavailable") end,
    } })
    local handle, err = hosts:resolve("fixed", {}, { "stable" })
    T.equal(handle, nil)
    T.truthy(err:find("host_version_failed", 1, true))

    local normal = HostRegistry.new({ fixed = { capabilities = { "stable" } } })
    handle, err = normal:resolve("fixed", {}, "stable")
    T.equal(handle, nil)
    T.equal(err, "required_capabilities_must_be_a_list")
    handle, err = normal:resolve("fixed", {}, { {} })
    T.equal(handle, nil)
    T.equal(err, "invalid_required_capability")
  end)
end
