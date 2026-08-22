-- Synthetic, ROM-free host trees for migration and uninstall contract tests.
-- These strings are invented test data. They are not copied from a voxel host.

local PATHS = {
  "ChunkMesher.lua",
  "Structures.lua",
  "main.lua",
}

local MARKERS = {
  "KFP_LEGACY_SPLICE_BEGIN",
  "payload_backdrop",
  "payload_ceiling",
  "payload_flora",
  "payload_jump",
  "payload_sky",
}

local function files(structures, mesher)
  return {
    ["ChunkMesher.lua"] = mesher,
    ["Structures.lua"] = structures,
    ["main.lua"] = "return { voxel_companion = true }\n",
  }
end

return {
  paths = PATHS,
  markers = MARKERS,
  clean = {
    id = "DRAMALESS_SHAPE",
    version = "2.0.3-test",
    files = files(
      "return { structures = 'synthetic-clean' }\n",
      "return { mesher = 'synthetic-clean' }\n"
    ),
  },
  legacy = {
    id = "DRAMALESS_SHAPE",
    version = "1.60-patched-test",
    files = files(
      "-- KFP_LEGACY_SPLICE_BEGIN\nreturn { payload_ceiling = true }\n",
      "return { payload_sky = true }\n"
    ),
  },
}
