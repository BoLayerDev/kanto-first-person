-- Deterministic cooperative scheduler with cost and callback bounds.
-- Task callbacks must honor their supplied slice; Lua cannot preempt them.

local Scheduler = {}
Scheduler.__index = Scheduler

local function positiveInteger(value, fallback, name)
  value = math.floor(tonumber(value) or fallback)
  assert(value > 0, name .. " must be positive")
  return value
end

local function emit(diagnostics, level, code, message, fields)
  if diagnostics and type(diagnostics.emit) == "function" then
    pcall(diagnostics.emit, diagnostics, level, code, message, fields)
  end
end

function Scheduler.new(opts)
  opts = opts or {}
  local maxBudget = positiveInteger(opts.maxBudget, 1024, "Scheduler maxBudget")
  local quantum = positiveInteger(opts.quantum, 32, "Scheduler quantum")
  if quantum > maxBudget then quantum = maxBudget end
  return setmetatable({
    maxTasks = positiveInteger(opts.maxTasks, 128, "Scheduler maxTasks"),
    maxBudget = maxBudget,
    maxCallbacks = positiveInteger(opts.maxCallbacks, 256,
      "Scheduler maxCallbacks"),
    quantum = quantum,
    diagnostics = opts.diagnostics,
    tasks = {},
    queue = {},
    head = 1,
    tail = 0,
    count = 0,
    serial = 0,
    counters = { spawned = 0, completed = 0, cancelled = 0,
                 failed = 0, callbacks = 0, charged = 0 },
  }, Scheduler)
end

function Scheduler:_enqueue(task)
  self.tail = self.tail + 1
  self.queue[self.tail] = task
end

function Scheduler:_dequeue()
  if self.head > self.tail then return nil end
  local task = self.queue[self.head]
  self.queue[self.head] = nil
  self.head = self.head + 1
  return task
end

function Scheduler:_compact(force)
  local queued = math.max(0, self.tail - self.head + 1)
  if not force and queued <= self.maxTasks * 2
      and (self.head <= 256 or self.head <= self.tail / 2) then
    return
  end
  local nextQueue, nextTail = {}, 0
  for index = self.head, self.tail do
    local task = self.queue[index]
    if task and self.tasks[task.id] == task then
      nextTail = nextTail + 1
      nextQueue[nextTail] = task
    end
  end
  self.queue, self.head, self.tail = nextQueue, 1, nextTail
end

function Scheduler:spawn(id, step, opts)
  opts = opts or {}
  if type(id) ~= "string" or id == "" then return nil, "invalid_task_id" end
  if type(step) ~= "function" then return nil, "task_step_must_be_a_function" end
  if self.tasks[id] then return nil, "duplicate_task" end
  if self.count >= self.maxTasks then return nil, "task_limit" end
  local quantum = positiveInteger(opts.quantum, self.quantum, "task quantum")
  if quantum > self.maxBudget then quantum = self.maxBudget end
  self.serial = self.serial + 1
  local task = {
    id = id,
    step = step,
    context = opts.context,
    quantum = quantum,
    onDone = opts.onDone,
    onCancel = opts.onCancel,
    onError = opts.onError,
    serial = self.serial,
  }
  self.tasks[id] = task
  self.count = self.count + 1
  self.counters.spawned = self.counters.spawned + 1
  self:_enqueue(task)
  return task
end

local function notify(callback, ...)
  if type(callback) ~= "function" then return true end
  return pcall(callback, ...)
end

function Scheduler:cancel(id, reason)
  local task = self.tasks[id]
  if not task then return false, "unknown_task" end
  self.tasks[id] = nil
  self.count = self.count - 1
  self.counters.cancelled = self.counters.cancelled + 1
  local ok, err = notify(task.onCancel, reason or "cancelled", task.context)
  if not ok then
    emit(self.diagnostics, "warn", "CORE.SCHEDULER_CANCEL_CALLBACK_FAILED",
      tostring(err), { task = id })
  end
  if self.tail - self.head + 1 > self.maxTasks * 2 then self:_compact(true) end
  return true
end

function Scheduler:has(id)
  return self.tasks[id] ~= nil
end

function Scheduler:size()
  return self.count
end

function Scheduler:step(budget, frameContext)
  budget = tonumber(budget)
  if not budget or budget ~= budget then budget = self.maxBudget end
  budget = math.floor(budget)
  if budget < 0 then budget = 0 end
  if budget > self.maxBudget then budget = self.maxBudget end

  local report = { requested = budget, used = 0, callbacks = 0,
                   completed = 0, failed = 0, remainingTasks = self.count }
  local remaining = budget
  while remaining > 0 and self.count > 0
      and report.callbacks < self.maxCallbacks do
    local task = self:_dequeue()
    if task == nil then break end
    local id = task.id
    if self.tasks[id] == task then
      local slice = math.min(remaining, task.quantum)
      report.callbacks = report.callbacks + 1
      self.counters.callbacks = self.counters.callbacks + 1
      local ok, done, used = pcall(task.step, slice, task.context, frameContext)

      local charged = tonumber(used)
      if not charged or charged ~= charged or charged < 1 then charged = 1 end
      charged = math.floor(charged)
      if charged > slice then
        emit(self.diagnostics, "warn", "CORE.SCHEDULER_COST_CLAMPED",
          "Task reported more work than its slice", { task = id,
          reported = charged, slice = slice })
        charged = slice
      end
      remaining = remaining - charged
      report.used = report.used + charged
      self.counters.charged = self.counters.charged + charged

      -- A callback may cancel itself or replace its id. Do not touch the new
      -- owner in that case.
      if self.tasks[id] == task then
        if not ok then
          self.tasks[id] = nil
          self.count = self.count - 1
          report.failed = report.failed + 1
          self.counters.failed = self.counters.failed + 1
          emit(self.diagnostics, "error", "CORE.SCHEDULER_TASK_FAILED",
            tostring(done), { task = id })
          local errorOk, errorErr = notify(task.onError, done, task.context)
          if not errorOk then
            emit(self.diagnostics, "warn", "CORE.SCHEDULER_ERROR_CALLBACK_FAILED",
              tostring(errorErr), { task = id })
          end
        elseif done == true then
          self.tasks[id] = nil
          self.count = self.count - 1
          report.completed = report.completed + 1
          self.counters.completed = self.counters.completed + 1
          local doneOk, doneErr = notify(task.onDone, task.context)
          if not doneOk then
            emit(self.diagnostics, "warn", "CORE.SCHEDULER_DONE_CALLBACK_FAILED",
              tostring(doneErr), { task = id })
          end
        else
          self:_enqueue(task)
        end
      end
    end
  end
  self:_compact()
  report.remainingTasks = self.count
  return report
end

function Scheduler:clear(reason)
  local ids = {}
  for id in pairs(self.tasks) do ids[#ids + 1] = id end
  table.sort(ids)
  for _, id in ipairs(ids) do self:cancel(id, reason or "cleared") end
  self.queue, self.head, self.tail = {}, 1, 0
  return #ids
end

function Scheduler:stats()
  local out = {}
  for key, value in pairs(self.counters) do out[key] = value end
  out.active = self.count
  out.queued = math.max(0, self.tail - self.head + 1)
  return out
end

return Scheduler
