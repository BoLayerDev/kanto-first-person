# Kanto First Person 2.0

Kanto First Person (KFP) is a safe companion for Gen1recomp voxel hosts. The
v2 rewrite adds first-person world detail without reading, changing, restoring,
or deleting another mod's files.

Current release state: **`2.0.0-alpha.1` development source**. It is not a
stable end-user release. All three local host adapters pass source-level
contract tests, but host-owner releases, real GPU tests, visual parity, asset
rights, devices, and stable release gates are still open.

## Safety model

- KFP keeps the existing mod ID `ds_fp_ceiling`.
- It requests no permissions.
- The voxel host keeps the only active `drawWorld` pipeline.
- KFP registers through Voxel Companion API v1.
- Zero or multiple compatible hosts make KFP inactive.
- A KFP callback failure disables that extension, not the host renderer.
- Removing KFP cannot change a host source tree.
- The old patcher, backups, file ledger, and `REMOVE PATCH` option are gone.

## Compatibility baseline

Development is pinned to:

- Gen1recomp `v0.2.17` at `44f4680b24823629489ed5a2adad648d0dceb640`.
- Gen1recomp `v0.2.18` at `70d7b6383e2c005857013dc897fd096886b08f0b`.
- Gen1recomp baseline `dev` at `06e06e305bbcefe97c216a31bb25265ffb5e6b18`.
- Gen1recomp current `dev` at `087a2751895899ad6e79800599ae27a8f40cf1e3`.
- `DRAMATIC_SHAPE` 1.9.0 at `cd10ac3158db9a53e2e33efa3651935723715c9b`.
- `BATTLE_ART_VOXEL_FORK` 1.9.7 at `fcbe541676cd7f245fa73df3d01dcbabec37a1fe`.
- `DRAMALESS_SHAPE` 2.0.3 at `f14795b17e85d5d5baedcad63944065e446a4b0b`.

KFP supports Red, Blue, and Yellow by contract. A platform or host is not
certified until its recorded tests pass. See [compatibility](docs/compatibility.md).

## Implemented architecture

- Sandboxed module loader based on `mod:read()` and sandboxed `load()`.
- One immutable, migrated configuration snapshot per option generation.
- Exactly-one host discovery with capability checks.
- Normalized, bounded world snapshots.
- Incremental main-thread scene compilation with atomic packet swaps.
- Deterministic command batching for the five KFP render phases.
- Bounded diagnostics, scheduler, LRU, and exactly-once resource ownership.
- Declarative interiors, caves, outdoor structures, battle props, shadows,
  sky, flora, weather, wildlife, camera, and audio intent.
- A fail-closed, ROM-free Ledge Leap policy and input module. Alpha does not
  install its input hook or queue movement; the option is hidden and forced
  off until Gen1recomp supplies an atomic public movement-attempt API.

The command packets are host-neutral. A certified host adapter converts them
to its own public drawing operations and restores graphics state after each
extension callback.

## Build and test

Requirements:

- LuaJIT 2.1 or the LuaJIT bundled with LÖVE.
- Python 3 for the Gen1recomp mod kit.
- A clean checkout of a pinned Gen1recomp target for final validation.

Run the ROM-free suite:

```text
luajit tools/run_tests.lua
```

Then run the repository policy and syntax checks:

```text
luajit tools/check_syntax.lua
luajit tools/validate_project.lua
```

The deterministic package wrapper runs the pinned engine's strict validation,
ROM lint, and pack commands against a runtime-only staging tree. It reads the
engine from its pinned Git commit, not from local engine edits. Runtime source
must be Git-visible and match the explicit source and asset allowlist; ignored
files are never copied. The output directory must be outside this project:

```text
python tools/package_release.py --engine "<pinned-gen1recomp>" --output-dir "<private-output>" --epoch <unix-time> --allow-dirty
```

`--allow-dirty` marks an artifact as a private test build. Public release mode
refuses dirty source unless rights evidence, every machine-readable release
gate, the exact source commit, and a verified signed annotated tag all agree.
It also needs the trusted signer's full fingerprint through
`--trusted-signing-key` or `KFP_TRUSTED_SIGNING_KEY`. A public package copies
runtime files from that verified tag, not from the working tree.

Public tests do not need a ROM and do not contain extracted game data.

## Upgrade from v1

Old KFP releases could leave edits in a voxel host. Do not launch an old
patched host after you delete KFP v1.

1. Close Gen1recomp.
2. Reinstall the selected voxel host from a verified clean release.
3. Replace KFP v1 with KFP v2.
4. Start Gen1recomp and read the KFP compatibility status.

KFP v2 never tries to repair or delete host files. An updated host adapter
must refuse registration when it finds a known legacy splice marker. See the
[full upgrade guide](docs/upgrade-v1-to-v2.md).

## Rights

Independently authored v2 source is MIT licensed. Legacy panoramas, posters,
and audio are outside that grant. They remain blocked from a public stable
release until modification and redistribution rights have durable evidence.
See [third-party notices](THIRD_PARTY_NOTICES.md).

The bird transform ships only a recipe. It derives frames from the player's
own imported cache on that player's machine and does not package ROM data.

## Project records

- [Architecture](docs/architecture.md)
- [Voxel Companion API v1](docs/voxel-companion-api-v1.md)
- [Feature parity ledger](docs/feature-parity.md)
- [Option migration](docs/options-migration.md)
- [Machine-readable release gates](docs/release-gates.json)
- [Recovery record](docs/recovery-record.md)
- [Roadmap](ROADMAP.md)
- [Current status](PROJECT_STATUS.md)
- [Contribution rules](CONTRIBUTING.md)

Stable `2.0.0` remains blocked until every host, parity, rights, platform,
performance, packaging, and uninstall-integrity gate has recorded evidence.
