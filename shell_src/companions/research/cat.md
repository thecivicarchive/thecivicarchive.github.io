# Tabby cat (Felis catus): models and motion, for the companion builder

Research note, 2026-10-03, for the agent that rebuilds `shell_src/companions/cat.js`. Two parts: whether a licensed 3D
model exists that is worth building on (it does not; sculpt in code), and how a cat's body is proportioned and actually
moves, turned into numbers. Every figure carries its source; figures marked **(estimate)** are the researcher's reading
of photographs or Muybridge frames where no measured source was found, and the builder should treat them as a starting
point to be judged by eye in the still-frame lab.

Working conditions worth knowing: the web-search budget of the session ran out partway, and this machine's router drops
DNS lookups for some hosts (petmd.com, news.cornell.edu, animalfacs.com, icatcare.org, nga.gov, 3d.nih.gov, sloyd.ai,
uaiasi.ro never resolved in a dozen tries; 3d.si.edu and repository.si.edu answer scripts with a Cloudflare challenge,
which was not worked around). Facts from those pages are taken from search-result summaries and are flagged "(summary
only)". Everything else was read from the source page, PDF, PubMed abstract or image named.

---

## Part 1. Models

### 1.1 Rules applied

A model counts only if (a) its licence plainly allows use on a public website (CC0, CC-BY with credit, or equivalent), (b)
it downloads without an account, login, purchase, paywall or CAPTCHA, from the maker's or an archive's own page, (c) it is
a data file three.js can load with the loaders vendored in the kit (only `vendor/jsm/loaders/GLTFLoader.js` exists, so a
plain glTF/GLB with no Draco, meshopt or KTX2 compression; OBJ would need OBJLoader vendored from the same release), and
(d) it is true to the animal: a cat's build, not a toy's. The whole download must stay small (target under 2 MB
compressed per companion). Colours: only black, white, greys, browns and buff.

### 1.2 Every candidate found, with verdicts

**Quaternius, "Animated Animales Low Poly" (Animal Pack Vol.2, 3 Nov 2017), OpenGameArt.**
Page: https://opengameart.org/content/animated-animales-low-poly . Licence shown on the page: "CC0"
(http://creativecommons.org/publicdomain/zero/1.0/). Download: "Animal Pack Vol.2 by @Quaternius.zip", 2,069,972 bytes,
no account needed; fetched and inspected; SHA-256 `6d8f6789d65dbdb352ebad98a4209f26b41b384e87d81bc05e9ca76139db1248`.
Contents: Blend, FBX and OBJ for Wolf, Eagle, Dog, Cat, Piranha, plus Preview.png; **no glTF**. Cat.obj: 406 vertices,
402 faces (807 triangles), three flat materials named Grey, Pink, White; the FBX carries the rig and animations (the
page says animated; the binary FBX was not parsed here). Look (Preview.png): a flat-shaded, faceted low-poly tuxedo cat,
standing with the tail straight up; proportions roughly feline (body about 1.8 times the head, legs short) but a
cartoon. Verdict: licence perfect, anatomy not. Not used.

**Quaternius, "Cat" on poly.pizza (CC0 1.0), two models.**
- https://poly.pizza/m/qKICY6xla2 : GLB 238,672 bytes (SHA-256
  `842c5f96c480b9a7800994345ed83be5e9ba5fc8e18be633f2b7cfe09cf8fef7`), 2,448 triangles, one mesh, a 16-joint
  "AnimalArmature" (Root, Body, Head, Tail, FrontLeg.L/R, BackLeg.L/R with end bones), one PNG atlas texture, and
  eight clips: Idle (6.67 s), Idle_Eating (3.33 s), Walk (1.00 s), Run (0.67 s), Jump_Start (0.25 s), Jump_Loop (1.0 s),
  Headbutt (0.62 s), Death (0.88 s). Written by FBX2glTF 0.9.7, so GLTFLoader loads it as is. Look (preview): a
  **blocky, voxel-style cat** (box body, box head, box ears). Verdict: the only rigged, animated, CC0 cat in glTF found
  anywhere, and the wrong look entirely. Its clip lengths are a useful cross-check (a 1.0 s walk cycle, a 0.67 s run)
  and its bone list shows how little a quadruped rig needs, but nothing from it should reach the page.
- https://poly.pizza/m/2f54vbV0In : GLB 111,948 bytes (SHA-256
  `aa098d43c1006110d5a4fa3a6e6d4c843c8d8d90ffccc48f5bf32e3aadf7a3a9`), 1,772 triangles, 4 joints, clips Dance, Yes,
  No, Idle, Jump, Walk, Bite_Front, HitRecieve, Death; a **chibi cat head ("Cat_Blob")** with no body. Verdict: no.
poly.pizza itself: downloads need no login (the model page says "No login required"); it re-hosts Google Poly's
CC-BY 3.0 models and makers' CC0 uploads. Both files were fetched to the session scratchpad only, for inspection, and
were not copied into the project.

**Quaternius, "Ultimate Animated Animal Pack" (July 2021).** https://quaternius.com/packs/ultimateanimatedanimals.html .
"Models 12, Animated, Textured, Formats FBX OBJ Blend glTF, License CC0", "more than 12 unique animations" each. The
roster image (ultimateanimatedanimal.jpg) shows deer, stag, alpaca, fox, cow, bull, horse, donkey, wolf, husky and a
shiba; **no cat**. Verdict: no cat. If the builder wants a worked example of a CC0 quadruped GLB with walk, run and
idle clips to compare rig conventions against, this pack's fox or wolf is the cleanest one on the open web.

**poly.pizza search "cat"** (https://poly.pizza/search/cat, 32 results read from the page's embedded data): "Cat" and
"Kitten" by Poly by Google (CC-BY 3.0; the first "Cat", /m/6dM1J6f6pm9, is 594 triangles, static), "Dingus the cat",
"Tubbs the cat", "cat loaf" (Hiroyuki Kajiwara), "Cat" by J-Toastie, elkiotbear, jeremy, madtrollstudio, "Kitty"
(Corentin Fatus), plus Bobcat, Tiger, Cougar, Jaguar, Ocelot by Poly by Google, all CC-BY 3.0, all low-poly stylised.
Verdict: none is anatomical.

**OpenGameArt, others.** "Simple Cat" (drummyfish, CC0; https://opengameart.org/content/simple-cat): extremely low
poly, a walk made of two shape keys; no. "Cat Pilot (rigged + animated)" (CC0;
https://opengameart.org/content/cat-pilot-rigged-animated): an anthropomorphic cartoon pilot; no. "CC0 3D
Animals/Creatures" collection (josepharaoh99; https://opengameart.org/content/cc0-3d-animals-creatures): low-poly
Simple Cat, Tiger, Lion among others; no.

**Daily Lowpoly, "Lowpoly cat + run animation"** (https://dailylowpoly.itch.io/lowpoly-cat-running): FBX only
(cat_rigged.fbx, 390 kB), rigged with a run clip, name-your-price, no account needed; terms read "You can use this model
in commercial projects", which is not a licence that says anything about redistribution. Verdict: no (licence not
plainly stated; FBX; low-poly).

**Thingiverse, "Seated Curious Cat" by ottaross** (https://www.thingiverse.com/thing:5243945): a sitting cat sculpted
from scratch in Blender, STL, unrigged, untextured; licence **CC BY-NC 4.0**. The non-commercial clause is not a
licence that "plainly allows" by this project's rule, so it was not downloaded; John could decide otherwise for a
non-commercial site, but as an STL with no texture or rig it would only be a silhouette reference.

**Sloyd.ai, "decorative cat in low poly style, sitting"** (CC BY 4.0 per the search listing, GLB/FBX/OBJ/STL): a
parametric "decorative" model, not anatomical; the page never resolved from this machine (summary only). No.

**Kenney, "cubic pets"** (CC0, FBX/OBJ/glTF, 16 animated pets per the search summary): cubic style. No.

**Three D Scans** (https://threedscans.com/, Oliver Laric's museum-sculpture scans): the Info page lists the
institutions and supporters but **states no licence**, so it fails rule (a) regardless; a "Lion" sculpture is listed,
no domestic cat. No.

**Smithsonian 3D** (https://3d.si.edu/): answers scripts with a Cloudflare verification page (HTTP 403), not worked
around. Search summaries show no Felis catus 3D model; the Key Marco Cat statuette (a 600-year-old carving) is hosted
on Sketchfab, which needs a login to download, and the NMNH "Felis catus" records are specimen records without models.

**MorphoSource / oVert** (Felis catus CT scans exist): downloads need an account. Out by rule; thumbnails can still be
looked at for skeleton proportions. **Sketchfab, CGTrader, TurboSquid, Free3D, Cults3D, MyMiniFactory (Scan the World)**:
login, paywall or non-commercial terms. Out. **Wikimedia Commons**: one decorative "Cube Diorama – Cat in a Blanket.stl";
no. **NIH 3D Print Exchange**: never resolved from here; nothing expected (human anatomy). **Blender Studio open
films**: no cat character. **Poly Haven, ambientCG**: no animals (textures only). **Khronos glTF Sample Assets "Fox"**
(PixelMannen, CC-BY 4.0; rigged; Survey, Walk, Run): a canid, a different build; only a reference for how a small rigged
quadruped GLB is laid out for GLTFLoader.

### 1.3 Verdict

**No model is good enough to build on.** Nothing with a cat's real anatomy exists under CC0 or CC-BY without a login;
the only rigged and animated CC0 cats in glTF are a voxel toy and a chibi head. Nothing was copied into
`shell_src/companions/models/cat/` and nothing was added to `credits.json`. The builder sculpts the cat in code, from the
proportions and movements below and from Muybridge's plates 716 and 717 (public domain, Wellcome Collection, links in
Part 3), which show a tabby in side view at twenty-four and twenty consecutive phases.

What the sculpt should get right, from the plates and the literature: a long, low body (shoulder-to-hip 1.33 times the
forelimb length), the hind limb a third longer than the fore, a crouched stance with the shoulder blades riding above
the line of the back, a round skull with a short muzzle, a tail about as long as the body, and mackerel stripes that run
in vertical bars down the flanks and rings down the tail.

---

## Part 2. Motion

### 2.1 Skeleton in proportion

**Segments (measured).** Day & Jayne (2007), nine felid species including six domestic cats of 3.7 ± 0.2 kg
(3.3–4.0 kg): intergirdle distance (shoulder joint to hip joint) 32 ± 1 cm; forelimb length 24 ± 1 cm; hindlimb length
33 ± 1 cm. Segments as a share of limb length: humerus 36.8 %, radius 34.2 %, metacarpus 14.6 %, phalanges 14.1 %;
femur 34.7 %, tibia 32.4 %, metatarsus 22.1 %, phalanges 10.5 %. In centimetres for that cat: humerus 8.8, radius 8.2,
metacarpus 3.5, fore toes 3.4; femur 11.5, tibia 10.7, metatarsus 7.3, hind toes 3.5. Shoulder and hip heights stayed
at about 72–74 % of limb length across all felids: the crouched, digitigrade stance is the family's, from house cat to
tiger. Source: https://doi.org/10.1242/jeb.02703 .

**(estimate)** Not measured in that paper: scapula about 7–8 cm (it is the real top segment of the forelimb and
rotates visibly); head 9–10 cm from occiput to nose, 6–7 cm wide at the cheeks; tail 25–30 cm; standing shoulder
height about 23–25 cm, rump a little higher than the withers. In rig units with the sitting height as 1 (a sitting cat
is about 30 cm from floor to ear tips): shoulder-to-hip 1.05, forelimb 0.8, hindlimb 1.1, head 0.32 long, tail 0.9–1.0.

**Vertebrae.** 7 cervical, 13 thoracic, 7 lumbar, 3 sacral (fused), and a variable tail: Wikipedia's cat anatomy
article gives 19–21 caudal, veterinary case reports found by search give 20–23 (one 18–23). Use 20 for the tail.
Sources: https://en.wikipedia.org/wiki/Cat_anatomy ; vertebral-formula case reports (summary only). The forelimbs hang
from a free-floating clavicle (same page), which is why the shoulders move so freely and the chest narrows through
gaps. Toes: 5 in front (dewclaw off the ground), 4 behind; digitigrade.

**Neck at rest is vertical.** X-rays of unrestrained cats (and seven other species) show the cervical column standing
nearly vertical at rest, whatever the posture (lying, sitting, standing), as part of an S-shaped spine with an
inflection at C7/T1; raising and lowering the head happens mainly at the atlanto-occipital joint (skull on C1) and at
the cervico-thoracic junction (C7/T1), while the column between keeps its shape; **head yaw turns about the vertical
odontoid axis of C2**. At rest the head is carried pitched up about 5° (horizontal semicircular canals 5° above level)
and is brought level "presumably when the vigilance level increased". Vidal, Graf & Berthoz (1986), Exp Brain Res
61:549–559, https://pubmed.ncbi.nlm.nih.gov/3082659/ . Rig consequence: put the neck as a vertical column from the
C7/T1 inflection (top of the chest) to the skull base, a pitch joint at each end, the yaw joint at the top; "notice"
tips the head down about 5° as it comes level.

**Tail.** About 20 vertebrae, thick at the root, tapering: model as a chain of 6–8 segments with lengths 0.22, 0.18,
0.16, 0.14, 0.12, 0.10, 0.08 of the tail. The tail is a working counterweight: on a beam that was suddenly shifted
sideways, cats "responded to beam movement by rapidly moving the tail in the opposite direction", realigning the hips;
with the tail paralysed they fell more (Walker, Vierck & Ritz 1998, Behav Brain Res 91:41–47,
https://pubmed.ncbi.nlm.nih.gov/9578438/ ). So whenever the body leans or steps sideways, the tail swings the other way
first, 10–20° at the root, 40–60° at the tip (estimate of amplitude).

### 2.2 Joints: ranges and the walking pattern

**Hind limb, walking (measured).** A three-dimensional multiplane kinematic model of cats walking
(https://pmc.ncbi.nlm.nih.gov/articles/PMC6078300/): hip flexion–extension range 45–47° about a mean of ~102°
(internal–external rotation 13–15°, abduction–adduction 13–15°); stifle (knee) range ~37° about a mean of ~127°
(rotation 11–12°, ab/adduction 8–15°); tarsus (hock) range 24–30° about a mean of ~117° (rotation 11–25°, ab/adduction
5–9°). Pattern: "the hip extends throughout stance, reaching maximum extension at the end of stance ... then flexes
throughout swing"; the stifle "remains extended throughout stance, flexes in early swing"; the tarsus "flexes slightly
in early stance, remains extended throughout stance, flexes in early swing". The classic account, Goslow, Reinking &
Stuart (1973, J Morphol 141:1–41, https://pubmed.ncbi.nlm.nih.gov/4727469/ ), filmed 11 unrestrained cats walking,
trotting, galloping, jumping and landing and measured the lower spine, hip, knee, ankle and metatarsophalangeal angles;
Halbertsma (1983) adds that no element of the stride is fixed: durations of every phase shrink with speed, stance far
more than swing, the toe's position at touchdown stays almost constant, and hip, knee and ankle angles at touchdown are
correlated so the foot lands precisely (https://pubmed.ncbi.nlm.nih.gov/6582764/ ).

**Fore and hind, at footfall and midstance (measured; Day & Jayne 2007, domestic cat, 180° = straight):**
elbow 129° at footfall, 127° at midstance; wrist 184° at footfall (slightly hyperextended), 176° at midstance; knee
130° then 115°; ankle (hock) 118° then 114°.

**A walk cycle to animate (builder's curves, fitted to the figures above; p = phase 0–1 from this foot's touchdown;
stance ends at p ≈ 0.6).**

| joint | touchdown p=0 | midstance p=0.3 | lift-off p=0.6 | mid-swing p=0.8 | note |
|---|---|---|---|---|---|
| hip | 88° | 105° | 125° | 95° (flexing to 85° at p≈0.93) | extends all through stance |
| stifle | 130° | 115° | 138° | 98° | yields early, flexes hard early in swing |
| hock | 118° | 108° | 136° | 90° | small yield, push-off extension, flex to clear the toes |
| hind toes | flat | flat | roll to tip | curled under | |
| scapula | tipped back 12° | 0° | tipped forward 15° | swinging back | rotates about its upper third; the blade rises above the backline in stance |
| elbow | 129° | 127° | 150° | 80° | the big fore flexion is in swing: the paw lifts and folds |
| wrist | 184° | 176° | 195° | 130° | the paw flips back and under in swing, very visible |
| fore toes | flat | flat | roll to tip | curled | |

Body: the back stays level to within about 1 cm (2–4 % of shoulder height, two small rises per stride, **estimate**),
because a cat's walk is built for stealth, not economy: mechanical energy recovery averaged only 17.6 ± 11.3 %
(maximum 37.9 %), far below distance-walking mammals, with no relation to the vertical movement of the centre of mass
(Bishop, Pai & Schmitt 2008, https://pmc.ncbi.nlm.nih.gov/articles/PMC2583958/ ). The head holds a fixed height while
the shoulders rise and fall under it (Muybridge 716, frames 1–6: the ear line is level across all six frames while the
shoulder blades alternate).

### 2.3 Gaits: sequence, timing, duty factor

**Walk.** Lateral sequence: left hind, left fore, right hind, right fore (each hind foot followed by the fore foot of
the same side). Measured for domestic cats at 80 ± 3 cm/s: stride frequency 1.5 ± 0.07 Hz (cycle 0.67 s), duty factor
62 % fore, 59 % hind (Day & Jayne 2007); stride length therefore about 53 cm, 1.65 times the shoulder-to-hip distance.
Treadmill cats from 0.3 to 1.0 m/s: cycle 0.90–1.47 s at 0.3 m/s, 0.50–0.65 s at 1.0 m/s; hind stance 0.70–1.17 s at
0.3 m/s while **swing stays 0.20–0.30 s at every speed**; fore and hind of the same side are coupled about 90° apart
(the fore lands a quarter-cycle after the hind) at 0.3–0.4 m/s and about 60° at faster walks; diagonal limbs about 270°;
left and right 180°. Support sequence at a moderate walk: 3 feet, 4, 3, 2, 3, 4, 3, 2 (two feet down only briefly);
at 0.9–1.0 m/s: 3, 2, 3, 2 with no four-foot moments. Frigon et al. (2014), J Neurophysiol 111:1885–1902,
https://pmc.ncbi.nlm.nih.gov/articles/PMC4044364/ . Cats "often used footfall patterns with diagonality close to 25 %",
and the more crouched the cat, the more evenly spaced its footfalls and the less energy it recovered (Bishop 2008).
The walk-to-trot transition is at about 1 m/s (Froude 0.5) (Bishop 2008).

Numbers for the "arrive" walk at dock scale: cycle 0.8 s (a relaxed 0.6 m/s), duty 0.62, phases LH 0.00, LF 0.25,
RH 0.50, RF 0.75; swing 0.28 s for every foot (so stance = 0.52 s); each foot lifts 2.5–3 cm (about 0.1 of sitting
height) and the swing is a quick flick-forward with the paw curled, landing toe first with the wrist hyperextended.

**Tail in the walk (Muybridge 716, frames 1–6):** this cat walked with the **tail straight up**, tip bent back 15–25°,
the classic tail-up; in plate 717 the trotting cat carried it low and straight behind with a slight downward curve.
Both are real; tail-up is the friendly one (see 2.8).

**Trot (Muybridge 717, frames 1–6).** Diagonal pairs land together; head level; tail trailing, gently curved; body
long and low. Stride about 0.45 s (**estimate** from the speed range between the 1 m/s transition and the gallop).

**Gallop (Muybridge 716 frames 13–24; 717 frames 9–20).** Two flight phases per stride: an **extended** flight after
the hind legs push (body stretched flat, forelegs reaching, tail streaming back and lifting) and a **gathered** flight
after the forelegs push (back strongly arched, hind feet swinging forward past where the forepaws were). The spine does
much of the work: between the gathered and extended frames the back goes from a tight arch to flat or slightly hollow.
Stride about 0.3–0.35 s (**estimate**). The dock never needs a gallop, but the "dance" hop borrows the gathered-to-
extended spring.

**Walk into gallop (716 frames 7–12; 717 frames 7–10).** The cat first drops into a crouch: body lowers, head goes low
and forward, hind legs gather under the belly for two or three frames before the first bound, and **the tail swings up
into a hook at the moment of acceleration** (717 frames 7–9), then streams back once the gallop is running.
Public-domain plates: Wellcome Collection b20152619 (plate 716) and b20152620 (plate 717), Public Domain Mark; links
in Part 3.

### 2.4 Sitting, settling, the loaf

No measured kinematics exist for sitting; these are **(estimates)** read from photographs and the plates, in the paper
convention (180° = straight).

**Upright sit (the rest pose).** Forelimbs vertical and close together, elbow 155–165°, wrist 180° with the paws flat
and slightly turned out; scapula steep (about 60° from the horizontal); hind limb folded: hip 50–60°, stifle 35–45°,
hock 35–45°, feet flat under the haunches with the toes pointing forward; pelvis tipped back 40–50° from vertical;
lumbar spine rounded when relaxed, straightened when alert (the back lengthens about 3 %); chest lifted; neck vertical
(Vidal 1986) with the head pitched up 5° at rest; tail wrapped round the front paws (the commonest sit) or laid out
straight behind. Weight is on the haunches, so the front paws can lift without the body tipping, which is what makes
the pre-pounce treading and the "dance" readable in a sitting rig.

**Sitting down from standing (1.0–1.5 s).** The hindquarters sink first (hip and hock fold over 0.6–0.8 s), the forepaws
step back a little to land under the shoulders, the tail sweeps round last (0.4 s), and there is a 0.3 s settle at the
end as the weight comes onto the haunches.

**Settling / weight shift (idle B).** Drop 5–6 % of sitting height over 0.6 s, hold 1–1.5 s with the eyes narrowing
(lid 0.4–0.5), rise over 0.8 s; or a sideways weight shift of 1.5 cm with the tail base swinging 10° the other way
first (Walker 1998).

**The loaf.** Sternal recumbency: sternum on the ground, all four paws tucked under so none shows, back rounded, tail
wrapped along the flank, head up and level, eyes half closed; breathing shows most in the flank behind the ribs.
Grooming tends to follow a rest (Eckstein & Hart 2000, below), so a loaf that wakes should groom.

### 2.5 Head, eyes, ears, whiskers: how a cat attends

**Eyes move little; the head does the work.** Cats have an oculomotor range of only about ±25° against a field of view
of about ±70°, so any target further off is reached with a saccade-like head movement plus an eye saccade; the head
movement's peak velocity grows with its amplitude; "head movements terminated with the head on target"; "the eye saccade
usually lagged the head displacement" (Guitton, Douglas & Volle 1984, J Neurophysiol 52:1030–1050,
https://pubmed.ncbi.nlm.nih.gov/6335170/ ). Numbers to animate: a 30–45° turn to the pointer in 0.25–0.35 s with a
fast, slightly overshooting profile (critically damped, 5–8 % overshoot), eyes leading by 5–10° and then counter-rotating
as the head arrives; for targets inside ±20° the eyes alone move, 60–80 ms. The kit's yaw 0.85 rad (49°) and pitch 0.4
rad for the head are right; let the eyeballs take the first ±20°.

**Posture of attention.** From rest (head pitched up 5°) the head comes level and forward 1–2 cm, ears both forward,
pupils widen, whiskers forward: this is "vigilance" in Vidal's X-rays and the pre-pounce stare of 2.10.

**Ears (pinnae).** Measured with search coils (Populin & Yin 1998, J Neurosci 18:4233–4243,
https://pmc.ncbi.nlm.nih.gov/articles/PMC6792787/ ): to a sound the pinna begins to move after only **about 25 ms**
(short-latency component, 21–26 ms ± 15), then a second movement arrives with the eye saccade at about 265 ms; movements
to targets 18–23° off the midline were about 10°, up to about 20°; the two pinnae move **asymmetrically**, larger on the
side of the sound; with visual targets the pinnae move together with the eyes (r = 0.68) as part of the general
orienting response. Pet and veterinary sources say each pinna has 32 muscles and rotates up to 180° (FirstVet, Catit;
Wikipedia's anatomy page says 15 muscles: the count is contested, the mobility is not). CatFACS (Caeiro, Burrows &
Waller 2017) codes seven Ear Action Descriptors (forward, adductor, flattener, rotator, downward among them) alongside
15 facial Action Units. Numbers: idle ear flick, one ear only, rotate back 20–40° in 80–120 ms, hold 0.3–1 s, return in
150–250 ms, roughly one every 4–10 s; attention, both ears swivel toward the pointer 10–20° **25 ms before the head
starts**; relaxed, ears sit at about 30° off the midline, slightly out; startled, both flatten back and sideways
("airplane ears", 60–90°) within about 100 ms.

**Blinks are rare and asymmetric.** Alert laboratory cats blinked spontaneously only **0.2–0.5 times a minute**, each
blink "a fast, large downward lid movement followed by a slower up phase"; smaller, slower lid movements accompanied
peering and grimacing; the down phase of a typical 10° blink was about **ten times faster than the up phase**; a reflex
blink's downstroke lasts 25–30 ms (Gruart, Blázquez & Delgado-García 1995, J Neurophysiol 74:226–248,
https://pubmed.ncbi.nlm.nih.gov/7472326/ ). Clinical counts in awake pet cats: 5.0 ± 2.3 blinks/min in 53 healthy cats
(Oksa-Minaļto et al. 2023, https://pubmed.ncbi.nlm.nih.gov/36519689/ ), 3.0 ± 1.5/min in healthy controls (Sebbag et
al. 2021, https://pubmed.ncbi.nlm.nih.gov/33575276/ ), 4.1 ± 2.7/min while gazing at a person (Koyasu et al. 2021,
https://pmc.ncbi.nlm.nih.gov/articles/PMC8962689/ ). **So the Field Guide's generic 2.5–6 s between blinks is wrong for a
cat**: full blinks every 12–25 s (random, never on a beat), close in 40–60 ms, hold 30–50 ms, open in 200–300 ms;
between them, half-blinks (one lid moves part way, no closure) every 5–10 s while engaged, 150 ms down, 300 ms up.
Blinking and half-blinking were the facial actions most associated with **fear** in shelter cats, and relaxed engagement
with a right-side gaze and head-turn bias (Bennett, Gourkow & Mills 2017, https://pubmed.ncbi.nlm.nih.gov/28341145/ ), so
keep fast blinks sparse and let the greeting blink be slow.

**The slow blink (react).** Humphrey et al. (2020, Sci Rep 10:16503, https://pmc.ncbi.nlm.nih.gov/articles/PMC7536207/ )
define a half-blink ("one of the eyelids moves towards the other without ever closing the eye"), eye narrowing (lids
"held half closed" for at least 0.08 s) and eye closure (closed for more than 0.5 s), and a slow blink sequence as a
series of half-blinks followed by a prolonged narrowing or a closure; cats half-blinked and narrowed more after a
person slow-blinked at them, and approached a stranger more after a slow blink than after a neutral face. Timeline for
the 1.9 s react: two or three half-blinks at 0.25 s each, 0.3 s apart (lid 0.45–0.55), then lids to 0.9 over 0.35 s,
held 0.5–0.7 s, opened over 0.4 s; head tipped down 5° and ears half-back while the eyes are closed; nothing else moves.

**Pupils.** Vertical slits whose area changes **135-fold** between constricted and dilated (Malmström & Kröger 2006,
J Exp Biol 209:18–25, https://pubmed.ncbi.nlm.nih.gov/16354774/ ; the 135-fold figure is in the journal's "Inside JEB"
note, https://cob.silverchair.com/jeb/article/209/1/i/33393/ ). Animate the pupil as a slit 25–35 % of the iris width at
rest in a lit room, opening to 70–90 % (nearly round) in 0.3 s when startled or playing, closing back over 2–3 s.

**Whiskers.** "Most cats have 12 whiskers that are arranged in four rows on each cheek"; curious cats raise them; "if a
cat feels threatened, they will pull the whiskers on their muzzle taut, flare them, and then direct them forward"
(VCA Hospitals, veterinary authors, https://vcahospitals.com/know-your-pet/why-do-cats-have-whiskers ). "Whiskers bend
forward as the cat pounces"; cats do not whisk rhythmically the way rodents do (https://en.wikipedia.org/wiki/Whiskers ).
Numbers: rest, whiskers 10–15° back of lateral and drooping 10°; attention or pounce, swing forward 30–40° and spread
in 150 ms; fear, back against the cheeks 40° in 100 ms. Twelve a side, four rows, the top row shortest.

### 2.6 Breathing

Resting respiratory rate 15–30 breaths per minute (Cornell tip sheet, https://news.cornell.edu/node/320991 , summary
only; other veterinary pages give 20–30, down to about 15 in deep sleep). That is 0.25–0.5 Hz: the kit's 0.42 Hz (25 a
minute) is right for a sitting cat; use 0.28 Hz in "rest", and 0.6 Hz for 4–5 s after the dance, easing back. The
movement is in the ribs and the flank behind them (1.5–2 % of body width), with a slight rise of the shoulders; in a
loaf it is almost all flank. Add 13 % and 7 % slow wander to the rate as the kit already does; cats also sigh: one
breath in twenty 1.6× deeper, with a visible settle on the exhale.

### 2.7 Grooming, stretching, yawning (idle B material)

**Grooming is the cat's main fidget.** In 11 filmed cats, oral grooming took 4 % of the whole day and 8 % of waking
time; 91 % of bouts went to more than one body region, with a cephalocaudal trend (head first, tail end last); grooming
tended to follow sleep or rest; scratch-grooming took about a fiftieth of the time of licking (Eckstein & Hart 2000,
Appl Anim Behav Sci 68:131–140, https://pubmed.ncbi.nlm.nih.gov/10771321/ ). Of grooming time, **52 % goes to the face
and head**, 14 % sides and back, 9 % hind limbs, 8 % neck and chest, 3 % each to tail, abdomen and anogenital region
(Kim et al. 2018, J Feline Med Surg 21:373–378, https://pmc.ncbi.nlm.nih.gov/articles/PMC10814636/ ).

The face wash, the one everyone recognises (3.5–4 s): lift one forepaw to the mouth (0.3 s), lick its inner wrist 4–6
times at about 2 licks/s with the head nodding 10° each lick, then sweep the wet paw up over the ear and down the face
3 times (0.5–0.7 s a sweep, the paw rising above the ear line, the head tipping 15° away and the eye on that side
closing as the paw passes), then one more lick and the paw goes down (0.3 s); switch sides on the next bout. A flank
lick for variety: head turns 100–120° and down, spine bending, 3–5 licks, tail tip twitching.

**The stretch after rest (2–2.5 s):** forepaws slide forward, chest down to the ground, rump high, back sagging then
arching; then one hind leg extends straight back and shakes (0.6 s each). The stretch starts the same way a sitting cat
rises, so it reads as waking.

**Yawn (2–3 s):** mouth opens wide over 0.8 s, eyes close, ears go back 30°, tongue curls, closes over 0.6 s, a lick of
the lips after.

### 2.8 Tail signals and tail motion

The **tail up** (held vertical, tip often curled) is a greeting: kittens show it to their mother, adults show it when
meeting another cat "and it signals the intention to interact amicably"; it goes with rubbing and other friendly acts
(Cafazzo & Natoli 2009, Behav Processes 80:60–66, https://pubmed.ncbi.nlm.nih.gov/18930121/ ). Muybridge 716 shows the
tail-up carried through a whole walk. The tail counterbalances every lean (Walker 1998, 2.1). Twitching of the tip
while the cat watches something, and a full lash when annoyed, are the everyday observations (iCatCare's body-language
page, summary only); keep lashing out of the companion, it reads as anger.

Numbers: at rest the tail lies in a curve on the floor (round the paws), the tip lifting 1–2 cm and settling every 3–8
s; alert, tip flick sideways 20–40° in 0.15–0.25 s, one or two in a row, one every 3–8 s; tail-up, root rotates to
vertical in 0.4 s, segments following 60 ms apart (a wave travelling up), tip hooked forward 30–50°, with a 10 Hz
quiver of ±5° at the tip when it is a greeting; lowering takes 0.5–0.7 s with the same travelling wave. Base segments
move at 0.3–0.5 Hz at most; the tip carries the fast motion.

### 2.9 Startle and fear (so the builder knows what not to do, and how "notice" differs)

Leyhausen's (1979) descriptions, still the standard (via Bennett et al. 2017): the defensive cat arches its back, raises
its fur, flattens its ears sideways and back, dilates its pupils, bristles its tail and turns side-on. A mild startle:
freeze, ears swivel back and flatten, head pulls back and down, pupils widen, body crouches, whiskers back; recovery over
1–2 s with the ears coming forward first. Timings: ears 100 ms, crouch 150–250 ms, pupils 300 ms. None of this belongs
in the ordinary clips; "notice" is its opposite (ears forward, head comes level and forward, eyes to the pointer).

### 2.10 The pre-pounce wiggle (the raw material of the dance)

Leyhausen (1979, *Cat Behavior: The Predatory and Social Behavior of Domestic and Wild Cats*) describes the hunting
sequence as stalk, crouch, "treading" of the hind feet, and the spring. Veterinary summaries (petMD, vet-reviewed,
summary only): the cat crouches low and still, eyes fixed and pupils dilated, ears forward (or flattened to hide), then
raises its hind end and "quickly transfers weight back and forth between his two hind legs", swaying the back end,
before pushing off **with both hind legs at once** (walking alternates the hind legs; a pounce pairs them). Numbers
(**estimate** from footage): 3–5 weight shifts in 0.6–0.9 s (about 5 Hz), pelvis rolling ±5–8°, each hind foot
lifting about 1 cm in turn, head and eyes dead still throughout, tail tip quivering; take-off 0.12–0.18 s; a short
play-pounce is airborne 0.3–0.4 s and lands forepaws first.

### 2.11 The hover dance: proposal (2.2 s, ends exactly on the rest pose)

**"Pounce-play"**, built from 2.10 and the slow blink, sized to a dock where the cat sits facing the reader.

| time (s) | what happens | numbers |
|---|---|---|
| 0.00–0.25 | Attention snaps on: ears forward first, then the head comes level and forward, eyes fix on the pointer, pupils widen, whiskers forward. The chest drops into a play-crouch. | ears +15° toward the viewer at t=0 (25 ms lead); head pitch −5° and +0.05 forward; pupil slit 30 % → 75 % over 0.3 s; whiskers +30°; body py −0.06, shoulders forward +0.04 |
| 0.25–0.95 | Treading: the hind end rises a little and the weight rocks left-right at about 5 Hz, 3.5 cycles; forepaws stay planted; head counter-rotates so the eyes never leave the pointer; tail base straight back and low, tip quivering. | rump +0.03; pelvis/body rz ±6° (sin, 5 Hz); each haunch alternately +0.01 py; head rz = −0.8 × body rz; tail tip ±15° at 8 Hz |
| 0.95–1.10 | Take-off: both hind legs push together; body pitches up; forepaws lift and reach. | body rx −12°; mover py 0 → +0.08 by 1.25; shoulder flex 25°, elbow flex 40°, wrists curl 30° |
| 1.10–1.45 | A small hop in place: forepaws land first with wrists hyperextended, then the hind feet come under; a landing squash. | mover py back to 0 at 1.40; wrists +10° past straight at 1.38; body sy −4 % for 0.12 s; tail swings up 40° during flight (counterweight) |
| 1.45–1.85 | Settles into the sit with weight (critically damped, one small overshoot); ears relax to neutral; pupils narrow again. | return spring ω = 9 s⁻¹; ears → 30° out over 0.3 s; pupil 75 % → 30 % over 0.6 s |
| 1.50–2.20 | The greeting: the tail rises into a tail-up hook and comes down again as a travelling wave, and the eyes give one slow blink. Last frame is the rest pose. | tail root to vertical by 1.9 (segments 60 ms apart), tip hooked 40°, down by 2.2; lids to 0.9 over 0.3 s from 1.75, hold 0.15, open by 2.2 |

Variant for the "never twice in a row" rule, **"the greeting"** (2.0 s): tail up with a quivering tip (0.3 s up,
10 Hz quiver for 0.8 s), a head-bunt (the head rolls 20° and pushes forward 0.05 twice, 0.4 s each, as if rubbing a cheek
on the reader's hand), one slow blink, tail down to rest. Both are movements the real animal makes toward someone it
likes (Cafazzo & Natoli 2009; Humphrey et al. 2020).

### 2.12 Clip by clip, in numbers

- **arrive (1.5–2.0 s):** walk in from the edge with the tail up (2.3 numbers), 2 strides, head level; stop with the
  forepaws, then sit (2.4: 1.0 s), tail sweeping round last, settle 0.3 s. Ends on rest.
- **idle A (4–6 s loop):** breathing 0.42 Hz with wander; a half-blink at 2–3 s; one ear flick; the tail tip lifts and
  settles; the eyes drift a few degrees and return.
- **idle B (species fidget), variants:** tail-tip flick (1.6 s); one ear rotates back, holds, returns, then the other
  (2.4 s); face wash (3.5–4 s); settle lower with eyes narrowing (3.6 s); a yawn (2.5 s, rarely).
- **notice (1.2–1.4 s):** ears forward (t=0), head to the pointer in 0.3 s with a 5–8 % overshoot, pitch comes level,
  pupils open slightly, whiskers forward; hold; drift back over 0.5 s.
- **react (1.9 s):** the slow blink of 2.5 (half-blinks, then a closure of 0.5–0.7 s), head tipped down 5°, ears half
  back while closed.
- **talk (3 s loop):** attentive: ears forward, small head nods of 3–4° at about 1 Hz, half-blinks, tail tip swaying
  0.5 Hz, pupils a little wider than rest.
- **lookLeft / lookRight (1.2 s):** head yaw 45–50° in 0.3 s (saccade-like, eyes leading 10° then counter-rotating),
  hold, return over 0.4 s with weight.
- **rest (4–6 s loop):** breathing 0.28 Hz, lids 0.6, head pitched up 5° (Vidal's resting carriage), back rounded,
  tail still; one slow half-blink.
- **dance:** 2.11.

### 2.13 Tell-tale habits a viewer recognises at once

The tail-up walk with the hooked tip; the slow blink; ears that swivel one at a time, and toward a sound before the
head turns; the face wash with a licked paw; the loaf with no paws showing; the stretch with the chest down and rump
up; the rump-wiggle before a pounce; whiskers that come forward when curious; the sit with the tail wrapped over the
front paws; the tail tip twitching while the eyes stay fixed; a head that turns instead of eyes that roll (eyes stop at
25°); the back that arches and flattens in a bound. None of them is a generic "pet" movement; all of them are in the
numbers above.

---

## Part 3. Sources

Measured locomotion and anatomy
- Day, L.M. & Jayne, B.C. (2007). Interspecific scaling of the morphology and posture of the limbs during the
  locomotion of cats (Felidae). J Exp Biol 210:642–654. https://doi.org/10.1242/jeb.02703
- Bishop, K.L., Pai, A.K. & Schmitt, D. (2008). Whole body mechanics of stealthy walking in cats. PLoS ONE 3(11):e3808.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC2583958/
- Frigon, A. et al. (2014). Speed-dependent modulation of phase variations ... during quadrupedal locomotion in intact
  adult cats. J Neurophysiol 111:1885–1902. https://pmc.ncbi.nlm.nih.gov/articles/PMC4044364/
- A three dimensional multiplane kinematic model for bilateral hind limb gait analysis in cats (2018).
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6078300/
- Goslow, G.E., Reinking, R.M. & Stuart, D.G. (1973). The cat step cycle: hind limb joint angles and muscle lengths
  during unrestrained locomotion. J Morphol 141:1–41. https://pubmed.ncbi.nlm.nih.gov/4727469/
- Halbertsma, J.M. (1983). The stride cycle of the cat. Acta Physiol Scand Suppl 521:1–75.
  https://pubmed.ncbi.nlm.nih.gov/6582764/
- Vidal, P.P., Graf, W. & Berthoz, A. (1986). The orientation of the cervical vertebral column in unrestrained awake
  animals. I. Resting position. Exp Brain Res 61:549–559. https://pubmed.ncbi.nlm.nih.gov/3082659/
- Walker, C., Vierck, C.J. & Ritz, L.A. (1998). Balance in the cat: role of the tail and effects of sacrocaudal
  transection. Behav Brain Res 91:41–47. https://pubmed.ncbi.nlm.nih.gov/9578438/
- Wikipedia, Cat anatomy (vertebral counts, clavicle, digitigrade stance, toes). https://en.wikipedia.org/wiki/Cat_anatomy

Head, eyes, ears, whiskers
- Guitton, D., Douglas, R.M. & Volle, M. (1984). Eye-head coordination in cats. J Neurophysiol 52:1030–1050.
  https://pubmed.ncbi.nlm.nih.gov/6335170/
- Populin, L.C. & Yin, T.C.T. (1998). Pinna movements of the cat during sound localization. J Neurosci 18:4233–4243.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6792787/
- Gruart, A., Blázquez, P. & Delgado-García, J.M. (1995). Kinematics of spontaneous, reflex, and conditioned eyelid
  movements in the alert cat. J Neurophysiol 74:226–248. https://pubmed.ncbi.nlm.nih.gov/7472326/
- Oksa-Minaļto, J. et al. (2023). Ocular surface physiology and aqueous tear secretion in cats of diverse cephalic
  conformations. Vet Ophthalmol 26 Suppl 1:109–118. https://pubmed.ncbi.nlm.nih.gov/36519689/
- Sebbag, L. et al. (2021). Altered corneal innervation and ocular surface homeostasis in FHV-1-exposed cats.
  Front Vet Sci 7:580414. https://pubmed.ncbi.nlm.nih.gov/33575276/
- Koyasu, H. et al. (2021). Mutual synchronization of eyeblinks between dogs/cats and humans.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8962689/
- Humphrey, T. et al. (2020). The role of cat eye narrowing movements in cat–human communication. Sci Rep 10:16503.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7536207/
- Bennett, V., Gourkow, N. & Mills, D.S. (2017). Facial correlates of emotional behaviour in the domestic cat.
  Behav Processes 141:342–350. https://pubmed.ncbi.nlm.nih.gov/28341145/
- Caeiro, C.C., Burrows, A.M. & Waller, B.M. (2017). Development and application of CatFACS. Appl Anim Behav Sci
  189:66–78. Manual: https://animalfacs.com/catfacs_new (host unreachable from this machine; counts of 15 AUs, 6 ADs
  and 7 EADs from the Portsmouth and NTU records found by search,
  https://researchportal.port.ac.uk/portal/en/publications/development-and-application-of-catfacs(d90fe259-e2f5-40d7-80eb-c0ca1293686a).html )
- Malmström, T. & Kröger, R.H.H. (2006). Pupil shapes and lens optics in the eyes of terrestrial vertebrates. J Exp Biol
  209:18–25. https://pubmed.ncbi.nlm.nih.gov/16354774/ ; "Why some creatures have slit-shaped pupils" (Inside JEB,
  135-fold): https://cob.silverchair.com/jeb/article/209/1/i/33393/
- VCA Hospitals, Why do cats have whiskers? (Barnes, Dagner, Hunter, Buzhardt, DVMs).
  https://vcahospitals.com/know-your-pet/why-do-cats-have-whiskers
- Wikipedia, Whiskers. https://en.wikipedia.org/wiki/Whiskers
- Ear muscle count and 180° rotation (pet/veterinary sites, 32 muscles): https://firstvet.com/us/articles/10-cool-and-interesting-facts-about-your-cats-ears ;
  https://www.catit.com/spotlight/cat-senses-quiz-hearing-march-2025/

Behaviour
- Eckstein, R.A. & Hart, B.L. (2000). The organization and control of grooming in cats. Appl Anim Behav Sci 68:131–140.
  https://pubmed.ncbi.nlm.nih.gov/10771321/
- Kim, H.S. et al. (2018). Evaluation of grooming behaviour and apparent digestibility method in cats. J Feline Med Surg
  21:373–378. https://pmc.ncbi.nlm.nih.gov/articles/PMC10814636/
- Cafazzo, S. & Natoli, E. (2009). The social function of tail up in the domestic cat. Behav Processes 80:60–66.
  https://pubmed.ncbi.nlm.nih.gov/18930121/
- Leyhausen, P. (1979). Cat Behavior: The Predatory and Social Behavior of Domestic and Wild Cats. Garland STPM Press
  (cited through Bennett et al. 2017; https://search.ub.tum.de/vufind/Record/DE-604.BV007522844 )
- Stanton, L.A., Sullivan, M.S. & Fazio, J.M. (2015). A standardized ethogram for the Felidae. Appl Anim Behav Sci
  173:3–16. https://repository.si.edu/items/0b86a7e7-0dc5-4976-8650-9f1f1a8a838a (behind a challenge page for scripts;
  abstract read via AGRIS: https://agris.fao.org/search/en/records/65df0e0e63b8185d9caa8022 )
- petMD, Why do cats wiggle before they pounce? (vet-reviewed; summary only).
  https://www.petmd.com/cat/behavior/why-do-cats-wiggle-their-butts-they-pounce
- Cornell Chronicle tip sheet on feline respiratory rate (summary only). https://news.cornell.edu/node/320991
- International Cat Care, Cat body language (summary only). https://icatcare.org/advice/cat-body-language/

Frame-by-frame photographs (public domain)
- Muybridge, E. (1887). Animal Locomotion, plate 716: cat walking, changing to a gallop (24 frames). Wellcome
  Collection b20152619, "A cat running", Public Domain Mark: https://wellcomecollection.org/works/y6rt665e ; image
  https://iiif.wellcomecollection.org/image/B20152619.JP2/full/2400,/0/default.jpg ; also NGA
  https://www.nga.gov/collection/art-object-page.220470.html
- Muybridge, E. (1887). Plate 717: cat trotting, changing to a gallop (20 frames). Wellcome b20152620, Public Domain
  Mark: https://wellcomecollection.org/works/an4bpesp ; image
  https://iiif.wellcomecollection.org/image/B20152620.JP2/full/2400,/0/default.jpg
- Further Wellcome cat plates, same licence (not read here): b20152632, b20152644, b11862117. NGA plate 718 (trotting
  to galloping): https://www.nga.gov/collection/art-object-page.220471.html ; plate 720 (galloping):
  https://www.nga.gov/artworks/220472-plate-number-720-cat-galloping

Models looked at
- Quaternius, Animated Animales Low Poly (CC0): https://opengameart.org/content/animated-animales-low-poly
- Quaternius, Cat (CC0, GLB): https://poly.pizza/m/qKICY6xla2 and https://poly.pizza/m/2f54vbV0In
- Quaternius, Ultimate Animated Animal Pack (CC0, no cat): https://quaternius.com/packs/ultimateanimatedanimals.html
- poly.pizza cat search (CC-BY 3.0 / CC0 low-poly): https://poly.pizza/search/cat ; Poly by Google "Cat":
  https://poly.pizza/m/6dM1J6f6pm9
- OpenGameArt: https://opengameart.org/content/simple-cat ; https://opengameart.org/content/cat-pilot-rigged-animated ;
  https://opengameart.org/content/cc0-3d-animals-creatures
- Daily Lowpoly (itch.io, FBX): https://dailylowpoly.itch.io/lowpoly-cat-running
- Thingiverse, Seated Curious Cat (CC BY-NC 4.0): https://www.thingiverse.com/thing:5243945
- Sloyd.ai decorative cat (CC BY 4.0 per listing; unreachable): https://www.sloyd.ai/free-3d-models/model/3d-model-of-a-decorative-cat-in-low-poly-style-sitting-rgssm1bj
- Three D Scans (no licence stated): https://threedscans.com/info/
- Smithsonian 3D (challenge page for scripts): https://3d.si.edu/
- Khronos glTF Sample Assets, Fox (CC-BY 4.0, a canid): https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/Fox
- Kenney (CC0 cubic pets): https://kenney.nl/
