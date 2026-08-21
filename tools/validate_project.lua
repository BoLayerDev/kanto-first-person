-- Fast repository-policy checks that need no ROM, engine, or third-party tool.

local function normalize(path)
  return (path:gsub("\\", "/"):gsub("/+", "/"))
end

local source = normalize(debug.getinfo(1, "S").source:gsub("^@", ""))
local toolsDir = source:match("^(.*)/[^/]+$") or "."
local root = toolsDir:match("^(.*)/tools$") or "."

local function read(relative)
  local file, err = io.open(root .. "/" .. relative, "rb")
  if not file then return nil, err end
  local body = file:read("*a")
  file:close()
  return body
end

local failures = {}
local function check(ok, message)
  if not ok then failures[#failures + 1] = message end
end

for _, path in ipairs({
  "manifest.json", "main.lua", "LICENSE", "THIRD_PARTY_NOTICES.md",
  "PROJECT_STATUS.md", "ROADMAP.md", "docs/architecture.md",
  "docs/voxel-companion-api-v1.md", "docs/release-gates.json",
  "tools/ManifestPolicy.lua",
}) do
  check(read(path) ~= nil, "missing required file: " .. path)
end

local manifest = read("manifest.json") or ""
local ManifestPolicy = assert(loadfile(toolsDir .. "/ManifestPolicy.lua"))()
local manifestOk, manifestError = ManifestPolicy.validate(manifest)
check(manifestOk, manifestError or "manifest policy validation failed")

for _, retired in ipairs({
  "payload_backdrop.lua", "payload_ceiling.lua", "payload_flora.lua",
  "payload_jump.lua", "payload_sky.lua", "jump_button.lua",
}) do
  check(read(retired) == nil, "retired patch payload returned: " .. retired)
end

local function executableBody(body)
  local lines = {}
  for line in (body .. "\n"):gmatch("(.-)\n") do
    lines[#lines + 1] = line:gsub("%-%-.*$", "")
  end
  return table.concat(lines, "\n")
end

local forbidden = {
  { "global _G", "[^%w_]_G[^%w_]" },
  { "raw love.filesystem", "love%s*%.%s*filesystem" },
  { "raw io", "[^%w_]io%s*%." },
  { "dofile", "[^%w_]dofile%s*%(" },
  { "loadfile", "[^%w_]loadfile%s*%(" },
  { "global random seed", "math%s*%.%s*randomseed%s*%(" },
  { "engine-private require", "[%s%(,=]require%s*%(" },
}

local pipe = assert(io.popen("git -C \"" .. root:gsub('"', '""')
  .. "\" ls-files --cached --others --exclude-standard -- main.lua src companion", "r"))
for relative in pipe:lines() do
  relative = normalize(relative)
  if relative:match("%.lua$") then
    local body = executableBody(read(relative) or "")
    for _, rule in ipairs(forbidden) do
      check(not body:find(rule[2]), relative .. " uses forbidden " .. rule[1])
    end
  end
end
check(pipe:close(), "runtime source discovery failed")

local secretPatterns = {
  { "private key", "%-%-%-%-%-BEGIN [A-Z ]-PRIVATE KEY%-%-%-%-%-" },
  { "GitHub token", "ghp_[A-Za-z0-9_]+" },
  { "GitHub fine-grained token", "github_pat_[A-Za-z0-9_]+" },
  -- Include the left boundary in the match so ordinary words such as
  -- "task-owned" cannot be mistaken for an API key.
  { "OpenAI key", "[^A-Za-z0-9_]sk%-[A-Za-z0-9_-][A-Za-z0-9_-]+" },
  { "AWS access key", "AKIA[A-Z0-9][A-Z0-9][A-Z0-9][A-Z0-9]+" },
}
local textExtensions = {
  lua = true, md = true, json = true, yml = true, yaml = true,
  py = true, ps1 = true, txt = true, toml = true, env = true,
  pem = true, key = true, cfg = true, ini = true,
}
local projectFiles = assert(io.popen("git -C \"" .. root:gsub('"', '""')
  .. "\" ls-files --cached --others --exclude-standard", "r"))
for relative in projectFiles:lines() do
  relative = normalize(relative)
  local lower = relative:lower()
  check(not lower:match("^evidence/") and not lower:match("^private%-fixtures/")
      and not lower:match("^baseroms/") and not lower:match("^roms/"),
    "private evidence or game material is tracked: " .. relative)
  check(not lower:match("%.gbc?$") and not lower:match("%.sav$"),
    "ROM or save material is tracked: " .. relative)
  local extension = lower:match("%.([a-z0-9]+)$")
  if textExtensions[extension] then
    -- Prefix one byte so a real key at byte one still has a left boundary.
    local body = "\n" .. (read(relative) or "")
    for _, secret in ipairs(secretPatterns) do
      check(not body:find(secret[2]), relative .. " contains a possible " .. secret[1])
    end
  end
end
check(projectFiles:close(), "project file discovery failed")

if #failures > 0 then
  for _, failure in ipairs(failures) do io.stderr:write("FAIL ", failure, "\n") end
  io.stderr:write(("%d project policy checks failed\n"):format(#failures))
  os.exit(1)
end

io.write("project policy checks passed\n")
