-- Ordered lifecycle coordinator with rollback and idempotent reverse teardown.
-- Component callbacks are closures, not methods. Signatures are:
-- start(context, lifecycle), update(dt, context, lifecycle),
-- invalidate(reason, context, lifecycle), and stop(reason, context, lifecycle).

local Lifecycle = {}
Lifecycle.__index = Lifecycle

Lifecycle.NEW = "new"
Lifecycle.STARTING = "starting"
Lifecycle.RUNNING = "running"
Lifecycle.STOPPING = "stopping"
Lifecycle.STOPPED = "stopped"
Lifecycle.FAILED = "failed"

local unpackValues = table.unpack or unpack

local function pack(...)
  return { n = select("#", ...), ... }
end

local function emit(diagnostics, level, code, message, fields)
  if diagnostics and type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

local function call(component, method, ...)
  local fn = component[method]
  if type(fn) ~= "function" then return true end
  local result = pack(pcall(fn, ...))
  if not result[1] then return false, result[2] end
  if result[2] == false then return false, result[3] or (method .. " refused") end
  return true, unpackValues(result, 2, result.n)
end

function Lifecycle.new(components, opts)
  opts = opts or {}
  local self = setmetatable({
    components = {},
    ids = {},
    started = {},
    state = Lifecycle.NEW,
    generation = 0,
    diagnostics = opts.diagnostics,
    lastError = nil,
  }, Lifecycle)
  for _, component in ipairs(components or {}) do
    assert(self:add(component))
  end
  return self
end

function Lifecycle:add(component)
  if self.state ~= Lifecycle.NEW then return false, "lifecycle_already_started" end
  assert(type(component) == "table", "lifecycle component must be a table")
  assert(type(component.id) == "string" and component.id ~= "",
    "lifecycle component needs an id")
  if self.ids[component.id] then return false, "duplicate_component" end
  self.ids[component.id] = true
  self.components[#self.components + 1] = component
  return true
end

function Lifecycle:_stopStarted(reason, context)
  local errors = {}
  for index = #self.started, 1, -1 do
    local component = self.started[index]
    self.started[index] = nil -- exactly once, even if stop throws
    local ok, err = call(component, "stop", reason, context, self)
    if not ok then
      errors[#errors + 1] = component.id .. ": " .. tostring(err)
      emit(self.diagnostics, "error", "CORE.LIFECYCLE_STOP_FAILED",
        tostring(err), { component = component.id, reason = tostring(reason) })
    end
  end
  return #errors == 0, errors
end

function Lifecycle:start(context)
  if self.state ~= Lifecycle.NEW then return false, "invalid_state: " .. self.state end
  self.state = Lifecycle.STARTING
  for _, component in ipairs(self.components) do
    self.started[#self.started + 1] = component
    local ok, err = call(component, "start", context, self)
    if not ok then
      self.lastError = component.id .. ": " .. tostring(err)
      emit(self.diagnostics, "error", "CORE.LIFECYCLE_START_FAILED",
        tostring(err), { component = component.id })
      self:_stopStarted("start_rollback", context)
      self.state = Lifecycle.FAILED
      return false, self.lastError
    end
  end
  self.generation = self.generation + 1
  self.state = Lifecycle.RUNNING
  return true
end

function Lifecycle:update(dt, context)
  if self.state ~= Lifecycle.RUNNING then return false, "invalid_state: " .. self.state end
  if type(dt) ~= "number" or dt ~= dt or dt < 0 or dt == math.huge then
    return false, "invalid_dt"
  end
  for _, component in ipairs(self.started) do
    local ok, err = call(component, "update", dt, context, self)
    if not ok then
      self.lastError = component.id .. ": " .. tostring(err)
      emit(self.diagnostics, "error", "CORE.LIFECYCLE_UPDATE_FAILED",
        tostring(err), { component = component.id })
      self.state = Lifecycle.STOPPING
      self:_stopStarted("update_failed", context)
      self.state = Lifecycle.FAILED
      return false, self.lastError
    end
  end
  return true
end

function Lifecycle:invalidate(reason, context)
  if self.state ~= Lifecycle.RUNNING then return false, "invalid_state: " .. self.state end
  local errors = {}
  for index = #self.started, 1, -1 do
    local component = self.started[index]
    local ok, err = call(component, "invalidate", reason or "invalidated", context, self)
    if not ok then
      errors[#errors + 1] = component.id .. ": " .. tostring(err)
      emit(self.diagnostics, "warn", "CORE.LIFECYCLE_INVALIDATE_FAILED",
        tostring(err), { component = component.id })
    end
  end
  self.generation = self.generation + 1
  return #errors == 0, #errors > 0 and table.concat(errors, "; ") or nil
end

function Lifecycle:stop(reason, context)
  if self.state == Lifecycle.STOPPED then return true end
  if self.state == Lifecycle.NEW then
    self.state = Lifecycle.STOPPED
    return true
  end
  if self.state == Lifecycle.STOPPING then return false, "already_stopping" end
  self.state = Lifecycle.STOPPING
  local ok, errors = self:_stopStarted(reason or "stopped", context)
  self.state = Lifecycle.STOPPED
  return ok, not ok and table.concat(errors, "; ") or nil
end

function Lifecycle:status()
  return { state = self.state, generation = self.generation,
           started = #self.started, error = self.lastError }
end

-- Return a function that invokes fn once and replays every returned value.
function Lifecycle.once(fn)
  assert(type(fn) == "function", "Lifecycle.once needs a function")
  local called, result = false, nil
  return function(...)
    if not called then
      result = pack(fn(...))
      called = true
    end
    return unpackValues(result, 1, result.n)
  end
end

-- Protect an optional integration edge and return fallback when it fails.
function Lifecycle.safe(fn, fallback, onError)
  assert(type(fn) == "function", "Lifecycle.safe needs a function")
  return function(...)
    local result = pack(pcall(fn, ...))
    if result[1] then return unpackValues(result, 2, result.n) end
    if type(onError) == "function" then pcall(onError, result[2]) end
    if type(fallback) == "function" then return fallback(result[2]) end
    return fallback
  end
end

return Lifecycle
