# Third-Party Notices

The MIT license in this repository applies only to independently authored Kanto First Person 2.0 source.

Legacy Kanto First Person audio, panoramas, poster art, and any source-derived
material remain the property of their original authors. They are not relicensed
under MIT by this repository.

The project holds a separate express creator grant that permits use,
modification, derivative works, packaging, and redistribution of the covered
legacy assets in free or paid Kanto First Person packages. The private original
contains identifying information and is not published. The redacted,
hash-bound approval record is `docs/rights-approval.json`. No attribution is
required by that grant.

The public panorama inventory is
`docs/legacy-panorama-inventory.json`. It records the four preserved 4096-pixel
source panoramas and their deterministic 2048-pixel and 1024-pixel derived
variants, with dimensions, source relationships, and SHA-256 values. It does
not contain the private grant or identifying evidence.

The public sky inventory is `docs/legacy-sky-inventory.json`. It records three
deterministic, binary-coverage cloud textures derived from the authorized
legacy cloud design. Their generator uses a local deterministic random stream;
it does not read game data or change Lua's global random state.

No Pokémon ROM, extracted Gen1recomp cache, save file, or ROM-derived image may be distributed with this project.

## Website dependencies

The optional `website/` source uses React, React DOM, Three.js, React Three
Fiber, React Three Postprocessing, and Zustand under their MIT licenses.
It uses Postprocessing under the zlib license and the Press Start 2P font under
the SIL Open Font License 1.1. Exact versions are locked in
`website/package-lock.json`.

The website does not package the legacy mod audio, panoramas, posters, ROM
data, screenshots, or private evidence.
