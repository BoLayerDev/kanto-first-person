return function(T)
  local ModuleLoader = T.loadCore("ModuleLoader")

  T.test("loads, caches, and invalidates sandbox-owned source", function()
    local reads = 0
    local sources = { ["src/core/Answer.lua"] = "return { value = 42 }" }
    local loader = ModuleLoader.new({
      root = "src/core",
      read = function(path) reads = reads + 1; return sources[path] end,
    })
    local first = loader:resolve("Answer")
    local second = loader:resolve("Answer")
    T.equal(first, second)
    T.equal(first.value, 42)
    T.equal(reads, 1)
    T.truthy(loader:invalidate("Answer"))
    T.equal(loader:resolve("Answer").value, 42)
    T.equal(reads, 2)
  end)

  T.test("supports explicit safe module paths", function()
    local seen
    local loader = ModuleLoader.new({ read = function(path)
      seen = path
      return "return 'ok'"
    end })
    T.truthy(loader:register("src.core.Special", "src/core/alternate.lua"))
    T.equal(loader:resolve("src.core.Special"), "ok")
    T.equal(seen, "src/core/alternate.lua")
  end)

  T.test("rejects traversal, absolute paths, and bytecode", function()
    local loader = ModuleLoader.new({ read = function() return "\27bad" end })
    local value, err = loader:try("Safe")
    T.equal(value, nil)
    T.truthy(err:find("bytecode", 1, true))
    T.raises(function() loader:resolve("../escape") end, "invalid_module_id")
    T.raises(function() loader:register("Safe.Path", "../escape.lua") end,
      "invalid module path")
  end)

  T.test("detects dependency cycles and can retry after failure", function()
    local sources = {
      ["a.lua"] = "local L = ...; return L:resolve('b')",
      ["b.lua"] = "local L = ...; return L:resolve('a')",
    }
    local loader = ModuleLoader.new({ read = function(path) return sources[path] end })
    local value, err = loader:try("a")
    T.equal(value, nil)
    T.truthy(err:find("a -> b -> a", 1, true))
    sources.b = nil
    sources["b.lua"] = "return { repaired = true }"
    T.truthy(loader:resolve("a").repaired)
  end)

  T.test("bounds module source and reports contextual failures", function()
    local loader = ModuleLoader.new({ maxBytes = 4,
      read = function() return "return true" end })
    local value, err = loader:try("Large")
    T.equal(value, nil)
    T.truthy(err:find("limit is 4", 1, true))

    local broken = ModuleLoader.new({ read = function() return "error('boom')" end })
    local _, runErr = broken:try("Broken")
    T.truthy(runErr:find("Broken", 1, true))
    T.truthy(runErr:find("boom", 1, true))
  end)

  T.test("binds an injected environment in LuaJIT tests", function()
    local loader = ModuleLoader.new({
      read = function() return "return SECRET" end,
      environment = { SECRET = 73 },
    })
    T.equal(loader:resolve("Secret"), 73)
  end)

  T.test("bounds cached modules and registered paths", function()
    local loader = ModuleLoader.new({ maxModules = 2,
      read = function(path) return "return " .. string.format("%q", path) end })
    T.equal(loader:resolve("One"), "One.lua")
    T.equal(loader:resolve("Two"), "Two.lua")
    local value, err = loader:try("Three")
    T.equal(value, nil)
    T.truthy(err:find("module limit", 1, true))
    T.truthy(loader:invalidate("One"))
    T.equal(loader:resolve("Three"), "Three.lua")
    T.equal(loader:stats().loaded, 2)

    local paths = ModuleLoader.new({ maxModules = 1,
      read = function() return "return true" end })
    T.truthy(paths:register("One", "one.lua"))
    local ok, reason = paths:register("Two", "two.lua")
    T.falsy(ok)
    T.equal(reason, "module_path_limit")
  end)
end
