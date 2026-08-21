-- Rising-edge input for the optional Ledge Leap action.
--
-- A future engine adapter can inject small keyboard and gamepad facades here.
-- Alpha does not construct this module or install an input.step hook.

local InputBinding = {}
InputBinding.__index = InputBinding

local KEYS = { space = true, j = true, lctrl = true, off = true }
local PAD_BUTTONS = { y = true, x = true, off = true }
local MAX_GAMEPADS = 8

local function emitOnce(self, code, message, fields, key)
  key = key or code
  if self.reported[key] then return end
  self.reported[key] = true
  local diagnostics = self.diagnostics
  if diagnostics == nil then return end
  if type(diagnostics) == "function" then
    pcall(diagnostics, "warn", code, message, fields)
  elseif type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, "warn", code, message, fields)
  end
end

local function option(config, field, row, default)
  if type(config) ~= "table" then return default end
  if config[field] ~= nil then return config[field] end
  local values = config.values
  if type(values) == "table" then
    if values[field] ~= nil then return values[field] end
    if values[row] ~= nil then return values[row] end
  end
  return default
end

local function binding(self, value, allowed, kind)
  local text = type(value) == "string" and value:lower() or "off"
  if allowed[text] then return text end
  emitOnce(self, "GAMEPLAY.INPUT_BINDING_INVALID",
    "An invalid Ledge Leap input binding was treated as OFF.",
    { kind = kind, value = tostring(value) }, "binding:" .. kind .. ":" .. text)
  return "off"
end

local function keyboardDown(self, key)
  if key == "off" or not self.keyboard then return false end
  local ok, down = pcall(self.keyboard.isDown, self.keyboard, key)
  if not ok then
    emitOnce(self, "GAMEPLAY.KEYBOARD_READ_FAILED",
      "The Ledge Leap keyboard state could not be read.",
      { error = tostring(down) })
    return false
  end
  return down == true
end

local function controllerDown(self, controller, button, index)
  if type(controller) ~= "table" or type(controller.isDown) ~= "function" then
    emitOnce(self, "GAMEPLAY.GAMEPAD_INVALID",
      "A gamepad facade was invalid and was ignored.",
      { index = index }, "gamepad:invalid:" .. tostring(index))
    return false
  end
  if type(controller.isGamepad) == "function" then
    local okGamepad, isGamepad = pcall(controller.isGamepad, controller)
    if not okGamepad or isGamepad ~= true then return false end
  end
  local okButton, down = pcall(controller.isDown, controller, button)
  if not okButton then
    emitOnce(self, "GAMEPLAY.GAMEPAD_READ_FAILED",
      "A Ledge Leap gamepad state could not be read.",
      { index = index, error = tostring(down) }, "gamepad:read:" .. tostring(index))
    return false
  end
  if down ~= true then return false end

  -- Preserve the engine display-chord namespace. A held Back/Select button
  -- gives the face-button press back to the engine.
  local okBack, back = pcall(controller.isDown, controller, "back")
  return not (okBack and back == true)
end

local function gamepadDown(self, button)
  if button == "off" or not self.gamepads then return false end
  local ok, controllers = pcall(self.gamepads.list, self.gamepads)
  if not ok or type(controllers) ~= "table" then
    emitOnce(self, "GAMEPLAY.GAMEPAD_LIST_FAILED",
      "The Ledge Leap gamepad list could not be read.",
      { error = tostring(controllers) })
    return false
  end
  local count = math.min(#controllers, MAX_GAMEPADS)
  for index = 1, count do
    if controllerDown(self, controllers[index], button, index) then return true end
  end
  return false
end

function InputBinding.new(opts)
  opts = opts or {}
  if opts.keyboard ~= nil then
    assert(type(opts.keyboard) == "table"
      and type(opts.keyboard.isDown) == "function",
      "InputBinding keyboard needs isDown(key)")
  end
  if opts.gamepads ~= nil then
    assert(type(opts.gamepads) == "table" and type(opts.gamepads.list) == "function",
      "InputBinding gamepads needs list()")
  end
  return setmetatable({
    keyboard = opts.keyboard,
    gamepads = opts.gamepads,
    diagnostics = opts.diagnostics,
    reported = {},
    primed = false,
    enabled = false,
    key = "off",
    pad = "off",
    keyHeld = false,
    padHeld = false,
  }, InputBinding)
end

function InputBinding:reset()
  self.primed = false
  self.enabled = false
  self.keyHeld = false
  self.padHeld = false
end

function InputBinding:poll(config)
  local enabled = option(config, "ledge_leap", "ledge_leap", false) == true
  local key = binding(self, option(config, "ledge_key", "jumpkey", "off"),
    KEYS, "keyboard")
  local pad = binding(self, option(config, "ledge_pad", "jumppad", "off"),
    PAD_BUTTONS, "gamepad")

  if not enabled then
    self.enabled, self.key, self.pad = false, key, pad
    self.primed, self.keyHeld, self.padHeld = true, false, false
    return false
  end

  local keyDown = keyboardDown(self, key)
  local padDown = gamepadDown(self, pad)
  local changed = not self.primed or not self.enabled
    or key ~= self.key or pad ~= self.pad
  self.enabled, self.key, self.pad = true, key, pad
  if changed then
    -- A held control must be released after enable, reset, or rebinding.
    self.primed, self.keyHeld, self.padHeld = true, keyDown, padDown
    return false
  end

  local keyPressed = keyDown and not self.keyHeld
  local padPressed = padDown and not self.padHeld
  self.keyHeld, self.padHeld = keyDown, padDown
  if keyPressed then return true, "keyboard" end
  if padPressed then return true, "gamepad" end
  return false
end

InputBinding.MAX_GAMEPADS = MAX_GAMEPADS

return InputBinding
