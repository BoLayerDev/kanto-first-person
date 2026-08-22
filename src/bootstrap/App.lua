-- Composition root for Kanto First Person 2.0.
--
-- This is the only module that knows the Gen1recomp mod facade. Features get
-- constructor-injected pure services and never inspect broad engine state.

local App = {}
App.__index = App

local PHASES = {
  "background",
  "opaque_after_terrain",
  "translucent_after_actors",
}

local HOSTS = {
  "BATTLE_ART_VOXEL_FORK",
  "DRAMALESS_SHAPE",
}

local function emit(self, level, code, message, fields)
  if self.diagnostics and self.diagnostics.emit then
    pcall(self.diagnostics.emit, self.diagnostics, level, code, message, fields)
  end
end

local function safeCall(object, method, ...)
  local callback = type(object) == "table" and object[method]
  if type(callback) ~= "function" then return nil, "method_unavailable" end
  local ok, first, second = pcall(callback, object, ...)
  if not ok then return nil, tostring(first) end
  return first, second
end

local function monotonicClock()
  if love and love.timer and type(love.timer.getTime) == "function" then
    return love.timer.getTime()
  end
  return os.clock()
end

local function qualityValue(facade, field, method)
  if type(facade) ~= "table" then return nil end
  local value = facade[field]
  if type(value) == "string" then return value end
  value = safeCall(facade, method)
  if type(value) == "string" then return value end
  return nil
end

local function snapshotSource(value)
  if type(value) ~= "table" then return nil, "world facade is missing" end
  if type(value.snapshot) == "function" then
    local snapshot, err = safeCall(value, "snapshot")
    if type(snapshot) ~= "table" then
      return nil, err or "world snapshot is unavailable"
    end
    return snapshot
  end
  return value
end

local function sceneGenerationKey(config)
  local generations = config and config.group_generation or {}
  local parts = {}
  for _, group in ipairs({
    "geometry", "lighting", "sky", "weather", "flora",
    "particles", "camera", "streaming",
  }) do
    parts[#parts + 1] = group .. "=" .. tostring(generations[group] or 0)
  end
  return table.concat(parts, ",")
end

local function capabilityKey(capabilities)
  local parts = {}
  for name, version in pairs(type(capabilities) == "table" and capabilities or {}) do
    if tonumber(version) == 1 then parts[#parts + 1] = tostring(name) .. "=1" end
  end
  table.sort(parts)
  return table.concat(parts, ",")
end

function App.new(options)
  options = options or {}
  assert(type(options.mod) == "table", "App needs mod")
  assert(type(options.loader) == "table", "App needs loader")
  assert(type(options.diagnostics) == "table", "App needs diagnostics")
  return setmetatable({
    mod = options.mod,
    loader = options.loader,
    diagnostics = options.diagnostics,
    clock = options.clock or monotonicClock,
    state = "new",
    world = nil,
    worldIndex = nil,
    sceneKey = nil,
    config = nil,
    quality = nil,
    hostTier = "AUTO",
    hostCapabilities = {},
    hostId = "unknown",
    hostVersion = "unknown",
    platform = "",
    pendingDoorway = false,
    subscriptions = {},
  }, App)
end

function App:_loadModules()
  local L = self.loader
  self.modules = {
    Config = L:resolve("src.config.Config"),
    Quality = L:resolve("src.render.Quality"),
    LRU = L:resolve("src.core.LRU"),
    ResourceOwner = L:resolve("src.core.ResourceOwner"),
    Metrics = L:resolve("src.core.Metrics"),
    TextureCatalog = L:resolve("src.assets.TextureCatalog"),
    AudioBackend = L:resolve("src.audio.AudioBackend"),
    CommandBuffer = L:resolve("src.render.CommandBuffer"),
    PacketHash = L:resolve("src.render.PacketHash"),
    SceneCompiler = L:resolve("src.render.SceneCompiler"),
    Renderer = L:resolve("src.render.Renderer"),
    Client = L:resolve("src.companion.Client"),
    WorldSnapshot = L:resolve("src.companion.WorldSnapshot"),
    FeatureSet = L:resolve("src.features.FeatureSet"),
    Util = L:resolve("src.features.Util"),
  }
end

function App:_makeConfig()
  local Config = self.modules.Config
  local schema = Config.optionSchema()
  local present = {}
  for index = 1, #schema do
    local key = schema[index].key
    if self.mod.options:get(key) ~= nil then present[key] = true end
  end
  local legacyKeys = Config.legacyKeys()
  for index = 1, #legacyKeys do
    local key = legacyKeys[index]
    if self.mod.options:get(key) ~= nil then present[key] = true end
  end
  self.optionPresence = present
  self.mod.options:define(schema)
  local storage = {
    read = function(_, key) return self.mod.save:get(key) end,
    write = function(_, key, value)
      self.mod.save:set(key, value)
      return true
    end,
  }
  self.configService = Config.new({
    read = function(key)
      return self.mod.options:get(key), self.optionPresence[key] == true
    end,
    storage = storage,
    diagnostics = self.diagnostics,
  })
  self.config = self.configService:snapshot()
end

function App:_makeResources()
  self.resourceOwner = self.modules.ResourceOwner.new({
    diagnostics = self.diagnostics,
  })
  local audioOwner = assert(self.resourceOwner:child("audio"))
  local textureOwner = assert(self.resourceOwner:child("textures"))
  local newSource
  if love and love.audio and type(love.audio.newSource) == "function"
      and type(self.mod.assets) == "table"
      and type(self.mod.assets.path) == "function" then
    newSource = function(relative, sourceType)
      return love.audio.newSource(self.mod.assets:path(relative), sourceType)
    end
  end
  self.audioBackend = self.modules.AudioBackend.new({
    owner = audioOwner,
    newSource = newSource,
    maxOneShots = 8,
    diagnostics = self.diagnostics,
  })

  local newImage
  if love and love.graphics and type(love.graphics.newImage) == "function"
      and type(self.mod.assets) == "table"
      and type(self.mod.assets.path) == "function" then
    newImage = function(relative)
      local image = love.graphics.newImage(self.mod.assets:path(relative))
      local ok, err = pcall(function()
        if type(image.setFilter) == "function" then
          image:setFilter("nearest", "nearest")
        end
        if type(image.setWrap) == "function" then
          if relative:match("^assets/legacy/horizons/") then
            image:setWrap("repeat", "clamp")
          elseif relative:match("^assets/legacy/sky/") then
            image:setWrap("repeat", "repeat")
          else
            image:setWrap("clamp", "clamp")
          end
        end
      end)
      if not ok then
        if type(image.release) == "function" then pcall(image.release, image) end
        error("packaged texture configuration failed: " .. tostring(err), 0)
      end
      return image
    end
  end
  self.textureCatalog = self.modules.TextureCatalog.new({
    owner = textureOwner,
    newImage = newImage,
    maxEntries = 8,
    diagnostics = self.diagnostics,
  })
end

function App:_makeFeatures()
  local L, U = self.loader, self.modules.Util
  local constructors = {
    L:resolve("src.features.Interior"),
    L:resolve("src.features.Cave"),
    L:resolve("src.features.WorldGeometry"),
    L:resolve("src.features.Battle"),
    L:resolve("src.features.Atmosphere"),
    L:resolve("src.features.Flora"),
    L:resolve("src.features.Weather"),
    L:resolve("src.features.Wildlife"),
  }
  local features = {}
  for index, constructor in ipairs(constructors) do
    features[index] = constructor.new({ util = U })
  end
  self.camera = L:resolve("src.features.Camera").new({ util = U })
  self.audioFeature = L:resolve("src.features.Audio").new({
    util = U,
    facade = self.audioBackend,
  })
  self.featureSet = self.modules.FeatureSet.new({
    features = features,
    camera = self.camera,
    audio = self.audioFeature,
    diagnostics = self.diagnostics,
  })
end

function App:_makeRenderer()
  self.metrics = self.modules.Metrics.new({
    clock = self.clock,
    capacity = 240,
  })
  self.quality = self.modules.Quality.policy(
    self.config.quality,
    self.hostTier,
    self.platform
  )
  self.renderer = self.modules.Renderer.new({ diagnostics = self.diagnostics })
  local function releasePacket(packet, reason)
    if type(packet) == "table" and type(packet.release) == "function" then
      packet:release(reason)
    end
  end
  self.sceneCache = self.modules.LRU.new({
    maxCost = self.quality.cacheBytes,
    maxEntries = 32,
    release = releasePacket,
    diagnostics = self.diagnostics,
  })
  self.compiler = self.modules.SceneCompiler.new({
    diagnostics = self.diagnostics,
    features = self.featureSet:compilerFeatures(),
    newBuffer = function()
      return self.modules.CommandBuffer.new({
        maxCommands = 4096,
        maxBatchItems = 2048,
        hashCommand = self.modules.PacketHash.hashCommand,
        newHashCommandJob = self.modules.PacketHash.newCommandHashJob,
      })
    end,
    cache = self.sceneCache,
    releasePacket = releasePacket,
    clock = self.clock,
  })
end

function App:_sceneKey()
  if not self.world then return nil end
  return table.concat({
    self.world.key,
    "companion=1",
    "host=" .. tostring(self.hostId) .. "@" .. tostring(self.hostVersion),
    "caps=" .. capabilityKey(self.hostCapabilities),
    sceneGenerationKey(self.config),
    "quality=" .. tostring(self.quality.resolved),
  }, "|")
end

function App:_requestScene()
  local key = self:_sceneKey()
  self.sceneKey = key
  if not key then return false end
  local active = self.compiler:active()
  local activeKey = active and active.metadata and active.metadata.key or nil
  local _, cached = self.compiler:request({
    key = key,
    world = self.world,
    config = self.config,
    quality = self.quality,
    services = {
      capabilities = self.hostCapabilities,
      assets = self.textureCatalog,
    },
  })
  if cached == true then
    self.metrics:sceneRequested(key)
    self.metrics:sceneReady(key, true)
  elseif activeKey ~= key then
    self.metrics:sceneRequested(key)
  end
  return true
end

function App:_captureWorld(value, reason)
  local source, sourceError = snapshotSource(value)
  if not source then
    emit(self, "warn", "WORLD.SNAPSHOT_UNAVAILABLE",
      "The voxel host did not provide a world snapshot.",
      { reason = tostring(reason), error = tostring(sourceError) })
    return false
  end
  local snapshot, err = self.modules.WorldSnapshot.capture(source)
  if not snapshot then
    emit(self, "error", "WORLD.SNAPSHOT_INVALID",
      "The voxel host provided an invalid world snapshot.",
      { reason = tostring(reason), error = tostring(err) })
    return false
  end
  self.world = snapshot
  self.worldIndex = self.modules.WorldSnapshot.index(snapshot)
  if self.pendingDoorway then
    self.pendingDoorway = false
    self.featureSet:cameraImpulse("doorway")
    local tags = snapshot.tags or {}
    if not tags.cave and not tags.forest and not tags.tunnel then
      local sound = (tags.shop or tags.mart or tags.pokemon_center)
        and "shop_door" or "door"
      self.featureSet:oneShot(sound, self.config)
    end
  end
  self:_requestScene()
  return true
end

function App:_resolveQuality(tier, platform)
  if type(tier) == "string" then self.hostTier = tier end
  if type(platform) == "string" then self.platform = platform end
  local nextQuality = self.modules.Quality.policy(
    self.config.quality,
    self.hostTier,
    self.platform
  )
  local changed = not self.quality or nextQuality.resolved ~= self.quality.resolved
  self.quality = nextQuality
  if self.sceneCache then
    self.sceneCache:setLimits(nextQuality.cacheBytes, 32)
  end
  if changed and self.compiler then
    self.compiler:invalidate("quality_changed", false)
    self:_requestScene()
  end
end

function App:_attachServices(services)
  local quality = services.quality
  self:_resolveQuality(
    qualityValue(quality, "tier", "getTier"),
    qualityValue(quality, "platform", "getPlatform")
  )

  local integrity = services.integrity
  if type(integrity) == "table" and type(integrity.status) == "function" then
    local status, err = safeCall(integrity, "status")
    if type(status) ~= "table" then
      error("host integrity status failed: " .. tostring(err), 0)
    end
    if status.clean == false or status.legacyMarkers == true then
      error("legacy KFP splice markers detected; reinstall the voxel host", 0)
    end
  end
end

function App:_render(phase, context)
  local packet = self.compiler:active()
  if not packet or not packet.metadata or packet.metadata.key ~= self.sceneKey then
    return
  end
  local started = self.metrics:now()
  local submitted = self.renderer:renderPhase(packet, phase, context)
  self.metrics:rendered(self.metrics:now() - started, submitted)
end

function App:_update(context)
  local frame = type(context.frame) == "table" and context.frame or context
  local tier = type(frame) == "table" and frame.qualityTier or nil
  local platform = type(frame) == "table" and frame.platform or nil
  if type(tier) == "string" or type(platform) == "string" then
    self:_resolveQuality(tier, platform)
  end
  local updateStarted = self.metrics:now()
  local updated, updateError = pcall(
    self.featureSet.update,
    self.featureSet,
    frame,
    self.world,
    self.config
  )
  self.metrics:recordSeconds("update", self.metrics:now() - updateStarted)
  if not updated then error(updateError, 0) end
  local buildStarted = self.metrics:now()
  local completed, packet = self.compiler:step(self.quality.buildBudgetMs)
  self.metrics:recordSeconds("build", self.metrics:now() - buildStarted)
  if completed and type(packet) == "table" and packet.metadata then
    self.metrics:sceneReady(packet.metadata.key, false)
  end
  if completed and type(packet) == "table"
      and packet.drawCalls > self.quality.drawCallTarget then
    emit(self, "warn", "PERF.DRAW_CALL_TARGET_EXCEEDED",
      "The compiled KFP scene exceeds its quality-tier draw-call target.", {
        actual = packet.drawCalls,
        target = self.quality.drawCallTarget,
        quality = self.quality.resolved,
      })
  end
end

function App:_extensionSpec(provider)
  provider = type(provider) == "table" and provider or {}
  local capabilities = type(provider.capabilities) == "table"
    and provider.capabilities or {}
  local host = type(provider.host) == "table" and provider.host or {}
  self.hostId = type(host.id) == "string" and host.id or "unknown"
  self.hostVersion = type(host.version) == "string" and host.version or "unknown"
  self.hostCapabilities = {}
  for name, version in pairs(capabilities) do
    if tonumber(version) == 1 then self.hostCapabilities[name] = 1 end
  end
  local render = {}
  for _, phase in ipairs(PHASES) do
    local name = phase
    render[name] = function(context) self:_render(name, context) end
  end
  if tonumber(capabilities.shadow_pass) == 1 then
    render.shadow_casters = function(context)
      self:_render("shadow_casters", context)
    end
  end
  if tonumber(capabilities.battle_pass) == 1 then
    render.battle_opaque = function(context)
      self:_render("battle_opaque", context)
    end
  end
  return {
    api = 1,
    id = "ds_fp_ceiling.environment",
    name = "Kanto First Person",
    version = self.mod.version,
    priority = 110,
    requires = {
      "world_snapshot",
      "camera_delta",
      "render_phases",
      "quality_tier",
    },
    optional = {
      "shadow_pass",
      "battle_pass",
      "integrity_status",
    },
    attach = function(services) self:_attachServices(services) end,
    lifecycle = {
      start = function(context)
        if type(context.world) == "table" then
          self:_captureWorld(context.world, "start")
        end
      end,
    },
    worldChanged = function(snapshot)
      local source = type(snapshot.world) == "table" and snapshot.world or snapshot
      self:_captureWorld(source, "world_changed")
    end,
    update = function(frame)
      self:_update(frame)
    end,
    render = render,
    modifyCamera = function(camera)
      local source = type(camera.camera) == "table" and camera.camera or camera
      return self.featureSet:cameraDelta(source)
    end,
    invalidate = function(reason)
      self.compiler:invalidate(reason or "host_invalidated", false)
      self.renderer:invalidateAll()
      self.featureSet:invalidate()
      self:_requestScene()
    end,
    dispose = function()
      self:_disposeRuntime("host_dispose")
    end,
  }
end

function App:_connect()
  if self.runtimeDisposed then return false, "runtime_disposed" end
  if self.client:status().state == "attached" then return true end
  local handle, err = self.client:attach()
  if not handle then
    emit(self, "warn", "COMPANION.INACTIVE",
      "KFP is inactive until exactly one compatible voxel host is enabled.",
      { error = tostring(err) })
    return false
  end
  self.state = "attached"
  return true
end

function App:_optionChanged(event)
  if self.runtimeDisposed then return end
  if type(event) == "table" and event.mod and event.mod ~= self.mod.id then return end
  local changedKey = type(event) == "table" and event.key or nil
  if type(changedKey) == "string" and changedKey ~= "" then
    self.optionPresence[changedKey] = true
  end
  local previous = self.config
  local reason = {
    kind = "options_changed",
    key = changedKey,
  }
  self.config = self.configService:refresh(reason)
  if self.config == previous then return end
  self:_resolveQuality(self.hostTier, self.platform)
  self.compiler:invalidate("options_changed", false)
  self.renderer:invalidateAll()
  self.featureSet:invalidate()
  self:_requestScene()
end

function App:_mapEntered(event)
  if self.runtimeDisposed or type(event) ~= "table" then return end
  self.pendingDoorway = event.via == "warp"
end

function App:_worldStepped(event)
  if self.runtimeDisposed or type(event) ~= "table" or not self.world then return end
  if tostring(event.mapId) ~= tostring(self.world.id) then return end
  local x, z = tonumber(event.x), tonumber(event.y)
  if not x or not z then return end
  local cell = self.modules.WorldSnapshot.cell(
    self.world,
    self.worldIndex,
    math.floor(x),
    math.floor(z)
  )
  local tags = cell and cell.tags or {}
  local worldTags = self.world.tags or {}
  if tags.grass then
    self.featureSet:oneShot("grass", self.config)
  elseif worldTags.cave or tags.cave then
    self.featureSet:oneShot("cave", self.config)
  elseif worldTags.interior or worldTags.building or tags.interior then
    self.featureSet:oneShot("wood", self.config)
  end
end

function App:_disposeRuntime(reason)
  if self.runtimeDisposed then return end
  self.runtimeDisposed = true
  if self.featureSet then self.featureSet:dispose() end
  if self.compiler then self.compiler:dispose() end
  if self.textureCatalog then self.textureCatalog:dispose(reason) end
  if self.audioBackend then self.audioBackend:dispose(reason) end
  if self.resourceOwner then self.resourceOwner:dispose(reason) end
  self.world = nil
  self.sceneKey = nil
  self.state = "disposed"
  emit(self, "info", "CORE.RUNTIME_DISPOSED", "KFP runtime resources were released.", {
    reason = tostring(reason),
  })
end

function App:dispose(reason)
  if self.client then self.client:detach() end
  self:_disposeRuntime(reason or "app_dispose")
  for index = #self.subscriptions, 1, -1 do
    local unsubscribe = self.subscriptions[index]
    if type(unsubscribe) == "function" then pcall(unsubscribe) end
    self.subscriptions[index] = nil
  end
  return true
end

function App:start()
  if self.state ~= "new" then return false, "already_started" end
  self:_loadModules()
  self:_makeConfig()
  self:_makeResources()
  self:_makeFeatures()
  self:_makeRenderer()
  self.client = self.modules.Client.new({
    find = function(id) return self.mod.find(id) end,
    hostIds = HOSTS,
    spec = function(provider)
      return self:_extensionSpec(provider)
    end,
    diagnostics = self.diagnostics,
  })

  self.subscriptions[#self.subscriptions + 1] = self.mod.events:on(
    "mods.loaded",
    function() self:_connect() end
  )
  self.subscriptions[#self.subscriptions + 1] = self.mod.events:on(
    "game.ready",
    function() self:_connect() end
  )
  self.subscriptions[#self.subscriptions + 1] = self.mod.events:on(
    "mod.options_changed",
    function(event) self:_optionChanged(event) end
  )
  self.subscriptions[#self.subscriptions + 1] = self.mod.events:on(
    "map.entered",
    function(event) self:_mapEntered(event) end
  )
  self.subscriptions[#self.subscriptions + 1] = self.mod.events:on(
    "world.stepped",
    function(event) self:_worldStepped(event) end
  )
  self.subscriptions[#self.subscriptions + 1] = self.mod.hooks:wrap(
    "core.quit_to_launcher", function(nextQuit)
      local result = nextQuit()
      self:dispose("quit_to_launcher")
      return result
    end, 1000)

  self.state = "waiting_for_host"
  return true
end

function App:status()
  local client = self.client and self.client:status() or { state = "not_started" }
  local scene = self.compiler and self.compiler:status() or nil
  local audio = self.audioBackend and self.audioBackend:status() or nil
  local textures = self.textureCatalog and self.textureCatalog:status() or nil
  local resources = self.resourceOwner and self.resourceOwner:stats() or nil
  return {
    state = self.state,
    host = client,
    worldKey = self.world and self.world.key or nil,
    scene = scene,
    renderer = self.renderer and self.renderer:status() or nil,
    features = self.featureSet and self.featureSet:status() or nil,
    audio = audio,
    textures = textures,
    resources = resources,
    quality = self.quality and self.quality.resolved or nil,
    configGeneration = self.config and self.config.generation or nil,
    gameplay = { ledgeLeap = "unavailable_alpha" },
    metrics = self.metrics and self.metrics:snapshot({
      quality = self.quality and self.quality.resolved or nil,
      cache = scene and scene.cache or nil,
      resources = resources,
      textures = textures,
      audio = audio,
    }) or nil,
  }
end

function App:available()
  return self.state == "attached" and self.world ~= nil
end

return App
