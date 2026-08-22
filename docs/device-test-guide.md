# KFP 2.0 Device-Owner Test Guide

This guide collects ROM-safe evidence from real devices. It does not permit a
public support claim by itself. The release coordinator validates each record,
matches it to private evidence by SHA-256, and applies the release gates.

## Supported platform classes

Use one exact `platform_class` value from the evidence schema:

| Platform class | Native evidence target |
|---|---|
| `windows` | Windows x86-64 |
| `linux_x86_64` | Linux x86-64 |
| `linux_arm64` | Linux ARM64 |
| `macos_x86_64` | macOS on Intel |
| `macos_arm64` | macOS on Apple silicon |
| `android` | Android |
| `ios_love12` | iOS with LÖVE 12 |
| `xbox_uwp` | Xbox UWP Dev Mode |
| `nintendo_switch` | Nintendo Switch |
| `portmaster` | PortMaster-class SBC hardware |
| `anbernic_stock` | Anbernic stock-OS class hardware |

Emulation, virtual machines, compatibility layers, and remote rendering do not
count as native platform evidence. Record them as `experimental` and describe
the deviation with public-safe text.

## Privacy and ROM-safety rules

Keep raw evidence under the private evidence root given by the release
coordinator. Never add it to Git or a release package.

Do not submit:

- ROMs, saves, extracted cache files, ROM-derived images, or raw screenshots;
- local paths, user names, email addresses, serial numbers, IP addresses, URLs,
  account IDs, device IDs, or permission conversations;
- crash dumps or logs before a person removes private data;
- free-form text copied from the game or another copyrighted source.

The public JSON record contains short neutral labels and SHA-256 digests only.
Use a pseudonymous tester alias. Do not use a legal name, account name, or email
address. Evidence file names and storage locations are not part of the record.

Before hashing a text report, remove paths, user names, host names, network
addresses, tokens, and game-derived text. Hash the final immutable file:

```text
certutil -hashfile <file> SHA256
sha256sum <file>
```

Do not edit the file after its digest is recorded. A changed file is new
evidence and needs a new digest.

## Fixed test setup

Use an official Gen1recomp build and one compatible voxel host. Test Battle Art
and Dramaless in separate runs and separate records. Never enable both hosts in
a normal pass run; the multiple-host case is a separate negative test.

Record immutable Git commits and package SHA-256 values for KFP, the host, and
Gen1recomp. A branch name, pull-request number, or mutable download URL is not
an immutable identity.

Use the same power mode, thermal state, driver, quality tier, fixed clock,
feature seed, and option snapshot for paired measurements. Close overlays and
unrelated workloads. Run performance tests with one Gen1recomp instance.

Resolution policy:

- Windows reference evidence uses 1920 x 1080 and
  `resolution_mode: "reference_1080p"`.
- Other devices use their normal native rendering resolution and
  `resolution_mode: "native"`.
- A device that can render 1920 x 1080 may also submit a separate reference
  run. Do not scale a native result and label it as a 1080p result.
- Record both the physical native resolution and the actual test resolution.

Use legally owned Red, Blue, and Yellow imports. Public records name the game
edition only. Map IDs, coordinates, screenshots, and saves remain private.
ROM-free synthetic testing is useful, but it cannot replace all three games for
a `pass` classification.

## Required run

### Functional and visual

Follow `docs/qa-matrix.md` with first-person coverage for interiors, caves,
forests, cities, routes, shores, weather, sky, battles, and UI. Sample third
person and tilt/diorama. Exercise keyboard, gamepad, or touch as applicable.

Also test no host, one host, two hosts, incompatible API major, legacy marker,
injected callback faults, map entry, warp, reload, option changes, resize,
suspend, resume, disable, hot reload, and shutdown. The host must continue after
a KFP fault and graphics state must be restored.

A human must review visual output. Keep screenshots private and record the
digest of the redacted review report in `evidence`.

### Performance

Follow `docs/benchmark-method.md` exactly:

1. Warm caches.
2. Alternate five 60-second host-only and host-plus-KFP samples.
3. Report median, p95, and p99 in the private report.
4. Record the schema's bounded p95 and maximum values.
5. Measure an uncached scene entry.

Desktop High must meet the 2.0 ms KFP CPU p95 gate. The lowest certified Low
device must meet 3.0 ms. Frame-time regression must not exceed 15% p95 when the
host meets its target. Scene readiness must be at most 250 ms on desktop and
750 ms on the lowest certified device. Build slices and draw submissions must
meet the selected quality policy.

### Leak and uninstall integrity

Alternate two stress maps 100 times. Then run a 30-minute soak that includes a
map, battle, menu, suspend, and resume. After collection, Lua heap must be
within 5% of warm steady state. Mesh, image, canvas, shader, and audio-source
counts must not grow after warmup.

Hash the clean host and KFP test trees before and after install, run, disable,
update, and removal. They must remain byte-identical. The test must perform no
automatic repair or deletion of another mod.

## Result classification

Use `pass` only when all of these conditions are true:

- testing ran on native hardware with released KFP, host, and Gen1recomp
  packages identified by immutable hashes;
- Red, Blue, and Yellow are all covered;
- every functional, visual, performance, leak, and uninstall check passes;
- the required sample counts, 100 transitions, and 30-minute soak complete;
- private evidence exists and its digest matches the public record;
- all privacy, ownership, and no-ROM attestations are true.

Use `experimental` when evidence is useful but incomplete, uses an unreleased
host branch, uses non-native execution, omits a game, or misses a required
check. No completed check may have failed. Experimental evidence cannot satisfy
a stable platform gate.

Use `fail` when a required completed check fails. Add a short public-safe
`failure_summary`; put technical details in private evidence.

One platform class becomes eligible for a stable support claim only after the
release coordinator has current `pass` records for both released hosts. A
record for one host does not certify the other host.

## Submission and validation

1. Copy `docs/release-evidence/device-result.schema.json` to a new working
   directory outside the repository.
2. Create one JSON result per device, host, and run.
3. Validate it with a JSON Schema Draft 2020-12 validator.
4. Run `python -m unittest tests.tools.test_device_evidence -v` in the KFP
   source tree.
5. Send the JSON record and private evidence through the release coordinator's
   approved private route. Do not open a public issue with raw evidence.

The release coordinator rejects records with unknown fields, missing hashes,
unbounded text, private paths, or inconsistent classification.
