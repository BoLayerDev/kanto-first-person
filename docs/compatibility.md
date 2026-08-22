# Compatibility Matrix

## Engine

| Target | Commit | State |
|---|---|---|
| Gen1recomp v0.2.17 | `44f4680b24823629489ed5a2adad648d0dceb640` | Minimum range; validate and lint pass |
| Gen1recomp v0.2.18 | `70d7b6383e2c005857013dc897fd096886b08f0b` | Retained release target; validate and lint pass |
| Gen1recomp v0.2.19 | `116a6ba450dd65f25c9be150952fc3c27be904c0` | Latest audited release; validate, lint, and private package pass |
| Gen1recomp dev baseline | `06e06e305bbcefe97c216a31bb25265ffb5e6b18` | Validate and lint pass |
| Gen1recomp dev current | `478e3bf8ebf7646edfda88320c6472cf32db2e67` | Re-audited; API 2, sandbox, pipelines, strict validate, and lint pass |

Release range: `>=0.2.17 <0.3.0`. Development builds report `0.0.0-dev`, so CI pins their commit separately.

The v0.2.19 release contains the current audited dev commit plus release-only
iOS repository metadata. From v0.2.18, the manifest validator, sandbox, render
registry schema, render pipeline, and modkit are byte-identical. The Loader
adds a Gen1-side denial for Gen2 engine-module imports, and the other mod API
change is Gold-only. KFP does not use those imports and declares Gen1 only.
See the hash-bound
[engine audit](release-evidence/gen1recomp-2026-08-22.json).

The same five pins have no public owner-scoped runtime method for output from
`assets_transforms`. Birds and ground flocks therefore stay disabled. See the
[derived-asset runtime API proposal](derived-asset-runtime-api-proposal.md).

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
