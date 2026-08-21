local Client = {}
Client.__index = Client

local DEFAULT_HOSTS = {
  "BATTLE_ART_VOXEL_FORK",
  "DRAMALESS_SHAPE",
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

local function report(self, level, code, message, fields)
  if self._diagnostics and self._diagnostics.emit then
    pcall(self._diagnostics.emit, self._diagnostics, level, code, message, fields)
  end
end

local function compatible(provider, required)
  if type(provider) ~= "table" then return false, "provider is not a table" end
  local api = provider.api
  if api ~= 1 then return false, "unsupported companion API" end
  local register = provider.register
  if type(register) ~= "function" then return false, "register is missing" end
  local host = provider.host
  local hostId = type(host) == "table" and host.id or nil
  if type(hostId) ~= "string" then
    return false, "host identity is missing"
  end
  local capabilities = provider.capabilities
  if type(capabilities) ~= "table" then capabilities = {} end
  for _, capability in ipairs(required) do
    if tonumber(capabilities[capability]) ~= 1 then
      return false, "missing capability: " .. capability
    end
  end
  local hostVersion = host.version
  return true, nil, {
    api = api,
    register = register,
    hostVersion = type(hostVersion) == "string" and hostVersion or nil,
  }
end

local function inspectCandidate(mod, required)
  if type(mod) ~= "table" then return nil end
  local exports = mod.exports
  if type(exports) ~= "table" then return nil end
  local provider = exports.voxel_companion
  if provider == nil then return nil end
  local valid, reason, connection = compatible(provider, required)
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
    _required = copyArray(options.requiredCapabilities or {
      "world_snapshot", "camera_delta", "render_phases", "quality_tier",
    }),
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
        pcall(inspectCandidate, modOrErr, self._required)
      if not inspected then
        rejected[#rejected + 1] = { id = id, reason = safeErrorText(provider) }
      elseif valid then
        matches[#matches + 1] = {
          id = id,
          mod = modOrErr,
          provider = provider,
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
  return self._selected
end

function Client:attach()
  if self._handle then return self._handle end
  local selected = self._selected or self:resolve()
  if not selected then return nil, self._error end
  local spec = self._spec
  if type(spec) == "function" then
    local okSpec, built = pcall(spec, selected.provider)
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
