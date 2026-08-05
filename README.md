# Kanto in First Person — Interiors and Tweaks

A companion mod for the [Dramatic Shape Voxel Mod](#requirements) that
finishes Kanto's first-person view.

Dramatic Shape turns Gen 1 into a voxel world and lets you stand inside
it. This fills in what the original 2D maps never had to draw: interiors
get real walls, a ceiling and proper doors; the outdoor world gets a
horizon, weather and a sky with things in it; the woods get a canopy; and
walking, hopping and stepping through doors all get some weight behind
them.

Everything here is presentational. Collision, movement, ledge rules,
triggers, encounters, scripts and saves are untouched — nothing in this
mod can move the player a single pixel.

---

## What it adds

### Interiors and caves

- **Contact shadow** where floor meets wall, **a picture rail and
  skirting**, **daylight lying in through doorways** and **lamps hanging
  from the ceiling** with their pools beneath.
- **Pictures on the walls**: thirty-five hand-drawn 16x16 frames in three
  sets -- general, Poke Centre and Mart -- hung by room. Caves, woods and
  the Tower get none, which is as it should be.

- **Walls.** Gen 1 only ever draws a room's north wall — the other three
  are the map edge, which the original camera never showed. These are
  synthesized floor-to-ceiling wherever open floor meets the void.
- **Ceilings** at a configurable headroom, so a room feels like a room.
  Walls rise to meet them, and tall furniture plugs its own column.
- **Doors** wearing the map's own door art, full width, with a lintel
  above -- and a two-cell double doorway is simply two of them, as the
  original draws it.
- **Still pools** underground, **torches set in the rock**, and **bats**
  that roost near the roof and scatter when you get close.
- **Rock overhead in caves**: an uneven sagging roof with stalactites,
  and stalagmites rising to meet them.
- **Cave darkness** on the floors the engine marks unlit — and **Flash**
  doesn't switch it off, it pushes the walls back, so the HM finally
  does something you can see.
- **Materials come from the room itself.** Every surface is textured from
  that map's own tile art, so a cave is rock, a Mart is Mart wall and a
  house is wallpaper — with nothing authored by hand, following whichever
  colour mode you're playing in. Walls above the drawn row use the room's
  plainest tile, measured off the atlas, with its featured tiles
  sprinkled through as accents.

### Outdoors

- **A painted horizon** wrapped around the world at distance, centred on
  the player so it never gets closer.
- **Layered clouds** — three decks at different heights and drift speeds,
  thinning out after dark.
- **A night sky**: stars at four brightnesses over a faint nebula, two
  dozen twinkling on their own clocks, and the occasional shooting star.
- **Birds**: flocks of distant flyers with synthesised wingbeats, facing
  the way they fly, recycling around you as you travel. About one flock
  in forty is something rarer, alone and higher than the rest.
- **Aircraft**: a rare high plane laying a contrail, and a very
  occasional blimp.
- **Rain** on its own weather clock — and every NPC puts up a little
  pixel umbrella while it falls.
- **Rainbows** after a shower, hung opposite the sun.
- **Thunderstorms**, rarely: thunderheads, heavier rain and forked
  lightning at distance. Flashes are deliberately infrequent and gentle,
  and can be turned off on their own.
- **Puddles** that fill as it rains and dry slowly afterwards.
- **Chimney smoke** by day and **fog** over Lavender Town. (Lit windows
  come from Dramatic Shape itself.)

### Woods and ground level

- **The view carries on past the map edge**: grass continues onto
  neighbouring maps, hazed with distance so the join is not a cut.

- **A leafy forest canopy** in two layers: a gapped lower one and a solid
  upper one, so the light wells show sunlit leaves rather than void. The
  wood is walled at its rim, and foliage is chosen by measured greenness
  rather than by which tile happens to be common.
- **Sun shafts** leaning down through the canopy.
- **Hanging vines** that sway, and swing away when you brush past them.
- **Trees at varied heights**, so a wood has a skyline instead of a flat
  hedge line. Buildings are a different class and are untouched.
- **Tall grass with varied height**, so encounter cells look like
  somewhere things live.
- **Particles**: seeds kicked up as you move through grass, cave drips
  with a splash, fireflies after dark, falling leaves under the canopy,
  dust turning in interior air, spray at the water's edge, and very
  occasionally a distant rustle in the grass with nothing attached to it.
- **Insect swarms** hanging over the grass by day and under the canopy.
- **Wind**, gusting across the tall grass in waves rather than all at once.
- **A ground flock** that settles on open ground to peck, and flushes
  when you get too close.

### Movement

- **Head bob and sway**, driven by distance walked rather than by a
  clock, so they stay locked to your feet and stop dead when you do.
- **Jump feel**: the engine already hops you over ledges; this gives the
  hop a crouch, a boosted arc and a landing settle.
- **A doorway step**: the eye dips and leans through a warp instead of
  cutting to the other side.

### Third person

- **A Sims-style cutaway** in the diorama rungs: near walls melt to stubs
  as you walk and the ceiling opens around you, so you can see into a
  roofed room from outside.

---

## Requirements

- The Gen 1 Recompilation Project
- The **Dramatic Shape Voxel Mod**, installed and working (tested against
  1.5.4)

## Install

1. Download the release `.zip`.
2. Unzip it into your `mods/` folder so you have `mods/ds_fp_ceiling/`,
   sitting alongside your Dramatic Shape folder.
3. Start the game. The mod patches Dramatic Shape before Dramatic Shape
   loads, so it works on this boot — no restart.
4. Set Dramatic Shape's VOXEL mode to **1ST** and go outside.

## Options

In the mod manager, under this mod:

| Row | Default | What it does |
| --- | --- | --- |
| REMOVE PATCH | OFF | Turn ON and restart to uninstall cleanly |
| CEILING | ON | Walls, ceilings and doors indoors |
| HEADROOM | AIRY | Ceiling height: AIRY (32), MID (24), SNUG (16) |
| SIMS CUTAWAY | ON | Cutaway view in the third-person diorama rungs |
| CONTACT SHADOW | ON | A dark band where floor meets wall |
| RAIL AND SKIRTING | ON | A picture rail near the ceiling |
| DOORWAY LIGHT | ON | Daylight lying in through doorways |
| CEILING LAMPS | ON | Hanging fittings with light pooled beneath |
| CAVE ROCK | ON | Uneven cave roof, stalactites and stalagmites |
| BUILDING BACKS | ON | Covers the false door repeated on a building's back |
| CAVE POOLS | ON | Still water underground |
| CAVE TORCHES | ON | Guttering torches set along cave walls |
| BATS | ON | Roosts that scatter when you approach |
| 3RD CEILING | CUTAWAY | What 3RD person sees overhead: NONE, CUTAWAY or FULL |
| CAVE DARKNESS | ON | Unlit floors close in; Flash widens the light |
| HORIZON | ON | The painted backdrop outdoors |
| HORIZON ART | VALLEY | Which panorama: KANTO, FUJI, VALLEY or CITY |
| CLOUDS | ON | Drifting cloud layers |
| NIGHT SKY | ON | Stars, nebula and shooting stars after dark |
| BIRDS | ON | Flocks of distant flyers |
| AIRCRAFT | ON | Occasional planes with contrails, rare blimps |
| RAINBOWS | ON | A bow opposite the sun after a shower |
| INSECTS | ON | Gnat swarms over grass and under the canopy |
| GROUND FLOCK | ON | Birds that peck on open ground and flush |
| WIND | BREEZE | Grass sway: OFF / BREEZE / GUSTY |
| RAIN | SOMETIMES | Showers, and occasionally storms: OFF / SOMETIMES / ALWAYS |
| PUDDLES | ON | Puddles fill in the rain and dry afterwards |
| LIGHTNING | ON | Forked lightning and a gentle flash during storms |
| LAMPLIGHT | ON | Doorway lamps casting light that stops at walls |
| NPC UMBRELLAS | ON | Umbrellas go up when it rains |
| LAVENDER FOG | ON | Fog over Lavender Town and its tower |
| FOREST CANOPY | ON | A leafy roof over the woods, with light wells |
| HANGING VINES | ON | Strands from the canopy that swing as you pass |
| SUN SHAFTS | ON | Light through the canopy |
| HANGING VINES | ON | Vines that dangle and swing when brushed |
| TREE HEIGHT | SUBTLE | Varied treetops: OFF / SUBTLE / WILD |
| GRASS HEIGHT | SUBTLE | Extra grass blades: OFF / SUBTLE / WILD |
| PARTICLES | ON | Seeds, drips, fireflies, leaves, dust, spray, smoke |
| JUMP FEEL | SUBTLE | Ledge-hop weight and head bob: OFF / SUBTLE / BIG |
| DOORWAY STEP | ON | The eye steps through warps instead of cutting |
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
- **Immediate.** The mod loads before Dramatic Shape, so the patch is in
  place by the time Dramatic Shape reads its files. No restart.
- **Survives updates.** When Dramatic Shape updates, stale patched copies
  are cleared and the new version is patched fresh.
- **Refuses rather than guesses.** If a future Dramatic Shape moves the
  anchor text, nothing is written and it says so.
- **Backs out cleanly.** REMOVE PATCH restores everything, byte for byte.

A boot log is written to `ds_fp_ceiling_log.txt` in the game's save folder.

## Removing it

Either way works:

- **Tidy:** turn REMOVE PATCH on in the options and restart. Everything
  is restored byte for byte.
- **Or just delete the mod folder.** The patch notices that the mod has
  gone, puts Dramatic Shape's own files back, deletes its own, and says
  so in `ds_fp_ceiling_log.txt`. From the next boot Dramatic Shape is
  stock again.

## Troubleshooting

Turn **DEBUG HUD** on. It reports what the patcher did at boot and what
each effect decided this frame — including why something isn't appearing.
Almost every problem is legible there, and if you're reporting a bug, that
panel plus the boot log is exactly what's needed.

If nothing at all appears, check that REMOVE PATCH is off.

## Compatibility

**Dramatic Shape forks.** Tested against the standard mod (1.5.4) and
absol89's battle-art fork (based on 1.3.0). On builds without a
first-person rig the interior, canopy and sky work in the diorama view
and the movement features are skipped, since there is nothing to splice
them into. If a build is too different to patch safely, nothing is
written and the boot log says so.

Known to run alongside **Wilds of Kanto**, which adds visible wild Pokemon
to the overworld. Its sprites are drawn by Dramatic Shape's own cast pass,
which runs after this mod's geometry in the same frame, so this mod keeps
every draw inside a graphics-state guard rather than restoring state by
hand. If sprites from another mod ever disappear while this one is
loaded, that is the first thing to suspect and worth reporting.

## Credits and licence

Built on the Dramatic Shape Voxel Mod, which does the actual hard work of
rendering Kanto in three dimensions.

No ROM data ships in this mod and none is read at runtime. Every texture
is sampled from the game's own map renderer on your machine, and the bird
frames are derived once from your own imported cache by this mod's asset
transform. The horizon artwork, umbrellas, aircraft and all generated
sprites are original.
