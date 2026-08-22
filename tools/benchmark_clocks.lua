-- Platform clocks for controlled native benchmarks.

local ok, ffi = pcall(require, "ffi")
if not ok then error("benchmark clocks require LuaJIT FFI") end

local Clocks = {}

if ffi.os == "Windows" then
  ffi.cdef([[
    typedef struct kfp_benchmark_filetime {
      unsigned long low;
      unsigned long high;
    } kfp_benchmark_filetime;
    void *GetCurrentProcess(void);
    int GetProcessTimes(
      void *process,
      kfp_benchmark_filetime *created,
      kfp_benchmark_filetime *exited,
      kfp_benchmark_filetime *kernel,
      kfp_benchmark_filetime *user
    );
    int QueryPerformanceCounter(int64_t *value);
    int QueryPerformanceFrequency(int64_t *value);
  ]])
elseif ffi.os == "Linux" or ffi.os == "OSX" then
  ffi.cdef([[
    struct kfp_benchmark_timespec { long tv_sec; long tv_nsec; };
    int clock_gettime(int clock_id, struct kfp_benchmark_timespec *value);
  ]])
else
  error("benchmark clocks do not support this platform: " .. tostring(ffi.os))
end

function Clocks.monotonicWallClock()
  if ffi.os == "Windows" then
    local value = ffi.new("int64_t[1]")
    local frequency = ffi.new("int64_t[1]")
    assert(ffi.C.QueryPerformanceFrequency(frequency) ~= 0,
      "QueryPerformanceFrequency failed")
    local unitsPerSecond = tonumber(frequency[0])
    return function()
      assert(ffi.C.QueryPerformanceCounter(value) ~= 0,
        "QueryPerformanceCounter failed")
      return tonumber(value[0]) / unitsPerSecond
    end
  end

  local clockId = ffi.os == "OSX" and 6 or 1
  local value = ffi.new("struct kfp_benchmark_timespec[1]")
  return function()
    assert(ffi.C.clock_gettime(clockId, value) == 0, "clock_gettime failed")
    return tonumber(value[0].tv_sec) + tonumber(value[0].tv_nsec) / 1000000000
  end
end

local function filetimeTicks(value)
  return tonumber(value.high) * 4294967296 + tonumber(value.low)
end

function Clocks.processCpuClock()
  if ffi.os == "Windows" then
    local process = ffi.C.GetCurrentProcess()
    local created = ffi.new("kfp_benchmark_filetime[1]")
    local exited = ffi.new("kfp_benchmark_filetime[1]")
    local kernel = ffi.new("kfp_benchmark_filetime[1]")
    local user = ffi.new("kfp_benchmark_filetime[1]")
    local function clock()
      assert(ffi.C.GetProcessTimes(process, created, exited, kernel, user) ~= 0,
        "GetProcessTimes failed")
      return (filetimeTicks(kernel[0]) + filetimeTicks(user[0])) / 10000000
    end
    return clock, {
      platform = ffi.os,
      scope = "process",
      source = "GetProcessTimes",
      components = "kernel+user",
      unit = "seconds",
      idleWaitIncluded = false,
    }
  end

  local clockId = ffi.os == "OSX" and 12 or 2
  local value = ffi.new("struct kfp_benchmark_timespec[1]")
  local function clock()
    assert(ffi.C.clock_gettime(clockId, value) == 0,
      "CLOCK_PROCESS_CPUTIME_ID failed")
    return tonumber(value[0].tv_sec) + tonumber(value[0].tv_nsec) / 1000000000
  end
  return clock, {
    platform = ffi.os,
    scope = "process",
    source = "clock_gettime(CLOCK_PROCESS_CPUTIME_ID)",
    components = "all-thread CPU",
    unit = "seconds",
    idleWaitIncluded = false,
  }
end

return Clocks
