# KFP 2 Feature Parity Ledger

## Baseline and meaning

The parity baseline is the [published KFP 1.60 archive](https://github.com/mrmushrooms11/kanto-first-person/releases/tag/firstperson1.60.0).
Its source is newer than [repository commit `94d0151`](https://github.com/mrmushrooms11/kanto-first-person/commit/94d0151be839f02fea4a35ab1c3df41fbaddc6c1),
even though the release tag points to that commit. A source file in this rewrite
is not proof of visual parity.

`docs/project-coordination/source-registry.md` records the exact ZIP and MODPKG
hashes. Update this ledger only against that fixed evidence set.

Status terms:

- **Represented**: v2 has a declarative feature intent or policy and a ROM-free
  unit test can inspect it.
- **Corrected**: v2 intentionally changes unsafe or incorrect behavior.
- **Open**: real output, timing, assets, or host behavior still needs evidence.
- **Retired**: v2 intentionally does not implement the old behavior.

Every represented visual item remains **Open** until it passes declarative
packet checks, synthetic render review, and private in-game review on Red,
Blue, and Yellow.

## Interior and cave

| Legacy behavior to preserve | v2 decision | Current evidence still needed |
| --- | --- | --- |
| Atlas-derived walls and ceilings with AIRY, MID, and SNUG headroom | Represented | Material, seam, and first-person screenshots |
| Full and cutaway first-person ceiling modes | Represented | Camera-mode and cutaway corpus |
| Third-person and diorama ceiling modes | Represented | NONE, CUTAWAY, and FULL packet tests pass; camera-mode and GPU review remain open |
| Single and two-cell double doors | Represented | Door orientation and warp tests |
| Windows and Center, Mart, and general poster strips | Represented | Asset-frame and alpha-cutoff tests |
| Contact shadows, picture rails, skirting, and doorway spill | Represented | Depth, cutoff, and light-boundary tests |
| Ceiling lamps, pooled light, detail, beams, and roses | Represented | Exact geometry, light placement, and GPU review |
| Cave roofs, stalactites, and stalagmites | Represented | Cave tileset and collision-safe visual corpus |
| Cave pools, torches, light spread, and bats | Represented | Animation, batching, and audio tests |

## Outdoor static world

| Legacy behavior to preserve | v2 decision | Current evidence still needed |
| --- | --- | --- |
| World apron, floor closure, deep skirt, neighbors, and distance haze | Represented | Map-edge and connection corpus |
| Raised trees, stone stacks, mountains, and summits | Represented | Semantic-tag and cross-map tests |
| Boulder-tree hoods | Represented | Red, Blue, and Yellow placement corpus |
| Object shadows | Corrected | Separate option, alpha cutoff, caster pass, and GPU review |
| Battle trees, boulder hoods, and other opaque props | Represented | Battle phase and occlusion corpus |
| Shore detection and water-edge effects | Represented | Coast and lake corpus; no full-map render scan |

## Sky, weather, flora, and wildlife

| Legacy behavior to preserve | v2 decision | Current evidence still needed |
| --- | --- | --- |
| KANTO, FUJI, VALLEY, and CITY panoramas | Represented | Name-to-asset and HIGH/BALANCED/LOW file selection are locked by tests and a public hash inventory; GPU tiling still needs review |
| Three cloud decks | Represented | Parallax and day/night blending |
| Stars, nebula, twinkle, and shooting stars | Represented | Night timing and deterministic seed tests |
| Distant birds and derived local bird frames | Open | Import transform exists, but no public runtime resolver emits them; alpha control is hidden |
| Ground flocks that reset by map | Open | No executable packet is emitted; alpha control is hidden |
| Planes, contrails, and rare blimps | Represented | Spawn timing, batching, and visibility tests |
| Rain, storms, lightning, umbrellas, puddles, splashes, and rainbows | Represented | Weather transitions and photosensitivity review |
| Lavender fog and the 1.60 veil | Represented | Lavender map tags and post-process cost |
| Night lamplight | Open | No runtime consumer; alpha control is hidden |
| Forest canopy, light wells, hanging vines, and sun shafts | Represented | Cutaway, sway, interaction, and mesh-lifetime tests |
| Grass height, wind, insects, leaves, seeds, drips, dust, spray, and smoke | Represented | Fixed-capacity pool and density policy tests |

## Audio and camera

| Legacy behavior to preserve | v2 decision | Current evidence still needed |
| --- | --- | --- |
| Cave, forest, night, rain, route, town, and shore ambient beds | Represented | Rights gate, loop points, cross-fade, and suspend/resume tests |
| Grass, cave, wood, door, and shop-door one-shots | Represented | Event routing, cadence, and volume review |
| Jump crouch, arc, landing settle, and independent head bob | Represented | Fixed-step timing and first-person camera corpus |
| Doorway step | Represented | Warp-distance false-positive tests |
| Narrow, normal, wide, and ultra first-person FOV | Represented | Host camera capability and projection tests |
| Depth blur levels | Represented | Depth source, quality policy, and GPU cost tests |

## Gameplay, diagnostics, and lifecycle

| Legacy behavior | v2 decision | Reason or gate |
| --- | --- | --- |
| Ledge Leap from any side | Open | A corrected pure policy exists, but alpha has no safe atomic engine execution seam. |
| Jump on the spot when no ledge matches | Retired | Invalid input must not consume the engine action or change player state. |
| Ledge Leap on upgrades | Corrected | Alpha forces it off. Bindings alone never enable it. |
| Two-cell seam leap through `queueScript` | Corrected | The policy rejects it. Normal engine input owns connection transitions. |
| Structured diagnostics | Represented | Bounded diagnostic and fault-isolation tests |
| Debug HUD | Open | No runtime consumer; alpha control is hidden |
| Optional feature failures | Corrected | A feature circuit breaker isolates the failure. Silent success is not allowed. |
| Live config bridge through `_G` | Retired | KFP uses injected services and immutable snapshots. |
| Per-frame option reads | Retired | Refresh is event-driven and generation-based. |
| Global random reseeding | Retired | Each feature uses deterministic local seeds. |

### Ledge Leap contract

`LedgeLeapPolicy.decide(request)` receives copied facts only. The request must
state free-roam, script, input-lock, player movement, surfing, hop, map,
front-cell, landing-cell, occupancy, and ledge-registry data. Unknown state is a
denial.

An allowed result matches `tileset`, `facing`, `input`, `standingTile`, and
`ledgeTile`. It names a two-cell movement but performs no action. The separate
runtime adapter validates the decision again and passes one bounded row list to
its injected `queue_script` function. It never writes player state directly.

The policy checks no more than 256 ledge rules. It rejects off-map landings
because queued scripted movement does not own Gen1recomp connection changes.

`InputBinding.new({ keyboard, gamepads, diagnostics? })` receives normalized
facades. The keyboard facade supplies `isDown(key)`. The gamepad collection
supplies `list()`, and each returned controller supplies `isDown(button)` and an
optional `isGamepad()`.

`binding:poll(config)` returns `true, "keyboard"` or `true, "gamepad"` only on
a rising edge. It returns `false` for OFF, disabled, held, invalid, or failed
input. Enable, reset, and rebind transitions prime held controls without an
action.

Alpha does not construct this binding, install an `input.step` hook, retain
host ledge facts, or queue movement. Gen1recomp must first expose one public,
synchronous, atomic attempt that owns current control state, collision,
scripts, actors, warps, ledge direction, and movement side effects. The pure
policy and binding modules remain ROM-free test targets only until that seam
exists.

## Removed legacy systems

The following systems must not return:

- source splices, host-file writes, shadow copies, backup files, write ledgers,
  self-removal, and the `REMOVE PATCH` action;
- Building Backs until a new semantic face detector has independent evidence;
- Cave Darkness opaque shells;
- the old unauthored `mountains` cluster-depth attempt;
- Window Light blocks; and
- Sun Bloom made with the opaque alpha-cutoff shader.

The current `MOUNTAIN PEAKS` feature is separate from the retired `mountains`
attempt.

## Release parity gates

`tests/integration/test_synthetic_scene_golden.lua` now provides the public,
ROM-free declarative packet lane. Its authored fixtures cover interior, cave,
forest, city and Lavender, connected route edges, shore, mountain, day, night,
rain, storm, and supported and unsupported battle output. Reviewed hashes lock
packet structure. The test also checks API v1 portable commands, phases,
materials, batch and tier limits, borrowed-host-object isolation, path removal,
and distinct HIGH, BALANCED, and LOW output.

This lane is not a pixel golden and does not prove GPU, host, real-map, or game
parity. Those claims remain open until the later gates provide direct evidence.

No item is complete until the applicable gates pass:

1. ROM-free unit and contract tests inspect deterministic commands.
2. Synthetic render tests verify phase, material, depth, blend, and batch keys.
3. Private player-owned Red, Blue, and Yellow review verifies visual placement.
4. Battle Art and Dramaless adapters pass one companion
   conformance suite.
5. Frame time, build slices, cache limits, draw calls, pools, and release counts
   stay inside HIGH, BALANCED, and LOW policy.
6. Map change, option change, host change, reload, suspend, and shutdown release
   every owned resource once.
7. Windows, Linux, macOS, Android, iOS, Switch, Xbox, PortMaster, and Anbernic
   claims stay open until device owners provide evidence.
8. Packaged legacy art and audio have a private creator grant and a hash-bound
   inventory. Any asset change must refresh that evidence before release.

Unverified behavior must stay marked Open. A source-level match is not a device,
host, performance, or visual pass.
