# Benchmark Method

## Measures

Record KFP update CPU time, build CPU time, render submission CPU time, added draw calls, Lua heap after collection, owned GPU/audio resource counts, cache cost, scene readiness, and frame time with and without KFP.

`mod.exports.kfp.status().metrics` is a read-only, schema-versioned (`schema = 1`)
runtime snapshot. Timing values use milliseconds and retain only the latest 240
samples. Recording uses fixed-capacity arrays; it does not grow a per-frame log.

- `timing.update` measures dynamic feature updates, excluding scene compilation.
- `timing.build` measures each incremental compiler slice.
- `timing.render` measures KFP command submission to the borrowed host draw facade.
- `scene.readiness` measures request-to-packet readiness, including cache hits.
- `submissions` separates render callbacks from accepted draw commands.
- `runtime` reports bounded cache, resource, texture, and audio gauges when those
  subsystems are available.

These measurements use the injected LÖVE monotonic clock. They include Lua and
host-facade call time but do not isolate graphics-driver execution. Use an
external frame-time capture for the host-only comparison and frame regression.

## Tiers

| Tier | Build slice | Cache cap | Density | Added draw target |
|---|---:|---:|---:|---:|
| High | 2.0 ms | 128 MiB | 100% | 48 |
| Balanced | 1.0 ms | 64 MiB | 60% | 32 |
| Low | 0.5 ms | 32 MiB | 30% | 20 |

## Corpus

The public corpus uses synthetic ROM-free maps for indoor, cave, forest, city, route, shore, mountain, Lavender, rain, storm, day, night, battle, neighbor-atlas, and high-actor stress cases. The private corpus maps equivalent scenes from user-owned Red, Blue, and Yellow imports.

## Procedure

1. Pin engine, host, platform, resolution, quality, map, camera, seed, and options.
2. Warm the host and KFP caches.
3. Measure host-only for 60 seconds.
4. Measure host plus KFP for 60 seconds.
5. Repeat five times after alternating run order.
6. Report median, p95, and p99. Keep raw local results outside release packages.
7. Run an uncached map-entry test separately.
8. Run 100 alternating transitions and a 30-minute soak.

`tools/run_benchmarks.lua` is a ROM-free packet-seal stress check. The command
buffer is built before timing and the compiler has no feature tasks. It is not a
complete uncached-scene benchmark. Its 4,096-item synthetic corpus is the
High-tier workload. Balanced and Low apply their production 60% and 30% density
policies to that same ordered corpus. The report includes the exact item count
for each tier and uses one compiler update per simulated 60 Hz frame.

The default command uses `KFP_BENCHMARK_MODE=strict`. Run it only on a controlled
native reference system. Strict mode applies the unchanged build-slice limit
plus 0.25 ms and the 250 ms simulated packet-seal readiness limit to High,
Balanced, and Low.

The workflow explicitly sets `KFP_BENCHMARK_MODE=shared-ci`. This mode validates
packet shape, API conformance, tier workload, and incremental completion. It
reports monotonic wall-clock observations but does not treat them as performance
evidence because shared-runner descheduling can add unbounded wall time that KFP
did not consume. Deterministic slice and hash-parity tests remain mandatory in
the normal test suite. Shared-CI mode must never approve a performance gate.

Passing strict mode does not satisfy the complete uncached-scene gate. Record
that gate separately with the runtime corpus and the injected LÖVE monotonic
clock. Native 30 Hz Low-tier results are also separate device evidence. The
750 ms allowance applies only to the lowest certified native device.

## Pass conditions

- Desktop High KFP CPU is at most 2.0 ms p95.
- Lowest certified Low device KFP CPU is at most 3.0 ms p95.
- Frame-time regression is at most 15% p95 when the host meets its own target.
- Every observed build slice stays at or below its policy plus 0.25 ms,
  excluding recorded driver calls.
- Complete uncached scene readiness is at most 250 ms on desktop and 750 ms on the lowest certified device.
- Resource counts stop growing after warmup.
- Post-collection Lua heap remains within 5% of warm steady state.

Do not compare results from different engine, host, driver, thermal, power, or resolution states as if they are equivalent.

For live scene diagnosis, `mod.exports.kfp.status().scene` also reports the
active packet without exposing graphics resources:

- `activeKey`, `activeGeneration`, and `activeDrawCalls` identify the packet.
- `activeCommands.commands` and `batchItems` report bounded totals.
- `activeCommands.phases`, `kinds`, and `owners` report count-only maps.

These values are defensive copies. They contain no textures, meshes, host
objects, asset paths, or borrowed callback data.
