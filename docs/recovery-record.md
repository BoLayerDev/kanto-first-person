# Recovery Record

## Verified source checkpoint

- Runtime checkpoint: `568ef6994fa9cb8daae5fc0853bab6b589b961f2`.
- Branch: `v2-rewrite`.
- Source workspace: `C:\Users\bolay\Documents\Kanto First Person`.
- Independent clone:
  `C:\Users\bolay\Documents\Kanto First Person Evidence\verification\restore-0f45318`.
- Clone method: local Git clone with independent object files (`--no-hardlinks`).

The clone contains only committed files. It does not use ignored caches,
private provenance files, host worktrees, or files from the source working
tree.

## Verification on 2026-08-21

- Git HEAD matched the runtime checkpoint commit.
- ROM-free Lua suite: 215 passed, 0 failed.
- LuaJIT syntax gate: 77 files compiled, 0 failed.
- Repository policy gate: passed.
- Python release-control suite: 8 passed, 0 failed.

The clean checkpoint also produced the same fixed-epoch v0.2.18 private test
packages as both pre-commit builds:

- MODPKG SHA-256:
  `4c123b992ba0439171cc908232b51099b9a39f0e322d5d1d7f6e3c2a5fb694f5`.
- ZIP SHA-256:
  `72fec6b1a96557466d467fba3d2f60c9bd2a1cfeaabd40341e296cb1ddede77f`.

The clean attestation records `source_dirty=false`, `publishable=false`, and
engine commit `70d7b6383e2c005857013dc897fd096886b08f0b`.

## Remote status

The first push of this checkpoint was rejected because the active personal
GitHub OAuth token lacks the `workflow` scope required to create
`.github/workflows/ci.yml`. The local commit and independent recovery clone are
safe. A remote-clone recovery test remains pending until the `BoLayerDev`
personal authentication is renewed with `workflow` scope and the local
checkpoint commits are pushed. Do not use the separate ROE account for this
personal repository.
