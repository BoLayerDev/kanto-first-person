# Workstream Ownership

Last updated: 2026-08-21

| Workstream | Owner | Exclusive paths | State |
|---|---|---|---|
| Integration and release | Coordinator | `main.lua`, `manifest.json`, root docs, `src/companion/`, `src/features/`, `src/render/`, integration tests, assets | In progress |
| Voxel Companion API | Companion lane | `companion/`, `docs/voxel-companion-api-v1.md`, `tests/companion/` | Frozen v1 source contract complete |
| Core runtime | Core lane | `src/core/`, `tests/core/`, test bootstrap, CI | Source implementation complete |
| Options and gameplay | Config/gameplay lane | `src/config/`, `src/gameplay/`, parity and migration docs, related tests | Migration complete; Ledge runtime gated off |
| Host adapters | Three isolated host lanes | Isolated task-owned host clones only | Local source tests pass; owner/GPU gates open |

## Handoff contract

Each handoff contains goal, changed files, public interfaces, verification commands and results, open risks, and the exact next action. Workers do not commit, push, or edit another lane unless the coordinator reassigns ownership.

## Shared-resource rules

- The coordinator owns Git integration, commits, pushes, packages, and Backup Guardian.
- Existing Gen1recomp and voxel-host directories are read-only evidence.
- Host implementation uses new isolated clones after the API contract passes.
- Private ROM and permission evidence never enter worker prompts, Git, logs, or public fixtures.
