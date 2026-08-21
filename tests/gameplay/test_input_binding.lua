return function(T)
  local InputBinding = assert(loadfile(T.root .. "/src/gameplay/InputBinding.lua"))()

  local function keyboard(state)
    local facade = { state = state or {}, reads = 0 }
    function facade:isDown(key)
      self.reads = self.reads + 1
      return self.state[key] == true
    end
    return facade
  end

  local function controller(state, gamepad)
    local facade = { state = state or {}, reads = 0, gamepad = gamepad ~= false }
    function facade:isGamepad() return self.gamepad end
    function facade:isDown(button)
      self.reads = self.reads + 1
      return self.state[button] == true
    end
    return facade
  end

  local function gamepads(controllers)
    local facade = { controllers = controllers or {}, reads = 0 }
    function facade:list()
      self.reads = self.reads + 1
      return self.controllers
    end
    return facade
  end

  local function config(extra)
    local out = { ledge_leap = true, ledge_key = "space", ledge_pad = "y" }
    for key, value in pairs(extra or {}) do out[key] = value end
    return out
  end

  local function diagnostics()
    local sink = { entries = {} }
    function sink:emit(level, code, message, fields)
      self.entries[#self.entries + 1] = {
        level = level, code = code, message = message, fields = fields,
      }
    end
    return sink
  end

  T.test("input binding validates injected facades", function()
    T.raises(function() InputBinding.new({ keyboard = {} }) end, "isDown")
    T.raises(function() InputBinding.new({ gamepads = {} }) end, "list")
    T.truthy(InputBinding.new({}))
  end)

  T.test("disabled Ledge Leap does not sample devices", function()
    local kb, pads = keyboard(), gamepads()
    local binding = InputBinding.new({ keyboard = kb, gamepads = pads })
    T.falsy(binding:poll(config({ ledge_leap = false })))
    T.equal(kb.reads, 0)
    T.equal(pads.reads, 0)
  end)

  T.test("keyboard emits only rising edges", function()
    local kb = keyboard()
    local binding = InputBinding.new({ keyboard = kb })
    T.falsy(binding:poll(config())) -- prime an enabled binding while up
    kb.state.space = true
    local pressed, source = binding:poll(config())
    T.truthy(pressed)
    T.equal(source, "keyboard")
    T.falsy(binding:poll(config()))
    kb.state.space = false
    T.falsy(binding:poll(config()))
    kb.state.space = true
    T.truthy(binding:poll(config()))
  end)

  T.test("gamepad emits rising edges and Back suppresses the face button", function()
    local pad = controller()
    local binding = InputBinding.new({ gamepads = gamepads({ pad }) })
    T.falsy(binding:poll(config()))
    pad.state.y = true
    local pressed, source = binding:poll(config())
    T.truthy(pressed)
    T.equal(source, "gamepad")
    T.falsy(binding:poll(config()))
    pad.state.y = false
    binding:poll(config())
    pad.state.y, pad.state.back = true, true
    T.falsy(binding:poll(config()))
    pad.state.back = false
    -- The face button is still physically held. Back release can expose it as
    -- one new edge, which matches the aggregate sampled action state.
    T.truthy(binding:poll(config()))
  end)

  T.test("OFF bindings never read their device facade", function()
    local kb, pads = keyboard({ space = true }), gamepads({ controller({ y = true }) })
    local binding = InputBinding.new({ keyboard = kb, gamepads = pads })
    binding:poll(config({ ledge_key = "OFF", ledge_pad = "off" }))
    binding:poll(config({ ledge_key = "off", ledge_pad = "OFF" }))
    T.equal(kb.reads, 0)
    T.equal(pads.reads, 0)
  end)

  T.test("enable and binding changes prime held controls without firing", function()
    local kb = keyboard({ space = true, j = true })
    local binding = InputBinding.new({ keyboard = kb })
    T.falsy(binding:poll(config({ ledge_leap = false })))
    T.falsy(binding:poll(config()), "enable while held must not fire")
    kb.state.space = false
    binding:poll(config())
    kb.state.space = true
    T.truthy(binding:poll(config()))

    T.falsy(binding:poll(config({ ledge_key = "j" })), "rebind while held must not fire")
    kb.state.j = false
    binding:poll(config({ ledge_key = "j" }))
    kb.state.j = true
    T.truthy(binding:poll(config({ ledge_key = "j" })))
  end)

  T.test("reset requires a release before another edge", function()
    local kb = keyboard({ space = true })
    local binding = InputBinding.new({ keyboard = kb })
    binding:poll(config())
    binding:reset()
    T.falsy(binding:poll(config()))
    kb.state.space = false
    binding:poll(config())
    kb.state.space = true
    T.truthy(binding:poll(config()))
  end)

  T.test("keyboard wins a simultaneous edge and both latches advance", function()
    local kb, pad = keyboard(), controller()
    local binding = InputBinding.new({ keyboard = kb, gamepads = gamepads({ pad }) })
    binding:poll(config())
    kb.state.space, pad.state.y = true, true
    local pressed, source = binding:poll(config())
    T.truthy(pressed)
    T.equal(source, "keyboard")
    T.falsy(binding:poll(config()), "gamepad edge must not repeat next step")
  end)

  T.test("non-gamepads are skipped and gamepad scans are bounded", function()
    local controllers = { controller({ y = true }, false) }
    for index = 2, 8 do controllers[index] = controller() end
    controllers[9] = controller({ y = true })
    local binding = InputBinding.new({ gamepads = gamepads(controllers) })
    binding:poll(config())
    controllers[1].state.y = false
    T.falsy(binding:poll(config()))
    T.equal(controllers[9].reads, 0)
    T.equal(InputBinding.MAX_GAMEPADS, 8)
  end)

  T.test("compatibility values can supply canonical bindings", function()
    local kb = keyboard()
    local binding = InputBinding.new({ keyboard = kb })
    local nested = { values = { ledge_leap = true, jumpkey = "j", jumppad = "off" } }
    binding:poll(nested)
    kb.state.j = true
    local pressed, source = binding:poll(nested)
    T.truthy(pressed)
    T.equal(source, "keyboard")
  end)

  T.test("invalid bindings and facade errors fail closed", function()
    local diag = diagnostics()
    local kb = { isDown = function() error("keyboard boom") end }
    local pads = { list = function() error("gamepad boom") end }
    local binding = InputBinding.new({ keyboard = kb, gamepads = pads, diagnostics = diag })
    local bad = config({ ledge_key = "delete", ledge_pad = "a" })
    binding:poll(bad)
    T.falsy(binding:poll(bad))
    T.equal(diag.entries[1].code, "GAMEPLAY.INPUT_BINDING_INVALID")

    binding:reset()
    binding:poll(config())
    T.falsy(binding:poll(config()))
    local codes = {}
    for _, entry in ipairs(diag.entries) do codes[entry.code] = true end
    T.truthy(codes["GAMEPLAY.KEYBOARD_READ_FAILED"])
    T.truthy(codes["GAMEPLAY.GAMEPAD_LIST_FAILED"])
  end)
end
