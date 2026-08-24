return function(T)
  local ResourceOwner = T.loadCore("ResourceOwner")
  local AudioBackend = assert(loadfile(T.root .. "/src/audio/AudioBackend.lua"))()

  local function fixture(maxOneShots)
    local created = {}
    local owner = ResourceOwner.new()
    local backend = AudioBackend.new({
      owner = owner,
      maxOneShots = maxOneShots or 2,
      newSource = function(path, sourceType)
        local source = {
          path = path,
          sourceType = sourceType,
          playing = false,
          releases = 0,
          plays = 0,
        }
        function source:setLooping(value) self.looping = value end
        function source:setVolume(value) self.volume = value end
        function source:play() self.playing = true; self.plays = self.plays + 1 end
        function source:stop() self.playing = false end
        function source:isPlaying() return self.playing end
        function source:release() self.releases = self.releases + 1 end
        created[#created + 1] = source
        return source
      end,
    })
    return backend, owner, created
  end

  T.test("streams one selected bed and releases the replaced source", function()
    local backend, owner, created = fixture()
    T.truthy(backend:playStream("route", "assets/route.mp3", 0.2))
    T.equal(created[1].sourceType, "stream")
    T.truthy(created[1].looping)
    T.equal(created[1].volume, 0.2)
    T.truthy(backend:playStream("town", "assets/town.mp3", 0.3))
    T.equal(created[1].releases, 1)
    T.equal(owner:count(), 1)
    T.equal(backend:status().stream, "town")
  end)

  T.test("one-shot sources reuse only after playback stops", function()
    local backend, _, created = fixture(2)
    T.truthy(backend:playOneShot("grass1", "assets/grass.mp3", 0.5))
    T.truthy(backend:playOneShot("grass1", "assets/grass.mp3", 0.5))
    T.equal(#created, 2)
    created[1].playing = false
    T.truthy(backend:playOneShot("grass1", "assets/grass.mp3", 0.6))
    T.equal(#created, 2)
    T.equal(created[1].plays, 2)
    T.equal(created[1].volume, 0.6)
  end)

  T.test("a full active one-shot pool drops work without growing", function()
    local backend, owner, created = fixture(1)
    T.truthy(backend:playOneShot("door", "assets/door.mp3", 0.5))
    local played, err = backend:playOneShot("step", "assets/step.mp3", 0.5)
    T.falsy(played)
    T.equal(err, "one_shot_pool_busy")
    T.equal(#created, 1)
    T.equal(owner:count(), 1)
    T.equal(backend:status().dropped, 1)
  end)

  T.test("invalid paths and unavailable audio fail closed", function()
    local owner = ResourceOwner.new()
    local backend = AudioBackend.new({ owner = owner })
    T.falsy(backend:available())
    local ok, err = backend:playStream("bad", "../outside.mp3", 1)
    T.falsy(ok)
    T.equal(err, "invalid_asset_path")
    ok, err = backend:playStream("safe", "assets/safe.mp3", 1)
    T.falsy(ok)
    T.equal(err, "audio_unavailable")
  end)

  T.test("backend clamps every stream and one-shot gain without clipping", function()
    local backend, _, created = fixture(4)
    T.truthy(backend:playStream("route", "assets/route.mp3", 2))
    T.equal(created[1].volume, 1)
    T.truthy(backend:setVolume("route", -1))
    T.equal(created[1].volume, 0)
    T.truthy(backend:setVolume("route", 0 / 0))
    T.equal(created[1].volume, 0)
    T.truthy(backend:playOneShot("door", "assets/door.mp3", math.huge))
    T.equal(created[2].volume, 1)
    T.truthy(backend:playOneShot("wood", "assets/wood.mp3", "invalid"))
    T.equal(created[3].volume, 0)
  end)

  T.test("dispose releases every source exactly once", function()
    local backend, owner, created = fixture(3)
    backend:playStream("route", "assets/route.mp3", 0.2)
    backend:playOneShot("a", "assets/a.mp3", 0.4)
    backend:playOneShot("b", "assets/b.mp3", 0.4)
    T.truthy(backend:dispose("test"))
    T.truthy(backend:dispose("again"))
    T.equal(owner:count(), 0)
    for _, source in ipairs(created) do T.equal(source.releases, 1) end
  end)
end
