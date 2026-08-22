local Renderer = {}
Renderer.__index = Renderer

local METHOD_FOR_KIND = {
  mesh = "mesh",
  instances = "instances",
  billboards = "billboards",
}

local function diagnose(self, code, message, fields)
  if self._diagnostics and self._diagnostics.emit then
    pcall(self._diagnostics.emit, self._diagnostics, "error", code, message, fields)
  end
end

function Renderer.new(options)
  options = options or {}
  return setmetatable({
    _diagnostics = options.diagnostics,
    _disabledOwners = {},
    _drawn = 0,
    _failed = 0,
  }, Renderer)
end

function Renderer:renderPhase(packet, phase, context)
  if not packet or not packet.phases then return 0 end
  local commands = packet.phases[phase]
  if not commands then return 0 end
  local draw = context and context.draw
  if type(draw) ~= "table" then
    diagnose(self, "RENDER.DRAW_FACADE_MISSING", "Host draw facade is missing", { phase = phase })
    return 0
  end

  local submitted = 0
  for _, command in ipairs(commands) do
    local owner = command.owner or "core"
    if not self._disabledOwners[owner] then
      local methodName = METHOD_FOR_KIND[command.kind]
      local method = methodName and draw[methodName]
      if type(method) ~= "function" then
        self._disabledOwners[owner] = true
        self._failed = self._failed + 1
        diagnose(self, "RENDER.DRAW_METHOD_MISSING", "Host draw method is missing", {
          phase = phase,
          owner = owner,
          kind = command.kind,
        })
      else
        local ok, accepted, drawError = pcall(method, command, context)
        if ok and accepted == true then
          submitted = submitted + 1
          self._drawn = self._drawn + 1
        else
          self._disabledOwners[owner] = true
          self._failed = self._failed + 1
          diagnose(self, "RENDER.DRAW_COMMAND_FAILED", "Feature draw command failed", {
            phase = phase,
            owner = owner,
            kind = command.kind,
            error = tostring(ok and (drawError or "host rejected the command")
              or accepted),
          })
        end
      end
    end
  end
  return submitted
end

function Renderer:invalidateOwner(owner)
  self._disabledOwners[owner] = nil
end

function Renderer:invalidateAll()
  self._disabledOwners = {}
end

function Renderer:status()
  local disabled = {}
  for owner in pairs(self._disabledOwners) do disabled[#disabled + 1] = owner end
  table.sort(disabled)
  return {
    drawn = self._drawn,
    failed = self._failed,
    disabledOwners = disabled,
  }
end

return Renderer
