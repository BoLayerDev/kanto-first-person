return function(T)
  local ResourceOwner = T.loadCore("ResourceOwner")
  local TextureCatalog = assert(loadfile(T.root .. "/src/assets/TextureCatalog.lua"))()

  local function fixture(maxEntries)
    local owner, images = ResourceOwner.new(), {}
    local catalog = TextureCatalog.new({
      owner = owner,
      maxEntries = maxEntries or 3,
      newImage = function(path)
        local image = { path = path, releases = 0 }
        function image:release() self.releases = self.releases + 1 end
        images[#images + 1] = image
        return image
      end,
    })
    return catalog, owner, images
  end

  T.test("shared texture leases release after the last packet", function()
    local catalog, owner, images = fixture()
    local first, leaseA = catalog:acquire("assets/a.png")
    local second, leaseB = catalog:acquire("assets/a.png")
    T.equal(first, second)
    T.equal(#images, 1)
    T.equal(owner:count(), 1)
    leaseA:release("first")
    T.equal(images[1].releases, 0)
    leaseB:release("last")
    T.equal(images[1].releases, 1)
    T.equal(owner:count(), 0)
  end)

  T.test("a scope deduplicates paths and has idempotent release", function()
    local catalog, _, images = fixture()
    local scope = catalog:scope()
    local a = assert(scope:image("assets/a.png"))
    local b = assert(scope:image("assets/a.png"))
    T.equal(a, b)
    T.truthy(scope:used())
    T.truthy(scope:release())
    T.truthy(scope:release())
    T.equal(images[1].releases, 1)
  end)

  T.test("catalog capacity and paths fail closed", function()
    local catalog = fixture(1)
    local _, lease = catalog:acquire("assets/a.png")
    local image, _, err = catalog:acquire("assets/b.png")
    T.falsy(image)
    T.equal(err, "texture_catalog_full")
    image, _, err = catalog:acquire("../outside.png")
    T.falsy(image)
    T.equal(err, "invalid_asset_path")
    lease:release()
  end)

  T.test("dispose releases outstanding images exactly once", function()
    local catalog, owner, images = fixture()
    local _, lease = catalog:acquire("assets/a.png")
    T.truthy(catalog:dispose("test"))
    T.truthy(catalog:dispose("again"))
    lease:release("late")
    T.equal(images[1].releases, 1)
    T.equal(owner:count(), 0)
  end)
end
