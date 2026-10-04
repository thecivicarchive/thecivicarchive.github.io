# Black-capped chickadee (*Poecile atricapillus*): models and motion

Research for the companion builder, 2026-10-03. Two parts: (1) whether a licensed 3D model exists that is worth
building on; (2) how the real bird is put together and how it moves, turned into numbers for the rig and its clips.
Every figure is tagged **[measured]** (from a source that measured it), **[proxy]** (measured on a close relative or a
bird of the same size, named), or **[working value]** (my estimate from the anatomy and the footage, to be judged by
eye in the still-frame lab). Sources are listed at the end with their addresses.

---

## 1. Models

### Verdict: no model to build on. Sculpt the bird in code from the numbers in part 2.

Nothing found meets all three tests at once (true to the animal's anatomy, a licence that plainly allows use on a
public website, downloadable without an account). The nearest miss is a CC BY 3.0 low-poly Great Tit (a Paridae
cousin with the same build) from the Google Poly archive: a faceted art-style model with eight flat colours, no
textures, no rig, and blue, yellow and green panels that break the colour rule. It is useful only as a silhouette
check and was **not** copied into `shell_src/companions/models/`; nothing is added to `credits.json`.

### Candidates examined

| Candidate | Page | Licence (as shown) | Format | Size | Rigged / animated | Look | Verdict |
|---|---|---|---|---|---|---|---|
| **Great Tit (small bird)**, Tekano Bob, 2017 (Google Poly archive) | https://poly.pizza/m/1RWQSUcDqsG | "Creative Commons Attribution (CC BY 3.0)"; page states "No login required" | GLB (also OBJ); file `https://static.poly.pizza/b3d180be-86cf-456d-9e7d-4b5692ca9b2b.glb`, SHA-256 `4f6e74b4f503cb17aaa6dedb64954627e82ff1ab5f65df49ba65b495a8e66f42` | 287 KB; 10,438 vertices, 4,887 triangles; one mesh, 8 flat materials, no textures | No / no | Low-poly art style (faceted), Great Tit colours including blue, yellow and green | Right family, wrong style and colours. Silhouette reference only. Not used. |
| **Sparrow**, Poly by Google, 2017 | https://poly.pizza/m/3rTjKefT184 | "Creative Commons Attribution (CC BY 3.0)" | GLB (also OBJ); `https://static.poly.pizza/8eab0575-29bc-4c34-a372-d0f12083db66.glb`, SHA-256 `c37ab6840d187d67bd14c7529ce5bb39a10139a47388049cdc086de971608a47` | 43 KB; 1,156 vertices, 608 triangles, one texture | No / no | Blocky Google Blocks bird, orange bill and legs | Toy-like. Not used. |
| **Bird** (texturised, rigged, animated by Fabio Gonzalez, from the OpenGameArt bird basemesh) | https://opengameart.org/content/bird | "CC0" | `.blend` only (1 MB) | not stated | Yes / yes | Generic small bird, stylised | three.js cannot read `.blend`; converting needs Blender, which is not installed here and may not be installed system-wide. Not usable as delivered. |
| **Bird basemesh**, "noway" | https://opengameart.org/content/bird-basemesh | "CC0" (attribution requested, not required) | `.blend` (474 KB), ~750 triangles | ~750 tris | No | Sparrow-like, untextured | Same `.blend` problem; too coarse anyway. |
| **Bird (Yellow-billed Shrike)**, "pistachio" | https://opengameart.org/content/bird-yellow-billed-shrike | "CC0" | `.blend` in zip (11 MB), 996 triangles, 2K hand-painted maps | 996 tris | IK rig | Stylised passerine, a "feathers under 1k tris" workflow test | Wrong species and shape (a shrike is a long-tailed hook-billed bird); `.blend` only. |
| three.js sample birds (Parrot, Flamingo, Stork; morph-target flapping) | shipped in the three.js repository `examples/models/gltf/` | not confirmed (made by Mirada for the ro.me project; the three.js examples pages credit them, the licence text was not reachable from here) | GLB | small | morph targets | Low-poly, bright colours | Wrong species; red/green/pink colours. Worth opening only to see how a vertex-morph flap is authored. |
| Sloyd.ai "free 3D models" (Bird, Chick, Cockatiel, Starling) | https://www.sloyd.ai/free-3d-models/model/bird-gshze and siblings | "CC BY 4.0" | GLB/FBX/OBJ/STL | n/a | No | Generated, generic, stylised | Machine-generated shapes with no fidelity to a species. Not pursued. |

### Archives searched with no usable result

- **Khronos glTF sample assets, three.js, Babylon.js sample sets**: the only birds are the Duck, the Parrot/Flamingo/Stork trio and a Fox (CC BY 4.0, not a bird). No songbird.
- **Smithsonian 3D (3d.si.edu)**: the site answers scripts with HTTP 403; its known bird holdings are skulls and large specimens, nothing in the Paridae. Not verified from here.
- **MorphoSource / oVert (CT scans)**: the record found for a *Poecile* skeleton (ark:/87602/m4/M43557) sits behind an Anubis bot check for scripts, and MorphoSource downloads need an account in any case. Out under the rules. Useful later only if John wants to open a scan himself for skeleton proportions.
- **AVES 3D (aves3d.org)**: bird bone scans, terms unknown; the host did not resolve from this machine three times. Bones only, so not a renderable bird anyway.
- **Poly Haven, ambientCG, Quaternius, Kenney, KayKit**: no realistic animals; the stylised animal packs have no songbird.
- **OpenGameArt advanced search for "sparrow"** (3D): one result, the basemesh above. No tit, finch or chickadee.
- **Wikimedia Commons** (STL search for "chickadee"): no results.
- **Thingiverse, Printables, Cults3D, MakerWorld, Thangs**: searches return chickadee *birdhouses and feeders*; the one bird ornament ("Blue Tit Bird (Chickadee)" on Printables) is behind a login, as all Printables downloads are. Out.
- **Sketchfab, TurboSquid, CGTrader, Free3D, 3D Warehouse, RenderHub**: downloads need an account. Out by the rules.
- **Digital Life 3D (UMass)**: photoreal living-animal models, but delivered only through Sketchfab. Out.

### What this means for the build

Sculpt from the proportions in section 2, paint the plumage from section 2.3, rig from section 3, and animate from
sections 4 to 8. The reference footage to judge against is the Macaulay Library list in section 9.

---

## 2. The animal in numbers

### 2.1 Size [measured]

| Measure | Value | Source |
|---|---|---|
| Mass | 9–14 g (All About Birds); 10–14 g both sexes (Birds of North America via Wikipedia) | S1, S2 |
| Length, bill tip to tail tip | 12–15 cm | S1 |
| Wingspan | 16–21 cm | S1 |
| Wing chord | males 63.5–67.5 mm, females 60.5–66.5 mm | S2 |
| Tail | males 58–63 mm, females 56.3–63 mm; **tail/wing-chord ratio 0.944–0.955** across 4,422 banded birds | S2, S3 |
| Bill (exposed culmen) | 8–9.5 mm | S2 |
| Tarsus (the visible lower leg, the tarsometatarsus) | 16–17 mm | S2 |
| Eye | black, set in the black cap: "The cap extends down just beyond the black eyes, making the small eyes tricky to see" | S1 |
| Shape in one sentence | "a short neck and large head, giving it a distinctive, rather spherical body shape ... a long, narrow tail and a short bill" | S1 |

### 2.2 Proportions for the sculpt [working values, from the measurements above and the Macaulay footage]

Work in millimetres, then scale so 1 rig unit = the standing height on the perch.

| Part | Working size | Note |
|---|---|---|
| Standing height, branch top to crown, relaxed | 58–65 mm | fluffed in cold: 65–70 mm, and rounder |
| Head, feathered, front to back / side to side | 24–26 mm / 20–22 mm | the skull inside is ~20 mm; the "oversized round head" is mostly feathers, so the head *changes size* with mood (section 5.3) |
| Bill | 8–9.5 mm, straight, conical, black; gape line ends under the front of the eye | S2 |
| Eye, visible aperture | ~3 mm (eyeball ~4.5–5 mm) | from Brooke et al.: eye radius scales with skull size; a 6–14 g bird sits at the bottom of their range (S19). The visible eye is black on black; only a specular glint reads at dock size |
| Body, feathered, length / depth / width | 60–70 mm / 35–40 mm / 32–36 mm | the rump and belly make one egg; the breast is deepest just behind the bib |
| Neck | invisible at rest (head sits on the shoulders); extends 15–20 mm when alert | S1 ("short neck"); see 3.1 |
| Folded wing, shoulder to tip | 60–68 mm (= wing chord) | tips reach the base of the tail; secondaries and tertials show pale edges (S1: "Note white-edged secondaries") |
| Tail | 56–63 mm, 12 feathers (6 pairs), narrow, square-tipped, the outer webs pale-edged | S4 (six pairs of rectrices in most birds) |
| Lower leg (tarsometatarsus) | 16–17 mm, dark grey; the tibiotarsus above it is almost wholly inside the flank feathers, only the "ankle" shows | S2 |
| Toes | three forward, one back (anisodactyl), 14 phalanges per foot; the hind toe and claw are long and wrap under the perch | S18 |

### 2.3 Plumage map [measured descriptions]

- Cap: black from the bill base over the crown to the nape, ending **just below the eye**, so the eye sits inside the black (S1).
- Bib: black from chin to upper breast, with a "messier" lower border than a Carolina Chickadee's; males' bibs are larger (S2).
- Cheeks: clean white, a wedge from the bill back to the nape sides, widening backward (S1, S2).
- Back: unstreaked grey (Wikipedia says "greenish grey"; keep it neutral or faintly warm grey, never green, by the colour rule); wings and tail slate grey with white edging on the secondaries and tertials and pale edges on the outer tail feathers (S1, S2).
- Underparts: white, with soft buff flanks grading to white below (S1).
- Bill black; legs and feet dark grey; eye dark brown-black (S1, S2).

### 2.4 Skeleton counts the rig should respect

| Part | Count | Source and confidence |
|---|---|---|
| Cervical vertebrae | about 14. Birds range 10–26; the Australaves (falcons, parrots, passerines) have the lowest counts; the turkey and the barn owl, both measured, have 14 | S5, S6, S7, S8. **The count for this species was not read from a specimen**; treat 13–14 as the working value |
| Free caudal vertebrae + pygostyle | 5–8 free vertebrae, then the fused pygostyle that carries the 12 tail feathers | S8 |
| Remiges | 10 primaries (the outermost tiny), secondaries with the inner three as tertials | S4 |
| Hindlimb | femur, tibiotarsus, tarsometatarsus, toes; the knee is inside the body feathers, the visible backward-bending joint is the ankle | S8 |

Leg segment lengths for the chickadee itself were not found in an open source (Zeffer et al. 2003 measured femur,
tibiotarsus and tarsometatarsus for 323 species but the table is not online; S20). Use the measured tarsometatarsus,
16–17 mm, and set femur ≈ 0.75–0.85 × and tibiotarsus ≈ 1.35–1.5 × the tarsometatarsus **[working values for a small
arboreal passerine; verify against a specimen or a scan if the leg is ever shown bare]**. The whole leg folds into a Z
at rest: hip and knee strongly flexed, ankle at roughly 70–90°.

---

## 3. Joints and ranges

### 3.1 Head and neck

The neck is an S at rest (dorsal pitch at the skull end, ventral in the middle, dorsal at the base), which lets the head
sit on the shoulders and still shoot forward or straight up (S6, S7). Passive per-joint ranges measured in a bird neck
(turkey, 14 cervicals; S7):

| Region | Dorsoventral per joint | Lateral bend per joint | Axial rotation per joint |
|---|---|---|---|
| Cranial joints (C3–C5) | ~70° | 7–41° | 44–54° (where most of the twist happens) |
| Middle (C5–C7) | ~70° | 23–35° | <12° |
| Caudal (C8–C10) | 50–70° | 54–69° (where most of the side bend happens) | 2–3° |

Working ranges for the companion's **head as one joint on a short neck** (two neck joints if the rig can afford them:
one at the skull, one at the base):

| Motion | Working range | Why |
|---|---|---|
| Yaw | ±120° in one snap; up to ±180° to look straight back or preen the back | owls photographed at 180° (S6); songbirds routinely preen the mantle |
| Pitch | +60° (bill to the sky) to −80° (bill to the feet; hanging upside-down the head bends back toward the twig) | S9 (hanging postures) |
| Roll (the head cock) | ±45° common, ±90° to aim one eye at something overhead | birds view distant or interesting things with the *side* of one eye (S10) |
| Neck extension | head centre rises 15–20 mm from drawn-in to alert | S1 |
| Eye in socket | tiny: 10–20° in most birds (some passerines more); **the head does the looking** | S10 |
| Bill gape | closed at rest; opens ~15–25° for calls, wider in the "open-mouthed advance" **[working value]** | S28 |

### 3.2 Wings

Folded tight at rest, tips at the tail base. Three real wing actions, and no others at rest:

- **Single wing-flick** (a display, S11): the bird faces the other bird, lifts and extends **one** wing, and folds it again at once; "extremely brief". Working: 80 ms up to ~60° of extension, 60 ms hold, 80 ms fold.
- **Wing stretch** (comfort): one wing and the leg of the same side stretched down and back together, 1–2 s hold, slow fold **[working value]**.
- **Flight stroke**: zebra finches of the same size beat 24.3 Hz in a wind tunnel and 28.5 Hz in free flight, flapping 50–69% of the time and bounding with wings shut between bursts (S12). At 30 frames a second a 25 Hz stroke cannot be drawn; render it as a translucent blur fan plus a 6–8 Hz visible stroke, and never as a clean sine.

### 3.3 Tail

One joint at the pygostyle: pitch ±35° (flicks), yaw ±15°, fan from closed (~6 mm wide) to ~60° spread when landing or
braking **[working values]**. The tail is a counterweight: it dips when the bird crouches and lifts when it lands.

### 3.4 Legs (from X-ray data on zebra finches, 15 g, the best-measured bird of this size; S13, S14)

| Joint | Range during the take-off leap [proxy] | Note |
|---|---|---|
| Hip flexion/extension | 42° (−4° to 38°) | plus 15° ab/adduction and 20° long-axis rotation |
| Knee | 123° to 163° (40° of extension) | |
| Ankle (the visible joint) | 61° to 135° (74° of extension) | the ankle and hip drive the leap, the knee less |

The toes grip with the digital flexors; perching uses the proximally inserted flexors more than carrying does (S18).
When the bird crouches the toes tighten on the perch and when it stands tall they loosen: couple toe curl to ankle
angle (a classic tendon-locking account exists, Quinn & Baumel 1990, not opened here).

---

## 4. Gaits and the moves that carry weight

### 4.1 The hop (the only gait on a branch)

Small passerines hop with both feet together; in the one bird studied across gaits (magpie), hopping stride frequency
barely changes with speed and the swing phase lasts the same whatever the gait (S15). Working numbers for a chickadee
branch hop, built from the leap data below:

| Phase | Duration | What moves |
|---|---|---|
| Crouch | 60–90 ms | ankle 135°→70°, hip and knee flex, body drops 4–6 mm, tail dips 15–20°, head stays level |
| Push | ~60 ms | all three joints extend (hip and ankle most); a leap into flight lasts 62–65 ms in total (S14) |
| Air | 80–150 ms | rise 10–25 mm, travel one body length (60–70 mm) or a pivot of 90–180° |
| Touchdown | 12 ms | legs absorb the landing (S13); tail lifts 20–30° |
| Settle | 150–250 ms | one damped bounce of the body (about 2 Hz), toes re-grip, feathers resettle |

Active foraging: 2–4 hops a second with pauses; a hop often turns the bird 180° on the perch **[working value]**.

### 4.2 Take-off [proxy: zebra finch, 15.4 g; S13, S14]

- The whole leap lasts 62–65 ms; peak ground force 4.9 × body weight; lift-off speed 1.7 m/s; the legs supply 93.6% of
  the initial flight velocity; the first downstroke begins ~2 ms *after* the feet leave the perch.
- Order of events (S16): the head moves first and lines up with the direction of flight; the trunk pitches down and the
  ankle and hip flex (the crouch loads the leg muscles); then everything extends. **Animate head first, then crouch,
  then the leap, then the wings.**

### 4.3 Landing [proxy: zebra finch; S13]

- Body held steep, ~58° to the horizontal, with the legs forward; horizontal speed falls from 1.3 to 0.8 m/s in the
  last approach phase; the last wingbeat has only 13% of the force of the ones before (the wings switch off just before
  the perch); forces peak 12 ms after touchdown and the legs absorb the rest.
- Landing forces are smaller than take-off forces, and a flexible perch soaks up energy by bending (S17): give the
  branch a small dip (1–2 mm at dock scale, one damped cycle) on every landing and hop.

### 4.4 Flight between perches

Flights are short bursts, under 15 m, at about 20 km/h (5.6 m/s), with wings tucked between bursts (S2); All About Birds
calls it "bouncy flight" (S1). The arrival clip should bound in on a sine-like path with the wings shut on the down
curve and a burst on the up curve, then flare steep for the landing above.

### 4.5 Acrobatics

Chickadees "often move acrobatically through small branches, and can perch sideways or upside-down" (S1). Among tits,
the species that hang most have hindlimbs modified for leg flexion (S9): when hanging, the ankle and hip are flexed
hard and the head bends back up toward the twig. Use it sparingly on the dock (one idle variant), it is the single
most chickadee-looking thing the bird can do.

---

## 5. Head, eyes, breathing, feathers

### 5.1 Head snaps (saccades)

Birds move the head in quick snaps and hold it still between them. In flying zebra finches a snap lasts 15.6 ± 0.4 ms,
peaks at ~1,080°/s (up to 2,150°/s), and the head is still 83% of the time, with pitch wandering under 3.5° (S21).
Perched birds snap less often but just as fast. Working values: snap 15–50 ms depending on size (10° in one frame,
90° in two frames at 30 fps), then a hold of 0.3–2.5 s drawn from a random range, never a steady rhythm. Birds look at
things with the side of one eye (S10): to "notice" the pointer, the head yaws 60–90° so one eye faces it, and to look
at something above, it rolls.

### 5.2 Blinks

- Blinks are a sweep of the translucent nictitating membrane from the inner (bill-side) corner outward, "frequent,
  rapid, brief", and they **coincide with head movements**; the lower lid rises only when the bird is drowsy or
  preening, slowly, as a sustained closure (S22).
- Measured in a bird: membrane-only blink 100 ms, membrane plus lids 200 ms; blinks occurred during 85–87% of gaze
  shifts and never without one; diurnal birds blink 0.2–0.9 times a second (S23).
- For the companion: start a 100 ms membrane sweep 0–20 ms before each head snap (so it hides the snap), add a few
  stand-alone blinks at 2.5–6 s random gaps, and let the lower lid creep up 40–60% during `rest`. Because the eye is
  black inside a black cap, draw the blink as a brief milky sweep plus the specular glint going out and coming back.

### 5.3 Breathing

Resting breathing in birds scales as f = 182 W^−0.33 breaths/min (W in grams, the units the fitted values imply: 82/min
at 11 g, 19/min at 1 kg; Calder 1968, S24) and 17.2 M^−0.31 (M in kg; Lasiewski & Calder 1971, confirmed with "only
minor changes" by Frappell et al. 2001, S25). For an 11 g bird: **70–85
breaths a minute, 1.2–1.4 Hz**, faster in the cold or when excited, slower (~1.0 Hz) in `rest`. Birds breathe by
expanding the whole thoraco-abdominal cavity (S8), so the whole body swells, not a chest: body scale +2–3% at
inspiration, with the tail tip rising ~1.5° a tenth of a cycle later and the head lifting a fraction of a millimetre.
Keep it going in Still mode's poster frame (mid-breath).

### 5.4 Feather postures (the mood dial)

Morris's classic scheme (S26): **sleeked** (thin, alert or alarmed), **relaxed**, **fluffed** (round, cold or resting),
**ruffled** (a display). The chickadee has a measured display of the last kind: the body ruffling display, "extreme
ruffling of the breast and back feathers", often with wing extension and spread primaries, used to keep others at a
distance and get at food (S27); crown feathers are raised in aggression as well (S11). Model the head and body as
scalable shells: sleek 0.96, relaxed 1.0, fluffed 1.08, ruffled 1.15 on the breast and back only.

---

## 6. The tell-tale habits a viewer recognises at once

| Habit | What happens | Timing | Source |
|---|---|---|---|
| Head cock and snap | one eye to the thing, hold, snap to the other eye | 15–50 ms snaps, 0.3–2.5 s holds | S10, S21 |
| Single wing-flick | one wing lifted and extended, folded at once | ~220 ms total | S11 |
| Tail flick | a quick dip and lift, sometimes a half-fan | 150–250 ms **[working value]** | seen in the footage listed in section 9 |
| Hop-pivot | hops on the spot and turns to face a new way, used as a display too | one hop cycle, 0.35–0.55 s | S28, section 4.1 |
| Hammering a seed | pins the seed to the perch under the toes, pecks "a hole in the shell, and then chip[s] out and eat[s] tiny bits of seed while expanding the hole" | pecks at 5–8 a second in bursts of 3–6, pauses to look up | S1, S2; footage ML432857 |
| Bill wipe | after eating: the bill is drawn along the perch, one side then the other | 2 strokes of ~100 ms | footage ML201457271 ("pecking a branch and rubbing the bill") |
| Head scratch | indirect: the wing droops and the foot comes up **over** it to the head | 1–2 s | S29 |
| Rouse | all feathers raised, then a 3–4-cycle shake that resettles them, tail and wings shivering | 0.5–0.8 s **[working value]**; described in S30 |
| Startle | sleeks thin, head up, freeze; then crouch and leap in 60–90 ms | S14, S26 |
| Scold | sleeked, bill opening on each "dee", facing the threat | footage ML471330 ("Mob") | S1 |
| Fluff to a ball | in cold or rest: head drawn in, body round, lower lids up | S22, S26 |

---

## 7. Clip-by-clip numbers for the companion rig

Every clip starts and ends **exactly** on the rest pose (relaxed feathers, head centred and level, tail at 0°, wings
folded, ankle ~80°, breathing continuous). Angles are in degrees, times in seconds from the clip start.

**arrive (~1.6 s, "lands")** — 0.00–0.75 bounding in from the upper right on two sine arcs (wings shut on the down
curve, 6–8 Hz visible stroke with blur on the up curve); 0.75–0.95 flare: body pitches to ~55–60°, tail fans to 60°
and lifts, legs swing forward, wings on their last weak stroke; 0.95–0.97 touchdown (12 ms), branch dips 1–2 mm;
0.97–1.25 settle bounce (2 Hz, damped), wings fold in two 120 ms moves, tail closes; 1.25–1.60 head snap to face the
reader with one eye (yaw 70°, 20 ms), blink, hold, snap back to rest at 1.5.

**idleA (4–6 s loop)** — breathing at 1.2–1.4 Hz with ±10% wander; a membrane blink at two random moments; one small
weight shift (body roll 3° over 0.4 s and back); feathers relax by 2% over the loop and recover.

**idleB (3–4 s, one of four, never the same twice)** — (a) head cocks: three snaps of 30–45° roll with 0.4–0.9 s holds;
(b) wing-flick + tail flick: the display above, then a 200 ms tail dip; (c) hammering: pitch the body 35° down, head
to the perch, 5 pecks at 7 Hz, look up (snap), 4 more pecks, bill wipe left and right (100 ms each), up; (d) hang: a
hop to the underside of the twig (pivot 180° about the perch axis over 0.3 s), 1.5 s hanging with the head bent back
up, hop back.

**notice (~1.2 s)** — head yaws 60–90° in 20 ms to put one eye on the pointer (blink with it), neck extends 10 mm,
feathers sleek 2%; hold 0.8 s with two micro-adjustments of 3–5°; return snap.

**react (~1.5 s, tapped)** — the real startle-and-hop: sleek (0.05 s), crouch (0.08 s), leap 15–20 mm with a 150 ms
wing flutter (two visible strokes with blur), land (12 ms), settle (0.25 s), then a wing-flick toward the reader and a
head cock.

**talk (3 s loop, Help open)** — attentive: head angled with one eye to the reader (yaw 50°, roll 20°), two or three
snaps of 10–15° per loop, bill opening 15–20° in short bursts of 3–4 at 6 Hz (silent "dee" notes), tail dipping 5° with
each burst, no hops.

**lookLeft / lookRight (~1 s holds)** — a single 70–90° yaw snap toward the side (with roll 15° so one eye leads),
blink, hold 0.7 s, snap back.

**rest (4–6 s loop, after a long idle)** — fluff to 1.08, head drawn in 10 mm and pitched down 10°, lower lids up
40–60%, breathing 1.0 Hz with a larger body swell (+3%), one slow re-settle of the feathers per loop.

**dance** — section 8.

---

## 8. The hover dance (2.2 s): a branch jig made only of real moves

Every beat is something the bird does (sections 4 and 6); the charm is in the quickness of the snaps against the
slowness of the settles.

| Time (s) | Beat | Numbers |
|---|---|---|
| 0.00–0.15 | Crouch | ankle 80°→60°, body down 5 mm, tail dips 15°, feathers sleek 3%, head stays level |
| 0.15–0.21 | Push: hop-pivot 90° to the right | 60 ms extension, branch dips 1.5 mm |
| 0.21–0.33 | Airborne | rise 15 mm, wings flick half-open once (blur) |
| 0.33–0.35 | Land | 12 ms absorb; tail lifts 25° |
| 0.35–0.50 | Settle + head snap | body bounce 2 Hz damped; head yaws 70° to the reader in 20 ms with a 100 ms membrane blink |
| 0.50–0.72 | Single wing-flick (right) + tail flick | 80 ms up to 60°, 60 ms hold, 80 ms fold; tail dip 20° over 150 ms |
| 0.72–1.10 | Hop-pivot 180° to the left | same hop timings; lands facing the other way, then head snaps back over the shoulder to the reader (yaw 150°, 30 ms), head cock 40° |
| 1.10–1.40 | Bill wipe | head to the perch (pitch −60°, 120 ms), stroke left 100 ms, stroke right 100 ms, head up (snap) |
| 1.40–1.78 | Rouse | feathers out to 1.10 over 150 ms; four shake cycles at 12 Hz (body roll ±6°, wings and tail quivering); settle to 1.0 over 150 ms |
| 1.78–2.10 | Resettle | head snaps to centre (20 ms) with a blink at 1.9; tail returns to 0°; one damped weight shift |
| 2.10–2.20 | Rest | exactly the rest pose; breathing phase continuous throughout |

Motion off: no dance (the shell already gates it). Keyboard focus plays the same clip.

---

## 9. Reference footage (Macaulay Library, Cornell Lab)

486 Black-capped Chickadee videos: https://search.macaulaylibrary.org/catalog?taxonCode=bkcchi&mediaType=video&sort=rating_rank_desc
(the archive answers scripts with a bot check, so open it in a browser). Checked entries:

- ML201457271, Josep del Hoyo, Vancouver, 2012: "A bird changing perch, pecking a branch and rubbing the bill" (the hop, the peck and the bill wipe). https://macaulaylibrary.org/asset/201457271
- ML432857, David Brown, New York, 2004, 28 s, close-up: "eat seed" (seed handling). https://macaulaylibrary.org/asset/432857
- ML476193, Matthew D. Medler, New York, 2014, 41 s: foraging or eating. https://macaulaylibrary.org/asset/476193
- ML452131, Timothy Barksdale, Duluth, 1996, 26 s, close-up: "perch, eat, take-flight" (the leap). https://macaulaylibrary.org/asset/452131
- ML475325, Matthew D. Medler, 2014, 16 s: feeding then departing a snow-covered suet feeder ("Take Flight"). https://macaulaylibrary.org/asset/475325
- ML471330, Jay McGowan, New York, 2012, 22 s: mobbing and scolding (sleeked posture, calls). https://macaulaylibrary.org/asset/471330
- ML468565611, Liam Ragan, Montréal, 2018: carrying food, flying, foraging. https://macaulaylibrary.org/asset/468565611

Muybridge's *Animal Locomotion* bird plates are of large birds (pigeons, a cockatoo, hawks, eagles, vultures, storks,
an ostrich), none a small passerine as far as I know (the plate list was not checked from here), so they are no help. The oVert CT scans (MorphoSource) hold a *Poecile* skeleton but need an account.

---

## Sources

Reached and read from this machine unless marked. SORA (the Searchable Ornithological Research Archive) has moved;
its old `sora.unm.edu` addresses redirect to the archive's new home, and the Wayback Machine holds copies of S3, S24,
S27 and the Stokes notes.

- S1. All About Birds, Black-capped Chickadee: Identification (measurements, "cap extends down just beyond the black eyes", "short neck and large head", "bouncy flight", "perch sideways or upside-down"), Overview, Life History ("peck a hole in the shell, and then chip out ... tiny bits"). https://www.allaboutbirds.org/guide/Black-capped_Chickadee/id , https://www.allaboutbirds.org/guide/Black-capped_Chickadee/overview , https://www.allaboutbirds.org/guide/Black-capped_Chickadee/lifehistory (refuses scripts; read in a browser)
- S2. Wikipedia, Black-capped chickadee (measurements and plumage cited there to Birds of North America; flight bursts under 15 m at ~20 km/h; hammering seeds on a branch; roosting singly in cavities). https://en.wikipedia.org/wiki/Black-capped_chickadee
- S3. Yunick, R. P. (2003). Effectiveness of wing chord/tail length measurements in separating Black-capped Chickadee from Carolina Chickadee. North American Bird Bander 28(2): 52–57 (tail/wing ratio 0.944–0.955, n = 4,422). https://sora.unm.edu/sites/default/files/journals/nabb/v028n02/p0052-p0057.pdf
- S4. Wikipedia, Flight feather (ten primaries in most passerines, the outermost tiny; six pairs of rectrices in the vast majority of birds). https://en.wikipedia.org/wiki/Flight_feather
- S5. Böhmer, C., Plateau, O., Cornette, R., Abourachid, A. (2019). Correlated evolution of neck length and leg length in birds. Royal Society Open Science (Australaves have the lowest cervical counts). https://pmc.ncbi.nlm.nih.gov/articles/PMC6549945/
- S6. Krings, M., Nyakatura, J. A., Fischer, M. S., Wagner, H. (2014). The cervical spine of the American barn owl: quantitative analysis of 3D motion. PLoS ONE (14 cervical vertebrae; the S-curve; a head turned 180°). https://journals.plos.org/plosone/doi?id=10.1371/journal.pone.0091653
- S7. Kambic, R. E., Biewener, A. A., Pierce, S. E. (2017). Experimental determination of three-dimensional cervical joint mobility in the avian neck. Frontiers in Zoology 14: 37 (turkey, 14 cervicals; per-joint ranges). https://pmc.ncbi.nlm.nih.gov/articles/PMC5525307/
- S8. Wikipedia, Bird anatomy (cervical count range; 5–8 free caudal vertebrae and the pygostyle; femur/tibiotarsus/tarsometatarsus; breathing by the whole thoraco-abdominal cavity). https://en.wikipedia.org/wiki/Bird_anatomy
- S9. Moreno, E., Carrascal, L. M. (1993). Leg morphology and feeding postures in four Parus species: an experimental ecomorphological approach. Ecology 74: 2037–2044 (hanging tits have hindlimbs modified for flexion). Abstract via Europe PMC: https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=TITLE:%22Leg%20morphology%20and%20feeding%20postures%20in%20four%20Parus%20species%22&format=json&resultType=core
- S10. Wikipedia, Bird vision (eye movement 10–20° in most birds, more in some passerines; head movements do the work; lateral monocular viewing; head stabilisation reflexes; the lower lid closes the eye in most birds). https://en.wikipedia.org/wiki/Bird_vision
- S11. Smith, S. M. (1996). The single wing-flick display of the Black-capped Chickadee. Condor 98: 885–887 (one wing lifted and extended, immediately folded; "extremely brief"; faces the opponent). https://sora.unm.edu/sites/default/files/journals/condor/v098n04/p0885-p0887.pdf (read through its abstract and summary; the PDF itself was not reachable from here)
- S12. Davis, A. P., Tobalske, B. W. Effect of distance on flap-bounding flight performance (SICB abstract: zebra finch wingbeat 28.5 Hz free flight vs 24.3 Hz wind tunnel; %flap 50.2 vs 68.7). https://sicb.org/?p=37064 ; and Tobalske, B. W., Peacock, W. L., Dial, K. P. (1999). Kinematics of flap-bounding flight in the zebra finch over a wide range of speeds. J. Exp. Biol. 202: 1725–1739 (13.2 g; flap-bounding at all speeds). https://journals.biologists.com/jeb/article/202/13/1725/7978/
- S13. Provini, P., Tobalske, B. W., Crandell, K. E., Abourachid, A. (2012). Transition from leg to wing forces during take-off in birds. J. Exp. Biol. 215: 4115–4124 (zebra finch 15.4 g: 4.9 BW, 1.74 m/s, legs 93.6%, wings 2 ms after lift-off). https://journals.biologists.com/jeb/article/doi/10.1242/jeb.074484/257959/ ; and (2014). Transition from wing to leg forces during landing in birds. J. Exp. Biol. 217: 2659–2666 (body ~58° at touchdown; forces peak 12 ms after; last wingbeat 13%). https://journals.biologists.com/jeb/article/doi/10.1242/jeb.104588/257790/
- S14. On the hindlimb biomechanics of the avian take-off leap. bioRxiv preprint 2021.11.19.469279 (a University of Southampton group; authors not confirmed from here). Zebra finch musculoskeletal model driven by Provini's data: leap 62–65 ms; hip −4° to 38°, knee 123°–163°, ankle 61°–135°; 1.08–1.39 m/s. https://www.biorxiv.org/content/10.1101/2021.11.19.469279.full
- S15. Verstappen, M., Aerts, P. (2000). Terrestrial locomotion in the black-billed magpie. I. Spatio-temporal gait characteristics. Motor Control 4: 150 (hopping frequency barely changes with speed; constant swing phase); and Verstappen, Aerts, Van Damme (2000) J. Exp. Biol. 203: 2159–2170 (joint patterns alike across gaits; hopping preferred). https://journals.biologists.com/jeb/article/203/14/2159/8464/
- S16. Provini, P., Abourachid, A. (2018). Whole-body 3D kinematics of bird take-off: key role of the legs to propel the trunk. The Science of Nature 105: 12, doi 10.1007/s00114-017-1535-8 (head moves first; trunk pitches down; ankle and hip flex, knee less; then extension). Abstract via Europe PMC: https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=TITLE:%22Whole-body%203D%20kinematics%20of%20bird%20take-off%22&format=json&resultType=core
- S17. Bonser, R. H. C. (1999). Branching out in locomotion: the mechanics of perch use in birds and primates. J. Exp. Biol. 202: 1459–1463 (landing forces smaller than take-off; flexible perches dissipate energy). https://journals.biologists.com/jeb/article/202/11/1459/7926/
- S18. Backus, S. B., Sustaita, D., Odhner, L. U., Dollar, A. M. (2015). Mechanical analysis of avian feet: multiarticular muscles in grasping and perching. Royal Society Open Science (anisodactyl feet, 14 phalanges, proximally inserted flexors in perching). https://pmc.ncbi.nlm.nih.gov/articles/PMC4448815/
- S19. Brooke, M. de L., Hanley, S., Laughlin, S. B. (1999). The scaling of eye size with body mass in birds. Proc. R. Soc. B (eye mass ∝ body mass^0.68 from 6 g up; eye radius and skull size co-vary in strict proportion). https://pmc.ncbi.nlm.nih.gov/articles/PMC1689681/
- S20. Zeffer, A., Johansson, L. C., Marmebro, Å. (2003). Functional correlation between habitat use and leg morphology in birds. Biol. J. Linn. Soc. 79: 461–484 (femur, tibiotarsus, tarsometatarsus for 323 species; table not online). Abstract via Europe PMC: https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=TITLE:%22Functional%20correlation%20between%20habitat%20use%20and%20leg%20morphology%20in%20birds%22&format=json&resultType=core
- S21. Eckmeier, D. et al. (2008). Gaze strategy in the free flying zebra finch. PLoS ONE 3: e3956 (saccades 15.6 ms, ~1,083°/s peak, head still 83% of the time). https://pmc.ncbi.nlm.nih.gov/articles/PMC2600564/
- S22. Morris, J. G. L., Parsons, J. J. (2023). The various ways in which birds blink. Animals (591 species: membrane sweeps inner to outer canthus, "frequent, rapid, brief and coincided with head movement"; lower lid rises slowly in drowsiness and preening; only 18 of 131 passerines blink with the upper lid). https://pmc.ncbi.nlm.nih.gov/articles/PMC10705787/
- S23. Yorzinski, J. L. (2016). Eye blinking in an avian species is associated with gaze shifts. Scientific Reports 6: 32471 (membrane blink 0.10 s, with lids 0.20 s; blinks during 85–87% of gaze shifts; diurnal birds 0.20–0.89 blinks/s). https://pmc.ncbi.nlm.nih.gov/articles/PMC5004160/
- S24. Calder, W. A. (1968). Respiratory and heart rates of birds at rest. Condor 70: 358–365 (f = 182 W^−0.33, 45 species). https://sora.unm.edu/sites/default/files/journals/condor/v070n04/p0358-p0365.pdf (equation read from the paper's indexing; the scanned PDF's text layer could not be opened here)
- S25. Frappell, P. B., Hinds, D. S., Boggs, D. F. (2001). Scaling of respiratory variables and the breathing pattern in birds. Physiol. Biochem. Zool. 74: 75–89 (re-fits Lasiewski & Calder 1971 with "only minor changes in the coefficients"). Abstract via Europe PMC: https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=TITLE:%22Scaling%20of%20respiratory%20variables%20and%20the%20breathing%20pattern%20in%20birds%22&format=json&resultType=core
- S26. Morris, D. (1956). The feather postures of birds and the problem of the origin of social signals. Behaviour 9: 75–113 (sleeked, relaxed, fluffed, ruffled). doi 10.1163/156853956X00264 (not opened from here; the classic reference)
- S27. Piaskowski, V. D., Weise, C. M., Ficken, M. S. (1991). The body ruffling display of the Black-capped Chickadee. Wilson Bulletin 103 ("extreme ruffling of the breast and back feathers ... often ... associated with wing extension and spread primaries", as quoted in the archive's index of the paper). Held in SORA, https://sora.unm.edu/ (the archive has moved hosts; the paper's new address was not found from here, and the quotation comes from the index summary, not the PDF)
- S28. Ficken, M. S., Weise, C. M., Popp, J. W. (1990). Dominance rank and resource access in winter flocks of Black-capped Chickadees. Wilson Bulletin 102 (ruffling the body or crown feathers, hopping and pivoting, an open-mouthed advance), as summarised by the Animal Diversity Web account of the species. https://animaldiversity.org/accounts/Poecile_atricapillus/ (the account's address has changed; it answered 404 from here)
- S29. Simmons, K. E. L. (1957). The taxonomic significance of the head-scratching methods of birds. Ibis 99: 178–181; reviewed in Condor 61: 53–56 (1959): of 25 passerine families only the Timaliidae scratch directly; the rest, Paridae included, bring the foot up over the drooped wing. https://sora.unm.edu/sites/default/files/journals/condor/v061n01/p0053-p0056.pdf
- S30. Buffalo Bill Center of the West (2023). What's that bird doing? Preening, rousing (rousing: feathers raised then shaken back into place; a relaxed bird). https://centerofthewest.org/2023/07/10/whats-that-bird-doing-preening-rousing/
- S31. Smith, S. M. (1991). The Black-capped Chickadee: Behavioral Ecology and Natural History. Cornell University Press (the standard monograph; seed handling under the feet, displays; not opened here).
- S32. Roderick, W. R. T., Chin, D. D., Cutkosky, M. R., Lentink, D. (2019). Birds land reliably on complex surfaces by adapting their foot-surface interactions upon contact. eLife 8: e46415 (parrotlets reposition claws in 1–2 ms on landing). https://elifesciences.org/articles/46415
- S33. Model archive pages: poly.pizza (CC BY 3.0 pages above); OpenGameArt (CC0 pages above); Smithsonian 3D https://3d.si.edu/ (403 to scripts); MorphoSource record https://www.morphosource.org/concern/media/000043557 (bot check; account needed to download).
