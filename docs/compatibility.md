# Compatibility Matrix

## Engine

| Target | Commit | State |
|---|---|---|
| Gen1recomp v0.2.17 | `44f4680b24823629489ed5a2adad648d0dceb640` | Minimum range; validate and lint pass |
| Gen1recomp v0.2.18 | `70d7b6383e2c005857013dc897fd096886b08f0b` | Latest shipped tag; validate and lint pass |
| Gen1recomp dev baseline | `06e06e305bbcefe97c216a31bb25265ffb5e6b18` | Validate and lint pass |
| Gen1recomp dev current | `478e3bf8ebf7646edfda88320c6472cf32db2e67` | Re-audited; API 2, sandbox, pipelines, strict validate, and lint pass |

Release range: `>=0.2.17 <0.3.0`. Development builds report `0.0.0-dev`, so CI pins their commit separately.

The current dev audit found no KFP-facing contract change from v0.2.18. The
manifest validator, sandbox, render registry schema, render pipeline, and
modkit are byte-identical. The Loader change adds a Gen1-side denial for Gen2
engine-module imports; KFP does not use those imports. See the hash-bound
[engine audit](release-evidence/gen1recomp-2026-08-21.json).

## Games

| Game | 2.0 target |
|---|---|
| Red | Required |
| Blue | Required |
| Yellow | Required |
| Gold | Out of scope |
| Silver | Out of scope |

## Voxel hosts

| Host ID | Audited version | Audited commit | Companion API | Stable gate |
|---|---:|---|---|---|
| `BATTLE_ART_VOXEL_FORK` | 1.9.7 | `fcbe541` | PR adapter `8f1af4e` passes contract and cutaway tests | Host review and GPU run open |
| `DRAMALESS_SHAPE` | 2.0.3 | `f14795b` | PR adapter `8e045ad` passes contract, cutaway, and game-ID tests | Host review and GPU run open |

Runtime selection requires exactly one active compatible host. Zero or multiple hosts leave KFP inactive.
The adapter branches are pushed to project forks and submitted in upstream
pull requests. They are review evidence, not released host versions, and must
not be described as released until each host owner publishes them.

## Platforms

Windows, Linux x86-64, Linux ARM64, macOS x86-64, macOS ARM64, Android, iOS, Xbox UWP, Nintendo Switch, PortMaster SBC, and Anbernic stock OS each need recorded native evidence. A platform remains experimental until that evidence exists.
