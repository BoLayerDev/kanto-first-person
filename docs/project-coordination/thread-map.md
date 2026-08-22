# Workstream Ownership

Last updated: 2026-08-22

| Workstream | Owner | Exclusive paths | State |
|---|---|---|---|
| Integration and release | Coordinator | `main.lua`, `manifest.json`, root docs, `src/companion/`, `src/features/`, `src/render/`, integration tests, assets | Source checkpoint and private QA preparation in progress |
| Voxel Companion API | Companion lane | `companion/`, `docs/voxel-companion-api-v1.md`, `tests/companion/` | Frozen v1 source contract complete |
| Core runtime | Core lane | `src/core/`, `tests/core/`, test bootstrap, CI | Source implementation complete |
| Options and gameplay | Config/gameplay lane | `src/config/`, `src/gameplay/`, parity and migration docs, related tests | Migration complete; Ledge runtime gated off |
| Host adapters | Two isolated host lanes | Isolated task-owned host clones only | Pushed PR branches pass contracts; owner and GPU gates open |
| Runtime evidence | Coordinator | Private isolated identities and public evidence schemas | Yellow profiles prepared; activation and GPU runs open |
| Website showcase | Coordinator | `website/`, `.github/workflows/pages.yml`, website-only CI | Gen 1 options-menu redesign builds on a feature branch; publication and browser QA open |

## Handoff contract

Each handoff contains goal, changed files, public interfaces, verification commands and results, open risks, and the exact next action. Workers do not commit, push, or edit another lane unless the coordinator reassigns ownership.

## Shared-resource rules

- The coordinator owns Git integration, commits, pushes, packages, and Backup Guardian.
- Existing Gen1recomp and voxel-host directories are read-only evidence.
- Host implementation uses new isolated clones after the API contract passes.
- Private ROM and permission evidence never enter worker prompts, Git, logs, or public fixtures.
