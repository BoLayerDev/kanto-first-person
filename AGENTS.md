# Kanto First Person 2.0 Project Rules

## Identity

- Canonical local path: `C:\Users\bolay\Documents\Kanto First Person`.
- Canonical public remote: `BoLayerDev/kanto-first-person`.
- Active development branch: `v2-rewrite`.
- Mission: implement a sandbox-safe Kanto First Person rewrite for current
  Gen1recomp with Battle Art and Dramaless host support.
- Initial game scope: Red, Blue, and Yellow only.

## Non-negotiable boundaries

- Never inspect, write, copy, patch, restore, or delete another installed mod at runtime.
- Never recreate the legacy patcher, backup ledger, shadow copy, or unpatcher.
- Never use `_G`, raw `io`, raw `love.filesystem`, `dofile`, `loadfile`, or engine-private `require` paths.
- Never package ROMs, saves, extracted cache files, ROM-derived images, credentials, or private permission evidence.
- Keep `C:\Users\bolay\Documents\Kanto First Person Evidence`,
  `private-fixtures/`, `baseroms/`, and `roms/` outside release packages.
- Do not edit any existing Gen1recomp or voxel-host workspace. Use isolated task-owned clones.
- Do not delete or rewrite the legacy Git history. It is the recovery source.
- Do not publish a public release until rights, host, platform, reproducibility, and parity gates pass.
- Do not restart or stop applications, services, or user-owned processes without current-turn approval.
- Do not write into OneDrive.

## Folder map

- `main.lua`: small sandbox entry and composition root.
- `src/core/`: lifecycle, module loading, diagnostics, scheduling, caching, and host selection.
- `src/config/`: immutable options and migration.
- `src/companion/`: KFP-side companion client and normalized views.
- `src/features/`: isolated visual and audio feature systems.
- `src/render/`: scene compiler, render graph, batches, and resource lifetime.
- `src/gameplay/`: optional Ledge Leap policy and adapter.
- `companion/`: host-neutral Voxel Companion API reference implementation.
- `assets/`: authorized packaged assets. Legacy assets remain outside the MIT grant.
- `tests/`: ROM-free unit, contract, integration, and fixture tests.
- `tools/`: test, validation, benchmark, and package commands.
- `docs/`: architecture, compatibility, provenance, migration, parity, and coordination records.
- `website/`: isolated React Three Fiber showcase, field guides, and support
  interface. It is not part of the mod package.
- `C:\Users\bolay\Documents\Kanto First Person Evidence`: private rights,
  legacy-release, runtime, device, and test-artifact evidence outside this mod root.

## Required commands

- Run all tests: `luajit tools/run_tests.lua`.
- Syntax check: `luajit tools/check_syntax.lua`.
- Validate repository policy: `luajit tools/validate_project.lua`.
- Run benchmarks: `luajit tools/run_benchmarks.lua`.
- Run the controlled authored-corpus and full-scene stress benchmark:
  `luajit tools/run_full_scene_benchmark.lua`.
- Install website dependencies: `npm ci --prefix website`.
- Type-check and build the website: `npm run build --prefix website`.
- Run Gen1recomp mod validation: `python <gen1recomp>/tools/modkit.py validate .`.
- Build a private test package: `python tools/package_release.py --engine <gen1recomp> --output-dir <outside-project-dir> --epoch <unix-time> --allow-dirty`.

If LuaJIT is not on `PATH`, use the pinned runtime recorded in `PROJECT_STATUS.md`. Do not install a new runtime without checking existing tools first.

## Engineering rules

- Lua code must support LuaJIT and Lua 5.1 semantics.
- Use constructors and injected services. Do not use shared mutable module state.
- Keep host objects borrowed and read-only. Copy only the plain data needed after a callback.
- All created GPU and audio resources need one explicit owner and idempotent release.
- Render callbacks must not read files, decode assets, compile shaders, scan full maps, or build complete meshes.
- Use deterministic local random generators. Never call `math.randomseed`.
- Use bounded caches, bounded work queues, bounded diagnostics, and fixed-capacity effect pools.
- A feature fault must not stop the voxel host or another KFP feature.
- Add a test for every fixed defect and every public interface change.
- Do not approve a golden-image update in the same change that changes the renderer without independent review.
- Keep the website static and compatible with the `/kanto-first-person/`
  GitHub Pages base path. Do not copy ROM-derived or private evidence into it.
- Keep essential website actions in semantic HTML. Provide reduced-motion and
  non-WebGL fallbacks for the 3D experience.

## Git and publication

- Commit only focused, tested changes to `v2-rewrite` or a feature branch.
- Direct development pushes to `main` are forbidden.
- Preserve `upstream-original` as fetch-only.
- Run secret, ROM-content, license, syntax, unit, and package checks before any push intended for release.
- MIT covers independently authored v2 source only. See `THIRD_PARTY_NOTICES.md`.
- Use signed annotated tags and deterministic packages for releases.

## Model and worker policy

- One coordinator owns integration and release truth.
- Workers get exclusive paths. Do not edit another worker's files.
- Use GPT-5.6-Sol High for nonvisual work by default.
- Fable 5, when explicitly selected for a small visual task, always uses medium effort.
- Do not use above-medium Fable modes.
- Use Claude only through the noninteractive Claude Code CLI in this workspace, with Chrome integration disabled when practical.
- Preserve short handoffs in `docs/project-coordination/thread-map.md` and `PROJECT_STATUS.md`.

## Definition of done

Work is complete only when its tests pass, source and resource ownership are clear, documentation matches behavior, Git status is understood, and the relevant milestone gate in `ROADMAP.md` is satisfied. Source-only checks do not prove visual or device behavior.
