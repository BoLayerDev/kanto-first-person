# Architecture Decisions

## D001 — Clean rewrite

Decision: preserve behavior and history, but do not reuse the legacy patcher or proof implementation.

Reason: both depend on unsafe cross-mod mutation and private runtime state.

## D002 — Host-owned world pipeline

Decision: each voxel host keeps the single Gen1recomp `drawWorld` pipeline. KFP registers through Voxel Companion API v1.

Reason: current Gen1recomp selects one world pipeline. A second KFP pipeline would compete with the host.

## D003 — Same mod identity

Decision: keep `ds_fp_ceiling` and migrate options in place.

Consequence: the manifest uses `affects_link: true` because Ledge Leap can change movement.

## D004 — Permission-free runtime

Decision: KFP 2.0 requests no filesystem, engine-internal, background, compute, or network permission.

Reason: bounded incremental main-thread work is portable and avoids uncancellable worker risk.

## D005 — Corrected parity

Decision: stable requires all intended 1.60 features, but dangerous operations, duplicate settings, broken rendering, leaks, and incorrect gameplay are corrected or retired.

## D006 — Rights split

Decision: new v2 source is MIT. Legacy assets stay under the creator grant and outside the MIT grant.

## D007 — Stable host gate

Decision: Dramatic Shape, Battle Art, and Dramaless Shape must all pass the same API contract before `2.0.0` stable.
