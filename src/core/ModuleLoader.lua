-- Sandboxed module loader for mod-owned Lua source.
--
-- The caller injects mod:read and the sandbox-provided load function. This
-- module never uses package, require, io, love.filesystem, or a host path.

local ModuleLoader = {}
ModuleLoader.__index = ModuleLoader

local DEFAULT_MAX_BYTES = 4 * 1024 * 1024
local DEFAULT_MAX_MODULES = 256
local MAX_ID_BYTES = 192
local MAX_PATH_BYTES = 1024

local function safeId(id)
  if type(id) ~= "string" or id == "" or #id > MAX_ID_BYTES then return false end
  if id:sub(1, 1) == "." or id:sub(-1) == "."
      or id:find("..", 1, true) then
    return false
  end
  for segment in id:gmatch("[^.]+") do
    if not segment:match("^[%a_][%w_]*$") then return false end
  end
  return true
end

local function safeRelativePath(path)
  if type(path) ~= "string" or path == "" or #path > MAX_PATH_BYTES then
    return false
  end
  if path:sub(1, 1) == "/" or path:find("\\", 1, true)
      or path:find(":", 1, true) then
    return false
  end
  for segment in path:gmatch("[^/]+") do
    if segment == "" or segment == "." or segment == ".." then return false end
  end
  return not path:find("//", 1, true)
end

local function emit(diagnostics, level, code, message, fields)
  if diagnostics and type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

local function join(root, path)
  if not root or root == "" then return path end
  return root .. "/" .. path
end

function ModuleLoader.new(opts)
  opts = opts or {}
  assert(type(opts.read) == "function", "ModuleLoader needs a read(path) function")
  local compiler = opts.compile or loadstring or load
  assert(type(compiler) == "function", "ModuleLoader needs a Lua compiler")

  local root = opts.root or ""
  assert(root == "" or safeRelativePath(root), "ModuleLoader root must be relative")
  root = root:gsub("/+$", "")

  local maxBytes = math.floor(tonumber(opts.maxBytes) or DEFAULT_MAX_BYTES)
  local maxModules = math.floor(tonumber(opts.maxModules) or DEFAULT_MAX_MODULES)
  assert(maxBytes > 0, "ModuleLoader maxBytes must be positive")
  assert(maxModules > 0, "ModuleLoader maxModules must be positive")

  return setmetatable({
    read = opts.read,
    compile = compiler,
    environment = opts.environment,
    root = root,
    maxBytes = maxBytes,
    maxModules = maxModules,
    paths = {},
    cache = {},
    loaded = {},
    loading = {},
    loadedCount = 0,
    loadingCount = 0,
    pathCount = 0,
    stack = {},
    diagnostics = opts.diagnostics,
    counters = { reads = 0, compiles = 0, executions = 0,
                 hits = 0, failures = 0 },
  }, ModuleLoader)
end

function ModuleLoader:register(id, path)
  assert(safeId(id), "invalid module id: " .. tostring(id))
  assert(safeRelativePath(path), "invalid module path: " .. tostring(path))
  if self.loaded[id] or self.loading[id] then
    return false, "module_already_loaded"
  end
  local current = self.paths[id]
  if current and current ~= path then return false, "module_path_conflict" end
  if not current and self.pathCount >= self.maxModules then
    return false, "module_path_limit"
  end
  self.paths[id] = path
  if not current then self.pathCount = self.pathCount + 1 end
  return true
end

function ModuleLoader:pathFor(id)
  if not safeId(id) then return nil, "invalid_module_id" end
  local relative = self.paths[id] or (id:gsub("%.", "/") .. ".lua")
  if not safeRelativePath(relative) then return nil, "invalid_module_path" end
  return join(self.root, relative)
end

local function cycleMessage(stack, id)
  local first = 1
  for i = 1, #stack do
    if stack[i] == id then first = i; break end
  end
  local chain = {}
  for i = first, #stack do chain[#chain + 1] = stack[i] end
  chain[#chain + 1] = id
  return "circular module dependency: " .. table.concat(chain, " -> ")
end

function ModuleLoader:try(id)
  local path, pathErr = self:pathFor(id)
  if not path then return nil, pathErr end
  if self.loaded[id] then
    self.counters.hits = self.counters.hits + 1
    return self.cache[id]
  end
  if self.loading[id] then return nil, cycleMessage(self.stack, id) end
  if self.loadedCount + self.loadingCount >= self.maxModules then
    self.counters.failures = self.counters.failures + 1
    return nil, "module limit reached"
  end

  self.loading[id] = true
  self.loadingCount = self.loadingCount + 1
  self.stack[#self.stack + 1] = id

  local function fail(reason)
    self.loading[id] = nil
    self.loadingCount = self.loadingCount - 1
    self.stack[#self.stack] = nil
    self.counters.failures = self.counters.failures + 1
    local message = ("module %s (%s): %s"):format(id, path, tostring(reason))
    emit(self.diagnostics, "error", "CORE.MODULE_LOAD_FAILED", message,
      { module = id, path = path })
    return nil, message
  end

  self.counters.reads = self.counters.reads + 1
  local okRead, source, readErr = pcall(self.read, path)
  if not okRead then return fail(source) end
  if type(source) ~= "string" then
    return fail(readErr or "read returned no source")
  end
  if #source > self.maxBytes then
    return fail(("source is %d bytes; limit is %d"):format(#source, self.maxBytes))
  end
  if source:sub(1, 1) == "\27" then return fail("Lua bytecode is not allowed") end

  self.counters.compiles = self.counters.compiles + 1
  local okCompile, chunk, compileErr = pcall(self.compile, source, "@" .. path)
  if not okCompile then return fail(chunk) end
  if type(chunk) ~= "function" then return fail(compileErr or "compile failed") end
  if self.environment and setfenv then setfenv(chunk, self.environment) end

  self.counters.executions = self.counters.executions + 1
  local okRun, value = pcall(chunk, self)
  if not okRun then return fail(value) end
  if value == nil then value = true end

  self.cache[id] = value
  self.loaded[id] = true
  self.loading[id] = nil
  self.loadingCount = self.loadingCount - 1
  self.loadedCount = self.loadedCount + 1
  self.stack[#self.stack] = nil
  return value
end

function ModuleLoader:resolve(id)
  local value, err = self:try(id)
  if value == nil then error(err, 2) end
  return value
end

function ModuleLoader:preload(id, value)
  assert(safeId(id), "invalid module id: " .. tostring(id))
  assert(value ~= nil, "preloaded module value cannot be nil")
  if self.loaded[id] or self.loading[id] then return false, "module_already_loaded" end
  if self.loadedCount + self.loadingCount >= self.maxModules then
    return false, "module_limit"
  end
  self.cache[id], self.loaded[id] = value, true
  self.loadedCount = self.loadedCount + 1
  return true
end

function ModuleLoader:invalidate(id)
  if not safeId(id) then return false, "invalid_module_id" end
  if self.loading[id] then return false, "module_is_loading" end
  local existed = self.loaded[id] == true
  self.cache[id], self.loaded[id] = nil, nil
  if existed then self.loadedCount = self.loadedCount - 1 end
  return existed
end

function ModuleLoader:clear()
  if #self.stack > 0 then return false, "modules_are_loading" end
  self.cache, self.loaded, self.loading, self.stack = {}, {}, {}, {}
  self.loadedCount, self.loadingCount = 0, 0
  return true
end

function ModuleLoader:stats()
  local out = {}
  for key, value in pairs(self.counters) do out[key] = value end
  out.loaded = self.loadedCount
  out.loading = self.loadingCount
  out.maxModules = self.maxModules
  return out
end

ModuleLoader.safeId = safeId
ModuleLoader.safeRelativePath = safeRelativePath

return ModuleLoader
