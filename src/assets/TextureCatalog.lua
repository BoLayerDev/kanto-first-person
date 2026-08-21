-- Reference-counted packaged texture catalog.
--
-- KFP resolves its own mod assets and passes opaque image handles to a host.
-- A host may use a handle only during the draw callback. Scene packets keep
-- explicit leases, so an image is released after the last packet retires.

local TextureCatalog = {}
TextureCatalog.__index = TextureCatalog

local function emit(self, level, code, message, fields)
  local diagnostics = self._diagnostics
  if diagnostics and type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

local function validAsset(path)
  return type(path) == "string" and path:match("^assets/") ~= nil
    and #path <= 256
    and not path:find("..", 1, true)
    and not path:find("\\", 1, true)
end

local function count(entries)
  local total = 0
  for _ in pairs(entries) do total = total + 1 end
  return total
end

function TextureCatalog.new(options)
  options = options or {}
  if type(options.owner) ~= "table" or type(options.owner.own) ~= "function"
      or type(options.owner.release) ~= "function" then
    error("TextureCatalog needs a ResourceOwner", 2)
  end
  local maxEntries = math.floor(tonumber(options.maxEntries) or 8)
  if maxEntries < 1 or maxEntries > 64 then
    error("TextureCatalog maxEntries must be 1..64", 2)
  end
  return setmetatable({
    _owner = options.owner,
    _newImage = type(options.newImage) == "function" and options.newImage or nil,
    _diagnostics = options.diagnostics,
    _maxEntries = maxEntries,
    _entries = {},
    _disposed = false,
    _created = 0,
    _released = 0,
  }, TextureCatalog)
end

function TextureCatalog:available()
  return not self._disposed and self._newImage ~= nil
end

function TextureCatalog:_drop(entry, reason)
  if not entry or entry.released then return true end
  entry.released = true
  self._entries[entry.path] = nil
  local ok, err = self._owner:release(entry.image, reason or "texture_released")
  if ok then self._released = self._released + 1 end
  return ok, err
end

function TextureCatalog:acquire(path)
  if self._disposed then return nil, nil, "texture_catalog_disposed" end
  if not validAsset(path) then return nil, nil, "invalid_asset_path" end
  local entry = self._entries[path]
  if not entry then
    if not self._newImage then return nil, nil, "graphics_unavailable" end
    if count(self._entries) >= self._maxEntries then
      return nil, nil, "texture_catalog_full"
    end
    local ok, image, err = pcall(self._newImage, path)
    if not ok or image == nil then
      local problem = ok and err or image
      emit(self, "warn", "ASSET.TEXTURE_LOAD_FAILED", "A packaged texture could not be loaded.", {
        path = path,
        error = tostring(problem),
      })
      return nil, nil, tostring(problem or "texture_load_failed")
    end
    local owned, ownError = self._owner:own(image, function(value)
      local method = value and value.release
      if type(method) == "function" then method(value) end
    end, "texture:" .. path)
    if not owned then return nil, nil, tostring(ownError) end
    entry = { path = path, image = image, refs = 0, released = false }
    self._entries[path] = entry
    self._created = self._created + 1
  end
  entry.refs = entry.refs + 1
  local lease = { _catalog = self, _entry = entry, _released = false }
  function lease:release(reason)
    if self._released then return true end
    self._released = true
    local catalog, held = self._catalog, self._entry
    self._catalog, self._entry = nil, nil
    if not catalog or held.released then return true end
    held.refs = held.refs - 1
    if held.refs <= 0 then return catalog:_drop(held, reason or "texture_lease_released") end
    return true
  end
  return entry.image, lease
end

function TextureCatalog:scope()
  local catalog = self
  local held, order = {}, {}
  local scope = { _released = false }
  function scope:image(path)
    if self._released then return nil, "asset_scope_released" end
    local record = held[path]
    if record then return record.image end
    local image, lease, err = catalog:acquire(path)
    if not image then return nil, err end
    held[path] = { image = image, lease = lease }
    order[#order + 1] = held[path]
    return image
  end
  function scope:used()
    return #order > 0
  end
  function scope:release(reason)
    if self._released then return true end
    self._released = true
    local ok, errors = true, {}
    for index = #order, 1, -1 do
      local released, err = order[index].lease:release(reason or "asset_scope_released")
      if not released then ok, errors[#errors + 1] = false, tostring(err) end
      order[index] = nil
    end
    held = {}
    return ok, #errors > 0 and table.concat(errors, "; ") or nil
  end
  return scope
end

function TextureCatalog:dispose(reason)
  if self._disposed then return true end
  self._disposed = true
  local pending = {}
  for _, entry in pairs(self._entries) do pending[#pending + 1] = entry end
  for _, entry in ipairs(pending) do self:_drop(entry, reason or "texture_catalog_disposed") end
  return true
end

function TextureCatalog:status()
  local refs = 0
  for _, entry in pairs(self._entries) do refs = refs + entry.refs end
  return {
    available = self:available(),
    entries = count(self._entries),
    references = refs,
    capacity = self._maxEntries,
    created = self._created,
    released = self._released,
    disposed = self._disposed,
  }
end

return TextureCatalog
