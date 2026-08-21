# Benchmark Method

## Measures

Record KFP update CPU time, build CPU time, render submission CPU time, added draw calls, Lua heap after collection, owned GPU/audio resource counts, cache cost, scene readiness, and frame time with and without KFP.

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

## Pass conditions

- Desktop High KFP CPU is at most 2.0 ms p95.
- Lowest certified Low device KFP CPU is at most 3.0 ms p95.
- Frame-time regression is at most 15% p95 when the host meets its own target.
- A build slice exceeds its policy by no more than 0.25 ms, excluding recorded driver calls.
- Complete uncached scene readiness is at most 250 ms on desktop and 750 ms on the lowest certified device.
- Resource counts stop growing after warmup.
- Post-collection Lua heap remains within 5% of warm steady state.

Do not compare results from different engine, host, driver, thermal, power, or resolution states as if they are equivalent.
