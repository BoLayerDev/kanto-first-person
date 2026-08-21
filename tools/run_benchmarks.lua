-- ROM-free microbenchmarks. These detect large regressions but do not replace
-- the host, GPU, device, or 30-minute release performance gates.

local Bootstrap = assert(loadfile("tools/test_bootstrap.lua"))()

local function load(relative)
  return assert(loadfile(Bootstrap.path(relative)))()
end

local Config = load("src/config/Config.lua")
local LRU = load("src/core/LRU.lua")
local LedgeLeapPolicy = load("src/gameplay/LedgeLeapPolicy.lua")

local optionValues = {}
for _, row in ipairs(Config.optionSchema()) do optionValues[row.key] = row.default end
local config = Config.new({ read = function(key) return optionValues[key] end })

local ledgeRequest = {
  enabled = true,
  mode = "free_roam",
  script_running = false,
  input_locked = false,
  direction = "down",
  player = {
    cell_x = 10, cell_y = 20, facing = "down", moving = false,
    surfing = false, hop_frames = 0, step_frames = 16,
  },
  map = { tileset = "OVERWORLD", standing_tile = 44 },
  front = { x = 10, y = 21, in_bounds = true, tile = 55, occupied = false },
  landing = { x = 10, y = 22, in_bounds = true, walkable = true, occupied = false },
  ledges = {
    { facing = "down", input = "down", standingTile = 44, ledgeTile = 55 },
  },
}

local cache = LRU.new({ maxCost = 1024, release = function() end })
for index = 1, 128 do cache:put("key:" .. index, { index = index }, 1) end

local cases = {
  {
    name = "config_snapshot_cached",
    iterations = 1000000,
    run = function() return config:snapshot() end,
  },
  {
    name = "lru_hot_get",
    iterations = 1000000,
    run = function(index) return cache:get("key:" .. ((index - 1) % 128 + 1)) end,
  },
  {
    name = "ledge_policy_valid",
    iterations = 250000,
    run = function() return LedgeLeapPolicy.decide(ledgeRequest) end,
  },
}

collectgarbage("collect")
local retained
for _, case in ipairs(cases) do
  local started = os.clock()
  for index = 1, case.iterations do retained = case.run(index) end
  local elapsed = os.clock() - started
  io.write(("%-24s %9d iterations %9.3f ms %9.1f ns/op\n"):format(
    case.name,
    case.iterations,
    elapsed * 1000,
    elapsed * 1000000000 / case.iterations
  ))
end

if retained == nil then error("benchmark result was unexpectedly nil") end
