# Kanto First Person 2.0

Kanto First Person (KFP) is a safe visual companion for Gen1recomp voxel
hosts. It adds first-person world detail without reading, changing, restoring,
or deleting another mod's files.

Current state: **`2.0.0-alpha.1` development source**. This is not a stable
end-user release. The Battle Art and Dramaless adapters pass source-level
contract tests. Host-owner releases, real GPU tests, visual acceptance, asset
rights, device evidence, and stable release gates are still open.

## What changed in v2

KFP v1 inserted Lua source into another mod. That design became incompatible
with Gen1recomp's API 2 sandbox and could leave unsafe edits in a voxel host.
KFP v2 is a clean companion rewrite:

- It keeps the existing mod ID `ds_fp_ceiling` for settings migration.
- It requests no permissions.
- It does not inspect or mutate any host source tree.
- It does not install backups, ledgers, shadow files, or an unpatcher.
- It uses a small, versioned public contract: Voxel Companion API v1.
- The voxel host keeps full ownership of Gen1recomp's one active world
  pipeline.
- KFP supplies bounded, declarative scene work through the selected host.
- Removing KFP cannot alter the host.

The proof-of-concept branch informed the isolation model only. None of its
broken runtime code was copied into v2.

## Supported scope

### Games

- Pokémon Red
- Pokémon Blue
- Pokémon Yellow

Gold and Silver are outside this project.

### Gen1recomp baseline

| Target | Commit | Use |
|---|---|---|
| `v0.2.17` | `44f4680b24823629489ed5a2adad648d0dceb640` | Minimum supported version |
| `v0.2.18` | `70d7b6383e2c005857013dc897fd096886b08f0b` | Latest audited stable version |
| baseline `dev` | `06e06e305bbcefe97c216a31bb25265ffb5e6b18` | Original rewrite baseline |
| current `dev` | `087a2751895899ad6e79800599ae27a8f40cf1e3` | Current compatibility audit |

Manifest range: `>=0.2.17 <0.3.0`.

### Voxel hosts

| Host ID | Audited source | Adapter state |
|---|---|---|
| `BATTLE_ART_VOXEL_FORK` | 1.9.7 at `fcbe541676cd7f245fa73df3d01dcbabec37a1fe` | Local adapter passes contract tests; owner review and GPU run open |
| `DRAMALESS_SHAPE` | 2.0.3 at `f14795b17e85d5d5baedcad63944065e446a4b0b` | Local adapter passes contract tests; owner review and GPU run open |

KFP needs exactly one compatible active host. With zero hosts, KFP remains
inactive. With multiple compatible hosts, KFP also remains inactive and emits
one diagnostic. It never chooses an ambiguous renderer.

## User safety and upgrade

Old KFP releases can leave edits inside a voxel host. Use this sequence:

1. Close Gen1recomp.
2. Reinstall the selected voxel host from a verified clean release.
3. Replace KFP v1 with KFP v2.
4. Start Gen1recomp.
5. Check the KFP compatibility status.

Do not delete KFP v1 and then launch an old patched host. KFP v2 does not
repair, restore, or delete host files. An updated host adapter performs only a
read-only scan for known legacy splice markers. If it finds a marker, it
refuses companion registration and tells the user to reinstall that host.

See the [complete upgrade guide](docs/upgrade-v1-to-v2.md).

## Architecture at a glance

```text
Gen1recomp render_pipelines
          |
          v
Selected voxel host owns drawWorld
          |
          v
Voxel Companion API v1 dispatcher
          |
          v
KFP normalized world + immutable config snapshots
          |
          v
Incremental scene compiler + bounded resource caches
          |
          v
Host-native batches in controlled render phases
```

Gen1recomp permits one active `drawWorld` owner. KFP therefore does not
register a competing world renderer. Battle Art or Dramaless keeps its normal
official pipeline and calls the KFP extension inside that pipeline.

If KFP fails, the host renderer continues. If the host fails, Gen1recomp keeps
its own existing fallback behavior.

## Voxel Companion API v1

Each supported host exports:

```lua
provider.exports.voxel_companion = {
  api = 1,
  host = { id = "...", version = "..." },
  capabilities = {
    world_snapshot = 1,
    camera_delta = 1,
    render_phases = 1,
    quality_tier = 1,
    integrity_status = 1,
  },
  register = function(spec)
    -- Returns an idempotent disposable handle, or nil plus an error.
  end,
}
```

KFP registers one descriptor with identity, priority, required capabilities,
optional capabilities, lifecycle callbacks, and render callbacks. The core
callbacks are:

- `attach(services)`
- `worldChanged(snapshot)`
- `update(frame)`
- `modifyCamera(camera)`
- `invalidate(reason)`
- `dispose()`

Portable render phases are:

- `background`
- `opaque_after_terrain`
- `translucent_after_actors`

`shadow_casters`, `battle_opaque`, and `terrainPatch` are optional. KFP adds
them only when the selected provider advertises the matching capability.

### Contract rules

- API major versions must match.
- Required capabilities decide compatibility.
- A missing optional capability disables only its related feature.
- Host IDs are discovery addresses, not proof of compatibility.
- Callback contexts and host resources are borrowed and read-only.
- KFP does not retain live host objects after a callback.
- Camera callbacks return finite additive deltas in defined units.
- Terrain callbacks return declarative changes. They do not mutate map data.
- The host isolates graphics state around each extension callback.
- The host catches extension faults and disables only the failed extension.
- Fault cleanup cannot re-enter dispatch, registration, or dispatcher
  disposal.
- KFP releases every resource that it creates exactly once.
- `dispose()` is idempotent.

The normative contract, validation rules, and schemas are in
[Voxel Companion API v1](docs/voxel-companion-api-v1.md).

## Runtime lifecycle

1. `main.lua` reads the sandbox-safe module loader with `mod:read()`.
2. The composition root creates diagnostics, configuration, resources,
   features, renderer, scene compiler, and companion client.
3. KFP discovers only the two supported host IDs.
4. The client selects exactly one provider with all required capabilities.
5. KFP registers a host-specific descriptor.
6. The host supplies normalized world, quality, drawing, and integrity
   services.
7. World and option changes create new immutable generations.
8. The compiler builds a new scene in bounded main-thread slices.
9. A completed packet replaces the old packet atomically.
10. Invalidation, host removal, or shutdown releases owned resources once.

The host continues to draw its last valid scene while KFP builds a replacement.
No render callback reads a file, decodes an image, compiles a shader, scans a
full map, or builds a full scene.

## Source layout

| Path | Responsibility |
|---|---|
| `main.lua` | Minimal API 2 sandbox entry and composition root |
| `companion/` | Host-neutral API v1 reference dispatcher |
| `src/bootstrap/` | App lifecycle, dependency composition, and engine facade |
| `src/companion/` | Host selection and normalized world snapshots |
| `src/config/` | Immutable options and legacy migration |
| `src/core/` | Diagnostics, loader, RNG, scheduler, LRU, ownership, lifecycle |
| `src/render/` | Packet schema, hashes, quality, compiler, and submission |
| `src/features/` | Static world, atmosphere, weather, flora, camera, and audio intent |
| `src/gameplay/` | Disabled-by-default Ledge Leap policy and input code |
| `src/assets/` | Packaged texture ownership and derived-asset boundaries |
| `src/audio/` | Stream and one-shot source ownership |
| `tests/` | ROM-free unit, property, contract, and integration tests |
| `tools/` | Test, syntax, policy, benchmark, and package controls |
| `docs/` | Normative architecture, migration, parity, release, and recovery records |

Modules use constructor injection. Runtime code does not use `_G`, raw `io`,
raw `love.filesystem`, private engine `require`, `dofile`, `loadfile`, source
splicing, callback replacement, or `math.randomseed`.

## World snapshot boundary

Only host adapter code can inspect the host's broad engine state. It publishes
a normalized plain-data view with:

- Game and map identity
- Map, palette, tileset, and atlas revisions
- Bounds and cell size
- Current and neighboring terrain data
- Stable map tags
- Player pose
- Actor snapshots
- Render mode

KFP copies only validated fields. Snapshot capture has aggregate limits for
cells, nodes, text, metadata, tags, coordinates, and work. It rejects sparse,
cyclic, oversized, or malformed input before scene compilation. Host objects,
functions, metatables, and resource handles cannot enter the retained world
snapshot.

## Scene compiler and draw packets

The compiler runs incrementally on the main thread. It uses cancellation
generations and never asks for `background` or `compute` permission.

Cache identity includes:

- Companion API version
- Game and map identity
- Map revision
- Palette and atlas revision
- View mode
- Relevant option generations
- Selected host identity and capabilities
- Quality tier

Commands use draw schema v1. The portable packet kinds are `mesh`,
`instances`, and `billboards`. Each command has a bounded deterministic cache
key and canonical content hash. A host caches by copied key and digest, never
by retaining KFP's command table. Reuse of one key with different content
fails closed.

KFP batches compatible work by phase, owner, material, texture, primitive,
blend, and depth state. Dynamic effects use fixed limits. Cutaways use local
masks instead of full-scene rebuilds.

## Quality and performance model

| Tier | Build budget | KFP cache cap | Effect density | Added draw-call target |
|---|---:|---:|---:|---:|
| High | 2.0 ms/frame | 128 MiB | 100% | 48 or fewer |
| Balanced | 1.0 ms/frame | 64 MiB | 60% | 32 or fewer |
| Low | 0.5 ms/frame | 32 MiB | 30% | 20 or fewer |

`AUTO` follows the host quality tier. The user can select a fixed tier. High
uses the original panorama size. Balanced and Low are designed for prebuilt
2048 and 1024 variants when those approved assets are available.

Release performance gates include CPU p95 limits, bounded build slices,
draw-call limits, scene-ready latency, 30-minute heap stability, and no GPU or
audio resource growth across 100 alternating map transitions. Source tests do
not claim those device gates have passed.

## Features and parity

The architecture has isolated systems for:

- Interiors, ceilings, doors, windows, fixtures, and posters
- Caves, roofs, pools, sconces, and bats
- World edges, terrain apron, trees, mountains, and object grounding
- Sky, horizon, stars, clouds, aircraft, weather, fog, and rainbows
- Flora, canopy, vines, grass, particles, wildlife, and water effects
- Camera motion, field of view, depth effects, and audio intent
- Battle props and shadow casters when the host supports those phases

“Represented” in the parity ledger means the source can produce bounded
declarative intent. It does not mean final visual acceptance. Some alpha
options remain hidden when no honest runtime implementation exists. See the
[feature parity ledger](docs/feature-parity.md) for preserved, corrected,
retired, unavailable, and open behaviors.

## Options and migration

KFP records a migration version in mod-owned storage and accounts for all 53
unique release 1.60 option keys.

Important corrections:

- Legacy `shadows` maps only to `contact_shadows`.
- `object_shadows` gets its corrected v2 default because the duplicated old
  key could not retain two independent values.
- `fastchunks=false` maps to Low quality.
- `fastchunks=true` or a missing value maps to Auto quality.
- `REMOVE PATCH` is retired and never runs cleanup.
- Legacy keyboard and gamepad jump bindings are retained.
- Ledge Leap is never enabled by migration.
- Invalid live values keep the last safe stored value.

See [option migration](docs/options-migration.md) for the complete table.

## Ledge Leap status

Ledge Leap is gameplay-changing, so `affects_link` remains true. The v2 policy
and input modules validate directional, collision, script, warp, actor, and
state facts and use only a public movement-script queue.

The alpha does not install an input hook or queue movement. The option is
hidden and forced off because the current companion frame does not provide an
atomic public movement-attempt operation with fresh collision and script
facts. KFP will not restore the unsafe old behavior as a shortcut.

## Host adapter requirements

A host maintainer must:

1. Vendor the frozen API dispatcher and contract document.
2. Export `voxel_companion` from the existing official voxel pipeline.
3. Publish honest capability versions only.
4. Normalize broad engine state into the bounded world schema.
5. Call the fixed lifecycle and render phases in documented order.
6. Restore graphics state around every extension call.
7. Keep extension errors isolated from the host and other extensions.
8. Cache only host-owned compiled resources by copied key and content digest.
9. Never retain command tables or callback-borrowed resources.
10. Release host-owned compiled resources once on eviction or invalidation.
11. Perform only a read-only legacy-marker scan.
12. Pass the shared ROM-free packet fixture and companion conformance suite.

Current adapter commits and patches are local evidence only. They are not
released host versions and must receive host-owner review.

## Failure behavior

| Condition | Result |
|---|---|
| No supported host | KFP stays inactive and logs one diagnostic |
| Both supported hosts active | KFP stays inactive; it does not choose one |
| API major mismatch | Provider is rejected |
| Missing required capability | Provider is rejected |
| Missing optional capability | Only that feature is omitted |
| Invalid world snapshot | New scene is rejected; valid host scene continues |
| Feature compile fault | Optional feature is omitted or the active packet is preserved |
| Render callback fault | Failed extension is quarantined; host continues |
| Legacy splice marker | Host refuses companion registration and requests reinstall |
| Resource or cache limit | New work fails closed; capacity does not grow |

Diagnostics are structured, bounded, rate-limited, and available through the
mod export. KFP does not hide recurring frame faults with silent `pcall` loops.

## Build and verification

Requirements:

- LuaJIT 2.1 or the LuaJIT bundled with LÖVE
- Python 3
- A clean checkout of a pinned Gen1recomp target for final validation

Run the public ROM-free gates:

```text
luajit tools/run_tests.lua
luajit tools/check_syntax.lua
luajit tools/validate_project.lua
luajit tools/run_benchmarks.lua
python -m unittest tests.tools.test_package_release -v
```

Run strict engine checks for each pin:

```text
python <gen1recomp>/tools/modkit.py validate --strict --base fixture .
python <gen1recomp>/tools/modkit.py lint .
```

Public tests contain no ROM, save, extracted cache, or ROM-derived image. They
use synthetic maps, fixed seeds, fixed clocks, and the shared packet fixture.

## Deterministic packaging

The package wrapper:

- Accepts only audited engine commits.
- Archives engine tools from the pinned commit into isolated staging.
- Does not execute a dirty engine working tree.
- Copies only Git-visible, explicitly allowed runtime source and assets.
- Rejects duplicate JSON keys, unsafe paths, links, private files, and unknown
  package content.
- Runs strict validation, ROM lint, and Gen1recomp pack.
- Writes a root-level ZIP, `.modpkg`, SHA-256 list, and attestation.
- Uses `SOURCE_DATE_EPOCH` for reproducible output.

Private test build:

```text
python tools/package_release.py \
  --engine "<pinned-gen1recomp>" \
  --output-dir "<outside-project-directory>" \
  --epoch <unix-time> \
  --allow-dirty
```

`--allow-dirty` always marks the artifact as private and not publishable.
Release mode requires clean tagged source, every machine-readable gate,
approved rights evidence, and the trusted signer's complete fingerprint. It
builds from the verified signed tag, not the working tree.

## Rights and ROM boundaries

Independently authored v2 source is MIT licensed. Legacy panoramas, posters,
and audio are outside the MIT grant. Public redistribution remains blocked
until durable evidence confirms modification and redistribution rights.

The bird transform contains only a recipe. It derives frames on the player's
machine from that player's imported cache. KFP does not package the derived
output or ROM data.

Never commit or package:

- Pokémon ROMs
- Save files
- Extracted Gen1recomp cache content
- ROM-derived PNG files
- Credentials or private permission records
- Private device or real-game evidence

See [third-party notices](THIRD_PARTY_NOTICES.md).

## Release status and next gates

Source-level verification currently passes, but stable `2.0.0` still needs:

- Battle Art and Dramaless host-owner review, merge, versioning, and release
- Real GPU acceptance for Red, Blue, and Yellow
- Corrected full 1.60 visual parity
- Asset modification and redistribution rights
- Native evidence for every claimed platform class
- Performance and resource-leak soak evidence
- Reproducible tagged release and uninstall-integrity evidence
- Community review
- A fresh Gen1recomp audit before the release candidate

If any gate remains open, the project stays prerelease.

## Project records

- [Architecture](docs/architecture.md)
- [Voxel Companion API v1](docs/voxel-companion-api-v1.md)
- [Compatibility matrix](docs/compatibility.md)
- [Feature parity ledger](docs/feature-parity.md)
- [Option migration](docs/options-migration.md)
- [Upgrade guide](docs/upgrade-v1-to-v2.md)
- [Benchmark method](docs/benchmark-method.md)
- [Machine-readable release gates](docs/release-gates.json)
- [Source registry](docs/project-coordination/source-registry.md)
- [Risk register](docs/project-coordination/risk-register.md)
- [Recovery record](docs/recovery-record.md)
- [Roadmap](ROADMAP.md)
- [Current status](PROJECT_STATUS.md)
- [Contribution rules](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

Stable `2.0.0` must not be published until every required gate has recorded
evidence.
