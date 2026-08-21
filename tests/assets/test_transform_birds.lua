return function(T)
  local transform = assert(loadfile(T.root .. "/transform_birds.lua"))()

  local function image(width, height)
    local pixels = {}
    return {
      getWidth = function() return width end,
      getHeight = function() return height end,
      getPixel = function(_, x, y)
        local value = pixels[y * width + x + 1]
        if value then return unpack(value) end
        return 1, 1, 1, 1
      end,
      setPixel = function(_, x, y, r, g, b, a)
        pixels[y * width + x + 1] = { r, g, b, a }
      end,
      pixels = pixels,
    }
  end

  T.test("bird transform derives only player-owned available species", function()
    local source = image(8, 8)
    local written = {}
    local count = transform({
      exists = function(path) return path == "battle/front/pidgey.png" end,
      readImage = function() return source end,
      blank = function(width, height) return image(width, height) end,
      writeImage = function(value, path) written[path] = value end,
    })
    T.equal(count, 1)
    T.equal(written["birds/pidgey_a.png"], source)
    T.truthy(written["birds/pidgey_b.png"])
    T.equal(written["birds/pidgey_b.png"]:getWidth(), 8)
    T.equal(written["birds/pidgey_b.png"]:getHeight(), 8)
    T.falsy(written["birds/spearow_a.png"])
  end)

  T.test("bird transform fails closed for missing and invalid images", function()
    local writes = 0
    local count = transform({
      exists = function(path) return path == "battle/front/pidgey.png" end,
      readImage = function() return image(4, 4) end,
      blank = function(width, height) return image(width, height) end,
      writeImage = function() writes = writes + 1 end,
    })
    T.equal(count, 0)
    T.equal(writes, 0)
  end)
end
