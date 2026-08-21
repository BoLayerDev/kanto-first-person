-- Side-effect adapter for LedgeLeapPolicy decisions.
--
-- A future atomic engine adapter can inject queue_script. Alpha does not
-- construct this module. It does not reference mod, Game, love, or an engine
-- module.

local LedgeLeapRuntime = {}
LedgeLeapRuntime.__index = LedgeLeapRuntime

local DIRECTIONS = { up = true, down = true, left = true, right = true }

local function emit(diagnostics, level, code, message, fields)
  if diagnostics == nil then return end
  if type(diagnostics) == "function" then
    pcall(diagnostics, level, code, message, fields)
  elseif type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

local function defaultScript(decision, arcCommand)
  return {
    { arcCommand, decision.arc_frames },
    { "play_sound", decision.sound },
    { "move_player", decision.direction, 2 },
  }
end

function LedgeLeapRuntime.new(opts)
  opts = opts or {}
  local decide = opts.decide
  if decide == nil and type(opts.policy) == "table" then decide = opts.policy.decide end
  assert(type(decide) == "function", "LedgeLeapRuntime needs a decide(request) function")
  assert(type(opts.queue_script) == "function",
    "LedgeLeapRuntime needs a queue_script(script) function")
  assert(opts.build_script == nil or type(opts.build_script) == "function",
    "LedgeLeapRuntime build_script must be a function")
  local arcCommand = opts.arc_command or "kfp_ledge_arc"
  assert(type(arcCommand) == "string" and arcCommand ~= "",
    "LedgeLeapRuntime arc_command must be a non-empty string")
  return setmetatable({
    decide = decide,
    queueScript = opts.queue_script,
    buildScript = opts.build_script,
    arcCommand = arcCommand,
    diagnostics = opts.diagnostics,
  }, LedgeLeapRuntime)
end

local function safeDecision(decision)
  return type(decision) == "table" and decision.allowed == true
    and decision.action == "ledge_leap" and DIRECTIONS[decision.direction] == true
    and decision.distance == 2 and type(decision.arc_frames) == "number"
    and decision.arc_frames >= 2 and decision.arc_frames <= 64
    and decision.arc_frames == math.floor(decision.arc_frames)
    and decision.sound == "Ledge" and type(decision.rule_index) == "number"
    and decision.rule_index == math.floor(decision.rule_index)
    and decision.rule_index >= 1 and decision.rule_index <= 256
end

local function safeScript(script)
  if type(script) ~= "table" or #script < 1 or #script > 8 then return false end
  for index = 1, #script do
    if type(script[index]) ~= "table" then return false end
  end
  return true
end

function LedgeLeapRuntime:attempt(request)
  local okDecision, decision = pcall(self.decide, request)
  if not okDecision then
    emit(self.diagnostics, "error", "GAMEPLAY.LEDGE_POLICY_FAILED",
      "The Ledge Leap policy failed. No movement was queued.",
      { error = tostring(decision) })
    return { allowed = false, action = "none", reason = "policy_failed" },
      false, tostring(decision)
  end
  if type(decision) ~= "table" or decision.allowed ~= true then
    return decision or { allowed = false, action = "none", reason = "invalid_decision" },
      false
  end
  if not safeDecision(decision) then
    emit(self.diagnostics, "error", "GAMEPLAY.LEDGE_DECISION_INVALID",
      "An invalid Ledge Leap decision was rejected.", {})
    return { allowed = false, action = "none", reason = "invalid_decision" }, false
  end

  local okBuild, script
  if self.buildScript then
    okBuild, script = pcall(self.buildScript, decision)
  else
    okBuild, script = true, defaultScript(decision, self.arcCommand)
  end
  if not okBuild or not safeScript(script) then
    emit(self.diagnostics, "error", "GAMEPLAY.LEDGE_SCRIPT_BUILD_FAILED",
      "The Ledge Leap script could not be built. No movement was queued.",
      { error = tostring(script) })
    return decision, false, tostring(script)
  end

  local okQueue, queued, queueError = pcall(self.queueScript, script)
  if not okQueue or queued == false then
    local detail = okQueue and queueError or queued
    emit(self.diagnostics, "error", "GAMEPLAY.LEDGE_QUEUE_FAILED",
      "The Ledge Leap script was rejected. No direct movement was attempted.",
      { error = tostring(detail) })
    return decision, false, tostring(detail)
  end
  return decision, true
end

return LedgeLeapRuntime
