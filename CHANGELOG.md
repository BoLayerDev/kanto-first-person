# Changelog

## 1.36.0

- **MOUNTAINS removed.** Deriving the HEIGHT from how deep a cell sits
  inside its own cluster worked, and looked good. Deciding WHICH cells
  are rock never did: the tile classes come back unauthored for ordinary
  terrain, an Image cannot be read back so the colour test never ran at
  all, and every rule tried either raised the whole world -- trees,
  houses and sea -- or nothing whatever. Six attempts is enough; it is
  left out rather than left broken, and the MOUNTAINS option is gone.
- Everything the attempt brought with it stays: neighbouring maps still
  draw their grass, the distance haze still sets them back, and the backs
  of buildings are still covered.

## 1.35.1

- **Fixed: the mountains asked about the wrong corner of every cell.**
  A cell is two tiles by two, and the engine's canonical one is the
  BOTTOM LEFT -- `Map:cellTile` is literally `tileAt(cx * 2, cy * 2 + 1)`
  and the collision rules read that corner. This module sampled the TOP
  left, so TileShape was asked about a tile the map does not consider the
  cell's own, found nothing authored for it, and answered nil for all six
  hundred and thirty-nine cells in Pewter City. That is what `?=639` on
  the debug HUD was saying.
- Unauthored solid tiles are now read as `wall`, which is what Dramatic
  Shape's own mesher does with them, rather than as unknown.

## 1.35.0

- **Mountains, from the engine's own classification.** Dramatic Shape
  already sorts every tile: `tree`, `cylinder`, `canopy` and `stump` for
  foliage, `roof`, `wall`, `fence` and `sign` for built things, and
  `ledge` and `cliff` for the steps in the terrain. Reading colours off
  the atlas was inventing an answer the engine was already holding -- and
  it did not even work, because an Image cannot be read back, so the
  colour test returned nothing and the fallback raised the entire world,
  trees and houses included. Rock is now `ledge`, `cliff` and `wall`
  minus anything a doorway climbs to; foliage and roofs are never raised.
- The colour test is gone rather than repaired, and the debug HUD reports
  a CENSUS of the classes a map actually uses, so if this comes out wrong
  again the answer is on screen rather than in a guess.

## 1.34.0

- **Rainbows stand still.** The bow was positioned relative to the
  player, so it travelled with them -- walk a hundred units and it walked
  too. It is now pinned once, where the shower left it, and stays there:
  walk toward it and you approach it, as you would.
- **Real back doors are left alone.** Some houses have a genuine rear
  entrance, and the cover-up was boarding it over. A cell that is itself
  a door tile is skipped.
- **Mountains: diagnostics, and a floor under the whole rule.** Three
  releases have ended with no hills at all because some test excluded
  everything, and guessing which one from here has not worked. The debug
  HUD now reports what the rule actually saw -- how many cells were
  solid, how many were reached by the walk, how many the engine called
  `cliff`, and how many scored as rock -- so the answer comes from the
  game rather than from me. And if the atlas cannot be read at all, the
  fallback raises solid non-water, non-building cells, because an
  imperfect hill beats an empty world.

## 1.33.1

- **Rainbows: back to facing you, further off and stronger.** Fixing the
  bow in world space was the wrong lesson to draw from "it moves when I
  turn". A flat quad standing in the world is a rainbow only from square
  on; from any other angle it foreshortens into a thin upright sliver,
  which is what it became. What must stay put is its POSITION -- and that
  is anti-solar, which does not care where the player is looking. Facing
  the viewer is then not a cheat: a real bow is a cone of light around
  the anti-solar point and presents its face wherever you stand.
  - 1600 out rather than 900, spanning about sixty degrees and topping
    out around thirty up, at eighty percent opacity.
  - The test now asserts the right thing: the bow's POSITION must not
    change when the camera turns, while its facing must follow.

## 1.33.0

- **Mountains, properly this time.** Cells had to be TWO deep inside a
  solid cluster before they would rise. That worked while trees and
  buildings were still being swept up -- they form thick clumps -- but
  Kanto's actual rock is a ledge one or two cells thick, so excluding the
  impostors left almost nothing that qualified. Every rock cell rises
  now: a single ledge gets one step, and a broad outcrop still peaks in
  the middle, because the ring count still drives the height.
- **The backs of buildings: only the door column.** Covering the whole
  rear wall put a slab of one tile across the back of a house, which
  bleeds past its edges and looks worse than the fault it was fixing.
  The mirroring that matters is the DOOR -- the mesher repeats the door
  tile on the far face, so a house appears to have a second entrance
  round the back. That column is covered and nothing else.
- **VALLEY is the default horizon.**

## 1.32.0

- **Interior doorways are drawn as doors.** 1.31.0 used the map's own
  tile on the assumption that the art under a doorway IS a door. Often it
  is not -- it is whatever the wall happens to be -- so the doorway came
  out looking like more wall. The door is drawn instead: a frame, two
  panels, a handle and a step, in four shades, on its own mesh with its
  own texture. A double doorway is two of them, side by side.
- **Fixed: the mountains vanished again.** 1.29.1's whitelist asked that
  rock be dull as well as neither leaf nor water -- and Kanto's ledges
  and outcrops are a strong orange-brown, high in colour, so the
  saturation test threw out everything it was meant to keep. Not green
  and not blue is the whole distinction needed; buildings are already
  excluded by their doors.

## 1.31.1

- **Rainbows arch over the horizon instead of filling the sky.** At 4200
  across and 2200 out the bow subtended most of the view, which reads as
  a wall of colour rather than as weather. It now spans about seventy
  degrees and tops out around thirty-five up, with its feet on the
  skyline -- which is where a rainbow stands. A little more transparent
  with it: present, not painted on.

## 1.31.0

- **Interior doorways use the game's own door art.** This mod used to
  BUILD a door -- jambs cut in from the sides, a leaf recessed by shade,
  two panels proud of it -- which was carpentry laid over art that
  already exists. The map draws a door on that tile, and a double doorway
  is simply two of those tiles side by side, exactly as the original
  does. Each door cell now shows its own tile across the full width of
  the cell, with plain wall above.
- **The backs of buildings are plain wall.** The mesher extrudes a
  building cell as a box and wears the same tile on every face, so a
  shopfront's door and windows appeared again on the back wall -- false
  doors all over Kanto, leading nowhere. Any building cell with an
  exposed north face now gets a quad of the building's own SIDE tile laid
  a hair proud of it. Fronts are untouched: a shopfront should look like
  a shopfront. New BUILDING BACKS toggle.

## 1.30.0

- **Deleting the mod now removes the patch.** The patch lives in Dramatic
  Shape's own folder, so deleting this mod used to leave it behind -- the
  shadow copies kept loading, and the REMOVE PATCH option that would have
  undone them went with the mod. People got stuck, reasonably.
  - The patched modules check once whether the companion is still there:
    it publishes a config bridge as it loads, always before Dramatic
    Shape, so no bridge means no mod.
  - Orphaned, they take themselves out -- originals restored where they
    were backed up, shadow copies deleted where they were not -- and go
    quiet for the rest of the session. From the next boot Dramatic Shape
    is stock again with nothing left to clean.
  - A line is written to `ds_fp_ceiling_log.txt` saying so, in case
    anyone wonders where it went.
- REMOVE PATCH still works as before and is still the tidy way to do it;
  this is the safety net for people who delete the folder instead.

## 1.29.1

- **Fixed: mountains grew out of water, trees and buildings.** The test
  was "anything solid that is not a building and not green", which is a
  blacklist -- and water is solid, unwalkable and not green, so the sea
  rose into hills and took Dramatic Shape's water surface with it.
  Raising is a WHITELIST now: never water (asked of the map directly),
  yes to the engine's own `cliff` class where it says so, otherwise only
  tiles whose art is rock-coloured -- dull, and neither leaf nor water.
  With no atlas to read, nothing is raised at all: better a flat world
  than hills growing out of the sea.

## 1.29.0

- **Mountains and grass now continue onto the maps either side of you.**
  Dramatic Shape has always meshed and drawn its neighbours' terrain, but
  every feature in this mod was built for the current map alone -- so
  hills and grass stopped dead at the boundary and appeared the moment
  you crossed it. That was the popping. Each neighbour's geometry is
  built once, cached for as long as it stays next door, and drawn at the
  neighbour's own offset exactly as the terrain is.
- **Distance haze.** Air is not clear: far ground loses contrast and
  cools toward the colour of the sky, beginning a couple of hundred units
  out and deepening to about a third by the far edge. It is what sets a
  distant map back behind a near one, so the join stops reading as a cut.
- Deliberately NOT extended across the boundary: particles, weather,
  bats, vines and torches. Those are things happening near you, and
  simulating them on four maps at once would cost real time for something
  you could barely see.

## 1.28.0

- **MOUNTAINS.** Outdoor rock read as a flat kerb because every solid
  cell is one block tall whatever its neighbours are doing. Height now
  comes from how DEEP a cell sits inside its own cluster: a walk out from
  open ground gives each solid cell its distance to the nearest gap, and
  the block rises in proportion. A lone boulder stays a boulder; the
  middle of a large outcrop becomes a peak and the sides step down to
  meet the path. It is the shape a hill actually is, taken from the map
  rather than invented. Buildings and anything green are left alone.
  OFF / SUBTLE / BIG.
- **Switching panorama now takes effect at once.** The choice was
  resolved once at boot; it is re-read each frame, and the backdrop
  notices when the path it loaded is no longer the one being asked for.
- **Umbrellas sit in front of their NPC.** Dramatic Shape draws its cast
  after this mod's pass, so an umbrella sharing the NPC's position lost
  the depth test to them. It is nudged a couple of units toward the
  camera.
- **The forest edge has its floor back.** Dropping it clear of the real
  ground to stop the flicker had put it out of sight; it sits a whisker
  above instead.
- **Rainbows are drawn both ways round.** Fixing the bow in world space
  gave it a single face, and when that face pointed away from you it was
  culled -- so the bow was there and invisible.

## 1.27.0

Playtest round. Eight faults, most of them mine from the last three
releases.

- **Choosing a panorama did nothing on a fresh install.** The lookup that
  honours HORIZON ART lived only in the already-patched branch, so a
  first boot always got KANTO whatever the option said.
- **Smoke rose off the scenery.** A building was "a solid two-by-two",
  which is also a clump of trees, a rock, a hedge or a fence corner. A
  building has a DOOR: the doors are found first now, and the chimney is
  the roof above one. Nothing else smokes.
- **Stalactites in ordinary rooms**, because the Tower and the route
  tunnels count as organic for keeping pictures off their walls, and rock
  followed the same list. Rock is now for actual caves.
- **Ceiling lamps and doorway daylight in caves.** Both are for built
  rooms; neither belongs underground.
- **Pictures still hung over doorways.** The poster code asked its own
  weaker question instead of the module's door test, which counts warps
  as well as door tiles.
- **The forest floor vanished** after being dropped clear of the real
  ground to stop it flickering. It sits a fifth of a unit down now rather
  than more than half.
- **The skirting board is gone.** It read as a stripe of somebody else's
  tile along the floor rather than as a moulding. The picture rail stays.
- **Lamps were making rooms DARKER.** All this light was alpha-blended,
  and a warm quad at thirty percent over a pale floor is darker than the
  floor. It is drawn additively now, indoors and in caves, so light adds
  light.

## 1.26.0

- **Three more horizons**, selectable in the options: FUJI (a great
  volcano over lighthouses and farmland), VALLEY (villages giving way to
  a city under a mountain range) and CITY (a river frontage of towers
  running out to peaks). KANTO remains the default.
- Each was keyed, trimmed to its own artwork, fitted by HEIGHT so the
  proportions hold -- scaling to the full width would squash a mountain
  into a ridge -- then mirror-tiled across the cylinder so the ridgeline
  runs on without an obvious repeat.
- The wrap seam is blended in premultiplied alpha. Mixing colour and
  alpha separately leaves the colour of transparent pixels behind, and
  the keyed magenta came back as a faint pink haze exactly at the join.

## 1.25.1

- **Fixed: CAVE DARKNESS never worked.** The engine keeps its list of
  unlit floors at `field.darkMaps.MAPS` -- an array inside a table, as
  its own Rock Tunnel test asserts -- and this mod looked for the ids
  directly on `darkMaps`. The lookup matched nothing, so the darkness
  shells never drew, Flash never widened them, and 1.25.0's pools,
  torches and bats never appeared either, since all of it is gated behind
  the same flag.
- The harness deserves the blame for this surviving: it modelled the
  shape this mod *assumed* rather than the one the engine has, and so
  cheerfully confirmed a lookup that could never match. It now uses the
  real shape, and asserts that a listed map reads as dark, an unlisted
  one does not, and Flash widens the shells rather than switching them
  off.

## 1.25.0

Three more for caves.

- **Still pools.** The puddles' permanent cousin: water that was here
  before you and will be here after, built once per cave rather than
  filled by weather, wearing the map's own water tile. The drips already
  falling from the roof land in them.
- **Torches.** Set into the rock at intervals along a wall rather than
  only at the mouth -- somebody has been down here before, and a cave
  with one lit entrance and a mile of blackness reads as unfinished
  rather than as dark. Each flame gutters on its own clock.
- **Bats.** They roost in clusters near the roof, breathing gently, and
  scatter when you come within a few cells -- dropping first, then
  climbing hard, fluttering rather than flying in lines. One waking wakes
  the roost. They wear frames derived from the player's own Zubat, so
  they are the right animal and no new artwork.
- New CAVE POOLS, CAVE TORCHES and BATS toggles. `invalidate` now also
  forgets the derived bat frames, so a reload looks for them again rather
  than remembering that they were missing.

## 1.24.0

- **Caves get rock instead of plaster.** The structural lid stays where
  it is, so walls still meet something, and a second UNEVEN surface hangs
  beneath it: a panel per cell at a hashed height with a skirt wherever
  it drops below its neighbour, built exactly the way the forest canopy
  is. Rock sags; a bedroom ceiling does not.
- **Stalactites and stalagmites.** Tapering spikes from the rock above,
  and rather less than half of them stood on their head to grow from the
  floor instead. Both wear the cave's own tile art and are hashed per
  cell, so Mt Moon looks the same on every visit. New CAVE ROCK toggle.
- **Fixed: caves had a picture rail.** Only the posters consulted the
  list of organic interiors, so 1.23.0's rail and skirting ran merrily
  round Mt Moon. Both now check it, as they should have from the start.

## 1.23.0

Four things for interiors, all of them light and shade on geometry that
already exists rather than new objects.

- **Contact shadow.** A dark band where the floor meets a wall, made of
  the floor's own art at a fraction of its brightness. It is the cheapest
  trick in real-time rendering and it does more than it costs: without
  it, everything looks placed ON the floor rather than standing IN the
  room, because nothing grounds it.
- **Rail and skirting.** One course of the room's busiest tile near the
  ceiling and another at the floor, chosen by the same measure that picks
  the plainest tile for the wall field. Besides looking like a room, this
  is what will make taller ceilings possible: a tall wall is one tile
  repeated, and a rail breaks the run.
- **Doorway light.** A wedge of daylight lying on the floor inside each
  door, narrowing as it reaches in, because a door is a slot.
- **Ceiling lamps.** A flex, a shade and the pool it throws, hung on a
  loose grid so a big room gets several -- and one in the middle
  regardless, so a small room still gets its light rather than falling
  through the grid. The vines provided the precedent: a pendant is the
  same shape with a shade on the end.

Light and spill are drawn on their own mesh with a plain texture, because
they are light rather than surface. New options: CONTACT SHADOW, RAIL AND
SKIRTING, DOORWAY LIGHT, CEILING LAMPS, all on by default.

## 1.22.0

- **Rainbows stand still.** The bow was billboarded like the clouds and
  the birds, so it swung round as you looked about -- which is precisely
  what gives a painted backdrop away. It now hangs on the anti-solar axis
  in world space and stays there while you turn your head. Nearly twice
  as large with it, and further off.
- **Fixed: the flickering ground at the forest edge.** Dramatic Shape
  draws the neighbouring maps as well, so the ring's floor and a real one
  could occupy the same plane -- two surfaces at identical depth flicker
  as the camera moves. The ring floor and the ring trees now sit a hair
  below, so real ground always wins and ours shows only where there is
  genuinely nothing.
- **Pictures no longer crowd or cover doorways.** No two hang in
  neighbouring cells, and none hangs on a door cell or on the wall a door
  passes through.

## 1.21.1

- **Fixed: the pictures were hung on the OUTSIDE of the walls.** Each was
  placed a fraction beyond its wall and wound to face outward, so every
  picture in Kanto was on the back of a building, facing the void, where
  nobody could ever see it. They hang on the inside face now, looking
  into the room.
- **Some vines run to the floor.** About one strand in four is long
  enough to reach the ground, which is what makes a canopy feel like
  something hanging over you rather than fringing along a ceiling.
- **Rainbows are visible again.** The arc's own texture peaked at 0.42
  opacity and was then DRAWN at 0.42 as well; the two multiplied to about
  a sixth, which is not ethereal, it is absent. It also hung about for
  only a minute after showers that come four to fifteen minutes apart.
  Now roughly two-thirds opacity at its heart, still soft at both rims,
  and it stays for two and a half minutes.

## 1.20.0

- **Hanging vines.** Strands drop from the underside of the forest
  canopy -- a stem with a stub or two off it -- swaying on the same slow
  clock the grass uses, and SWINGING when you walk through them, then
  settling over a couple of seconds with a swing back and forth rather
  than a slump.
  - A mesh is drawn with one matrix, so a single strand cannot move
    without moving every strand with it. The vines are therefore built
    into blocks of eight cells square, each its own mesh: pushing through
    a block disturbs that block and nothing else, while distant wood
    keeps swaying gently.
  - The bend is a shear about the CANOPY rather than the ground, since a
    vine's fixed end is its top and its free end is its tail.
  - They hang in first and third person only; the diorama rungs, looking
    down from above, would see nothing but clutter.
  - New HANGING VINES toggle.

## 1.20.0

- **Hanging vines.** Strands of stem and leaf stubs dangle out of the
  forest canopy, each swinging on its own slow clock -- and when you walk
  through one it takes a shove away from you, proportional to how fast
  you were going, then springs back with the overshoot damped out. The
  anchor stays in the leaves and the free end swings, which is a shear
  rather than an animation, so a wood full of them costs almost nothing.
  Only strands near you are updated or drawn at all.
  - First and third person only: from the diorama you would be looking
    down at the tops of them. New HANGING VINES toggle.
- **Fixed: movement was measured inside the particle pass**, so turning
  PARTICLES off silently stopped the vines noticing anyone walking
  through them. It is measured once a frame now, where everything can
  see it.

## 1.19.0

- **Fixed: TREE HEIGHT did nothing.** It identified trees by asking
  TileShape for class `tree`, which the real game never returns -- the
  same trap the canopy fell into. Trees are now found by what they look
  like: full height, not part of a solid two-by-two (that is a building),
  and GREEN, measured off the atlas. Fences and signs fail the colour
  test, buildings fail the shape test, and what is left is foliage. The
  setting has real effect for the first time.
- **The wood now extends past its own edge.** A curtain hung on the map's
  rim read as a wall with leaves on it, because that is what it was.
  There is now a four-cell RING of further trees beyond the map -- trunks
  at varied heights under canopy that carries on over them -- and the
  curtain has moved out behind that ring. You see wood receding into
  wood, and the thing that stops you seeing further is several trees
  away rather than one.

## 1.18.0

- **3RD CEILING** replaces the CEILING IN 3RD toggle, with three
  answers: NONE, CUTAWAY (the default) or FULL. Third person now has its
  own setting rather than sharing SIMS CUTAWAY, so you can have a cutaway
  in the diorama and nothing at all over your shoulder, or the reverse.
  It governs the forest canopy on the same terms.
- The three cases are now answered separately: inside the head is always
  the sealed room, a boomed-out third-person camera follows 3RD CEILING,
  and the diorama rungs follow SIMS CUTAWAY.

## 1.17.0

- **Ceilings and canopies open up in 3RD person.** Dramatic Shape 1.5.5
  added a third-person rung -- the same first-person rig with the eye
  boomed back behind the shoulder -- and the blend reads as engaged
  there, so a sealed ceiling would slam shut in front of a camera now
  standing outside the room. Boomed out, the room and the wood now get
  the same cutaway treatment the diorama gets.
- The signal is Dramatic Shape's own `showsPlayer()` rather than the
  raw extension, which means backing into a wall -- where the boom
  collapses into your head and the view really is first person again --
  correctly closes the room over you.
- **CEILING IN 3RD** (off by default) forces the old sealed behaviour for
  anyone who prefers it.

## 1.16.0

- **Thirty-five hand-drawn pictures now hang on interior walls**, in
  three sets chosen by room:
  - *Houses and everywhere else* (19): mountains, a potted plant, a
    clock, a sailboat, a noticeboard, a patterned hanging, a mushroom, a
    bird, a pair of shorts, a fish, a chicken, and a domestic set of a
    paw print, an egg in a nest, a berry, a bug net, a fishing rod, a
    region map, a trophy and a feather. Wooden frames.
  - *Poke Centres* (8): a medical cross, a ball emblem, a potion, a
    first-aid kit, the storage PC, a bed, a heart-rate trace and a
    certificate. Grey-and-red clinical frames.
  - *Marts* (8): a basket, a price tag, a barcode, a parcel, a till, a
    can, a sale starburst and a stocked shelf. Blue-and-white shop
    frames.
- **Nothing hangs in organic interiors.** Caves, woods, the Tower and
  the route tunnels are skipped outright -- a framed picture on a cave
  wall is the kind of detail that makes a whole scene read as a mistake.
  They do not even load a sheet.
- Missing sets fall back to the general one rather than to bare walls,
  and drop-in replacements are picked up on the next boot.

## 1.15.0

- **Wall accents replaced by posters.** The old sprinkle scattered
  fragments of the room's own featured tiles across the upper courses --
  half a window, part of a sign, stretched somewhere it never belonged.
  Walls are a plain field now, and pictures are hung on them instead,
  from a sprite sheet the mod carries (`posters.png`). One eligible wall
  face in six gets one, chosen by position hash, so a room hangs the same
  art every visit. With no sheet installed, walls are simply plain.
- **Horizon art is selectable.** Drop `backdrop2.png`, `backdrop3.png` or
  `backdrop4.png` into the mod folder and they appear in the options as
  ALT 1 to ALT 3, alongside the shipped KANTO panorama. A missing file
  falls back to the shipped one rather than emptying the sky.

## 1.14.0

- **Window light removed** -- it was the pale squares. Two faults at
  once: the sprite was built with square distance rather than radial, so
  it was a solid block by construction, and at pane size against a wall
  it was enormous. It was also redundant: Dramatic Shape's own glass mask
  already lights windows at night, "as a window with a lamp behind it
  is", so the feature was competing with a better one. The WINDOW LIGHT
  option is gone with it.
- Doorway lamps now use a small round mote rather than that square pane,
  and are a third the size.

## 1.13.1

- **Fixed: puddles indoors.** The wetness gate asked whether it had been
  raining, not whether there was any sky to rain from -- so walking into
  a house after a shower brought the puddles in with you. They are
  outdoors only now, and the street keeps drying while you are inside, so
  stepping back out finds it further along rather than frozen wet.
- **Fixed: the judder as puddles appeared.** Their geometry was built at
  the moment they first became visible, which put a few hundred quads'
  worth of construction in the middle of a walk. It is built on arriving
  at the map instead, when a frame is already being spent on loading.
- Puddles sit a little higher off the floor, so a moving camera cannot
  make the two surfaces argue about which is in front.

## 1.13.0

- **Puddles rebuilt.** They are round now -- a fan of wedges with a
  wobble on the rim, rather than one square quad per cell -- they wear
  the map's OWN water tile so they are made of the same stuff the sea is,
  and there are half as many. They also arrive in stages: puddles are
  split into four groups that ease in one after another as the ground
  wets, so they gather across a street instead of every tile switching on
  at once.
- **Walking in the rain kicks water up**, harder once the puddles have
  filled -- the small thing that ties the weather to you rather than to
  the scenery.
- **Fixed: the position hash was badly distributed.** An LCG step over a
  2^20 modulus had such poor high bits that `floor(h * 4)` returned zero
  for every cell on the map -- every puddle landed in the same group.
  Replaced with a properly spread mixer, which also means grass, tree
  heights and canopy leaves vary more than they have been.

## 1.12.3

- **Fixed: lone clouds sitting on the horizon.** The decks were flat
  sheets, and a flat sheet seen from the ground sinks toward the horizon
  as it recedes -- so its far rim ended up level with the skyline and
  single cloud blobs appeared perched on the mountains. The decks now
  curve upward with distance, lifting their rim about nine hundred units,
  which keeps the whole sheet overhead where cloud belongs. It is also
  what the real sky does: you never see a cloud's underside meet the
  horizon, because the horizon hides it.

## 1.12.2

- **The sun bloom is removed.** Three attempts, three different failures,
  and the last one was the honest answer: this renderer discards any
  texel under half alpha and draws the rest opaque, so it cannot express
  a glow at all. Dithered, the bloom became a stippled ring; undithered,
  a solid rectangle. Doing it properly needs alpha blending, which means
  patching Dramatic Shape's shader -- the one thing this mod has
  deliberately refused to do. Better removed than left looking broken.
  The SUN BLOOM option is gone with it.
- **Small lights are solid now, not stippled.** Fireflies, gnats, lamps
  and lit windows were soft discs, and dithering an eight-pixel falloff
  produces noise rather than light -- those were the odd blobs. They are
  drawn as solid little discs whose EDGE DARKENS instead of fading, so a
  firefly reads as a small bright dot, which is the entire point of one.

## 1.12.1

- **Every generated sprite is now dithered, and they look right for the
  first time.** The voxel shader discards any texel under half alpha and
  draws the rest fully opaque -- it cannot express a soft edge at all.
  Every glow, puff, drip, insect, cloud wisp and the rainbow was built as
  a soft gradient, so each was being reduced to a hard-edged blob: the
  sun bloom in particular arrived as a pale rectangle in the sky. They
  now use ordered dither, the technique the hardware this game came from
  used: partial coverage becomes a stipple of fully-on and fully-off
  texels, which survives the discard and looks like Game Boy art rather
  than a mistake.
- **Fixed: the lightning flash was drawn with no texture**, so a
  2400-unit quad wore the map atlas across the sky. It uses the plain
  white pixel like every other untextured surface.
- Both harnesses now assert that no generated texel has partial alpha.

## 1.12.0

- **Fixed: no rainbow after the rain.** The bow's art is a half-disc
  springing from the BOTTOM edge of its texture, but a quad is positioned
  by its CENTRE -- so translating to the height of the arc's feet buried
  five hundred units of bow below the ground. It is now centred half its
  own height above the feet.
- **Fixed: the sun bloom, properly this time.** 1.11.1 corrected the
  degrees-versus-radians reading but still used the sun's TRUE elevation.
  Dramatic Shape hangs the visible disc on a squashed arc (about a
  seventh of the true angle, because the real noon sun would sit far
  above any frame), so the bloom was floating roughly a thousand units
  above the sun you can actually see. It now uses the same placement the
  disc does.
- **Fixed: invisible puddles.** They were drawn as small blots at a
  quarter shade -- present, and impossible to see against the ground.
  Bigger, brighter, a paler sheen and rather more of them.
- **Lamplight (prototype).** Light is flood-filled through the cell grid
  from every doorway on a map, so it spreads round corners and STOPS at
  walls -- occlusion is inherent rather than computed. Drawn as a warm
  floor pool that falls off with distance, plus a glow at each lamp.
  Active after dark outdoors and in unlit caves at any hour. No shader
  patching and no re-meshing of Dramatic Shape's chunks. New LAMPLIGHT
  toggle.

## 1.11.4

- **The cloud layer no longer ends in a straight line.** Each deck was a
  single quad, and a quad has an edge -- which read as a hard cut across
  the sky. Decks are now built as concentric bands of cells drawn with
  falling alpha, so the cloud thins into the blue instead of stopping,
  and the plane is nearly three times wider (7200 units) so the fade
  happens well beyond anything you can resolve. UVs run continuously
  across the bands, so the cloud pattern itself does not break at a band
  edge.

## 1.11.3

- **Works with newer Dramatic Shape builds** (reported on 1.63). The
  scene splice matched a five-line block around the terrain draw, and any
  rewording of those lines made the patch refuse outright. It now falls
  back to the terrain draw itself -- one line, whatever its arguments --
  and splices around that, which should survive most future edits. The
  boot log says when it has used the fallback.
- If even that is unrecognisable the patch still refuses and writes
  nothing, and now asks for the version number in the message.

## 1.11.2

- **Fixed: the planes were invisible, not absent.** They were drawn at 26
  units, at 620 up and 2200 away -- about half a degree across, which is
  one pixel. Sizes are angular, not absolute, and I had picked them by
  eye against nothing. Planes now fly lower and nearer at 95 units, the
  blimp at 230, and contrail puffs are broad enough to read as a trail
  rather than as dust. A test now asserts a plane is drawn large enough
  to see at the range it flies.

## 1.11.1

- **Fixed: the sun bloom did nothing.** `DayNight.bodyAt` returns the
  sun's bearing and elevation in DEGREES -- the engine's own shadow code
  converts them with `math.rad` -- and this mod was treating both as
  radians. The bloom was therefore hung at an arbitrary bearing, at a
  fixed height, usually below the horizon. It now follows the sun both
  around the sky and up it, and is bigger with it.
- **The rainbow was pointed by the same broken reading**, so its
  anti-solar arc was anti-nothing. Fixed, and while there: much larger
  (it spans the sky rather than sitting in it), far softer -- the bands
  blend into one another instead of stepping, the whole thing peaks under
  half opacity, and both rims dissolve -- so it reads as light hanging in
  the air rather than a painted arch.
- **Fixed: chimney smoke never appeared.** Buildings were found by asking
  for tiles classified `roof`, and the real game classifies none that way
  -- the debug HUD had been quietly reporting "0 chimneys" all along. A
  building is now found by its shape instead: a solid two-by-two block of
  unwalkable cells, which a tree or a fence post is not. Lit windows use
  the same detection, so those should appear now too.

## 1.11.0

- **Thunderstorms**, rare and large. About one shower in seven arrives as
  a storm: heavier, faster rain, and the cloud decks darken and thicken
  into thunderheads. **Forked lightning** strikes at distance -- a jagged
  trunk with two or three forks peeling off it, drawn in code, flickering
  down in steps rather than dissolving.
  - *On flashing light:* strikes are far apart (a hard four-and-a-half
    second floor between them, never in bursts), the screen brightening
    is partial, low-alpha and painted at the horizon rather than over the
    whole view, and it eases away instead of cutting. LIGHTNING can be
    turned off on its own -- the rain and thunderheads stay.
- **Puddles.** Rain fills them over half a minute and they dry slowly
  afterwards, hashed so the same lane puddles in the same places. Dark
  and wet rather than mirror-bright: there is no reflection to give them,
  and a fake one would look worse than a wet patch. New PUDDLES toggle.
- **Sun bloom**, the restrained half of a lens flare: a soft glow at the
  sun's own angle, so it swells as you turn toward the sun and is absent
  when you turn away. No streaks, no ghosts down the screen. Dimmed by
  cloud, and much dimmer under a storm. New SUN BLOOM toggle.
- **Fixed: the cloud layer could stop drawing entirely.** A local named
  `w` for wind speed shadowed the weather table of the same name, so
  `w.storm` indexed a number and threw inside the draw guard -- silently,
  because that is what the guard is for. Caught by a new test that
  asserts the decks actually reach the screen.

## 1.10.0

- **Wind on the tall grass.** The blades are split into four meshes by
  position and each is drawn through a shear that leans its tops over and
  leaves its roots where they are, on its own clock -- so a gust travels
  across a field rather than the whole meadow nodding in unison. A slow
  wave plus a faster flutter, so it never settles into an obvious sine.
  WIND: OFF / BREEZE / GUSTY.
- **A ground flock.** Now and then a scatter of small birds settles on
  open ground and pecks about -- and holds its nerve until you get close,
  then flushes all at once, bursting apart and climbing out of sight.
  They only land where there is actually room (a clear patch of walkable
  cells, checked when they arrive), and they wear the same derived frames
  as the sky flocks. New GROUND FLOCK toggle.

## 1.9.0

- **Insects.** Swarms of gnats hang over patches of tall grass by day and
  under the forest canopy at any hour. A swarm is a *column* of air that
  insects orbit rather than a scatter of independent motes, which is what
  makes a cloud of them read as one thing hovering over one spot. New
  INSECTS toggle.
- **Rainbows.** When a shower passes, a bow fades up opposite the sun --
  anti-solar, which is where a real one is, so turning your back on the
  sun finds it and facing the sun does not. Seven bands, red on the
  outside, soft at both rims. It holds for a minute and fades out, and
  never appears at night. New RAINBOWS toggle.
- The weather clock now publishes its state, so the sky layer knows the
  moment a shower ends.

## 1.8.4

- **Works with Dramatic Shape forks as well as the standard mod.**
  Tested against absol89's battle-art build, which is based on Dramatic
  Shape 1.3.0 and has neither a `Water` module nor a first-person rig.
  - The require splice now tries a list of anchors rather than assuming
    one line exists, falling back to the `Voxel3D` require that every
    build seen so far has.
  - The payload modules no longer require the first-person rig at load
    time. On a build without one they fall back to a blend of zero, which
    means the diorama cutaway view -- exactly right for a build that has
    no first person to be inside of.
  - The jump, head bob and doorway step are skipped silently where there
    is no rig to splice them into, instead of failing the patch.
  Nothing about the standard mod's behaviour changes.

## 1.8.3

- **A pipeline census on the debug HUD.** It lists every registered
  render pipeline and whether the engine still considers it eligible.
  The engine retires a pipeline for the whole session the moment one of
  its stages throws, and some mods -- Wilds of Kanto among them -- run
  their simulation from a pipeline's present stage, so "registered but
  not eligible" distinguishes "switched off" from "died and stayed
  dead". Turn DEBUG HUD on and read the PIPE line.

## 1.8.2

- **Compatibility with Wilds of Kanto.** Every draw this mod makes now
  sits inside a `push("all")`/`pop()` guard. They all change graphics
  state -- colour, alpha, depth mode -- and were relying on setting it
  back by hand, which does not happen if a draw throws partway through.
  The leaked state then applied to everything drawn AFTER us in the same
  frame. Wilds of Kanto's wild Pokemon are drawn by Dramatic Shape's own
  cast pass, which runs after this mod's geometry, so a stray alpha from
  us would make their sprites invisible while ours looked fine.
- The guard is headless-safe, and a regression test forces a draw to
  throw partway through and asserts the state guard stays balanced.

## 1.8.1

- **The forest canopy now melts for the diorama rungs.** It was drawn
  whole in every view, so from outside first person you were looking at
  the top of a lid. It now opens a clearing around the player and drops
  the near rim walls, the same way the interior ceiling does, and closes
  again when you dive back into the head.
- The umbrella's pole runs the full height of its frame and the whole
  thing hangs lower, so NPCs carry it at hand height, slightly off to one
  side, rather than balancing it on their heads.

## 1.8.0

The weather-and-wildlife release. Everything below is presentational:
collision, movement, ledge rules, triggers, encounters, scripts and saves
remain untouched.

### Outdoors

- **A painted horizon** wrapped around the world at distance, centred on
  the player so it never gets closer.
- **Layered clouds**: three decks at different heights, tile scales and
  drift speeds, so the parallax between them reads as depth. They thin
  out after dark.
- **A night sky**: stars at four brightnesses over a faint nebula, two
  dozen of them twinkling on their own clocks, and the occasional
  shooting star. Fades in at dusk rather than snapping on.
- **Birds**: flocks of distant flyers in loose echelon with synthesised
  wingbeats, recycling around you as you travel. About one flock in forty
  is a rare flyer, alone and higher than the rest. They wear frames
  derived on your own machine from your own cache -- no sprite ships in
  this mod.
- **Aircraft**: a rare high plane laying a contrail, and a very
  occasional blimp.
- **Rain** on its own weather clock, with every NPC putting up a little
  pixel umbrella while it falls.
- **Lit windows** after dark, **chimney smoke** by day, and **fog** over
  Lavender Town.

### Ground level

- **Tall grass with varied height**, so encounter cells look like
  somewhere things live rather than a lawn.
- **Trees at varied heights**, so a wood has a skyline. Buildings are a
  different class and are untouched.
- **A leafy forest canopy** in two layers -- a gapped lower one and a
  solid upper one, so light wells show sunlit leaves rather than void --
  with the wood walled at its rim. Foliage tiles are chosen by measured
  greenness, not by frequency.
- **Sun shafts** leaning through the canopy.
- **Particles**: seeds kicked up as you move through grass, cave drips
  with a splash, fireflies after dark, falling leaves, interior dust,
  spray at the water's edge, and the occasional distant rustle with
  nothing attached to it.

### Caves

- **Cave darkness** on the floors the engine marks unlit, with **Flash**
  pushing the walls back rather than simply switching the dark off.

### Movement

- **Head bob and sway**, driven by distance walked so they stay locked to
  your feet and stop dead when you do.
- **A doorway step**: the eye dips and leans through a warp instead of
  cutting.

### Under the hood

- **No restart needed.** The patch now applies before Dramatic Shape
  loads, so installing, updating and removing all take effect
  immediately.
- The debug HUD is off by default; turn on DEBUG HUD to see what the
  patcher and each effect decided.

## 1.7.1 — initial release

First public release. Interiors get walls, ceilings and doors; the
outdoor world gets a painted horizon; ledge hops get weight; the diorama
rungs get an optional Sims-style cutaway.
