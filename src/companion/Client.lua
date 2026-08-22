local Client = {}
Client.__index = Client

local DEFAULT_HOSTS = {
  "BATTLE_ART_VOXEL_FORK",
  "DRAMALESS_SHAPE",
}

local STANDARD_CAPABILITIES = {
  render_phases = true,
  camera_delta = true,
  terrain_patch = true,
  world_snapshot = true,
  quality_tier = true,
  shadow_pass = true,
  battle_pass = true,
  integrity_status = true,
}

local DEFAULT_REQUIRED_CAPABILITIES = {
  "world_snapshot",
  "camera_delta",
  "render_phases",
  "quality_tier",
}

local MAX_ERROR_LENGTH = 1024

local function safeErrorText(problem)
  local kind = type(problem)
  local message
  if kind == "string" then
    message = problem
  elseif kind == "number" or kind == "boolean" then
    message = tostring(problem)
  else
    message = "error value of type " .. kind
  end
  if #message > MAX_ERROR_LENGTH then
    return message:sub(1, MAX_ERROR_LENGTH) .. "..."
  end
  return message
end

local function copyArray(source)
  local out = {}
  for index, value in ipairs(source or {}) do out[index] = value end
  return out
end

local function copyRequiredCapabilities(source)
  if type(source) ~= "table" then
    error("requiredCapabilities must be a list", 3)
  end
  local out, seen = {}, {}
  for index, capability in ipairs(source) do
    if not STANDARD_CAPABILITIES[capability] then
      error("requiredCapabilities contains a non-standard API v1 capability", 3)
    end
    if seen[capability] then
      error("requiredCapabilities contains a duplicate capability", 3)
    end
    seen[capability] = true
    out[index] = capability
  end
  for key in pairs(source) do
    if type(key) ~= "number" or key < 1 or key > #out or key ~= math.floor(key) then
      error("requiredCapabilities must be a dense list", 3)
    end
  end
  return out
end

local function copyCapabilities(source)
  if type(source) ~= "table" then return nil, "capabilities are missing" end
  local out = {}
  for capability, version in pairs(source) do
    if type(capability) ~= "string" or not STANDARD_CAPABILITIES[capability] then
      return nil, "provider advertises a non-standard API v1 capability"
    end
    if version ~= 1 then
      return nil, "invalid capability version: " .. capability
    end
    out[capability] = 1
  end
  return out
end

local function copyDescriptor(connection)
  local capabilities = assert(copyCapabilities(connection.capabilities))
  return {
    api = connection.api,
    host = {
      id = connection.hostId,
      version = connection.hostVersion,
    },
    capabilities = capabilities,
    register = connection.register,
  }
end

local function copySelection(selected)
  return {
    id = selected.id,
    descriptor = copyDescriptor({
      api = selected.descriptor.api,
      hostId = selected.descriptor.host.id,
      hostVersion = selected.descriptor.host.version,
      capabilities = selected.descriptor.capabilities,
      register = selected.register,
    }),
    api = selected.api,
    register = selected.register,
    hostVersion = selected.hostVersion,
  }
end

local function report(self, level, code, message, fields)
  if self._diagnostics and self._diagnostics.emit then
    pcall(self._diagnostics.emit, self._diagnostics, level, code, message, fields)
  end
end

local function compatible(provider, required, expectedHostId)
  if type(provider) ~= "table" then return false, "provider is not a table" end
  local api = provider.api
  if api ~= 1 then return false, "unsupported companion API" end
  local register = provider.register
  if type(register) ~= "function" then return false, "register is missing" end
  local host = provider.host
  local hostId = type(host) == "table" and host.id or nil
  if type(hostId) ~= "string" or hostId == "" then
    return false, "host identity is missing"
  end
  if hostId ~= expectedHostId then return false, "host identity does not match mod id" end
  local hostVersion = host.version
  if type(hostVersion) ~= "string" or hostVersion == "" then
    return false, "host version is missing"
  end
  local capabilities, capabilityError = copyCapabilities(provider.capabilities)
  if not capabilities then return false, capabilityError end
  for _, capability in ipairs(required) do
    if capabilities[capability] ~= 1 then
      return false, "missing capability: " .. capability
    end
  end
  return true, nil, {
    api = api,
    register = register,
    hostId = hostId,
    hostVersion = hostVersion,
    capabilities = capabilities,
  }
end

local function inspectCandidate(mod, required, expectedHostId)
  if type(mod) ~= "table" then return nil end
  local exports = mod.exports
  if type(exports) ~= "table" then return nil end
  local provider = exports.voxel_companion
  if provider == nil then return nil end
  local valid, reason, connection = compatible(provider, required, expectedHostId)
  return provider, valid, reason, connection
end

function Client.new(options)
  options = options or {}
  if type(options.find) ~= "function" then error("Client needs find", 2) end
  if type(options.spec) ~= "table" and type(options.spec) ~= "function" then
    error("Client needs a registration spec or factory", 2)
  end
  return setmetatable({
    _find = options.find,
    _spec = options.spec,
    _diagnostics = options.diagnostics,
    _hostIds = copyArray(options.hostIds or DEFAULT_HOSTS),
    _required = copyRequiredCapabilities(
      options.requiredCapabilities or DEFAULT_REQUIRED_CAPABILITIES
    ),
    _selected = nil,
    _handle = nil,
    _handleDispose = nil,
    _handleInvalidate = nil,
    _state = "idle",
    _error = nil,
  }, Client)
end

function Client:resolve()
  local matches = {}
  local rejected = {}
  for _, id in ipairs(self._hostIds) do
    local ok, modOrErr = pcall(self._find, id)
    if ok and type(modOrErr) == "table" then
      local inspected, provider, valid, reason, connection =
        pcall(inspectCandidate, modOrErr, self._required, id)
      if not inspected then
        rejected[#rejected + 1] = { id = id, reason = safeErrorText(provider) }
      elseif valid then
        matches[#matches + 1] = {
          id = id,
          descriptor = copyDescriptor(connection),
          api = connection.api,
          register = connection.register,
          hostVersion = connection.hostVersion,
        }
      elseif provider ~= nil then
        rejected[#rejected + 1] = { id = id, reason = reason }
      end
    elseif not ok then
      rejected[#rejected + 1] = { id = id, reason = safeErrorText(modOrErr) }
    end
  end

  if #matches ~= 1 then
    self._selected = nil
    self._state = "inactive"
    self._error = #matches == 0 and "no compatible voxel host"
      or "multiple compatible voxel hosts"
    report(self, "warn", "COMPANION.HOST_SELECTION_FAILED", self._error, {
      compatible = #matches,
      rejected = rejected,
    })
    return nil, self._error
  end

  self._selected = matches[1]
  self._state = "resolved"
  self._error = nil
  return copySelection(self._selected)
end

function Client:attach()
  if self._handle then return self._handle end
  if not self._selected then self:resolve() end
  local selected = self._selected
  if not selected then return nil, self._error end
  local spec = self._spec
  if type(spec) == "function" then
    local okSpec, built = pcall(spec, copyDescriptor({
      api = selected.descriptor.api,
      hostId = selected.descriptor.host.id,
      hostVersion = selected.descriptor.host.version,
      capabilities = selected.descriptor.capabilities,
      register = selected.register,
    }))
    if not okSpec or type(built) ~= "table" then
      self._state = "failed"
      self._error = okSpec and "registration spec factory returned invalid data"
        or safeErrorText(built)
      report(self, "error", "COMPANION.SPEC_BUILD_FAILED",
        "KFP could not build a host-specific registration descriptor.", {
          host = selected.id,
          error = self._error,
        })
      return nil, self._error
    end
    spec = built
  end
  local ok, handle, err = pcall(selected.register, spec)
  if not ok then
    self._state = "failed"
    self._error = safeErrorText(handle)
    report(self, "error", "COMPANION.HOST_REGISTRATION_THREW", "Host registration threw", {
      host = selected.id,
      error = self._error,
    })
    return nil, self._error
  end
  local inspected, dispose, invalidate = pcall(function()
    if type(handle) ~= "table" then return nil, nil end
    return handle.dispose, handle.invalidate
  end)
  if not inspected or type(dispose) ~= "function"
      or (invalidate ~= nil and type(invalidate) ~= "function") then
    self._state = "failed"
    self._error = safeErrorText(inspected and
      (err or "host returned an invalid registration handle") or dispose)
    report(self, "error", "COMPANION.HOST_REGISTRATION_FAILED", self._error, { host = selected.id })
    return nil, self._error
  end
  self._handle = handle
  self._handleDispose = dispose
  self._handleInvalidate = invalidate
  self._state = "attached"
  return handle
end

function Client:invalidate(reason)
  if self._handle and self._handleInvalidate then
    local ok, err = pcall(self._handleInvalidate, self._handle, {}, reason)
    if not ok then
      report(self, "error", "COMPANION.HOST_INVALIDATE_FAILED", "Host invalidation failed", {
        error = safeErrorText(err),
      })
    end
  end
end

function Client:detach()
  local handle = self._handle
  local dispose = self._handleDispose
  self._handle = nil
  self._handleDispose = nil
  self._handleInvalidate = nil
  if handle and dispose then
    local ok, err = pcall(dispose, handle, {}, "client_detach")
    if not ok then
      report(self, "error", "COMPANION.HOST_DISPOSE_FAILED", "Host disposal failed", {
        error = safeErrorText(err),
      })
    end
  end
  self._selected = nil
  self._state = "idle"
end

function Client:status()
  return {
    state = self._state,
    error = self._error,
    hostId = self._selected and self._selected.id or nil,
    hostVersion = self._selected and self._selected.hostVersion or nil,
    api = self._selected and self._selected.api or nil,
  }
end

return Client
