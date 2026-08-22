# KFP 2.0 Alpha Known Limitations

This record describes the current `2.0.0-alpha.1` source candidate. It is not
a waiver for a failed release gate.

## Installation and compatibility

- Battle Art and Dramaless compatibility exists only on the submitted PR
  branches until the host owners merge and publish releases.
- KFP needs exactly one compatible active voxel host. Zero or two compatible
  hosts leave KFP inactive by design.
- An old KFP installation can leave modified host files. KFP 2 does not repair
  them. Reinstall a clean host before testing or upgrading.
- Current native runtime evidence is Windows-only. Other platforms remain
  experimental until device owners complete the runtime QA matrix.

## Games and visual evidence

- The public suite is ROM-free and does not prove real-game visual output.
- Yellow is the only private game import currently available for local review.
  Red and Blue remain open.
- Represented effects still need host/GPU review. This includes interiors,
  caves, map edges, weather, skies, camera behavior, audio, battles, shadows,
  quality tiers, and transitions.
- Wildlife birds and ground flocks emit no runtime draw packet because no
  approved public derived-asset resolver is available.
- Third-person ceilings, lamplight, and the debug HUD have no certified runtime
  consumer and stay hidden.
- Rich battle props, object-shadow passes, and terrain lifts remain disabled on
  a host that does not advertise the matching optional capability.

## Gameplay

- Ledge Leap is hidden and forced off. Its policy is tested, but Gen1recomp
  does not expose one atomic public movement attempt that owns all collision,
  script, actor, warp, and movement side effects.
- `affects_link=true` remains in the manifest because a later compatible
  version can enable this gameplay-changing option.

## Performance and release state

- Source microbenchmarks pass, but real GPU frame-time, draw-call, scene-ready,
  100-transition, and 30-minute soak evidence is incomplete.
- No public alpha package is approved. Existing packages are private,
  non-publishable engineering artifacts.
- Stable publication also needs Red, Blue, and Yellow acceptance, native
  platform evidence, community review, a fresh engine audit, uninstall
  integrity, deterministic signed packages, and official compatible host
  releases.
