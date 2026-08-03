<img width="757" height="473" alt="kantohorizon2" src="https://github.com/user-attachments/assets/814dbfe2-55fd-4d54-8801-8cb697741cc7" />
# Kanto in First Person — Interiors and Tweaks
<img width="1708" height="647" alt="Screenshot 2026-08-03 200945" src="https://github.com/user-attachments/assets/a5dce2eb-893f-4158-af2d-32eb141026d5" />


A companion mod for the [Dramatic Shape Voxel Mod](#requirements) that
finishes Kanto's first-person view.

Dramatic Shape turns Gen 1 into a voxel world and lets you stand inside
it. This fills in what the original 2D maps never had to draw: interiors
get real walls, a ceiling and proper doors; the outdoor world gets a
horizon instead of empty sky. 

Yep, it's vibe coded. I just wanted to make a thing. If that's a problem, cool. Take it or leave it.

---

## What it adds

**Interiors and caves**
- **Walls.** Gen 1 only ever draws a room's north wall — the other three
  are the map edge, which the original camera never showed. These are
  synthesized floor-to-ceiling wherever open floor meets the void.
- **Ceilings** at a configurable headroom, so a room feels like a room.
  Walls rise to meet them, and tall furniture plugs its own column.
- **Doors**, including Gen 1's common two-cell double doors, with jambs,
  panelling and a lintel.
- **Materials come from the room itself.** Every surface is textured from
  that map's own tile art via the live terrain atlas, so a cave is rock,
  a Mart is Mart wall and a house is wallpaper — with nothing authored by
  hand, and following whichever colour mode you're playing in. The room's
  minority wall tiles are sprinkled through as accents so large walls
  don't read as flat.

**Outdoors**
- **A painted horizon** wrapped 360° around the world at distance,
  centred on the player so it never gets closer. Drawn behind everything
  with depth writes masked, so it can never occlude real geometry.

**Third person**
- **A cutaway** in the diorama rungs: near walls melt to stubs
  as you walk and the ceiling opens around you, so you can see into a
  roofed room from outside.

Everything is presentational. Collision, movement, ledge rules, triggers,
encounters, scripts and saves are untouched — nothing here can move the
player a single pixel.

---

## Requirements

- The Gen 1 Recompilation Project
- The **Dramatic Shape Voxel Mod**, installed and working.

## Install

1. Download the release `.zip`.
2. Install with the zip installer in Gen1Recomp.
3. Start the game once. The mod finds Dramatic Shape and applies its
   patch.
4. **Restart the game.** The patched modules load on the next boot.
5. Set Dramatic Shape's VOXEL mode to **1ST** and walk indoors.

## Options

In the mod manager, under this mod:

| Row | Default | What it does |
| --- | --- | --- |
| REMOVE PATCH | OFF | Turn ON and restart to uninstall the patch cleanly |
| CEILING | ON | Walls, ceilings and doors indoors |
| HEADROOM | AIRY | Ceiling height: AIRY (32), MID (24), SNUG (16) |
| SIMS CUTAWAY | ON | Cutaway view in the third-person diorama rungs |
| HORIZON | ON | The painted backdrop outdoors |
| JUMP FEEL | SUBTLE | Ledge-hop weight: OFF, SUBTLE, BIG |
| DEBUG HUD | OFF | On-screen diagnostic panel |

---

## How it works, and why it's a patcher

The engine draws exactly one world pipeline per frame, and Dramatic Shape
keeps its modules private with no exports — so a second mod has no seam to
draw through into its depth-buffered scene. This mod therefore carries its
renderer modules as a **patch to Dramatic Shape** and applies it for you:

- **Non-destructive by default.** Writes go through LÖVE's save directory,
  which shadows the game folder, so Dramatic Shape's own files are never
  modified when it lives there. If it lives in the save directory instead,
  originals are backed up (`*.pre-ceiling`) before being replaced.
- **Survives updates.** When Dramatic Shape updates, stale patched copies
  are cleared and the new version is patched fresh on the next boot.
- **Refuses rather than guesses.** If a future Dramatic Shape moves the
  anchor text, nothing is written and it says so.
- **Backs out cleanly.** REMOVE PATCH restores everything, byte for byte.

A boot log is written to `ds_fp_ceiling_log.txt` in the game's save folder.

## Troubleshooting

Turn **DEBUG HUD** on. It reports three lines: what the patcher did at
boot, what the ceiling decided this frame, and the horizon's state. Almost
every problem is legible there — and if you're reporting a bug, that panel
plus the boot log is exactly what's needed.

If nothing at all appears, check that REMOVE PATCH is off, then restart
twice: the patch applies on one boot and loads on the next.

## Credits and licence

Built on the Dramatic Shape Voxel Mod, which does the actual hard work of
rendering Kanto in three dimensions.

No ROM data ships in this mod and none is read from disk: every texture is
sampled at runtime from the game's own map renderer, on your machine, from
your own imported cache. The horizon artwork is original.
