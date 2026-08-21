local FeatureSet = {}
FeatureSet.__index = FeatureSet

local function report(self, code, message, fields)
  if self._diagnostics and self._diagnostics.emit then
    pcall(self._diagnostics.emit, self._diagnostics, "error", code, message, fields)
  end
end

function FeatureSet.new(options)
  options = options or {}
  local features = {}
  for _, feature in ipairs(options.features or {}) do features[#features + 1] = feature end
  table.sort(features, function(a, b)
    local ao, bo = tonumber(a.order) or 0, tonumber(b.order) or 0
    if ao ~= bo then return ao < bo end
    return tostring(a.id) < tostring(b.id)
  end)
  return setmetatable({
    _features = features,
    _camera = options.camera,
    _audio = options.audio,
    _diagnostics = options.diagnostics,
    _disabled = {},
  }, FeatureSet)
end

function FeatureSet:compilerFeatures()
  local out = {}
  for _, feature in ipairs(self._features) do
    if not self._disabled[feature.id] and type(feature.compile) == "function" then
      out[#out + 1] = feature
    end
  end
  if self._camera and not self._disabled[self._camera.id] then out[#out + 1] = self._camera end
  return out
end

local function guarded(self, feature, method, ...)
  if not feature or self._disabled[feature.id] or type(feature[method]) ~= "function" then return nil end
  local ok, result = pcall(feature[method], feature, ...)
  if not ok then
    self._disabled[feature.id] = tostring(result)
    report(self, "FEATURE.RUNTIME_FAILED", "Feature runtime callback failed", {
      feature = feature.id,
      method = method,
      error = tostring(result),
    })
    return nil
  end
  return result
end

function FeatureSet:update(frame, world, config)
  for _, feature in ipairs(self._features) do guarded(self, feature, "update", frame, world, config) end
  guarded(self, self._camera, "update", frame, config)
  guarded(self, self._audio, "update", frame, world, config)
end

function FeatureSet:cameraDelta(context)
  return guarded(self, self._camera, "modify", context) or {
    positionDelta = { x = 0, y = 0, z = 0 },
    rotationDelta = { yaw = 0, pitch = 0, roll = 0 },
    fovDelta = 0,
  }
end

function FeatureSet:cameraImpulse(kind)
  return guarded(self, self._camera, "impulse", kind)
end

function FeatureSet:oneShot(kind, config)
  return guarded(self, self._audio, "oneShot", kind, config) == true
end

function FeatureSet:invalidate(featureId)
  if featureId then
    self._disabled[featureId] = nil
    for _, feature in ipairs(self._features) do
      if feature.id == featureId then guarded(self, feature, "invalidate") end
    end
    if self._camera and self._camera.id == featureId then
      guarded(self, self._camera, "invalidate")
    end
    if self._audio and self._audio.id == featureId then
      guarded(self, self._audio, "invalidate")
    end
    return
  end
  self._disabled = {}
  for _, feature in ipairs(self._features) do guarded(self, feature, "invalidate") end
  guarded(self, self._camera, "invalidate")
  guarded(self, self._audio, "invalidate")
end

function FeatureSet:status()
  local disabled = {}
  for id, err in pairs(self._disabled) do disabled[id] = err end
  return { disabled = disabled }
end

function FeatureSet:dispose()
  for _, feature in ipairs(self._features) do guarded(self, feature, "dispose") end
  guarded(self, self._camera, "dispose")
  guarded(self, self._audio, "dispose")
end

return FeatureSet
