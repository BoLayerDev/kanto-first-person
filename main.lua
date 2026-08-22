-- Kanto First Person 2.0 sandbox entry point.
-- All implementation modules are read from this mod and compiled in the
-- engine-provided sandbox. No engine-private module or filesystem API is used.

local function bootstrap(mod, path)
  local source, readError = mod:read(path)
  assert(type(source) == "string", readError or ("cannot read " .. path))
  local chunk, compileError = load(source, "@" .. path)
  assert(chunk, compileError)
  return chunk()
end

return function(mod)
  local ModuleLoader = bootstrap(mod, "src/core/ModuleLoader.lua")
  local loader = ModuleLoader.new({
    read = function(path) return mod:read(path) end,
    compile = load,
  })

  local Diagnostics = loader:resolve("src.core.Diagnostics")
  local diagnostics = Diagnostics.new({
    capacity = 128,
    rate = 1,
    burst = 4,
    sink = function(entry)
      local logger = mod.log and mod.log[entry.level]
      if type(logger) == "function" then
        logger(mod.log, "%s: %s", entry.code, entry.message)
      end
    end,
  })
  loader.diagnostics = diagnostics

  local App = loader:resolve("src.bootstrap.App")
  local clock
  if love and love.timer and type(love.timer.getTime) == "function" then
    clock = love.timer.getTime
  end
  local app = App.new({
    mod = mod,
    loader = loader,
    diagnostics = diagnostics,
    clock = clock,
  })
  app:start()

  -- The closure keeps the app alive without publishing mutable internals.
  mod.exports.kfp = {
    api = 1,
    version = mod.version,
    available = function() return app:available() end,
    status = function() return app:status() end,
    diagnostics = function(level) return diagnostics:snapshot(level) end,
  }
end
