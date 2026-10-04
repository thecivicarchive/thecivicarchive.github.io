# Adélie penguin (*Pygoscelis adeliae*): models and motion

Research notes for the companion builder, 2026-10-03. Two parts: (1) 3D models that could be used under the kit's
rules (licence allows a public website, downloadable without an account, from the maker's or an archive's own page),
and (2) how the real animal is built and moves, turned into numbers. Every figure says where it came from; figures the
sources did not give are marked **estimate** so the builder knows which are measured and which are a judgement.

Working conditions today: this machine's DNS dropped most lookups (the memory's "flaky router"), the session's web-search
budget ran out mid-way, and several hosts answer scripts with a bot check (Smithsonian, Macaulay Library, HAL, bioone,
science.org, digitalcommons). Nothing was worked around. Pages that could not be opened are listed as pointers, not
as sources, and nothing here is quoted from a page that was not read.

---

## 1. Models

**Verdict: no model found meets the rules and is true enough to the animal to build on. The builder sculpts the Adélie
in code from the notes below. Nothing was downloaded into `models/penguin/` and `credits.json` was not touched.**

What was looked at:

| Candidate | Page | Licence (as stated) | Format, size | Rigged / animated | Look | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| African penguin skeleton, Natural History Museum of the University of Pisa (AV 6822), uploaded by Patrizia17 | https://commons.wikimedia.org/wiki/File:Spheniscus_demersus_3d_scan_Natural_History_Museum_University_of_Pisa_AV_6822.stl | CC BY-SA 4.0 | STL, 172.7 MB (direct file https://upload.wikimedia.org/wikipedia/commons/f/f1/Spheniscus_demersus_3d_scan_Natural_History_Museum_University_of_Pisa_AV_6822.stl) | no / no | realistic surface scan of a mounted **skeleton**, bones only | Licence and download are fine, but it is a skeleton, of another genus (*Spheniscus*), and 172 MB. Not a companion mesh. Worth knowing about as a skeletal-proportion reference if anyone later wants to measure a real penguin skeleton; not downloaded (nothing of it would reach the page). The same museum's Commons category lists at least 100 STL scans; the only penguin among them is this one. |
| Emperor penguin, mounted taxidermy (DUNUC 12091, 108 cm), D'Arcy Thompson Zoology Museum, University of Dundee | https://app.dundee.ac.uk/museum/collections/zoology/zoology3d/emperorpenguin/index.html | none stated on the museum's page | OBJ with polypaint, Artec Eva scan | no / no | realistic scan of a stuffed bird (a 1892-93 specimen; taxidermy poses are stiff) | Out: offered only through Sketchfab, whose downloads need an account. |
| "Low Poly Penguin w/ Skeleton" by WarmHoneyBun | https://opengameart.org/content/low-poly-penguin-w-skeleton | CC-BY 4.0 | .blend, 1.3 MB (https://opengameart.org/sites/default/files/lowpoly_penguin_rig.blend) | rigged / no | cartoon low-poly | Licence fine; cartoon shapes, and a .blend needs Blender to convert. Not for a hyper-realistic look. |
| "Penguin low poly animated 3d model" by methodical pixel | https://opengameart.org/content/penguin-low-poly-animated-3d-model | CC0 | .blend in tar.gz, 126 KB, 684 triangles | rigged / animated | cartoon low-poly | Same as above. |
| "Penguin" by Poly by Google (and six more low-poly penguins: sugamo, jeremy, madtrollstudio, Damon Pidhajecky, Polygonal Mind) | https://poly.pizza/m/fBXvsC6pe_V and https://poly.pizza/search/penguin | CC-BY 3.0 (the Google one) | OBJ, glTF | no | stylized low-poly | Out for realism. |
| Quaternius animal packs (CC0) | https://quaternius.com/ | CC0 | GLB/glTF | yes / yes | stylized | No penguin in any pack (Ultimate Animated Animals, Farm Animals, Fish, Dinosaurs). |
| Kenney (CC0) | https://kenney.nl/assets?q=animal | CC0 | — | — | stylized | No penguin. |
| KayKit | https://kaylousberg.com/game-assets | CC0 | — | — | stylized | Site unreachable today (DNS); to my knowledge it has no animals. Not confirmed. |
| Smithsonian 3D | https://3d.si.edu/ | CC0 for its open-access objects | — | — | — | The site answers a script with a "Smithsonian request verification" page and its search runs by script; the Open Access API was unreachable. A web search of its pages turned up no penguin. **Not fully checked**: John can search "penguin" at 3d.si.edu in his browser in a minute. |
| MorphoSource / oVert CT scans | https://www.morphosource.org/ | varies | mesh / CT | — | skeleton/soft tissue | Out by rule: downloads need an account. |
| Sketchfab (many realistic penguin scans, e.g. the Dundee bird, "Lord of the Wings") | https://sketchfab.com/ | varies | — | — | realistic | Out by rule: downloads need a login. |
| Digital Life 3D (UMass Amherst) | https://www.digitallife3d.org/ | varies | — | — | realistic photogrammetry | Unreachable today; its models are served through Sketchfab, so out in any case. |
| Khronos glTF Sample Assets; three.js examples | https://github.com/KhronosGroup/glTF-Sample-Assets ; https://threejs.org/examples/ | CC-BY / mixed | GLB | some | — | No penguin (Duck, Fox; Flamingo, Parrot, Stork, Horse). |
| Marketplaces: CGTrader, TurboSquid/Free3D, RenderHub, Cults3D, Printables, MyMiniFactory; AI libraries such as Meshy | — | — | — | — | — | Not assessed: downloads need an account or a purchase, and a generated likeness is not a record of the animal's anatomy. Thingiverse's search is a script-only page and was not assessed. |

Realistic, rigged, CC0/CC-BY, account-free Adélie models do not seem to exist. The honest route is the one the kit
already takes: sculpt it, and spend the realism on motion.

---

## 2. The animal: build and measurements

### 2.1 Size (sourced)

- Standing height about 70 cm; 3 to 6 kg (Australian Antarctic Program: "weighing 3 to 6 kg and standing 70 cm tall").
  Length 70–73 cm, 3.8–8.2 kg over the year (Wikipedia). Williams 1995 via German Wikipedia: length 70 cm, females
  3.9–4.7 kg, males 4.3–5.3 kg. Levick 1914: "about two feet five inches in height" (74 cm). Chappell & Souza's wild
  birds averaged 4.007 kg. Use **H = 0.70 m** as the unit (the kit's root unit is the body height).
- Body temperature 39.3 °C (Chappell & Souza 1988): irrelevant to the look, but it is a warm, fast-metabolism bird.

### 2.2 Markings and soft parts (sourced)

- **The white eye-ring is the eyelids: bare skin, not feathers.** Levick (1914, soft-parts list): "Eyelids, black
  throughout the first year; pure white in the adult at fourteen months and onwards"; Shirihai via German Wikipedia:
  "ein auffälliger weißer Hautring" (a conspicuous white skin ring). So when the bird blinks, a **white lid** slides over
  a dark eye: the blink is a white flash, the most visible blink of any companion. Draw the ring as smooth skin, not
  plumage; it rides with the lids.
- **The whites of its eyes show.** Levick: the white lids increase "the white area of the sclerotic so that the bird has
  the appearance of being perpetually surprised or very angry". Animal Diversity Web (citing Ainley 2002): the threat is
  "a sideways stare with their crest raised and their eyes rolled downward". Iris brown (Levick: "reddish brown to
  greenish brown"). Give the eye a visible white sclera that shows more when the eye rolls down.
- Bill black, short, "largely feathered with only the tip exposed" (Wikipedia); the feathers cover about half of it
  (Animal Diversity Web); some reddish-brown at the base/gape in adults (Levick: "brick-red" gape; keep it brown, never
  red, per the colour rule).
- A small erectile crest on the back of the head (French Wikipedia: "une petite crête érectile"); raised in threat
  (ADW). Levick, quoting Gain: when tormented it "ruffles the black feathers which cover its back".
- Feet "pale flesh pink above, black beneath" (Levick; Williams via German Wikipedia: "mattweiß bis rosafarben, die
  Sohlen sind schwarz"); claws brown to black.
- Tail: long, stiff feathers (the genus name *Pygoscelis* is "rump-legged", the brush-tailed penguins; Wikipedia). The
  Adélie's tail is longer than its congeners' (German and Spanish Wikipedia). "The birds regularly use their tails for
  support, and the stiff feathers sweep the ground as the penguins walk" (Reilly 1994, via Wikipedia). Racovitza, via
  Levick: "tapering behind to a pointed tail that drags on the ground".
- Flippers: "paddles ... covered with very fine scale-like feathers" (Levick); black above with a thin white trailing
  edge, white beneath.

### 2.3 Skeleton in proportion

Measured:
- **Neck: 13 cervical vertebrae** held in an S-curve (Guinard et al. 2010, Polar Biology, *Morphology, ontogenesis and
  mechanics of cervical vertebrae in four species of penguins*; the HAL record https://hal.science/hal-00537386 refused
  the script, so the count is from the record's summary, not the paper's text). At rest the S is folded and the head
  sits on the shoulders; in display or alarm the S opens and the head rises by about a head's height (Levick:
  "stretching up its neck in a perpendicular line"; "stretch their necks up and take a good look").
- **Flipper joints are nearly rigid beyond the shoulder.** Raikow, Bicanovsky & Bledsoe 1988 (Auk 105:446–451) measured
  wing-joint mobility and found "great reduction in mobility of the intrinsic wing joints in penguins" (elbow, wrist,
  digits) against alcids and fliers. The flipper is one stiff blade moved at the shoulder. (Abstract via the SORA record
  https://sora.unm.edu/node/24581; the PDF sits behind a bot check and its degree figures could not be read.)
- **The leg is short and hidden.** Griffin & Kram 2000 attribute the high cost of penguin walking to "their short legs,
  and not their waddling gait". The femur and most of the tibiotarsus sit inside the feathered body contour; only the
  short tarsometatarsus and the toes show. (Standard penguin anatomy; Schreiweis 1982, *Smithsonian Contributions to
  Zoology* 341, is the full myology, at https://repository.si.edu/handle/10088/5410, which answered a verification page
  today.)

**Estimates** for the rig, as fractions of standing height H (from the measured sizes above and typical penguin
skeletons; check the hidden ones against a museum skeleton photo before trusting them to a millimetre):

| Part | Length ≈ | Notes |
| --- | --- | --- |
| Head, nape to bill tip | 0.19 H | skull ≈ 0.13 H plus exposed bill ≈ 0.055 H (culmen about 3.7–4 cm) |
| Eye diameter | 0.028 H | about 2 cm; set in the side of the head, axis yawed ≈ 70–80° from the bill line, pitched up ≈ 5° |
| Neck, retracted / stretched | 0.06 H / 0.16 H | the 13 vertebrae give a smooth curve: bend it as a chain of 3 animation joints (base, middle, atlas) |
| Torso, shoulders to vent | 0.48 H | widest at mid-belly, about 0.33 H across, 0.30 H deep |
| Flipper, shoulder to tip | 0.27 H | about 19 cm; blade ≈ 0.07 H wide at the base, tapering; hangs with the tip at mid-belly |
| Femur / tibiotarsus / tarsometatarsus | 0.09 / 0.16 / 0.055 H | ratio ≈ 0.57 : 1 : 0.32; femur near horizontal, knee flexed ≈ 90°, so the visible leg is only the tarsometatarsus (≈ 4 cm) |
| Foot, heel to middle claw | 0.11 H | three forward toes, webbed; a tiny hallux behind; toes spread ≈ 40° |
| Tail, vent to tip | 0.17 H | 12–16 stiff rectrices; the tip touches the ground when the bird leans back |
| Standing stance width | 0.14 H | feet toed out ≈ 10–15° |

### 2.4 Weight and posture (sourced)

- Upright on the toes and tarsometatarsi when walking; **rests back on heels and tail** (a tripod) when standing still for
  long (Reilly via Wikipedia: tails "for support"). Lean back ≈ 5–10° when settled (**estimate**).
- Dozing: "ruffling up his feathers sink into a doze"; waking: "opens his eyes, stretching himself, yawns, then finally
  walks off" (Levick). On the move a tired bird "stopped, ruffled up his feathers, closed his eyes for a moment, then
  'smoothed himself out' and went on again" (Levick).
- Sleeping or resting on snow: "lying on their breasts, with beaks outstretched", "chins outstretched on the snow"
  (Levick). Not for the dock (the companion stays upright) but the flop is a real pose.

---

## 3. How it moves

### 3.1 Breathing (sourced: Chappell & Souza 1988, *J. Comp. Physiol. B*)

- Resting rate **about 8 breaths a minute**: 7.96 ± 0.86 breaths/min between −20 and +10 °C; minimal 7.6–7.8; Murrish
  1982 reported 8. That is one breath every 7–8 s.
- The pattern is not a sine wave: "rapid inhalations and exhalations separated by 6–10 s apneas"; sleeping birds held
  "apneas of up to 35 s ... usually followed by 2–5 breaths in rapid succession". Rate climbs with heat to 54/min at
  30 °C (max 87) and the apneas disappear.
- After exertion the breathing is loud and fast: marching birds "seemed much out of breath, their wheezy respiration
  being distinctly heard" (Levick).

For the rig (the field guide wants breathing that never stops, so keep a faint continuous component):
- Calm: a quick breath, inhale 0.45 s (chest and back swell ≈ 2 % in width, ≈ 1.5 % in depth; the head lifts ≈ 0.003 H),
  exhale 0.6 s, then a near-still hold of 5–7 s with a continuous micro-swell of ≈ 0.3 % at 0.25 Hz; one visible breath
  every 6–8 s (irregular, ±1.5 s).
- Dozing (`rest`): hold 10–14 s, then 2–3 quick breaths 0.9 s apart.
- After `react`, `dance`, `arrive`: 25–35 breaths/min for 4–6 s, continuous, chest swell ≈ 3 %, throat pulsing; decay back
  to calm over the next 10 s.

### 3.2 Blinks

- Birds blink mostly with the nictitating membrane, which "moves horizontally across the eyeball" from the nasal corner
  (Wikipedia, *Nictitating membrane*). Measured in a songbird (great-tailed grackle): mean blink 0.067 s, almost never
  under 0.033 s, and about two thirds of blinks happen together with a head saccade (Yorzinski 2020, *Biology Letters*
  16:20200786). No penguin blink timings were found.
- On the Adélie the lids themselves are white (section 2.2), so a full lid blink reads as a white flash over the eye,
  while a membrane sweep is a faint grey flicker from the bill side.

For the rig:
- Two kinds of blink. Membrane sweep: 0.08–0.10 s total, a translucent grey veil from front to back, frequent. Lid blink:
  shut over 0.07 s, hold 0.04 s, open over 0.14 s (0.25 s total), white lids meeting a little below the eye's centre.
- Spacing 2.5–6 s, never on a beat (the kit already does this); about 1 in 7 blinks doubles. Time about two thirds of
  blinks to land within 0.1 s of a head turn (as in the grackles): the kit's `attend` snap can request a blink.
- The eye-roll (threat, display): iris turns down ≈ 20–25°, exposing more white above; 0.2 s in, held, 0.3 s out.

### 3.3 Looking: the one-eyed inspection (sourced: Levick 1914; Wikipedia *Bird vision*)

- Bird eyes move little in the socket (10–20°), so "head movements play a bigger role than eye movements", and many
  birds "orient themselves sideways to maximise visual resolution" on near objects (Wikipedia, *Bird vision*). Levick on
  an Adélie approaching a person: "he halts, poking his head forward with little jerky movements, first to one side,
  then to the other, using his right and left eye alternately ... He seems to prefer using one eye at a time when viewing
  any near object, but when looking far ahead, or walking along, he looks straight ahead of him, using both eyes. He does
  this, too, when his anger is aroused, holding his head very high, and appearing to squint at you along his beak."
  A searching bird "frequently poked his little head forward and from side to side, peering up".

For the rig (the reader is a near object, so the companion should look with one eye most of the time):
- Head yaw to present an eye: ±55–75° from straight ahead, reached in a 0.12–0.18 s snap (the kit's `snap` mode), held
  0.4–1.2 s, then a snap to the other eye about half the time. Add a forward poke of the head of 0.03–0.05 H with each
  snap (neck extends 0.02 H, head pitches down 8°), returning over 0.3 s. Let the body follow the head by 15 % of the yaw.
- Both-eyed stare (anger, far look): head high (neck +0.06 H), pitch up 15–20°, yaw 0, hold 1–2 s.
- Pitch range for the head: bill up to +85° (display), bill down to −60° (preening the breast); roll ±25° (head cock).
- Attention settles with weight: the kit's critically damped turn at ω ≈ 7–9 rad/s is right; add a 10 % overshoot on the
  yaw snaps and none on the pitch.

### 3.4 Walking: the waddle (sourced where marked)

Measured:
- Levick, Adélies on the march: "their stride amounts at most to four inches. Their rate of stepping averages about one
  hundred and twenty steps per minute" (2 steps/s, a 1.0 s stride cycle; his 10 cm is a short step: the travelling speed
  below needs 15–25 cm).
- Travelling speed on ice "averages 2.5 km/h" (Australian Antarctic Program) = 0.7 m/s; Williams via German Wikipedia:
  2.2–3.4 km/h (birds returning to nests) and 3.2–4.6 km/h (chick-rearing trips); French Wikipedia: 2 km/h with the
  pauses counted. So 0.5–0.7 m/s at 2–2.5 steps/s gives a step of 20–30 cm (0.3–0.4 H) when it means it, 10–15 cm when
  dawdling.
- King penguins (11–13 kg) walk at 1.4 km/h, "the modal speed within the breeding colony", at 1.27 ± 0.1 strides/s
  (2.5 steps/s) whatever their mass (Willener et al. 2016, PLoS ONE 11:e0147784); stride frequency, body acceleration
  and the waddle amplitude all rise with speed from 1.0 to 1.6 km/h, and the backward lean of the trunk decreases with
  speed (Willener et al. 2015, *J. Theor. Biol.* 387:166–173, abstract). Penguins stride at about twice the frequency of
  other birds of their mass.
- The rocking is the mechanism, not a flaw: emperor penguins recover up to 80 % of each stride's mechanical energy
  "because of similar amplitudes and out-of-phase fluctuations in gravitational potential and kinetic energies";
  "lateral movements increase the kinetic energy available to convert into gravitational potential energy", and the
  cost comes from the short legs (Griffin & Kram 2000, *Nature* 408:929, abstract; the full text could not be read
  here). So the body is highest when it has rolled furthest over the standing foot, and it looks effortless.
- Running: "each bird running, with wide gait, and outstretched flippers working" (Levick).
- Pinshow, Fedak & Schmidt-Nielsen 1977 (*Science* 195) put an emperor's top walking speed near 2.8 km/h at about
  85 steps/min (as relayed by UC Berkeley's 2000 release, which could not be opened today: secondary, unverified).

The waddle, in numbers (**estimates** built on the measured rates; stride cycle T = 1.0 s at a calm walk, 0.8 s hurrying;
duty factor 0.65 per foot, double support 15 % at each end):

| Phase of stride (fraction of T) | What happens |
| --- | --- |
| 0.00–0.15 | left foot lands flat (toes a hair first), double support, body lowest (−0.02 H), roll passing through zero toward the left |
| 0.15–0.50 | left single support; roll to the left reaches its peak **12°** (±10–14°) at 0.32; body highest (+0.01 H) at 0.32; right foot lifts at 0.15, swings low (clearance ≈ 0.02 H), toes drooping, knee hidden, reaching forward 0.3 H |
| 0.50–0.65 | right foot lands; double support; body lowest |
| 0.65–1.00 | right single support; roll to the right 12° at 0.82; body highest at 0.82; left foot swings |

- Yaw of the pelvis ±6° with the stride (the swinging side forward); pitch of the trunk a steady forward lean of 8–12°
  when walking (less when hurrying, per Willener 2015), bobbing ±2°.
- Head: counter-rolls about 40 % of the body roll, so the gaze stays steadier; small forward nod of 3–5° at each
  footfall (0.05 s after contact). Facing straight ahead while walking (Levick: both eyes).
- Flippers: held away from the body ≈ 20–30°, blade angled back 20° and tilted so the leading edge is down; each swings
  forward 10–15° with the opposite foot (left flipper forward as the right foot swings) and more, up to 45°, when
  hurrying or on rough ground.
- Tail: counters the roll by ≈ 5° and its tip brushes the ground at each roll extreme (Reilly: "the stiff feathers sweep
  the ground as the penguins walk").
- Stop: the last step is a half-step; the body settles with a damped roll of 2 cycles (amplitude 4°, period 0.5 s), then
  the weight goes back onto the heels and tail over 0.6 s.

### 3.5 Other ways of getting about (sourced: Levick; Animal Diversity Web)

- **Two-footed jump**: Adélies "walk upright with a waddling gait, progress by two-footed jump, or they can toboggan"
  (ADW, citing Ainley 2002). From the water they leap "exactly five feet" at most onto ice, "throw their legs well forward
  and land on their feet" on snow, or land on the breast on slippery ice (Levick). A standing hop: crouch 0.15 s (body
  down 0.05 H, flippers back), push 0.1 s, air 0.25–0.35 s for a rise of 0.1–0.2 H, land with knees (hidden) and a body
  dip of 0.04 H, flippers flung forward and up on take-off and down on landing (**estimates** of timing).
- **Tobogganing**: falls forward onto the breast and pushes "by alternate powerful little strokes of their legs behind
  them"; steers "with one or more strokes of the opposite flipper"; fleeing, uses both flippers and both feet (Levick).
  Not for the dock, but a real alternative to walking if a clip ever wants it.

### 3.6 Flippers (sourced: Raikow 1988; Levick; display descriptions)

- One stiff paddle rotating at the shoulder (Raikow). Ranges for the rig (**estimates** bounded by the anatomy): swing
  forward +60° / back −40° about the vertical; raise from hanging (≈ 15–20° off the body) to horizontal (90°) and a little
  above (110°) in display; long-axis rotation ±35° (the blade feathers so the leading edge dips); the "wrist" flexes no
  more than 10°.
- Display beating is slow: "flippers beating back and forth in time with breast heaving" (see 3.9), about 1–2 beats a
  second, 25–40° each way. Fighting blows are fast, "with the rapidity of a maxim gun" (Levick): 6–8 Hz, small amplitude.
- Stretch: both flippers back and up (raise 45°, back 30°), neck up, 1.5–2 s, with a shiver of 8 Hz × 0.3 s at the end
  (a common bird stretch; the kit's `idleB` variant 2 already does this).
- Preening "bill-to-axilla": one flipper lifts to 60–70°, the head turns 90–100° toward that side and down 40°, the bill
  works under the flipper with 6–8 Hz nibbles for 1–2 s; oiling reaches back to the gland at the tail base ("collecting
  waterproof oil from a gland near their tail with their beaks and spreading it over their feathers", IFAW; "well-oiled",
  California Academy of Sciences): head turned 150° and down, body twisted 20°.

### 3.7 Head-shake, ruffle, yawn (sourced where marked)

- **Head-shake**: Adélies "shake their heads" after discomfort (Levick). Marine birds shed salt-gland brine that "drips
  out" of the bill "and this gives the appearance of a runny nose", or "may also be sneezed out" (Wikipedia, *Salt
  gland*), so a quick sideways shake of the head is a constant penguin habit. Rig: yaw ±20–30° at 5–6 Hz for 0.3–0.5 s,
  roll ±8° a quarter-cycle behind, the whole body loosening by 2 % and the flippers lifting 5° (**timing estimate**).
- **Ruffle and smooth**: feathers lift (scale the body 3–4 % and the head 5 % over 0.3 s), held, then "smoothed out"
  over 0.5 s (Levick); happens when sleepy and when provoked (Gain, via Levick).
- **Yawn and stretch** on waking (Levick): bill opens 30–40° over 0.6 s with the neck stretched up 0.1 H, eyes narrowed,
  then closes; flippers lift 20° with it.
- **Body shake** (plumage shake after water, like a dog): head first, then a ripple down the body at 10–12 Hz for 0.5 s,
  tail wag last (**estimate**; common to all penguins).

### 3.8 Startle and threat (sourced: Levick, quoting Gain; ADW; California Academy)

- Provoked, the Adélie "faces its aggressor and ruffles the black feathers which cover its back. Then it takes a stand
  for combat, the body straight, the animal erect, the beak in the air, the wings extended, not losing sight of its
  enemy" (Gain, via Levick). The threat stare: "a sideways stare with their crest raised and their eyes rolled downward";
  apprehension: head feathers raised (ADW, citing Ainley 2002).
- The "slender walk" past other birds: "the body is stretched vertically, and the neck is elongated and the head held
  high" to signal no threat (California Academy of Sciences).
- Rig for a startle: in 0.12 s the neck shoots up 0.08 H and the body straightens (lean back 5°), flippers snap out to
  45°, feathers ruffle 3 %, one short step back (0.1 H) with a 6° roll; then a sideways stare at the cause (yaw 70°, eyes
  rolled down, crest up) held 0.8 s; then a head-shake and a slow settle over 1 s. The bird does not flee: "a brave
  animal, and rarely flees from danger" (Gain).

### 3.9 The displays (sourced: Levick; California Academy of Sciences; ADW; one relayed description)

- **Ecstatic display** (the species' signature). Levick: "The bird rears its body upward and stretching up its neck in a
  perpendicular line, discharges a volley of guttural sounds straight at the unresponding heavens. At the same time the
  clonic movements of its syrinx or 'sound box' distinctly can be seen going on in its throat." California Academy of
  Sciences: the penguin "stands with feet apart, slowly raises its head, pointing the beak upwards. Wings lifted outward,
  the chest heaves with an inhale of air, followed by a loud braying sound." The fuller sequence in the literature
  (Sladen 1958, Ainley 1975; relayed by Woods Hole's "How do I love thee" page, which could not be opened today, so
  treat the wording as secondary): the bird stands erect and slowly, deliberately stretches head and bill skyward, the
  bill opening as the head rises, flippers raised until nearly horizontal; breast and throat heave silently, then throb,
  then full braying with the head thrown back, bill wide, flippers beating back and forth in time with the heaves; a
  display may last up to a minute and is repeated many times. Marks, Brunton & Rodrigo (2010, *Behaviour*) found the
  call honestly predicts male condition (abstract page unreachable today).
- **Mutual display / bowing**: pairs "assume the 'ecstatic' attitude, rocking their necks from side to side as they faced
  one another" (Levick); "head-shaking and bowing" reinforce the bond (California Academy); courtship "neck arching and
  beak thrusting", the male "reaching his full height" (ADW; IFAW).
- A sleepy or appeased bird "hunching up his feathers and shutting his eyes" (Levick).

### 3.10 Tell-tale habits a viewer recognises at once

1. The sideways, one-eyed inspection with quick forward pokes of the head (3.3).
2. White eyelids blinking over a dark eye, and the whites showing when it rolls its eyes (2.2, 3.2).
3. The rocking waddle with the stiff tail brushing the ground, flippers held out for balance (3.4).
4. Bill to the sky, flippers out, chest pumping: the ecstatic display (3.9).
5. The quick head-shake that flicks brine off the bill (3.7).
6. The flipper-flap and two-footed hop (3.5, 3.6).
7. The ruffle-and-smooth of a sleepy bird, and the lean back onto heels and tail (2.4, 3.7).
8. Breathing as a quick breath then stillness, not a steady heave (3.1).

---

## 4. Numbers for the clips (the kit's list; every clip ends on the rest pose)

Angles in degrees, times in seconds, lengths in H (body height). Phase offsets as fractions of the clip.

- **Rest pose**: upright, trunk pitched forward 6°, weight slightly back (heels and tail touching), feet toed out 12°,
  flippers hanging 18° off the body and angled back 15°, neck folded, head yawed 20–25° to present one eye to the
  reader (the current `HEAD_YAW` of −0.42 rad is right), eyes open, lids showing white.
- **arrive (1.5–1.8 s)**: enter from off-canvas with 3 steps at 2.2 steps/s (stride cycle 0.9 s), step 0.3 H, roll ±12°,
  bob 0.02 H, flippers out 30° swinging ±12°, trunk lean 10°, head level and forward; from 0.65 to 0.85 the body turns
  toward the reader (yaw of the pose from −55° to −20°) with a half-step; 0.85–1.0 the damped settle (two roll cycles of
  4° at 0.5 s), weight back, flippers down, then a one-eyed snap to the reader at 0.92.
- **idleA (4–6 s)**: one quick breath at 0.1, the hold with micro-swell, a slow weight shift (roll 3° over 2 s and back),
  a second breath at 0.8; a single membrane blink mid-way; feet never move.
- **idleB (3–4 s), variants**: (a) head-shake 0.4 s at 5.5 Hz, yaw ±25°, then a ruffle 3 % and smooth; (b) bill-to-axilla
  preen 3 s as in 3.6; (c) flipper stretch 2 s with the 8 Hz shiver; (d) the sleepy ruffle-close-smooth 2.5 s (eyes shut
  0.8 s, lids white).
- **notice (~1.2 s)**: snap yaw toward the reader 0.15 s with a 0.04 H poke and a 10 % overshoot, hold 0.6 s, a lid blink
  on the snap, body follows 15 %, then release over 0.4 s.
- **react (~1.5 s)**: flipper-flap and hop: 0–0.15 crouch (body −0.05 H, flippers back 30°), 0.15–0.25 push, 0.25–0.55 in
  the air to 0.15 H with flippers flung up to 100° and the neck up 0.06 H, 0.55–0.7 land with a 0.04 H dip and flippers
  down, 0.7–1.0 two more flaps at 3 Hz of 60° and a head-shake, 1.0–1.5 settle with a damped roll.
- **talk (3 s loop)**: faces the reader two-eyed, neck up 0.03 H, small nods 4–6° at 1.2 Hz that are not on the beat
  (vary the interval ±30 %), a yaw snap to one eye once per loop held 0.6 s, breathing at the excited rate, flippers
  lifting 5–8° with each nod.
- **lookLeft / lookRight (~1 s holds)**: a one-eyed look: yaw 65° toward the side (so the far eye is turned to the point),
  poke 0.03 H, pitch down 8°, snap 0.15 s, hold, release; body follows 10 %.
- **rest (4–6 s loop)**: lids half closed (white showing at the top of the eye), the neck drawn in 0.02 H, head pitched
  down 10°, a 10–14 s breathing hold with two quick breaths, weight fully back on heels and tail (lean back 8°), feathers
  ruffled 2 %.
- **dance**: below.

## 5. The hover dance: "the little ecstatic" (2.2 s, silent, ends exactly at rest)

Built from the display every Adélie performs (3.9) and the head-shake (3.7). Five beats:

| Time (s) | Movement |
| --- | --- |
| 0.00–0.45 | Rises onto its toes (body +0.03 H), the neck opens from folded to stretched (+0.10 H, eased), bill tilts to the sky (pitch −80°, the bill opening 25° in the last 0.15 s), flippers rise from 18° to 90° with a 0.1 s lag behind the head, feet set a little apart (stance +0.02 H). |
| 0.45–1.55 | Three breast heaves at 2.7 Hz (chest and throat swell 4 % on each, the head rocking 6° up and back with each heave), flippers beating back and forth ±30° in time with the heaves (forward on the heave), the eyes rolled down so the whites show, the small crest up. A faint left-right rock of the whole bird of 4° at the heave rate, out of phase with the flippers. |
| 1.55–1.85 | The bill comes down and the neck folds (eased, slight overshoot of 5°); flippers drop to 35°. |
| 1.85–2.05 | A quick head-shake: yaw ±22° at 5.5 Hz, roll trailing by a quarter cycle; one white lid blink at the end. |
| 2.05–2.20 | Drops off its toes with a 0.015 H bounce, flippers settle to 18°, weight back onto heels and tail, head returns to the one-eyed rest yaw. Every channel at zero by 2.20. |

Alternative, if two dances are wanted: **"the greeting"** (1.8 s), from the mutual display: a bow (trunk pitch +25°, neck
out) 0.4 s, then the neck rocking side to side ±20° at 1.3 Hz for 0.9 s with the bill up 40° and flippers lifted 30°,
then a head-shake and settle.

Keep the colours as they are (black, white, greys, buff, pink feet; the gape's red-brown stays brown).

## 6. Notes on the present `penguin.js`

- Good already: the one-eyed rest yaw, white lids, the breathing hook, the preen and stretch idles, the flap-and-hop
  react, the kit's irregular blinks and damped attention.
- To change on the kit: add a neck chain (base, middle, atlas) so the head can rise 0.1 H in display and poke forward on
  looks; a white sclera on the eyeball that the iris can roll off; the tail long enough to touch the ground when leaning
  back; the arrive waddle at about 2 steps/s (the current 3.6 roll cycles in 1.44 s is 5 steps/s); the breath shaped as
  a quick breath then a hold rather than a continuous sine; the body highest at the roll extremes, not lowest; flippers
  swinging with the opposite foot; feet toed out and planted flat; the crest as a small raisable tuft.

---

## Sources

Read for these notes (the address is where the text was taken from):
- Levick, G. M. (1914). *Antarctic Penguins: A Study of Their Social Habits*. Project Gutenberg #36922.
  https://www.gutenberg.org/ebooks/36922 (plain text: https://www.gutenberg.org/cache/epub/36922/pg36922.txt). Gait
  (four-inch stride, 120 steps a minute, tobogganing, running), the one-eyed inspection, dozing and waking, the
  "ecstatic" attitude, mutual neck-rocking, leaps of five feet, the soft parts (white eyelids, brown iris, pink feet).
- Chappell, M. A. & Souza, S. L. (1988). Thermoregulation, gas exchange, and ventilation in Adelie penguins
  (*Pygoscelis adeliae*). *J. Comp. Physiol. B* (1988).
  https://biology.ucr.edu/people/faculty/Chappellpubs/PDFfiles/JCPBadelievent.pdf. Breathing rates and pattern, mass,
  body temperature.
- Willener, A. S. T., Handrich, Y., Halsey, L. G. & Strike, S. (2016). Fat King Penguins Are Less Steady on Their Feet.
  *PLoS ONE* 11(2): e0147784. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0147784. 1.4 km/h,
  1.27 strides/s.
- Willener, A. S. T., Handrich, Y., Halsey, L. G. & Strike, S. (2015). Effect of walking speed on the gait of king
  penguins: An accelerometric approach. *J. Theor. Biol.* 387:166–173. Abstract: https://pubmed.ncbi.nlm.nih.gov/26427338/.
- Griffin, T. M. & Kram, R. (2000). Penguin waddling is not wasteful. *Nature* 408:929. Abstract:
  https://www.nature.com/articles/35050167 (author's PDF at https://spot.colorado.edu/~kram/penguins.pdf is a scan; its
  body text could not be read here).
- Raikow, R. J., Bicanovsky, L. & Bledsoe, A. H. (1988). Forelimb joint mobility and the evolution of wing-propelled
  diving in birds. *Auk* 105:446–451. Record and abstract: https://sora.unm.edu/node/24581.
- Yorzinski, J. L. (2020). A songbird inhibits blinking behaviour in flight. *Biology Letters* 16:20200786.
  https://par.nsf.gov/servlets/purl/10283958. Blink duration and the link to head saccades.
- Jadwiszczak, P. (2001). Body size of Eocene Antarctic penguins. *Polish Polar Research* 22:147–158.
  https://www.czasopisma.pan.pl/Content/110730/PDF/2001-2_147-158.pdf (which bones are used for size; no Adélie figures).
- Jadwiszczak, P. & Mörs, T. (2011). Aspects of diversity in early Antarctic penguins. *Acta Palaeontologica Polonica*
  56:269–277. https://agro.icm.edu.pl/agro/element/bwmeta1.element.agro-fe2e6d80-4216-420f-8271-1766cd79959e/c/app20091107_269.pdf
  (no modern measurements).
- Australian Antarctic Program, Adélie penguins. https://www.antarctica.gov.au/about-antarctica/animals/penguins/adelie-penguins/
- Wikipedia, Adélie penguin (citing Reilly 1994 on the tail). https://en.wikipedia.org/wiki/Ad%C3%A9lie_penguin
- Wikipedia (German), Adeliepinguin (citing Williams 1995 and Shirihai). https://de.wikipedia.org/wiki/Adeliepinguin
- Wikipedia (French), Manchot d'Adélie. https://fr.wikipedia.org/wiki/Manchot_d%27Ad%C3%A9lie
- Wikipedia (Spanish), *Pygoscelis adeliae*. https://es.wikipedia.org/wiki/Pygoscelis_adeliae
- Wikipedia, *Pygoscelis*; Salt gland; Bird vision; Nictitating membrane. https://en.wikipedia.org/wiki/Pygoscelis ,
  https://en.wikipedia.org/wiki/Salt_gland , https://en.wikipedia.org/wiki/Bird_vision , https://en.wikipedia.org/wiki/Nictitating_membrane
- Animal Diversity Web, *Pygoscelis adeliae* (citing Ainley 2002). https://animaldiversity.org/accounts/Pygoscelis_adeliae/
- California Academy of Sciences, Common penguin behaviors. https://www.calacademy.org/explore-science/common-penguin-behaviors
- IFAW, Adélie penguins. https://www.ifaw.org/animals/adelie-penguins
- Sladen, W. J. L. (1958). The Pygoscelid penguins. I. Methods of study. II. The Adélie penguin. *FIDS Scientific
  Reports* 17. https://nora.nerc.ac.uk/id/eprint/511005/ (downloaded; a scan with no text layer, so only its plates could
  be looked at here. It is the primary description of the displays; worth reading in a browser.)
- Model pages: listed in the table in section 1.

Pointers not opened today (bot checks or failed lookups), named so the builder knows they exist:
- Ainley, D. G. (1975). Displays of Adélie penguins: a reinterpretation. In Stonehouse, B. (ed.) *The Biology of
  Penguins*; Spurr, E. B. (1975) Communication in the Adélie penguin, same volume; Penney, R. L. (1968)
  Territorial and social behavior in the Adélie penguin, *Antarctic Research Series* 12; Ainley, D. G. (2002) *The Adélie
  Penguin: Bellwether of Climate Change*.
- Pinshow, B., Fedak, M. A. & Schmidt-Nielsen, K. (1977). Terrestrial locomotion in penguins: it costs more to waddle.
  *Science* 195. https://www.science.org/doi/10.1126/science.835013 (UC Berkeley release on Griffin & Kram with
  the emperor figures: https://newsarchive.berkeley.edu/news/media/releases/2000/12/20_wadl.html).
- Guinard, G., Marchand, D., Courant, F., Gauthier-Clerc, M. & Le Bohec, C. (2010). Morphology, ontogenesis and mechanics
  of cervical vertebrae in four species of penguins. *Polar Biology* (2010). https://hal.science/hal-00537386
- Marks, E. J., Rodrigo, A. G. & Brunton, D. H. (2010). Ecstatic display calls of the Adélie penguin honestly predict
  male condition and breeding success. *Behaviour* (2010).
- Schreiweis, D. O. (1982). A comparative study of the appendicular musculature of penguins. *Smithsonian Contributions
  to Zoology* 341. https://repository.si.edu/handle/10088/5410
- Objective gait analysis in Humboldt penguins using a pressure-sensitive walkway (Brookfield Zoo), *J. Zoo Wildl. Med.*
  50(4), 2019. https://doi.org/10.1638/2019-0054
- Woods Hole Oceanographic Institution, "How do I love thee" (the ecstatic display sequence).
  https://www.whoi.edu/multimedia/how-do-i-love-thee
- Macaulay Library, Adélie penguin videos: https://search.macaulaylibrary.org/catalog?taxonCode=adepen1&mediaType=video
  (answers a script with a bot check; open it in a browser for slow-motion reference of the waddle, display and
  head-shake). Muybridge photographed no penguin: his bird plates are pigeons, a cockatoo, an ostrich, an eagle and storks.
