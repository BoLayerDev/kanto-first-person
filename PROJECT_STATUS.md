# Project Status

Last updated: 2026-08-22

## Current truth

- State: implementation in progress.
- Active branch: `v2-rewrite`.
- Public remote: `https://github.com/BoLayerDev/kanto-first-person`.
- Original history: preserved from `mrmushrooms11/kanto-first-person` at `94d0151`.
- Engine targets: Gen1recomp `v0.2.17` (`44f4680`), `v0.2.18`
  (`70d7b6`), `v0.2.19` (`116a6ba`), baseline `dev` (`06e06e3`), and
  current `dev` (`478e3bf`).
- Runtime target: LuaJIT / Lua 5.1, LÖVE 11.5, and LÖVE 12 on iOS.
- Current milestone: `2.0.0-alpha.1` source-integration candidate.
- Public source checkpoint `af8610cc2ddd7bb4049c26ca7673c8d0a5319351`
  passed [CI run 32558047311](https://github.com/BoLayerDev/kanto-first-person/actions/runs/32558047311)
  on Windows, Linux, macOS, and all five pinned engine commits. The run includes
  256 ROM-free Lua tests, 84 Lua syntax checks, 28 Python tests, repository
  policy, and byte-for-byte private package reproduction on v0.2.19.
- Shared-CI packet-seal timing is structural and advisory. Native CPU/GPU,
  complete uncached-scene, transition, and soak performance remain open.

## Active workstreams

- Coordinator: repository foundation, composition root, renderer, features, assets, integration, and release checks.
- Companion API lane: `companion/`, API specification, and contract fixtures.
- Core lane: `src/core/`, core tests, test harness, and CI.
- Config/gameplay lane: `src/config/`, `src/gameplay/`, option migration, parity, and tests.
- Website showcase lane: `website/` and the Pages workflow are published at
  `https://bolayerdev.github.io/kanto-first-person/`. The
  `feature/gen1-options-terminal` branch replaces the long scroll journey and
  scanner with one compact Gen 1-inspired options menu, a fixed-camera 3D
  diorama, keyboard/touch navigation, version palettes, field guides, and
  support routes. Its local production build passes; publication and
  desktop/mobile browser QA remain open.

## Known risks

- The Git tag named `firstperson1.60.0` contains manifest version 1.57.2. The release archives contain unpublished 1.60 source.
- The old mod can leave unsafe source edits inside voxel hosts.
- Both final adapter heads are pushed to `BoLayerDev` forks. [Battle Art PR
  #29](https://github.com/absol89/DramaticShapeVoxelMod/pull/29) is open and
  mergeable at `cee25fd117d881aa63ad7ef0bc7905ca0063fb29`; 2,636 host, 11
  lifecycle, and 54 companion checks pass. [Dramaless PR
  #47](https://github.com/artyrambles/DRAMALESS_SHAPE/pull/47) is open and
  mergeable at `f7575445d00593b7db1ecd66f93e8c26989f4136`; 89 host checks and
  59 syntax checks pass. Both still need owner review, merge, versioning,
  release, and real GPU testing.
- Both adapter heads commit Git-identical copies of the frozen KFP API and
  shared fixture. Their canonical source SHA-256 values are
  `6fded9c804298ab064db61b908382be7c9a74ad29d611444c33e1bcc53a33d26`
  and
  `de1dca98a04ad9446b0af4c13523dab7f365bc7a76e70bc44b24f323d98a9bfa`.
- Legacy audio and art remain outside MIT but now have a private creator-signed
  modification and redistribution grant with a redacted hash-bound record.
- Full real-game visual validation needs private player-owned imports and cannot run in public CI.
- Two isolated Yellow QA profiles run the Battle Art and Dramaless PR branches.
  A diagnostic restart proved that both attach KFP. Live captures then exposed
  bad panorama placement and repeated bands in Dramaless, plus oversized
  translucent cloud and canopy geometry in Battle Art. A pre-restart Dramaless
  Mart capture also lacked KFP walls and ceilings. The common packet contract
  and both host renderers now have source-level corrections at the recorded PR
  heads. A controlled restart at those exact commits must verify the outdoor
  and interior results. Red and Blue imports are not present.
- Battle Art has two pre-existing strict Modkit `MK301` findings for its own
  ROM-cache interface files. The companion contract suite still passes.
- All five pinned Gen1recomp targets can build KFP's declared bird transform,
  but none exposes an owner-scoped public runtime image resolver. Birds and
  ground flocks stay hidden and emit no packet. The bounded upstream contract
  is in `docs/derived-asset-runtime-api-proposal.md`.
- Native Switch, Xbox, iOS, Android, PortMaster, and Anbernic gates need device owners.
- The website production route and static asset delivery pass HTTP checks. Its
  live canvas, desktop interaction, mobile layout, and renderer budget have not
  passed browser QA.

## Recovery point

- Original baseline remains available at Git commit `94d0151be839f02fea4a35ab1c3df41fbaddc6c1`.
- Runtime checkpoint `568ef6994fa9cb8daae5fc0853bab6b589b961f2` is
  committed locally and passes an independent-clone restore test.
- The public remote tracks the maintained rewrite on `v2-rewrite`. Use
  `git ls-remote origin refs/heads/v2-rewrite` for the current immutable SHA.
- Public source checkpoint `af8610cc2ddd7bb4049c26ca7673c8d0a5319351`
  passed CI run 32558047311 across three hosted operating systems and five
  pinned engine commits.
- A fresh clone of exact public commit `af8610c` matched its Git tree, index,
  checkout, 166-file archive, and strict package allowlist. Git object, unsafe
  path, link, and secret checks passed. The hash-bound source-integrity record
  is referenced from the alpha evidence ledger.
- Existing local Gen1recomp workspaces are not part of this project and must remain unchanged.

## Next actions

1. Complete the Yellow visual, lifecycle, performance, transition, and soak
   matrix; import legally owned Red and Blue copies before their private runs.
2. Obtain host-owner review and released adapter versions from [Battle Art PR
   #29](https://github.com/absol89/DramaticShapeVoxelMod/pull/29) and
   [Dramaless PR #47](https://github.com/artyrambles/DRAMALESS_SHAPE/pull/47).
3. Keep the private rights inventory hash aligned if any covered legacy asset
   changes; never publish the original permission pages.
4. Request and re-audit an official owner-scoped derived-image API before any
   KFP wildlife runtime or option change.
5. Create or import a protected GPG release key, back it up, and record only
   its public fingerprint in repository configuration and release evidence.
6. Complete performance, leak, platform, reproducibility, and uninstall gates.
7. Run separately approved desktop and mobile website QA, then record canvas
   diagnostics and repair any visual or interaction findings.

## Completion rule

Do not label `2.0.0` stable while any host, rights, parity, platform, reproducibility, uninstall-integrity, or upstream-compatibility gate is open.
