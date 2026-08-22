# KFP 2.0 Runtime QA Matrix

This matrix defines private real-game testing. ROMs, extracted cache data,
saves, and raw screenshots stay outside Git under the private evidence root.

## Fixed test identity

Record these values for every run:

- KFP source commit and package SHA-256;
- host ID, source commit, and package SHA-256;
- Gen1recomp version and commit;
- game version, map ID, player cell, facing, camera mode, and resolution;
- quality tier, option snapshot generation, fixed clock, and feature seed;
- operating system, GPU, driver, power mode, and display scale.

Use 1920 x 1080 for the Windows reference capture. Compare one host-only run
with one host-plus-KFP run from the same copied save and camera position.

## Scene corpus

| Scene class | Required examples | Required checks |
|---|---|---|
| Interior | House, Center, Mart, large building | Ceiling, cutaway, walls, doors, windows, posters, rails, lights |
| Cave | Dry cave, pool, ladder or warp | Roof, formations, water, sconces, depth, collision visibility |
| Forest | Dense forest and edge connection | Canopy, vines, grass, particles, cutaway, neighboring terrain |
| City | Standard city and Lavender | Apron, buildings, horizon, fog, night lighting |
| Route | Open route and connected edge | Neighbor seams, trees, props, mountains, distance haze |
| Shore | Coast or lake edge | Water boundary, shore tag, spray, reflections, apron |
| Weather | Clear, rain, storm, rainbow | Transitions, lightning, puddles, photosensitivity review |
| Sky | Day, sunset, night | Panorama, clouds, stars, aircraft, deterministic placement |
| Battle | Outdoor and indoor battle | Host remains usable; unsupported KFP battle work stays disabled |
| UI | Menu, dialogue, transition | Engine UI and field effects remain above the world correctly |

Run every scene in first person. Also sample third person and tilt/diorama so
KFP does not corrupt a host mode that it does not own.

## Lifecycle and failure corpus

- Start with no compatible host: KFP stays inactive with one diagnostic.
- Start with exactly one host: KFP attaches once.
- Start with both hosts: KFP stays inactive and does not choose silently.
- Use an incompatible API major: KFP rejects it without stopping the host.
- Use a known legacy splice marker fixture: the host refuses registration and
  performs no repair or deletion.
- Inject one extension callback fault per lifecycle phase: only KFP is
  quarantined and host rendering continues with graphics state restored.
- Exercise map entry, warp, reload, block replacement, option change, resize,
  suspend, resume, disable, hot reload, and shutdown.
- Hash both installed source trees before and after install, run, disable,
  update, and removal. Every hash must remain unchanged except for the
  task-owned copied test installation itself.

## Performance and resource corpus

Functional captures may use two simultaneous 1080p instances. Performance
measurements must run one instance at a time.

For each host and quality tier:

1. Warm caches.
2. Alternate host-only and host-plus-KFP 60-second runs five times.
3. Record median, p95, and p99 frame and KFP timing results.
4. Measure one uncached scene entry.
5. Alternate two stress maps 100 times.
6. Run a 30-minute map, battle, menu, suspend, and resume soak.
7. Collect Lua heap, cache cost, draw submissions, and owned GPU/audio counts.

The thresholds are normative in `docs/benchmark-method.md`. A run with GPU
contention, a driver change, a thermal change, or a different power mode is
invalid and must not be compared as equivalent evidence.

## Acceptance

A matrix cell passes only when:

- the expected KFP behavior is visible and no host or engine behavior regresses;
- no unexpected diagnostic, graphics-state leak, or resource growth occurs;
- the evidence names immutable source and package hashes;
- a human approves visual differences; and
- private game material remains outside Git and public packages.

Yellow can run with the currently installed private import. Red and Blue stay
open until the user imports legally owned copies. Windows is the immediate
native platform. Other platform claims stay experimental until device-owner
evidence uses this same matrix.

## Current runtime checkpoint

The exact KFP `ee5b735` files and both submitted host adapters were placed in
isolated Windows identities with Yellow. The first runtime inspection found
KFP disabled in both active option profiles. Those captures are host-only
baselines, not KFP runtime evidence. No scene-class, visual-acceptance,
performance, lifecycle, transition, or soak row is complete yet.
