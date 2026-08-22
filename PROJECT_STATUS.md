# Project Status

Last updated: 2026-08-21

## Current truth

- State: implementation in progress.
- Active branch: `v2-rewrite`.
- Private remote: `https://github.com/BoLayerDev/kanto-first-person`.
- Original history: preserved from `mrmushrooms11/kanto-first-person` at `94d0151`.
- Engine targets: Gen1recomp `v0.2.17` (`44f4680`), `v0.2.18`
  (`70d7b6`), baseline `dev` (`06e06e3`), and current `dev` (`087a275`).
- Runtime target: LuaJIT / Lua 5.1, LÖVE 11.5, and LÖVE 12 on iOS.
- Current milestone: `2.0.0-alpha.1` source-integration candidate.

## Active workstreams

- Coordinator: repository foundation, composition root, renderer, features, assets, integration, and release checks.
- Companion API lane: `companion/`, API specification, and contract fixtures.
- Core lane: `src/core/`, core tests, test harness, and CI.
- Config/gameplay lane: `src/config/`, `src/gameplay/`, option migration, parity, and tests.

## Known risks

- The Git tag named `firstperson1.60.0` contains manifest version 1.57.2. The release archives contain unpublished 1.60 source.
- The old mod can leave unsafe source edits inside voxel hosts.
- Both adapters are pushed to `BoLayerDev` forks and submitted upstream. Battle
  Art PR #29 and Dramaless PR #47 await host-owner review, merge, versioning,
  release, and real GPU testing.
- Frozen adapter evidence commits are `0185b44` (Battle Art) and `bc24063`
  (Dramaless). Canonical patches are outside Git
  under `Kanto First Person Evidence\host-patches`.
- The repository has legacy audio and art but no historical license file.
- Full real-game visual validation needs private player-owned imports and cannot run in public CI.
- Native Switch, Xbox, iOS, Android, PortMaster, and Anbernic gates need device owners.

## Recovery point

- Original baseline remains available at Git commit `94d0151be839f02fea4a35ab1c3df41fbaddc6c1`.
- Runtime checkpoint `568ef6994fa9cb8daae5fc0853bab6b589b961f2` is
  committed locally and passes an independent-clone restore test.
- The private remote tracks the maintained rewrite on `v2-rewrite`. Use
  `git ls-remote origin refs/heads/v2-rewrite` for the current immutable SHA.
- A fresh clone from the private remote passed the Lua suite, syntax gate,
  repository policy gate, Python release-control suite, and removed-host scan.
- Existing local Gen1recomp workspaces are not part of this project and must remain unchanged.

## Next actions

1. Run both adapter branches in real Gen1recomp GPU sessions.
2. Complete corrected 1.60 visual and device evidence.
3. Obtain host-owner review and released adapter versions from
   `absol89/DramaticShapeVoxelMod#29` and `artyrambles/DRAMALESS_SHAPE#47`.
4. Send `docs/asset-permission-request-template.md` and preserve the signed
   modification and redistribution grant.
5. Create or import a protected GPG release key, back it up, and record only
   its public fingerprint in repository configuration and release evidence.
6. Complete performance, leak, platform, reproducibility, and uninstall gates.

## Completion rule

Do not label `2.0.0` stable while any host, rights, parity, platform, reproducibility, uninstall-integrity, or upstream-compatibility gate is open.
