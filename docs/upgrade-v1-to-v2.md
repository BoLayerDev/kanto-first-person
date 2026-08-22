# Safe Upgrade from KFP 1.x

KFP 1.x changed voxel-host source files. Some old cleanup paths could also
remove host files. KFP 2 does not patch, repair, restore, or delete a host
file.

> **Release status:** The ROM-free migration tests pass. The release gate is
> still open until the exact release candidate passes the installed-host and
> uninstall checks in this document.

## Important rule

Do not remove KFP 1.x and then start Gen1recomp with an old patched host. A
clean host reinstall must happen before the next start.

## Before the upgrade

Prepare these items while Gen1recomp is closed:

- a record of the enabled mods and the selected voxel host;
- a record or screenshots of the KFP option values;
- a clean host package from an owner-published release; and
- the KFP 2 package and its published SHA-256 hash.

Use one supported host only: Battle Art or Dramaless. Do not copy files from
the old host folder into the clean host folder.

## Required upgrade sequence

1. Close Gen1recomp completely.
2. Record the enabled mods, host version, and KFP option values.
3. Replace the selected voxel host with its verified clean release.
4. Verify the clean host package against the host owner's hash or release
   record. Do not manually remove suspected splice code.
5. Replace the complete KFP 1.x directory with the complete KFP 2 directory.
6. Confirm that exactly one supported voxel host is enabled.
7. Start Gen1recomp.
8. Check the KFP diagnostic. It must name the expected host and API v1, and it
   must not report legacy splice markers.
9. Check the migrated option values before normal play.

If a host adapter reports a legacy marker, close Gen1recomp and reinstall the
host again from a verified clean package. Do not ask KFP to repair the host.
Do not keep starting the marked host.

## Option migration

| KFP 1.x data | KFP 2 result |
| --- | --- |
| `shadows` | Contact Shadows |
| old Object Shadows row | Corrected v2 default |
| `fastchunks=false` | Low quality |
| `fastchunks=true` or missing | Auto quality |
| `REMOVE PATCH` / `remove` | Ignored; no file action |
| array-shaped Vine data | Last valid Vine value |
| `jumpkey`, `jumppad` | Preserved as preferences |
| Ledge Leap | Forced off in the alpha |

KFP stores the normalized result only in its own `config/v2` save area. It
does not delete legacy option data. See [KFP 1.x Option
Migration](options-migration.md) for the complete map.

## Disable or remove KFP 2

1. Close Gen1recomp.
2. Keep a record of the KFP 2 option values if you may reinstall it.
3. Disable KFP in the mod manager, or remove only the KFP 2 package.
4. Start Gen1recomp and confirm that the voxel host starts without KFP output.

On a normal quit, KFP detaches its companion registration, removes its event
and hook subscriptions, and releases its own scene, image, and audio
resources. On the next disabled or removed boot, the Gen1recomp Loader does
not run the KFP entry file.

KFP does not change the host during install, run, disable, or removal. It also
does not remove its saved option record. Do not depend on that record as the
only backup because engine storage policy can change.

If the host was ever used with KFP 1.x, reinstall the clean host before you
start the game without KFP. Removing KFP 2 cannot repair an old v1 patch.

## Rollback

The supported rollback target is a verified KFP 2 package that uses the same
companion contract. The KFP 1 patcher is retired and is not a supported
rollback target.

1. Close Gen1recomp.
2. Reinstall the verified clean host release.
3. Replace only the KFP directory with the earlier verified KFP 2 package.
4. Start Gen1recomp and check the host, API, integrity, and option diagnostic.

If no compatible KFP 2 package is available, leave KFP disabled. The clean
host can run without it.

## What the public tests prove

`tests/integration/test_migration_safety.lua` runs the real KFP `main.lua`,
module loader, configuration migration, companion client, and Voxel Companion
API v1 dispatcher. `tools/test_engine_migration.lua` also runs the exact KFP
manifest and runtime through the real Gen1recomp Loader. CI runs that check on
all five pinned engine commits. Both tests use invented, ROM-free host source
strings.

The test proves these KFP-owned facts:

- the manifest ID stays `ds_fp_ceiling` and permissions stay empty;
- KFP uses the Loader's public `mod.find` handle without host-file access;
- a clean synthetic host can register, start, detach, and re-register;
- a synthetic adapter refuses known legacy marker strings before registration;
- KFP also faults closed if integrity reports markers after registration;
- KFP reads only its own packaged Lua modules;
- option migration writes only the KFP-owned `config/v2` record;
- `remove` causes no delete action;
- legacy options and synthetic host files stay unchanged; and
- quit removes KFP registrations, subscriptions, and owned resources;
- a disabled KFP package is discovered but its entry does not run; and
- a removed KFP package is not discovered and no KFP state is created.

These tests do not prove an owner host release, its real marker scanner, an
installed filesystem, or a live engine shutdown. The headless real-Loader
check cannot replace the final release-candidate test in a clean profile.

## Evidence still required for the release gate

Run the following checks with the exact release-candidate package and each
owner-published compatible host:

- record the engine, host, KFP commit, package hash, and device;
- hash the host tree before install, after run, after disable, after KFP
  update, and after KFP removal;
- confirm that all host hashes are identical;
- confirm that a read-only legacy-marker fixture is refused with the correct
  reinstall message;
- confirm option values after upgrade, disable, re-enable, and rollback;
- confirm a clean quit and a new disabled or removed boot; and
- record the diagnostic and test result without ROM data or private paths.

The migration-safety release gate must remain false until this evidence is
accepted for both released hosts.
