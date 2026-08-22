# Source and Provenance Registry

## Gen1recomp

- Minimum stable release: `v0.2.17` at
  `44f4680b24823629489ed5a2adad648d0dceb640`.
- Latest audited stable release: `v0.2.19` at
  `116a6ba450dd65f25c9be150952fc3c27be904c0`.
- Retained stable target: `v0.2.18` at
  `70d7b6383e2c005857013dc897fd096886b08f0b`.
- Baseline audited dev commit:
  `06e06e305bbcefe97c216a31bb25265ffb5e6b18`.
- Current audited dev commit:
  `478e3bf8ebf7646edfda88320c6472cf32db2e67`.
- Current engine audit record:
  `docs/release-evidence/gen1recomp-2026-08-22.json`.
- Sandbox change: `83682f011df5039c4ea7042141590d38ca7e21d5`.
- Source: `https://github.com/bryanthaboi/gen1recomp`.

## KFP alpha checkpoint

- Public source commit:
  `cfc045bec72c2ceecd558b24bcd643c8e0b720dc`.
- [CI run
  32570167507](https://github.com/BoLayerDev/kanto-first-person/actions/runs/32570167507):
  all 11 jobs passed on Windows, Linux, macOS, both pinned LuaJIT hash
  runtimes, all five pinned Gen1recomp targets, and the website build.
- The v0.2.19 job reproduced the private test package byte for byte.
- `README.md` is part of the audited package. Its `af8610c` CI link is an
  intentional historical checkpoint in those exact bytes, not the current
  alpha ledger. Change it only before a new exact package-integrity audit.
- A fresh public clone matched commit
  `cfc045bec72c2ceecd558b24bcd643c8e0b720dc`, Git tree
  `7ef75f14ec471ed8e78dae68e438dda4063b0efd`, and all 197 tracked files.
  Source-integrity record SHA-256:
  `152fef45e4201951d95b1bbc9c6bdc08d2f6be8f56355f8a4680dedbf016b95e`.
- The 76-file runtime fingerprint is
  `534a6aa7af6d97985d34781031dc8bb27031bc3c93014482c8e4e49be21cb756`.
  Two fixed-epoch builds produced ZIP SHA-256
  `84b62b890a1eb6a86d2a1426b4f5b4afc0e150d8d71deaa0f3664c65696b81a4`
  and MODPKG SHA-256
  `dbe52f2d023a3a3fcd2fd4f0d553119e318af79966e0a74a9a1c590415d4b4c2`.
- Shared-CI timing is structural and advisory. It is not native or full-scene
  performance evidence.
- Machine-readable evidence:
  `docs/release-evidence/alpha-readiness-2026-08-22.json`.

## Preserved KFP historical checkpoint

- Public source commit
  `0683051a9ade567df8f5a5a73a2693646274e578` passed CI run
  `32561890609` on Windows, Linux, macOS, and all five pinned engine commits.
- Its source-integrity record remains at
  `private-evidence://source-integrity/2026-08-22-0683051/source-integrity.json`
  with SHA-256
  `e17cd7141f9b6d884108912c6fdc11fee1dcf55c94094e47ec23fb8274721260`.
- Its byte-preserved public readiness record is
  `docs/release-evidence/alpha-readiness-2026-08-22-0683051.json` with
  SHA-256
  `688cc40cfd3b6011f74b6a92611caf72765bdbc64fec139364099d0690ef4e6b`.

## Kanto First Person legacy

- Git source commit: `94d0151be839f02fea4a35ab1c3df41fbaddc6c1`.
- Git manifest version at that commit: `1.57.2`.
- Release URL: `https://github.com/mrmushrooms11/kanto-first-person/releases/tag/firstperson1.60.0`.
- Release ZIP SHA-256: `b54b28271918aaab9a11ced66247898e51cff5e5f03d3530ff3b81bb3b25af29`.
- Release MODPKG SHA-256: `28ce02e4bf57143677a9664146ad45814818f213f5e3b53ceb4546a8cf3a80b8`.
- Published 1.60 `main.lua` SHA-256:
  `79b0099852cfced98977682892259ef7af534b6fa3c5bb790da5f2f9024597f2`.
- Status: code and behavior reference only. The release archives are not reproducible from the tag.

## Proof branch

- Commit: `e1f3d8111bdad1c5f69528c78f575d42d181b5d0`.
- Source: `https://github.com/artyrambles/kanto-first-person/tree/proof-of-concept-rewrite`.
- Status: design evidence only. Do not cherry-pick.

## Initial voxel host baselines

- Battle Art: `BATTLE_ART_VOXEL_FORK` 1.9.7, commit `fcbe541676cd7f245fa73df3d01dcbabec37a1fe`.
- Dramaless Shape: `DRAMALESS_SHAPE` 2.0.3, commit `f14795b17e85d5d5baedcad63944065e446a4b0b`.

Fork adapter commits and patch hashes are implementation evidence only.
They are not host-owner releases:

- Frozen companion API (`companion/api_v1.lua`) SHA-256:
  `6fded9c804298ab064db61b908382be7c9a74ad29d611444c33e1bcc53a33d26`.
- Shared draw fixture (`tests/fixtures/voxel_companion_draw_v1.lua`) SHA-256:
  `de1dca98a04ad9446b0af4c13523dab7f365bc7a76e70bc44b24f323d98a9bfa`.
- Battle Art adapter: `cee25fd117d881aa63ad7ef0bc7905ca0063fb29`;
  patch SHA-256
  `5d65aabd8a4f759cc28d57c97173ff4e521466d25d414f340b4796fb8a5e6539`.
  The branch passes 2,636 host, 11 lifecycle, and 54 companion checks.
- Dramaless adapter: `f7575445d00593b7db1ecd66f93e8c26989f4136`;
  patch SHA-256
  `2b771ec588cd9ea34b24d9e820b23015fb11d3ec684ef6e7fd53c7ee220180df`.
  The branch passes 89 host checks and 59 Lua syntax checks.
- Battle Art delivery fork and upstream review:
  [delivery branch](https://github.com/BoLayerDev/DramaticShapeVoxelMod/tree/kfp-companion-api-v1)
  and [Battle Art PR #29](https://github.com/absol89/DramaticShapeVoxelMod/pull/29),
  which is open and mergeable at the recorded head.
- Dramaless delivery fork and upstream review:
  [delivery branch](https://github.com/BoLayerDev/DRAMALESS_SHAPE/tree/kfp-companion-api-v1)
  and [Dramaless PR #47](https://github.com/artyrambles/DRAMALESS_SHAPE/pull/47),
  which is open and mergeable at the recorded head.

## Private evidence

Permission-message exports, screenshots, downloaded release archives, pinned
runtimes, and private test artifacts belong in the sibling directory
`C:\Users\bolay\Documents\Kanto First Person Evidence`. Record hashes in its
private index. Do not move that evidence into the mod root or commit it.
