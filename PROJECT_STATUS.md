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
- Current milestone: `2.0.0-alpha.1` source-evidenced candidate.
- Exact public source checkpoint
  `cfc045bec72c2ceecd558b24bcd643c8e0b720dc` passed
  [CI run 32570167507](https://github.com/BoLayerDev/kanto-first-person/actions/runs/32570167507)
  in all 11 jobs: Windows, Linux, macOS, both pinned LuaJIT hash runtimes, all
  five pinned engine commits, and the website build.
- A fresh clone, source archive, strict 76-file runtime allowlist, and two
  fixed-epoch v0.2.19 private package builds passed with zero mismatches. The
  exact record is in the current alpha-readiness evidence.
- `README.md` remains byte-bound to source checkpoint `cfc045b`. Its older
  checkpoint links are historical evidence, not current host status. Do not
  edit it before a new exact package-integrity audit.
- The alpha ledger records asset rights, automated tests, companion contracts,
  known limitations, package reproducibility, and source integrity as passed.
  It remains unapproved. Released hosts and migration safety are false. Live
  visual acceptance, native and complete uncached-scene performance, signing,
  transition, and soak evidence remain open.
- Shared-CI packet-seal timing is structural and advisory. Native CPU/GPU,
  complete uncached-scene, transition, and soak performance remain open.

## Active workstreams

- Coordinator: repository foundation, composition root, renderer, features, assets, integration, and release checks.
- Companion API lane: `companion/`, API specification, and contract fixtures.
- Core lane: `src/core/`, core tests, test harness, and CI.
- Config/gameplay lane: `src/config/`, `src/gameplay/`, option migration, parity, and tests.
- Website showcase lane: `website/` and the Pages workflow are published at
  `https://bolayerdev.github.io/kanto-first-person/`. The
  merged `feature/gen1-options-terminal` work replaces the long scroll journey and
  scanner with one compact Gen 1-inspired options menu, a fixed-camera 3D
  diorama, keyboard/touch navigation, version palettes, field guides, and
  support routes. Merge commit `dec53c15fdc32285afae0313c8bbe7e8615b2def`
  passed [CI run 32560074293](https://github.com/BoLayerDev/kanto-first-person/actions/runs/32560074293)
  and [Pages run 32560074192](https://github.com/BoLayerDev/kanto-first-person/actions/runs/32560074192).
  The production route and all 10 generated assets return HTTP 200.
  Desktop/mobile browser QA remains open.

## Known risks

- The Git tag named `firstperson1.60.0` contains manifest version 1.57.2. The release archives contain unpublished 1.60 source.
- The old mod can leave unsafe source edits inside voxel hosts.
- [Battle Art PR
  #29](https://github.com/absol89/DramaticShapeVoxelMod/pull/29) merged from
  `cee25fd117d881aa63ad7ef0bc7905ca0063fb29`, and owner release `1.9.8` at
  `6586ef5f7a86c1bfefcea931bd6571538c9f8d15` contains the approved companion
  runtime. Its 2,636 host, 11 lifecycle, and 54 companion checks pass; live GPU
  acceptance remains open. [Dramaless PR
  #47](https://github.com/artyrambles/DRAMALESS_SHAPE/pull/47) remains open and
  dirty at `f7575445d00593b7db1ecd66f93e8c26989f4136`; its 89 host checks and
  59 syntax checks pass. Owner release `v2.0.3` at
  `23750150ae6f939e09f9ac6ca6d80c382ec9997a` lacks the approved companion
  runtime. Dramaless still needs conflict resolution, merge, a replacement
  owner release, and live GPU testing.
- Both adapter heads commit Git-identical copies of the frozen KFP API and
  shared fixture. Their canonical source SHA-256 values are
  `6fded9c804298ab064db61b908382be7c9a74ad29d611444c33e1bcc53a33d26`
  and
  `de1dca98a04ad9446b0af4c13523dab7f365bc7a76e70bc44b24f323d98a9bfa`.
- Legacy audio and art remain outside MIT but now have a private creator-signed
  modification and redistribution grant with a redacted hash-bound record.
- Full real-game visual validation needs private player-owned imports and cannot run in public CI.
- Two isolated Yellow QA profiles use Battle Art `1.9.8` and the unreleased
  Dramaless `f757544` companion candidate.
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
- The frozen API v1 draw baseline contains only `mesh`, `instances`, and
  `billboards`. Doorway light, lightning, Lavender fog, and depth blur keep
  their migrated values but emit no alpha packet and have hidden controls.
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
- Historical public checkpoint `0683051a9ade567df8f5a5a73a2693646274e578`
  passed CI run 32561890609 across three hosted operating systems and five
  pinned engine commits. Its fresh-clone, source-integrity, and package
  evidence remain preserved as history and are not referenced by the current
  alpha ledger.
- Existing local Gen1recomp workspaces are not part of this project and must remain unchanged.

## Next actions

1. Push the evidence-only commit and wait for green CI. Verify that all 76
   package-allowlisted files remain byte-identical to source checkpoint
   `cfc045bec72c2ceecd558b24bcd643c8e0b720dc`.
2. Stage the exact private package for controlled Yellow QA. Ask for fresh
   approval before closing or restarting either active host process.
3. Complete the Yellow visual, lifecycle, performance, transition, and soak
   matrix; import legally owned Red and Blue copies before their private runs.
4. Complete live acceptance for Battle Art `1.9.8`. Resolve, merge, and obtain
   a companion-enabled owner release from [Dramaless PR
   #47](https://github.com/artyrambles/DRAMALESS_SHAPE/pull/47).
5. Keep the private rights inventory hash aligned if any covered legacy asset
   changes; never publish the original permission pages.
6. Request and re-audit an official owner-scoped derived-image API before any
   KFP wildlife runtime or option change.
7. Create or import a protected GPG release key, back it up, and record only
   its public fingerprint in repository configuration and release evidence.
8. Complete performance, leak, platform, reproducibility, and uninstall gates.
9. Run separately approved desktop and mobile website QA, then record canvas
   diagnostics and repair any visual or interaction findings.

## Completion rule

Do not label `2.0.0` stable while any host, rights, parity, platform, reproducibility, uninstall-integrity, or upstream-compatibility gate is open.
