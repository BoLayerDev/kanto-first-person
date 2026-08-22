# Kanto First Person 2.0 Architecture

## Purpose

KFP adds environment, atmosphere, camera, and audio behavior to a voxel host.
The repository also contains a dormant, corrected Ledge Leap policy. It is a
companion, not a source patcher and not a second world renderer.

## Runtime flow

```text
Gen1recomp selects one host render pipeline
  -> host normalizes its live state
  -> host dispatches Voxel Companion API callbacks
  -> KFP copies one immutable world/config view
  -> incremental feature compilers create an owned scene packet
  -> render graph submits owned batches through the borrowed host draw facade
  -> host draws field effects and returns its world canvas
```

## Boundaries

### Engine boundary

Only the voxel host reads Gen1recomp `ctx.state`. Host adapters normalize it
into the companion contract. KFP uses official mod events, options, storage,
and assets. Alpha does not hook input or queue gameplay movement.

### Host boundary

The host exports `voxel_companion` API major 1. KFP finds known active host IDs,
then checks the exported API and capabilities. It rejects a descriptor whose
host ID does not match the selected mod, whose capability version is not the
number `1`, or whose capability name is outside the eight-name API v1 set. KFP
copies the validated host descriptor and capability map before registration. A
host ID never proves compatibility by itself.

### Feature boundary

Each feature receives injected services and immutable input. It returns update
state, render batches, audio intents, or camera deltas. It does not call
another feature directly.

### Resource boundary

Every owned resource enters one `ResourceOwner`. Release is idempotent. Borrowed host resources never enter that owner and KFP never releases them.

## Normalized world model

A world snapshot has a stable map ID and revision, game ID, dimensions, palette and tileset revisions, mode, player and actor poses, current and neighboring terrain views, map tags, time, and weather inputs.

Terrain cells provide stable coordinates, height, material reference, collision and walkability flags, semantic tags, and optional source metadata. Host adapters may retain native lookup tables, but KFP cannot see them.

Snapshots are valid beyond a callback only after the adapter copies them to
plain KFP-owned data. Capture enforces whole-snapshot limits of 65,536 cells,
65,536 tags, 8 MiB of structural text, 2 MiB and 32,768 items of metadata,
262,144 copied nodes, and 1,048,576 bounded work items. Lower injected limits
support stress tests. Oversized input fails before scene compilation.

## Scene compiler

The compiler uses a generation token. A map, palette, host, view, option, or quality change increments the relevant generation. Stale work stops before commit. Work runs only in update callbacks and stays inside a tier budget. Packet sorting, declarative content hashing, cache-key assignment, packet validation, cost accounting, and commit are compiler stages. Render callbacks do not do this work. Each compiler step reserves up to 0.025 ms of its tier budget for clock, loop-exit, coroutine, and garbage-collection tail overhead.

The compiler creates a new scene packet away from the active packet. It swaps the new packet only after all critical systems finish. Optional systems can attach later through versioned packet layers. Retired packets release through the resource owner after the frame boundary.

The injected `newBuffer(quality)` factory must return a buffer with `beginSeal(metadata)`. That method returns a job with `step(units) -> done, packet`. These two methods are the incremental sealing surface. The compiler rejects a buffer that does not provide `beginSeal` before it opens an asset scope. It does not call a synchronous `seal` fallback because that can exceed the frame budget. A rejection leaves the current KFP packet active. If no KFP packet exists, the host renderer continues without KFP geometry.

## Render graph

The fixed phase order is:

1. Camera delta.
2. Background.
3. Host terrain and neighbors.
4. KFP opaque geometry.
5. Host actors and water.
6. KFP translucent geometry and effects.
7. Host field effects.
8. Separate host shadow-caster pass when supported.
9. Separate host battle-opaque pass when supported.

Commands are sorted by explicit phase, material, shader, depth, blend, and stable batch key. They never depend on Lua table iteration order.

The portable command set is exactly `mesh`, `instances`, and `billboards`.
Command-buffer writes reject all other kinds. The renderer also refuses a
crafted packet with another kind and never calls an undeclared draw method.

## Failure model

- Entry failure rolls back mod-owned registrations through Gen1recomp.
- Host discovery failure keeps KFP inactive.
- Missing standard optional capabilities disable only affected systems.
- A feature error opens that feature's circuit breaker and records one diagnostic.
- A companion callback error disables KFP for the session, not the host.
- A draw failure restores host graphics state.
- A corrupt snapshot fails closed before compilation.
- Ledge Leap remains unavailable until one public engine operation can validate
  and own the movement atomically at input time.

## Performance invariants

- No render-time file or full-map work.
- No unbounded list, cache, queue, diagnostic, pool, or retry.
- No global random state.
- No more than one active and one building scene packet per view.
- No resource without an owner.
- No quality setting can exceed its CPU, memory, density, or draw-call policy.
