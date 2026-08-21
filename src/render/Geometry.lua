local Geometry = {}

local function finite(value, name)
  value = tonumber(value)
  if not value or value ~= value or value == math.huge or value == -math.huge then
    error((name or "value") .. " must be finite", 3)
  end
  return value
end

local function positive(value, name)
  value = finite(value, name)
  if value <= 0 then error((name or "value") .. " must be positive", 3) end
  return value
end

local function material(value)
  if type(value) ~= "string" or value == "" then
    error("material must be a non-empty string", 3)
  end
  return value
end

function Geometry.box(x, y, z, width, height, depth, materialId, extra)
  return {
    primitive = "box",
    x = finite(x, "x"),
    y = finite(y, "y"),
    z = finite(z, "z"),
    width = positive(width, "width"),
    height = positive(height, "height"),
    depth = positive(depth, "depth"),
    material = material(materialId),
    extra = extra,
  }
end

function Geometry.plane(x, y, z, width, depth, materialId, extra)
  return {
    primitive = "plane",
    x = finite(x, "x"),
    y = finite(y, "y"),
    z = finite(z, "z"),
    width = positive(width, "width"),
    depth = positive(depth, "depth"),
    material = material(materialId),
    extra = extra,
  }
end

function Geometry.wall(x1, z1, x2, z2, y, height, thickness, materialId, extra)
  x1, z1 = finite(x1, "x1"), finite(z1, "z1")
  x2, z2 = finite(x2, "x2"), finite(z2, "z2")
  if x1 == x2 and z1 == z2 then error("wall needs two distinct points", 2) end
  return {
    primitive = "wall",
    x1 = x1,
    z1 = z1,
    x2 = x2,
    z2 = z2,
    y = finite(y, "y"),
    height = positive(height, "height"),
    thickness = positive(thickness, "thickness"),
    material = material(materialId),
    extra = extra,
  }
end

function Geometry.billboard(x, y, z, width, height, materialId, extra)
  return {
    primitive = "billboard",
    x = finite(x, "x"),
    y = finite(y, "y"),
    z = finite(z, "z"),
    width = positive(width, "width"),
    height = positive(height, "height"),
    material = material(materialId),
    extra = extra,
  }
end

return Geometry
