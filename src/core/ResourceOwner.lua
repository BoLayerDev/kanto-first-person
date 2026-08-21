-- LIFO resource ownership with idempotent, exactly-once cleanup.

local ResourceOwner = {}
ResourceOwner.__index = ResourceOwner

local function inferredRelease(resource)
  local kind = type(resource)
  if kind ~= "table" and kind ~= "userdata" then return nil end
  local ok, release = pcall(function() return resource.release end)
  if ok and type(release) == "function" then
    return function(value) return release(value) end
  end
  return nil
end

local function emit(diagnostics, level, code, message, fields)
  if diagnostics and type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

function ResourceOwner.new(opts)
  opts = opts or {}
  assert(opts.release == nil or type(opts.release) == "function",
    "ResourceOwner release must be a function")
  return setmetatable({
    defaultRelease = opts.release,
    diagnostics = opts.diagnostics,
    records = {},
    order = {},
    active = 0,
    disposed = false,
    releases = 0,
    errors = 0,
  }, ResourceOwner)
end

function ResourceOwner:_adopt(resource, releaser, label)
  if self.disposed then return nil, "owner_disposed" end
  local existing = self.records[resource]
  if existing and not existing.released then return resource, "already_owned" end
  releaser = releaser or self.defaultRelease or inferredRelease(resource)
  if type(releaser) ~= "function" then return nil, "resource_has_no_releaser" end
  local record = { resource = resource, releaser = releaser,
                   label = label, released = false }
  self.records[resource] = record
  self.order[#self.order + 1] = record
  self.active = self.active + 1
  return resource
end

function ResourceOwner:_compact()
  if self.disposed or #self.order <= self.active * 2 + 64 then return end
  local order = {}
  for index = 1, #self.order do
    local record = self.order[index]
    if record and not record.released then order[#order + 1] = record end
  end
  self.order = order
end

function ResourceOwner:own(resource, releaser, label)
  assert(resource ~= nil, "owned resource cannot be nil")
  if self.disposed then
    local release = releaser or self.defaultRelease or inferredRelease(resource)
    if release then pcall(release, resource, "owner_disposed", label) end
    return nil, "owner_disposed"
  end
  return self:_adopt(resource, releaser, label)
end

function ResourceOwner:defer(cleanup, label)
  assert(type(cleanup) == "function", "deferred cleanup must be a function")
  local token = {}
  local owned, err = self:own(token, function() cleanup() end, label)
  if not owned then return nil, err end
  return token
end

function ResourceOwner:_invoke(record, reason)
  if not record or record.released then return true end
  record.released = true -- before user code, for re-entrant disposal
  self.records[record.resource] = nil
  self.active = self.active - 1
  self.releases = self.releases + 1
  local ok, err = pcall(record.releaser, record.resource,
    reason or "released", record.label)
  if not ok then
    self.errors = self.errors + 1
    emit(self.diagnostics, "error", "CORE.RESOURCE_RELEASE_FAILED",
      tostring(err), { label = tostring(record.label or "") })
    self:_compact()
    return false, err
  end
  self:_compact()
  return true
end

function ResourceOwner:release(resource, reason)
  local record = self.records[resource]
  if not record then return false, "not_owned" end
  return self:_invoke(record, reason)
end

function ResourceOwner:transfer(resource, target)
  assert(getmetatable(target) == ResourceOwner,
    "resource transfer target must be a ResourceOwner")
  local record = self.records[resource]
  if not record or record.released then return false, "not_owned" end
  if target == self then return true end
  if target.disposed then return false, "target_disposed" end
  local targetRecord = target.records[resource]
  if targetRecord and not targetRecord.released then
    record.released = true
    self.records[resource] = nil
    self.active = self.active - 1
    self:_compact()
    return true
  end
  local adopted, err = target:_adopt(resource, record.releaser, record.label)
  if not adopted then return false, err end
  record.released = true -- transferred, not physically released
  self.records[resource] = nil
  self.active = self.active - 1
  self:_compact()
  return true
end

function ResourceOwner:child(label)
  local child = ResourceOwner.new({ diagnostics = self.diagnostics })
  local adopted, err = self:own(child,
    function(value, reason) value:dispose(reason) end, label or "child")
  if not adopted then return nil, err end
  return child
end

function ResourceOwner:dispose(reason)
  if self.disposed then return false, "already_disposed" end
  self.disposed = true
  local ok, errors = true, {}
  for index = #self.order, 1, -1 do
    local record = self.order[index]
    if record and not record.released then
      local released, err = self:_invoke(record, reason or "owner_disposed")
      if not released then
        ok = false
        errors[#errors + 1] = tostring(err)
      end
    end
    self.order[index] = nil
  end
  return ok, #errors > 0 and table.concat(errors, "; ") or nil
end

function ResourceOwner:count()
  return self.active
end

function ResourceOwner:stats()
  return { active = self:count(), releases = self.releases,
           errors = self.errors, disposed = self.disposed,
           orderSlots = #self.order }
end

return ResourceOwner
