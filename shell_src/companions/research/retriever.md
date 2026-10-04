# Golden retriever (*Canis familiaris*): models and motion

Research notes for the companion builder. Written 2026-10-03 by the retriever research agent of the
`companions-models-and-motion` workflow. Everything below either quotes a source (address given) or is marked
**working value** (derived or estimated, with the reasoning). Nothing was downloaded into `models/` and nothing was
added to `credits.json`: see the verdict in section 1.

The rules applied: a model counts only if its licence plainly allows use on a public website (CC0, CC-BY with a
credit, or the like), it downloads without an account, login, purchase, paywall or CAPTCHA, and it comes from the
maker's or an archive's own page. The web-search budget of the session ran out partway (200 searches shared by the
seven research agents), so the second half of the work went through direct fetches of known addresses; the home
router dropped many lookups, and those pages were fetched again through the kit's patient downloader
(`states/net.py`). Two hosts (PubMed Central's table pages, MorphoSource) showed a CAPTCHA or bot wall and were left
alone.

---

## 1. Models

### Verdict

**No downloadable model of a golden retriever (or a dog of the same build) meets the rules, so the builder sculpts
the animal in code from section 2.** What exists under free licences falls into three groups, none of which is a
realistic retriever:

1. **Stylized low-poly game dogs with working rigs and clips** (Quaternius's Husky and Shiba Inu, CC0; the Khronos
   Fox, CC0 model with CC-BY 4.0 rig and animations; OpenGameArt's rigged Jack Russell, CC0). Good as a reference
   for a quadruped joint plan and clip list; wrong look (flat-shaded blocks), wrong breed.
2. **Museum scans of dog sculptures** (threedscans.com, the free archive of Oliver Laric's project): two seated
   greyhounds (the Townley Greyhounds, British Museum), two pack hounds standing (Vacossin, 1911), two sighthounds
   (Franzoni), a child with a small dog. Real anatomy, but stone (no eyes, fur or colour), sighthound or hound
   builds, two animals fused to a plinth, 43 to 45 MB of raw triangles each, no rig. Separating one dog, retopologising
   and rigging it would need a modelling tool the kit does not have, and the result would still be a greyhound.
3. **Everything that looks right is behind a login, a paywall or a "personal use only" licence** (Sketchfab, CGTrader,
   TurboSquid, Fab, RenderHub, Free3D, Printables, MakerWorld, Cults, MyMiniFactory), or is re-hosted with no
   provenance (remeshy.com's "free STL" pages). Out by the rules.

The one thing worth borrowing from group 1 is the joint plan of the Khronos Fox (section 2.1), which is the simplest
proven canid skeleton for real-time animation.

### Every candidate checked

| Source and page | Licence (as the page states it) | Format, size, polygons | Rigged / animated | Look | Verdict |
| --- | --- | --- | --- | --- | --- |
| **threedscans.com, The Townley Greyhounds** (British Museum, marble, 1st–2nd c., H 59.7 cm) https://threedscans.com/uncategorized/the-townley-greyhounds/ ; file https://threedscans.com/wp-content/uploads/2020/02/Townley-Greyhounds.OBJ.zip | The pages carry no licence line in their markup; the archive calls itself a "Free 3D scan archive", downloads are a plain link with no account, and the project has stated since 2016 that every scan is free to download and use without copyright restrictions (reported by BlenderNation, 2016). Confirm by mail (contact@threedscans.com) before any use. | OBJ in a zip, 42,839,024 bytes (43 MB); raw scan, millions of triangles | No | Realistic marble: two greyhounds seated, one licking the other's ear | Not to build on: sighthound build, two dogs on a plinth, stone, unrigged |
| **threedscans.com, "Deux chiens de meute à l'attache"** (Georges Lucien Vacossin, 1911, Dépôt des sculptures de la Ville de Paris, 105 × 125 × 135 cm) https://threedscans.com/depot-des-sculptures-de-la-ville-de-paris/deuxchiensdemeutealattache/ ; file https://threedscans.com/wp-content/uploads/2016/10/Georges-Lucien-Vacossin.OBJ.zip | as above | OBJ zip, 45,227,134 bytes (45 MB) | No | Realistic sculpture (material not stated on the page): two pack hounds standing, tied; the closest build to a retriever among the scans (drop ears, deep chest, long tail) | Not to build on for the reasons above; the best **silhouette reference** if the builder wants one |
| threedscans.com, "Gruppe mit zwei Windhunden" (Franzoni, 1770–90, Tiroler Landesmuseum) https://threedscans.com/ferdinandeum-innsbruck/gruppe-mit-zwei-windhunden/ ; "Enfant au Chien" (Roman, Musée de la Romanité) https://threedscans.com/musee-de-la-romanite/enfant-au-chien/ ; "Hunter and Dog" (Lincoln) https://threedscans.com/lincoln/hunter-and-dog/ | as above | OBJ zips | No | Sighthounds; a small dog; a hunting group | No |
| **Quaternius, Ultimate Animated Animal Pack** (July 2021) https://quaternius.com/packs/ultimateanimatedanimals.html | "License CC0" (linked to creativecommons.org/publicdomain/zero/1.0/); "free to use in personal and commercial projects" | glTF, FBX, OBJ, Blend; the glTF folder holds Alpaca, Bull, Cow, Deer, Donkey, Fox, Horse, Horse_White, **Husky**, **ShibaInu**, Stag, Wolf, each 1.4 to 3.4 MB; "Textured" is unchecked (flat colours) | Yes, "more than 12 unique animations" each (Attack, Death, Kicks, Gallops, Walk, Jump ...) | Low-poly, blocky, stylized | The best rigged CC0 dog there is, but not a realistic look and not a retriever. Download is a public Google Drive folder, no account: folder `1uJ3N5HfB7jKTseJUNQr3N4YaN0UuEtHk`, glTF subfolder `1yJXdB1iSrI8Db7hG77zxZ66vKsqIt0ry` (its License.txt answered "quota exceeded" on 2026-10-03; the pack page states CC0) |
| Quaternius, Animal Pack Vol. 2 (wolf, eagle, dog, cat, piranha) https://opengameart.org/content/animated-animales-low-poly ; Farm Animals (pug, dog ...) https://opengameart.org/content/lowpoly-animated-farm-animal-pack | "CC0" | FBX (2.1 MB); Blend/OBJ/FBX (7 MB) | Yes | Low-poly | No (look) |
| **Khronos glTF Sample Assets, Fox** https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/Fox (README quoted from https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/Fox/README.md) | "© 2014, Public. Creative Commons Zero v1.0 Universal" (model, PixelMannen); "© 2014, tomkranis. Creative Commons Attribution 4.0 International" (rigging and animation); "© 2017, @AsoboStudio and @scurest. Creative Commons Attribution 4.0 International" (glTF conversion) | glTF + Fox.bin + Texture.png; 1,728 vertices; 24 joints | Yes: Survey, Walk, Run | Low-poly fox | Not a retriever; **copy its joint plan** (section 2.1) |
| OpenGameArt, "Dog Low Poly (Rigged)" by crownjoshua https://opengameart.org/content/dog-low-poly-rigged | "CC0" | Blend 818 KB, OBJ 44 KB; 1,428 vertices | Rigged, no clips | Low-poly Jack Russell | No |
| OpenGameArt, "Benny, the Rottweiler" (found in search) | CC-BY-SA 3.0 | Blend | Rigged and animated | Low-poly Rottweiler | No (share-alike licence, wrong breed) |
| poly.pizza: Quaternius Husky https://poly.pizza/m/wcWiuEqwzq , Shiba Inu https://poly.pizza/m/y4wdQpg767 ("Public Domain (CC0)"), German Shepard https://poly.pizza/m/Hssa6NPc6W ("Creative Commons Attribution"); Poly by Google Beagle https://poly.pizza/m/0BnDT3T1wTE , Puppy, Dog (CC BY 3.0); Pat Siefring Greyhound https://poly.pizza/m/eO3-2e_AkxH (CC BY 3.0) | as shown | FBX / glTF, OBJ | Quaternius ones animated | Low-poly | The Beagle page said login is required to download, so the archive route is out; Quaternius's own site serves the same dogs without one |
| Smithsonian 3D https://3d.si.edu/ | CC0 | — | — | — | Only a dire wolf skull (*Canis dirus*, USNM V8306): https://3d.si.edu/object/3d/canis-dirus-leidy:6796319b-6445-435f-994b-2f40fd8d08e4 . No dog |
| Thingiverse, "CF Dog – Golden Retriever" by AR3DP https://www.thingiverse.com/thing:7180988 | Listed as Creative Commons – Attribution in search results; the page is script-drawn and its description sells "a commercial license to sell prints" through Patreon | STL | No | Faceted "crystal" style, seated | No (stylized facets; licence wording not re-read on the page) |
| Wikimedia Commons (STL search "golden retriever") https://commons.wikimedia.org/w/index.php?search=golden+retriever+filemime%3Aapplication%2Fsla&ns6=1 | — | — | — | — | No results |
| MorphoSource / oVert https://www.morphosource.org/ | CC0 / CC BY / CC BY-NC by specimen | CT meshes | No | Skeletons | Catalogue answered with a bot wall (Anubis) and downloads need an account: out by the rules; a *Canis familiaris* skeleton would be a proportion check only |
| Kenney (Cubic Pets, glTF, CC0) https://kenney.nl/assets/cubic-pets | CC0 | glTF | animated | cubic | Page answered 404 on 2026-10-03; cubic style is wrong anyway |
| Digital Life 3D https://digitallife3d.org/ | CC BY-NC-ND typical | — | — | photogrammetry of living animals | No dog in the catalogue |
| remeshy.com "free STL" golden retrievers | not stated; re-hosted files | STL/GLB | No | mixed | Out: no provenance |
| Sketchfab, CGTrader, TurboSquid, Fab, RenderHub, Free3D, Printables, MakerWorld, Cults3D, MyMiniFactory, SuperHive, Gumroad packs | login, payment, or personal-use terms | — | — | several realistic rigged goldens exist here | Out by the rules (John's decision: no purchases, no logins) |

Also looked at for motion rather than models: Truebones Zoo (Gumroad, no licence stated: out), the SMAL / RGBD-Dog
research models (research-only licences with registration: out).

---

## 2. Motion: how a golden retriever is built and moves

### Numbers at a glance (for the builder)

| Thing | Value | Source |
| --- | --- | --- |
| Height at withers H | males 23–24 in (58–61 cm), females 21.5–22.5 in; weight 65–75 lb males | AKC standard |
| Length (breastbone to buttocks) : height | 12 : 11 (body 1.09 H long) | AKC standard |
| Pelvis slope; femur–pelvis angle standing | about 30° from horizontal; about 90° | AKC standard |
| Spine | 7 cervical, 13 thoracic, 7 lumbar, 3 sacral (fused), 20–23 tail vertebrae | canine osteology (Auburn) |
| Weight on the forelimbs | about 60 % fore, 40 % hind, standing and moving, whatever the size | Kano et al. 2016 |
| Resting breathing | 18–34 breaths/min (period 1.8–3.3 s); panting about 300/min | Merck Veterinary Manual; Meyer et al. 1989 |
| Blink rate | 2.4 ± 1.4/min (50 Shih Tzus) to 6.5 ± 3.8/min (7 pet dogs looking at a person): one blink every 9–25 s | Sebbag et al. 2023; Koyasu et al. 2022 |
| Sniffing | 4–7 Hz, bouts of 0.5 s to several seconds (includes a 52.9 kg Labrador) | Craven et al. 2010 |
| Wet-dog shake | 4.3–4.6 Hz in Labradors; amplitude 90 ± 10° (skin 60°, spine 30°) | Dickerson et al. 2012 |
| Walk | lateral sequence, lateral couplets in long-legged breeds (the Golden Retriever named); hind duty factor 0.58–0.63; 0.9–1.3 m/s; stride 0.73 s at 1 m/s for 22 kg dogs | Hildebrand 1968; Fischer et al. 2018; Kano et al. 2016 |
| Trot | diagonal couplets ("second figure about 50"); duty factor 0.39–0.47; 1.7–2.5 m/s; hind feet down slightly longer than fore (fore contacts 93–97 % of hind) | Hildebrand 1968; Fischer et al. 2018; Fu et al. 2010 |
| Hip excursion walking/trotting | 36–48° (large dogs 47–48°); the femur does most of the hind limb's swing | Fischer et al. 2018 |
| Head nod at the walk (Labradors, 0.98 m/s) | atlanto-occipital sagittal up to 16.8°, lateral 11.7°, axial 12.0°; atlanto-axial 9.7° / 7.8° / 15.8°; tied to forelimb stance and swing | Schikowski et al. 2021 |
| Sit-to-stand | 1.14 ± 0.16 s; hip 53°, stifle 78°, tarsus 89° of extension; hip 0–20 %, stifle 10–50 %, tarsus 25–60 % of the move | Ellis et al. 2018 (greyhounds) |
| Head tilt | shown in 43 % of trials by dogs that know toy names vs 2 %; each dog keeps the same side for months | Sommese et al. 2022 |
| Tail wag bias | to the dog's right for the owner (positive), left for a threat; the right bias grows over days of familiarity | Quaranta et al. 2007; Ren et al. 2022 |
| Puppy eyes (inner brow raise, AU101) | about twice as often when a person faces the dog (0.121 vs 0.056) | Kaminski et al. 2017 |
| Fear/startle sign | ears turned back at the base is the strongest sign (d = 0.68); more panting, moving, blinking | Gähwiler et al. 2020 |

Radians = degrees × 0.01745. The kit's joints take radians.

### 2.1 Skeleton and proportions

**The record (AKC breed standard, approved 1981):** "symmetrical, powerful, active dog ... not clumsy nor long in the
leg"; males 23–24 inches at the withers, females 21½–22½; "Length from breastbone to point of buttocks slightly
greater than height at withers in ratio of 12:11"; weight 65–75 lb (dogs), 55–65 (bitches). Head "broad in skull,
slightly arched ... Stop well defined but not abrupt. Foreface deep and wide, nearly as long as skull. Muzzle straight
in profile". Eyes "medium large with dark, close-fitting rims, set well apart and reasonably deep in sockets. Color
preferably dark brown"; "No white or haw visible when looking straight ahead". Ears "rather short with front edge
attached well behind and just above the eye and falling close to cheek. When pulled forward, tip of ear should just
cover the eye." Nose "black or brownish black". Neck "medium long, merging gradually into well laid back shoulders".
"Backline strong and level from withers to slightly sloping croup, whether standing or moving." Chest "deep", "Brisket
extends to elbow", "Ribs long and well sprung", "Loin short ... with very little tuck-up". Tail "well set on, thick and
muscular at the base, following the natural line of the croup. Tail bones extend to, but not below, the point of hock.
Carried with merry action, level or with some moderate upward curve; never curled over back nor between legs."
Forequarters: "Shoulder blades long and well laid back with upper tips fairly close together at withers. Upper arms
appear about the same length as the blades, setting the elbows back beneath the upper tip of the blades"; "Pasterns
short and strong, sloping slightly". Hindquarters: "the pelvic bone slopes at a slightly greater angle (approximately
30 degrees from horizontal). In a natural stance, the femur joins the pelvis at approximately a 90-degree angle;
stifles well bent; hocks well let down with short, strong rear pasterns." Feet "medium size, round, compact". Coat:
"moderate feathering on back of forelegs and on underbody; heavier feathering on front of neck, back of thighs and
underside of tail. Coat on head, paws, and front of legs is short and even." Colour "Rich, lustrous golden of various
shades. Feathering may be lighter than rest of coat." Gait: "When trotting, gait is free, smooth, powerful and well
coordinated, showing good reach ... legs turn neither in nor out ... As speed increases, feet tend to converge toward
center line of balance." Source: https://images.akc.org/pdf/breeds/standards/GoldenRetriever.pdf

**Vertebral formula:** 7 cervical, 13 thoracic, 7 lumbar, 3 sacral, 20–23 caudal (C7 T13 L7 S3 Cd20–23); the tail
count varies by breed. Source: Auburn University canine osteology, https://canineosteology.vetmed.auburn.edu/Vertebral_column/Vertebrae.html

**The forelimb has no collarbone:** the shoulder blade slides and rotates on the ribcage, and "the dominant action of
scapular rotation for forelimb kinematics was confirmed" by X-ray (Andrada, Reinhardt, Lucas and Fischer 2017). The
thoracic limbs are stiffer than the pelvic limbs and absorb energy at the scapulothoracic joint; they bear weight and
contribute less to propulsion than the hind limbs (Andrada et al. 2023). So the fore "shoulder" joint the viewer sees
moving is really the scapula rocking about a point near its upper third.

**Working proportions (derived from the standard; use these to sculpt).** With H = height at the withers = 1.0:

- body length breastbone to buttocks 1.09; chest floor (brisket) at elbow height, 0.50–0.52 above the floor; loin
  short; croup slopes about 10° and the pelvis about 30°
- neck 0.33 (medium long), leaving the head's eye line at about 1.05–1.10 when alert and sitting about 1.0 when
  relaxed; neck base at the withers
- head: skull 0.22 long and 0.24 wide; muzzle 0.20 long (nearly as long as the skull), 0.11 deep at the stop tapering
  to 0.09; stop angle about 25°; eyes 0.16 apart, set at the stop, pupils 0.03 across; nose pad 0.06 wide
- ears: leather 0.15 long and 0.10 wide (tip reaches the eye when pulled forward), base set just above and behind the
  eye at about 0.9 of skull height, hanging flat on the cheek
- forelimb: scapula 0.30 lying at 45° lay-back along the ribs; humerus 0.30 (same as the blade); radius/ulna 0.30;
  pastern plus paw 0.12, pastern sloping 10–15° from vertical; the fore paw sits under the upper tip of the blade
- hind limb: pelvis 0.25; femur 0.33; tibia 0.33; metatarsus ("rear pastern") 0.16, short; standing, the hock is well
  let down (point of hock about 0.23 above the floor)
- tail: 0.45 long (tail bones reach the hock), 0.05 thick at the base, carried level or up to 20° above the backline,
  heavy feathering below
- paw: 0.09 long, 0.08 wide, four toes with dark pads (the fifth, the dewclaw, on the inside of the forelegs)

Check: Malinois of 18.6–28.5 kg have a hip-height leg length of 0.47–0.57 m (Andrada et al. 2023), so a 30 kg golden
with H ≈ 0.6 m and a 0.5 m leg is in proportion.

**Joint plan (24–30 joints).** Copy the Khronos Fox's proven plan and add what a drop-eared, long-tailed dog needs:

```
root (floor, feet at y=0)
└ hip  (pelvis)                      rx pitch, rz roll, ry yaw: 3 DOF, small
  ├ spine01 (lumbar)  ├ spine02 (thoracic/chest)   each rx ±8°, ry ±4°, rz ±3°
  │                   ├ neck01 (base)  ├ neck02 (atlas)  ├ head   (3 DOF each; see 2.5)
  │                   │                                   ├ jaw (rx 0–25°)
  │                   │                                   ├ earL/earR base (ry/rx swivel) ├ earL/earR leather (hangs, 2 DOF spring)
  │                   │                                   ├ eyeL/eyeR (ry ±20°, rx ±12°) + lids + inner brows (AU101)
  │                   ├ scapulaL/R (rx rock about the upper third ±15°)
  │                   │  └ shoulder (humerus)  └ elbow (forearm)  └ carpus (pastern/paw)  └ toes
  ├ femurL/R (hip joint)  └ stifle (tibia)  └ tarsus (metatarsus)  └ toes
  └ tail01 ... tail05 (five segments of 20–23 vertebrae; ry wag, rx carriage, each lagging the last)
```
The Fox's 24 joints: b_Root, b_Hip, b_Spine01, b_Spine02, b_Neck, b_Head, b_Right/LeftUpperArm, ForeArm, Hand,
b_Tail01–03, b_Left/RightLeg01, Leg02, Foot01, Foot02 (clips Survey, Walk, Run). Source: Fox.gltf in the Khronos
sample assets. Stark et al. 2021 modelled a Beagle forelimb with scapula 5 DOF, shoulder 3, elbow 2, carpus 2, paw 3,
which is the realistic upper bound.

### 2.2 Joint ranges (passive, goniometry)

The Labrador reference is Jaegger, Marcellin-Little and Levine 2002 (16 adult Labradors; "Goniometry is a reliable
and objective method"; repeat measurements vary 1–6°). Its table could not be re-read here. The French Bulldog study
that reproduces the method reports shoulder extension "similar to those reported in Labrador Retrievers" and
"shoulder, carpal, and tarsal flexion angles reflected those reported in Labrador Retrievers", and gives (right limb,
mean ± SD, degrees): shoulder extension 160 ± 19, flexion 51 ± 8; elbow 174 ± 11 / 51 ± 13; carpus 204 ± 8 / 32 ± 7;
hip 181 ± 7 / 58 ± 10; stifle 172 ± 8 / 58 ± 8; tarsus 188 ± 7 / 40 ± 6 ("Goniometric Assessment in French
Bulldogs", Front. Vet. Sci. 2019, 6:424). Healthy control dogs' stifle: maximum flexion 38.9 ± 3.4°, maximum
extension 152 ± 3.4° (stifle goniometry study, 2024, PMC11293097).

For the animator: the carpus hyperextends about 20° past straight (that is the "sloping pastern"); the elbow and
stifle never lock straight (extension stops around 170°); a fully flexed elbow or stifle folds to about 50°. **Nothing
in the clips should exceed these.** Active ranges in motion are far smaller (next section).

### 2.3 Poses: standing, sitting, lying

**Standing (working values, from the standard's angles and the goniometry envelopes):** scapula laid back 45°;
shoulder joint 110–115°; elbow 140–145°; carpus 185–190° (slight slope); hip joint about 110° (the femur at 90° to a
pelvis that slopes 30°, so the femur points down and forward at about 60° from horizontal); stifle 130–135°; tarsus
140–145°; back level; neck 45–60° above horizontal; head level.

**Sitting (the companion's rest pose).** Ellis et al. 2018 measured greyhounds standing up from a sit: the hip
extends 53.4 ± 5.6°, the stifle 78.5 ± 10.7°, the tarsus 88.7 ± 15.7°, and the foot goes "from a plantigrade to a
digitigrade foot posture" (the whole metatarsus lies on the ground when sitting). Subtracting those from the
standing angles gives the sit: **hip about 60°, stifle about 55°, tarsus about 55°, metatarsus flat on the floor,
toes forward beside or just ahead of the forepaws.** The croup drops to about 0.45 H above the floor (the hock
folded under); the back rises from the croup to the withers at about 35–45°; the forelegs stand vertical with the
elbow 150–160°, carpus straight, paws together under the blades; the neck comes up to 60–70° and the head sits level
at about 1.0–1.05 H. Weight: still about 60 % on the forelegs (Kano et al. 2016), which is why a sitting dog that
turns its head far also leans. Goldens relaxed in a sit often roll one hip and let a hind leg slide out (the "sloppy
sit"): a tell-tale habit, 0.6–0.8 s to slump, with the whole trunk rolling 8–12° and the tail sliding sideways.

**Stand-to-sit (arrive):** 1.0–1.4 s (the greyhounds' sit-to-stand took 1.14 ± 0.16 s; Yoshikawa et al. 2023 found
the hip moves half as much as in walking while the stifle and tarsus move more, and that the moves cannot be split
into phases, so animate one smooth curve). Order: the hind feet step forward a little under the body (0–20 %), the
tarsus and stifle fold while the hip flexes (20–85 %), the rump lands with a small settle (85–100 %, 1–2 cm rebound);
the forepaws usually stay planted, or step back one short step. Standing up reverses it, hip first (0–20 %), stifle
(10–50 %), tarsus (25–60 %), with the nose dipping forward as the rump rises.

**Lying down (rest after a long idle, optional):** forelegs slide forward, chest down, then the hips roll to one
side; 1.5–2 s; head on the paws for the deepest rest.

### 2.4 Gaits

**Hildebrand's gait formula** (1968, 37 breeds filmed at 64–72 frames/s, the Golden Retriever among them): the first
figure is the percentage of the stride each hind foot is on the ground (duty factor), the second the percentage by
which a forefoot's footfall lags the same-side hind foot's. The dogs' walks fell at about 50–70 on the first figure
and their trots near 45 (a Great Dane walked at 66-13, a Basset Hound at 69-25, an English Bulldog at 64-39; a
Bloodhound trotted at 45-55 and paced at 47-1). Long-legged breeds, the Golden Retriever listed among them, "tend to use lateral-couplets gaits"
at the moderate walk (second figure roughly 10–25: the two feet on one side move nearly as a pair), short-legged
breeds the single-foot (25). The true pace (second figure below 7) "was recorded for the Bloodhound, German Shepherd,
and Golden Retriever", but only in certain individuals, usually at a fast walk: avoid it in the companion, it reads as
lazy. Fore and hind feet stay on the ground about equally long at the walk (86–109 %, mean 100 %). At the trot "Most
dogs swing diagonally opposite legs together or nearly so (second figure about 50)", the forefeet are down 77–114 %
as long as the hind (mean 93 % in long-legged dogs: hind feet stay down slightly longer), and "many dogs turn their
bodies slightly from the line of travel when trotting" so the hind feet pass beside the forefeet instead of hitting
them: a few degrees of body yaw at the trot is correct, not a bug. Source PDF: https://www.originalwisdom.com/wp-content/uploads/bsk-pdf-manager/2019/04/Hildebrand_1968_Symmetrical-Gaits-of-Dogs-in-Relation-to-Body-Build.pdf

**Measured timings.** Kano et al. 2016 (BMC Vet. Res.; 29 dogs on a pressure walkway): walking dogs of 22.3 kg at
0.9–1.1 m/s had forelimb stance 0.46 s, swing 0.28 s, stride length 0.74 m, cycle 0.73 s (1.37 Hz), hind stance 0.45 s,
swing 0.30 s; trotting dogs (small, 6.5 kg) cycle 0.44 s. Fischer, Lehmann and Andrada 2018 (X-ray video, four
breeds): walk 0.7–1.3 m/s with duty factors 0.58–0.63; trot 1.4–2.5 m/s (Malinois 2.3–2.5) with duty factors
0.39–0.47; hip flexion-extension 36–48° per stride (Malinois 47–48°); the stifle's "effective" contribution to the
swing is in the single digits because "femur retraction" does most of the work; pelvic roll under 3° in whippets,
yaw 5° in Beagles, far larger in French bulldogs (16–19° roll). Fu et al. 2010 used 0.9–1.2 m/s for the walk and
1.7–2.1 m/s for the trot in mixed-breed dogs. Andrada et al. 2023: dogs walk below and "trot at speeds ranging from 0.5
Fr up to 3 Fr"; walk speeds Malinois 1.2, Beagle 1.0, Whippet 1.0 m/s; trot 2.5, 2.2, 1.8 m/s; at the trot the legs
"lengthen" 6–7 % in late stance (the body is bounced up), at the walk the forelimbs barely change length. Bertram
et al. 2000: Labradors and greyhounds trot in a dynamically similar way; the larger dog takes fewer, longer strides.
Maes et al. 2008 (Malinois, 0.4–10 m/s): continuity from walk to rotary gallop; at high speed the swing lengthens as
the spine flexes.

**Working gait tables for a 30 kg golden (H ≈ 0.6 m, leg ≈ 0.5 m):**

*Walk*, 1.1 m/s, stride 0.80 s (1.25 Hz), stride length 0.88 m, duty 0.62. Footfall phases (fraction of stride):
LH 0.00, LF 0.15, RH 0.50, RF 0.65 (lateral couplets). Per limb over its cycle: scapula rocks ±13° about its upper
pivot; shoulder ±8°; elbow flexes to 110° mid-swing, extends to 145° at touchdown; carpus folds 40–60° in swing (the
paw flips back visibly), hyperextends 10° in late stance; hip ±22° (46° excursion); stifle flexes 35° in swing;
tarsus flexes 35° in swing, extends in late stance; toes bend 20° at lift-off. Trunk: withers rise and fall about
±1.5 cm twice per stride (estimate), roll ±2°, pelvic yaw ±3°; head nods twice per stride at the atlanto-occipital
joint, up to 17° sagittal, 12° lateral and 12° axial in Labradors at 0.98 m/s (Schikowski et al. 2021): use ±4° pitch
on the head, ±2° on the neck base, the nose dipping as each forefoot lands.

*Trot*, 2.2 m/s, stride 0.50 s (2.0 Hz; estimate from Kano, Fischer and Bertram above), duty 0.45, hind feet down
0.02 s longer than fore. Footfalls: LH + RF together at 0.00 (hind a hair first), RH + LF at 0.50; two short
suspensions at 0.45–0.50 and 0.95–1.00. Joint swings about 1.3× the walk's; the head is held steadier (one nod per
diagonal step, ±3°); the trunk bounces ±2–3 cm (3–5 % of leg length, estimate from the 6–7 % leg lengthening); body
yaw 3–5° from the line of travel; the tail streams level and swings ±10° in antiphase to the pelvis. AKC: "legs turn
neither in nor out ... As speed increases, feet tend to converge toward center line of balance", so paws land under the
midline, not under the hips.

*Gallop:* rotary, as in Muybridge's plates 707 (Dread), 708 (Ike) and 710 (Maggie). Not needed in the dock.

**Reference frames.** Eadweard Muybridge, *Animal Locomotion* (1887), the dog plates as scanned by the USC Digital
Library and mirrored on Wikimedia Commons: Plate 704 "Dog Dread walking" (mastiff), 705 "Dog Dread trotting", 706
"Dog Smith trotting", 707 "Dog Dread galloping", 708 "Dog Ike galloping", 710 "Dog Maggie galloping" (white racing
hound), 712 "Dog Dread jumping hurdle" (files named `rbm-QP301M8-1887-7NN`, e.g.
https://commons.wikimedia.org/wiki/File:Dog_Dread_walking_(rbm-QP301M8-1887-704).jpg ; search
https://commons.wikimedia.org/w/index.php?search=Muybridge+%22Animal+Locomotion%22+dog&ns6=1 ). The National Gallery of
Art holds 706 https://www.nga.gov/collection/art-object-page.220467.html , 707
https://www.nga.gov/collection/art-object-page.167096.html , 710 https://www.nga.gov/collection/art-object-page.220618.html
and 712 https://www.nga.gov/collection/art-object-page.221204.html . Wellcome Collection has collotypes after
Muybridge of "A mastiff walking" (works dtv3jctk, eez4cznu, pemntfyj), "A mastiff rises from the ground" (jc5xa9sp:
the only published frame series of a dog getting up), "A dog turning round" (dyxkx5a9) and "A dog prowling"
(ayqa972c), at https://wellcomecollection.org/works/<id> . Public domain, all of them.

### 2.5 Head, neck, ears, eyes, face

**Head turns (attention).** Two neck joints do most of the visible work: the atlanto-occipital (nod) and the
atlanto-axial (turn), coupled so that a turn carries a little roll ("Lateral and axial rotation occurs as a coupled
motion pattern", Schikowski et al. 2021). Working values: a glance at the pointer = yaw 30–50° in 0.25–0.35 s with the
eyes leading the head by 50–100 ms, then a hold of 1–3 s and a slower return (0.5–0.8 s); a full look-round = up to
80° of yaw with 10° of roll the same way and 5–8° of body yaw (the 60 % front load means the shoulders lean too). Pitch
range ±35° (nose to the floor to sniff, nose up to the reader's face). Use a critically damped spring (the kit's
`look.speed` 6–7) so the head settles with weight, never a snap.

**The head tilt (React).** Sommese et al. 2022 (40 dogs): dogs that knew the names of toys tilted in 43 % of trials
against 2 % for typical dogs when their owner named a toy, and "the side of the tilt was stable across several months
and tests" (direction correlations r = 0.74–0.84). So: the companion always tilts to **the same side** (its right,
toward the viewer's left), roll 25–30° in 0.25 s with a 5° nose-up pitch and the ears pulled forward, hold 0.8–1.2 s,
return in 0.4 s. It should happen when the dog is "listening", that is after a tap and sometimes while Help is open,
never at random.

**Ears.** A golden's ears are drop ears: a muscular base that swivels and a heavy leather that hangs. DogFACS names
the base movements: EAD101 ears forward, EAD102 ears adductor (drawn up and together), EAD103 ears flattener (back and
down), EAD104 ears rotator, EAD105 ears downward (Waller et al. 2013; Bremhorst et al. 2019). Gähwiler et al. 2020 scored the
base from 1 "turned as far backwards as possible" to 5 "directed forward" and found ears back the strongest sign of
fear (d = 0.68). Working angles at the base: alert = 15–20° forward and 10° up (the leather lifts off the cheek and
its fold opens); neutral = hanging; appeasing or startled = 25–30° back and down, leather pressed to the skull.
Movement time 0.12–0.2 s. The leather follows with a lag: treat each ear as a pendulum of natural frequency about
3 Hz and damping ratio 0.3 hung from the base, so it swings on head turns, flaps on a shake and settles in two
bounces. **Ear flick** (a fidget): one ear, base back-and-forward in 0.2 s, often twice in a row; the head twitches
2–3° the other way.

**Eyes and lids.** Dark brown irises, almost no white showing (AKC). Blink rate is low: 6.529 ± 3.752 per minute in 7
pet dogs looking at a person (Koyasu et al. 2022) and 2.4 ± 1.4 per minute in 50 Shih Tzus at an eye exam (Sebbag et al. 2023),
so one complete blink every 9–25 s, far fewer than the Field Guide's 2.5–6 s (a human rate). Recommend a mean gap of
10 s, range 4–20 s, a double blink 15 % of the time, blink duration 0.15–0.25 s (estimate; dogs' lids move about as
fast as ours), and more blinks when the reader is active (dogs blink back at a blinking face: Canori et al. 2025) or
after a startle (Gähwiler et al. 2020). Eyes track before the head moves; add ±15° of eye yaw and ±10° pitch toward the pointer
with the head following.

**Puppy-dog eyes.** The inner brow raiser (AU101) lifts the inner corner of the brow and makes the eye look larger;
dogs produced it about twice as often when a person faced them than when she turned away (0.121 vs 0.056; Kaminski
et al. 2017), and shelter dogs showing it five times in two minutes stayed 50 days, ten times 35 days (Waller et al.
2013). For the companion: when the pointer rests on the dog or Help is open, raise the inner brows about 8° (2–3 mm on
a real dog) for 0.5–1 s every 10–20 s, sometimes with a small head lower. It is the single most recognisable "dog
looking at you" cue.

**Mouth, tongue, nose.** Closed mouth at rest, soft lips, no flews hanging. A relaxed golden often holds the mouth a
little open with the tongue tip showing; panting is about 300 breaths a minute (313 ± 19/min in 32 kg dogs, Meyer et
al. 1989), 5 Hz: use a light pant only in "talk" if ever, never in rest. **Nose lick** (AD137): the tongue sweeps up over
the nose and back in about 0.3 s, a very dog-specific fidget (also a mild appeasement sign). **Sniff:** 4–7 Hz, bouts
from half a second to several seconds (Craven et al. 2010, seven dogs 6.8–52.9 kg including a Labrador): the nose lifts
10–15°, nostrils flare, the head makes 4–5 micro-nods of ±2° at 5 Hz, 0.8 s, then a swallow.

### 2.6 Tail

20–23 vertebrae, thick at the base, reaching the hock, feathered beneath, carried "level or with some moderate upward
curve; never curled over back nor between legs", with "merry action" (AKC). Quaranta, Siniscalchi and Vallortigara 2007
(30 dogs, *Current Biology*): the wag is biased to the dog's **right** for the owner (and a friendly person or a cat),
to the left for an unfamiliar dominant dog or when left alone. Ren et al. 2022 (iScience, 150 frames/s tracking):
each dog has its own stable wag signature; the right bias develops over three days of meeting the same person; the
tail tip's angle is tracked over the full ±180° range and its speed reaches 16° per frame at 150 frames/s (about
2,400°/s). Leonetti et al.
2024 (*Biology Letters*) note that wag frequency has rarely been measured; pups start wagging at 4–5 weeks.

Working wag: a travelling wave from the base, base ±15°, mid ±35°, tip ±55° (greeting) with each of five segments
lagging the one before by 30° of phase; frequency 2.5–3.5 Hz for a happy greeting (estimate: slower than the 4.5 Hz
body resonance of the shake, faster than a casual 1 Hz sweep), 1 Hz and ±15° for a slow uncertain wag with the tail
lower; carriage lifts 10–20° when happy, the whole tail sweeps right of centre by 10–15° (the right bias). Very
excited: the "helicopter" (the tip traces a circle, add ±20° of rx at the same frequency, 90° out of phase). Sitting
at rest the tail lies on the floor curved to one side and the tip twitches once in a while (0.3 s, ±5°).

### 2.7 Breathing

Resting dogs breathe 18–34 times a minute (Merck Veterinary Manual), so 1.8–3.3 s a breath; a calm sitting golden
about 20/min = 3.0 s, slower in rest (15/min = 4 s). The ribcage widens 2–3 % and the belly moves more than the chest
in a relaxed dog; inhale 40 % of the cycle, exhale 60 %. The **sigh** is one breath at 1.5× amplitude with a slow
exhale and the head and shoulders settling 1 cm. Panting (300/min, 5 Hz) is for heat or excitement only.

### 2.8 The wet-dog shake and the other fidgets

**Shake:** Dickerson, Mills and Hu 2012 (33 animals, five dog breeds): Labradors shake at 4.3–4.6 Hz; "shake amplitude
is A = 90 ± 10°" at the skin, of which the skin itself swings about 60° and the spine about 30°; frequency scales as
mass^-0.22. The shake starts at the head and runs back; the feet plant wide, the head drops, the ears and tail flail
with lag; 1.0–1.5 s, 5–7 cycles (duration estimated). A **head shake** is the short version: 2–3 cycles at 4.5 Hz, ears
flapping, often after a sniff or a tilt. **Scratch:** a hind foot at about 5 Hz behind the ear (estimate). **Stretch**
after rest: forelegs stretched forward, chest down, rump up (the "downward dog"), then each hind leg stretched back,
2–3 s. **Yawn:** mouth open at least one second (Gähwiler et al. 2020's definition), head tipped back, 2–3 s. **Weight shift:** a
forepaw lifts 2 cm and resettles 3 cm to the side, the trunk rolling 3–4°; or the sloppy-sit hip roll of 2.3.

### 2.9 Startle and notice

Orienting: the head snaps toward the stimulus in 0.15–0.25 s with the ears forward (EAD101), the body still and the
breath held for one cycle; eyes first. If alarmed: ears turned back at the base (the strongest sign, Gähwiler et al. 2020, d =
0.68), the body lowered 5–10 %, the tail lowered, the weight shifted back over the hind feet, sometimes one short
backward hop; recovery over 1–2 s with a nose lick, a blink cluster or a shake. For the companion the "notice" clip
should be the friendly orienting response only; the alarmed version is for a sudden page event, if ever.

### 2.10 The clip list with numbers

Durations fit the Field Guide; every clip ends exactly on the rest pose (sitting, section 2.3).

| Clip | Length | What the dog does |
| --- | --- | --- |
| arrive | 2.0 s | trots in from the right at 2 Hz for 3 strides (0–1.0 s), drops to two walk steps as it turns 70° to face the reader (1.0–1.4 s), sits in 1.0 s as in 2.3 (1.3–2.0 s, hind feet step under, rump lands with a 1 cm settle); the tail starts a 3 Hz right-biased wag as it turns; ears forward; one blink on landing |
| idleA | 5 s | breathing at 20/min, one slow 1 Hz tail sweep of ±15° at 1–3 s, a double blink, a 3° weight shift at the end |
| idleB (variants) | 1.3–3.4 s | ear flick (0.5 s, twice); sniff bout (nose up 12°, 5 Hz micro-nods, 0.9 s); nose lick (0.3 s); sigh (2.0 s); sloppy-sit hip roll (0.8 s, trunk roll 10°, hind foot slides out, held until the next clip); head shake (3 cycles at 4.5 Hz, 0.7 s, ears flapping) |
| notice | 1.2 s | eyes lead 80 ms, head yaws 45° toward the reader in 0.3 s with 5° roll, ears forward 18°, brows up; hold 0.6 s; ease back 0.3 s |
| react | 1.5 s | the head tilt: 28° roll to its right in 0.25 s, nose up 5°, ears forward, eyes on the reader; hold 0.9 s with a small 3 Hz wag; return 0.35 s |
| talk | 3 s loop | ears forward, head nods ±4° every second with a 3° roll, soft 2.5 Hz wag biased right, brows raise once per loop, mouth closed (or a light pant if John wants it) |
| lookLeft / lookRight | 1.0 s | head yaw 45°, eyes lead, 5° body yaw the same way, ear on that side forward |
| rest | 5 s | breathing slows to 15/min, lids to 60 %, head lowers 15° and the neck 10°, ears relax, tail still; a sigh at the start |
| dance (hover) | 2.3 s | see 2.11 |

### 2.11 The hover dance: "the merry greeting"

Built only from movements a real golden makes when it greets someone it likes: the play-bow, the front-foot bounce,
the helicopter wag, a head shake that flaps the ears, and the puppy eyes. 2.3 s, p = 0..1:

| p | time | movement |
| --- | --- | --- |
| 0.00–0.22 | 0–0.5 s | **Play-bow:** forelegs slide forward and the chest drops to 0.25 H (shoulder flexes to 90°, elbow 160°, carpus flat), rump up (the dog rises off its sit onto its hind feet: hip 100°, stifle 110°), head low and turned 20° to its right, ears forward, tail up 25° and wagging 3.5 Hz to the right |
| 0.22–0.48 | 0.5–1.1 s | **Bounce:** two hops of the forefeet at 2.5 Hz (the paws leave the floor 3 cm, the chest 4 cm), the rump stays up; the wag becomes a helicopter (tip circles at 3.5 Hz) |
| 0.48–0.70 | 1.1–1.6 s | **Shake:** three cycles at 4.5 Hz starting at the head, 60° of skin and 30° of spine rotation, ears flapping with 60 ms lag, eyes closed for the middle cycle; the tail keeps wagging, slower |
| 0.70–0.92 | 1.6–2.1 s | **Sit back and look:** the hind legs fold (stifle 55°, tarsus 55°) and the rump lands with a 1 cm settle; the head comes up and tilts 15° right with the inner brows raised; wag drops to 2.5 Hz, right-biased |
| 0.92–1.00 | 2.1–2.3 s | **Settle:** everything eases to the rest pose; the last half-wag ends with the tail curved right on the floor |

Why it reads as a golden and not a generic dog: the bow and bounce are the breed's standard invitation to play; the
shake with heavy flapping ears is unmistakably a drop-eared dog; the right-biased, whole-body wag is the record's
"merry action"; the tilt and brows are the two best-documented "listening to you" faces. Keep the bounce height small
(3–4 cm) so it stays in the dock.

### 2.12 Secondary motion the builder should add

- ears: pendulum from the base, 3 Hz, damping 0.3, follow-through on every head turn, flap on shakes
- feathering (chest, back of the legs, under the tail): springs at 4–6 Hz with small amplitude, driven by the body
- tail: five-segment chain with 30° phase lag per segment, gravity sag when still (tip touches the floor in the sit)
- weight: the 60/40 front load means head turns pull the shoulders a little; the rump lands with a 1 cm rebound
- breathing never stops, blinks never land on a beat, the two sides of the face are never perfectly symmetrical

---

## 3. Sources

Standards, anatomy and physiology
- American Kennel Club, *Official Standard for the Golden Retriever* (approved 1981, reformatted 1990), https://images.akc.org/pdf/breeds/standards/GoldenRetriever.pdf
- Auburn University College of Veterinary Medicine, Canine Osteology: Vertebral Column, https://canineosteology.vetmed.auburn.edu/Vertebral_column/Vertebrae.html (C7 T13 L7 S3 Cd20–23)
- Merck Veterinary Manual, Description and Physical Characteristics of Dogs (resting respiratory rate 18–34 breaths/min; heart rate 70–120), https://www.merckvetmanual.com/dog-owners/description-and-physical-characteristics-of-dogs/description-and-physical-characteristics-of-dogs
- Meyer, Hahn, Buess, Mesch and Piiper 1989, Pulmonary gas exchange in panting dogs, *J. Appl. Physiol.* 66:1258–1263 (313 ± 19 breaths/min in 32 kg dogs), https://doi.org/10.1152/jappl.1989.66.3.1258
- Jaegger, Marcellin-Little and Levine 2002, Reliability of goniometry in Labrador Retrievers, *AJVR* 63:979–986, https://doi.org/10.2460/ajvr.2002.63.979
- Goniometric Assessment in French Bulldogs, *Front. Vet. Sci.* 2019, 6:424 (Table 2 quoted above), https://www.frontiersin.org/journals/veterinary-science/articles/10.3389/fvets.2019.00424/full
- Inter-rater reliability in performing stifle goniometry in normal and cranial cruciate ligament disease affected dogs, 2024, https://pmc.ncbi.nlm.nih.gov/articles/PMC11293097
- Stark, Fischer, Hunt, Young, Quinn and Andrada 2021, A three-dimensional musculoskeletal model of the dog, *Sci. Rep.*, https://doi.org/10.1038/s41598-021-90058-0 (PMC8166944)

Gait and limb mechanics
- Hildebrand 1968, Symmetrical gaits of dogs in relation to body build, *J. Morphol.* 124:353–360, PDF https://www.originalwisdom.com/wp-content/uploads/bsk-pdf-manager/2019/04/Hildebrand_1968_Symmetrical-Gaits-of-Dogs-in-Relation-to-Body-Build.pdf
- Fischer, Lehmann and Andrada 2018, Three-dimensional kinematics of canine hind limbs: in vivo, biplanar, high-frequency fluoroscopic analysis of four breeds during walking and trotting, *Sci. Rep.* 8:16982, https://doi.org/10.1038/s41598-018-34310-0 (PMC6242825)
- Andrada, Reinhardt, Lucas and Fischer 2017, Three-dimensional inverse dynamics of the forelimb of Beagles at a walk and trot, *AJVR* 78:804, https://doi.org/10.2460/ajvr.78.7.804
- Andrada, Hildebrandt, Witte and Fischer 2023, Positioning of pivot points in quadrupedal locomotion: limbs global dynamics in four different dog breeds, *Front. Bioeng. Biotechnol.*, https://doi.org/10.3389/fbioe.2023.1193177 (PMC10360120)
- Kano, Rahal, Agostinho et al. 2016, Kinetic and temporospatial gait parameters in a heterogeneous group of dogs, *BMC Vet. Res.*, https://doi.org/10.1186/s12917-015-0631-2 (PMC5015230)
- Fu, Torres and Budsberg 2010, Evaluation of a three-dimensional kinematic model for canine gait analysis, *AJVR* 71:1118, https://doi.org/10.2460/ajvr.71.10.1118
- Maes, Herbin, Hackert, Bels and Abourachid 2008, Steady locomotion in dogs: temporal and associated spatial coordination patterns and the effect of speed, *J. Exp. Biol.* 211:138–149, https://doi.org/10.1242/jeb.008243
- Bertram, Lee, Case and Todhunter 2000, Comparison of the trotting gaits of Labrador Retrievers and Greyhounds, *AJVR* 61:832–838, https://doi.org/10.2460/ajvr.2000.61.832
- Agostinho et al. 2011, Kinematic analysis of Labrador Retrievers and Rottweilers trotting on a treadmill, *VCOT*, https://doi.org/10.3415/vcot-10-03-0039
- Hottinger et al. 1996, Noninvasive kinematic analysis of the walk in healthy large-breed dogs, *AJVR* 57:381, https://doi.org/10.2460/ajvr.1996.57.03.381
- Schikowski, Eley, Kelleners, Schmidt and Fischer 2021, Three-Dimensional Kinematic Motion of the Craniocervical Junction of Chihuahuas and Labrador Retrievers, *Front. Vet. Sci.*, https://doi.org/10.3389/fvets.2021.709967 (PMC8417724)
- Ellis, Rankin and Hutchinson 2018, Limb Kinematics, Kinetics and Muscle Dynamics During the Sit-to-Stand Transition in Greyhounds, *Front. Bioeng. Biotechnol.* 6:162, https://doi.org/10.3389/fbioe.2018.00162 (PMC6250835)
- Yoshikawa, Kitazawa, Sano, Ino and Miyasaka 2023, Kinematic characteristics of canine hindlimb movement during sit-to-stand and stand-to-sit motions, *Res. Vet. Sci.*, https://doi.org/10.1016/j.rvsc.2023.104944
- Feeney et al. 2007, Validation of two-dimensional kinematic analysis of walk and sit-to-stand motions in dogs, *AJVR* 68:277, https://doi.org/10.2460/ajvr.68.3.277
- Eadweard Muybridge, *Animal Locomotion* (1887), dog plates 704–712: Wikimedia Commons (USC Digital Library scans) https://commons.wikimedia.org/w/index.php?search=Muybridge+%22Animal+Locomotion%22+dog&ns6=1 ; National Gallery of Art plates 706, 707, 710, 712 (addresses in 2.4); Wellcome Collection collotypes (ids in 2.4), https://wellcomecollection.org/

Behaviour, face, tail, senses
- Sommese, Miklósi, Pogány, Temesi, Dror and Fugazza 2022, An exploratory analysis of head-tilting in dogs, *Animal Cognition* 25:701–705, https://doi.org/10.1007/s10071-021-01571-8 (PMC9107419)
- Quaranta, Siniscalchi and Vallortigara 2007, Asymmetric tail-wagging responses by dogs to different emotive stimuli, *Current Biology* 17:R199, https://doi.org/10.1016/j.cub.2007.02.008
- Ren, Wei, Yu and Zhang 2022, Left-right asymmetry and attractor-like dynamics of dog's tail wagging during dog-human interactions, *iScience*, https://doi.org/10.1016/j.isci.2022.104747 (PMC9356099)
- Leonetti, Cimarelli, Hersh and Ravignani 2024, Why do dogs wag their tails?, *Biology Letters*, https://doi.org/10.1098/rsbl.2023.0407 (PMC10792393)
- Waller, Peirce, Caeiro, Scheider, Burrows, McCune and Kaminski 2013, Paedomorphic facial expressions give dogs a selective advantage, *PLoS ONE* 8:e82686 (DogFACS codes; AU101 and rehoming), https://doi.org/10.1371/journal.pone.0082686 (PMC3873274)
- Kaminski, Hynds, Morris and Waller 2017, Human attention affects facial expressions in domestic dogs, *Sci. Rep.* 7:12914, https://doi.org/10.1038/s41598-017-12781-x (PMC5648750)
- Bremhorst, Sutter, Würbel, Mills and Riemer 2019, Differences in facial expressions during positive anticipation and frustration in dogs awaiting a reward, *Sci. Rep.* (DogFACS variables incl. EAD101–103, AD19, AD137, AD126), https://pmc.ncbi.nlm.nih.gov/articles/PMC6917793/
- Gähwiler, Bremhorst, Tóth and Riemer 2020, Fear expressions of dogs during New Year fireworks: a video analysis, *Sci. Rep.* 10:16035, https://doi.org/10.1038/s41598-020-72841-7 (PMC7525486)
- Koyasu, Goto, Takagi, Nagasawa, Nakano and Kikusui 2022, Mutual synchronization of eyeblinks between dogs/cats and humans, *Current Zoology*, https://doi.org/10.1093/cz/zoab045 (PMC8962689)
- Canori, Travain, Pedretti, Fontani and Valsecchi 2025, If you blink at me, I'll blink back. Domestic dogs' feedback to conspecific visual cues, *R. Soc. Open Sci.*, https://doi.org/10.1098/rsos.241703 (PMC11836432)
- Sebbag, Silva, Santos, Raposo and Oriá 2023, An eye on the Shih Tzu dog: Ophthalmic examination findings and ocular surface diagnostics, *Vet. Ophthalmol.* 26 (Suppl. 1):59–71 (blink rate 2.4 ± 1.4/min in 50 dogs), https://doi.org/10.1111/vop.13022
- Craven, Paterson and Settles 2010, The fluid dynamics of canine olfaction: unique nasal airflow patterns as an explanation of macrosmia, *J. R. Soc. Interface* 7:933, https://doi.org/10.1098/rsif.2009.0490 (PMC2871809)
- Dickerson, Mills and Hu 2012, Wet mammals shake at tuned frequencies to dry, *J. R. Soc. Interface* 9:3208, https://doi.org/10.1098/rsif.2012.0429 (PMC3481573)

Models (addresses in the table of section 1)
- threedscans.com (Oliver Laric's free scan archive; downloads are direct links; BlenderNation's 2016 report of its terms https://www.blendernation.com/2016/05/09/free-high-resolution-3d-scans-download/ )
- Quaternius, Ultimate Animated Animal Pack, https://quaternius.com/packs/ultimateanimatedanimals.html (CC0; Drive folder 1uJ3N5HfB7jKTseJUNQr3N4YaN0UuEtHk)
- Khronos Group, glTF Sample Assets, Fox, https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/Fox
- OpenGameArt, https://opengameart.org/content/dog-low-poly-rigged ; https://opengameart.org/content/animated-animales-low-poly ; https://opengameart.org/content/lowpoly-animated-farm-animal-pack
- poly.pizza (Google Poly archive), https://poly.pizza/search/dog
- Smithsonian 3D, https://3d.si.edu/object/3d/canis-dirus-leidy:6796319b-6445-435f-994b-2f40fd8d08e4
- Thingiverse, https://www.thingiverse.com/thing:7180988
