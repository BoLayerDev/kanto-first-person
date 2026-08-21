-- Compile every tracked or untracked Lua source file without executing it.

local function normalize(path)
  return (path:gsub("\\", "/"):gsub("/+", "/"))
end

local source = normalize(debug.getinfo(1, "S").source:gsub("^@", ""))
local toolsDir = source:match("^(.*)/[^/]+$") or "."
local root = toolsDir:match("^(.*)/tools$") or "."

local function quote(path)
  if package.config:sub(1, 1) == "\\" then
    return '"' .. path:gsub('"', '""') .. '"'
  end
  return "'" .. path:gsub("'", "'\\''") .. "'"
end

local luaPathspec = package.config:sub(1, 1) == "\\" and "*.lua" or "'*.lua'"
local command = "git -C " .. quote(root)
  .. " ls-files --cached --others --exclude-standard -- " .. luaPathspec
local pipe = assert(io.popen(command, "r"), "cannot list Lua files")
local files = {}
for line in pipe:lines() do
  line = normalize(line)
  if line ~= "" then
    local file = io.open(root .. "/" .. line, "rb")
    if file then
      file:close()
      files[#files + 1] = line
    end
  end
end
local closed = pipe:close()
assert(closed, "git file discovery failed")
table.sort(files)

local failed = 0
for _, relative in ipairs(files) do
  local chunk, err = loadfile(root .. "/" .. relative)
  if not chunk then
    failed = failed + 1
    io.stderr:write("FAIL ", relative, "\n", tostring(err), "\n")
  end
end

io.write(("%d Lua files compiled, %d failed\n"):format(#files, failed))
if failed > 0 then os.exit(1) end
