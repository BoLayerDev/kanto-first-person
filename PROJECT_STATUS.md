# Project Status

Last updated: 2026-08-21

## Current truth

- State: implementation in progress.
- Active branch: `v2-rewrite`.
- Public remote: `https://github.com/BoLayerDev/kanto-first-person`.
- Original history: preserved from `mrmushrooms11/kanto-first-person` at `94d0151`.
- Engine targets: Gen1recomp `v0.2.17` (`44f4680`), `v0.2.18`
  (`70d7b6`), baseline `dev` (`06e06e3`), and current `dev` (`478e3bf`).
- Runtime target: LuaJIT / Lua 5.1, LÖVE 11.5, and LÖVE 12 on iOS.
- Current milestone: `2.0.0-alpha.1` source-integration candidate.
- Current common-source gates pass: 227 Lua tests, 81 Lua syntax checks,
  28 Python tests, repository policy, deterministic cloud generation, and
  microbenchmarks.

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
- New Battle Art and Dramaless visual corrections are under final local review.
  The PR heads and canonical patch hashes will be refreshed only after the
  common sky contract and both host suites pass together.
- Legacy audio and art remain outside MIT but now have a private creator-signed
  modification and redistribution grant with a redacted hash-bound record.
- Full real-game visual validation needs private player-owned imports and cannot run in public CI.
- Two isolated Yellow QA profiles run the Battle Art and Dramaless PR branches.
  A diagnostic restart proved that both attach KFP. Live captures then exposed
  bad panorama placement and repeated bands in Dramaless, plus oversized
  translucent cloud and canopy geometry in Battle Art. A pre-restart Dramaless
  Mart capture also lacked KFP walls and ceilings. The common packet contract
  and both host renderers now have source-level corrections under review. A
  controlled restart at the final commits must verify the outdoor and interior
  results. Red and Blue imports are not present.
- Battle Art has two pre-existing strict Modkit `MK301` findings for its own
  ROM-cache interface files. The companion contract suite still passes.
- All four pinned Gen1recomp targets can build KFP's declared bird transform,
  but none exposes an owner-scoped public runtime image resolver. Birds and
  ground flocks stay hidden and emit no packet. The bounded upstream contract
  is in `docs/derived-asset-runtime-api-proposal.md`.
- Native Switch, Xbox, iOS, Android, PortMaster, and Anbernic gates need device owners.

## Recovery point

- Original baseline remains available at Git commit `94d0151be839f02fea4a35ab1c3df41fbaddc6c1`.
- Runtime checkpoint `568ef6994fa9cb8daae5fc0853bab6b589b961f2` is
  committed locally and passes an independent-clone restore test.
- The public remote tracks the maintained rewrite on `v2-rewrite`. Use
  `git ls-remote origin refs/heads/v2-rewrite` for the current immutable SHA.
- A fresh clone from the public remote passed the Lua suite, syntax gate,
  repository policy gate, Python release-control suite, and removed-host scan.
- Existing local Gen1recomp workspaces are not part of this project and must remain unchanged.

## Next actions

1. Complete the Yellow visual, lifecycle, performance, transition, and soak
   matrix; import legally owned Red and Blue copies before their private runs.
2. Obtain host-owner review and released adapter versions from
   `absol89/DramaticShapeVoxelMod#29` and `artyrambles/DRAMALESS_SHAPE#47`.
3. Keep the private rights inventory hash aligned if any covered legacy asset
   changes; never publish the original permission pages.
4. Request and re-audit an official owner-scoped derived-image API before any
   KFP wildlife runtime or option change.
5. Create or import a protected GPG release key, back it up, and record only
   its public fingerprint in repository configuration and release evidence.
6. Complete performance, leak, platform, reproducibility, and uninstall gates.

## Completion rule

Do not label `2.0.0` stable while any host, rights, parity, platform, reproducibility, uninstall-integrity, or upstream-compatibility gate is open.
