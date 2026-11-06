# The snail's shell model

`shell.glb` is a CC0 photogrammetry scan of a real land-snail shell (TinyWorlds, OpenGameArt, 2017; see LICENSE.txt),
converted here from FBX 6.1 to a glTF 2.0 binary, turned into a frame the companion can wear and stretched along its
coiling axis to a garden snail's proportions. It is the only part of the snail companion that comes from a file; the
body, head and tentacles are sculpted in code (shell_src/companions/snail.js), and so is the shell's colour: the
companion's fragment shader paints Cornu aspersum's pattern over the surface, so the file carries no colour map.

| | |
|---|---|
| File | `shell.glb`, 454,984 bytes (444 KB) |
| SHA-256 (this GLB) | `a2562310cf287b9cd6151bd41299bad83d96f7c2930e945c70b72c206081bb19` |
| SHA-256 (original zip) | `544e647c39d761f3b9601530ca65557da2c67e7c6e0f6d4a4b708881db768cbd` |
| Mesh | 3,088 vertices, 6,069 triangles, one primitive, one material, one UV island (positions, normals, uv) |
| Textures | normal 1024² JPEG 4:4:4 (306 KB), occlusion-roughness-metallic 512² JPEG (4 KB: nearly uniform); no colour map |
| Frame | coiling axis = +Y through the origin, apex up at (0, 0.45, 0); the aperture on the +X side, facing +Z and down; dextral |
| Stretch | 1.175× along the coiling axis (the scanned shell is more depressed than Cornu's: height/diameter 0.75 against 0.85–1.0) |
| Extents | x −0.448 … 0.578, y −0.449 … 0.454, z −0.503 … 0.394 |

## Where things are (also in the file's `extras`)

- Aperture (the mesh's one hole; a rim loop of 105 vertices): centre (0.139, −0.143, 0.211), outward normal
  (0, −0.576, 0.817), reach 0.471. Measured on the rim: an oval 0.89 by 0.62 across, its long axis 0.907 rad from the
  coiling axis within the aperture's plane, its centre offset (−0.022, −0.028) along the oval's axes from the rim's
  mean point (`RIM` in snail.js).
- Apex: (0, 0.45, 0). The angle between the apex direction and the aperture's outward normal is 125°, a property of
  the shell that fixes how it can be worn: with the apex to the snail's right, up and back, the aperture faces down
  and forward onto the mantle.
- `scan_frame` in the extras holds the rotation and the apex position that took the scan's own frame to this one.

## How the companion wears and paints it

`snail.js` reads the extras, builds the wearing rotation from an apex direction and a desired aperture direction
(`SHELL` in the file), sculpts the mantle to the aperture's oval so the lip rests on it, and dresses the mesh with the
kit's physical material (clearcoat over the scan's normal and roughness maps, both sides drawn) with a fragment shader
chunk that paints the colour: on a whorl's tube the latitude is the angle of the surface normal in the plane through
the coiling axis, so five interrupted chestnut bands sit at five fixed angles, broken by pale flecks, over a buff
ground streaked along the growth lines (constant angle about the axis), with a whitish lip near the aperture's plane
and a worn pale apex. No colour on the shell is red or blue.

## Loading

The kit vendors `vendor/jsm/loaders/GLTFLoader.js`; `build_shell.py` mirrors this folder to `shell/companions/models/`
beside the companions and copies `credits.json` with it.
