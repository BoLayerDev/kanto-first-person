return function(T)
  local Metrics = T.loadCore("Metrics")

  T.test("metrics retain a fixed rolling sample capacity", function()
    local now = 0
    local metrics = Metrics.new({ capacity = 8, clock = function() return now end })
    for index = 1, 12 do
      T.truthy(metrics:recordSeconds("update", index / 1000))
    end
    local status = metrics:snapshot()
    T.equal(status.schema, 1)
    T.equal(status.capacity, 8)
    T.equal(status.timing.update.retained, 8)
    T.equal(status.timing.update.total, 12)
    T.equal(status.timing.update.latest, 12)
    T.equal(status.timing.update.mean, 8.5)
    T.equal(status.timing.update.p95, 12)
    T.equal(status.timing.update.maximum, 12)
  end)

  T.test("metrics use the injected monotonic clock for scene readiness", function()
    local now = 10
    local metrics = Metrics.new({ capacity = 8, clock = function() return now end })
    T.truthy(metrics:sceneRequested("map:a"))
    now = 10.125
    T.truthy(metrics:sceneReady("map:a", false))
    T.falsy(metrics:sceneReady("map:a", false))
    metrics:sceneRequested("map:b")
    metrics:sceneRequested("map:c")
    now = 10.130
    metrics:sceneReady("map:c", true)
    local scene = metrics:snapshot().scene
    T.equal(scene.requests, 3)
    T.equal(scene.ready, 2)
    T.equal(scene.cacheHits, 1)
    T.equal(scene.superseded, 1)
    T.near(scene.readiness.latest, 5, 1e-9)
    T.falsy(scene.pending)
  end)

  T.test("metrics count render callbacks and accepted submissions", function()
    local metrics = Metrics.new({ capacity = 8, clock = function() return 0 end })
    metrics:rendered(0.001, 3)
    metrics:rendered(0.002, 0)
    local status = metrics:snapshot()
    T.equal(status.submissions.callbacks, 2)
    T.equal(status.submissions.commands, 3)
    T.equal(status.timing.render.latest, 2)
  end)

  T.test("metrics copy bounded runtime gauges into the status snapshot", function()
    local metrics = Metrics.new({ capacity = 8, clock = function() return 0 end })
    local status = metrics:snapshot({
      quality = "HIGH",
      cache = { count = 2, cost = 1024, secret = "excluded" },
      resources = { active = 3, disposed = false },
      textures = { entries = 4, references = 5 },
      audio = { oneShots = 2, stream = "town" },
    })
    T.equal(status.runtime.quality, "HIGH")
    T.equal(status.runtime.cache.cost, 1024)
    T.falsy(status.runtime.cache.secret)
    T.equal(status.runtime.resources.active, 3)
    T.equal(status.runtime.textures.references, 5)
    T.equal(status.runtime.audio.stream, "town")
  end)

  T.test("metrics reject invalid series and capacity", function()
    local metrics = Metrics.new({ capacity = 8, clock = function() return 0 end })
    local ok, err = metrics:recordSeconds("missing", 1)
    T.falsy(ok)
    T.equal(err, "unknown_series")
    T.raises(function() Metrics.new({ capacity = 7 }) end,
      "Metrics capacity must be an integer")
  end)
end
