# Eastern gray squirrel (*Sciurus carolinensis*): models found, and how the animal moves

Research notes for whoever builds the squirrel companion (`shell_src/companions/squirrel.js`). Written 2026-10-03 by the
squirrel research agent of the `companions-models-and-motion` workflow. Everything below is either quoted from a
source with its address, or marked **estimate** (my reading of reference stills and of general small-mammal rules,
to be checked against footage). Numbers are for an adult of about 500 g unless stated.

Short version: **no usable 3D model exists** under the rules (CC0 or CC-BY, downloadable without an account, true to
the animal); the Google Poly archive on poly.pizza has nine CC-BY 3.0 squirrels, all faceted "Blocks" toys of 260 to
1,330 triangles, none rigged. **Sculpt the animal in code** from section 2. Nothing was added to `credits.json`.

---

## 1. Models

### 1.1 Rules applied

Licence must allow use on a public website (CC0, CC-BY with a credit, or a licence that plainly allows it); the file
must be downloadable without an account, purchase or CAPTCHA, from the maker's or an archive's own page; glTF/GLB
preferred, OBJ fine; no tool that must be installed system-wide (so a `.blend`-only file is out: there is no Blender
here). Colours on the finished companion: black, white, greys, browns, buff only.

### 1.2 Where I looked, and what is there

| Archive | Result |
| --- | --- |
| **poly.pizza** (the Google Poly archive; every model CC-BY 3.0, files served from `static.poly.pizza` with no account) | Nine squirrels: see the table below. All are Google Blocks / low-poly toys. |
| **Smithsonian 3D** (3d.si.edu, CC0 scans) | `https://3d.si.edu/explore?edan_q=squirrel` → "Your search found no results", with and without the CC0 filter (checked in the Browser pane on 2026-10-03; the site answers scripts with 403). No squirrel skull or skeleton either. |
| **collections.si.edu** (the Smithsonian catalogue, 3D-media filter) | Behind a Cloudflare "request verification" page; not worked around. |
| **MorphoSource / oVert** (CT scans of museum specimens, incl. *Sciurus*) | `https://www.morphosource.org/catalog/media?q=Sciurus+carolinensis` answers scripts "Access Denied", and downloads need an account → reference only, not usable under the rules. |
| **OpenGameArt** | "Undead Squirrel (ANIMATED)" by CDmir, CC0, `undeadsquirrell.zip` 3.5 MB, `.blend` only, rigged and animated, a zombie stylisation (`https://opengameart.org/content/undead-squirrel-animated`); "Flying Squirrel" by shikah, CC0, `squirrel.blend` 1.8 MB, "A badly rigged flying squirrel" (`https://opengameart.org/content/flying-squirrel`). Both out: wrong animal or look, and Blender-only. The CC0 animals collection (`https://opengameart.org/content/cc0-3d-animals-creatures`) has no other squirrel. |
| **itch.io** | polyducks "3D Model - Squirrel" (`https://polyducks.itch.io/3d-model-squirrel`): $5.00 or more, not rigged (shape keys), licence forbids AI, crypto and resale → paid, out. The free tag page (`https://itch.io/game-assets/free/tag-squirrel`) lists only 2D sprites. |
| **openFrameworks example data** | "New Squirrel" by Bruce Lehmann (Omind), Attribution License 2.5, `NewSquirrel.3ds` + `Squirrel.jpg`, published on 3dvia.com (gone); readme at `https://math.vu.nl/~eliens/demo/lib-of-vs-addons-ofx3DModelLoader-example-data-squirrel-readme.txt`. The model file itself was not located, and 3DS is not a format the vendored three.js loaders read → out. |
| **Quaternius, Kenney, KayKit, Khronos glTF samples, three.js examples, Poly Haven, Digital Life 3D** | No squirrel. (Quaternius's animal packs: `https://quaternius.com/`.) |
| **Wikimedia Commons** | No squirrel 3D files (STL/OBJ/glTF). |
| **Sketchfab, CGTrader, TurboSquid, Free3D, SuperHive, Fab, RenderHub** | Login or purchase required → out by rule. (Several realistic rigged squirrels exist there for money, e.g. SuperHive "Grey Squirrel"; that would be John's decision, not taken.) |
| **Thingiverse, Printables, Cults, MakerWorld** | Not searched to the end (script-rendered search pages; the session's web-search budget ran out); their squirrels are untextured printing sculpts or CC-BY-NC, low expected value. |

### 1.3 The poly.pizza candidates (all "Creative Commons Attribution 3.0", OBJ + glTF, none rigged or animated)

Triangle counts were read from the GLB headers (downloaded to the session scratchpad only, not into the project).

| Page | Author | Triangles | Look (from the thumbnail) | Verdict |
| --- | --- | --- | --- | --- |
| `https://poly.pizza/m/caxos24uWC9` | Poly by Google | 716, one texture | grey with a brown wash, on all fours, tail curled over the back; blocky but squirrel-proportioned | best proportions of the nine; still a faceted toy |
| `https://poly.pizza/m/1-x1WzixbjR` | Danni Bittman | 1,330, vertex colours | grey, sitting up with a nut, tail in an S | best silhouette of the nine; faceted |
| `https://poly.pizza/m/2WqY_AFEn-M` | Poly by Google | 844, one 2 MB texture | grey, on all fours, flat tail | tail is a board |
| `https://poly.pizza/m/794lutNHni-` | Poly by Google | 764 (page) | grey, upright, nut, pink ears | chunky, stylised |
| `https://poly.pizza/m/fQ5KzXoR2uA` | Poly by Google | 634 (page) | brown with white stripes, straight tail | looks like a chipmunk |
| `https://poly.pizza/m/64Yw0UoayhC` | Poly by Google | 292 | red, faceted | red is a forbidden colour anyway |
| `https://poly.pizza/m/dQdmcEiCXU3` | Simon Graff | 792 (page) | orange-tan, nut, on a base | stylised |
| `https://poly.pizza/m/eGdXC-5V2wM` | Tipatat Chennavasin | 260 | tan and white, sitting | stylised |
| `https://poly.pizza/m/24FL2riioG5` | Paul Hoover | 1,028 | tan, sitting, googly eye | stylised |

Licence text for all nine: `https://creativecommons.org/licenses/by/3.0/` (credit the named author and link the licence).

### 1.4 Verdict

None is good enough to build a hyper-realistic animal on: every candidate is a faceted toy with no rig, and smoothing
one would leave worse anatomy than the SDF sculpt already in `squirrel.js`. **Build in code**, using section 2 for the
proportions and the motion. If a quick proportion check is wanted, `caxos24uWC9` and `1-x1WzixbjR` are the two to open
(CC-BY 3.0; nothing copied into the project, so no credit is owed yet).

### 1.5 Reference footage and stills (for looking, not for copying)

Macaulay Library (Cornell) holds video of this species; the pages sit behind an Anubis proof-of-work wall for scripts
(not worked around) but open normally in a browser, and the search engine's descriptions of three clips are: ML406639
(T. Barksdale, Kern, California: "perching and tapping its front feet"), ML468702 (G. Vyn, Ithaca, New York: foraging
or eating), ML441286 (T. Barksdale, Arkansas: walking and foraging). `https://macaulaylibrary.org/asset/406639`,
`.../468702`, `.../441286`. Their poster frames (© the contributors) show: a squirrel sitting on a branch against a
trunk, body upright, tail up behind; one foraging head-down in wood chips with the **tail laid flat forward over its
back**, tip toward the head; and one on a log in an open S-curve tail-up walk. The builder can time gaits from the
videos in a browser (200 ms resolution is enough for a bound).

---

## 2. Motion: how the body articulates and moves

### 2.1 Size and proportions

Sources: Hayssen (2008) Appendix I, *Sciurus carolinensis* row (head-body, tail, mass: females 253.5 mm, 215.5 mm,
512.7 g; males 260.0 mm, 204.4 mm, 430.8 g; unsexed adults 270.0 mm, 212.7 mm, 356.7 g) [1]; Koprowski (1994) via
Animal Diversity Web: total length 380–525 mm, tail 150–250 mm, ear 25–33 mm, hind foot 54–76 mm, mass 338–750 g
(mean 540 g), whiskers present at birth, "four toes on the front feet and five on the hind feet" [2][3]; Fukushima et
al. (2021): one gray squirrel of 341 g, body 236 mm, tail 215 mm (91 % of body), **tail mass 11 g (3 % of body mass)**,
body roll inertia 1.11 × 10⁻⁴ kg·m², body yaw inertia 1.62 × 10⁻³ kg·m², tail longitudinal inertia 4.26 × 10⁻⁵ kg·m²
[4]; Wikipedia (secondary): head-body 23–30 cm, tail 19–25 cm, 400–600 g, no sexual dimorphism in size or colour [5].

Working skeleton for the rig, with head-body length (HB) = 1.0 (≈ 260 mm):

| Part | Length / HB | Basis |
| --- | --- | --- |
| Tail vertebrae | 0.80–0.91 | measured [1][4] |
| Tail plume (hair) | adds 0.15–0.25 all round the bone; the plume is 0.30–0.45 HB wide seen from the side | **estimate** from stills |
| Hind foot (heel to claw tips) | 0.21–0.29 | measured [2] |
| Ear | 0.10–0.13 | measured [2] |
| Skull | ≈ 0.24 | **estimate** |
| Scapula / humerus / radius+ulna / hand | ≈ 0.20 / 0.16 / 0.16 / 0.12 | **estimate**; arboreal rodents have relatively long humeri and digits and "equally proportioned fore and hind limbs" [6] |
| Femur / tibia / foot | ≈ 0.20 / 0.22 / 0.23–0.25 | **estimate** except the foot; hind limb only a little longer than the fore [6] |
| Shoulder and hip height, standing on all fours | ≈ 0.40 (the scapular pivot and the hip sit at the same height above the ground in small mammals) | [7] |
| Head top, standing / sitting upright | ≈ 0.55 / 0.85–0.95 | **estimate** from stills |
| Tail tip, curled over the back while sitting | 1.10–1.25 above the ground | **estimate** from stills |

Exact gray-squirrel humerus, femur and tibia lengths exist in Blake & Chirchir (2026, 136 skeletons) [8] but the paper
is paywalled and the abstract gives none; check the estimates against it if access appears.

Vertebral column: 7 cervical (fixed in almost all mammals) and 19 thoracolumbar is the mammalian ground pattern [9];
for a squirrel read that as about 12–13 thoracic + 6–7 lumbar, 3 sacral (**the split is a typical-rodent estimate**).
Caudal vertebrae: about two dozen (**estimate**; Hofmann et al. 2021 measured the caudal series of 20 squirrel species
and found the primate/carnivore scheme of a **proximal, a transitional and a distal tail region** applies to almost
all squirrels regardless of locomotor type [10]). For the rig: 1 proximal stiff root (3–4 vertebrae's worth, small
range), a long transitional middle that does the bending, and a distal whip that overshoots.

Hands and feet: four long fingers in front (the thumb is a nub), five toes behind [3]. Tree-squirrel wrists allow the
supination used in food handling and climbing [11]. **Hind-foot reversal:** sciurids rotate the hind foot about 180°
(crurotalar plantarflexion + subtalar inversion + transverse-tarsal supination) to descend head-first or hang [12]; if
the companion ever climbs down, the hind feet point backwards and up.

Eyes: large, set high and lateral on the skull (stills); squirrels are diurnal and highly visual, with a cone-dominated
retina and dichromatic (green and blue cone) colour vision, and large visual brain areas [13]. Because the eyes face
sideways, a squirrel looks *at* you with one eye: the head yaws 30–60° off the body axis and often rolls 10–20°
(**estimate**). That one-eyed cocked look is the single most recognisable pose.

Coat (from the field guide and stills): grey with a brown wash down the back and over the head, white belly and throat,
a pale (buff-white) eye-ring, ears grey to white behind; the tail a grey-brown core with dark banding and a silver
fringe of long tipped hairs.

### 2.2 Joint ranges for the rig (degrees)

All ranges are **modelling targets**: estimates bracketed by the sources named.

| Joint | Range | Notes |
| --- | --- | --- |
| Neck yaw | ±90 | can look back over the shoulder; pitch −60 (nose to belly) to +60 (up a trunk); roll ±25 |
| Spine, sagittal | ~90 total between the tight grooming ball and the stretched leap; ±20–30 about neutral in a bound | in asymmetrical gaits the lumbar spine's flexion–extension supplies about half the hind-limb step length [7]; bounding = "flexion and extension" of the trunk, trotting = side bending [14] |
| Scapula (shoulder pivot) | rotates ~40–50 per stride | the scapula is the dominant forelimb element; proximal segments give more than half the propulsion [7] |
| Elbow | 60–150 | crouched, zigzag limb [7]; more flexion on slopes and on branches [15][16] |
| Wrist | flex/extend ±60, supination for handling | [11] |
| Hip | 30 (crouch) to 150 (take-off) | hind-limb launch is "essentially identical" across leaping squirrels [17] |
| Knee | 40–150 | |
| Ankle | 30–160; the ankle does more of the leap than the knee | Essner's launch kinematics as summarised at [18] |
| Hind foot, long-axis reversal | 0 to 180 | head-first descent [12] |
| Tail root (proximal region) | pitch ±15, yaw ±10 | stiff |
| Tail middle (transitional) | cumulative curl to >270 (it curls over the back to the head); lateral S ±40 | [10] and stills |
| Tail tip (distal) | free whip, overshoots the middle by 20–30 | |
| Tail about its own axis | full rotations possible (a falling squirrel spun its tail at about 500 rpm, four turns in 0.5 s) | [4] |
| Ears | swivel ~20, flatten in alarm | **estimate** |
| Jaw | gape 20–30 for an incisor bite; chewing 3–5 Hz | bite force rises at wider gapes [19]; chewing frequency ∝ body mass⁻⁰·¹²⁸ across mammals [20] (the 3–5 Hz for 500 g is my estimate on that line; the mammal regression itself is in [21]) |
| Eyelids | close in ~0.06 s, open in ~0.10 s | **estimate** (small-mammal blink) |

### 2.3 Breathing (never stops, even in the Still frame)

- Allometry (Stahl 1967 [22], equation as commonly quoted: breaths/min ≈ 53.5 × M⁻⁰·²⁶, M in kg; verify against the
  paper's table): 0.5 kg → ~64/min (1.07 Hz); 0.35 kg → ~70/min. Heart rate on the same scaling ≈ 241 × M⁻⁰·²⁵ →
  ~290 bpm at 0.5 kg.
- Measured in a close relative: 24 wild Caucasian squirrels (*S. anomalus*, 255–410 g), awake in a restraint jacket,
  "at the resting stage": respiratory rate 106.3 ± 2.1/min (85–125), heart rate 342.9 ± 8.6 bpm (286–423), 38.9 °C
  [23]. Restraint is arousing, so take this as the *alert* end.
- **Use:** alert 1.0–1.2 Hz; rest clip 0.7–0.8 Hz; for 3–5 s after `arrive` 1.6–2.0 Hz decaying to alert; rate jitter
  ±10–15 % (the kit already drifts the rate). Amplitude: flanks ±2–3 % width, chest a little more when sitting upright
  (the white chest visibly swells); sitting squirrels show the breath in the belly, standing ones along the ribs.

### 2.4 Blinking

No measurement for any tree squirrel was found. Rats (nocturnal, 200–600 g) blink 5.3 ± 0.3 times a minute, humans
17.6 [24]; across 71 primate species diurnal animals blink more than nocturnal ones and the rate rises with body size
[25]; peafowl time most blinks to coincide with gaze shifts, when vision is already suppressed [26]. **Use:** a diurnal,
very visual 500 g mammal → mean gap 5–8 s, drawn irregularly (the field guide's 2.5–6 s is livelier and acceptable),
about one in seven a double blink, blink total 0.12–0.18 s, and bias blinks to land on head saccades. Half-closed lids
in `rest`.

### 2.5 Gaits

What the species does (Dunham et al. 2019, free-ranging and lab gray squirrels on high-speed video [27]): on branches
the gaits are **asymmetrical**: gallops and half-bounds, and "high-impact bounds, with reduced limb-lead durations" on
declines; more gallops and half-bounds on small and medium branches; lab animals ran faster than wild ones and, on
narrower poles, slowed down and (at a given speed) raised duty factor, kept more limbs on the support and lengthened
the forelimb lead. Bounding animals are less consistent stride to stride than trotters and keep correcting sideways
[14] — add 5–10 % random variation to every stride.

Definitions (Hildebrand 1977 [28], as applied in [29]): **full bound** = fore pair and hind pair each land together
(lead < 10 % of the stride); **half-bound** = hind pair together, forefeet staggered (fore lead > 10 %); **gallop** =
both pairs staggered. Within a pair the first foot down is the *trailing* limb (shock absorber), the second the
*leading* limb (stiff); on branches squirrels slow down, flatten the vertical oscillation of the centre of mass
("compliant gait"), flex the limbs more and lengthen the lead intervals; the trailing forelimb "tests" the branch [15].
On inclines limbs flex and retract more to hug the substrate; forelimbs go to the sides and under a branch, hind feet
on top [16].

Numbers from the only sciurid with published duty factors on the flat and on a pole (Swinhoe's striped squirrel,
~100 g [29]): mean speed 1.7 ± 0.4 m/s, range 0.8–3.4 m/s, above 2.5 m/s rare; at the same speed the pole raised the
forelimb duty factor by about 13.5 percentage points and the hind by 12–17; running downhill on the flat raised duty
factors by 15–24 points. A gray squirrel is five times heavier; on the ground it bounds at roughly 2–4 m/s
(**estimate**; it covers a lawn in a few seconds).

**Bound / half-bound timing for the animator** (stride = 1.0; at ~2 m/s one stride ≈ 0.28–0.32 s, ≈ 2.2 HB long —
**estimate**; time it from the Macaulay clips if possible):

| Phase | Event | Body |
| --- | --- | --- |
| 0.00–0.42 | hind feet on the ground together, pushing | pitch rises to nose-up +15° by 0.40; spine extends; tail base swings down then trails |
| 0.42–0.55 | **extended flight** (stretched out) | tail streams straight back, tip trailing |
| 0.55 | trailing forefoot lands; 0.62 leading forefoot lands (half-bound stagger ≈ 0.07 of the stride; 0 in a full bound) | pitch falls to nose-down −12° by 0.70; elbows yield 20–30° |
| 0.62–0.80 | forelimbs bear weight, body passes over the hands | spine begins to flex; hind feet swing forward **outside and past** the hands |
| 0.80–1.00 | **gathered flight** | spine flexed 25–30°; tail lifts and the middle curls; hind feet reach for the ground in front of where the hands were |

Centre-of-mass rise and fall ±0.10–0.12 HB on the ground, less on a branch [15]. Duty factors on the ground at
moderate speed: fore ≈ 0.35–0.45, hind ≈ 0.40–0.50 (**estimate**, bracketed by [29]). Tail: base pitch follows body
pitch with a ~90° phase lag; tip lags the base a further 60–80 ms; amplitude ±20–30° at the base, ±50° at the tip.
Walking (used while foraging, head down, belly near the ground): a slow lateral-sequence walk at 0.3–0.6 m/s, stride
~0.5 s, tail held in a shallow S above the back (**estimate**, from stills).

### 2.6 Leaping, landing, falling

- Fox squirrels (the gray's larger cousin) leap gaps of 1.5–5 body lengths; horizontal velocities before landing 3–7
  m/s; they learned in five trials to correct launch **velocity** (not angle) from a bendy perch; landings that miss
  are saved by **swinging under or over the perch with the claws**; a mid-leap wall contact ("parkour") changes
  horizontal velocity by about −0.6 m/s; nobody fell [30].
- The hind-limb launch is the same across leaping, parachuting and gliding squirrels [17]; gray squirrels jumping from
  narrow poles prioritise moving the centre of mass through a long push (deep crouch, long extension) over raw force
  [31]. Launch sequence for a hop: crouch 0.10–0.15 s (hip/knee/ankle flex), forefeet leave first, hind limbs extend
  through ~100–120° of hip and knee travel in 0.08–0.12 s, body pitch at take-off +20–35° (**estimate**), tail streams
  then arcs up as the body starts to rotate.
- Falling: the squirrel stabilises the **head first** (29–169 ms), then counter-rotates the tail to right the body (a
  −360°/s roll corrected within ~0.5 s) [4]. Lesson for the rig: the tail is light (3 %) and *fast*; the head is the
  steady reference point and the body swings about it.

### 2.7 Sitting, handling food, vigilance

- The sit: haunches down, long hind feet flat and pointing forward, back curved into a hump, forepaws together at the
  chest, head raised; food is "held and rotated by the front paws as the squirrel either sits or hangs" [32]. Squirrels
  are **vigilant while handling food with the head up**, and will move to a spot with a better side view before eating
  a large item, but not a small one [33]. Seeds are handled for 2–5 s each (faster far from cover) [32, citing Newman et
  al.]; a hazelnut takes 10–60 s to open [32].
- **Use:** an "eat" idle of 3–4 s: sit up, rotate the item one turn per 2–3 s with alternating paw pushes, jaw at 3–5 Hz
  with ±10° gape, eyes up and scanning every 0.5–1 s, two small head turns, then drop the forepaws.
- Tail while sitting: an open S over the back when calm; a **tighter curl and more of the tail bent** reads as more
  aroused/aggressive — tail curvature and the portion of tail bent predicted a dominant squirrel's aggression [34].
  Piloerection (a fluffed tail) is part of the display [34]: fluff the plume +15–25 % when alarmed.

### 2.8 Alarm: freeze, scan, tail signals, foot stamping

- Tail movements are classed as **twitches/flicks (< 45°)** and **flags (> 45°, "waggled purposefully in S-shaped
  movements")**; flags and the vocal moan are the predator-specific signals: **flags go with terrestrial threats**
  (cats, humans), moans with aerial ones; kuks and quaas are general alarms [35][36]. A robot squirrel's tail flag
  plus bark gets the biggest response; squirrels react by flagging their own tails, stopping foraging to look, or
  running up a tree; urban squirrels respond more to the visual flag than rural ones [37][38]. The repertoire also
  includes **foot stamping and teeth chattering**; kuks are repeated rapidly for a few seconds, then slow [36].
- The freeze: a squirrel stops dead mid-move (often flattened to the bark, or upright like a post), scans with
  head snaps, then bolts or sits up. Timing for the rig: stop within 0.1 s; hold 0.5–3 s; 2–3 head snaps of 30–60°,
  each 0.10–0.15 s with 0.3–0.8 s holds; then a bound (**estimate** from the behaviour described in [37]).
- Numbers for the tail (**estimates** built on the 45° rule): **flick** 0.15–0.25 s, base ±15°, tip ±40° (tip lags
  60–80 ms); **flag** a wave running base → tip, 0.4–0.6 s per wave, 2–4 waves a bout, base ±35–45°, tip ±70°, plus a
  sideways S component ±15°; bouts every 1–3 s while agitated; **foot stamp**: two quick taps of a hind foot 0.1 s
  apart with the body rocking 2–3°.

### 2.9 Head and gaze

Rodents shift gaze by **"saccade and fixate", head first** — the eyes move with the head during the saccade, then
counter-rotate to hold the image during the fixation [39]. Squirrels, being far more visual than mice [13], do this
conspicuously: a quick head snap (0.10–0.15 s), a hold of 0.5–2 s, then the next snap; the eyes drift slightly against
the head during each hold. With lateral eyes the "look at the reader" is a head yaw of 30–60° to aim one eye, often
with a 10–20° head roll (**estimate**). The kit's critically damped turn (`speed: 11`) is right for the settle; add the
snap-and-hold quality by driving the target in steps rather than continuously.

### 2.10 Grooming (the species fidget, variant)

Rodent grooming runs **head to tail** in a fixed chain [40]: phase 1, elliptical bilateral paw strokes near the nose
(paw and nose); phase 2, unilateral strokes from the whiskers to below the eye (face); phase 3, bilateral strokes
backwards and up over the head and ears; phase 4, body licking; tail and genital grooming and scratching follow the
same head-to-tail rule outside the chain. A captive *Sciurus* ethogram lists four basic postures, five grooming
behaviours and a separate "face wiping" behaviour [41]. Tree squirrels also pull the tail forward over a shoulder and
comb it with paws and teeth (stills; common footage). **Use** (3–4 s "face wash"): sit up; 6 elliptical strokes at ~4
Hz (0.12–0.15 s each); 2 slow unilateral strokes each side (0.3 s); 1 bilateral stroke over the ears (0.4 s); a quick
body shake; back to all fours. Hind-foot scratch (optional): 6–8 Hz for 0.5–1 s, head tilted toward the foot.

### 2.11 Weight, settling, rest

- After every hop the body settles with a small overshoot over 0.2–0.3 s; the tail overshoots more and settles over
  ~0.5 s (a spring with damping ratio ≈ 0.5 and natural frequency ≈ 3 Hz at the base, lighter and faster at the tip) —
  consistent with a 3 %-mass, 90 %-length tail [4] (**the spring numbers are estimates**).
- Rest: lower crouch, tail laid forward along the back like a blanket (as in the foraging still), eyes half closed,
  breathing 0.7–0.8 Hz. In heat, squirrels lie flat on a cool surface with limbs spread to shed heat (reported for a
  captive *Sciurus*, resting out on branches "to decrease their body heat" [41]; the "sploot" is widely photographed in
  grays). A flattened belly-down rest is a charming, true alternative `rest` pose.

### 2.12 Tell-tale habits a viewer recognises at once

1. The **tail flick** and the S-wave **flag**, tip whipping after the base.
2. **Sitting up with the paws held to the chest**, head high, eyes scanning.
3. The **one-eyed cocked look**: head turned 30–60° and rolled a little to aim one eye at you.
4. **Stop-and-go**: dead freeze, two head snaps, then a sudden bound.
5. The tail carried **over the back like a parasol**, or laid flat forward along the back while head-down.
6. Rotating a nut in the forepaws while gnawing.
7. The flattened "post" freeze against a trunk; the head-first descent with the hind feet turned backwards.
8. A face wash with both paws; a hind-foot scratch; a quick whole-body shake.
9. Fake burying: a squirrel "will pretend to bury the object if they feel that they are being watched" [5] — a short
   dig-and-tamp pantomime (dig 3 strokes, press with the nose, pat twice with the forepaws, look up) makes a lovely
   idle.
10. The double hind-foot stamp when annoyed.

### 2.13 Mapping to the clip list (suggestions)

- **arrive** (1.5 s): three half-bounds in from the edge with the timings in 2.5 (stride 0.30 s; trailing/leading
  forefeet 0.02 s apart), a hard stop with a 0.25 s settle, one tail flick, a head snap to the reader.
- **idle A** (4–6 s loop): breathing at 1.0–1.2 Hz with jitter, the tail tip stirring ±5° at 0.3 Hz, two blinks, one
  small head saccade.
- **idle B** (3–4 s, variants): tail flag bout (2–3 waves); freeze-scan (2 snaps); face wash; nut-rotation eat;
  fake-bury; hind-foot scratch.
- **notice** (1.2 s): head snap to the reader (0.12 s), hold with one eye on them, one tail flick.
- **react** (1.5 s): sit up, paws to chest, tail curls tighter and fluffs, one flag wave, then down.
- **talk** (3 s loop): sitting up, small nods at ~1.5 Hz, tail tip quivering, occasional head roll.
- **look left / right** (1 s holds): a 45–60° head yaw with the roll, eye counter-drift during the hold.
- **rest** (4–6 s loop): low crouch or belly-flat sploot, tail blanket, lids half down, 0.75 Hz breathing.

### 2.14 Proposed hover dance: "flag, spin and wash" (2.2 s, ends exactly on rest)

Every piece is something the real animal does: the alarm sit-up, the S-wave tail flag, the pivot-bound a squirrel
uses to reverse on a trunk, the face wipe, and the settle.

| Time (s) | Movement | Numbers |
| --- | --- | --- |
| 0.00–0.25 | Freeze, then the head snaps to the reader; ears up | head yaw 45° + roll 10° in 0.12 s; one tail-tip flick (±40°, 0.2 s) |
| 0.25–0.70 | Sits up tall, forepaws to the chest; the tail runs two flag waves base → tip and fluffs | body pitch −55° (upright), paws 1.3 rad, waves 0.22 s each: base ±40°, tip ±70°, S ±15°; plume +20 % |
| 0.70–1.40 | Two pivot-hops: the first turns the body 180°, the second completes 360°; a hind-foot stamp on each landing | hop height 0.06 HB, each hop 0.30 s with 0.05 s crouch; spine flexes 25° in the air; tail streams then re-curls with a 90° lag; stamp = double tap 0.1 s apart |
| 1.40–1.90 | Back on all fours facing the reader; three quick elliptical face strokes with both paws | strokes at 4 Hz (0.14 s each), head pitched down 25° |
| 1.90–2.20 | Drops into the rest pose with weight: overshoot and settle, tail last; one slow blink | body settle 0.25 s (ζ 0.5), tail settle 0.5 s; blink 0.18 s |

A shorter alternative (1.6 s): sit-up + two flags + one 360° pivot-hop + settle, no face wash.

---

## Sources

1. Hayssen V (2008). Patterns of body and tail length and body mass in Sciuridae. *Journal of Mammalogy* 89(4):852–873. https://doi.org/10.1644/07-MAMM-A-217.1 — Appendix I PDF: https://www.science.smith.edu/departments/biology/VHAYSSEN/sq_size.pdf
2. Koprowski JL (1994). *Sciurus carolinensis*. *Mammalian Species* 480:1–9. https://doi.org/10.2307/3504224
3. Lawniczak MK, *Sciurus carolinensis*, Animal Diversity Web (measurements and behaviour citing Koprowski 1994). https://animaldiversity.org/accounts/Sciurus_carolinensis/
4. Fukushima T, Siddall R, Schwab F, Toussaint SLD, Byrnes G, Nyakatura JA, Jusufi A (2021). Inertial tail effects during righting of squirrels in unexpected falls: from behavior to robotics. *Integrative and Comparative Biology* 61(2):589–602. https://doi.org/10.1093/icb/icab023 — open text: https://pmc.ncbi.nlm.nih.gov/articles/PMC8427179/
5. Wikipedia, Eastern gray squirrel (secondary). https://en.wikipedia.org/wiki/Eastern_gray_squirrel
6. Samuels JX, Van Valkenburgh B (2008). Skeletal indicators of locomotor adaptations in living and extinct rodents. *Journal of Morphology* 269(11):1387–1411. https://doi.org/10.1002/jmor.10662
7. Fischer MS, Schilling N, Schmidt M, Haarhaus D, Witte H (2002). Basic limb kinematics of small therian mammals. *Journal of Experimental Biology* 205:1315–1338. https://doi.org/10.1242/jeb.205.9.1315
8. Blake T, Chirchir H (2026). Evaluating Bergmann's and Allen's rules in the long bones of the eastern gray squirrel. *Anatomical Record*. https://doi.org/10.1002/ar.70313
9. Narita Y, Kuratani S (2005). Evolution of the vertebral formulae in mammals: a perspective on developmental constraints. *Journal of Experimental Zoology B* 304(2):91–106. https://doi.org/10.1002/jez.b.21029
10. Hofmann R, Lehmann T, Warren DL, Ruf I (2021). The squirrel is in the detail: anatomy and morphometry of the tail in Sciuromorpha. *Journal of Morphology* 282(11):1659–1682. https://doi.org/10.1002/jmor.21412
11. Thorington RW, Darrow K (2000). Anatomy of the squirrel wrist: bones, ligaments, and muscles. *Journal of Morphology* 246(2):85–102. https://doi.org/10.1002/1097-4687(200011)246:2<85::AID-JMOR4>3.0.CO;2-5
12. Jenkins FA, McClearn D (1984). Mechanisms of hind foot reversal in climbing mammals. *Journal of Morphology* 182(2):197–219. https://doi.org/10.1002/jmor.1051820207
13. Van Hooser SD, Nelson SB (2006). The squirrel as a rodent model of the human visual system. *Visual Neuroscience* 23(5):765–778. https://doi.org/10.1017/S0952523806230098
14. Lammers AR, Stakes SA (2025). Kinetics of symmetrical versus asymmetrical in-phase gaits during arboreal locomotion. *Journal of Experimental Zoology A* 343(2):159–171. https://doi.org/10.1002/jez.2878
15. Schmidt A (2011). Functional differentiation of trailing and leading forelimbs during locomotion on the ground and on a horizontal branch in the European red squirrel. *Zoology* 114(3):155–164. https://doi.org/10.1016/j.zool.2011.01.001 — SICB abstract: https://sicb.org/abstracts/functional-differentiation-of-the-trailing-and-leading-forelimbs-during-terrestrial-and-arboreal-locomotion-in-the-european-red-squirrel-sciurus-vulgaris-rodentia
16. Schmidt A, Fischer MS (2011). The kinematic consequences of locomotion on sloped arboreal substrates in a generalized (*Rattus norvegicus*) and a specialized (*Sciurus vulgaris*) rodent. *Journal of Experimental Biology* 214:2544–2559. https://doi.org/10.1242/jeb.051086
17. Essner RL (2002). Three-dimensional launch kinematics in leaping, parachuting and gliding squirrels. *Journal of Experimental Biology* 205:2469–2477. https://doi.org/10.1242/jeb.205.16.2469
18. Holland M (ed.), "Springing Squirrels: The Mechanics of Squirrel Leaping and Landing", Biomechanics in the Wild (University of Notre Dame course blog, secondary; summarises Essner and Boulinguez-Ambroise). https://sites.nd.edu/biomechanics-in-the-wild/?p=4372
19. Cox PG, Watson PJ (2023). Masticatory biomechanics of red and grey squirrels modelled with multibody dynamics analysis. *Royal Society Open Science* 10(2):220587. https://doi.org/10.1098/rsos.220587
20. Druzinsky RE (1993). The time allometry of mammalian chewing movements: chewing frequency scales with body mass in mammals. *Journal of Theoretical Biology* 160(4):427–440. https://doi.org/10.1006/jtbi.1993.1028
21. Gerstner GE, Gerstein JB (2008). Chewing rate allometry among mammals. *Journal of Mammalogy* 89(4):1020–1030. https://doi.org/10.1644/07-MAMM-A-188.1 (not opened: BioOne's bot check)
22. Stahl WR (1967). Scaling of respiratory variables in mammals. *Journal of Applied Physiology* 22(3):453–460. https://doi.org/10.1152/jappl.1967.22.3.453
23. Physiological and hematological reference values of wild Caucasian squirrels (*Sciurus anomalus pallescens*) in northern Iraq. *Iraqi Journal of Veterinary Sciences* (2023). https://doi.org/10.33899/ijvs.2022.135861.2538 — https://www.vetmedmosul.com/article_178832.html
24. Kaminer J, Powers AS, Horn KG, Hui C, Evinger C (2011). Characterizing the spontaneous blink generator: an animal model. *Journal of Neuroscience* 31(31):11256–11267. https://doi.org/10.1523/JNEUROSCI.6218-10.2011 — https://pmc.ncbi.nlm.nih.gov/articles/PMC3156585/
25. Tada H, Omori Y, Hirokawa K, Ohira H, Tomonaga M (2013). Eye-blink behaviors in 71 species of primates. *PLoS ONE* 8(5):e66018. https://doi.org/10.1371/journal.pone.0066018
26. Yorzinski JL (2016). Eye blinking in an avian species is associated with gaze shifts. *Scientific Reports* 6:32471. https://doi.org/10.1038/srep32471
27. Dunham NT, McNamara A, Shapiro L, Phelps T, Wolfe AN, Young JW (2019). Locomotor kinematics of tree squirrels (*Sciurus carolinensis*) in free-ranging and laboratory environments. *Journal of Experimental Zoology A* 331(2):103–119. https://doi.org/10.1002/jez.2242
28. Hildebrand M (1977). Analysis of asymmetrical gaits. *Journal of Mammalogy* 58(2):131–156. https://doi.org/10.2307/1379571
29. Wölfer J, Aschenbach T, Michel J, Nyakatura JA (2021). Mechanics of arboreal locomotion in Swinhoe's striped squirrels. *Frontiers in Ecology and Evolution* 9:636039. https://doi.org/10.3389/fevo.2021.636039
30. Hunt NH, Jinn J, Jacobs LF, Full RJ (2021). Acrobatic squirrels learn to leap and land on tree branches without falling. *Science* 373(6555):697–700. https://doi.org/10.1126/science.abe5753 — author manuscript: https://pmc.ncbi.nlm.nih.gov/articles/PMC9446516/ — data: https://doi.org/10.6078/D11Q5Q
31. Boulinguez-Ambroise G, Dunham N, Phelps T, et al., Young JW (2023). Jumping performance in tree squirrels: insights into primate evolution. *Journal of Human Evolution* 180:103386. https://doi.org/10.1016/j.jhevol.2023.103386
32. Baldwin M, Wildlife Online: Squirrels, Food & Feeding — Feeding Behaviour (secondary; cites Newman et al. 1988, Polo-Cavia et al. 2010). https://www.wildlifeonline.me.uk/animals/article/squirrels-food-feeding-feeding-behaviour
33. Makowska IJ, Kramer DL (2007). Vigilance during food handling in grey squirrels, *Sciurus carolinensis*. *Animal Behaviour* 74(1):153–158. https://doi.org/10.1016/j.anbehav.2006.11.019 — abstract: https://czaw.org/?p=9845
34. Pardo MA, Pardo SA, Shields WM (2014). Eastern gray squirrels (*Sciurus carolinensis*) communicate with the positions of their tails in an agonistic context. *American Midland Naturalist* 172(2):359–365. https://doi.org/10.1674/0003-0031-172.2.359
35. McRae TR, Green SM (2014). Joint tail and vocal alarm signals of gray squirrels (*Sciurus carolinensis*). *Behaviour* 151(10):1433–1452. https://doi.org/10.1163/1568539X-00003194 — the flick < 45° / flag > 45° classes as summarised by Kaneda & Digweed (MacEwan University poster): https://journals.macewan.ca/studentresearch/article/download/1927/1247/3469
36. McRae T, interviewed in "Squirrel Talk: What Does That Noise Mean?", *Northern Woodlands* (secondary). https://northernwoodlands.org/outside_story/article/squirrel-talk
37. Partan SR, Larco CP, Owens MJ (2009). Wild tree squirrels respond with multisensory enhancement to conspecific robot alarm behaviour. *Animal Behaviour* 77(5):1127–1135. https://doi.org/10.1016/j.anbehav.2008.12.029 — https://digitalcommons.usf.edu/fac_publications/2688
38. Partan SR, Fulmer AG, Gounard MAM, Redmond JE (2010). Multimodal alarm behavior in urban and rural gray squirrels studied by means of observation and a mechanical robot. *Current Zoology* 56(3):313–326. https://doi.org/10.1093/czoolo/56.3.313
39. Meyer AF, O'Keefe J, Poort J (2020). Two distinct types of eye-head coupling in freely moving mice. *Current Biology* 30(11):2116–2130. https://doi.org/10.1016/j.cub.2020.04.042
40. Kalueff AV, Stewart AM, Song C, Berridge KC, Graybiel AM, Fentress JC (2016). Neurobiology of rodent self-grooming and its value for translational neuroscience. *Nature Reviews Neuroscience* 17:45–59. https://doi.org/10.1038/nrn.2015.8 — https://pmc.ncbi.nlm.nih.gov/articles/PMC4840777/
41. Comportamentos e atividade diária de *Sciurus ingrami* (Thomas) em cativeiro. *Revista Brasileira de Zoologia* 14 (1997). https://doi.org/10.1590/S0101-81751997000300019
42. Young JW, Chadwell BA, Dunham NT, McNamara A, Phelps T, Hieronymus T, Shapiro LJ (2021). The stabilizing function of the tail during arboreal quadrupedalism. *Integrative and Comparative Biology* 61(2):491–505. https://doi.org/10.1093/icb/icab096 (primates; the general case for a long tail cancelling body angular momentum)
43. Young JW, Chadwell BA (2020). Not all fine-branch locomotion is equal: grasping morphology determines locomotor performance on narrow supports. *Journal of Human Evolution* 142:102767. https://doi.org/10.1016/j.jhevol.2020.102767 (gray squirrels need the largest kinematic adjustment on narrow supports)
44. Tail signals in eastern gray squirrels include both generic and predator-specific alarms (ESA 2011 abstract, from the Companion Field Guide; the host's lookup failed here). https://eco.confex.com/eco/2011/webprogram/Paper32421.html
45. Macaulay Library assets ML406639, ML468702, ML441286 (video, © contributors). https://macaulaylibrary.org/asset/406639 , https://macaulaylibrary.org/asset/468702 , https://macaulaylibrary.org/asset/441286

Walls met and not worked around: Macaulay (Anubis proof-of-work), collections.si.edu (Cloudflare), MorphoSource
("Access Denied"), journals.biologists.com and repository.si.edu (403 to scripts), BioOne (bot check), DOAJ (403).
The Smithsonian 3D explorer was read in the Browser pane as an ordinary browser visit.
