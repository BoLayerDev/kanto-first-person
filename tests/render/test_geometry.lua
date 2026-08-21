return function(T)
  local Geometry = assert(loadfile(T.root .. "/src/render/Geometry.lua"))()

  T.test("geometry creates normalized primitives", function()
    local box = Geometry.box(1, 2, 3, 4, 5, 6, "wall")
    T.equal(box.primitive, "box")
    T.equal(box.height, 5)
    T.equal(box.material, "wall")
    local wall = Geometry.wall(0, 0, 10, 0, 1, 8, 0.5, "stone")
    T.equal(wall.primitive, "wall")
  end)

  T.test("geometry rejects invalid dimensions and materials", function()
    T.raises(function() Geometry.box(0, 0, 0, 0, 1, 1, "x") end)
    T.raises(function() Geometry.plane(0, 0, 0, 1, 1, "") end)
    T.raises(function() Geometry.wall(0, 0, 0, 0, 0, 1, 1, "x") end)
    T.raises(function() Geometry.billboard(0 / 0, 0, 0, 1, 1, "x") end)
  end)
end
