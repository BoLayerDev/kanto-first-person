# Kanto in First Person — Interiors and Tweaks

A companion mod for the **Dramatic Shape Voxel Mod** that finishes Kanto's
first-person view.

Dramatic Shape turns Gen 1 into a voxel world and lets you stand inside it.
This fills in what the original 2D maps never had to draw: rooms get walls,
ceilings, doors and pictures; the sky gets weather, birds and aircraft; the
woods get a canopy with vines hanging from it; caves get rock, water and
bats; and walking, hopping and stepping through a doorway all carry some
weight.

Everything here is presentational. Collision, movement, ledge rules,
triggers, encounters, scripts and saves are untouched — nothing in this mod
can move the player a single pixel.

---

## What it adds

### Interiors

- **Walls.** Gen 1 draws only a room's north wall; the other three are the
  map edge, which the original camera never showed. These are synthesized
  floor to ceiling wherever open floor meets the void.
- **Ceilings** at a configurable headroom, with walls rising to meet them
  and tall furniture plugging its own column.
- **Doors** drawn as doors — frame, panels, handle and a step — full width,
  with a lintel above. A two-cell double doorway is simply two of them, as
  the original draws it.
- **Pictures on the walls**: thirty-five hand-drawn 16×16 frames in three
  sets, hung by room — general and domestic for houses, clinical for Poké
  Centres, shop signage for Marts. Never two side by side, never over a
  door.
- **Contact shadow** where the floor meets a wall, **a picture rail** near
  the ceiling, **daylight lying in through doorways**, and **lamps hanging
  from the ceiling** with light pooled beneath them.
- **Materials come from the room itself.** Every surface is textured from
  that map's own tile art, so a cave is rock, a Mart is Mart wall and a
  house is wallpaper — nothing authored by hand, and it follows whichever
  colour mode you play in.

### Caves

- **Rock overhead**: an uneven, sagging roof with **stalactites**, and
  **stalagmites** rising to meet them.
- **Still pools**, **torches guttering in the rock**, and **bats** that
  roost near the roof and scatter when you get close.

### Outdoors

- **A painted horizon**, in four panoramas you can switch between.
- **Layered clouds** — three decks at different heights and drift speeds,
  domed so they never meet the skyline, thinning after dark.
- **A night sky**: stars over a faint nebula, two dozen twinkling on their
  own clocks, and the occasional shooting star.
- **Birds** in loose echelon, facing the way they fly; **a ground flock**
  that pecks on open ground and flushes when you approach; **aircraft** —
  a rare plane laying a contrail, and a very occasional blimp.
- **Rain** on its own weather clock, with **NPCs putting up umbrellas**,
  **puddles** that fill and dry, and water kicked up as you walk.
- **Thunderstorms**, rarely: thunderheads, heavier rain and forked
  lightning at distance. Flashes are deliberately infrequent and gentle,
  and can be switched off on their own.
- **Rainbows** after a shower, hung opposite the sun and standing where the
  rain left them.
- **Chimney smoke** by day and **fog** over Lavender Town.

### Woods and ground level

- **A leafy forest canopy** in two layers with light wells between them,
  the wood walled at its rim and extending past the map edge into more
  wood.
- **Hanging vines** that sway, and swing when you walk through them.
- **Sun shafts** leaning down through the canopy.
- **Tall grass with varied height**, leaning in the **wind** — gusts travel
  across a field rather than the whole meadow nodding at once.
- **Insect swarms** over the grass by day and under the canopy.
- **Particles**: seeds kicked up as you walk, cave drips with a splash,
  fireflies after dark, falling leaves, interior dust, spray at the water's
  edge, and the occasional distant rustle with nothing attached to it.
- **The view carries past the map edge**: neighbouring maps draw their
  grass too, hazed with distance so the join is not a cut -- and beyond
  everything, each edge's own terrain continues outward as an apron,
  falling gently away, so the world never ends in a paper-thin rim.

### Movement

- **Jump feel**: the engine already hops you over ledges; this gives the
  hop a crouch, a boosted arc and a landing settle.
- **A doorway step**: the eye dips and leans through a warp instead of
  cutting to the other side.

### Third person and the diorama

- **A Sims-style cutaway**: near walls melt and the ceiling opens around
  you, so a roofed room can be seen into from outside.
- **3RD person** has its own setting — nothing, cutaway or the full sealed
  room — independent of what the diorama rungs get.

---

## Requirements

- The Gen 1 Recompilation Project
- The **Dramatic Shape Voxel Mod**, installed and working

Tested against absol89's fork 1.7.6 -- the mainline since the upstream
repository was deleted -- and against archived Dramatic Shape 1.5.4,
1.5.5, 1.6.0 and 1.7.0.

Incorporates **Ledge Leap 1.0.1** (a jump button: hop ledges from any
side, bounce elsewhere -- JUMP KEY and PAD BUTTON rows, both with OFF).
If you also run the standalone Ledge Leap, disable one copy. Dramatic Shape 1.6.1 and 1.6.2 declare a
conflict with this mod; this mod respects the flag, patches nothing, and
removes any earlier patch. On builds without a first-person rig the interior, canopy
and sky work in the diorama view and the movement features are skipped.

## Install

1. Download the release `.zip`.
2. Unzip into your `mods/` folder so you have `mods/ds_fp_ceiling/`
   alongside your Dramatic Shape folder.
3. Start the game. The patch applies before Dramatic Shape loads, so it
   works on this boot — no restart.
4. Set Dramatic Shape's VOXEL mode to **1ST** and go outside.

## Removing it

Either way works:

- **Just delete the mod folder.** This is enough on its own now: every
  file written into Dramatic Shape's folder is recorded in a ledger, and
  on the next boot the patch notices the mod has gone, walks that ledger
  to restore Dramatic Shape byte for byte, deletes its own files, and
  says so in `ds_fp_ceiling_log.txt`.
- **Or use REMOVE PATCH** and restart, if you prefer an explicit switch.
  It does the same thing from the same ledger; it is no longer
  necessary.

## Options

| Row | Default | What it does |
| --- | --- | --- |
| REMOVE PATCH | OFF | Explicit uninstall; deleting the folder does the same |
| CEILING | ON | Walls, ceilings and doors indoors |
| HEADROOM | AIRY | Ceiling height: AIRY / MID / SNUG |
| SIMS CUTAWAY | ON | Cutaway view in the diorama rungs |
| 3RD CEILING | CUTAWAY | What 3RD sees overhead: NONE / CUTAWAY / FULL |
| CONTACT SHADOW | ON | A dark band where floor meets wall |
| RAIL AND SKIRTING | ON | A picture rail near the ceiling |
| DOORWAY LIGHT | ON | Daylight lying in through doorways |
| CEILING LAMPS | ON | Hanging fittings with light pooled beneath |
| BUILDING BACKS | ON | Patches false back doors with the wall's own brick |
| WORLD APRON | ON | Boundary terrain continues past the map's rim |
| TALL TREES | ON | Rounds stand on trunks -- or stone stacks on rocky maps |
| MOUNTAIN PEAKS | ON | Clustered rock rises into massifs, across map seams |
| HEAD BOB | OFF | A gentle walk bob for those who miss it |
| FAST CHUNKS | ON | Doubles the mesh-build slice so chunks land sooner |
| JUMP KEY | SPACE | Ledge Leap: hop ledges from any side (J/L-CTRL/OFF) |
| PAD BUTTON | Y | Ledge Leap on a pad (X/OFF) |
| CAVE ROCK | ON | Uneven cave roof, stalactites and stalagmites |
| CAVE POOLS | ON | Still water underground |
| CAVE TORCHES | ON | Guttering torches set along cave walls |
| BATS | ON | Roosts that scatter when you approach |
| LAMPLIGHT | ON | Doorway lamps casting light that stops at walls |
| HORIZON | ON | The painted backdrop outdoors |
| HORIZON ART | VALLEY | Which panorama: KANTO / FUJI / VALLEY / CITY |
| CLOUDS | ON | Drifting cloud decks |
| NIGHT SKY | ON | Stars, nebula and shooting stars after dark |
| BIRDS | ON | Flocks of distant flyers |
| GROUND FLOCK | ON | Birds that peck on open ground and flush |
| AIRCRAFT | ON | Occasional planes with contrails, rare blimps |
| RAINBOWS | ON | A bow opposite the sun after a shower |
| RAIN | SOMETIMES | Showers, and occasionally storms: OFF / SOMETIMES / ALWAYS |
| LIGHTNING | ON | Forked lightning and a gentle flash during storms |
| NPC UMBRELLAS | ON | Umbrellas go up when it rains |
| PUDDLES | ON | Puddles fill in the rain and dry afterwards |
| LAVENDER FOG | ON | Fog over Lavender Town and its tower |
| FOREST CANOPY | ON | A leafy roof over the woods, with light wells |
| HANGING VINES | ON | Strands from the canopy that swing as you pass |
| SUN SHAFTS | ON | Light through the canopy |
| GRASS HEIGHT | SUBTLE | Extra grass blades: OFF / SUBTLE / WILD |
| WIND | BREEZE | Grass sway: OFF / BREEZE / GUSTY |
| INSECTS | ON | Gnat swarms over grass and under the canopy |
| PARTICLES | ON | Seeds, drips, fireflies, leaves, dust, spray, smoke |
| JUMP FEEL | SUBTLE | Ledge-hop crouch, arc and landing: OFF / SUBTLE / BIG |
| DOORWAY STEP | ON | The eye steps through warps instead of cutting |
| DEBUG HUD | OFF | On-screen diagnostic panel |

## Adding your own art

Drop files into the mod folder and reboot; they are installed
automatically.

- **Panoramas**: `backdrop2.png`, `backdrop3.png`, `backdrop4.png` —
  4096×256, transparent above the skyline, tiling left to right.
- **Pictures**: `posters.png`, `posters-pokecenter.png`,
  `posters-pokemart.png` — a horizontal strip of 16×16 frames. Alpha must
  be fully on or fully off: the renderer discards anything under half
  alpha, so there are no soft edges.

## How it works, and why it's a patcher

The engine draws exactly one world pipeline per frame, and Dramatic Shape
keeps its modules private with no exports — so a second mod has no seam to
draw through into its depth-buffered scene. This mod therefore carries its
renderer modules as a **patch to Dramatic Shape** and applies it for you:

- **Non-destructive by default.** Writes go through LÖVE's save directory,
  which shadows the game folder, so Dramatic Shape's own files are never
  modified when it lives there. Where it doesn't, originals are backed up
  (`*.pre-ceiling`) first.
- **Immediate.** The mod loads before Dramatic Shape, so the patch is in
  place by the time Dramatic Shape reads its files.
- **Survives updates.** When Dramatic Shape updates, stale patched copies
  are cleared and the new version patched fresh.
- **Refuses rather than guesses.** If a future Dramatic Shape moves the
  anchor text too far, nothing is written and the boot log says so.
- **Backs out cleanly**, whether you use REMOVE PATCH or delete the folder.

## Troubleshooting

Turn **DEBUG HUD** on. It reports what the patcher did at boot and what
each effect decided this frame — including why something isn't appearing —
plus a census of every registered render pipeline and whether the engine
still considers it eligible. Almost every problem is legible there, and
that panel plus `ds_fp_ceiling_log.txt` is exactly what's needed in a bug
report.

## Compatibility

Known to run alongside **Wilds of Kanto**. Its wild Pokémon are drawn by
Dramatic Shape's own cast pass, which runs after this mod's geometry, so
every draw here sits inside a graphics-state guard rather than restoring
state by hand. If sprites from another mod ever disappear while this one is
loaded, that is the first thing to suspect and worth reporting.

## Credits and licence

Built on the Dramatic Shape Voxel Mod, which does the actual hard work of
rendering Kanto in three dimensions.

No ROM data ships in this mod and none is read at runtime. Every surface is
textured from the game's own map renderer on your machine, and the bird
frames are derived once from your own imported cache by this mod's asset
transform. The panoramas, pictures, umbrellas, aircraft, door art and all
generated sprites are original.
