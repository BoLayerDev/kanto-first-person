-- Explicit host registry. Unknown hosts and undeclared capabilities fail closed.

local HostRegistry = {}
HostRegistry.__index = HostRegistry

local function validId(id)
  return type(id) == "string" and id:match("^[%a][%w_%-]*$") ~= nil
end

local function validCapability(name)
  return type(name) == "string" and name:match("^[%a][%w_%.%-]*$") ~= nil
end

local function capabilitySet(value)
  assert(type(value) == "table", "host capabilities must be a table")
  local out = {}
  for key, item in pairs(value) do
    local name = type(key) == "number" and item or key
    assert(validCapability(name), "invalid capability id: " .. tostring(name))
    out[name] = true
  end
  return out
end

local function emit(diagnostics, level, code, message, fields)
  if diagnostics and type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

local function makeHandle(id, version, declared, providers)
  local handle = { id = id, version = version }

  function handle:has(name)
    return declared[name] == true and providers[name] ~= nil
      and providers[name] ~= false
  end

  function handle:get(name)
    if not declared[name] then return nil, "unknown_capability" end
    local value = providers[name]
    if value == nil or value == false then return nil, "capability_unavailable" end
    return value
  end

  function handle:require(name)
    local value, err = self:get(name)
    if value == nil then error(("host %s: %s (%s)"):format(id, name, err), 2) end
    return value
  end

  function handle:call(name, ...)
    local fn, err = self:get(name)
    if fn == nil then return nil, err end
    if type(fn) ~= "function" then return nil, "capability_not_callable" end
    return fn(...)
  end

  function handle:capabilities()
    local out = {}
    for name in pairs(declared) do
      if self:has(name) then out[#out + 1] = name end
    end
    table.sort(out)
    return out
  end

  return handle
end

function HostRegistry.new(definitions, opts)
  opts = opts or {}
  local self = setmetatable({
    definitions = {},
    sealed = false,
    diagnostics = opts.diagnostics,
  }, HostRegistry)
  for id, definition in pairs(definitions or {}) do
    assert(self:register(id, definition))
  end
  if opts.mutable ~= true then self:seal() end
  return self
end

function HostRegistry:register(id, definition)
  if self.sealed then return false, "registry_sealed" end
  assert(validId(id), "invalid host id: " .. tostring(id))
  assert(type(definition) == "table", "host definition must be a table")
  if self.definitions[id] then return false, "duplicate_host" end
  local capabilities = capabilitySet(definition.capabilities or {})
  assert(definition.probe == nil or type(definition.probe) == "function",
    "host probe must be a function")
  assert(definition.bind == nil or type(definition.bind) == "function",
    "host bind must be a function")
  assert(definition.version == nil or type(definition.version) == "function"
    or type(definition.version) == "string", "host version must be a string or function")
  local providers = {}
  for name, value in pairs(definition.providers or {}) do
    if capabilities[name] then providers[name] = value end
  end
  self.definitions[id] = {
    capabilities = capabilities,
    providers = providers,
    probe = definition.probe,
    bind = definition.bind,
    version = definition.version,
  }
  return true
end

function HostRegistry:seal()
  self.sealed = true
  return self
end

function HostRegistry:ids()
  local out = {}
  for id in pairs(self.definitions) do out[#out + 1] = id end
  table.sort(out)
  return out
end

function HostRegistry:resolve(id, host, required)
  if not validId(id) then return nil, "invalid_host_id" end
  if required ~= nil and type(required) ~= "table" then
    return nil, "required_capabilities_must_be_a_list"
  end
  local definition = self.definitions[id]
  if not definition then
    emit(self.diagnostics, "warn", "CORE.UNKNOWN_HOST", "Unknown host id",
      { host = id })
    return nil, "unknown_host"
  end

  if definition.probe then
    local ok, supported, reason = pcall(definition.probe, host)
    if not ok then return nil, "host_probe_failed: " .. tostring(supported) end
    if supported ~= true then return nil, reason or "host_not_supported" end
  end

  local providers = {}
  for name, value in pairs(definition.providers) do
    if definition.capabilities[name] then providers[name] = value end
  end
  if definition.bind then
    local ok, bound = pcall(definition.bind, host)
    if not ok then return nil, "host_bind_failed: " .. tostring(bound) end
    if type(bound) ~= "table" then return nil, "host_bind_returned_no_capabilities" end
    for name, value in pairs(bound) do
      if definition.capabilities[name] then providers[name] = value end
    end
  end

  local version = definition.version
  if type(version) == "function" then
    local ok, value = pcall(version, host)
    if not ok then return nil, "host_version_failed: " .. tostring(value) end
    version = value
  end
  local handle = makeHandle(id, version, definition.capabilities, providers)

  for _, name in ipairs(required or {}) do
    if not validCapability(name) then return nil, "invalid_required_capability" end
    if not definition.capabilities[name] then return nil, "unknown_capability: " .. name end
    if not handle:has(name) then return nil, "missing_capability: " .. name end
  end
  return handle
end

function HostRegistry:resolveHost(host, required)
  if type(host) ~= "table" then return nil, "host_descriptor_required" end
  return self:resolve(host.id, host, required)
end

HostRegistry.validId = validId
HostRegistry.validCapability = validCapability

return HostRegistry
