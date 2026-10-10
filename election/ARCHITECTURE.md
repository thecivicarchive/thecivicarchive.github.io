# Election Night: the plan

Written 2026-10-09 (a Friday) by the architect, for the agents who build Election Night and for John. Read it with
CLAUDE.md (the sections On The Ballot; State and local races on the ballot; County and local races, every state;
Minnesota, finished), the memory note `election-night.md` (John's request and his eight answers, which bind this plan)
and the scouts' files in `election/scout/` (results_mn.json, results_ne.json, results_az.json, results_la.json,
results_pa.json, feeds.md, feeds.json, model.md), all checked on 2026-10-09. Where this plan and John's own words
differ, John's words win.

## 0. In plain words

- **A third space**, beside On The Ballot and Legislation & Legislatures, at `/dev/night/`: a home page with three
  doors, **Results**, **The feed** and **Forecasts**, and a door to it on the site's home page and in its top bar.
- **Results** are official counts only, as each state's own election office posts them, each with its time. Minnesota
  at every level, from files John saves by hand from the Secretary of State's site (it shows this computer a CAPTCHA,
  so no program ever asks it for anything). 25 states and DC publish a results feed a program may read; 8 more can be
  read with care; Oklahoma by hand if John wants; 15 states publish no live count a program may read, so their pages link
  to the state's own results and fill in when the state certifies.
- **The feed** shows news headlines with links (GDELT's free files, 145 outlets' RSS feeds) and posts only from
  newsrooms, election offices and candidates' official accounts. Everyone else is counted, never shown or named. A
  leaderboard ranks races by coverage per 100,000 residents, attention gap, momentum and source breadth.
- **Forecasts** give every contested Minnesota race and every race for Congress, governor and the other statewide
  offices a chance of winning and a likely vote range wherever the record allows one, labelled Analysis. Every model run
  is kept and its trend drawn.
- **One program on John's computer**, `run_night.py`, does the night's work and publishes every 10 minutes.
- **Measured today**: GitHub's servers keep every file for 10 minutes and ignore anything after a `?` in an address;
  each build of the main site takes 1.5 to 5 minutes; the published site is at 747 MB of its 1 GB limit. So the live
  figures go to a small second site (recommended) in folders that are never overwritten, and a 1 KB pointer file says
  which folder is newest. Readers see figures about 10 to 20 minutes after the state posts them, with the time on
  every number.
- **Dates**: Minnesota's pages and the foundations Oct 10 to 16; the updater Oct 14 to 21 (first rehearsal Tue Oct 20);
  every state's feeds Oct 15 to 25; the feed Oct 17 to 26; forecasts Oct 16 to 27; reviews Oct 26 to 28; dress
  rehearsal Thu Oct 29; freeze Oct 31; the updater starts Mon Nov 2 at 6 p.m.; Election Day Tue Nov 3.

---

## 1. The space

### 1.1 Pages and addresses

All under `site/dev/` (published as `thecivicarchive.github.io/dev/`), except the live figures.

| Address | Page | Routes (after #) | Built by |
| --- | --- | --- | --- |
| `night/` | Election Night home: the three doors, the night's timetable (when polls close, state by state), what is read live and how, a countdown | none | `build_night_home.py` |
| `night/us/` | Results across the country: the US map (Senate, Governor, House, What is counted here), every state's statewide and congressional races, Use my location | `#state=MN`, `#race=<race id>`, `#mine` | `build_night_us.py` |
| `night/mn/` (later `night/<code>/`) | One state at every level: the precinct map, statewide, Legislature, courts, county, city and town, township, school, hospital and other districts; your own ballot's results by location | `#statewide`, `#legislature`, `#courts`, `#county=053`, `#race=<race id>`, `#map=<layer>:<id>`, `#mine` | `build_night_state.py` |
| `night/feed/` | The feed: a map of coverage, the stream of headlines and official posts, the leaderboard by level | `#state=MN`, `#race=<race id>`, `#board=<level>`, `#how` | `build_night_feed.py` |
| `night/forecasts/` | Forecasts: every race's chances and likely ranges, the trend across runs, the inputs, the method, the track record | `#state=MN`, `#race=<race id>`, `#track`, `#method` | `build_night_forecasts.py` |
| `night/og/` | Four share images (home, results, feed, forecasts). No figure of any kind on an image | none | `build_night_home.py` |
| `/night-live/` (beside `/dev/`, not inside it) | The live figures: `now.json` and the snapshot folders | none | `run_night.py` |

**Race ids are the ballot databases' own.** Congress: `ballot_2026.sqlite` `races.race_id` (`2026-MN-H05`,
`2026-MN-S2`). Everything else: `ballot_local_2026.sqlite` `sl_races.race_id` (`2026-MN-0121-MN`; Minnesota's embed the
Secretary's office id and the place key). A result, a forecast and a feed item about the same contest share its id.

### 1.2 The look

- **The home** is built on the whole shell, as the front door, Method and Access are (`build_home.page()`:
  `S.head`, `S.top_bar(current="night")`, `S.panels`, `S.tab_bar`, the footer), with door cards in the `tca-door`
  style, a plain-language twin for each main paragraph (Flesch-Kincaid grade 7 or lower, checked at build) and every
  number counted at build time.
- **The four inner pages** are built the way the ballot pages are: their own top bar, the federal stylesheet and the
  ballot stylesheet borrowed by landmark, the emblem's icons and share tags through `brand.head_tags` (the `__BRAND__`
  placeholder the other builders use), the site's own type copied beside the page (`copy_fonts`; nothing from Google
  Fonts), and the companion and page guide through `shell/rider.js`. When the shell rolls onto every page, they move
  with the ballot pages. (The shell's script and the rider are alternatives: never both on one page.)
- **Colours**: red and blue (`var(--pD)`, `var(--pR)`, `var(--pI)`) only for party data: a partisan candidate's bar,
  a county or precinct where a party's candidate is ahead. Everything else (status, coverage, forecasts' frames,
  nonpartisan races) in verdigris, brass, ink and greys. A nonpartisan race's candidates take neutral tones in ballot
  order, never red or blue. Under the colour-vision palettes, Calm and high contrast, fills also carry patterns.
- **Every page**: "Generated on <date>" in the footer, the version badge, no name of the kit's files or programs (each
  builder runs the same check `build_home.py` runs, and `quiet_pages.py` runs at publish), the GDELT credit wherever its
  items appear, each outlet named on its own headline.
- **Share images**: one per section through `brand.site_card`. Never a count, a percentage or a chance on an image:
  other sites keep these images for days.
- **Practice figures never reach `site/dev/`**: a build with `--practice` writes to `site/practice/night/`, which no
  publish script copies.

### 1.3 Doors into the space

One agent (N5 in section 5), and only after the member-file-tabs work now running has been saved: on 2026-10-09 git
shows `build_home.py`, `build_shell.py`, `shell_src/boot.js`, `shell_src/guide.js`, `shell_src/shell.js`,
`Publish dev site.bat` and `publish_dev.ps1` changed by that work. The main session checks `git status` before starting
N5.

- `build_shell.py`: "Election Night" in the top bar between Ballot and Officials, in the phone menu, and in the phone
  tab bar as "Results" if six tabs keep 44-pixel targets at 320 pixels wide (`shell.css`: `repeat(6, ...)`);
  otherwise in the phone menu only. `site_places()` learns `night`. `RIDE` learns
  `night/(us|feed|forecasts|[a-z]{2})/index.html`, and `ride()`'s walk goes one folder deeper under `night/` as it does
  under `ballot/`.
- `shell_src/icons.js`: a sixth icon, `night`, drawn like the other five (brass and ink, never red or blue).
- `shell_src/guide.js`: an entry for the home and for each inner page and route (t, a, s, n), in the pages' own words.
- `build_home.py`: a sixth door, "Election Night", with a line for John to approve (proposed: "Follow the count, race by
  race."), its plain twin, facts counted at build (states read live, races with forecasts, outlets in the feed); "Five
  ways in" becomes "Six ways in"; the footer's Go list; Help's quick actions. A short Election Night section on the
  Method page comes in phase 6.
- `Preview dev site.bat`: builds the Night pages (`run_night.py build`) after the ballot pages and before the doors.
- Not now (John may want them later): a third switch on the ring of cards and the ballot door, a third poster in the
  cabin.

### 1.4 What is borrowed, and how

Nothing is copied by hand. Code comes by landmark (the build stops and names a landmark that moved) or by import.

| What | From | How | Used for |
| --- | --- | --- | --- |
| The federal stylesheet, theme, changelog badge, the Albers projection and point-in-polygon test (`conic`, `albersUsa`, `inRing`, `inShape`, `pathRings`, `decodeRing`) | `build_site_dev.py`'s page | `build_state_dev.borrow("CSS")`, `("THEME")`, `("CHANGELOG")`, `("GEO")` | every inner page; placing a reader on the US map |
| A sortable table | the same | `build_state_dev.borrow("GRID")` | the leaderboard |
| The ballot pages' stylesheet (cards, maps), the source folds | `build_ballot_dev.PAGE` | `build_ballot_state_dev.borrow_ballot("BALLOT_CSS")`, `("SOURCEFOLD")` | result cards, maps, "Where this comes from" |
| A state's races, candidates, places, counties and each race's shape on the map (`g`, the shape `race_shape()` gives it) | `ballot_local_2026.sqlite` through `build_ballot_state_dev` | import `build(db, code, lines)` and `geo_for(code)`, read only (note: `build()` writes a county-lines cache file the first time a state has local rows) | the Night state page's races and "your ballot" |
| The ballot map: Web Mercator, layer and precinct files, zoom, drag, pinch, keyboard, `locate()`, `focus()` | `build_ballot_state_dev.MAPKIT`, its BallotMap part | taken from the start of `MAPKIT` up to the landmark `/* ---------- the map set into the page's "your ballot"` (the GEOKIT after it uses the ballot page's own globals and is not taken) | the results map, written beside the page as `night/<code>/mapkit.js` with the Night results kit |
| The map's files (index.json, layers, a precinct file per county, school files, `reader.js`) | `site/dev/ballot/<code>/geo/` | fetched by address (`../../ballot/mn/geo/`), never copied; `index.json`'s `v` is the cache key | saves publishing 7.1 MB of Minnesota's lines twice |
| Congress races and candidates, state outlines and boxes | `ballot_2026.sqlite` through `build_ballot_dev.build(...)`; `us_states_albers.json` through `build_site_dev.state_paths()` | import, read only | the US map and race list |
| House district lines | `site/dev/ballot/us/data/districts.json` | fetched by address | the House view; states with new 2026 lines show their outline and say why, as the ballot pages do |
| Slimming, writing only on change, the site's type | `build_ballot_state_dev.slim_page`, `write_if_changed`, `copy_fonts` | import | every inner page |
| The shell | `build_shell.py` | `build`, `head`, `top_bar`, `panels`, `tab_bar`, `icon`, `site_places` | the Night home |
| Emblem, share images, icon and share tags | `brand.py` | `site_card`, `save_card`, `head_tags` | every page |
| Polite downloads, patient address lookups, the issuer-certificate repair | `states/net.py` | import (`UA`, `get`, `patient_lookups`) | every request |
| Minnesota's results file reader | `states/load_local_results.read_file` | import | John's hand-saved files |
| Minnesota's office ids and place keys | `ballot/state_local_mn.py` | import its key functions | the crosswalk from the Secretary's office id to race ids |
| County lines of one state | `states/load_counties.py`'s reader on `states_cache/census/cb_2024_us_county_500k.zip`, projected with `AlbersUsa().by_state(code)` | import | county results maps on the US page |
| PDF text | `ballot/pdftext.py` | import | Wyoming's summaries |
| Contact-detail test | `ballot/check_local.contact_like()` | import | the privacy scan |
| Polls, AAPOR Transparency Initiative members only | `ballot/polls/polls_2026.json`, `polls_mn_state_2026.json`, `aapor_ti_members.json` | read | forecasts |
| Formats the kit already reads for the 2026 primaries | `ballot/lists/<code>.py`, `ballot/state_local_<code>.py` (Clarity, Enhanced Voting, Tally, Civix, Louisiana, CTEMS, Vermont, North Carolina, Pennsylvania, Florida, Indiana, New Mexico, Hawaii, Delaware, Alaska, Oklahoma) | read for their lessons; import a parsing function where it stands alone, otherwise write the reader new | the live readers |

**The one change to existing ballot code.** BallotMap draws lines, not results. One optional hook is added to it, under
a landmark comment `/* ---------- results paint (Election Night) ---------- */`, in `draw()` right after the state's
surface is filled and before the faint county lines: `if (opt.paint) opt.paint(kit)`, where `kit.fill(kind, colourOf,
alpha)` fills every shape of a kind in view (close in, the precincts of the county files in use, coloured by
`colourOf(precinct id)` or by the precinct's own property for a district kind; far out, the shapes of that layer's own
file) and `kit.pattern(...)` gives a hatch for "not yet reported". The ballot pages pass no `paint`, so they draw exactly
as before. Check: rebuild the Minnesota and Wisconsin ballot pages; their data files are byte-identical and only
`geo/mapkit.js` differs, by the hook. While this change is open no other agent edits `build_ballot_state_dev.py`.

### 1.5 What is new

Top level:
- `run_night.py`: the one command (section 3.1).
- `build_night_home.py`, `build_night_us.py`, `build_night_state.py`, `build_night_feed.py`,
  `build_night_forecasts.py`: one builder per page kind. Each exposes
  `build(dev_root, version=None, practice=None, say=print) -> {written path: bytes}`, so `run_night.py build` can call
  whichever exist.
- `night_common.py`: what the four inner builders share: the borrowing helpers; the Night stylesheet and script pieces
  (status chips, "as of" stamps, the polls-open notice, the Analysis chip, time in the reader's own zone,
  `NIGHTLIVE` (the live poller), the stale notice, the rehearsal banner); the Night results kit for BallotMap; the US
  SVG map code (its own code, following the ballot maps' rules: 12px type scaled by transform, no pointer capture,
  window listeners dropped through an AbortController).
- `Start Election Night.bat`, `Stop Election Night.bat`, `Update Election Night once.bat`,
  `Open Minnesota results folder.bat`.

`election/` (a package):
- `store.py` (the results database), `source.py` (every request goes through it: live or replay), `registry.py` and
  `registry/<code>.json` (one file per state and DC), `crosswalk/<code>.json` (and `crosswalk/mn_precincts.json`),
  `poll_hours.json`, `readers/<family>.py`, `live.py` (the cycle), `livejson.py` (snapshots, pointer, pruning),
  `publish.py`, `replay.py`, `awake.py`, `feeds/` (`outlets.py`, `accounts.py`, `keywords.py`, `gdelt.py`, `rss.py`,
  `bluesky.py`, `mastodon.py`, `youtube.py`, `geotag.py`, `measures.py`), `model/` (`data_mn.py`, `census.py`,
  `features.py`, `forecast.py`, `live_model.py`, `simulate.py`, `blindspots.py`, `backtest.py`, `runs.py`,
  `data_us.py`, `other_states.py`), `tests/`, `fixtures/` (small test files from public results only).

Databases (ignored by git, as every `.sqlite` is): `election_2026.sqlite`, `night_feed_2026.sqlite`,
`election_model_2026.sqlite`. Never the ballot or record databases, which Night reads only.

Folders ignored by git: `election_cache/` (every raw file fetched), `site/night-live/` (already ignored with `site/`),
`election_live/` (the clone of the live site, option B).

---

## 2. The data

### 2.1 What Night reads and never writes

`ballot_2026.sqlite` (470 races for Congress), `ballot_local_2026.sqlite` (31,211 state and local races in 49 states;
266 statewide offices in 43 states, 36 governors; Minnesota 4,721 races), `ballot_geo/` and the built ballot pages'
`geo/` folders, `states_cache/acs2024/` (B01001, B01002, B01003, B03002, B05002, B09001, B15003, B17001, B19013,
B25003 national files), `states_cache/census/`, `us_states_albers.json`, the polls files, `ballot/lean/`, the state
databases (to recognise sitting legislators only).

### 2.2 Results: `election_2026.sqlite`

| Table | One row per | Columns (short) |
| --- | --- | --- |
| `elections` | state and election | election id (`2026-11-03`), state, kind, date, certified on, certifying body, note |
| `feeds` | feed of a state | state, feed id, family, address pattern, status, approved, last ok, last failure, failures in a row, why stopped |
| `snapshots` | file read | snapshot id, state, feed id, fetched at (UTC), the source's own time and version, SHA-256, raw file path, status (`ok`, `same`, `held`, `failed`, `test`, `refused`), rows, note |
| `contests` | contest in a feed | race id, state, the feed's own contest key, office, level, district, seats, decision rule, ranked-choice flag, what its units are (precinct, county, town, parish, ward), units in all |
| `choices` | candidate line | race id, choice key, name as printed, party as printed, the ballot database's candidate (race id plus name as filed), write-in flag, order |
| `units` | reporting unit | state, unit id, kind, name, parent, the map's id (VTDID, county FIPS, town GEOID) |
| `counts` | changed number | snapshot id, race id, unit id, choice key, vote type (`total`, `election_day`, `early`, `mail`, `absentee`, `provisional`, `other`; the state's own word kept in `feeds`), votes |
| `reporting` | changed status | snapshot id, race id, unit id, units in, units in all, ballots, registered |
| `checks` | check run | snapshot id, check, passed, detail |
| `certified` | certified figure | race id, choice key, votes, source, date |

Rules: a `counts` or `reporting` row is written only when a number changed since the last snapshot, so every night can
be replayed in order. Checks: units add up to the source's own totals; units in never exceed units in all; every
contest in the file is matched or listed; a fall in a candidate's votes is flagged (corrections happen), never refused.
A snapshot that fails a check is held and the page keeps the last good figures with their time. No count is ever
edited by hand; if numbers do not reconcile, the report says which and why.

**Minnesota's precincts**: the map's precinct id is the VTDID (`270010005` = 27, county FIPS 001, precinct code 0005).
The Secretary's files give the county number (1 to 87, alphabetical) and the precinct code, so VTDID = `27` +
(2 x county number - 1, three digits) + code. The crosswalk agent confirms this on the first real file and lists every
precinct that does not fit.

### 2.3 The feed: `night_feed_2026.sqlite`

| Table | Holds |
| --- | --- |
| `outlets` | outlet id, name, domain, kind, home state, market, feed address, whether the feed carries full text (never shown), credit line |
| `accounts` | platform, account, owner kind (newsroom, election office, candidate), owner, the page that links it, the proof it points back, checked on, active |
| `items` | item id, source (gdelt, rss, bluesky, mastodon, youtube), outlet or official account, canonical address, headline (or an official post's text), published at, fetched at |
| `item_places` | item id, race id or place id, state, confidence (high, medium, low), the rule that placed it |
| `counts` | minute, race id, kind (news, social), items, distinct people |
| `measures` | time, level, race id, items, residents, coverage raw and shown, attention gap and its margin's source, momentum and whether rising, outlets and effective outlets, ranked or not |
| `deletions` | platform, post address, time |

Nothing about an ordinary account is ever written: no id, handle, text or post id. Only counts.

### 2.4 Forecasts: `election_model_2026.sqlite` (model.md 3.6)

`runs` (run id, kind: pre, live, backtest, replay; method version; SHA-256 of the model's code; seed; draws; start and
end; rehearsal flag), `run_inputs` (run, input, file or address, SHA-256, as of), `race_runs` (run, race, status, units
in and in all, ballots counted, expected total range), `candidate_runs` (run, race, choice key, chance, median share,
80 and 95 percent ranges), `features`, `backtests`, `calibration`. A race gets a row only when its inputs or outputs
changed. The seed comes from the run id, so any run can be redone from its stored inputs.

### 2.5 Files on disk

- **Minnesota on the night**: `states_cache/mn_local/sos/20261103/results/`. John saves every Media File there, any
  extension (his earlier saves are `.md`); the reader checks each file by its first line, never by its name.
- **Minnesota for rehearsals**: `states_cache/mn_local/sos/20260811/` (the Aug 11 primary) and `20241105/` (the 2024
  general), both empty today.
- **Oklahoma, if John agrees**: `ballot_cache/ok/results/20261103/` (the two Export files; the kit already reads that
  layout for the primaries).
- **Raw files**: `election_cache/<code>/<feed>/<UTC time>-<first 8 of SHA-256>.<ext>`, kept whole for audit (some carry
  columns never read, such as Connecticut's address field), never published, never printed.

### 2.6 What the pages read

**Static**, published with the draft and rebuilt by `run_night.py build`:
- `night/us/data/races.json`: every race for Congress, governor and the other statewide offices: id, state, office,
  district, seats, decision rule, candidates (key, name as filed, party), the state's feed status, the state's own
  results page.
- `night/<code>/data/races.json`: every race of the state: id, level, kind, office, place, counties, district,
  partisan or not, shape (`g`), candidates (key, name as filed, party or "Nonpartisan office", order). Only these
  fields, taken from `build_ballot_state_dev.build()`.
- `night/us/data/counties/<code>.json`: county lines for states whose feeds report by county.
- Poll closing times and polling-place lookups inside each page's `BOOT`.
- Map lines by address from the ballot pages (2.1).

**Live**, written each cycle into `site/night-live/` and published as `/night-live/`:
- `now.json`, the only file at a fixed address (at most 4 KB), for example:
  ```
  {"v":1,"seq":184,"at":"2026-11-04T03:40:00Z","next":"2026-11-04T03:50:00Z","run":"running","rehearsal":false,
   "base":"s/000184/","st":{"MN":{"s":"counting","t":"2026-11-04T03:36:12Z","f":"mn.json","by":"hand"},...},
   "fc":{"t":"2026-11-04T03:38:40Z","m":"1.0"},"fd":{"t":"2026-11-04T03:39:05Z"}}
  ```
  State status words: `wait` (polls open), `none` (no votes yet), `counting`, `done` (every unit in, not certified),
  `official` (certified), `held` (the file changed; last good shown), `stale` (the source has not answered), `link` (not
  read here), `refused`.
- `s/<seq>/`, a snapshot folder, never changed once written: `us.json` (the US map and national lists: each federal and
  statewide race's status, reporting, time, candidate totals); `<code>.json` (every race the state's feed carries:
  totals, reporting, time, official flag, by county where reported, by vote type where reported);
  `<code>/c/<county>.json` and `<code>/c/<county>-court.json` (precinct rows, the judges apart; Minnesota and any
  precinct-level state); `fc/<code>.json` (each race's
  latest forecast: run, time, method, share counted, each candidate's chance, median and 80 percent range);
  `feed/us.json` and `feed/<code>.json` (latest items, the boards).
- `h/<code>/<race>.json`: each race's run history (time, method version, share counted, chances, ranges), at a fixed
  address; a few minutes' delay is harmless there.
- Keep the last four snapshot folders in the live folder; the databases keep everything.
- `rehearsal/`: the same layout, read only when the page's address has `#rehearsal`, with a banner.

County file names (settled 2026-10-10): a county is its five-digit FIPS code everywhere (`27053`, never `053`): the store's county units, the state file's `k` keys and the file names, which come only from `election.store.county_file()`; the files' short layout is in `night_common.py`'s account of the live figures.

Size budgets: `now.json` 4 KB; `us.json` 150 KB; a state's file 800 KB; a county's precinct file 150 KB; forecasts 300
KB a state; feed 200 KB a state; a snapshot 8 MB in all. Night's static files on the main site: 25 MB in all.

**How a page reads it** (`NIGHTLIVE` in `night_common.py`): ask for `now.json` every 2 minutes while the page is
visible (none while hidden), then fetch from `base` only the files the page shows, and only when `seq` changes; never mix
files from two snapshots; numbers update in place and a list that would re-sort says "New figures are ready: show them";
one polite announcement per new snapshot ("New figures as of 9:52 p.m."); if `now.json` is more than 25 minutes old by
the reader's clock, say that updates have paused, keep the last figures with their time and link to the state's own
results. On `127.0.0.1:8790` (the usual preview, which serves `site/dev` only) there are no live figures and the page
says so; `run_night.py preview` serves `site/` on port 8791 so `/dev/night/` and `/night-live/` sit together as they
will on GitHub.

---

## 3. The updater: `run_night.py`

### 3.1 Commands

| Command | Does |
| --- | --- |
| `check` | Python, the three databases, the registry, the never-request lists, each reader's self-test on its fixture. Downloads nothing |
| `build [--practice]` | the five page builders; practice figures only to `site/practice/night/` |
| `discover` | once a day from Oct 20: each state's list of elections (one request a state) for its Nov 3 id; prints what is found and what is missing |
| `once [--publish] [--state xx] [--from-file raw]` | one cycle; `--from-file` tests a mended reader on a held file |
| `live` | the night: cycles until stopped |
| `replay --election <past> [--states mn,ia] [--speed 6] [--order random\|small-first\|metro-last]` | a past election as if live, to `/night-live/rehearsal/` |
| `preview` | serves `site/` at http://127.0.0.1:8791/ |
| `status` | rewrites `election_night_status.md`: what is read, what waits on John, the last publish |
| `scan` | the built pages and live files: contact-like text (`check_local.contact_like`), any social account not on the official list, any name of the kit's files |
| `certify <code>` | loads a state's certified results after its canvass |
| `forecast` | the day's pre-election forecast runs for every state (Minnesota included); `live` also runs them once a day before Nov 3, in the sections thread, never in the results cycle. Whether forecasts reach any page or the live folder is one switch, `FORECASTS_PUBLIC` in `election/model/__init__.py` (off until John says yes) |

### 3.2 One cycle

1. **Results**: for each state whose status is live or care, from its first poll closing: ask its cheap "what's new"
   address (Clarity `current_ver.txt`, Tally `versionID`, Enhanced Voting `lastUpdated`, CTEMS `Version.json`,
   Vermont's index, Indiana's `settings.json`, Arizona's `election_<id>_0.json`); fetch the data only when it changed;
   keep the raw file; read it; match it through the crosswalk; write the changes; run the checks; set the state's
   status. Anything a feed carries before the state's first poll closing is a test (California serves test numbers
   today) and is never published.
2. **Hand-saved**: look in each watched folder for new or changed files; the same steps. A figure's time is the time
   the file itself states, or else when John saved it.
3. **Feed**: GDELT, RSS, Mastodon and YouTube on their own clocks (3.3); Bluesky's two streams run in the background.
4. **Forecasts**: the live model for each state with new results (Minnesota about 7 seconds); before results, the
   pre-election run.
5. **Measures**: every 5 minutes.
6. **Every 10 minutes on the clock** (:00, :10 ...): write the snapshot folder, the history files and `now.json`;
   prune; publish.
7. Log, console line, status file.

Each section owns the function that turns its database into JSON (`election.store.page_json(state)`,
`election.model.runs.page_json(state)`, `election.feeds.measures.page_json(state)`); the updater owns the snapshot
folder, `now.json` and publishing, and skips a section that is not there yet.

### 3.3 How often

| What | How often |
| --- | --- |
| A state's "what's new" address | every 2 minutes, from its first poll closing; data only on change |
| Minnesota's folder | every 30 seconds (a look at a folder; no network) |
| GDELT `lastupdate.txt` | every 15 minutes; each new zip parsed, then deleted |
| RSS (145 feeds) | every 10 minutes, conditional (ETag, Last-Modified); every 30 minutes in the 24 hours before |
| Mastodon (7 servers, 6 tags each) | every 3 minutes, at most 14 requests a minute in all |
| YouTube channel feeds (official channels only) | every 30 minutes, at most one a second |
| Bluesky | live, two streams |
| Model | after new results, at most once a cycle |
| Publish | every 10 minutes from 5 p.m. to 3 a.m. Central; every 30 minutes to 8 a.m.; hourly while it runs after that; on later days as John runs it |

### 3.4 Politeness, and hosts never asked

- Every request goes through `election/source.py`: the kit's honest User-Agent (`states/net.UA`), one request at a
  time per host, at least 1 second apart (2 for small state sites), at most 4 hosts at once, patient address lookups
  (this router drops about one lookup in three), conditional requests where a host supports them.
- A 403, a 429, a challenge page or a CAPTCHA stops that host for the night. The state then says "the state's site
  refused this request" and links to it. Never retried under another identity, never worked around.
- A certificate that fails stays failed (South Dakota's results site had an expired certificate on 2026-10-09). The
  check is never switched off. `states/net.py`'s issuer repair is the one repair allowed; it still requires a trusted
  root.
- Each `registry/<code>.json` carries a `never` list that `source.py` refuses before any request: every Minnesota
  Secretary of State host (`*.sos.mn.gov`: results, results files, candidates, the main site, the poll finder, which
  pages link to but no program requests), Kentucky's `vrsws.sos.ky.gov` (its Acceptable Use Policy limits scraping, and a
  block would fall on John's own address), and every host a scout found behind a challenge or wall (Wisconsin's
  commission and the Milwaukee and Dane county sites, Michigan's MVIC, Chicago's board, Ohio's LiveResults and
  publicfiles, Missouri's results, Kansas's election-night page, Oklahoma's results, Arizona's results front page,
  Nevada's results hosts, Tennessee's, New York's results page, New Hampshire's, Massachusetts's sec.state.ma.us, New
  Jersey's elec.nj.gov, the old results.texas-election.com) and GDELT's search API (429 to this machine).
- Arizona's data host `cdn1.arizona.vote` (the address the official page itself reads) only if John says yes.
- Readers keep only the fields they name (an allowlist). Contact columns are never read or printed.

### 3.5 Publishing

**Measured 2026-10-09:**
- GitHub's own page of limits (docs.github.com, "GitHub Pages limits", read 2026-10-09): published sites no larger
  than 1 GB; source repositories recommended under 1 GB; deployments time out after 10 minutes; a soft limit of 100 GB
  of bandwidth a month; a soft limit of 10 builds an hour ("does not apply if you build and publish your site with a
  custom GitHub Actions workflow"); 429 when rate limits apply. Files over 100 MiB are blocked, with a warning at 50 MiB
  (docs.github.com, "About large files on GitHub").
- The main site: `docs/` holds 747 MB (`docs/dev` 737 MB in 51,624 files); the repository's packs are 790 MiB.
- Its last 12 Pages builds (Oct 3 to Oct 8, `gh run list`) took 1 minute 29 seconds to 4 minutes 40 seconds, most about
  1.5 minutes.
- Caching, tested with three requests to the published site: every file is served with `Cache-Control: max-age=600`
  through GitHub's CDN; a request with `?t=...` added was answered from the same cached copy (`X-Cache: HIT`, same
  ETag), so a query string does not fetch a fresh file; a "404" is cached too.

**What follows:**
- A file at a fixed address can be 10 minutes old for a reader. Hence one tiny fixed file (`now.json`) and snapshot
  folders with new names; a page never asks for a file before it exists.
- Publishing more often than every 10 minutes buys little. Every 10 minutes is 6 builds an hour, under the soft limit
  with room to spare.
- A reader sees figures about 10 to 20 minutes after the state posts them (at worst about 24): up to 10 minutes to the
  next publish, under a minute to push, the build, up to 10 minutes in the CDN, up to 2 minutes until the page looks
  again. Every number carries its time.

**Options for the live figures (John chooses; the address `/night-live/` is the same in all three, so the pages need no
change if he switches):**
- **B, recommended: a second public repository**, `night-live`, in the thecivicarchive organization, with Pages
  published from its main branch, served at `https://thecivicarchive.github.io/night-live/` (same origin as the pages,
  so nothing extra is needed). The updater keeps a clone in `election_live/`, copies `site/night-live/` into it, makes
  one fresh commit with no history and force-pushes. The repository stays the size of one snapshot (about 30 MB), builds
  are small and quick, the main site and its history are never touched, and it has its own 10 builds an hour. John's
  step: create the repository and switch Pages on (five minutes), or say yes and Claude runs the two commands.
- **A, no new repository**: the live folder is copied to `docs/night-live/` in the main repository, committed alone
  (`git add docs/night-live` only, never the whole draft) and pushed every 10 minutes. Each push rebuilds the whole
  750 MB site (1.5 to 5 minutes), every snapshot stays in the repository's history for good (tens of MB a night, on a
  repository already at 790 MiB of a recommended 1 GB), and a normal publish of the draft shares the same 10 builds an
  hour.
- **C, fresher but needs a sign-up**: a free account with a host that lets a site set its own cache time (Cloudflare
  Pages or Netlify), with a token kept on John's computer; figures could reach readers within 1 to 2 minutes. A new
  company in the chain and a token to look after. Not recommended this year; an emergency route if GitHub's limits bite.
- Not used: GitHub Actions on a timer (runs late on busy evenings, and from addresses some state sites refuse);
  `raw.githubusercontent.com` (not meant as a host).

Publishing is retried every 20 seconds up to 6 times (as `publish_dev.ps1` does, for the router's lost lookups and
Windows briefly locking a file); after that the cycle moves on and the next publish sends the newest snapshot, never a
backlog. `Publish dev site.bat` and `publish_dev.ps1` never touch `site/night-live/`, which sits outside `site/dev`.

### 3.6 Logs and status

- `logs/night_<yyyy-mm-dd>.log`: every request (host, path, status, bytes, time taken; never a body), every snapshot
  (state, version, rows, checks), every publish (seq, files, push result). Never feed text, never an account.
- The console: one line a cycle for each state that changed ("MN 9:52 p.m.: 2,840 of 4,103 precincts; published
  9:50").
- `election_night_status.md`, John's file to open, rewritten each cycle.

### 3.7 When something goes wrong

| What | What happens |
| --- | --- |
| A state's feed does not answer | retried next cycle; after 3 failures in a row the state says "the state's site has not answered since 9:40 p.m."; the last figures stay, with their time |
| A refusal (403, 429, challenge) | that host is stopped for the night; the state links out |
| A file that does not read (format changed) | held; last good figures kept; raw file kept; the state says "the state's file changed tonight; figures held as of 9:40 p.m."; the console says so; a Claude session mends `election/readers/<family>.py`, tests it with `once --state xx --from-file <raw>`, and the updater picks it up |
| The connection drops | everything is written locally first; publishing retries, then resumes with the newest snapshot |
| The computer stops or the program closes | the pages say updates paused after 25 minutes; double-clicking Start resumes from the databases (Bluesky's stream resumes from its cursor) |
| Time | stored in UTC; daylight time ends Sunday Nov 1, so Nov 3 is Central Standard Time (UTC-6); pages show the reader's own zone |

### 3.8 John: starting and stopping

- `Start Election Night.bat`: opens a window that runs `run_night.py live`, asks Windows not to sleep while it runs (a
  request that ends with the program; no setting is changed) and prints one line a cycle.
- `Stop Election Night.bat`: asks the program to finish its cycle, publish "updates paused" and stop. Ctrl+C or closing
  the window also stops it (the pages then say paused after 25 minutes).
- `Open Minnesota results folder.bat`: opens the folder the Minnesota files go into.
- `Update Election Night once.bat`: one cycle and a publish (the daily forecasts in the week before).

### 3.9 Replays and rehearsals

- Every reader reads through `election/source.py`, which can serve files from a replay folder on a clock instead of
  the internet, so a rehearsal runs the night's own code.
- Minnesota: from John's saved past Media Files, the replay reveals precincts in an order (random; small first; metro
  last; late absentee batches held back) and writes partial files into a rehearsal folder on a schedule, as his saves
  would arrive.
- Other states: their past election's final files revealed the same way by county; where a Clarity site still serves
  an earlier version folder, the real sequence of a past night (checked with one request, never swept).
- Rehearsals publish only to `/night-live/rehearsal/`. The pages read it only with `#rehearsal` in the address and say
  "Rehearsal: replayed figures from <election>. Not 2026 results."

---

## 4. Forecasts, measures and the rules

### 4.1 The forecast pipeline (model.md, sections 1 to 3)

- **Unit**: today's precinct (4,105 in Minnesota), added up to every district made of whole precincts; school districts
  from 2020 blocks, since they split precincts.
- **Inputs for Minnesota**: the Secretary's precinct tables for every general election 2012 to 2024 from the Minnesota
  Geospatial Commons (official); MEDSL's public-domain copies for judges, county offices and soil and water in 2022 and
  2024 (secondary, labelled, if John agrees); the Media Files John saves (cities, schools, hospitals, townships, the
  Aug 11 primary); ACS 2020-2024 block groups carried to precincts through 2020 blocks (on disk: B01001, B01002,
  B01003, B03002, B15003, B19013, B25003; to fetch if John agrees: B12001 marital status, B11005 households with
  children, C17002 poverty, B25038 year moved in, B29001 citizens of voting age, the CVAP file, the 253 MB block file);
  registration (the newest precinct counts and the May 1 precinct-split file, John's save); polls (AAPOR Transparency
  Initiative members only: Governor and Senate, one each); money (FEC, Campaign Finance Board); incumbency; party
  endorsements on the record; how each place voted.
- **Before Election Day, partisan races**: precinct lean (weights from the backtest) plus the 2026 statewide mood
  (Minnesota's midterm history, the national mood from member polls in the 35 Senate races, Minnesota's member polls),
  turnout (registration times midterm turnout, adjusted by the Census figures that predicted midterm drop-off),
  roll-off by office class, candidate terms (each kept only if the backtest shows it helps), and errors at statewide,
  regional, district and precinct level.
- **Before Election Day, nonpartisan races**: shares in proportion to exp(b x features), on the record only
  (incumbency, the primary share, an earlier share, a published endorsement combined with how the place voted, first
  place on a township's alphabetical ballot, names against seats). Where the record is silent the chances are equal,
  and the page says "The record gives no reason to favour any candidate here." Several seats: the chance of a seat.
  One name per seat: "Unopposed", no percentages.
- **On the night**: each reported precinct (Minnesota reports a precinct only when it is complete) gives a turnout
  ratio and a shift against the forecast; the shifts are explained by region, Census features and past swing, pulled
  toward the forecast while few precincts are in; the rest are projected (turnout times one minus roll-off, shares plus
  the predicted shift, the first-listed edge where a precinct's printed order is known); each county's late absentee
  batch is its own block (size from the county's website; lean from its reported precincts plus an unknown offset,
  about 5 points, narrowed when the county adds it); 1,000 or more draws give the chances and ranges. States that report
  by ballot type get a shift for each type.
- **The three blind spots** (John's choice): **count order** (Minnesota: which precincts come first and the late
  absentee batches; elsewhere, the order of ballot types: Florida's mail first, Pennsylvania's and New York's mail late,
  Ohio's early votes first, upload order in the all-mail states); **roll-off** (18 to 52 percent of voters skip a
  county or judicial race; measured by precinct and office class); **ballot position** (Minnesota rotates names by
  precinct; townships list them alphabetically; a prior of 0 to 1 point in partisan races and 1 to 4 in nonpartisan ones
  until Minnesota's own estimate exists).
- **What a forecast says**: each candidate's chance of winning (or of a seat), median share and 80 percent range (95 on
  request), and the likely margin of the top two. Whole percents; never 0 or 100 before the canvass ("over 99%",
  "under 1%").
- **Versions**: every run stored with its inputs' fingerprints; the method version goes up whenever a formula changes;
  a race's page draws the trend across runs and marks where a new method version begins. Pre-election runs once a day
  from Tue Oct 27 (and on a new poll, filing or saved file); live runs after each new snapshot.
- **Calibration**: backtests on 2022 and 2024, before the election and in replays at 10, 25, 50, 75 and 90 percent
  counted, in several reporting orders (random, small first, metro last, late batches held back); Brier score, log loss,
  calibration, how often the 80 and 95 percent ranges held, against "the incumbent wins" and "last time repeats"; the
  error terms are widened until the 80 percent ranges hold about 80 percent of the time in every order. Race types never
  tested (cities and schools until their files exist) say so.
- **Track record**: after Nov 3 every forecast is scored against the canvass, including how it did as the count went
  on. The `#track` page keeps it.
- **Speed**: pure Python, no numpy (John's call; not needed). Minnesota about 7 seconds a run (model scout, synthetic
  data); the limit is 30 seconds.

### 4.2 Other states: Congress, governor and the other statewide offices

- County level (precinct where a state's live feed gives precincts). Inputs: MEDSL county and precinct returns 2018 to
  2024 (public domain, secondary, labelled, if John agrees), the kit's place votes (16 states), official 2026 primary
  votes already in the ballot database (42 states), ACS county figures, polls from AAPOR Transparency Initiative members
  only, FEC totals, incumbency.
- House seats in states with new 2026 lines (AL CA FL LA NC OH TN TX UT; Missouri pending its referendum) get a forecast
  only where an official or labelled secondary source gives past results on the new lines. Otherwise the page says the
  model has no past results for the new district and shows no chance.
- The decision rule defines the outcome: plurality; majority with a runoff (Georgia, Dec 1; Louisiana's House open
  primary, Dec 12); ranked choice (Alaska, Maine, DC: first choices on the night, said so); top two (California,
  Washington).
- Forecasts for other states' legislatures and local races come after Nov 3, ring by ring; their pages say so.

### 4.3 The leaderboard (feeds.md; John's measures)

All over a rolling 60 minutes on election night (24 hours before it), recomputed every 5 minutes. News items and social
mentions are separate numbers. Boards are kept per level (statewide, Congress, legislature, county, city and school),
never one board for all.

- **Counting rules**: one story is one canonical address (no query strings, no AMP); the same wire story counts once per
  outlet; at most 3 items per outlet per race per window; an aggregator counts as the outlet it links to; social counts
  are distinct people, once per race per hour; reposts are not read.
- **Coverage per 100,000 residents** (the leveller): raw = 100,000 x N / residents; shown = 100,000 x (N + R) /
  (residents + 100,000), where R is the average rate of races at that level. The raw figure is shown beside it. Ranked
  only with 3 or more items from 2 or more outlets. Residents from ACS 2020-2024 table B01003 at the race's own level
  (already on disk for states, congressional districts, both legislative chambers, counties, county subdivisions,
  places and school districts; a district across counties adds them).
- **Attention gap**: the race's percentile for closeness (1 minus the absolute margin) minus its percentile for
  coverage, within its level, -100 to +100. The margin is the live count's once 20 percent of the expected vote is in,
  before that the forecast's median margin; with neither, not ranked; its source is printed beside it. Retention and
  unopposed races are left out. Close races with no coverage are included: that is the point.
- **Momentum**: (last hour + 1) / (hour before + 1), items plus distinct people. Ranked with 10 or more in the two
  hours. Called "rising" only when the last hour is above the 95 percent Poisson upper bound of the hour before.
- **Source breadth**: distinct outlets (registered domain) in 24 hours, and the effective number exp(-sum p ln p) over
  each outlet's share of the race's items. Ranked with 3 or more items.
- Labelled Analysis: "Counted from public headlines and posts. Not a measure of importance or of support."

### 4.4 Placing items on the map (feeds.md)

1. High: the headline names a candidate on a race's list (full name, or family name with the office or district words)
   and the outlet's home state or a state in the headline matches the race.
2. High, or not placed: a place name in the headline matched to `sl_places` or Census names within a state the outlet
   or the headline gives; a common name (Washington, Springfield, Jackson County) only when one place fits that state.
3. Medium: GDELT's most-mentioned US state or city that agrees with the outlet's home state (county from ADM2, place
   from the GNIS id); low when it disagrees (the scouts saw a Washington State paper's story placed at the White House).
4. Low: the outlet's home market, marked "placed by where the outlet is", shown only at state zoom.
5. Social posts: only through a race or place named in their text; never by anyone's location.

Each item on the map carries its confidence and the rule that placed it.

### 4.5 Privacy and copyright

- **Results** are public record. Candidates appear as the official list and the results print them. State and local
  candidates are under `ballot/found_local/RULES.md`: nothing beyond what the ballot pages may show of them.
- **News**: headline, outlet, time and link. Never the summary or the article, even where a feed carries the whole text.
  GDELT credited with a link (its terms require it) wherever its items appear.
- **Social posts are shown** only from newsrooms, election offices and candidates' official accounts, each with two
  anchors (the official website links the account, and the account points back: a Bluesky handle on the site's domain or
  naming it; Mastodon's verified link; the YouTube channel's own link). For state and local candidates, only for offices
  whose websites RULES.md lets the pages show. Text, time, account and a link; never images or thumbnails (a reader's
  browser would contact the platform).
- **Everyone else is counted**: matched in memory, added to a per-race per-minute counter; distinct people through a
  keyed hash whose key is made at start and never written, the set kept for one hour and then only its size. No account
  id, handle, text or post id of an ordinary user is ever written to disk or a log.
- **Bluesky's duties** (its developer guidelines, read by the feeds scout 2026-10-09): a deleted shown post is removed by
  the next publish; an inactive account's posts are hidden; a way to report a shown post; a public contact address that
  someone reads. **No social post is shown until John has chosen that address.** Until then the feed shows headlines
  and counts.
- **Mastodon**: count only accounts that are indexable or discoverable and not bots; skip any with #nobot; one post
  counted once (by its address) across servers.
- **Not read, and why**: X (paid API; John said no), Facebook, Instagram and Threads (no open access), TikTok and
  Reddit (registration or approval needed), AP and Reuters (no public feeds; their stories reach GDELT through member
  outlets), Bluesky's search (refused), YouTube's search (needs a key and allows 100 searches a day). The feed page says
  plainly that most candidates post where this site does not read.
- **Census figures** describe places, never voters.
- **Contact details**: readers keep only allowlisted fields; contact columns are never read or printed (Connecticut's
  address field, New Jersey's candidate e-mail lists, Philadelphia's office phones). Files kept whole on disk are never
  published. Agents print only headers, counts and allowlisted cells while exploring.

### 4.6 Words on the pages

| Where | What the page says |
| --- | --- |
| A result | "As reported by <the state's office> at 9:42 p.m. CST. Not final: <the certifying body> certifies the results on <date>." Chip: Fact |
| Certified | "Certified by <body> on <date>." Only now: "Elected" |
| Minnesota | "Copied from the Minnesota Secretary of State's results files, saved from the state's site at 9:40 p.m. The state's own site is the authority." |
| Ahead | "ahead in the count so far". Never "projected", "called", "wins", "will win", "victory", or a feed's own winner mark before certification |
| Reporting | "2,840 of 4,103 precincts have reported", and from the registry, how the state counts (Minnesota: absentee ballots that arrive after 3 p.m. on Election Day are added later, county by county) |
| Nothing yet | "No votes reported yet." Before polls close: "Polls close at 8 p.m. CST. The state releases no results before then." |
| Not read here | "<State> does not publish a live count this site may read. Its own results: <link>. Official totals are added when the state certifies them." |
| Ranked choice | "First choices. The state counts the later rounds on <date>." |
| A forecast | Chip: Analysis. "A computer model's estimate from past official results, Census figures, polls by members of AAPOR's Transparency Initiative, campaign money on file and the votes counted so far. Not a result: the official count decides." Then "62% chance; likely 50.5% to 54.0% of the vote", the inputs, the method version, the time of the run, the trend, a link to the track record |
| Early in the count | "Based on 3% of the expected vote. Early figures often move." (until 25 percent) |
| Polls open (John's words; his veto) | "Polls are still open here. If you haven't voted, your vote still counts." with "Find your polling place" (the state's own lookup; NASS's Can I Vote page, nass.org/can-I-vote, where a state has none), on every Night page and race where any part of the race's area still has open polls; on forecasts first |
| Measures | Chip: Analysis. "Counted from public headlines and posts. Not a measure of importance or of support." |
| Times | in the reader's own time zone with its abbreviation, worked out on the device |

---

## 5. The build plan to November 3

### 5.1 Rules for every agent (paste into each prompt)

```
You are building part of Election Night for The Civic Archive (C:\Users\16516\plain-congress). Read CLAUDE.md, the
memory note election-night.md and election\ARCHITECTURE.md first. Model at or below Opus 5.5 max; no Fable.
- Write only the files your task names. Read anything. Never edit build_site_dev.py, build_state_dev.py,
  build_ballot_dev.py, the ballot loaders, rubric_v1.md, seed/, CLAUDE.md or CHANGELOG.md, and never write to
  congress_119.sqlite, ballot_2026.sqlite, ballot_local_2026.sqlite or any state database.
- Never request any Minnesota Secretary of State host (*.sos.mn.gov), Kentucky's vrsws.sos.ky.gov, or any host on a
  registry's never list. Never solve, avoid or work around a CAPTCHA, challenge, bot wall, login or paywall; a refusal
  ends requests to that host. Never switch certificate checking off.
- Requests: through election/source.py once it exists (before that, states/net.py): the kit's honest User-Agent, one at
  a time per host, at least a second apart, patient address lookups. No paid service, no sign-up, no key.
- Privacy: allowlist the fields you read; never read, print, cache in new places or publish addresses, phone numbers,
  e-mail or any contact detail; print only headers, counts and allowlisted cells while exploring. Never store an
  ordinary social media user's id, handle, text or post id: counts only. State and local candidates: RULES.md.
- Copyright: headlines, outlet, time and link only; never article text or summaries.
- Honesty: official results only as results, each with its time and "not final" until certified; never "projected",
  "called" or "wins"; forecasts and measures labelled Analysis; no figure on a share image; red and blue only for party
  data; no names of the kit's files or programs on any page.
- Habits: python is .venv\Scripts\python.exe; patch files with the Edit tool (line endings differ); write patch scripts
  with the Write tool; never pipe a build through Select-Object -First; run long jobs as cmd /c "... > log 2>&1"; run
  scripts that read downloaded files with python -I; downloads in a folder of their own.
- Finish with the checks your task names, then report in plain words: what you changed and why, what you checked,
  what is left. Do not write report files.
```

### 5.2 Calendar

| Dates | Phase | Ends with |
| --- | --- | --- |
| Sat Oct 10 to Fri Oct 16 | 1. Foundations, Minnesota's results pages, the doors | Minnesota's page working from practice figures; code and look reviews |
| Wed Oct 14 to Wed Oct 21 | 2. The updater | Rehearsal 1, Tue Oct 20, 7 to 9 p.m. CT |
| Thu Oct 15 to Sun Oct 25 | 3. Every state's statewide and congressional feeds; the US page | every reader passes its replay |
| Sat Oct 17 to Mon Oct 26 | 4. The feed and the leaderboard | dry run Thu Oct 22, 6 to 9 p.m. |
| Fri Oct 16 to Tue Oct 27 | 5. Forecasts | backtest report; first public forecasts Tue Oct 27 (with John's yes) |
| Mon Oct 26 to Wed Oct 28 | 6. Reviews and fixes | confirmed findings fixed or listed for John |
| Thu Oct 29 to Mon Nov 2 | 7. Dress rehearsal Thu Oct 29, 6 to 11 p.m.; fixes Fri Oct 30; freeze Sat Oct 31; final checks Mon Nov 2 | the updater started Mon Nov 2, 6 p.m. CT |
| Tue Nov 3 | Election Day: polls close from 5 p.m. CT (eastern Indiana and Kentucky) to 11 p.m. (Hawaii, most of Alaska) and midnight (Alaska's western Aleutians); Minnesota's at 8 p.m. | |
| Nov 4 to late Nov | late counts; Minnesota's county canvass Nov 6 to 11 and State Canvassing Board Thu Nov 19 (the 16th day after, Minn. Stat. 204C.33); certified results loaded state by state; Georgia's runoffs Dec 1, Louisiana's Dec 12 | |

**Usage.** Weekly limits reset Thursdays about 3 p.m. CT (Oct 15, 22, 29). Launch agents in batches of about 10 million
tokens or less; read `get_usage` between batches; never start a batch above 40 percent of the 5-hour window; stop and ask
John at 92 percent of the week; never spend his extra usage. Keep 40 percent of the Oct 29 to Nov 5 week for the night
itself (a reader mended on the night). If time or usage runs short, cut in this order: other states' forecasts beyond
Senate and governor; Mastodon and YouTube; the legislature stretch in phase 3; share images. Never cut Minnesota, the
updater, or the statewide and congressional results.

### 5.3 Phases in detail

Agent ids (N for builders, R for reviewers, F for fixers) are used in the ownership table (5.4). All agents are
Opus 5.5.

**Phase 1, Sat Oct 10 to Fri Oct 16: foundations and Minnesota first**

Batch 1 (launch Sat Oct 10, four in parallel):
- **N1, results store and Minnesota's reader** (effort high). Writes `election/__init__.py`, `store.py`, `source.py`,
  `readers/__init__.py`, `readers/mn_media.py`, `crosswalk/mn.json`, `crosswalk/mn_precincts.json`,
  `registry/mn.json`, `tests/test_store.py`, `tests/test_mn.py`, `fixtures/mn/`. Reads `states/load_local_results.py`,
  `ballot/state_local_mn.py`, both ballot databases, `ballot_geo/mn/`, John's saved past files when present. Checks:
  the schema's self-test; every 2026 Minnesota contest (4,721 state and local, 9 for Congress) in the crosswalk or
  listed with a reason; every map precinct reachable from the files' county and precinct codes; precinct rows add up to
  each office's total in the file; `source.py` refuses a `*.sos.mn.gov` address (tested without any network).
- **N2, Minnesota's results pages** (effort max). Writes `night_common.py`, `build_night_state.py`, and in
  `build_ballot_state_dev.py` only the BallotMap paint hook (1.4). Output `site/dev/night/mn/` (the shell,
  `data/races.json`, `mapkit.js`); practice builds to `site/practice/night/mn/`. Checks: from practice figures
  (labelled "Practice: replayed 2024 figures") the map shades counties and precincts by who is ahead, nonpartisan races
  in neutral tones, not-yet-reported hatched; a reader placed at a faked spot sees their contests with results, their
  precinct's own numbers and the race totals; 320 and 375 pixels wide; light, dark and high contrast; the shell under
  380 KB; the Minnesota and Wisconsin ballot pages rebuilt and unchanged apart from `geo/mapkit.js`; no names of kit
  files; `python run_all.py smoke`.
- **N3, the Night home, its pictures and poll hours** (effort high). Writes `build_night_home.py`, `site/dev/night/og/`
  (four cards), `election/poll_hours.json` (research, polite: each state's poll closing times, by county where a state
  has two time zones, and its official polling-place lookup, each with its address and the date checked; NASS's Can I
  Vote page as the fallback). Checks: the home on the shell (`current=None` until N5's change), plain twins at grade 7
  or lower, 320, 375 and 1280 pixels; poll hours for all 50 states and DC, each with a source.
- **N4, every state's registry** (effort high). Writes `election/registry.py` and `election/registry/<code>.json` for
  the other 49 states and DC, from the scouts' files with their dates: the system and reader family, addresses, Nov 3 id
  or how to find it, cadence, status (live, care, hand, link), approval (Arizona waits for John), the state's own results
  page, certifying body and date, decision rule, how the state counts (the count-order note), the never list. Checks:
  every state present and valid; no state marked live that a scout found blocked; every state has a results page to link
  to.

Batch 2 (from Mon Oct 12, when batch 1 is done and the usage reading allows):
- **N5, the doors** (effort high). Starts only when the member-file-tabs work is saved and its files are clean in git.
  Writes `build_shell.py`, `shell_src/icons.js`, `shell_src/shell.css`, `shell_src/guide.js`, `build_home.py`,
  `Preview dev site.bat`. Checks: the front door, Method and Access rebuilt; six doors; the top bar at 1280 and 320
  pixels; the tab bar of six at 320 pixels or the fallback; guide entries for every Night page; the rider on the Night
  inner pages; smoke test; no names of kit files; the member pages unaffected.
- **N6, Minnesota's model data** (effort high; after John's yes on MEDSL and the downloads). Writes
  `election/model/__init__.py`, `data_mn.py`, `census.py`, `features.py`; `election_cache/model/mn/`; the `features`
  and `run_inputs` tables. Checks: blocks add up to the state's 2020 count; precinct figures against 2024 registration,
  outliers listed; every 2012 to 2024 contest's precinct sum equals the official total.
- **N7, the feed's groundwork** (effort high). Writes `election/feeds/__init__.py`, `outlets.py`, `accounts.py`,
  `keywords.py`; `night_feed_2026.sqlite` (outlets, accounts). Checks: the 145 outlets loaded; every official account
  with two anchors and a date; keyword sets for every Minnesota race and every federal and statewide race; a list of
  names that collide (common surnames) and the rule used for each.

End of phase (Fri Oct 16): **R1** code and data (effort medium) and **R2** look and rules (effort medium) in parallel;
then **F1** (effort high) on confirmed findings. The main session saves a version, adds an "Election Night" section to
CLAUDE.md and updates the memory note. Publishing the Night home and empty pages waits for John's yes; practice figures
are never published.

**Phase 2, Wed Oct 14 to Wed Oct 21: the updater**
- **N8, the updater** (effort max). Writes `run_night.py`, `election/live.py`, `livejson.py`, `publish.py`,
  `replay.py`, `awake.py`, the four `.bat` files, `.gitignore` (adds `election_cache/` and `election_live/`).
  Checks: a Minnesota replay (from John's past files, or a fixture if he has not saved them yet) at 6 times speed for
  two hours to the rehearsal path: a snapshot every 10 minutes, pruned, published to the live target John chose; a
  restart resumes; a dropped connection catches up; a malformed file holds the state; Stop publishes "paused"; Windows
  stays awake; the delay from snapshot to published page measured.
- **N2 again (N2b), the live poller** (effort high): `NIGHTLIVE` and the live states in `night_common.py` and
  `build_night_state.py`.
- **Rehearsal 1, Tue Oct 20, 7 to 9 p.m. CT**: Minnesota, North Dakota (its 2026 primary, election 346), one Clarity
  state (Iowa's primary, 126082) and one Enhanced Voting state (Georgia's 2024 general) replayed end to end. John is
  welcome to practise the Minnesota saves.

**Phase 3, Thu Oct 15 to Sun Oct 25: every state's statewide and congressional results**
Four readers in parallel (effort high), each owning its reader files and its states' registry and crosswalk files:
- **N9**: `readers/clarity.py` (IA CO SC WV; Oakland County, Michigan, as a labelled partial source), `tally.py` (ND AR),
  `in_enr.py` (IN), `resultssw.py` (NE NM MT SD OR).
- **N10**: `readers/enhanced_voting.py` (GA VA WA UT ID RI), `pcc_ems.py` (CT VT), `dc_boe.py`, `de_json.py`,
  `hi_text.py`.
- **N11**: `readers/civix.py` (TX), `ca_api.py` (CA), `fl_watch.py` (FL), `pa_returns.py` (PA), `nc_sbe.py` (NC),
  `la_portal.py` (LA).
- **N12**: `readers/ak_csv.py`, `md_pages.py`, `al_enr.py`, `wy_pdf.py`, `ok_export.py` (by hand), `az_cdn.py` (only
  after John's yes), `ms_frame.py` (only if the host answers in late October); the link-out states' registry files
  confirmed (WI OH MO KS NV KY TN NY MA NH ME MI IL NJ) with their results pages and certified-results sources.
Every reader: through `source.py`; fields allowlisted; a replay test on the state's past election whose totals equal
that election's certified totals (or the source's own final totals, saying which); the crosswalk to race ids with every
unmatched contest listed; the Legislature where the feed carries it and the crosswalk passes (a stretch).
Indiana's site still holds the May primary and will switch to Nov 3 in place, so N9 keeps a copy of the primary's files
first, for its replay.
- **N13, the US page** (effort high; from Mon Oct 19). Writes `build_night_us.py`, `site/dev/night/us/`,
  `night/us/data/counties/<code>.json`.
End of phase (Sun Oct 25): every reader's replay passes; `run_night.py discover` (daily from Oct 20) lists the Nov 3 ids
found and missing; the US page works from replay figures.

**Phase 4, Sat Oct 17 to Mon Oct 26: the feed and the leaderboard**
- **N14, collectors and placing** (effort high): `election/feeds/gdelt.py`, `rss.py`, `mastodon.py`, `youtube.py`,
  `bluesky.py` (the counting stream and the official stream, deletions honoured), `geotag.py`.
- **N15, measures and the feed page** (effort high): `election/feeds/measures.py`, `build_night_feed.py`.
- **Dry run, Thu Oct 22, 6 to 9 p.m. CT**: the live sources, publishing only to the rehearsal path; thresholds set
  against real volume; the privacy scan finds no ordinary account anywhere on disk; a deletion handled.
End of phase (Mon Oct 26).

**Phase 5, Fri Oct 16 to Tue Oct 27: forecasts**
- **N16, Minnesota before Election Day, and the backtests** (effort max): `election/model/forecast.py`, `backtest.py`,
  `runs.py`.
- **N17, the night's model and the three blind spots** (effort max): `election/model/live_model.py`, `simulate.py`,
  `blindspots.py`.
- **N18, other states** (effort high): `election/model/data_us.py`, `other_states.py`.
- **N19, the forecasts page** (effort high; from Wed Oct 21): `build_night_forecasts.py`.
End of phase (Tue Oct 27): the backtest report on `#track`; stored runs redo exactly; a full Minnesota live run under
30 seconds; no 0 or 100 anywhere; no forecast for an unopposed race; the first public forecasts, with John's yes.

**Phase 6, Mon Oct 26 to Wed Oct 28: reviews and fixes**
Four reviewers in parallel: **R3** look and access (the Browser pane at 320, 375, 768 and 1280 pixels with a set
viewport, dark, high contrast, Calm, keyboard, names for screen readers; effort medium); **R4** rules (privacy,
copyright, the words in 4.6, colours, no kit names; effort high); **R5** code and robustness (the updater's failure
paths, the readers' allowlists and politeness; effort high); **R6** numbers (replay totals against certified, crosswalk
gaps, calibration; effort medium). Then **F2** and **F3** (effort high), each given files no other fixer touches.

**Phase 7, Thu Oct 29 to Mon Nov 2: dress rehearsal and freeze**
- **Thu Oct 29, 6 to 11 p.m. CT**: the whole night replayed: Minnesota from the 2024 general, every live-readable state
  from its past election at its own pace, the real feed, forecasts running on the replay, publishing to the rehearsal
  path every 10 minutes; John starts it, practises the Minnesota saves, stops and restarts it; a network drop.
- Fri Oct 30: **F4** on the dress rehearsal's findings. Sat Oct 31: freeze (only fixes of confirmed failures).
- Mon Nov 2: Nov 3 ids filled; zero reports checked (Nebraska, North Dakota, Vermont, Connecticut; California's test
  numbers never shown); the last pre-election forecasts published; at 6 p.m. CT John starts the updater.

### 5.4 Who owns which file

One owner at a time; a file passes to a fixer only after its owner's phase ends.

| File or folder | Owner |
| --- | --- |
| `election/store.py`, `source.py`, `readers/mn_media.py`, `crosswalk/mn*.json`, `registry/mn.json`, `tests/test_store.py`, `tests/test_mn.py`, `fixtures/mn/` | N1 |
| `night_common.py`, `build_night_state.py`, BallotMap's paint hook in `build_ballot_state_dev.py` | N2, then N2b |
| `build_night_home.py`, `night/og/`, `election/poll_hours.json` | N3 |
| `election/registry.py`, `registry/<code>.json` (not MN) | N4 in phase 1; then each state's reader agent in phase 3 |
| `build_shell.py`, `shell_src/icons.js`, `shell.css`, `guide.js`, `build_home.py`, `Preview dev site.bat` | N5 (gated) |
| `election/model/data_mn.py`, `census.py`, `features.py` | N6 |
| `election/feeds/outlets.py`, `accounts.py`, `keywords.py` | N7 |
| `run_night.py`, `election/live.py`, `livejson.py`, `publish.py`, `replay.py`, `awake.py`, the `.bat` files, `.gitignore` | N8 |
| `election/readers/<family>.py`, `crosswalk/<code>.json` of their states | N9, N10, N11, N12 |
| `build_night_us.py`, `night/us/data/counties/` | N13 |
| `election/feeds/gdelt.py`, `rss.py`, `mastodon.py`, `youtube.py`, `bluesky.py`, `geotag.py` | N14 |
| `election/feeds/measures.py`, `build_night_feed.py` | N15 |
| `election/model/forecast.py`, `backtest.py`, `runs.py` | N16 |
| `election/model/live_model.py`, `simulate.py`, `blindspots.py` | N17 |
| `election/model/data_us.py`, `other_states.py` | N18 |
| `build_night_forecasts.py` | N19 |
| `CLAUDE.md`, `CHANGELOG.md`, the memory notes, saving versions, publishing | the main session only |
| `Publish dev site.bat`, `publish_dev.ps1` | nobody in Night (they never touch `site/night-live/`) |

### 5.5 What John must do, and when

1. **By Mon Oct 12**: answer the decisions in 5.6.
2. **By Mon Oct 12**: save Minnesota's Media Files (every text file on the Secretary's Media Files page) for the Aug 11,
   2026 primary into `states_cache\mn_local\sos\20260811\` and, if he can, the Nov 5, 2024 general into `...\20241105\`.
   If he agrees to the turnout and ballot-order inputs: the newest precinct registration counts and the May 1, 2026
   precinct-split file into `states_cache\mn_local\sos\registration\`. Without these files Minnesota cannot be rehearsed
   and its file layout cannot be confirmed.
3. **By Fri Oct 16, if he chooses option B**: create the public repository `night-live` in the thecivicarchive
   organization and switch on Pages (main branch, root), or tell Claude yes and it runs the two commands.
4. **By Tue Oct 20**: choose a public contact address for reports. No social post is shown before then.
5. **Tue Oct 20, 7 to 9 p.m. CT**: rehearsal 1 (optional for him).
6. **Thu Oct 22, 6 to 9 p.m.**: leave the computer on (the feed's dry run).
7. **Thu Oct 29, 6 to 11 p.m.**: the dress rehearsal: start, save, stop.
8. **Mon Nov 2, 6 p.m. CT**: double-click `Start Election Night.bat`; computer plugged in and online. (Or Tue Nov 3 in
   the morning, if he prefers; the feed's 24-hour window then starts later.)
9. **Tue Nov 3, from about 8:15 p.m. CT**: save Minnesota's Media Files every 15 to 30 minutes into the folder
   (`Open Minnesota results folder.bat` opens it) until the counties finish, usually after 1 a.m.; once more in the
   morning for the late absentee batches. Oklahoma's two Export files too, if he chose that.
10. **When counting is done**: `Stop Election Night.bat`, or leave it running overnight.
11. **Nov 4 to Nov 19**: start it once or twice a day; save Minnesota's files once a day until the county canvass (Nov
    6 to 11) and the State Canvassing Board (Thu Nov 19); save certified files for the walled states as they post.
12. **No free key is needed** for any of it.

### 5.6 Decisions John has not made yet

| # | Decision | Recommendation |
| --- | --- | --- |
| D1 | Where the live figures are published: B (a second public repository), A (the main repository) or C (another host, sign-up) | B |
| D2 | May the updater read Arizona's data host `cdn1.arizona.vote`, the address the official results page itself reads, while the page itself shows scripts a challenge? | his call; without it Arizona links out |
| D3 | Hand-saves beyond Minnesota on the night: Oklahoma's two Export files; New York's or Kansas's results page | Oklahoma yes (two files, reader ready); others no, link out |
| D4 | MEDSL's public-domain copies of past results, labelled secondary, for the model | yes |
| D5 | One-time downloads for the model: about 330 MB of Census tables, the 56 MB CVAP file, the 253 MB Minnesota block file, MEDSL's files for every state (about 125 MB zipped for 2024; the earlier years' county files are smaller) | yes |
| D6 | Minnesota's ballot order: rebuild it from the May 1 counts (an estimate) or write to the 87 county auditors for their rotation reports (his step) | rebuild, labelled an estimate |
| D7 | The Internet Archive's captures of the Secretary's past results pages, to learn past reporting order | no; the order is learned on the night |
| D8 | A public contact address for reports (Bluesky's guideline; also the Access page's barrier reports) | needed before any post is shown |
| D9 | Kentucky: write to the State Board asking whether a published feed exists (his step), or link out | link out this year |
| D10 | The door's words: "Election Night" in the top bar, "Results" on the phone tab, "Follow the count, race by race." | approve or change |
| D11 | Start the updater Mon Nov 2 at 6 p.m. (about 36 hours of running) or Tue Nov 3 in the morning | Mon Nov 2 |
| D12 | Later: a third switch on the ring of cards and the ballot door; a third poster in the cabin | after Nov 3 |

---

## 6. Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| A state's site refuses scripts (15 states today; more may on the night) | link to the state's own results; certified totals added when the state certifies; John's hand-saves only where he chose them; never worked around |
| A feed changes its format on the night | structure checks hold the state and keep the last good figures with their time; the raw file is kept; a Claude session mends the reader and tests it on the held file; 40 percent of that week's usage kept for this |
| GitHub's limits: 10 builds an hour, a 10-minute cache that ignores query strings, a 1 GB site, 100 GB a month | 10-minute publishing; new snapshot folders plus a tiny pointer; option B keeps the live site small and the main site untouched; Night's static files under 25 MB; pages fetch only what they show, only on change, only while visible; option C if bandwidth runs out |
| The main site itself is at 747 MB of 1 GB | Night reuses the ballot's map files by address; share images limited to four; John should know the next large addition anywhere needs the planned split (code and pages in separate repositories) or trimming |
| John's computer, power or connection fails | pages say updates paused after 25 minutes, keep the last figures with their time and link to each state; restart resumes from the databases; nothing partial is published as a total |
| The model is wrong early in the night | pulled toward the forecast while few precincts are in; wide ranges; "Based on 3% of the expected vote" until 25 percent; calibrated in replays in several reporting orders, including metro last and late batches; never a call; labelled Analysis; the track record shows how it did through the night |
| A contest matched to the wrong race | never guessed; unmatched contests are not shown and are listed; control totals |
| Test numbers before polls close (California serves them today) | nothing before a state's first poll closing is treated as real; zero reports checked Nov 2 |
| Minnesota's saves late or missed | the page shows the time of the last save; the Secretary's site is named as the authority |
| A certificate fails (South Dakota's had expired) | never switched off; link out; rechecked in late October |
| Usage runs out | batches, readings, the 92 percent stop, the cut order in 5.2 |
| Parallel work (member-file-tabs now; Kentucky's ballot page later) | Night never edits the record builders; N5 waits for clean shell files; no ballot page agent edits `build_ballot_state_dev.py` while N2's hook is open |
| Bluesky's stream or a Mastodon server goes down | counts from the sources still in; the board says which sources are in |
| A common surname places a story on the wrong race | the placing rules; the collision list; low-confidence items shown only at state zoom |
| This router's lost address lookups | patient lookups and retries everywhere |

---

## 7. Every state on November 3

Status: **live** a program may read the state's own feed; **care** readable with conditions; **hand** John saves files;
**link** the page links to the state's own results and fills in when the state certifies. Every live or care state is
read for its statewide and congressional races by Nov 3, its Legislature where the feed carries it, and its local races
later. Minnesota is read at every level.

| State | System | Status (2026-10-09) | Reader | On the night |
| --- | --- | --- | --- | --- |
| AK | Division of Elections' static files | care: the issuer repair works; 26genr page posted, no files yet | ak_csv | first choices; ranked-choice rounds about Nov 18 |
| AL | Secretary's election-night pages | care: empty between elections | al_enr | read if the pages allow; else link |
| AR | Tally API | live; Nov 3 not listed yet | tally | live |
| AZ | results page behind a challenge; data host answers | care: needs John's yes; Nov 3 id not posted | az_cdn | live with his yes; else link |
| CA | api.sos.ca.gov/returns/ | live; serving Nov 3 test numbers now | ca_api | from 8 p.m. PT; counting goes on for weeks |
| CO | Clarity | live; Nov 3 not listed | clarity | live, by county |
| CT | CTEMS JSON | live; Nov 3 is 108, posted | pcc_ems | live, by town; probate judges and registrars too |
| DC | JSON | live; Nov 3 not listed | dc_boe | live; ranked-choice rounds later |
| DE | JSON | live; GE2026 expected | de_json | live, with ballot types |
| FL | Florida Election Watch file | live; 20261103 file expected | fl_watch | from 8 p.m. ET, by county |
| GA | Enhanced Voting | live; not posted | enhanced_voting | live; Dec 1 runoff rule |
| HI | text summary | live; folder not posted | hi_text | from 7 p.m. HST (11 p.m. CST), mail and in person apart |
| IA | Clarity | live; not posted | clarity | live |
| ID | Enhanced Voting | live; not posted | enhanced_voting | live |
| IL | 108 local authorities; no statewide live count | link | (Cook County later) | link; certified totals in December |
| IN | Election Division JSON | live; still the May primary (copy it first) | in_enr | live, by county, every 2 minutes |
| KS | election-night page behind Cloudflare | link | | link; precinct workbooks after certification |
| KY | live results host (acceptable-use block) | link; never polled | | link; certification PDFs |
| LA | Voter Portal JSON | live; election 344, folder 20261103 posted | la_portal | every level; the House is an open primary, runoff Dec 12 |
| MA | no live count | link | | link; ElectionStats after certification |
| MD | Board pages, data files after the canvass | care | md_pages | read if the pages allow; mail counted for days |
| ME | workbooks days after | link on the night | | link; workbooks and ranked-choice rounds the next week |
| MI | no statewide count; counties | link | (clarity for Oakland, labelled partial) | link; official results after the canvass |
| MN | Secretary's Media Files (CAPTCHA to this computer) | hand | mn_media | every level, by precinct |
| MO | results site behind a Cloudflare CAPTCHA | link | | link; Grand Totals PDF later |
| MS | results frame answered 503 | link (recheck late October) | (ms_frame) | link; recapitulations later |
| MT | Secretary's pages and exports (form postbacks) | care | resultssw | read if the exports allow |
| NC | State Board JSON | live; Nov 3 listed | nc_sbe | live, every level, ballot types |
| ND | Tally (resultsnd) | live; Nov 3 is 348, posted | tally | live, every level |
| NE | CSV exports | live; Nov 3 loaded with zeros | resultssw | live |
| NH | blocked; nothing live | link | | link; town returns days after |
| NJ | 21 county clerks only | link | | link |
| NM | CSV exports with ballot types | live; election 2917 not open yet | resultssw | live |
| NV | Incapsula wall | link | | link |
| NY | results page behind Cloudflare; New York City's site answers | link (New York City later) | | link |
| OH | LiveResults behind Cloudflare | link | | link |
| OK | results site refuses scripts | hand if John saves the two exports; else link | ok_export | by hand |
| OR | results site dormant between elections | care: recheck election week | resultssw | read if it answers |
| PA | Department of State API | live; Nov 3 id not posted | pa_returns | live, with Election Day, mail and provisional apart |
| RI | Enhanced Voting | live; not posted | enhanced_voting | live, with ballot types |
| SC | Clarity | live; id to find | clarity | live, with ballot types |
| SD | Secretary's pages | care: certificate expired 2026-10-09 | resultssw | read if renewed; else link |
| TN | CloudFront refusal | link | | link |
| TX | Civix | live; 53815, specials 66734 and 66618 | civix | live, early votes apart |
| UT | Enhanced Voting | live; not posted | enhanced_voting | live |
| VA | Enhanced Voting | live; 2026-November-General posted | enhanced_voting | live |
| VT | Election Management System JSON | live; guid posted | pcc_ems | live, by town |
| WA | Enhanced Voting and its workbook | live; 20261103 posted | enhanced_voting | live; daily counts to Nov 24 |
| WI | no statewide count; county sites walled | link | | link; canvass in late November |
| WV | Clarity | live; id unknown | clarity | live |
| WY | PDF summaries as counties finish | care | wy_pdf | county by county, complete counties only |

Totals: live 25 states and DC; care 8; hand 1 (Minnesota), plus Oklahoma if John chooses; link 15.

---

## 8. Sources checked

- The scouts' files, `election/scout/`, every finding dated 2026-10-09 with its address.
- GitHub, "GitHub Pages limits", https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
  (read 2026-10-09).
- GitHub, "About large files on GitHub",
  https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github (read
  2026-10-09).
- The published site's headers, https://thecivicarchive.github.io/dev/index.html (plain and with `?t=`) and
  https://thecivicarchive.github.io/dev/ballot/us/data/districts.json, and a missing address under /dev/night/, three
  requests with the kit's User-Agent, 2026-10-09 about 11:40 p.m. CT: `Cache-Control: max-age=600`; the query string
  served from the same cached copy; the 404 cached.
- The repository: `gh run list` for thecivicarchive/thecivicarchive.github.io (Pages builds Oct 3 to Oct 8);
  `git count-objects -vH`; sizes of `docs/` (2026-10-09).
- Minn. Stat. 204C.33, https://www.revisor.mn.gov/statutes/cite/204C.33 (read 2026-10-09): county canvassing boards
  meet between the third and eighth days after the state general election; the State Canvassing Board on the 16th day.
- NASS, Can I Vote, https://www.nass.org/can-I-vote (found by search 2026-10-09; it sends readers to each state's
  official polling-place lookup).
