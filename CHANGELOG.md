# Changelog

## 2.0.0-alpha.1 (unreleased)

- Replaced the host-file patcher with Voxel Companion API v1.
- Removed all host file reads, writes, backups, ledgers, and unpatch logic.
- Added a no-permission API 2 sandbox entry and constructor-injected modules.
- Added immutable option migration, including separate Contact and Object
  Shadows and corrected quality tiers. Ledge Leap preferences migrate, but the
  alpha forces execution off until an atomic public engine API exists.
- Added normalized world snapshots, incremental scene compilation, atomic
  packets, deterministic batching, bounded diagnostics, LRU, scheduling, and
  exactly-once resource ownership.
- Added host-neutral feature intent for static and dynamic 1.60 systems.
- Added ROM-free core, companion, render, feature, config, and gameplay tests.
- Added whole-snapshot resource and work budgets, a frozen 23-command host
  fixture, and local source-tested adapters for Battle Art and Dramaless Shape.
- Added a fail-closed machine-readable stable-release ledger and signed-tag
  packaging gate.
- Added separate signed alpha, beta, and release-candidate gate policies without
  weakening stable-release requirements.
- Published source pull requests for the Battle Art and Dramaless companion
  adapters; host-owner review, GPU testing, versioning, and release remain open.
- Moved legacy art and audio under a separate rights notice.
- Recorded a private creator-signed modification and redistribution grant for
  the current legacy-asset inventory; Git contains only its redacted hash.

This alpha is not a stable release. Certified adapters, real rendering,
device evidence, remaining channel gates, and reproducible artifacts remain
open. The asset-rights gate is complete for the current inventory.

Earlier release history remains available in the preserved Git history.
