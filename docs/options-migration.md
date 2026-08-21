# KFP 1.x Option Migration

## Result

KFP 2 reads old choices once and creates one plain, read-only configuration
snapshot. It does not patch, restore, or delete any voxel-host file.

The public runtime API is:

```lua
local config = Config.new({
  read = readOption,
  storage = migrationStorage, -- optional, but recommended for upgrades
  diagnostics = diagnostics,
})

local snapshot = config:snapshot()
local nextSnapshot, invalidated = config:refresh("option_changed:rain")
```

Source modules do not call an engine module. The composition root injects all
engine adapters.

## Rules that need special handling

| KFP 1.x data | KFP 2 result | Reason |
| --- | --- | --- |
| `shadows` | `contact_shadows` | KFP 1.60 used `shadows` for two rows. The stored value cannot identify the changed row. |
| old Object Shadows row | `object_shadows=true` | Object Shadows use their corrected v2 default. The ambiguous `shadows` value never changes them. |
| `fastchunks=false` | `quality=LOW` | This keeps the user's request for lower foreground build pressure. |
| `fastchunks=true` | `quality=AUTO` | AUTO uses the host tier and platform policy. |
| missing `fastchunks` | `quality=AUTO` | AUTO is the safe new-install default. |
| array-shaped `vines` data | one `vines` row | Defensive normalization keeps the last valid value. The published 1.60 archive has one Vine row; this is not a confirmed release collision. |
| `remove` | ignored | KFP 2 has no patch, unpatcher, ledger, or host-file delete path. |
| `jumpkey`, `jumppad` | preserved as bindings | A binding is a preference. It does not grant movement authority. |
| any KFP 1.x upgrade | `ledge_leap=false` | Ledge Leap changes gameplay. Alpha builds force it off because no atomic public engine attempt API exists. |

An explicit v2 value wins when the injected reader returns `value, true`.
The second result means that the value is persisted, not an automatic row
default.

Gen1recomp's public `mod.options:get()` returns one value. The KFP bootstrap
therefore records which canonical and legacy keys exist before it defines the
v2 rows. It supplies that recorded presence as the second result and marks a
key present when `mod.options_changed` names it. This keeps a stored v2 value
ahead of legacy data without mistaking a new row's automatic default for a
user choice.

## Complete option map

The row key stays unchanged when it is safe. Feature code receives the clear
snapshot field shown below.

| KFP 1.x key | KFP 2 row key | Snapshot field |
| --- | --- | --- |
| none | `quality` | `quality`, `quality_policy` |
| `ceiling` | `ceiling` | `ceiling` |
| `headroom` | `headroom` | `headroom`, `headroom_pixels` |
| `cutaway` | `cutaway` | `cutaway` |
| `third` | `third` | `third_person_ceiling` |
| `shadows` | `contact_shadows` | `contact_shadows` |
| none | `object_shadows` | `object_shadows` |
| `rails` | `rails` | `rails` |
| `spill` | `spill` | `doorway_light` |
| `fittings` | `fittings` | `ceiling_lamps` |
| `ceildetail` | `ceildetail` | `ceiling_detail` |
| `windows` | `windows` | `windows` |
| `rock` | `rock` | `cave_rock` |
| `pools` | `pools` | `cave_pools` |
| `sconces` | `sconces` | `cave_torches` |
| `bats` | `bats` | `bats` |
| `apron` | `apron` | `world_apron` |
| `talltrees` | `talltrees` | `tall_trees` |
| `peaks` | `peaks` | `mountain_peaks` |
| `bouldertrees` | `bouldertrees` | `boulder_trees` |
| `headbob` | `headbob` | `head_bob` |
| `backdrop` | `backdrop` | `horizon` |
| `horizonart` | `horizonart` | `horizon_art` |
| `clouds` | `clouds` | `clouds` |
| `stars` | `stars` | `night_sky` |
| `birds` | `birds` | `birds` |
| `groundflock` | `groundflock` | `ground_flock` |
| `aircraft` | `aircraft` | `aircraft` |
| `rainbows` | `rainbows` | `rainbows` |
| `rain` | `rain` | `rain` |
| `lightning` | `lightning` | `lightning` |
| `umbrellas` | `umbrellas` | `npc_umbrellas` |
| `puddles` | `puddles` | `puddles` |
| `lights` | `lights` | `lamplight` |
| `fog` | `fog` | `lavender_fog` |
| `canopy` | `canopy` | `forest_canopy` |
| `vines` | `vines` | `hanging_vines` |
| `shafts` | `shafts` | `sun_shafts` |
| `grass` | `grass` | `grass_height` |
| `wind` | `wind` | `wind` |
| `insects` | `insects` | `insects` |
| `particles` | `particles` | `particles` |
| `ambience` | `ambience` | `ambient_sound` |
| `grasssfx` | `grasssfx` | `grass_steps` |
| `stepsfx` | `stepsfx` | `footsteps` |
| `doorsfx` | `doorsfx` | `door_sound` |
| `fpfov` | `fpfov` | `first_person_fov` |
| `dof` | `dof` | `depth_blur`, `depth_blur_passes` |
| `jump` | `jump` | `jump_feel` |
| `doorstep` | `doorstep` | `doorway_step` |
| none | `ledge_leap` | `ledge_leap` |
| `jumpkey` | `jumpkey` | `ledge_key` |
| `jumppad` | `jumppad` | `ledge_pad` |
| `debug` | `debug` | `debug_hud` |

`snapshot.values` is a stable compatibility view for feature modules. In that
view, `shadows` means Contact Shadows only. Object Shadows always use
`object_shadows`.

## Retired data

These keys never enter the v2 snapshot:

- `remove`, `ceilingpatch`, and `ceiling_patch`;
- `dark` (Cave Darkness);
- `backs` (Building Backs);
- `mountains` (the old unauthored cluster-depth attempt);
- `windowlight` and `window_light`; and
- `sunbloom`, `sun_bloom`, and `bloom`.

KFP reports a bounded informational diagnostic when it sees one of these keys.
It does not delete the stored value.

## Quality policy

Only four user values are valid: `AUTO`, `HIGH`, `BALANCED`, and `LOW`.
`AUTO` resolves to one hard policy through the render quality service.

| Policy | Build slice | Cache limit | Density | Draw-call target | Panorama width |
| --- | ---: | ---: | ---: | ---: | ---: |
| HIGH | 2.0 ms | 128 MiB | 1.0 | 48 | 4096 |
| BALANCED | 1.0 ms | 64 MiB | 0.6 | 32 | 2048 |
| LOW | 0.5 ms | 32 MiB | 0.3 | 20 | 1024 |

`MEDIUM` normalizes to `BALANCED`. An unknown value fails to `AUTO`.

## Snapshot and invalidation contract

- `snapshot()` performs the first read, then returns the same snapshot until a
  value changes.
- `refresh(reason)` reads each key at most once.
- A no-change refresh keeps the global generation and object identity.
- A change creates a new snapshot and increments `generation` once.
- `group_generation` changes only for affected groups.
- `refresh` also returns the invalidated groups for immediate dispatch.
- Old snapshots stay unchanged after refresh.

Groups are `quality`, `geometry`, `lighting`, `sky`, `weather`, `flora`,
`particles`, `audio`, `camera`, `gameplay`, `streaming`, and `diagnostics`.

Consumers must treat snapshots and their nested tables as read-only plain data.

Alpha builds hide controls that do not yet have an executable and verified
runtime: third-person ceiling mode, ceiling detail, birds, ground flock,
lamplight, Debug HUD, and Ledge Leap. Their keys remain in the schema so
migration data is not lost. Ledge Leap alone is also forced to `false`.

## Persistent migration record

The optional storage adapter has this small interface:

```lua
storage:read("config/v2")
storage:write("config/v2", record)
```

The record keeps normalized values and their source. This resolves the
ambiguous v1 shadow key and makes defensive normalization stable on later
boots. KFP writes one record only when data changes. It never deletes a key.

For an intentional reset to a row default, call:

```lua
config:refresh("option_changed:<row-key>")
```

This reason makes the new row value authoritative, even when it equals the
automatic default.
