# KFP 2.0 Alpha Known Limitations

This record describes the current `2.0.0-alpha.1` source candidate. It is not
a waiver for a failed release gate.

## Installation and compatibility

- Battle Art and Dramaless compatibility exists only on the submitted PR
  branches until the host owners merge and publish releases. [Battle Art PR
  #29](https://github.com/absol89/DramaticShapeVoxelMod/pull/29) is open and
  mergeable at `cee25fd`; 2,636 host, 11 lifecycle, and 54 companion checks
  pass. [Dramaless PR
  #47](https://github.com/artyrambles/DRAMALESS_SHAPE/pull/47) is open and
  mergeable at `f757544`; 89 host and 59 syntax checks pass. These results do
  not make either branch an owner-published release.
- KFP needs exactly one compatible active voxel host. Zero or two compatible
  hosts leave KFP inactive by design.
- An old KFP installation can leave modified host files. KFP 2 does not repair
  them. Reinstall a clean host before testing, upgrading, disabling, or
  removing KFP. Follow the [safe upgrade sequence](upgrade-v1-to-v2.md).
- Current runtime activity is Windows-only and has no accepted visual or
  performance matrix. All platforms remain experimental until device owners
  complete the native runtime QA matrix.

## Games and visual evidence

- The public suite is ROM-free and does not prove real-game visual output.
- Yellow is the only private game import currently available for local review.
  A diagnostic restart proved that both host PR branches activate KFP. The live
  Dramaless scene showed the panorama with incorrect placement and repeated
  bands. The live Battle Art scene showed oversized translucent cloud and
  canopy geometry. Before that restart, the Dramaless Mart also lacked visible
  KFP walls and ceilings. Source fixes now correct the panorama contract,
  cloud ownership and alpha rules, canopy cutaway coordinates, and interior
  cutaway behavior. A new live restart and capture must prove those fixes.
  Red and Blue remain open.
- Represented effects still need host/GPU review. This includes interiors,
  caves, map edges, weather, skies, camera behavior, audio, battles, shadows,
  quality tiers, and transitions.
- Wildlife birds and ground flocks emit no runtime draw packet. All five pinned
  Gen1recomp targets can build the transform output, but none has a public,
  owner-scoped runtime image resolver. The exact blocker and bounded upstream
  proposal are in the
  [derived-asset runtime API proposal](derived-asset-runtime-api-proposal.md).
- API v1 permits only `mesh`, `instances`, and `billboards` draw commands. It
  has no portable light or post-process command. Doorway light, lightning,
  Lavender fog, and depth blur therefore emit no alpha packet. Their migration
  values remain stored, but their controls stay hidden.
- Third-person and diorama ceilings now emit portable NONE, CUTAWAY, and FULL
  policies. Ceiling detail emits portable beams and roses. Their controls are
  visible, but camera-mode placement and GPU review remain open.
- Night lamplight and the debug HUD also have no certified runtime consumer and
  stay hidden.
- Rich battle props, object-shadow passes, and terrain lifts remain disabled on
  a host that does not advertise the matching optional capability.

## Gameplay

- Ledge Leap is hidden and forced off. Its policy is tested, but Gen1recomp
  does not expose one atomic public movement attempt that owns all collision,
  script, actor, warp, and movement side effects.
- `affects_link=true` remains in the manifest because a later compatible
  version can enable this gameplay-changing option.

## Performance and release state

- [CI run
  32570167507](https://github.com/BoLayerDev/kanto-first-person/actions/runs/32570167507)
  passed 11 public jobs at exact KFP commit
  `cfc045bec72c2ceecd558b24bcd643c8e0b720dc`. The run covers Windows,
  Linux, macOS, both pinned LuaJIT hash runtimes, all five engine pins, and the
  website build. Its v0.2.19 job reproduced a private package byte for byte.
  This checkpoint does not approve a public package, a signed tag, live visual
  output, or native performance.
- Packet-seal, numeric-hash, and fixed scene-vector correctness pass on both
  exact LuaJIT pins. Shared-CI wall timing is structural and advisory. Native
  CPU/GPU frame time, draw calls, complete uncached-scene readiness,
  100-transition resource stability, and a 30-minute soak remain open.
- The v1-to-v2 migration-safety gate remains open. ROM-free tests now cover
  the exact KFP entry and manifest through the real Loader on all five pinned
  engine commits. They also cover option migration, clean registration,
  disabled and removed boots, synthetic legacy refusal, fail-closed integrity
  handling, quit cleanup, and host-source nonmutation. They do not prove the
  real adapters, installed host hashes, or a live shutdown. Both
  owner-published hosts still need the final release-candidate procedure in
  the [upgrade guide](upgrade-v1-to-v2.md).
- No public alpha package is approved. Existing packages are private,
  non-publishable engineering artifacts.
- Stable publication also needs Red, Blue, and Yellow acceptance, native
  platform evidence, community review, a fresh engine audit, uninstall
  integrity, deterministic signed packages, and official compatible host
  releases.
