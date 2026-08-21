# Safe Upgrade from KFP 1.x

KFP 1.x edited voxel-host source. Some versions also installed unsafe orphan cleanup code. Do not remove KFP 1.x and then start an old patched host.

## Required sequence

1. Close Gen1recomp.
2. Save a copy of your enabled-mod list and option choices.
3. Reinstall your voxel host from its verified clean release.
4. Confirm that no old `payload_ceiling`, `payload_flora`, `payload_sky`, `payload_backdrop`, or `payload_jump` source is present in the host package.
5. Replace the KFP 1.x directory with KFP 2.x.
6. Start Gen1recomp.
7. Check KFP diagnostics for the selected host, API version, integrity state, and migrated options.

KFP 2.x never repairs or deletes host files. A host adapter that detects legacy splice markers refuses registration and asks for a clean reinstall.

## Option migration

- The old `shadows` value becomes Contact Shadows.
- Object Shadows use the corrected v2 default because v1 stored both shadow rows under one key.
- `fastchunks=false` selects Low quality.
- `fastchunks=true` or missing selects Auto quality.
- `REMOVE PATCH` is ignored.
- Array-shaped Vine state is normalized defensively. The published 1.60
  archive itself has one Vine row.
- Jump key and gamepad preferences remain available.
- Ledge Leap stays forced off in alpha builds. It needs an atomic public
  engine movement-attempt API before it can be enabled.
