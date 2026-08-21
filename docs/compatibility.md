# Compatibility Matrix

## Engine

| Target | Commit | State |
|---|---|---|
| Gen1recomp v0.2.17 | `44f4680b24823629489ed5a2adad648d0dceb640` | Minimum range; validate and lint pass |
| Gen1recomp v0.2.18 | `70d7b6383e2c005857013dc897fd096886b08f0b` | Latest shipped tag; validate and lint pass |
| Gen1recomp dev baseline | `06e06e305bbcefe97c216a31bb25265ffb5e6b18` | Validate and lint pass |
| Gen1recomp dev current | `087a2751895899ad6e79800599ae27a8f40cf1e3` | Re-audited; validate and lint pass |

Release range: `>=0.2.17 <0.3.0`. Development builds report `0.0.0-dev`, so CI pins their commit separately.

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
| `DRAMATIC_SHAPE` | 1.9.0 | `cd10ac3` | Local adapter `a395bbc` passes contract tests and four-engine co-load checks | Host review and GPU run open |
| `BATTLE_ART_VOXEL_FORK` | 1.9.7 | `fcbe541` | Local adapter `0185b44` passes contract tests | Host review and GPU run open |
| `DRAMALESS_SHAPE` | 2.0.3 | `f14795b` | Local adapter `bc24063` passes contract tests | Host review and GPU run open |

Runtime selection requires exactly one active compatible host. Zero or multiple hosts leave KFP inactive.
Local adapter commits are unpushed implementation evidence. They do not change
the certified host versions above and must not be described as released.

## Platforms

Windows, Linux x86-64, Linux ARM64, macOS x86-64, macOS ARM64, Android, iOS, Xbox UWP, Nintendo Switch, PortMaster SBC, and Anbernic stock OS each need recorded native evidence. A platform remains experimental until that evidence exists.
