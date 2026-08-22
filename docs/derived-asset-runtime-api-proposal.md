# Derived Asset Runtime API Proposal

Audited: 2026-08-21

## Decision

KFP must not enable birds or ground flocks on the current engine targets.
Gen1recomp can build the declared `assets_transforms` output, but its public mod
facade cannot return a mod-owned derived image at runtime.

No KFP runtime code changed during this audit. The existing fail-closed state is
correct:

- `transform_birds.lua` can derive local bird frames during import;
- `src/features/Wildlife.lua` emits no bird or ground-flock packet;
- the `birds` and `groundflock` options stay hidden; and
- no code reads a ROM path, generated cache path, private engine module, or
  another mod's files.

## Audit scope

The audit used KFP commit
`3b21b584816ecd2f6a557678eadb83d28df526a0` and these exact public
Gen1recomp commits:

| Target | Commit | Result |
| --- | --- | --- |
| v0.2.17 | `44f4680b24823629489ed5a2adad648d0dceb640` | No public derived-image resolver |
| v0.2.18 | `70d7b6383e2c005857013dc897fd096886b08f0b` | No public derived-image resolver |
| Dev baseline | `06e06e305bbcefe97c216a31bb25265ffb5e6b18` | No public derived-image resolver |
| Dev current | `478e3bf8ebf7646edfda88320c6472cf32db2e67` | No public derived-image resolver |

The relevant engine files are byte-identical on all four targets except for an
unrelated Gen 2 import guard in the current Dev `Loader.lua`. The common Git
blob identities are:

| Engine file | Git blob |
| --- | --- |
| `src/mods/AssetTransform.lua` | `f6612b4eed826d8193345541720669b9ba1a5f6d` |
| `src/mods/Sandbox.lua` | `81e25be72babaaa16aa4203ef98da92d3331eaa7` |
| `src/render/Assets.lua` | `afcc577b3a8f1882fe1f84eb8ab6b480b48cf500` |
| Stable and baseline `src/mods/Loader.lua` | `ddfc3f1239bbd7a5c4b2e60494817e3496127705` |
| Current Dev `src/mods/Loader.lua` | `84b087cd2dfb170ee3cf0320cb400a8dd82414f5` |

## Why the current surfaces do not qualify

`AssetTransform.runFor` gives the one-time recipe a restricted `ctx`. The
recipe can read the player's generated images and write under the calling
mod's derived root. This `ctx` does not exist in the normal mod runtime.

The runtime `mod.assets` facade has `path`, `image`, `list`, and `info`. Each
method joins the request to the packaged mod directory. It cannot address the
derived root.

`src/render/Assets.resolve` is an engine-private resolver. It searches enabled
mods in override order and can return another mod's derived output for a shared
generated-asset name. Requiring that module would depend on engine internals.
It would also remove the caller-owned isolation that this feature needs.

Direct use of `save/mod-derived`, `assets/generated`, `love.filesystem`, or a
host-specific material name is not an alternative. These choices expose or
guess private storage, bypass the public facade, or do not return an image
handle.

## Proposed Gen1recomp API

Add one owner-scoped method to the existing facade:

```lua
local image, reason = mod.assets:derivedImage("birds/pidgey_a.png")
```

Required behavior:

1. The engine binds the request to the calling facade's mod ID. The caller
   cannot supply or change an owner ID.
2. `relative` uses the existing `SafePath` rules. It must reject an empty path,
   `..`, absolute paths, drive paths, backslashes, and control characters.
3. The engine reads only the current output of that mod's declared
   `assets_transforms` recipe. It must not search override order, packaged
   assets, the generated ROM cache, `mod.cache`, or another mod's derived root.
4. The method returns an opaque, engine-owned image handle. It never returns a
   path, byte string, filesystem object, or mutable loader object.
5. A valid missing image returns `nil, "not_found"`. A recipe that is absent,
   failed, or not current returns `nil, "not_ready"`. A headless runtime returns
   `nil, "graphics_unavailable"`. A decode fault returns
   `nil, "decode_failed"` and is attributed to the calling mod.
6. Invalid paths fail in the same way as existing `mod.assets` path checks.
7. The returned image is borrowed. A mod must not call `release` on it. The
   engine keeps it valid while that mod is loaded and releases it after all mod
   callbacks stop.
8. The cache key includes the mod ID, the current transform stamp, and the
   relative path. A transform rerun, disable, reload, or failed current recipe
   invalidates the old handle before new callbacks can use it.
9. A failed current recipe must not make stale output from an older stamp
   available. The engine can preserve files for recovery, but the public method
   must fail closed until the current stamp succeeds.
10. The method is additive. Existing `mod.assets:image`, global generated-asset
    overrides, no-mod runs, and API 1 mods keep their current behavior.

Do not implement this method as a public wrapper around
`src/render/Assets.resolve`. That resolver has global override semantics. The
new method needs an owner-scoped lookup from the mod facade.

## Required upstream tests

An upstream change is ready only when ROM-free tests prove all of these cases:

- one mod can receive its own current derived image after a successful recipe;
- a second mod cannot receive the first mod's output, including the same
  relative name;
- traversal, absolute, drive, backslash, empty, and control-character paths
  fail;
- absent, failed, outdated, and decode-failed outputs return the specified
  fail-closed result;
- a stale file from an older transform stamp is never returned;
- no call returns a host path, cache path, bytes, or filesystem handle;
- headless use is safe;
- cache invalidation and image release happen exactly once on rerun, disable,
  reload, and shutdown; and
- existing public-mod API, global asset override, no-mod parity, Modkit, and
  engine suites still pass.

The public modding guide must document the method, ownership, result codes,
call timing, and the ban on `release`.

## KFP contract after an official release

KFP can implement wildlife only after an exact released engine commit exposes
and documents the method above, or an equivalent owner-scoped public method.
KFP must then follow this contract:

- Feature-detect the public method. Do not use an engine version string as the
  only gate.
- Keep both option rows hidden when the method is absent.
- Ask only for the fixed `birds/<species>_a.png` and
  `birds/<species>_b.png` names that `transform_birds.lua` owns.
- Wrap each call so a missing image, result error, thrown error, or invalid
  non-opaque result omits that species. Do not emit a path string in a packet.
- Treat each returned image as borrowed and read-only. KFP and a voxel host
  must not release it.
- Emit a bird packet only when frame A exists. Frame B can fall back to frame A.
- Build ground flocks from available common-species frames. Reset their
  deterministic placement from the copied map key only.
- Omit only the affected wildlife family when resolution fails. Keep aircraft,
  insects, the voxel host, and the rest of KFP active.
- Rate-limit diagnostics and do not include host, ROM, cache, save, or private
  paths.

## KFP test gate

The current pin matrix must continue to pass these existing tests:

- `tests/assets/test_transform_birds.lua` proves local derivation and invalid
  source rejection;
- `tests/features/test_dynamic_features.lua` proves that birds and ground
  flocks emit no packet without a public resolver; and
- `tests/config/test_config.lua` proves that unavailable alpha options stay
  hidden.

The future KFP implementation must add injected, ROM-free tests for method
absence, method faults, partial species, frame-B fallback, borrowed lifetime,
option visibility, deterministic map resets, bounded counts, draw schema v1,
and the absence of path strings. Both host companion suites and the full
four-target engine matrix must then pass before device or GPU review starts.
