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
  fixture, and local source-tested adapters for all three target hosts.
- Added a fail-closed machine-readable stable-release ledger and signed-tag
  packaging gate.
- Moved legacy art and audio under a separate rights notice.

This alpha is not a stable release. Certified adapters, real rendering,
device evidence, rights evidence, and reproducible artifacts remain gates.

## 1.57.2

- **THE INSTALLER STOPS CHOOSING A BASE.** It cannot see which family
  member the launcher ENABLED: a disabled Dramatic Shape folder beside
  a live Dramaless is indistinguishable from the save directory, and
  1.57.1 kept patching the dormant sibling while the live one went
  bare -- which is why the Discord hand-hack worked on a machine with
  one base installed and this mod failed on a machine with two. Every
  Dramatic Shape descendant on disk is now managed, each under its own
  per-base state; patching a disabled copy is inert by definition, so
  the live one is always among the patched. The boot log names each.

- **PAYLOADS SELF-LOCATE.** The copy actually executing was loaded
  from the live base by definition, so Flora and Ceiling now read
  their own chunk path and claim the runtime globals (asset dirs, the
  patch base) for that folder -- settling the horizon art and sound
  paths however many siblings were patched. The ambience loader's
  fallback list also gains DRAMALESS_SHAPE and TERRARIUM, matching
  the Discord finding.

## 1.57.1

- **DRAMALESS SHAPE ACTUALLY INSTALLS.** Three compounding blockers,
  all diagnosed from one screenshot. (1) The tested-versions gate did
  not know "1.6.2.ST": fork-suffixed numbers now pass when their
  leading x.y.z is a tested base. (2) State was one global file, so
  the old Dramatic Shape install's "patched" state, applied to a base
  this mod had never touched, shunted boot into the REMOVAL path --
  teardown noise, no apply, nothing loaded. State is per-base now; a
  legacy file follows its own base (the one bearing the splice mark)
  and is cleared from any other. (3) The spliced requires were bare,
  so one failing payload would have taken VoxelScene down whole: the
  splice now loads each payload guarded, degrades a failure to a
  no-op, and prints the actual error on that module's HUD line.

- On a fresh fork install the status line announces the detected base
  and version. If a payload still refuses to load under a fork, its
  HUD line now says exactly why.

## 1.57.0

- **HEAD BOB IS STANDALONE.** JUMP FEEL scales the hop-derived motion
  only; the walk bob no longer requires it. With the jump row OFF the
  hop terms zero out and the bob walks on.

- **DEPTH BLUR THROUGH THE FRONT DOOR.** Forcing TiltShift.level
  directly lost every frame to the engine, whose pipeline record
  re-asserts the persisted option through update() -- which is why
  1.56.x showed nothing. The mod now calls Pipelines.setLevel
  ("tiltshift"), the documented engine API the T-SHIFT row itself
  uses, on transitions only, remembering the player's own setting and
  restoring it on leaving first person or turning the row OFF.

- **FORK COMPATIBILITY.** DRAMALESS_SHAPE (Stahltier's fork of 1.6.2,
  with TERRARIUM merges) and TERRARIUM join the known-id list beside
  the battle-art fork, and a second detection pass recognises ANY
  Dramatic Shape descendant by anatomy -- a lib/VoxelScene.lua that
  requires Voxel3D -- whatever it renamed itself to. The splices'
  multi-anchor fallbacks (built for the 1.3.0-era battle-art build)
  carry the rest; a fork install announces itself on the status line.
  Wilds of Kanto needs nothing: it adds entities and touches none of
  the files this mod splices, so the two coexist by construction --
  its overworld Pokemon simply ride the same sprite pipeline.

- **THE BOOT-TWICE RITUAL ENDS.** Payloads register their live module
  tables (and the V loader) in _G.__ds_live; after any refresh write,
  the installer compiles the new source against the same V and merges
  it into the table every caller already holds. One transitional
  double boot remains for THIS update (running sessions predate the
  registration); every update after lands live.

## 1.56.2

- **SPLASHES ARE AN OUTDOOR EFFECT.** Interior tile art can match the
  shore scan's pattern (a Viridian house counts four "shore" cells),
  so the splash fountain now requires the outdoor flag rather than
  trusting the scan indoors. The scan itself is untouched.

- **THE STUB SUSPECT, AND A LINE OF TRUTH.** Flora resolves the
  first-person rig once at module load; if that require raced the load
  order and failed, Flora holds a placeholder whose FOV assignment
  goes nowhere and whose blend reads a constant 0 -- FP FOV and DEPTH
  BLUR would both do exactly nothing while every other feature works,
  which is the reported shape. applyLens now retries the require each
  frame until the real rig arrives. And the FLOR debug line grows a
  lens report -- rig-or-STUB, both row values, TiltShift presence, the
  live FP blend, and the bob's own state (envelope, odometer, jump
  multiplier, or row-off) published from inside the eye expression --
  so the next screenshot names the failing link outright.

## 1.56.1

- **THE CEILING MODULE ACTUALLY SHIPS.** Ceiling.lua only refreshes on
  installed setups when its payload-version header RISES -- and no
  ceiling change since windows arrived ever bumped it, so 1.53.0
  through 1.55.0's windows, placement fixes, grain, beams and roses
  were all silently discarded at every boot ("ceiling patch active"
  is that path's message). The header now reads 24 and the whole
  backlog lands at once. No code changes in this release; the code
  was fine, the courier wasn't.

- **BOOT TWICE.** Module refreshes are written during boot, after the
  engine has loaded the old copies -- the mod's own "changes complete
  on next boot" notice has always meant exactly this. First boot
  writes; second boot runs. This applies to the head bob fix, FP FOV
  and DEPTH BLUR from 1.56.0, which are most likely already on disk
  and one boot from alive.

## 1.56.0

- **HEAD BOB WORKS.** The toggle read `me.moving`, a field the rig's
  entity never carries in this engine -- always nil, so the bob never
  engaged. It now runs off the module's own distance-driven sources,
  maintained a screen above it all along: phase from the odometer,
  amplitude from the walk ease. Locked to the feet, immune to
  framerate, stops mid-stride when you do -- the file's stated design,
  finally wired to itself.

- **FP FOV.** NARROW (55) / NORMAL (65) / WIDE (75) / ULTRA (85). The
  rig folds FirstPerson.FOV into its camera blend every frame, so the
  row assigns it and that is the entire feature.

- **DEPTH BLUR.** The engine's tilt-shift is a finished depth-of-field
  pass whose geometry is exactly right in first person: the sharp
  mid-band holds the played space while the far top and near ground
  soften. The DEPTH BLUR row (OFF/1/2/3) borrows it by forcing the
  level while the FP blend is up, remembering the engine's own T-SHIFT
  setting and handing it back the moment first person ends or the row
  goes OFF. No splice: two per-frame writes into machinery the engine
  already runs.

## 1.54.2

- **WINDOW PLACEMENT AS SPECIFIED.** Never on the wall faced on
  entering (the north run: that is where the game stations its
  objects, and a pane behind a bookcase reads as a mistake). Side
  walls allowed; the front-door wall allowed, but never beside the
  door -- the existing door-spacing rule covers that. Density rises
  from one eligible cell in three to one in two, since corners and
  door clearance already shorten the side and door-wall runs, and
  the north geometry from 1.54.1 stays in place as a dead path.

- **WINDOWS ALWAYS REPORT.** The ceiling debug note now states the
  window count even at zero, and says "windows: NO IMAGE" if the
  procedural pane texture failed to build -- so if a room still shows
  none, one screenshot of the note tells us whether placement or the
  texture is at fault.

## 1.54.1

- **WINDOWS APPEAR NOW.** 1.53.0's back-wall exclusion was aimed at
  the wrong wall: it excluded the north-void face -- which in a Gen 1
  interior is the PRINCIPAL wall, the one the camera looks at and the
  one the 2D art itself draws windows on. With that gone, and corners
  and doors eating the short side runs, no building had any windows.
  The excluded direction is now the SOUTH wall -- the street-facing
  run the door passes through, the true interior face of the
  building's front-door side, which the player almost never faces.
  The north wall also gets its own axes and pane geometry (it had
  neither, having never been reachable). Door spacing, edge rules and
  poster avoidance are unchanged.

- **A HEAVIER LEAF FALL.** Pick rate 16 -> 34 per second and the
  particle pool 220 -> 300, so a grove now sheds a proper drift
  without recycling the rain or the fireflies early.

## 1.54.0

- **CRICKETS AFTER DARK.** A night bed that plays OUTSIDE ONLY, and
  only where the outdoor beds play -- towns, cities and routes -- laid
  over whichever of the two is up. Night is read from the same
  palette-derived test the street lights use, so the crickets arrive
  and leave with the lamps.

- **RAIN YOU CAN HEAR.** A rain bed keyed to the same flag the
  droplets, puddles and umbrellas already run on, faded in with the
  weather and out with it, a shade louder than the place bed so
  weather reads over place. Both new beds ride the AMBIENT SOUND
  level, its OFF switch, and the crossfade ramps; both fall silent
  indoors.

## 1.53.1

- **SPLASHES at the waterline.** Roughly once a second somewhere along
  the nearby shore, one spot throws a small fountain: five to eight
  droplets, half foam-white and half a new water-blue, fanned in a
  ring and pulled back down by the same ballistics the spray already
  obeys. Rides the existing shoreline scan, the particle pool, and the
  PARTICLES toggle; with the shore-lapping bed underneath, the water's
  edge now moves and sounds like one.

## 1.53.0

- **WINDOWS.** Interior walls now carry panes: a procedural 12x14
  window texture (dark frame, cross mullion, sky-blue glass with a
  corner highlight) hung the way the posters are hung, a hair proud of
  the wall and facing the room. Three exclusions, by design: never on
  the back wall (the face whose void is north), never beside a door
  (not on a door cell, not through one, not one cell along the wall
  either side), and never at a wall's edge (both along-wall neighbours
  must be standing wall with the void on the same side, so no pane at
  a corner or on a one-cell stub). Windows claim their cell before the
  posters hang, so the posters' no-neighbours rule keeps pictures away
  from every pane. Organic interiors -- caves, the forest, the tunnels
  -- get none, on the same list that keeps pictures off their walls.
  Its own WINDOWS toggle row, on by default.

- **FOOTSTEPS BY SURFACE.** Rock underfoot through the caves and route
  tunnels, boards in every built interior, both on cell entry like the
  grass rustle. Outdoor non-grass steps stay silent: there is no dirt
  take, and silence beats a wrong sound on every step of a journey.
  FOOTSTEPS toggle row.

- **DOORS ON THE THRESHOLD.** The outdoor flag flipping across a map
  change is a doorway crossed. Marts, Centres and lobbies ring the
  shop bell; caves, tunnels and the forest have no door to sound;
  every other interior gets the house door -- the interior side names
  the sound whichever way the player is going. DOOR SOUND toggle row.

- **THE SHORE LAPS.** water.mp3 is a bed apart from the crossfade: its
  volume follows the player's distance to the nearest shoreline cell
  (full a stride from the waterline, gone past 130 units), riding the
  AMBIENT SOUND level and its OFF switch like the other beds.

## 1.52.0

- **BUILDING BACKS is retired for now.** The plain-wall patch on north
  faces misfired on several house drawings and in places covered the
  door itself. The option row is removed and the config bridge forces
  it off; the builder stays in Flora for the day the face detection is
  rebuilt.

- **AMBIENT SOUND is a menu row.** OFF / LOW / MID / HIGH in the mod
  options, defaulting to MID (0.62) -- noticeably hotter than
  1.51.1's fixed 0.35, which playtested too quiet under the game's own
  music. LOW is the old level; HIGH is 0.92. Pre-1.52 saves holding
  the old boolean are read correctly.

- **GRASS STEPS.** Stepping into a tall-grass cell rustles, the two
  takes alternating so back-and-forth pacing never stutters one
  sample. Cell ENTRY is the trigger -- the same edge the encounter
  system rolls on -- so it sounds like what it is: a step into the
  grass. Its own toggle row, on by default; the files ride the same
  install pipeline as the beds.

## 1.51.1

- **The last path ghosts are gone: base entries are now MAP-KEYED.**
  The 1.50.2 base gate asked "was this map's stamp ever meshed?" --
  but the answer table was keyed by bare local position, and two maps'
  cells at the same local coordinates shared one key. A Celadon path
  cell whose own stamp was never expanded could borrow a neighbouring
  map's entry and keep its stem until a local rebuild caught up --
  which is exactly the row that stood on the path and vanished as you
  approached. The mesher splice now writes `mapid:mx|mz` and every
  reader asks with the same key, so the collision is impossible. The
  installer upgrades the old splice in place (strip to stock,
  reapply); reboot once and every map meshes fresh under the new keys.

- **The leaf shower is much heavier.** The spawn is a burst loop (the
  same shape as the grass seeds), the pick rate is up from 3.4 to 16
  per second, and the particle pool grows from 150 to 220 so a heavy
  shower cannot starve the rain, smoke or fireflies. Each leaf is one
  textured quad from a shared 8x8 image -- the cost is what the rain
  already pays.

- **The silent ambience now explains itself.** The beds failing to
  load was swallowed by a pcall, so 1.51.0 shipped a feature nobody
  could hear. The loader now tries every plausible install directory
  (the posters path, the backdrop's own folder, both historical mod
  folder names) and both source types, and the FLOR debug line grows
  an `amb:` entry -- the live bed and its volume when working, or the
  load error when not, so the next screenshot says exactly what went
  wrong.

## 1.51.0

- **The lifted trees shed green leaves.** A new particle rides the
  forest leaf's tumble physics but wears a fresh green flake, and lets
  go from the crowns of the stem-bearing trees themselves: spawns pick
  a random cell from the trunk registry, so where the trees are is
  where the leaves fall, released from each crown's actual height
  (base + lift). Boulders and far cells are discarded picks, which is
  what keeps the shower gentle.

- **Ambient sound beds.** Four looping beds -- cave, forest, town,
  route -- crossfaded as you move between areas, faded out (not cut)
  indoors. CAVERN and FOREST classify by authored tileset; outdoors,
  TOWN/CITY map ids take the town bed and everything else is a route.
  The mp3s install into Dramatic Shape's lib folder alongside the
  poster sheets and stream from there, so a missing file costs its bed
  and nothing else. A once-only love.update watchdog fades everything
  out if the voxel mode stops drawing, so dropping to the 2D pipeline
  never strands a loop playing. Set `ambience = false` in the config
  to switch the beds off. (The whole feature hangs off an existing
  table: Flora's main chunk sits exactly at Lua's 200-local cap.)

## 1.50.3

- **Stems run across map boundaries.** Same cure as 1.50.0 gave the
  mountain peaks: a neighbour's rounds draw lifted (its own mesh bakes
  the lifts) but stems were built for the current map only, so a
  route's trees floated in the distance until you crossed over. Each
  neighbour's stems now build from its own registry -- same gates,
  same builder, cached per map id -- and draw at the neighbour's
  offset under its haze. The 1.50.2 BASE GATE does the seam hygiene
  for free: neighbours are meshed body-only, which skips every ring
  stamp before expansion, so a neighbour's ring cells never earn base
  entries and no stem grows outside its body.

## 1.50.2

- **The seam ghosts on pathways are gone -- and only they are.** The
  registry publishes a cell when Structures CREATES a stamp, but the
  mesher decides later whether the stamp is ever DRAWN, and it discards
  ring stamps wholly buried under a connected neighbour's body
  (`containedInMask`). Those discarded stamps kept their registry
  entries, so bare trunks stood on the neighbour's walkway at every
  connection. Two gates now make a stem prove its canopy exists, both
  replicas of facts the mesher already established, so neither can
  strand a drawn round: the MASK GATE re-runs the mesher's own
  containment test (same rects, same not-over-body condition), and the
  BASE GATE requires the stamp's `__ds_round_base` entry, which is
  written only inside the mesher's quad expansion. Base entries land as
  the async full build does, so the trunk cache watches the confirmed
  count and rebuilds as they arrive -- late stems pop in with their
  trees, exactly as the trees themselves do.

## 1.50.1

- **The floating rounds along map edges have their stems back.** The
  stemless ones were all in CONNECTION BANDS -- the two cells beside
  any connected edge, where 1.45.7 suppressed every support as a
  tourniquet for the seam ghosts. The ghosts' real causes were each
  fixed properly afterwards (the shared-object registry, group
  supersession, and supports rooted at flat ground under terraced
  stamps), so the band rule had become pure collateral: it starved
  legitimate border rows of their trunks while the walkability,
  tile-union and real-stamp gates carried the actual protection. The
  rule is retired for supports; the walkable-liar seam cells still
  build nothing, and the harness asserts both directions.

## 1.50.0

- **The folder and id are `ds_fp_ceiling` again** (singular -- the
  1.41.0 pluralisation is reverted). If you installed any 1.41-1.49
  build, delete the `ds_fp_ceilings` folder; upgrades from 1.40.x or
  earlier just overwrite in place. The launcher once more matches
  Dramatic Shape's old conflict flag natively on archived 1.6.1/1.6.2
  copies, which is the behaviour this mod enforced by hand anyway.

- **Ridges run across map boundaries.** MOUNTAIN PEAKS built only the
  current map, so the massif you stood in went flat two maps over --
  the most immersive feature undoing itself at every seam. Each
  NEIGHBOUR map's peaks are now built from its own cells (same gates,
  same builder, cached per map id) and drawn at the neighbour's offset
  under the same distance haze as its grass -- the ridge continues into
  the blue instead of vanishing. Connection bands still keep both sides
  of a seam corridor clear, so the crossing itself stays open.
- **HEAD BOB restored as a toggle, OFF by default.** Its removal was
  the most requested reversal this mod has had; its presence was the
  most complained-about thing it ever did. Both crowds were right about
  themselves. Off (the default), the camera responds only to events --
  hop, landing, doorway -- exactly as since 1.3x. On, a gentle sine
  rides each step, eased in over a few frames and eased out to exactly
  zero on stopping, and it stands down during hops so the two never
  fight. The old guarantee has a test: with the toggle off, a moving
  player's eye does not move.

## 1.49.0

The upstream Dramatic Shape repository was deleted by its author;
absol89's fork is now the mainline. This release moves with it.

- **absol89's fork 1.7.6 is fully supported.** Three things needed
  doing, each verified by the fork harness against the actual release:
  - 1.7.6 renamed the mod id to BATTLE_ART_VOXEL_FORK; discovery now
    accepts either identity.
  - 1.7.6 is whitelisted, and -- unlike the old 1.3.0-era fork -- it
    SHIPS the FirstPerson rig, so the jump payload installs there too.
  - The fork's sources mix LF with Windows-pasted CRLF regions, one of
    them exactly around the mesher's stamp expansion. Every anchored
    find written with \n silently misses a line ending \r\n -- the
    silent-no-op failure class -- so every engine source is normalised
    on read before any splice looks at it.
  All previously supported upstream versions (1.3.0-fork through 1.7.0)
  remain supported for anyone running archived copies.
- **JUMP BUTTON: Ledge Leap 1.0.1 incorporated**, design intact and
  credited: Space (or J / L-CTRL) and pad Y (or X) hop a faced ledge
  from ANY side -- including up -- via the engine's own forced two-cell
  walk, arc and chirp; anything else gets a bounce on the spot. The arc
  rides hopFrames, which the first-person camera already turns into
  vertical lift, so the button and JUMP FEEL compose automatically. New
  JUMP KEY and PAD BUTTON rows (with OFF); if you run the standalone
  Ledge Leap alongside, set these OFF or remove one copy -- two
  listeners means two hops per press.

## 1.48.0

- **FAST CHUNKS (new toggle, on): geometry stops appearing in front of
  you.** The "draw distance" was never a distance -- Dramatic Shape
  cooks chunk meshes inside a per-frame time budget, and the 5ms idle
  slice could not keep pace with a walking player. The slice is doubled
  while the option is on, read from the config bridge at load, so an
  orphaned install reverts to stock. Costs a few ms per frame while
  chunks stream; turn it off on weak hardware.
- **Buildings refuse the massif.** The flooded second material now
  vetoes any candidate touching a roof-class cell or a door -- the Poke
  Center wore a summit for three cells of flood reach. Authored rock ids
  are immune; only flooded cells must prove themselves.
- **Cave mouths get a LINTEL.** A door cell flanked by cluster rock on
  opposite sides is a cave entrance; skipping it (doors are walkable)
  notched a slot of sky through the massif over Mt. Moon. Rock now
  bridges across, its underside one band above the wall top so the
  doorway stays open, its summit never overtopping its shoulders, with
  a ceiling face so the pass reads solid from below.

## 1.47.1

Three refinements to MOUNTAIN PEAKS from the first playtest.

- **The second material joins the massif.** The same rock wall often
  runs two drawings -- the dark check and the light orange -- and only
  the authored pool ids erupted. Any contiguous upright, unwalkable cell
  within three cells of a pool seed now joins: the cluster vouches for
  it, whatever its tile id. A building cannot join -- walkable ground
  separates it, and even direct wall contact leaks at most three cells
  before the reach cap bites.
- **Taller and jagged.** Distance step 2 -> 3 bands, cap 7 -> 12
  (hearts near 200px over the wall), per-cell jitter widened to four
  bands, and roughly one cell in seven throws a three-band SPIRE past
  its neighbours -- so ridgelines read as rock, not battlements.
- **Peaks fade in** over about half a second on map entry, on the same
  colour+alpha path the fog uses -- a massif materialising instead of
  teleporting. (Trunks appearing with their bushes as chunks stream is
  the engine's own behaviour: the supports pop exactly when Dramatic
  Shape's bushes do, never alone.)

## 1.47.0

- **MOUNTAIN PEAKS: the clustered rock rises.** The route rock is
  authored -- on OVERWORLD, Dramatic Shape's own tables pin the mound
  drawing as `wall = { 2, 36 }` ("the rock pillar, the plateau body").
  Where those cells run in clusters of four or more, further courses of
  the same rock now stack on top, rising toward the cluster's interior:
  each cell's height grows with its BFS distance from the cluster's rim
  (plus a per-cell jitter so ridgelines are not staircases), up to seven
  extra courses at the heart. Every face and cap is textured with the
  cell's own four subtiles, band by band, so the drawn rock simply
  continues upward at true scale.
  - The full gate stack applies, in the order the ghosts taught:
    authored tile id AND authored upright class AND not walkable AND
    outdoors AND not in a connection band. No stamps, no registry --
    this derives from stable map data alone, so none of the seam
    machinery is even involved.
  - Lone pillars and pairs stay stock (cluster minimum four); indoor
    maps are untouched; a new MOUNTAIN PEAKS toggle (on) turns it off
    entirely.
  - Honest limits: heights root at the wall's authored top, so rock on
    elevated terraces may need the terrain-base treatment the trees got
    -- one playtest will say. And if this art pack binds the orange
    check to different ids, the pool is a one-line table edit
    (MOUND.PEAK_TILES), exactly like the tree/boulder swap was.

## 1.46.0

- **BUILDING BACKS: the false-door patch is now real brick.** Two
  faults, both visible in one department-store screenshot:
  - The cover stretched ONE 8px tile over the 16px cell -- brick at
    double size, a smear that matched nothing around it. The patch is
    now FOUR quads, each sampling the matching quadrant of a donor cell
    along the same back wall, so the courses line up with the brick on
    either side and the cover vanishes into it.
  - A double-wide entrance spans two cells but the engine flags only
    the warp cell, leaving its twin as a black column beside the patch.
    If a solid, unflagged neighbour's body row carries the same art as
    the door column's, it is the other half of the doorway and is
    covered too. A false positive on a plain wall is harmless: it gets
    covered with its own matching brick.

## 1.45.8

- **The ghosts were never headless -- their heads were upstairs.
  Supports now root at each stamp's TRUE terrain base.** The nearest-
  cell diagnostic plus two screenshots finally showed canopies floating
  far ABOVE the bare stems: Dramatic Shape bakes each cell's terrain
  height into the stamp template, so a bush on a ledge terrace sits at
  terrain + lift -- while every support rose from flat y=0. On flat
  ground they met perfectly (the "PERFECT" trees); on Kanto's terraced
  route mouths -- which is exactly where connections cluster, hence
  every seam correlation -- the stem stopped at ground level and its
  canopy floated at terrace height, reading as a ghost. The mesher
  splice now publishes each lifted stamp's true base (the minimum of its
  template's own geometry), and every trunk, stack and branch roots
  there. Upgraded in place on old installs, with a harness scenario for
  the upgrade and a terraced-stamp test that must touch its terrace
  exactly.

## 1.45.7

- **The seam ghosts, by the numbers: connection bands are now support-
  free.** The nearest-cell diagnostic named the ghosts as `12|0 12|1
  9|0` on ROUTE_1 -- the connection overlap rows. Adjacent maps BOTH
  author the rows where they join; each map's copy of that band contains
  round, unwalkable tiles, truthfully -- so every earlier gate passed --
  but the band's presentation belongs to whichever side the player is
  on. On any edge that has a connection, supports are no longer built
  within two cells of that edge or in the ring beyond it. Edges without
  a connection -- the border tree walls -- keep every trunk, as before.
  The harness models the seam exactly: round ids, unwalkable, in the
  band, and must stay bare, while the unconnected-edge ring tree keeps
  its trunk.

## 1.45.6

- **Diagnostic release.** The FLOR line now names the three built
  support cells NEAREST THE PLAYER, with kinds -- `near:12|7b 13|7t
  14|7b`. Stand inside a ghost cluster and the HUD identifies the exact
  registry cells producing it, plus which kind they resolved to. One
  screenshot from inside the ghosts turns the remaining archaeology
  deterministic. Nothing else is changed; the trees, boulders, stacks
  and heights are untouched.

## 1.45.5

- **THE ghost bug, found by its own confession: the registry was keyed
  by a map object the engine REUSES.** The new HUD diagnostic showed the
  identical tree/boulder split and the identical boulder cell keys on
  two different maps -- impossible unless the bucket was shared. It was:
  the engine keeps ONE map object and mutates it on every transition, so
  "keyed per map" merged every map into a single pot, and crossing a
  connection rained the previous map's cells onto the new one as
  indiscriminate ghost stems -- wooden stems around boulders, supports
  on paths -- until remeshes caught up. Exactly the reported behaviour.
  The registry (publish, tombstone, and read) is now keyed by the map's
  stable ID string. A regression test plants another map's entries in
  the registry and asserts they grow nothing here.
- The HUD split now belongs to the map being drawn, not the last map
  built, and the splice-upgrade shim recognises this edition too --
  stripping the tombstone before the lift block, since the tombstone
  contains no `return` and the lift pattern would overrun it.

## 1.45.4

- **The seam ghosts, actually: superseded singles, now tombstoned.**
  Route 22's count dropping 275 -> 27 proved the gates work; the
  survivors stood BESIDE grounded big trees, which was the tell. When a
  chunk first meshes a 2x2 tree straddling its border, the cells go down
  the SINGLE-cell path -- stamped, published, lifted. A later, fuller
  remesh forms the grouped big tree for those same cells, drawn
  grounded, and the singles are never recreated -- but the registry
  never forgot them, leaving supports under nothing, clustered exactly
  where big trees stand. The group stamp site now writes a TOMBSTONE:
  claiming a 2x2 deletes its four member cells from the registry. A
  harness test lifts the injected deletion out of the patched file and
  runs it: exactly the four members go, nothing else.
- **The FLOR line now reads like `27 trunks (19t/8b 12|7 13|7 14|7)`** --
  a tree/boulder split plus the first three boulder cells' coordinates.
  If any ghost survives the tombstone, its next screenshot names the
  exact cells, and the archaeology takes minutes instead of releases.

## 1.45.3

- **The seam ghosts are gone: supports never stand on walkable ground.**
  The tile-id filter could not catch them because their tiles LIE: near
  map connections the base data is padded with the border TREE block and
  the overlay draws path on top, so `tileAt` says tree while the player
  strolls across the cell -- which is why the ghosts hugged the seams
  and reported healthy tile ids. Collision cannot lie the same way: it
  has to match what the player can actually do. A registry entry on a
  WALKABLE cell now builds nothing. Real trees and boulders are never
  walkable and are untouched; out-of-bounds ring and strip cells read
  not-walkable and keep their trunks; and the harness now includes a
  lying seam cell -- tree id, walkable -- that must stay bare.

## 1.45.2

- **Ghost trunks filtered out; the trees and boulders are untouched.**
  Bare supports were standing on pathways, clustered at map-section
  seams -- registry entries for cells that draw no round object at all.
  A support is now built only where the cell's own tile is a KNOWN round
  id (the tree set or the boulder set for that tileset); path tiles fail
  that test and get nothing, while edge and connection-strip trees pass
  it, because the strip serves the neighbour's real tree ids. Tilesets
  without curated sets trust the registry as before, so nothing is lost
  where the catalogue is thin. The working delineation, the solid stone
  stacks and the exact stamp-to-support heights are all unchanged.

## 1.45.1

- **Fixed: every support vanished for anyone upgrading from 1.43.x.**
  Those releases spliced a lift with no publish, and the splice's own
  marker made 1.45.0's idempotence check say "already done" -- so the
  publishing edition never landed, the registry stayed empty, and the
  bushes floated with nothing beneath while the lifts lived on. The
  patcher now recognises an older edition of its own splice, strips it
  back to the stock line, and applies the current one -- with a test
  that regresses the file and asserts the upgrade, without duplicates.

## 1.45.0

Three fixes to TALL TREES from the Viridian playtest, one of them
structural.

- **Supports are built only under REAL stamps.** The HUD's "660 trunks"
  in Viridian was the tell: re-deriving tree cells from TileShape
  over-matched wildly, which is what scattered supports across walkable
  paths. The Structures splice now PUBLISHES each cell it actually
  stamps (keyed per map, with the exact lift the mesher applies), and
  the payload builds supports only from that registry -- a support with
  nothing above it is now impossible by construction, and trunk heights
  can never drift from bush heights. The mesh rebuilds as chunks stream
  in.
- **Tree and boulder ids were swapped.** In the shipped art the
  border-wall drawing is the GREEN tree rows and the lone canopy is the
  grey rock. Playtest beats archaeology; the sets are corrected.
- **Stone supports are solid.** The crossed-panel stack read as flat
  sheets; a boulder now stands on a four-sided BOX in two courses --
  wide below, narrower above -- so it reads as piled stone from every
  angle.

## 1.44.1

- **Boulders stand on stone stacks -- delineated by TILE ID, per cell.**
  The palette theory died on a route: grey rounds under a green palette,
  because they are a different DRAWING. The border-wall cell (tiles
  64/65/80/81 on OVERWORLD) is what reads as boulders; the lone canopy
  (42/43/58/59) is the tree. Both sit in Dramatic Shape's cylinder pool,
  but the authored ids are distinct -- the exact code-level delineator
  wanted from the start. Boulder cells now get a two-course stone stack
  (still lifted, still height-varied, so they hover as cairns); tree
  cells keep trunk and branches; both kinds mix correctly on one map.
  The gym rock (44-47 over 7/8/23/24) is stacked too.
- **Border rounds get their supports.** Dramatic Shape stamps rounds in
  a ring PAST the map edge (Structures' ROUND_RING); the support scan
  stopped at the boundary, so edge trees hovered on nothing. The scan
  now walks the same two-cell ring.

## 1.44.0

- **Stone stacks under stone-palette rounds.** The grey "boulders" that
  1.43.1 put on tree trunks are, in the engine's own data, TREES: the
  same eight tile ids as every route's round trees, coloured grey by the
  map's assigned SGB palette (Pewter's, the caves', the tower's). There
  is no boulder tile to key on -- the palette IS the distinction, and it
  is deterministic engine data, not sampled pixels. On the stone
  palettes (PEWTER, CAVE, GRAYMON, INDIGO) a lifted round now stands on
  a two-course STACK OF STONES -- squat, speckled, no branches -- and
  everywhere else on a trunk, as before. The lift itself is unchanged,
  so Pewter's rocks hover as stacked cairns rather than lollipops.

## 1.43.1

TALL TREES did nothing in 1.43.0, for two independent reasons -- either
alone would have sufficed.

- **The splice only ran on a FRESH install.** An already-patched game
  took the "ceiling patch active / module updated" branch, which
  refreshed payloads but never touched Structures or the mesher, so the
  lift was never spliced in. The tree splice now runs on every boot, on
  both branches, idempotently -- and re-lands automatically if a
  Dramatic Shape update overwrites the files.
- **It was keyed to the wrong class.** In TileShape's own tables the
  class named `tree` is the flat upright of the hedgerow tree-LINES; the
  round bush is class `cylinder`, and `tree` never reaches the
  round-stamp path at all. Both the lift and the trunks were checking a
  class that SOUNDED right instead of the one the engine routes there --
  the mountains lesson, relearned. Both sides now key on `cylinder`,
  hedgerows explicitly get no trunks, and a test holds each line.

## 1.43.0

- **TALL TREES: the round bushes stand on trunks.** Dramatic Shape
  authors its trees -- every round bush is a `tree`-class shape in
  TileShape's own tables, built as a "round stamp" by Structures and
  expanded by the mesher. No colour guessing anywhere: the stamp is
  tagged with a LIFT at creation, guarded by that authored class, and the
  mesher applies it on expansion. Heights vary per cell (three steps, by
  position hash), and this mod draws the trunks underneath -- crossed
  quads of generated bark, a branch on every third tree -- sharing the
  same hash so each trunk meets its own bush's base exactly.
  - This deepens the patch by two one-line splices (Structures,
    ChunkMesher), both anchored exactly, both in the write ledger, both
    reading the config bridge -- so with TALL TREES off, or this mod
    deleted, the lift is zero and the geometry is stock.
  - Known limits, stated plainly: collision is untouched (you cannot walk
    under a raised bush); the big 2x2 canopy-group trees stay grounded
    for now; CUT bushes rebuild their chunk and vanish correctly.
  - New TALL TREES toggle, on by default.

## 1.42.1

Both halves of "the world past the rim" redone after the first playtest.

- **The under-horizon is one flat tone, sampled from the art.** Pinning
  the skirt to the panorama's bottom ROW smeared every colour in it --
  trees, fields, shore -- into vertical streaks. The skirt and floor are
  now a single colour: the average of the panorama's own bottom row,
  read once from the file, so each horizon grounds itself in the tone
  its painted land actually ends in.
- **The apron continues the GROUND, not the obstacle.** A map's boundary
  row is very often the thing that stops you -- fences, ledges, tree
  lines -- and continuing that outward drew dark fence to the horizon.
  Water still continues as water; anything else takes its tile from the
  first WALKABLE cell inward from the edge, which is the grass, path or
  sand the boundary stands in. Hazing softened from 45% to 18%: distance
  should cool, not black out.

## 1.42.0

- **WORLD APRON: the world continues past its own rim.** The map was a
  plateau with nothing beyond its edge -- a paper-thin rim and then void
  all the way to the painted backdrop, which made the world read as
  SMALL. Each boundary cell's own tile now continues outward, ring by
  ring, stepping gently down and fading with the same haze the
  neighbouring maps use: grass runs on as grass, water as water, sand as
  sand, because the tile IS the edge it extends.
  - Cost: one static mesh per map, built once from the atlas already
    bound. No new textures, a few hundred quads -- memory cost as near
    nothing as makes no difference.
  - It sits a shade below true ground level, so real terrain and
    Dramatic Shape's own neighbour-map meshes always draw over it: no
    seams, no z-fighting, no connection bookkeeping.
  - New WORLD APRON toggle, on by default.

## 1.41.0

- **Dramatic Shape 1.7.0 is supported.** Nothing in 1.7.0 blocks this mod
  -- its conflict flag is unchanged and every anchor this patch uses is
  intact; what was stopping it was this mod's own untested-version gate,
  added after 1.6.2. 1.7.0 is now tested and listed. Its diorama viewport
  and chroma key are set for the whole frame, so this mod's passes are
  cut and keyed with everything else rather than fighting it.
- **Renamed to `ds_fp_ceilings`** -- plural, which it should always have
  been. NOTE: the launcher matches conflicts by id, so Dramatic Shape's
  `"conflicts": ["ds_fp_ceiling"]` no longer matches this mod's id. This
  mod therefore checks Dramatic Shape's manifest ITSELF, still matching
  the old spelling, and stands down exactly as before. The rename is not
  a way round the flag.
- **CAVE DARKNESS removed.** It drew nested shells to close the walls in,
  the same mesh the Lavender fog uses -- but the fog sets a colour with
  ALPHA before drawing and this never did, so the shells came out fully
  opaque: a cave of flat slabs with the clear colour showing through
  them. It was wrong every time it was switched on.
- **The horizon no longer cuts off from above.** Looking at the world
  from the diorama and 3RD rungs, the eye clears the map's own edge and
  saw under it, where the painted band stopped and the void began. The
  panorama's bottom row of pixels now continues straight down and across
  a floor, in the exact colour the painted land ends in.

## 1.40.1

- **Building backs: the door cell only, in the back wall's own brick.**
  1.40.0 covered the mirrored door and five neighbours with the SIDE
  wall's tile, which pasted the gable end's flat colour over brickwork
  and ran past the corner of the house -- worse than the false door it
  was hiding. Only the door cell is covered now, and the tile is sampled
  ALONG THE SAME BACK WALL: the nearest cell left or right whose north
  face is also exposed, which is by definition a neighbouring piece of
  the wall being repaired. It falls back to the row behind only if the
  wall is a single cell wide.

## 1.40.0

- **The head bob is gone.** It was the single most complained-about thing
  this mod did, and it went right to the top of the Dramatic Shape
  falling-out. Walking now moves the eye NOTHING. What remains responds
  to events, which is what reads as weight rather than seasickness: the
  ledge-hop crouch, arc and landing settle (JUMP FEEL), and the doorway
  step (DOORWAY STEP). The walking sway went with the bob.
- **Building backs: the mirrored door and its five neighbours.** Covering
  only the door's own column left the frame and lintel showing either
  side of the plain patch, which read as a bricked-up doorway. The cover
  is now the door cell plus the cells beside and above it, all wearing
  the side wall's art, so the whole feature disappears into plain wall.
  A cell that is a REAL door -- some houses genuinely have a back
  entrance -- is never covered, and there is a test holding that line.
- **Version support, stated plainly:** works with Dramatic Shape 1.5.4,
  1.5.5 and 1.6.0, and absol89's fork. 1.6.1 and 1.6.2 both declare a
  conflict with this mod and are declined out of respect for it -- the
  manifest scan catches the flag on either.
- **REMOVE PATCH is no longer necessary** -- deleting the mod folder now
  removes every trace via the write ledger, and both paths restore
  Dramatic Shape byte for byte. The option stays for anyone who prefers
  an explicit switch, but the folder is enough.

## 1.39.0

- **The rainbow is absolute.** Its position was already pinned where the
  shower ended, but the arc itself was a flat quad turned to face the
  camera -- so it swivelled to track you as you walked, which reads as
  movement. A flat quad cannot be both fixed and legible: hold it still
  and it foreshortens to a sliver from any angle but square on. The bow
  is now BENT around a partial cylinder, both-sided, placed once with a
  fixed facing and never touched again -- some part of it faces you from
  most directions, the way the painted horizon works.
- **Its feet run below the ground.** The legs used to stop in mid-air at
  the texture's bottom edge; they now continue down behind the terrain
  and the depth test crops them at the skyline, where a rainbow's legs
  actually disappear.
- For the avoidance of doubt: this release works with Dramatic Shape
  1.5.4, 1.5.5, 1.6.0 and 1.6.1, and absol89's fork. Only 1.6.2 is
  declined, in deference to its conflict flag.

## 1.38.0

Three changes about being a better neighbour, prompted by Dramatic
Shape 1.6.2 and the discussion around it.

- **Dramatic Shape's conflict flag is respected.** 1.6.2 declares a
  conflict with this mod at its author's request. When that flag is
  present, this mod patches NOTHING, removes any earlier patch, and
  explains itself in the log. Fighting a conflict flag from inside the
  other mod's folder is not a relationship.
- **Untested Dramatic Shape versions are left stock.** The tolerant
  splice used to try its luck on versions it had never seen. After a new
  DS release shipped mid-cycle, that is over: on an unlisted version this
  mod does not patch, keeps everything stock, and waits for an update. A
  missing feature is recoverable; a bad splice in someone else's mod is
  not. Tested: 1.5.4, 1.5.5, 1.6.0, 1.6.1, 1.6.2, and absol89's 1.3.0.
- **A write ledger.** Every file this mod writes into Dramatic Shape's
  folder is recorded as it is written, and BOTH removal paths -- the
  REMOVE PATCH option and the delete-the-folder safety net -- now walk
  that ledger: originals restored where they were backed up, everything
  else deleted, ledger removed. Removal restores exactly what was done,
  whatever version did it.

## 1.37.0

Two faults behind the uninstall complaints, both serious, both this
mod's.

- **The self-uninstall deleted nothing on most installs.** It looked for
  Dramatic Shape at `mods/DRAMATIC_SHAPE`, a hardcoded folder name --
  while the patcher itself finds Dramatic Shape properly, by scanning for
  its manifest id. The folder is commonly `DramaticShapeVoxelMod`, and on
  those installs REMOVE PATCH and the delete-the-folder safety net both
  removed nothing at all. That is the pile of files left in
  `mods/DramaticShapeVoxelMod`, and it is why the head bob was still
  there after people uninstalled: `FirstPerson.lua` stayed patched. It
  now finds the folder the same way the patcher does, with a fallback to
  any mod folder carrying this mod's payload.
- **The mod reported version 1.20.0 for sixteen releases.** Each bump
  searched the manifest for the PREVIOUS version string; the first search
  missed, and every one after it looked for a version that was never
  there. Launchers trim the trailing zero, so players saw "1.2" against a
  download labelled 1.36. The version is corrected, and a test now
  asserts the manifest matches the newest changelog entry.

To clear a bad install by hand: delete `ds_fp_ceiling` from your mods
folder, then delete the whole `DramaticShapeVoxelMod` folder from
`APPDATA/LOVE/pokemon-love2d/mods/` and re-import Dramatic Shape. That
restores it exactly.

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
