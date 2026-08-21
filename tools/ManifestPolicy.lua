-- Strict JSON decoding and the local KFP manifest policy.

local ManifestPolicy = {}
local NULL = {}

local function skipWhitespace(source, position)
  while true do
    local byte = source:byte(position)
    if byte ~= 0x20 and byte ~= 0x09 and byte ~= 0x0a and byte ~= 0x0d then
      return position
    end
    position = position + 1
  end
end

local function utf8(codepoint)
  if codepoint <= 0x7f then return string.char(codepoint) end
  if codepoint <= 0x7ff then
    return string.char(0xc0 + math.floor(codepoint / 0x40),
      0x80 + codepoint % 0x40)
  end
  if codepoint <= 0xffff then
    return string.char(0xe0 + math.floor(codepoint / 0x1000),
      0x80 + math.floor(codepoint / 0x40) % 0x40,
      0x80 + codepoint % 0x40)
  end
  return string.char(0xf0 + math.floor(codepoint / 0x40000),
    0x80 + math.floor(codepoint / 0x1000) % 0x40,
    0x80 + math.floor(codepoint / 0x40) % 0x40,
    0x80 + codepoint % 0x40)
end

local function parseString(source, position)
  if source:sub(position, position) ~= '"' then
    return nil, position, "expected JSON string"
  end
  local pieces, start = {}, position + 1
  position = start
  while position <= #source do
    local byte = source:byte(position)
    if byte == 0x22 then
      pieces[#pieces + 1] = source:sub(start, position - 1)
      return table.concat(pieces), position + 1
    end
    if byte < 0x20 then return nil, position, "control byte in JSON string" end
    if byte == 0x5c then
      pieces[#pieces + 1] = source:sub(start, position - 1)
      local escape = source:sub(position + 1, position + 1)
      local simple = {
        ['"'] = '"', ["\\"] = "\\", ["/"] = "/", b = "\b",
        f = "\f", n = "\n", r = "\r", t = "\t",
      }
      if simple[escape] then
        pieces[#pieces + 1] = simple[escape]
        position = position + 2
      elseif escape == "u" then
        local hex = source:sub(position + 2, position + 5)
        if not hex:match("^%x%x%x%x$") then
          return nil, position, "invalid JSON unicode escape"
        end
        local codepoint = tonumber(hex, 16)
        position = position + 6
        if codepoint >= 0xd800 and codepoint <= 0xdbff then
          if source:sub(position, position + 1) ~= "\\u" then
            return nil, position, "missing JSON low surrogate"
          end
          local lowHex = source:sub(position + 2, position + 5)
          local low = lowHex:match("^%x%x%x%x$") and tonumber(lowHex, 16) or nil
          if not low or low < 0xdc00 or low > 0xdfff then
            return nil, position, "invalid JSON low surrogate"
          end
          codepoint = 0x10000 + (codepoint - 0xd800) * 0x400 + low - 0xdc00
          position = position + 6
        elseif codepoint >= 0xdc00 and codepoint <= 0xdfff then
          return nil, position, "unexpected JSON low surrogate"
        end
        pieces[#pieces + 1] = utf8(codepoint)
      else
        return nil, position, "invalid JSON escape"
      end
      start = position
    else
      position = position + 1
    end
  end
  return nil, position, "unterminated JSON string"
end

local parseValue

local function parseArray(source, position, kinds)
  local out = {}
  kinds[out] = "array"
  position = skipWhitespace(source, position + 1)
  if source:sub(position, position) == "]" then return out, position + 1 end
  while true do
    local value, nextPosition, err = parseValue(source, position, kinds)
    if err then return nil, nextPosition, err end
    out[#out + 1] = value
    position = skipWhitespace(source, nextPosition)
    local separator = source:sub(position, position)
    if separator == "]" then return out, position + 1 end
    if separator ~= "," then return nil, position, "expected comma in JSON array" end
    position = skipWhitespace(source, position + 1)
  end
end

local function parseObject(source, position, kinds)
  local out, seen = {}, {}
  kinds[out] = "object"
  position = skipWhitespace(source, position + 1)
  if source:sub(position, position) == "}" then return out, position + 1 end
  while true do
    local key, nextPosition, err = parseString(source, position)
    if err then return nil, nextPosition, err end
    if seen[key] then return nil, position, "duplicate JSON key: " .. key end
    seen[key] = true
    position = skipWhitespace(source, nextPosition)
    if source:sub(position, position) ~= ":" then
      return nil, position, "expected colon in JSON object"
    end
    position = skipWhitespace(source, position + 1)
    local value
    value, nextPosition, err = parseValue(source, position, kinds)
    if err then return nil, nextPosition, err end
    out[key] = value
    position = skipWhitespace(source, nextPosition)
    local separator = source:sub(position, position)
    if separator == "}" then return out, position + 1 end
    if separator ~= "," then return nil, position, "expected comma in JSON object" end
    position = skipWhitespace(source, position + 1)
  end
end

local function parseNumber(source, position)
  local start = position
  if source:sub(position, position) == "-" then position = position + 1 end
  local first = source:sub(position, position)
  if first == "0" then
    position = position + 1
  elseif first:match("[1-9]") then
    repeat position = position + 1
    until not source:sub(position, position):match("%d")
  else
    return nil, position, "invalid JSON number"
  end
  if source:sub(position, position) == "." then
    position = position + 1
    if not source:sub(position, position):match("%d") then
      return nil, position, "invalid JSON fraction"
    end
    repeat position = position + 1
    until not source:sub(position, position):match("%d")
  end
  local exponent = source:sub(position, position)
  if exponent == "e" or exponent == "E" then
    position = position + 1
    local sign = source:sub(position, position)
    if sign == "+" or sign == "-" then position = position + 1 end
    if not source:sub(position, position):match("%d") then
      return nil, position, "invalid JSON exponent"
    end
    repeat position = position + 1
    until not source:sub(position, position):match("%d")
  end
  local number = tonumber(source:sub(start, position - 1))
  if not number or number ~= number or number == math.huge or number == -math.huge then
    return nil, position, "JSON number is not finite"
  end
  return number, position
end

parseValue = function(source, position, kinds)
  local token = source:sub(position, position)
  if token == '"' then return parseString(source, position) end
  if token == "{" then return parseObject(source, position, kinds) end
  if token == "[" then return parseArray(source, position, kinds) end
  if source:sub(position, position + 3) == "true" then return true, position + 4 end
  if source:sub(position, position + 4) == "false" then return false, position + 5 end
  if source:sub(position, position + 3) == "null" then return NULL, position + 4 end
  return parseNumber(source, position)
end

local function decode(source)
  if type(source) ~= "string" then return nil, nil, "JSON source must be text" end
  local kinds = setmetatable({}, { __mode = "k" })
  local position = skipWhitespace(source, 1)
  local value, nextPosition, err = parseValue(source, position, kinds)
  if err then return nil, nil, err end
  nextPosition = skipWhitespace(source, nextPosition)
  if nextPosition <= #source then return nil, nil, "trailing JSON data" end
  return value, kinds
end

function ManifestPolicy.decode(source)
  local value, _, err = decode(source)
  return value, err
end

function ManifestPolicy.validate(source)
  local manifest, kinds, err = decode(source)
  if err then return nil, "manifest JSON is invalid: " .. err end
  if type(manifest) ~= "table" or kinds[manifest] ~= "object" then
    return nil, "manifest root must be a JSON object"
  end
  if manifest.id ~= "ds_fp_ceiling" then
    return nil, "manifest id must remain ds_fp_ceiling"
  end
  if manifest.api ~= 2 then return nil, "manifest API must be 2" end
  if manifest.profile ~= "overhaul" then
    return nil, "manifest profile must be overhaul"
  end
  if type(manifest.permissions) ~= "table"
      or kinds[manifest.permissions] ~= "array"
      or #manifest.permissions ~= 0 then
    return nil, "manifest permissions must stay empty"
  end
  if manifest.affects_link ~= true then
    return nil, "manifest affects_link must remain true"
  end
  return true
end

return ManifestPolicy
