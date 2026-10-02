# Plain Congress build kit

You are running a data pipeline on John's own computer. John is a tax professional who builds systems, not a
software developer. Speak plainly, give one short status line per stage, and ask before anything that costs money,
deletes data, or changes the rating rubric.

## What this project is

Plain Congress catalogs every bill and joint resolution in the 119th Congress (introduced since 2025-01-01), loads
every recorded floor vote member by member, and builds a one-file website (`site/index.html`) with plain-language
bill cards and a state-by-state vote map. Sources are public records: GovInfo Bill Status bulk data (GPO and the
Library of Congress), House Clerk and Senate roll-call XML, and the `congress-legislators` member roster.

## How to run it

Everything goes through `run_all.py`. Use `python3` on a Mac and `python` (or `py`) on Windows. The first run creates
a private environment in `.venv` and installs five small packages (openpyxl, pyyaml, certifi, pillow, pyshp); do not create another environment or install anything
system-wide.

| Command | What it does | Typical time |
| --- | --- | --- |
| `python run_all.py check` | Python, packages, disk and network checks; downloads nothing | 10 s |
| `python run_all.py smoke` | Offline test on 8 bundled bills | 10 s |
| `python run_all.py` | Full build: check, roster, catalog, titles, actions, rollcalls, profiles, donors, photos, districts, ratings, build, verify | 30 to 60 min the first time |
| `python run_all.py refresh` | Weekly update: re-downloads the catalog, then everything after it | 15 to 30 min |
| `python run_all.py <stage>` | One stage: `roster`, `catalog`, `titles`, `actions`, `rollcalls`, `profiles`, `donors`, `photos`, `districts`, `ratings`, `build`, `verify` | varies |

First run order: `check`, then `smoke`, then the full build. Run long stages in the foreground and let them finish;
the catalog prints progress every 1,000 files and the roll-call loader every 50 roll calls. If anything stops
partway, re-run the same command: downloads are cached in `billstatus_cache/` and `rollcall_cache/`, so nothing is
fetched twice. Every run writes a log to `logs/`.

Options on `run_all.py`: `--all-types` also includes simple and concurrent resolutions (H.Res., S.Res. and so on,
mostly procedural); `--skip-excel` skips the Excel workbook; `--db` picks a different database file.

## Definition of done

1. `verify_report.md` says PASS, or you have explained every CHECK line to John in plain words.
2. For every roll call with member-level votes, the member counts match the official tally (verify checks this).
3. `site/index.html` exists and is under 16 MB (the limit for publishing it as a claude.ai artifact).
4. Open `site/index.html` in John's default browser (`open site/index.html` on a Mac,
   `start site\index.html` on Windows) and show him the summary table from `verify_report.md`.

## Guardrails

- Never call the Anthropic API. Use `score_bills.py` only with `--backing-only`, `--import`, `--export-json`,
  `--review-md` or `--dry-run`. Paid rating is John's own step (`python run_all.py rate`, below). Never ask him to
  paste an API key into the chat.
- Do not edit `rubric_v1.md` or anything in `seed/`. Ratings are judgments that show their evidence; the factual
  record is never hand-edited.
- `nicknames.json` holds names that are not in the record, so John approves each one. Propose names in
  `nickname_candidates.md`, each with a link showing the name in real use; add an entry, or set `"approved": true`,
  only for a name John has approved in the conversation. The record's own titles come from `load_titles.py`.
- Never write a description of a member's character, beliefs or politics. "Get to know" shows the record (terms,
  committees, how they voted, what they sponsor) and lets the reader judge. The one piece of outside prose is
  Wikipedia's opening paragraph, fenced off and labelled as not an official record.
- Donor lists name organizations only: PACs, party committees, other candidates' committees (John's decision,
  2026-09-20). People who gave are public record at the FEC, but here they appear only as totals; don't add their
  names, or "employees of X" groupings, unless John asks. Outside spending (super PACs and the like) is always shown
  apart from donations, with a sentence saying the campaign never received it. Joint fundraising committees and a
  member's own committees are not donors; what they pass along is reported as "moved in".
- Do not change the database by hand to make verify pass. If numbers don't reconcile, report which votes and why.
- Do not delete `billstatus_cache/`, `rollcall_cache/`, `congress_119.sqlite` or `logs/` without asking.
- Keep request rates as they are (8 parallel downloads for GovInfo, 4 for roll calls). These are public servers.
- Keep the User-Agent honest (it identifies the tool as personal legislative research); don't impersonate a browser.
- If you change a script: say what and why, run `python run_all.py smoke`, then re-run only the affected stage.

## Troubleshooting

- **`python` not found**: on Windows try `py run_all.py ...`; on a Mac use `python3`. If neither works, Python isn't
  installed or isn't on PATH (John's guide covers installing it).
- **`CERTIFICATE_VERIFY_FAILED`** (usually a Mac with Python from python.org): `run_all.py` points Python at the
  bundled certifi certificates automatically; if a script run on its own still fails, run the "Install
  Certificates.command" file in the Python folder under Applications, or set `SSL_CERT_FILE` to
  `.venv`'s certifi bundle.
- **Check stage FAILs on a website**: the check asks each site up to four times over half a minute, so a FAIL means
  the site stayed out of reach. Confirm the machine is online; a work VPN or firewall can block government sites. Try
  again off the VPN.
- **HTTP 403 or timeouts from clerk.house.gov or senate.gov during `rollcalls`**: wait a few minutes and re-run
  `python run_all.py rollcalls`. Failed roll calls are retried; cached ones are reused.
- **GovInfo listing errors (406, empty listing)**: `congress_catalog.list_folder` sends the Accept header GovInfo
  requires; wait and retry, since GovInfo refreshes this data every 4 hours.
- **verify says the district lines are the 2016 vintage**: census.gov was not reachable when the districts stage ran (a VPN or firewall, usually). Run `python run_all.py districts` on a normal home network; it downloads the current Census file and rebuilds the lines. Then `python run_all.py build`.
- **Portraits missing for some members**: the source project has no photo for a few members; the site shows a party initial instead. `python run_all.py photos` retries failures.
- **"member id(s) missing from the roster"**: run `python run_all.py roster`, then `python run_all.py rollcalls`.
- **A vote doesn't reconcile in verify**: open its official roll-call page from the report and compare. Report the
  vote and the difference to John; don't patch the data.
- **Site over 16 MB**: `python build_site.py --db congress_119.sqlite --out site/index.html --summary-chars 80`
  (shortens summaries on introduced-only bills; the full summary stays one tap away on Congress.gov).
- **Excel stage slow or memory-hungry**: re-run the catalog with `python run_all.py catalog --skip-excel`.
- **`getaddrinfo failed` during `donors`**: the FEC's bulk files sit on a storage host with a long name, and some
  home routers drop one address lookup in three. `load_donors.py` already asks again patiently; if it still gives
  up, wait a minute and re-run `python run_all.py donors`. Files already fetched are kept in `fec_cache/`.

## Files

| File | Purpose |
| --- | --- |
| `START_HERE.txt` | The plain-words walkthrough John follows; `Start Claude Code (Mac).command` and `Start Claude Code (Windows).bat` open this folder in Claude Code with one double-click (installing Claude Code the first time) |
| `run_all.py` | Orchestrator: stages, private environment, logs, verify report |
| `congress_catalog.py` | Downloads GovInfo Bill Status XML and loads the database (and Excel copy) |
| `load_legislators.py` | Loads the member roster: age, years in Congress, phone, website, Senate ID crosswalk |
| `load_titles.py` | Reads every title the record carries (the popular title, and the short title at each stage) from the cached Bill Status files into a `titles` table; downloads nothing |
| `load_actions.py` | Every action of every measure, in the order it happened, from the cached Bill Status files into an `actions` table (68,407 rows; nothing downloaded; 8 seconds). The draft builds each measure's path from it |
| `nicknames.json` | Names in common use that are not in the record, kept by hand; the draft site shows only entries John has approved |
| `load_roll_calls.py` | Loads every linked House and Senate roll call, member by member, with a disk cache |
| `load_profiles.py` | What the member cards say about who someone is: every term served, committee seats and official social accounts from the roster project, and the opening paragraph of their Wikipedia article (cached in `profile_cache/`, one polite request a second). The Wikipedia text is not a government record; the site fences it off, says so, credits it and links to it |
| `load_donors.py` | Campaign money from the Federal Election Commission's public bulk files, 2016 through 2026 (about 170 MB, cached in `fec_cache/`, no key): which FEC candidate numbers belong to which member, each campaign's own totals, and every itemized payment by a committee to, for, or against a member. Organizations only; memo lines are left out, as the FEC's totals leave them out |
| `money_views.py` | Shapes those tables for the site: each member's top donors by cycle and office, every payment behind them, and outside spending kept apart. `build_site_dev.py` calls it; it downloads nothing |
| `run_states.py`, `states/` | The state side: `places.py` (what each state calls its chambers and parties, its election year, map zooms and the money agency's page addresses), `net.py` (polite, patient downloads), `load_people.py`, `load_sld.py`, `load_legiscan.py`, `money_mn.py`, `money_views.py` (shapes a state's money tables for the pages, as `money_views.py` does federally). See "The state side" below |
| `states/share_state.py` | A state's share pages (`m/<id>.html`) and 1200 by 630 preview images (`og/`), drawn with `share_cards.py`'s type and colours: portrait, seat, committees, money on file and the district picked out on the state. Redrawn only when what they show has changed. Portraits come from the originals the people stage keeps in `states_cache/photos/<code>/` |
| `states/save_key.py`, `Save LegiScan key.bat` | John's own step for the LegiScan key: he pastes it into a window where it is not shown, and it is saved as `legiscan_key.txt`. Never run it for him with a key, and never read that file |
| `build_state_dev.py` | Builds one state's draft pages into `site/dev/<code>/` from `state_<code>.sqlite`, the district file and `places.py`. It takes the styles and the shared parts of the page from `build_site_dev.py` at build time (the landmarks are listed in `BORROWED`), so the two sides look and behave alike; if a landmark goes missing the build stops and names it |
| `load_photos.py` | Official member portraits (public domain, unitedstates/images) as 2 KB WebP thumbnails in the database |
| `load_districts.py`, `albers_usa.py` | House district lines for the map's zoom-in view: Census cartographic file for the current Congress when reachable, else the 2016 lines from GitHub; projected into the map's Albers space |
| `us_districts_albers.json` | The district lines the site embeds (the kit ships the 2016 fallback; the districts stage replaces it with the current Census lines) |
| `district_shapes.py`, `district_people.py` | The districting lenses: the shape of every district (Polsby-Popper, Reock, convex hull) and who lives in each (2020 count, people per seat against the ideal, ACS estimates with margins), for Congress and every state chamber, each with a self-test, fingerprinted sources, control totals and a CSV of every figure |
| `score_bills.py` | Ratings: import, party backing from roll calls (`--backing-only`, free), optional Claude API scoring |
| `build_site.py` | Builds the one-file website from the database |
| `run_ballot.py`, `ballot/`, `build_ballot_dev.py` | On The Ballot: who is on the November ballot, race by race, from each state's official candidate list, with FEC money; builds `site/dev/ballot/`. See "On The Ballot" below |
| `door_transit3d.js`, `vendor/three.module.min.js` | The two crossings between the front door and On The Ballot, drawn in 3D in the first person with three.js (MIT); `build_door.py` copies both into `site/dev/` |
| `rubric_v1.md` | The rating rubric (read-only) |
| `seed/seed_ratings_119.json` | Ten hand-applied preview ratings for current bills |
| `us_states_albers.json` | State map shapes (public domain, from the us-atlas package) |
| `schema_postgres.sql` | The same database schema for Postgres, for a hosted version later |
| `tests/samples/` | Eight real 2025-26 bills for the offline smoke test |

## The draft site (versions 4.x)

The live site at thecivicarchive.github.io is built by `build_site.py`. Alongside it there is a draft, built by
`build_site_dev.py`, where changes are tried first. From version 4.0.000 on, every build of the draft carries a
number in the 4.x.xxx chain and every saved build can be brought back.

- `Preview dev site.bat` builds the draft and opens it at http://127.0.0.1:8790/ (a small local server; the
  draft is several files, so it cannot be opened from a double-click the way the one-file site can). That address
  is the front door; the federal side is at http://127.0.0.1:8790/us/.
- `Publish dev site.bat` copies the draft to `docs/dev/` and pushes it; it appears at thecivicarchive.github.io/dev/.
- `Save this version.bat` commits everything and tags it with the version named at the top of `CHANGELOG.md`.
  `Go back to a version.bat` restores any saved version. Both call `version.py`, which also has `current`,
  `next`, `new` and `list`.
- The version lives in one place: the newest heading of `CHANGELOG.md`, `## v4.0.002 — 2026-09-20 — title`.
  The build stamps it on the badge, the footer and a meta tag. Every change gets a changelog entry written for
  a reader; the last three digits go up with each saved build, the middle number when John signs off a milestone.

The draft has a front door and rooms behind it. `build_door.py` writes the front door, `site/dev/index.html`: a
small page that welcomes everyone, with a ring of cards turning in 3D (one card per level of government) and a
three-second page-turn into the chosen space; its State card opens a map of the country built from
`states/places.py` and whatever each state's database holds. The federal side lives one step inside, in
`site/dev/us/` (thecivicarchive.github.io/dev/us/), and each state will live in its own two-letter folder
(`site/dev/mn/`, written by `build_state_dev.py`). `Preview dev site.bat` builds the federal side, Minnesota and the
door; `Publish dev site.bat` mirrors the whole of `site/dev`.

The federal draft build writes two things. `site/dev.html` is the one-file archive (everything inline; the 16 MB rule
in "Definition of done" applies to it). `site/dev/us/` is the fast site: `index.html` is a small shell, and
`data/*.json`, `data/bill/<key>.json`, `data/member/<bioguide>.json`, `data/donors/<bioguide>.json` (a member's top
hundred donors, every payment, and outside spending; about 42 MB across all members) and `photos/*.webp` are
fetched only when a page needs them. The one-file archive carries each member's top ten donors only. The two share
one page template and one code path, so a change to either is a change to both. When you change the page's
code, test both: the fast site through the local server, the archive from its file.

From version 4.0.044 (John, 2026-09-27) every draft page opens light (`||"light"` in each page's head script and in
the theme code; a reader's saved choice still wins), and three kinds of pop-out card open beside what they explain, on
hover, on keyboard focus, or on a tap: a name (`[data-person]`, any `a[href^="#member="]` that is not a chip, and the
member buttons) opens a short card of record facts, the first sentence of the fenced Wikipedia paragraph, and links to
the member's page and money; a rating bar (`[data-axis]`, with `data-bill`) opens its whole reasoning: position and range,
justification, magnitude, grade and what it means, confidence, sources, the scale's definition, and who rated it, when and
under which rubric, verbatim from `ratings.rater`; for "Who backed it" it shows the yes-rate arithmetic from the roll-call
refs; a step on a bill's path (`[data-step]` inside `[data-path]`) opens what happened that day, the deciding vote with
each party's yes and no, the votes along the way, and links to the roll call and the map. The engine is one landmarked
block (`/* ---------- pop-outs: ...` to `/* ---------- end of pop-outs ---------- */`) that the state builder borrows as
`POP`; each side writes its own `personPop` and registers it with `pop.add(selector, builder, {tap})`. A bill's path
replaced the six fixed stops: `path_for` in `build_site_dev.py` reads the `actions` table into steps (introduced,
committee, received, passed or failed, accepted or changed the other chamber's changes, disagreed or tabled, conference
report, presented, signed, law without signature, vetoed, override, law), each stored compact as
`[kind, lane, date, quick count, extras]` (extras: `d2`, `rp`, `out`, `chg`, `am`, `r` the deciding roll call, `law`,
`desk`, `tbl`, `ok`); the page draws them in three lanes (House, Senate, President; the states for a constitutional
amendment), adds dashed steps still ahead, files the measure's key votes under their steps (`filedVotes`), and lists every
step in plain words in the Votes and path tab. What each committee did (`cnotes`) rides in the fast site's bill files
only; the one-file archive leaves it out to stay under its budget.

The fast site also carries share pages, written by `share_cards.py`: `b/<key>.html` for every bill with a full
record, `v/<vote>.html` for every roll call and `m/<bioguide>.html` for every member, each with a 1200 by 630 preview image under `og/` drawn in the
site's own type (`fonts/`, Open Font License). A pasted link shows a card; a person who follows it lands on the
bill or the vote. Images are redrawn only when what they show has changed. Absolute addresses come from
`--base-url` (default `https://thecivicarchive.github.io/dev/us`); the live site would be built with its own address.

Counting visits is off until John creates a GoatCounter account (free, no cookies, no personal data) and puts
its endpoint, one line like `https://civicarchive.goatcounter.com/count`, in `analytics.txt` next to the
builder. The build then adds the counter and a sentence about it to the footer; page views, bill and vote
views and share taps are counted, nothing else. Never create that account or ask for its credentials.
The fast site is installable (a manifest, icons and a service worker that never serves a stale page).

## The districting lenses (from version 4.0.030)

John's idea (2026-09-20): let people look at the district maps through four measurable lenses, then through
rule-drawn what-if maps, so that anyone can see for themselves how the lines were drawn. His conditions: only
sources that would survive an audit, and sources and methods shown for every figure. His order: the measures first,
the what-if maps after; Congress as one national map, then Congress state by state, then state Senates, then state
Houses. He allowed respected academic compilations as well as official sources, provided each says which it is.

- The page never says a map is gerrymandered, and never ranks "worst" districts. It measures, labels every derived
  figure Analysis, says what a figure cannot tell you wherever it appears, and leaves the judging to the reader.
- Lens one, shape, is built: `district_shapes.py` measures Polsby-Popper, Reock and convex hull for every district in
  the Census Bureau's cartographic boundary file and writes `us_district_shapes.json` and `.csv`; the `districts` stage
  runs it (self-test first). Area is exact on the GRS80 ellipsoid and perimeter is geodesic, so no projection is
  chosen. The file's SHA-256 travels with the results. A district is marked "shoreline" when the Bureau's own land plus
  water area exceeds the shape's by more than 1.5 percent. The federal page is `#shapes`; `#shape=MN-5` opens one
  district; the "Sources and methods" window is part of the page.
- Lens one is on the states too (v4.0.031): `python district_shapes.py --state mn` measures a state's chambers from
  the Census ZIPs in `states_cache/census/` and writes `state_<code>_shapes.json` and `.csv`; the state `districts`
  stage runs it after the lines download. `build_state_dev.py` puts the Shapes page (`#shapes`, `#shape=H-8B`) on any
  state that has the file and hides it otherwise. The federal page's `#shapes/MN` opens one state, lists its districts
  side by side and links to `../mn/#shapes`; the shared wording lives in one landmarked block of `build_site_dev.py`
  (`BORROWED["LENS"]`) that the state builder borrows, so change it in one place.
- Lens two, people, is built (v4.0.034) at every level in one run: `python district_people.py` reads the Bureau's
  population-by-district files (`states_cache/census_rel/`: CD119, SLDU2024 and SLDL2024 UR_POPAREA) and ten ACS
  2020-2024 table files (`states_cache/acs2024/`, about 700 MB, fetched once through `states/net.py`) and writes
  `us_district_people.json/.csv` and `state_<code>_people.json/.csv`. `--selftest` reproduces the handbook's worked
  examples (sum 203,119 ±5,070; proportion 0.322 ±0.008) and checks the table shells' labels. Controls: count =
  apportionment resident population (`RESIDENT_2020`, a checked list), the three tabulations agree, ACS sums = state
  figure, under-18 from bands = B09001. The federal page is `#people` (`#people/MN`, `#people=MN-5`); the state page
  `#people` (`#people=S-61`); the shared words (`PEOPLE_MEAS`, `plValue`, `plFmt`, `plBreaks`, `plKey`,
  `peopleWords`) live in the same landmarked `LENS` block as the shape words. One "Sources and methods" box serves
  both lenses (`METHODS[kind]`, `openMethods("people")`). The state builder renames Census codes to roster names for
  the people rows as it does for shapes, and for chambers whose seats vary (MD, VT) computes people per seat from the
  roster's seat counts (`dev_from_roster`); a chamber with unmapped districts (NH House) gets no deviation, with the
  reason in `why_no_dev`. People per seat is shaded in fixed steps either side of the ideal (teal below, sand above,
  never party colours); every other figure in five equal groups.
- Every lens gets the same furniture: a named primary source with its address, date and fingerprint; the formula and
  its citation; a self-test against known answers; a control total against the source's own figures; a plain list of
  what the figure cannot tell you; a download of every number; a method version. Change a method, bump its version.
- Sources verified 2026-09-20 for the lenses to come (all keyless files on www2.census.gov; the Census data API began
  requiring a key in May 2026, so do not build on keyless API calls): 2020 PL 94-171 files; `cb_2020_*_tract/bg_500k`;
  ACS 2020-2024 table-based summary files (`acsdt5y2024-b01003.dat` and the like) for congressional and legislative
  districts; block equivalency files `cd119.zip`, `sldu24.zip`, `sldl24.zip`; `CD119_UR_POPAREA.txt` and its
  legislative twins (population and area by district); county and place relationship files `tab20_cd11920_county20_*`.
  Votes: the Clerk of the House's "Statistics of the Congressional Election" (PDF, 2022 and 2024), the FEC's Federal
  Elections 2022 workbook (2024 not yet published), Minnesota's Secretary of State result files; secondary, both CC0,
  MIT Election Data and Science Lab and Klarner's state legislative returns.

## The state side (Minnesota first)

John's plan (2026-09-20): the same record for every state legislature, Minnesota first, then outward to every state
plus DC, Puerto Rico and Guam; after that, one shared home page with a 3D carousel of cards (one card per level of
government) and a three-second page-turn into the chosen space.

Everything goes through `run_states.py`: `python run_states.py mn` runs people, districts, bills, money, check and
site; `python run_states.py mn <stage>` runs one. The `site` stage runs `build_state_dev.py` (the state's pages,
`site/dev/mn/`) and then `build_door.py`, so the front door knows the state is open; `Preview dev site.bat` does the
same after the federal build. Each state has its own database, `state_<code>.sqlite`, laid out like
`congress_119.sqlite` (the member id column is still called `bioguide_id` so the same code reads both), its own
district file `state_<code>_districts.json`, and a plain report `state_<code>_report.md`. Downloads live in
`states_cache/`. The federal database is never touched by the state pipeline.

| Stage | Source | Needs |
| --- | --- | --- |
| `people` | Open States "people" project (CC0): members, service, committees, portraits; Wikipedia's opening paragraph, fenced off as on the federal side | nothing |
| `districts` | Census Bureau cartographic boundary files, upper and lower chamber | nothing |
| `bills` | LegiScan weekly datasets: bills and roll calls with every member's vote (50 states and DC) | John's free LegiScan key |
| `money` | the state's own campaign-finance agency, one loader per state (`states/money_mn.py` reads Minnesota's Campaign Finance Board downloads; `states/money_ia.py` the Iowa Ethics and Campaign Disclosure Board's datasets on data.iowa.gov, 405 MB zipped, cached in `states_cache/ia_iecdb/`; `states/money_wa.py` the Washington Public Disclosure Commission's open data on data.wa.gov, fetched by SoQL query in pages of 100,000 rows, cached in `states_cache/wa_pdc/`; `states/money_co.py` the Colorado Secretary of State's TRACER yearly bulk zips, cached in `states_cache/co_tracer/`; `states/money_tx.py` the Texas Ethics Commission's 1 GB bulk zip, cached in `states_cache/tx_tec/`, an eight-minute scan; `states/money_ca.py` the California Secretary of State's Cal-Access raw data export, 1.6 GB, cached in `states_cache/ca_calaccess/`, a 90-second read; `states/money_fl.py` the Florida Division of Elections' query service, one POST per family name, cached in `states_cache/fl_dos/` for a month; `states/money_nj.py` the New Jersey Election Law Enforcement Commission's reports and data search system (njelecefilesearch.com), asked through the JSON calls its own pages make, one per chamber and election year, cached in `states_cache/nj_elec/` for a month) | nothing for Minnesota, Iowa, Washington, Colorado, Texas, California, Florida or New Jersey |

- The LegiScan key is John's. It lives as one line in `legiscan_key.txt` (ignored by git). Never ask him to paste it
  into the chat, never print or log it, and never try to get past the bot check on legiscan.com; the API manual at
  api.legiscan.com/dl/ is readable. The free key allows 30,000 queries a month and the bills stage uses about two
  per state per week. LegiScan's terms ask for a credit line; the state pages must carry it.
- The donor rule is the same as federal: organizations by name, people as totals. State files carry individual
  donors' and lobbyists' names; the loader must add those rows into totals and never write the names anywhere.
- Committees are matched to members by name and never guessed: a match needs the family name, a compatible given
  name and a chamber the member has served in, and must be the only fit. The run lists anything left out.
- Rollout rule: Minnesota is built complete, money included. Every other state goes live once people, districts,
  bills and votes are in, with a note that campaign money is coming; money is added state by state.
- Windows match the federal side: bills and votes from January 2025, money for the 2016 through 2026 cycles. A cycle
  begins in the odd year, so Minnesota's money is loaded from January 2015 and shown in the Campaign Finance Board's
  own two-year segments (2015-16 through 2025-26).
- The state pages (version 4.0.025 on): home with "who represents you" (location worked out on the device, or pick a
  district), the district map for both chambers, a roster table, a page per member (service, committees, money,
  the fenced Wikipedia paragraph) and a Sources page. Bills, votes and a statewide Money page are marked as coming
  until they are loaded. A state that is open without its bills shows on the front door as "Open, still filling in".
- Say only what the record supports. The Open States roster has no start date for many long-serving members (43 in
  Minnesota), so their pages say "before 2023" or "2009 or earlier"; never fill in a year from memory. The Board's
  contribution file lists only givers of more than $200 a year and leaves out the public subsidy, so the pages say the
  totals are lower than everything a campaign took in.
- A member's own earlier committee (a House account passed to a Senate one) is "moved in", not a donor, as on the
  federal side. The build lists every committee it treated that way by name; read that list after a money reload.
- John's order (2026-09-24): money for every state from the state's own agency, one loader at a time, never a
  compilation. A loader writes the four `state_*` tables `states/money_views.py` reads, is named in `places.py`
  (`"money": "ia_iecdb"`), dispatched in `run_states.py`, and gives its state a `"money_rule"` sentence (what the
  agency's file holds and leaves out) and, where a licence asks for it, a `"money_credit"` line; both appear on every
  money card and on the Sources page. Iowa's lessons: the register (dataset 704) only lists committees still open, so
  closed committees' candidates are read from their titles (`name_from_title`); givers without a committee number
  are totalled as "other", never named; a member's registered committee for another office is matched only when the
  full name fits exactly one sitting member. Washington's lessons: Socrata (data.wa.gov) answers keyless SoQL queries
  (`$where`, `$order=:id`, `$limit`, `$offset`); its CSV writes dates as MM/DD/YYYY; the Campaign Finance Summary
  dataset (3h9x-7bvm) is the register, with `person_id` tying a candidate's campaigns together and names written
  three ways (`readings()`); the contributor `code` column names the giver's kind, and where a state lets businesses,
  unions and other organizations give directly they are named under the kinds `biz`, `union`, `org` (in
  `states/money_views.py` KINDS and the page's SRC list and colours). Colorado's lessons: TRACER's yearly zips
  (`<year>_ContributionData.csv.zip`, UTF-16 or UTF-8 with a BOM; older years resolve though the page lists only
  recent ones) carry no office, so a match is a STATEWIDE candidate committee with no other-office word in its title
  and a full name fitting exactly one sitting member, else the title's own words or the seat it names
  (`title_reading`); skip `Amended = Y` rows; the expenditure files do not attribute independent spending to
  candidates, so `state_outside` stays empty and the `money_rule` says so. A state's `money_rule` should say what its
  file itemizes and what it lacks. Texas's lessons: the Commission's filer index (filers.csv) carries the office
  sought and held with district and a CURRENT_OFFICEHOLDER status, so the seat record settles a formal-name mismatch;
  ENTITY givers' kinds come from the same index by name (a registered GPAC is a PAC whatever the campaign wrote); the
  first six CSV fields never hold commas, so a line's filer number is read before the row is parsed; a shell heredoc
  turns `\\b` into a backspace, so write patch scripts with the Write tool. California's lessons: the Cal-Access export
  (`dbwebexport.zip`, every table as UTF-8 TSV, format guides inside) carries the candidate, office (ASM, SEN) and
  district on every statement's cover page (CVR_CAMPAIGN_DISCLOSURE), and FILER_LINKS type 12011 ties every committee
  to one candidate record, so match by the cover page's name and then take every committee of the same record; the
  entity code is not reliable (real candidate committees appear as RCP), so a committee's purpose is read from its
  name and offices, and ballot measure committees and other-office committees are left out and listed; the highest
  AMEND_ID replaces a filing; gifts are Form 460 Schedules A and C only (Form 497 repeats them), memo lines out,
  under-$100 sums from SMRY line A-2, loans from B1; outside spending is Schedule D and Form 461 Part 5 with
  EXPN_CODE IND (Forms 496 and 465 duplicate them), and spenders write the candidate's whole name in CAND_NAML, so
  split it; a transfer (TRAN_TYPE X) is attributed by Cal-Access to the original givers, so record it as coming from
  INTR_CMTEID instead (a member's own committees then show as moved in) and skip forgiven loans (TRAN_TYPE F); a
  statement can be filed twice under two FILING_IDs (same filer, FROM_DATE, THRU_DATE: keep the later); a committee's
  purpose is read per statement too (only covers naming ASM/SEN count, officeholder accounts and legal defense funds
  whole); campaigns file people under the OTH and COM codes and register people as major donors, so `People` in the
  loader reads names (the file's own given names, credentials, trusts, estates, dba, "and affiliated entities",
  "LAST, FIRST", a person beside a business) and cuts contact names off business names; a business named after its
  owner may be hidden, a person is never shown; cal-access.sos.ca.gov sits behind an Incapsula bot wall, so no donor
  links. Florida's lessons: no bulk file; the Division's form (`/cgi-bin/contrib.exe`, POST, `queryformat=2`, blank
  `rowlimit` = every row) returns a tab-separated file of Candidate/Committee "Last, First (PARTY)(OFFICE)", date,
  amount, type (CHE, CAS, INK, LOA, REF, INT, COF, X), contributor name, address, city, occupation, in-kind text; it
  gave 502 to everything one day and answered the next, so retry rather than rewrite; `CanNameSrch` 1 and 2 both match
  the start of the family name (3 is soundex), so filter for the exact name yourself; no district in a row (query by
  `cdistrict` when one is needed) and no giver type at all, so an organization is named only when its name or its
  occupation column says committee, party or company, else it is counted with people; individuals are written
  "LAST FIRST M"; expenditure records do not say which candidate a committee spent for or against, so no outside
  spending. New Jersey's lessons: elec.nj.gov sits behind an Incapsula bot wall (212-byte stub) and its old data-download
  page is gone, but the Commission's search system njelecefilesearch.com answers plain requests; its pages are DataTables
  fed by form-encoded POSTs (`/api/VWEntity/Entities20` for the register of every candidacy by office code, 1 Senate,
  2 Assembly, E joint candidates committee; `/api/VWContributionDetail/GetContBitsDataByObject` for the rows, `length`
  up to 100,000 honoured; `/api/VWContributionDetail/DownlodDataCSV` returns a signed link to a CSV with fewer columns)
  and `GET /api/VWEntity/GetEntityList?LastName=` finds accounts by name; one account per candidate per election (year
  and type P/G), with office, legislative district and party; the Commission codes every giver (`CONT_TYPE`: A
  individual, B business, H union, C party, R legislative leadership committee, Q/D candidate committees, E/F/G/I/J/V/W/X
  PACs, Z political club, Y not provided, K/L/N miscellaneous) and every receipt (MONETARY, IN-KIND, CURRENCY, LOAN,
  LOAN PAY, ADJUSTMENTS negative, INTEREST); joint candidates committees hold a third of legislative money and carry no
  link to their candidates, so `named_in` reads the family names from the title against the register's slate for that
  district, election and party (one slip of spelling allowed) and every gift is divided equally among them; a member's
  own committee paying into the joint committee is "moved in"; a business coded B under a person's own name (a doctor's
  practice) is counted with people; a few dates are typed as 3026, filed under the account's election year; no outside
  spending (expenditures name payees only, Form IND reports are PDFs). New York's lessons: publicreporting.elections.ny.gov
  and the file host cfapp.elections.ny.gov sit behind a Cloudflare challenge that a plain fetch cannot pass and must not
  be worked around; the Browser pane passes it, and a JavaScript result larger than the tool's limit is saved to a file
  under the session's tool-results folder, so the Bulk Download files were carried out of the pane as base64 pieces
  (in-page `fetch` after `POST /DownloadCampaignFinanceData/SetSessions/` {lstDateType, lstUCYearDCF, lstFilingDesc},
  then `GET /DownloadCampaignFinanceData/DownloadZipFile?...`; 30 MB slices tagged `ZIPB64:<name>.partNN:<len>:<b64>`,
  decoded and joined into `states_cache/ny_boe/`). `states/money_ny.py` therefore downloads nothing and reads what is
  there: ALL_REPORTS_StateCommittee.zip (year All, type State Committee: every state-level committee's transactions
  since 1999, 441 MB zipped, 11.9M rows), ALL_REPORTS_StateCandidate.zip, any one-year period file (2025jul.zip and the
  like, read last so a newer copy of a transaction wins), filers.json (the List of Filers page's data, `POST
  /ActiveDeactiveFiler/GetSearchListOfFilersData` lstDateType=All: 64,677 filers with id, name, candidate or committee,
  office, district, status) and links.json (which candidates each authorized committee was formed for: `POST
  /ActiveDeactiveFiler/GetSearchListOfFilersCandidateData` strFilerID=, one call per committee, run as a loop inside
  the pane). The all-years files carry FILER_PREVIOUS_ID as their second column and the period files do not (59 against
  58 columns); the guide's 45 named fields are followed by public-financing flags and the giver's employer, occupation
  and address, which are never read. Every transaction has a TRANS_NUMBER (an amended report repeats it: keep the last
  copy). Schedules: A individuals and partnerships (CNTRBR_TYPE_DESC Individual, Partnership, Candidate/Candidate Spouse,
  Candidate Family Member, Sole Proprietorship, Unitemized), B corporations, C all other (PAC, Political Committee,
  Union, PLLC/LLC, Association, Other), D in-kind, E other receipts, G transfers in (Type 1 from a party committee, Type
  2 between the candidate's own committees: moved in), I loans, M contributions refunded (netted), L expenditure refunds,
  P housekeeping, S public funds; F, H, J, K, N, O, Q, T, U are spending, liabilities and the owners behind an LLC. A
  candidate's register row carries only their latest office, so a member is matched by name whatever the chamber, and
  a candidacy for the member's own seat under another given name (Palmo for Paul) counts only when registered in the
  member's own time; relatives and predecessors hold the same seats often (Weprin, Wright, Hevesi). A committee the
  Board lists for several distinct people (the same person registered twice is one) is shared equally, as New Jersey's
  joint committees are; rows are keyed by (filer, schedule, TRANS_NUMBER) because a transfer's two sides can share a number. Schedule R rows carry an
  office and district but no candidate name, so no outside spending. Names come title-cased; the leadership committees
  are spelled many ways (DACC, NYS Democratic Assembly Campaign Committee...), folded by `donor_key`. Loaders still to
  write: Oregon has no bulk file (ORESTAR export only); North Dakota 2025-26 only; Wisconsin waits on John's robots.txt
  answer; South Dakota has PDFs only.
- Free text can name a person, so none of it reaches the site: outside spending's "purpose" column stays in the
  database and is never written to a page, and the contribution file's employer and in-kind description columns are
  not loaded at all.
- "Forget my location" on a state page clears the same `pin` the federal pages keep, plus the state's own
  `sld:<code>` record of the reader's districts; keep it that way, so one tap forgets everywhere.
- When you change a shared part of the federal page (anything named in `BORROWED` in `build_state_dev.py`), rebuild
  and look at a state page too.
- All fifty states are open (v4.0.033), built in rings outward from Minnesota. Still to come: the District of
  Columbia, Puerto Rico and Guam, each with a loader of its own.
- Named districts (Massachusetts "First Middlesex", Vermont "Chittenden Southeast", New Hampshire "Belknap 7"): the
  Census file codes them (D11, CHS, 007) and `load_sld.py` keeps the Bureau's name for each; `crosswalk_names()` in
  `build_state_dev.py` matches roster names to Bureau names by spelling (`spelling()`: ordinals as numbers, hyphens,
  commas, "and" and the kind-of-district words set aside), requires a unique match, and files the shapes, the Shapes
  page rows and the CSV under the roster's names. A chamber whose districts are named sets `"district_name": ""` in
  `places.py`, and `dLabel()` in the page code then uses the name alone; never write "District" in front of one.
- A roster district with no shape (New Hampshire's floterial districts, Maine's tribal representatives) is
  `unmapped`: listed in the roster ("not on the map"), a member page without a map link, a sentence on the map page
  and under "who represents you"; the reason belongs in the state's `"note"`. A chamber that seats members beyond
  its seat count says so with `"beyond": "tribal representatives"` on the chamber, and those members are counted
  apart from the seats.
- Where districts elect different numbers of members (NH, MD, VT), `collect()` sets `varies` and reads each
  district's seats from the roster; vacancies are then chamber-level only, and the lede says "between one and
  three ... depending on the district". A joint nomination not listed in `parties` is counted with the party named
  first (`party_code`), with the whole label kept. A state can set `"tolerance"` (map pixels) for its district
  lines; Alaska uses 0.02.
- An upper chamber can have several members per district too (West Virginia, two senators a district): the
  seats-per-district logic runs for both chambers, and the "who represents you" sentence is built per chamber
  (`seat_words` in `render()`). A joint nomination such as "Democratic/Working Families" is mapped in `places.py` to
  the nominating party's colour with its own label kept. A roster district with no shape of its own whose number has one (Idaho's
  1A and 1B) is a seat within that district: the builder files the member under the district and shows the seat.
  Statewide offices are whatever the roster carries for that state (two in Tennessee, six in Arkansas). A one-chamber legislature (Nebraska) has no `"lower"` in
  `places.py`, files its members under the chamber "Legislature", and may give its districts their own name
  (`"district_name"`) and the page a sentence of explanation (`"note"`).
- `states/net.get` repairs one thing a browser repairs: a server that leaves its issuer's certificate out of the
  handshake (cdn.ilga.gov, www.house.mi.gov). It fetches that certificate from the address printed in the server's
  own certificate and still requires the chain to end at a root certifi trusts. Never turn certificate checking off
  to get a file. To add a state: add it to
  `states/places.py` (chamber names and seats, how its parties are named, Census number, map zooms; leave `"next"`
  out unless the election year has been checked against the record, and give it by odd and even district where terms
  are staggered), then `python run_states.py <code> people`, `districts`, `site`. `build_state_dev.py --place all`
  builds every state that has a database; `Preview dev site.bat` uses it. John's order (2026-09-20): keep going
  outward ring by ring at this level; campaign money follows one state at a time; bills wait.
- Some chambers elect two members from one district (the Dakotas' Houses). The pages read how many from the seat
  count and the district list, show every member of a district, and draw a district split between parties half and
  half. Which lower-chamber districts sit inside which upper-chamber district is worked out from the lines at build
  time (`nesting()`); no state's numbering scheme is assumed, and if the lines do not nest the pages say nothing.
- Statewide officials (`officials` table, from the roster's `executive` files): Governor, Lieutenant Governor,
  Attorney General, Secretary of State, and only an office held today. John's line for this wave (2026-09-20): the
  offices the roster carries; an auditor, a treasurer, judges and appointed agency heads wait for a source of their
  own. A term that ends in January was won the November before; that is how "next on the ballot" is worked out.
- A roster date of 1 January is a real year with a placeholder day, so the page gives the year alone; up to 2011 it
  only marks where the roster begins, and the page says "or earlier".
- Portraits some agencies' sites refuse to our honest User-Agent stay missing (a party initial shows instead).
  Never disguise the User-Agent to get them.
- The two sides point at each other. The federal shell carries `state_sites` (every state in `places.py` whose
  database exists), and "How did your members vote?" links a reader of such a state through to `../<code>/`; the
  one-file archive has no neighbours, so it shows no such link. State pages link back through "All levels".
- Type inside a zoomed SVG map: browsers will not draw text below a minimum size, and in map units a label is a
  fraction of a pixel. Keep the font at 12px and scale each label with a `transform`, as the state map does.
- LegiScan and Open States do not cover Guam, and Puerto Rico's record is in Spanish with its own parties. Those two
  come last, with their own loaders.

## The local level (Minnesota's counties first, from version 4.0.043)

John's plan (2026-09-24): the same record for county boards, sheriffs, county attorneys, then mayors, councils and school
boards, Minnesota first, then outward; party only from a partisan ballot, "nonpartisan office" where the law makes it so,
never an estimate. Everything goes through `run_local.py`: `python run_local.py mn` runs counties, results, check and
site; one stage by name. Files next to the script: `local_<code>.sqlite`, `local_<code>_counties.json`,
`local_<code>_report.md`; pages in `site/dev/<code>/counties/` (one page, hash-routed, `#c=<county fips>`), built by
`build_local_dev.py`, which borrows the federal stylesheet; the front door's third card opens it (`local_facts` in
`build_door.py`).

- `states/load_counties.py`: county lines from the Census Bureau's national county file (cb_<year>_us_county_500k.zip,
  11 MB, cached in `states_cache/census/`), projected like the state districts, with the file's SHA-256.
- `states/load_local_results.py`: who holds each county office, from the Minnesota Secretary of State's official
  results, read from the "media results" text files (semicolon-separated: state, county id, precinct, office id,
  office name, district, candidate order, candidate name, suffix, incumbent, party, precincts reporting, precincts
  total, votes, percent, office total; check this layout against the real files). **The Secretary's results sites
  (electionresults.sos.mn.gov, electionresultsfiles.sos.mn.gov, and www.sos.mn.gov after a few requests) answer this
  machine with a Radware CAPTCHA, in the Browser pane too. Never solve or work around a CAPTCHA, and do not keep
  requesting those hosts.** John downloads each election's Media Files text files in his own browser into
  `states_cache/mn_local/sos/<yyyymmdd>/` (the November 2024 and November 2022 general elections cover every county
  seat now held), and the loader reads whatever is there. Every county office in Minnesota is nonpartisan on the
  ballot. The record shows winners and votes only; a resignation or appointment since is not in it, and the page says
  the county's own site is the authority for today.
- Commissioner district lines exist only county by county (Hennepin, Aitkin, Dakota and Ramsey publish feature
  services on gis.data.mn.gov, whose search is `/api/search/v1/collections/all/items?q=`); school district lines
  statewide from the Department of Education there. The state portal's county website list
  (mn.gov/portal/government/local/counties/) answered once with 87 links and then with a short page: fetch it once,
  keep it.

## On The Ballot (from version 4.0.046)

John's idea (2026-09-29): a switch at the top middle of the front door, "On The Ballot"; a click pulls the reader
through a wormhole into a second space built like the first (Congress, State, County and city cards), given over to
who is literally on the ballot in every district, primaries included, with the general election drawn as a card
"arena" and a primary as a "field". His answers: Congress first; official lists state by state, biggest states
first; after the three-second hover the fireworks wait for a click; polls only from pollsters in AAPOR's
Transparency Initiative (the latest from up to five, and our own average of the ten most recent, arithmetic shown).
Defaults he was shown and accepted: cards show record facts only, all the same size, in ballot order or by surname,
party colour as a band, never a score; positions only in the candidates' own words (their campaign's issues page)
plus their voting record; ads as FEC spending by kind, for and against, plus links to Google's and Meta's public ad
libraries (never copied); the money rule as everywhere; after Election Day, the official result.

- Everything goes through `run_ballot.py` (`races`, `fec`, `lists [codes]`, `match`, `check`, `site`). The database
  is `ballot_2026.sqlite` (never congress_119.sqlite); downloads in `ballot_cache/`; the report `ballot_report.md`.
- `ballot/races.py`: the 435 House seats (the district file plus six at-large states) and the Senate (class 2 plus a
  special wherever an appointee holds a seat of another class: Ohio and Florida). State notes on new lines cite
  NCSL's tracker (secondary, labelled, updated 2026-09-11): AL CA FL LA NC OH TN TX UT use new lines; Missouri is back
  on its 2022 lines pending a November referendum; Louisiana's congressional primaries are on November 3 and its
  general on December 12. A reader is never placed in a district from the 2024 lines in a state whose lines changed.
- `ballot/fec26.py`: every 2026 House and Senate candidate from the cached FEC bulk files, with load_donors' rules.
- `ballot/lists/<code>.py`, one loader per state, named in `LOADERS`. California: the Statement of Vote's "CSV Files
  - Voter Nominated" workbook for the June 2 top-two primary (county rows summed); the top two advance. Checking them
  against the Certified List of Candidates (a PDF) is still to do. Florida: the Candidate Tracking System download
  (POST `extractCanList.asp`, elecID 20261103-GEN, office FED, status All, cantype STA; tab-separated; statuses
  Qualified, Unopposed, Defeated, Withdrew, Did Not Qualify; an unopposed candidate is not printed on the ballot,
  section 101.151). Florida's primary vote counts are not loaded yet. Addresses, phones, e-mail and treasurers' names
  in any file are never read.
- `ballot/match.py` ties candidates to FEC numbers and Bioguide ids: same state, office and district, the family name
  (particles such as de, van, le set aside), a given name that fits (`given_fits`); a first-letter match only when
  the family name is unique in the race (Ami for Amerish, Ro for Rohit). Write-ins and small campaigns often have no
  FEC registration.
- `build_ballot_dev.py` writes `site/dev/ballot/us/index.html` (routes `#state=FL`, `#race=2026-FL-H07`), borrowing
  CSS, MONEYFMT and CHANGELOG by the landmarks in build_state_dev.py, and reading a sitting member's record from the
  draft's `us/data/member/` files, so build the federal draft first. `build_door.py --ballot` writes the ballot door;
  the main door shows the switch only when `site/dev/ballot/index.html` exists. `Preview dev site.bat` builds both.
- The switch: a real pointer movement onto it starts a three-second charge; canvas fireworks spell ON THE BALLOT /
  CLICK TO SEE over a blurred night sky and hold about three seconds; a click runs the wormhole (canvas tunnel, the
  page and the words pulled into the middle, two seconds) and `sessionStorage.wormhole` plays the arrival on the
  other side. Motion off: a plain fade. Phones: a tap goes straight through.
- Texas (v4.0.047): the Secretary of State's Ballot Certification Report PDF, county by county, read with
  `ballot/pdftext.py` (pure Python: object streams, the page tree, ToUnicode maps; a simple font's codes are always one
  byte even when its map claims two). Every county's list of a district must agree. Names are printed in capitals;
  the page shows ordinary capitals (a sitting member as the roster spells them) and says so.
- The Upper Midwest (John, 2026-09-30, v4.0.053: MN WI IA MI ND SD next). Michigan (`mi.py`): the Bureau of Elections'
  Official Candidate Listing from its filing system, mi-boe.entellitrak.com (`page.miboePublicReport&electionYear=2026
  &electionType=GEN` and `PRI`), which answers scripts although the rest of michigan.gov (and mvic) returns 403 and the
  old mielections.us host is gone; rows are status (DISQ, WITHD: off the ballot), party, "Last, First", date, method;
  primary fields from the PRI listing, the advancer read from the GEN listing, no votes. Wisconsin (`wi.py`):
  elections.wi.gov answers scripts with 403 and serves browsers, so "Candidates on Ballot By Election" (PDF, media
  40951) and the Partisan Primary "County by County Report" (xlsx, one sheet per office and party named in its Document
  map; the Office Totals row; SCATTERING is write-ins) are carried out of the Browser pane as base64 (an in-page fetch
  handed back through the tool's saved result; a public page may not post to a local port) into ballot_cache/wi/; the
  loader downloads nothing; the signed canvass statements are scans. Iowa (`ia.py`): the Secretary of State's candidate
  list PDF, linked as "candidate list" from sos.iowa.gov/general-election; headings are centred and entries are not,
  so the column edges come from where cells start in rows that name an office; only the first three columns are ever
  turned into text. North Dakota (`nd.py`): vip.sos.nd.gov/candidatelist.aspx?eid=348, the page's own Search posted for
  "Representative in Congress"; columns by name (Contest printed twice, the second is the office). South Dakota
  (`sd.py`): vip.sdsos.gov/candidatelist.aspx?eid=774, a Telerik grid sorted by office (federal first, checked); its CSV
  export needs more than a plain post; columns by an allowlist, Withdrawn left off, REP/DEM/IND/LIB written out. Never
  exclude columns by position in these grids: allowlist them, and print nothing else while testing. Minnesota (`mn.py`):
  candidates.sos.mn.gov shows the same Radware CAPTCHA as the results sites, so the loader waits for John's files in
  states_cache/mn_local/sos/20261103/ (and 20260811/ for primary votes), read with the county loader's `read_file`.
  `match.py` also matches a name kept on the ballot that the FEC files among the given names (ARENHOLZ, ASHLEY HINSON).
- Maps (John, 2026-09-30, v4.0.053: "the ability to look at the map(s) like [the Vote map]"). The state page draws its
  districts (House view) or the whole state (Senate view), each seat in the colour of the party holding it today and
  striped where that member is not on the seat's November list (`seatState`: running, open, unknown when the list is
  not loaded, vacant), labelled at the largest ring's centroid with 12px type scaled by transform, small ones hidden
  until zoomed; hover or tap previews the race beside the map; zoom buttons, double-click, drag to pan when zoomed (no
  pointer capture; window listeners dropped through an AbortController when the map goes). Race pages show a locator
  (the district on its state, others clickable). The home map's second view shows the Senate seats. District lines go in
  `site/dev/ballot/us/data/districts.json`, fetched when a map opens, and only for states whose lines did not change
  for 2026 (`district_file`); a changed state shows its outline and says why. Test maps with a set viewport
  (resize_window) because the hidden pane lays out at width 0; see them by drawing the SVG, computed styles inlined,
  to a canvas and carrying the PNG out as base64.
- Ads (v4.0.054, `ballot/ads.py`, `run_ballot.py ads`): the FEC's independent_expenditure_2026.csv (dates written
  15-MAY-26; the latest copy of each spender's transaction, then one count per spender, candidate, side, date and
  amount; ele_type P/G splits the primary from the general) and oppexp26.zip (the candidates' own P and A committees;
  memo lines out) into `ad_money` and `ad_spenders`, for every 2026 FEC candidate. Kind from the purpose line by the
  ordered patterns in `MEDIUM` (digital before TV, "MEDIA PLACEMENT" = medium not stated). Spenders named only when a
  committee; FEC type I (person or group) is "people and groups filing on their own". Payees never stored. The page
  links Meta's ad library search and Google's political ads page; ads are never copied. Dates typed in the future are
  ignored for "through".
- Polls (v4.0.054): `ballot/polls/aapor_ti_members.json` (AAPOR's list; its page shows twelve and loads the rest by
  script, and its WordPress API answers 401, so it was read in the Browser pane after Load More) and a hand-kept
  `ballot/polls/polls_2026.json`: each poll checked against the pollster's own release (Wikipedia's table only to find
  them and to count those left out, labelled secondary). Minnesota's Senate race: of ten published polls only Emerson
  (Feb 6-8, 2026) is by a member; Mason-Dixon, SurveyUSA, InsiderAdvantage and the rest are not members. Michigan (v4.0.055):
  Marist, Emerson x2, SSRS (CNN's PDF at s3.documentcloud.org/documents/<id>/<slug>.pdf; the viewer page has no text),
  MSU IPPSR; Iowa: Marist, Emerson x2. Polls by members that cannot yet be checked (a paywall, a secondhand report) go
  in `pending` and are named, not counted. South Dakota (v4.0.060): no TI member has polled it (PPP, Impact Research, Public
  Opinion Strategies, Mason-Dixon), so the race has `"polls": []` with `left_out`, and the page says none has published one
  yet. State helplines (`HELPLINES`) only from the state's own page: MN, IA, MI (read in the Browser pane; michigan.gov
  refuses scripts), WI (dhs.wisconsin.gov/disease/gambling-disorder.htm), ND (HHS news release of 2026-03-09: GamblerND),
  SD (the Lottery's Responsible Play page; the DSS page is an empty shell), OH (dbh.ohio.gov, which answers scripts 404 and
  browsers normally: read in the Browser pane), IN (FSSA DMHA), NE (the Commission on Problem Gambling), MT (the Department
  of Justice's Gambling Control page, naming the Montana Council on Problem Gambling's line), TN (TDMHSAS: Tennessee REDLINE).
  NC (NCDHHS), VA (DBHDS, 888-532-3500), WA (HCA), AZ (the Department of Gaming's line, named in an Attorney General
  release; the gaming and problem-gambling sites refuse scripts), MD (MDH: 1-800-GAMBLER answered in Maryland), LA
  (Gaming Control Board), OR (OHA), NM (Gaming Control Board, naming the Council's crisis line), MA (DPH), NJ (DMHAS:
  1-800-GAMBLER answered by the state council), SC (BHDD), CT (DMHAS), DE (Gaming Enforcement), ME (211 Maine, which the
  Maine CDC names for gambling help "anytime"), CA (CDPH), NY (OASAS HOPEline), PA (DDAP), IL (IDHS), FL (Gaming Control
  Commission). National line only, by each state's own page: WY, CO, KY, OK, AR, KS, WV, GA, AL, NV, VT, RI, NH, AK, HI, TX, and MS (its portal names only a Gamblers Anonymous line);
  Idaho's lottery page names the 2-1-1 CareLine, a general referral line open weekdays only, so Idaho stays national too.
  The notice promises "day and night" only for the national line, so a state line need not state its hours.
  Polls so far (v4.0.061): members' polls for OH (Marist, Emerson x2), MT (Rutgers-Eagleton for Montana Free Press), KS
  (Emerson), TN (Targoz for the Beacon Center) and ID (Change Research for Stegner's campaign, a half-sample question); none
  by members in SD NE WY CO KY OK AR WV (WY and WV: no poll by anyone). A poll's optional `"sample"` string replaces the
  table's "n population, ±moe" line when the release's margin covers a different group than the figure shown.
- Betting markets (v4.0.054, `ballot/odds.py`, `run_ballot.py odds`): `MARKETS` lists each race's Polymarket event slug
  and Kalshi event ticker, found and checked by hand (Kalshi's prices are `last_price_dollars`, volume `volume_fp` in
  contracts); a snapshot goes to ballot_cache/odds/odds_2026.json. The page folds them away, labelled, and "Go to" opens
  a notice dialog: bets not facts, 18 and over, legality disputed in some states, the National Problem Gambling
  Helpline 1-800-MY-RESET (NCPG's page; 1-800-GAMBLER is no longer the number there) and the state's line (`HELPLINES`;
  Minnesota 1-800-333-HOPE, from its Department of Human Services). "Stay here" is the main button. No referral links.
- Minnesota (v4.0.058-059): John saved the Secretary of State's files (he answered its CAPTCHA himself; never solve or
  work around it) into states_cache/mn_local/sos/20261103/, with a .md extension: "Candidates in the General Election -
  Federal, State, and County Offices" (number; name; office no.; office title; county, 88 statewide; ballot order;
  party; then addresses, phone, website [col 17], e-mail) and "Candidate Filings" (the same without the ballot order:
  party is col 6, website col 16), with the Secretary's own column note. `mn.py` reads name, office, order, party and the
  website only; the filings give the primary fields (winners from the November list; votes wait for the Aug 11 results
  files). IND = independent. Websites go to ballot_cache/lists_websites/mn.json, then `campaign.list_websites` puts them
  on the matched person; `campaign.issues` follows a home-page link labelled Issues/Priorities/Platform and keeps only
  the page's headings as topics (`topic()`: numbering off, all-caps to ordinary, sentences, furniture and appeals that
  name the candidate dropped; call net.patient_lookups first or the router's lost lookups fail whole sites).
- The rings outward (John, 2026-09-30: "keep moving outward from Minnesota ... largest first"; v4.0.061 on). Loaders are
  written by one agent per state, tested on a scratch copy of the database, then reviewed and run here. A state counts as
  listed on the page only when it has November candidates (`listed` in build_ballot_dev.py), so a state with primaries
  alone (Indiana) says its list is coming. Primary votes are stored only when official (canvassed or certified); the page
  labels them "as certified", so election-night figures are never stored (South Dakota's results site stays
  "Unofficial" for good; Missouri's is behind Cloudflare). Election codes: primary-REP/DEM/LIB/LMN, runoff-<party>.
  Iowa primary: the SOS "Election Results & Statistics" table's Primary row links the "Official Canvass by County" PDF
  (one section per office and party, county Election Day/Absentee/Total rows, statewide TOTAL; long county names touch the
  row label; shares are of candidates plus write-ins, the 35 percent rule's base). North Dakota primary: vip.sos.nd.gov
  eid=346; results moved to a Tally site whose keyless JSON is api.resultsnd.sos.nd.gov (cId north-dakota, electionID
  346; `isWinner` unset even when official, write-ins a choice named "write-in"). South Dakota primary: eid=773 (status
  sits inside the name: strip "(Withdrawn ...)"); the certified canvass is a scanned PDF on sdsos.gov's election history
  page, not yet posted for 2026. Indiana (`in.py`, a Python keyword: import with importlib): the Election Division's
  candidate workbooks on in.gov/sos/elections/candidate-information (OFFICE, CANDIDATE NAME, POLITICAL PARTY, DISTRICT,
  no contact columns); the 2026 general list's link (`Candidate_List_Abbreviated_2026..9.11.xlsx`) answers a 200 "Page
  Not Found" for scripts and browsers alike, so check the first bytes (PK); a hand-saved copy at
  ballot_cache/in/in_candidate_list_2026_general.xlsx is read if the link stays broken; certified primary results are
  plain JSON at enr.indianavoters.in.gov/site/data/ (settings.json, statewideElectionsC_<v>, OffCatC_<id>_<v>).
  Missouri (`mo.py`): "Certification of Candidates and Party Emblems" PDF (party by party, "District 5, Rick Brattin", no
  order numbers); primary lists at s1.sos.mo.gov/CandidatesOnWeb (ElectionCode 750006905, one captioned table per party;
  the removed page runs name, "(Party)" and address together: keep what precedes the bracket); official Grand Totals
  appear on sos.mo.gov/elections/results weeks after the canvass. Nebraska (`ne.py`): the final candidate list is a
  sideways PDF (bands from the heading strip; only allowlisted bands become text); the canvass book is the official
  primary result (check mark = nominee; county columns must add to the Total); "By Petition" is coloured independent; a
  primary winner removed from the ballot (Burbank) keeps "advanced" with a note. Montana (`mt.py`): candidatefiling.mt.gov
  Telerik grids (`CandidateList.aspx?e=450002987` general, `450002928` primary; the pager is a plain postback; party key
  DEM REP LIB IND MP NON; write-ins marked only in the contact column, so party NON on a partisan race is read as a
  declared write-in); the precinct workbook's sums match the State Canvass. Wyoming (`wy.py`): the roster PDF (column
  edges from its headings; each entry two lines) and the primary zip's "Results Summaries - OFFICIAL.xlsx" (a candidate
  who withdrew after printing is "* Withdrawn Candidate", named in a footnote; kept with a note). Ohio (`oh.py`): the
  Secretary of State publishes no general-election list for Congress (the board of each district's most populous county
  certifies it), so county boards' own lists are read (Franklin, Cuyahoga, Lake, Lorain, Stark, Wood, Butler, Union,
  Hamilton), each race from the first list carrying it and checked against the rest; ohiosos.gov, publicfiles.ohiosos.gov,
  boe.ohio.gov and votehamiltoncountyohio.gov answer scripts with a Cloudflare challenge, and the Browser pane passes it
  like any browser, so Hamilton's 46-day notice (R.C. 3511.16; no addresses, a good fallback every board posts) and the
  canvass workbooks ("Summary Level Official Results for 2026 Primary Election - <Party>", listed in
  publicfiles.ohiosos.gov/election-results/files-index.json; spaces as %20, "+" literal) were carried out of the pane
  and are read from ballot_cache/oh/. Names rotate by precinct (R.C. 3505.03): no ballot order. Districts 2 and 12 wait
  (boe.ohio.gov answered 522 in the pane). A race a state's loader cannot load goes in `list_gaps` (race, state, reason),
  and the page says the race's list is not loaded, with the reason, rather than "no candidate". `match.py` also ties a
  former member (service ended 2011 or later, same state and party, one fit) to their Bioguide id. Saves while agents
  are still writing loaders use `python version.py save --hold <path>` so unfinished files stay out.
  Ring three (v4.0.062): Colorado (`co.py`): coloradosos.gov's HTML list (withdrawals only as strike-through; the XLSX
  lags), the lot-drawing XLSX for ballot order, Clarity detailxml votes stored only where they equal the certified
  abstract (a scan; its federal totals typed into `ABSTRACT` with the scan's SHA-256). Kentucky (`ky.py`):
  web.sos.ky.gov/CandidateFilings (id=3 Senate, 4 House; withdrawn rows after pnlOfficeWddResults; party "Write-In" =
  declared write-in) and the Board's primary certification PDF (contested primaries only; wide fields printed sideways, so
  ky.py keeps its own page_runs copy that keeps text direction). Utah (`ut.py`): the Lieutenant Governor's signed,
  sideways certification scans with a text layer (names matched letters-only to the typed Candidate Filings page), the
  Master Ballot Position List, electionresults.utah.gov JSON (/results/public/api/elections/Utah/<id>, files under
  /cdn/results/). Arkansas (`ar.py`): candidates.arkansas.gov (`/wp-json/metl/v1/all?postID=2941`, five columns; ballot
  names can carry a filed title, "Senator Tom Cotton", kept as printed with a note) and the Tally results API
  (enr-results-api.totalresults.com, cId arkansas; isWinner unset, winners by majority). Idaho (`id.py`, a builtin name):
  the Candidate Filing Portal's JSON (api-run.voteidaho.gov; rows carry mailingAddress and voterId: allowlist keys) and
  the canvass report PDF ("**" = protected count). West Virginia (`wv.py`): candidates.wvsos.gov's JSON POST service
  (officeDescription as an array; the host omits its intermediate certificate, so the POST uses net's issuer repair) and
  Clarity (county status 4 = completely reported). Oklahoma (`ok.py`): hosting.okelections.us/electionlist.html (the
  November ballot county by county, drawing order; the address is reused, so the title is checked), the fixed-width
  Candidate List Book PDF (columns by character position); results.okelections.us refuses scripts and redirected to
  results.okelections.gov, which did not resolve, so no votes or runoffs yet. Kansas (`ks.py`): Official Vote Totals PDF
  and precinct workbooks answer scripts; the Candidate List page (.aspx) shows a "Human Verification" page even in the
  Browser pane: never solve it; John can save the page ("2026 General" chosen) into ballot_cache/ks/. Tennessee
  (`tn.py`): sos.tn.gov and its file host answer CloudFront 403 and the Browser pane is not allowed that site; tn.py
  reads the four files John saves into ballot_cache/tn/ (the Senate and House lists from sos.tn.gov/elections/2026-
  candidate-lists, and 20260806RepublicanPrimarybyCounty.pdf / 20260806DemocraticPrimarybyCounty.pdf).
  Ring four, first half (v4.0.063): North Carolina (`nc.py`): dl.ncsbe.gov Candidate_Listing_2026.csv (one row per
  county a contest reaches; columns by name) and the Board's official results files; no status column, so withdrawals
  cannot be counted. Virginia (`va.py`): the Department's "November 3, 2026 - Federal Offices" page and the official
  results of the August 4 primary (2024 lines kept; the April 21, 2026 amendment's result was not marked official).
  Washington (`wa.py`): voter.votewa.gov CandidateList.aspx?e=899 (the Montana grid format) and the certified top-two
  results; the page's top-two sentence now names the race's state. Maryland (`md.py`): the SBE's CSV candidate lists
  and official results. Georgia (`ga.py`): results.sos.ga.gov is an Enhanced Voting site (API: /results/public/api/
  jurisdictions/Georgia, elections/Georgia/<id> with isOfficialResults; "Total Votes Excel" under /cdn/results/); the
  November list is MVP's Qualifying Candidate Information search, behind reCAPTCHA: John saves its "Qualified
  Candidates.csv" into ballot_cache/ga/20261103/ (read by header; it carries e-mail and website columns, never read).
  Arizona (`az.py`): azsos.gov serves the Browser pane, but its Candidate Listing is an app on apps.arizona.vote (not
  on the pane's allowed list) and apps.azsos.gov's canvass PDFs answer scripts 403; az.py's readers were written
  blind and must be checked against the real files. `name_parts` reads a comma followed only by a suffix
  ("Beyer, Jr.") as a suffix.
  Ring five (v4.0.064): New Jersey (`nj.py`: nj.gov PDFs; the Address column sits between Name and Party, so read only
  pieces starting at a column's edge; removals show only by comparing the July certification with the September
  amendment), South Carolina (`sc.py`: vrems.scvotes.sc.gov Candidate Tracking System, no contact columns; enr-scvotes.org
  Clarity, "Official Results"; the special primary after Lindsey Graham's death is `special-primary-REP` /
  `special-runoff-REP`), Connecticut (`ct.py`: the SOTS system's official sample ballots of 19 towns; source kind
  "official sample ballot"), Maine (`me.py`: final RCV tabulations; first-choice votes stored, the RCV winner advanced),
  Delaware, Vermont (canvass by town, 741 columns), Alaska (`ak.py`: top-four primary, stored as election "primary";
  TOPN in the page makes it read "top-four"), Hawaii (`hi.py`: `primary-NP` for the nonpartisan section). Massachusetts
  (`ma.py`): primaries from electionstats.state.ma.us (certified, CSV); the November list page on www.sec.state.ma.us is
  behind Incapsula: John saves it into ballot_cache/ma/. Rhode Island (`ri.py`): primaries loaded; vote.sos.ri.gov is
  behind Cloudflare and not on the pane's allowed list: John saves the Senator and Representative in Congress pages into
  ballot_cache/ri/general/. New Hampshire (`nh.py`): sos.nh.gov answers Akamai 403: John saves the files the loader
  names into ballot_cache/nh/ (NH's results are the clerks' returns, subject to amendment). `match.py` now never gives
  one registration or member record to two candidates in a race, and uses middle initials to choose between two
  registrations (Alaska's Dan S. Sullivan and Daniel J. Sullivan Jr.). Polls: the UNH Survey Center's releases on
  scholars.unh.edu answer scripts with Cloudflare but open in the Browser pane; the PDFs were carried out into
  ballot_cache/polls/unh/ and read there.
  Ring four, second half (v4.0.065): Alabama (`al.py`: the 67 counties' official sample ballots, read in drawing order and
  only under the "NOVEMBER 3, 2026" heading; the certifications are text-less scans; primary and runoff votes from the
  Secretary's precinct .xls zips, since the parties' certified workbooks leave out counties; the August 11 special
  primaries replaced the May contests in districts 1 and 6). Louisiana (`la.py`): the Secretary of State's notice of May
  14, 2026 (not NCSL) is the authority: the House's Nov 3 contest is an open primary, stored as election `open-primary`
  dated 2026-11-03 (the page shows it as the November ballot, `openPrimary()`), with a Dec 12 runoff; the Senate held
  closed primaries (May 16, June 27) and has a Nov 3 general; voterportal.sos.la.gov Candidate Inquiry and the graphical
  results JSON (ResultsOfficial). races.py's `OWN_SOURCE` lets a state's own notice replace NCSL as a note's source.
  Oregon (`or.py`: ORESTAR's candidate filing search, posted with its anti-forgery token; the official abstract PDF),
  Mississippi (`ms.py`: sample ballots' order; official recapitulations), New Mexico (`nm.py`: candidateportal.servis
  eid=2917). Nevada (`nv.py`): www.nvsos.gov and silverstateelection.nv.gov answer scripts with Incapsula: John saves
  the certified list as ballot_cache/nv/nv_2026_general_candidates.html. `fec26.py` strips phone-like digit runs that
  filers typed into the name field.
  Primaries for the first states (v4.0.066): Texas (`tx.py`): the SOS's Civix results system (goelect.txelections.
  civixapps.com/api-ivis-system/api/s3/enr/electionConstants lists elections with an official flag; each election's
  "Official Canvass Report" PDF comes base64 inside JSON; ids 53813/53814 primaries, 58315/58314 runoffs); a no-majority
  field can end without a runoff (TX-23, TX-32 Republican). Illinois (`il.py`): the State Board's official canvass.
  Pennsylvania (`pa.py`): electionreturns.pa.gov JSON (GetOfficeData, electionid 117; the election list marks it
  Official) and the county CSV as a check. Florida (`fl.py`): the Division's official results files. New York (`ny.py`):
  the Board's results workbook (2026-june-primary-vote-results-08312026.xlsx, linked from its "Certified June 23rd
  Primary" page), carried out of the Browser pane; 2026's sheet titles read "Primary Election - June 23, 2026"; district
  15's Democratic sheet disagrees with itself (candidate vs party totals), which the source note records. Privacy: three agents
  printed a few contact cells while exploring layouts (never stored); agents are now told to print only headers, counts
  and allowlisted cells.
- Share pages (v4.0.056, `ballot/share_race.py`, run by `build_ballot_dev.py`): `r/<race>.html` and `og/r/<race>.png`
  for every race with a list, drawn with share_cards.py (the type has no star glyph: "serves in this seat today" is
  written under an incumbent's name; more than four candidates show three and "and N more"); redrawn only when the
  inputs' hash changes (bump `"v"` to force). The race page's "Share this race" uses navigator.share or copies the link.
- John's second round (2026-09-29): photos, age and years in office on every card. `ballot/people.py` takes birth
  dates, offices and portraits from official records only (the congress-legislators roster for Congress, the Open
  States roster in `state_<code>.sqlite` for state legislators and statewide officials, matched by name, same state,
  same party, and only when unique; every match is printed for reading). A term whose scheduled end is in the future is
  current; a run with no start date starts "at least" at the earliest date the record gives.
- Campaign photos (`ballot/campaign.py`): each campaign's website from its FEC Form 1 through OpenFEC, which needs
  John's free api.data.gov key (`Save FEC key.bat` writes `fec_key.txt`; never ask for it in chat, never print or read
  it; the demo key allows 10 requests an hour). docquery.fec.gov refuses scripts (403) and the FEC's committee pages
  load by JavaScript, so neither is used. Up to three photo options per candidate from their own site; each is looked at
  on a contact sheet and `ballot/photo_choice.json` records the option showing the candidate alone, or "none" with a
  note. Only chosen photos reach the page, credited and linked. Nobody's likeness is recognised or matched.
- The ballot door's switch reads "Legislation & Legislatures" ("Back to the public record" beneath) and has the same
  three-second fireworks for the way back, drawn as the American flag (canton of stars, thirteen stripes, a ripple).
  ON THE BALLOT is red, white and blue by word; CLICK TO SEE is silver; both end with a flash and a ring of sparks.
- The crossings (John, 2026-09-29, v4.0.051): into the ballot, a ballot fed into a scanner that confirms it was counted;
  back to the record, books falling off a shelf and a door behind it opening. Each door names its crossing in
  `DOOR.transit`; the wormhole (`tunnel`) and black hole (`blackhole`) stay in build_door.py as future ideas. The ballot
  is generic: no names, no parties.
- From v4.0.052 the crossings are 3D and first person (John: "3D anchored as if it were in reality right in front of
  the person ... immersive"): `door_transit3d.js` (an ES module, copied by build_door.py to `site/dev/transit3d.js`)
  draws them with three.js r169 (`vendor/three.module.min.js`, MIT, copied to `site/dev/vendor/`; nothing loads from
  a CDN). The door imports it on the switch's first hover, focus or tap (`load3d`, `DOOR.root` is "./" or "../") and
  calls `run(kind, url, {pt})`; if WebGL is missing or the file is slow (2.5 s) the flat SVG scenes play
  (`scannerScene`, `shelfScene`), and with Motion off the page fades. The camera is the reader's eyes and the hand is
  never drawn: the ballot rises from where a hand holds it, sways, leans toward the pointer and goes into the front slot
  as on the real machines; the book pulled is the one nearest the pointer; the pointer moves the head a little. Books
  tip about their front bottom edge, fall, and topple flat onto a cover (a coarse height grid lets them heap); all
  leave the shelves before the bookcase pushes back and swings into the passage. `still(kind, seconds, w, h)` draws one
  frame to a JPEG data URL for checking a scene; the browser pane draws no animation frames while hidden, so check with
  it, and a timer ends the crossing even there.
- Betting-market odds (John's answers, 2026-09-29): Polymarket and Kalshi, as information only, labelled "what
  bettors are paying: not a poll, a forecast or an official record", with trading volume and the time. A click opens a
  calm notice box: gambling disclaimer, age limits, a state-law warning (availability is disputed in some states),
  the national problem-gambling helpline and the reader's own state's (from the state they picked or their location,
  worked out on the device), and "Go to the market" or "Stay here". No slot machine, no referral codes. Not built yet.
- Where it stands (v4.0.067, 2026-09-30): 41 states' November lists loaded (400 of 470 races), primaries with official
  votes nearly everywhere, polls entries for all 35 Senate races (16 with checked member polls), markets for 100 races,
  helplines from 30 states' own pages. Waiting on John's own browser saves (bot walls or a broken link; never work
  around them): TN (four files), KS (Candidate List page), GA (Qualified Candidates.csv), AZ (candidate listing and
  canvass), MA (2026 State Election Candidates page), RI (Senator and Representative in Congress pages), NH (the files
  nh.py names), NV (the certified list), IN (the Election Division's list, once its link works), OK primary votes
  (results.okelections.us exports), and Minnesota's Aug 11 results files. Also still to come: South Dakota's certified
  canvass and Missouri's Grand Totals when posted; campaign websites and photos once the FEC key is saved; then state
  and local ballots (ask John about scope first).

## State and local races on the ballot (from v4.0.071)

John's go-ahead (2026-09-30): state legislature and local races on the November ballot, Minnesota first, built with
subagents, with the rule against personal or sensitive data pushed into every agent's instructions.

- Data: `ballot_local_2026.sqlite` (tables sl_races, sl_candidates, sl_sources, sl_places), apart from
  `ballot_2026.sqlite`, so the federal FEC matching and people stages never see a local name. One loader per state,
  `ballot/state_local_<code>.py`, each rewriting only its own state's rows. Minnesota's (`state_local_mn.py`) reads the
  Secretary of State files John saved in states_cache/mn_local/sos/20261103/ (general candidates: federal/state/county
  file, 21 columns; local file, 18; filings files for the partisan primaries) and covers every office: statewide, the
  Legislature, courts, county, soil and water, cities, townships, school and hospital districts (4,721 races, 7,981
  candidacies). Its "ballot order" column is each party's order code (90 for nonpartisan), so nonpartisan cards say the
  order is not given and sort by surname. Place names come from the Census county subdivision codes
  (st27_mn_cousub2020.txt) and the Education Department's district list. WI IA MI ND SD (and the next ring) carry
  statewide offices, the legislature and courts from the same official lists their federal loaders read.
- Pages: `build_ballot_state_dev.py` writes site/dev/ballot/<code>/ (index.html plus data/<code>.json and
  data/districts.json) and site/dev/ballot/states/; the ballot door's State and County-and-city cards open them.
  run_ballot.py stages `local` (the state loaders) and `adlib` (the ad library).
- The privacy rule for state and local candidates (stricter than federal): only name as filed, office, district or
  jurisdiction, party or "Nonpartisan office", ballot order, write-in and special marks; a sitting legislator (matched
  by chamber, district and name, one fit only) links to their existing state record page and nothing more. No photos,
  ages, websites, biographies, money or Wikipedia; the files' address, phone, e-mail and website columns are never
  read, printed or cached, even while exploring. Put this rule in every agent's prompt.
- Ads (John, 2026-09-30, "record only"): Google's Political Ads Transparency bundle (keyless, ~307 MB) is read by
  `ballot/adlibrary.py` into ad_library and ad_links; each ad links to its page in Google's Ads Transparency Center
  (where a video plays) and is never copied. Outside groups' ads are labelled from the group's own sworn FEC
  independent-expenditure filings (spent for or against named candidates, with amounts); a campaign's own ad says
  "Paid for by their campaign". Never write "attack" or "positive"; never guess which candidate an outside ad is about.
  Meta's per-ad data needs Meta's Ad Library API token (John's step; not asked yet).
- Loaded (v4.0.072): MN (state, county and local), and statewide/legislature/courts for WI IA MI ND SD OH IN MO NE MT WY
  CO KY UT OK AR ID WV; TN, KS and IN have races and holders but their November lists wait on John's browser saves (the
  same files as the federal side). Ohio has 60 legislative seats with no reachable list. When a state has no candidate
  list yet, the page names the state's results office, never the Open States roster or the Census Bureau.
  v4.0.073 adds GA (primaries; list behind reCAPTCHA) NC MD WA AL OR MS NM, VA (one special), LA (odd-year legislature),
  AZ and NV (waiting): 33 states. sl_places has no state column and is shared: county ids are 5-digit FIPS and
  district ids carry the state ("MT-1"), or one state's rows collide with another's (Oregon's did).
  v4.0.074: all 49 states with state races in 2026 (NJ has none: odd-year Legislature). Waiting: MA RI NH lists (bot
  walls), CT (only 19 towns' sample ballots posted), GA AZ NV TN KS IN (as on the federal side). The ring scripts live
  in the session's workflows/scripts folder (state-legislatures-ring*.js).

## County and local races, every state (from v4.0.075)

John's order (2026-09-30): the local level of On The Ballot for every state (county, city, township, school board,
special districts on the November 3, 2026 ballot), as far as official sources allow; an orchestrated run with one
Opus 5.5 max-effort agent per state, in waves of 8 to 10, rings outward from Minnesota, a saved version after each
wave; a scouting pass first; a running list of what waits on him (`ballot_local_status.md`, his file to open); never
his purchased usage: stop at 99 percent of the weekly limit.

- The scouting pass (49 agents, research only) is kept whole in `ballot/local_scout.json`: for each state, which local
  offices are on the November ballot and which are elected at another time, whether the state's own election office
  publishes one list, its format and columns, whether a script can fetch it, the county-by-county route, what needs
  John's browser, and a build plan. Read a state's entry before writing or changing its local loader.
  Four groups: a statewide list a script can read (ND SD KY OK ID WV NC VA WA MD AL LA NM SC DE VT HI; ME and TX for
  county offices); a statewide list behind a wall or a broken link (IN GA RI NH MA; NV's state list is walled but Clark
  and Washoe are readable); the state lists only judges or district boards and the rest is county by county (MI MO NE
  WY CO UT AR OR IL FL CT); county by county only (WI IA OH MT TN KS AZ MS NJ CA NY AK; Pennsylvania elects no regular
  local office in even years). Many states elect cities and schools at another time (Wisconsin in April, Iowa and
  Pennsylvania in odd years, Tennessee's counties in August): the page says so from `sl_notes`, never an empty list.
- Each state's agent extends `ballot/state_local_<code>.py` (the state-level rows stay exactly as they were) and must
  pass `python -m ballot.check_local --code <code> --db <a scratch copy>`, whose docstring states the conventions:
  levels county, soil_water, city, township, school, hospital, other (local judges, prosecutors and court clerks stay
  under court, with county_ids); `jurisdiction_id` a 5-digit county FIPS, or `<ST>-M-<key>` (city, town, village,
  township), `<ST>-S-<key>` (school), `<ST>-H-<key>` (hospital), `<ST>-X-<key>` (any other district); `county_ids` a
  JSON list of 5-digit FIPS; `sl_places` kinds county, mcd, school, hospital, special, source ids beginning `<code>-`;
  `sl_gaps` (state, scope state/county/place/race, place_id, place, what, reason, url) for everything that could not
  be loaded, with a reason a reader can follow; `sl_notes` (keys `local_calendar`, `local_coverage`). Minnesota keeps
  its older ids (3-digit counties, bare MCD codes). The check compares against a before-copy of the real database, so
  load like this: copy `ballot_local_2026.sqlite` aside, `python run_ballot.py local <codes>`, then the check for each
  code with `--real <the copy>`.
- Rules the first wave taught: no web address or site name in any note (addresses live in url columns; the check and
  the page's guard drop such text, and a number followed soon after by a street word such as Place, Court or Way reads
  as an address); a free-text cell can hold contact details typed into the wrong column (Kentucky: an e-mail in a Last
  Name cell), so a kept cell that `check_local.contact_like()` flags is blanked before it is cached; a town that is a
  municipality is level city (North Carolina, Virginia, West Virginia); a district reaching several counties is one
  place with every county in county_ids; a contest on two counties' lists is one race; where a list has no totals of
  its own, read it by two routes and compare. No ballot questions, levies or contests that are not between people
  (North Dakota's official newspapers). Local primaries are not loaded.
- State lessons. North Dakota: the list's Search with Jurisdiction "All" (the "County" choice leaves out commissioner
  districts and soil districts); a row with no name is a contest with no candidate; a soil conservation contest is
  filed under the candidate's county, so compare with the 2024 list (eid=333). South Dakota: the grid prints one title
  for contests that differ only in a hidden office number and never says how many are elected; statute and rule text
  at sdlegislature.gov/api/Statutes/<cite>.html. Kentucky: "Candidate Filings with the County Clerk", through the
  page's own Excel button and a small .xls reader in the loader; a city or school district is named only in free text
  and tied to Census names; a soil and water contest is printed only when more file than seats; Casey, Metcalfe and
  Carlisle leave the May primary's field on the list (35 contests kept without names); county sample ballots are at
  web.sos.ky.gov/ballots/<County> 2026G.pdf. Oklahoma: the November list prints only contested races (26 O.S. 6-102),
  county offices inside each county's section. Idaho: the portal's County and Local district types; county offices are
  partisan; magistrate retention is one county's yes-or-no vote. West Virginia: county rows come only from the CSV
  export; its Magisterial column is a district of residence on commission rows and a town or ward on town rows, and
  towns load only when every row names one. North Carolina: one CSV row per candidate per county, with is_partisan,
  is_unexpired and vote_for; the Board still calls its November lists not final. Virginia: the Local Offices workbook;
  towns named in the title, the District cell or not at all; no party is printed for local offices. Washington: the
  grid read once per county (&c=01 to 39) with the whole list as the control; a district can sit on a neighbouring
  county's list.
- Wave two (2026-10-01: MD AL LA NM SC DE VT HI ME TX). Maryland: the State Board's local candidates CSV names the
  county only on countywide rows, so the county comes from the same list's page headings, and each county's certified
  ballot PDF gives "Vote for" and the printed order; cities and towns run their own elections (Takoma Park and Ocean
  City vote on November 3 from their own lists: place gaps). Alabama: the Secretary's 67 county sample ballots are the
  statewide list (every county and county school office, all partisan; cities vote at their own municipal elections);
  count the "(Vote for" lines and the party lines as two controls; names carry small-letter hints (DeRAMUS) that plain
  capitalizing destroys. Louisiana: Candidate Inquiry gives a CSV per parish and the results site already posts
  November's race files, so the list is read three ways; a sole qualifier is "Unopposed" and elected off the ballot
  (two thirds of local contests); every local office prints a party; counties are parishes (the page must not add
  "County"); court districts are place kind `judicial`. New Mexico: the portal answers county by county
  (`&cty=<code>`); Filing County is the office's county only for county offices, probate judges, magistrates and the
  municipal judge; the checklist of offices is the Secretary's General Election Proclamation (a scan, typed into the
  loader with its SHA-256). South Carolina: city, town, school and special elections on November 3 are elections of
  their own in the Candidate Tracking System (State Senate 15's special among them): read every election of that date
  two ways (office All, then each office type); circuit solicitors are level other in special places. Delaware: the
  Department's workbooks carry all 20 county contests; compare kept rows, not SHA-256s (the workbook's bytes change).
  Vermont: static.electionresults.vermont.gov lists November's contests weeks ahead (seats, each town's county, towns
  with no candidate); justices of the peace are one race per town ("Voters choose N"), level township for towns and
  city for cities; no ballot order stored. Hawaii: county contests only; eight council seats were settled in the
  August primary; the Candidate Report can disagree with the certified count (Honolulu council District IV: loaded as
  marked, with a note and a race gap; worth asking the Office). Maine: county offices from the Secretary's general,
  special, withdrawal and write-in lists; district attorneys are level other in prosecutorial-district places; a
  candidate who withdraws after August 25 stays printed; cities and towns are each clerk's own posting. Texas: the
  Ballot Certification Report prints every county's county and precinct offices (2,646 contests, 254 counties), and the
  Secretary's portal answers one keyless POST (findQualifiedCandidates, election 53815; allowlist keys; cdFilingStatus
  CG = on the ballot, party W = declared write-in); statutes for scripts at tcss.legis.texas.gov/resources/.
- Wave three (v4.0.076: MI OH MO NE WY WI IA MT FL), the first county-by-county states: the statewide part, then the
  largest counties a script can read, each county's own office as the agency, a table in the loader naming each
  county's source address (hand-checked, never guessed), and a county-scope `sl_gaps` row for every county not read.
  Adding a county is one entry in that table (`AUTHORITIES` in Missouri's loader, `LOCAL_SOURCES` in Montana's) plus,
  where the layout is new, a small reader; a hand-saved file under `ballot_cache/<code>/local/<county>/` is read when
  present. Michigan: judges from the Bureau's statewide listing; nine county clerks' lists in six layouts (Wayne,
  Oakland, Macomb's published sheet, Kent, Ottawa, Ingham, Kalamazoo, Saginaw, Muskegon); status marks hide inside name
  cells ("(Withdrew)", "DISQUALIFIED 7/15/26 Name", Muskegon's unexplained "(W)"); school districts keyed by CEPI's
  Educational Entity Master. Ohio: every board must post a 46-day election notice (R.C. 3511.16: names, offices,
  parties, no addresses), so read that, never the board's candidate list; 23 boards read from their own sites, 61 sit
  on the state's shared site that refuses scripts; a court of appeals race is printed by every county of its district;
  the notices also carry 18 legislative districts the state rows lack (not loaded: a state-level run to do). Missouri:
  each election authority's notice or sample ballot PDF (13 read); St. Louis City is filed as a county (29510); a
  county's ballot can disagree with the Secretary's certification (Circuit 23 Division 2: a race gap, no name shown).
  Nebraska: the Secretary's workbook carries only district boards and judges and names no county (seats are placed
  from its by-county sheet); an office pattern without word boundaries ("governor") once swallowed every community
  college Board of Governors contest. Wyoming: each clerk's November sample ballots by precinct, merged per county,
  checked against the Secretary's CSV; three counties post scans. Wisconsin: sample ballots (a contest is found by its
  "Vote for 1" line); only sheriff, clerk of circuit court and coroner are on this ballot. Iowa: each auditor's sample
  ballots (columns from the "Vote for no more than N" lines), parties checked against the June primary. Montana:
  partisan or not is taken from what each county prints; in a centred table a contact cell can start left of its own
  heading, so take cells by the nearest heading's middle, never by a left-edge cut-off (one mailing-address cell was
  printed to an agent's output that way; nothing stored). Florida: the Division's local candidate download names no
  county (its only county code is in the address block, never read), so each row is placed by finding the same name,
  office and seat on the county supervisor's candidate page; "Unopposed" there also covers a candidate who won
  outright on August 18; accented letters are Windows-1252; 89 candidates could not be placed and are a state gap.
- `ballot/pdftext.py` has limits three loaders worked around in their own files and that deserve one shared fix (with
  the federal loaders re-tested): it reads nothing drawn inside Form XObjects (Muskegon, Jasper County, Ohio boards),
  does not put font and spacing back on `Q` (Converse County's watermarked ballots, Kansas City's party labels), and
  misses pages when a PDF's catalog is longer than 600 bytes.
- `build_ballot_state_dev.build()` is not read-only: it writes `states_cache/local_counties/local_<code>_counties.json`
  the first time a state has local rows. An office kind the builder does not know is listed after the known ones of
  its level under its own title and named in a build note ("is not placed in KINDS yet"); 45 such kinds wait to be
  placed (Florida's community development boards, Wyoming's district boards and others).
- Wave four (v4.0.077: CO UT IL OR AR CT NV), narrow on purpose: Colorado's RTD directors and 117 retention votes
  (judicial districts' counties from C.R.S. 13-5-102 on; the Secretary's page changes a tag attribute on every request,
  so compare rows, not page hashes); Utah's 30 justice court retention questions; Illinois's regional superintendents
  and circuit judges from the State Board's list, plus the Cook County Clerk's contest list (JSON) and the Chicago
  Board's PDF; Oregon's district attorneys and circuit judges from ORESTAR; Arkansas's four court runoffs plus Pulaski's
  ballot draw PDF and Washington County's page; Connecticut's judges of probate (one race per probate district) and
  registrars of voters from the town ballots posted so far (19 of 169; the rest are due by October 9: re-run
  `python run_ballot.py local ct` after that date); Nevada's Clark (PDF) and Washoe (workbook) county lists.
- Where it stands (v4.0.077, 2026-10-01): 34 states have county or local rows, 22,148 contests and 36,970 candidates;
  `ballot/local_status/` holds the status generator (`make_status.py`, `status_state.json`, every build agent's answer
  in `build_all.json`), which writes `ballot_local_status.md`. Still to do, in order: (1) more counties in the partly
  loaded states (MI OH MO NE IA MT WI WY IL AR NV CO UT OR), largest first; (2) the states not started: CA NY NJ KS TN
  AZ MS AK, and Pennsylvania's handful of special elections; (3) the states waiting on John's browser saves (IN GA RI
  NH MA); (4) cities and school districts in TX, ME, FL, MD; (5) a pages round: place the 45 office kinds the builder
  does not know yet, show notes and gaps for a state whose only local rows are court rows (UT, OR), "counties and
  cities" wording on county pages of states with independent cities, and the "is on the ... lists" sentence for
  county-by-county states; (6) Ohio's 18 legislative districts from the 46-day notices and Texas's newer state rows;
  (7) John's Agents of Audit over the whole site (fix what is plainly missing or stale; list every suggestion for his
  approval).
- Never pipe a build or a load through `Select-Object -First N` in PowerShell: it ends the pipeline and kills the
  Python process partway (it left Maine and Texas unloaded once, and stopped a site build before the doors). Send the
  output to a file, or use `-Last`.
- Patch a loader with the Edit tool, never a scripted text rewrite (half the loaders are CRLF, half LF). In a race
  note put dates in brackets or words: the page's guard reads a number followed by Court, Place or Way as an address.
- To look into (found by wave two, not acted on): Texas's live list has since added a Democrat in 2026-TX-DC486-UNEXP,
  nine state-level write-ins and separate November 3 specials for House 93 and a Senate seat, which the state rows do
  not have yet; `ballot_cache/me/` and other earlier caches keep official workbooks and PDFs whole, residence columns
  included (never read, but kept on disk).

## The cabin (from v4.0.078), and pages that do not show their workings

John's idea (2026-10-01): the landing page for the whole site is a room. A visitor stands in a cozy log cabin, in the
first person, and walks around; two posters on the wall glow and are the doors to the site's two spaces (he chose two:
ballots, and legislation and legislatures, with wording that invites: "Meet everyone asking for your vote." and "See
what they did with the last one."); modest furniture; outside the window the Rocky Mountains, at the visitor's own
time of day and season (worked out on the device; nothing is sent). The ring of cards stays as the plain way in.

- `cabin_room3d.js` draws the room with the kit's three.js (`start(canvas, opts)`; `still(w, h, view)` returns one
  frame as a JPEG data URL for checking where frames are not drawn; `setWhen(when, season)`), and `build_cabin.py`
  writes the page (`?time=morning|afternoon|dusk|night` and `?season=` in the address show another hour or season).
  `build_door.py` builds the cabin whenever it builds the front door. `CABIN_FIRST` in `build_door.py` is off: the ring
  of cards is `index.html` and the cabin is `cabin.html` beside it. Switched on, the cabin becomes `index.html` and the
  ring is written as `doors.html`. John switches it on once the cabin looks real.
- The first version was drawn entirely in code (flat-shaded boxes, canvas textures); John's verdict was that it must be
  "more immersive and 3D ... as hyper realistic (human) as possible", with two reference photos of real log great rooms.
  The second version (2026-10-01) is a log great room 10.4 by 9 m under a vaulted roof (eave 3.6 m, ridge 6.6 m): round
  logs as geometry for the walls (interlocking courses, ends proud of the corners), rafters, purlins, ridge, two log
  trusses, a loft over the back with a log railing and a steep stair, a gable wall of glass rising to the roof, a deck
  with a log railing outside, a stacked-stone chimney breast with the firebox cut into it, a hearth and a log mantel, and
  a fire of shader flames, sparks, coals and a flickering point light that casts shadows. Materials are photographed
  (CC0, Poly Haven and ambientCG, in `cabin_assets/tex/`: colour, normal and AO/roughness maps, shrunk to 1k or 512) and
  the furniture is CC0 models from Poly Haven (`cabin_assets/models/`, textures shrunk): a tufted leather sofa, two
  bergère armchairs, a rocking chair, a bench coffee table, two tall side tables, a wrought-iron lantern chandelier,
  throw pillows and a vase; the rug is a design drawn in the Persian manner over the weave of a photographed carpet.
  Outside the windows is a public-domain National Park Service photograph of Rocky Mountain National Park
  (`cabin_assets/view/`, 2048 px wide, from NPGallery, each record marked "Public domain"), one per hour and season
  where one was found, shown at the angle a real lens sees with its horizon at eye level, mirrored beyond its sides,
  graded for the hour; there is no night photograph, so night darkens the September twilight picture and strews stars
  over its sky parts, and the footer says so. `cabin_assets/credits.json` lists every work with author, licence and
  source page, and the page's Credits button shows them. The add-ons the room needs (GLTFLoader, EffectComposer,
  UnrealBloomPass, OutputPass, RoomEnvironment) are vendored from the same three.js release into `vendor/jsm/` with
  their `from 'three'` imports pointed at the kit's copy; `build_cabin.py` copies all of it beside the page (about 10 MB
  in all) and imports the room with a content hash so a browser never keeps an old copy. Phones (`?lite=1` forces it)
  draw without bloom and with smaller shadows, and a phone held upright starts further back so both posters fit. John
  likes the two doors as signs at the foot of the page: keep them bold and glowing. Keep also: walking, the visitor's
  clock, the plain way in, the still page for devices with no 3D or with Motion off, and no `setPointerCapture` (drag
  listeners sit on the window). What still falls short of a photograph: no global illumination (light does not bounce,
  so corners and the underside of the loft are evenly lit by the sky light), the sofa's leather grain is the model's
  normal map over a flat colour, the mantel books and the blanket are plain boxes, and the view is one flat photograph
  at 75 m, so the parallax is the deck railing's, not the mountains'.
- To check frames in the Browser pane (which draws no animation while hidden): start a throwaway local saver that
  accepts a POST with CORS, call `window.__cabin.still(960, 600, {x, z, yaw, pitch})` in the page, POST the data URL
  to it, and Read the JPEG. A `//` comment added in the middle of a one-line function swallows the rest of the line:
  use `/* */` there.
- Pages that do not show their workings (John, 2026-10-01): no page offers the whole site as a file to download (the
  one-file archive `site/dev.html` is still built, for the 16 MB rule, but `offline.html` is no longer copied into the
  fast site), and no page names the kit's own files or programs: footers say "Generated on <date>", the lenses' "Check
  it yourself" notes give the formulas, the self-test and the download of every figure without naming a program, and
  `build_ballot_state_dev.plain_source()` takes database and program names out of source lines on their way to the
  page. `quiet_pages.py` is the last pass over the built `.html` files (program names, "python ..." command lines and
  database names inside the pages' own script and comments); `Publish dev site.bat` runs it before it copies the draft.
  A reader can always save a page they are looking at; what is gone is the offer and the hints. The repository that
  serves the site is public and holds all the code and these notes; John chose to leave that for now and plan a split
  (code in a private repository, a public one holding only the built pages; creating the private repository is his
  step). Do not make the split, or change the repository's visibility, without him.

## The Congress ballot pages, reworked, and facts found on the open web (v4.0.079)

John's nine marked-up screenshots (2026-10-01). On `build_ballot_dev.py`'s pages: the "Every state" map sits directly
under the number tiles; "Your ballot" has "Use my location" (the state from the page's state shapes, the district from
the lines the maps draw, on the device; a state with new 2026 lines places the reader in the state only) and then a
paper-style preview headed "Your ballot: a preview" (office, "Vote for one", each name as printed with party, an empty
oval; the county's sample ballot is the authority); "The Senate races" and "Every race, state by state" start folded,
a fold per state; on a race page Polls and "What bettors are paying" are two pull-down tabs above the arena, closed to
start, with everything the betting notice carried; the comparison's sections start closed and each candidate's column
moves and hides; the fight cards move (arrows, drag without pointer capture) and hide, with "Put back the official
order". One arrangement serves cards and columns, kept per race in localStorage; the page's own order is always the
official list's and the note says so. The arena is `color-mix(ink 7%, bg)` and follows the theme (the state ballot
pages borrow the same stylesheet). Left for John: small arrow buttons on phones, a stray "vs" when cards wrap, Senate
folds in postal-code order, and no arrange controls on the state ballot pages.

Facts found on the open web (John: "sweep the internet, ethically and responsibly"), for candidates for Congress on
the November lists only; state and local candidates stay under the strict rule.
- `ballot/found/<ST>-<k>.json`: 56 files written by research agents and then checked by a second agent that re-opened
  every source ("verified": true on what it confirmed; unconfirmed findings deleted). Allowed: the campaign's own
  website (the site itself must name the candidate and the office or district), the year of birth (a full date only
  from an official or campaign page), and public offices held, each with the page that states it and its kind:
  `official` (a government's own page), `campaign`, `secondary` (Wikipedia with a citation, a named news
  organization). Never: addresses, phones, family, religion, health, employers, schools, legal troubles, endorsements,
  views; never people-search sites, data brokers, voter files, logins, paywalls, CAPTCHAs. A finding needs two anchors
  tying the person to the race, or it is left out.
- `ballot/found.py` (stage `found` of `run_ballot.py`, after `people`) loads only verified findings: websites into the
  `websites` table (source begins "Found on the open web"; a listed or FEC website is never replaced), birth years and
  offices into `found_facts`. Official records stay first: a found fact fills a blank only, and found offices of a
  person the official record already covers are held back and listed in `ballot/found/REVIEW.md` with the review
  items (things our pages show that an official source contradicts; a person reads them, nothing changes by itself).
  `run_ballot.py` also gained `--db <file>` and `--only "<person>;<person>"`.
- The page shows a found birth year as "about 51" on the card and, in the comparison, "born 1975, according to
  <source>" / "according to their campaign" / "as reported by <source>", linked; found offices as "office, 2015 to
  2019" with the same labels and "years not counted"; a found office reaches the card only when official and held
  today. Totals at v4.0.079: 824 websites, 191 offices (31 official, 73 campaign, 87 secondary), 56 birth years
  (9 official, 4 campaign, 43 secondary). Photo options fetched from found websites still need the contact-sheet
  review before any appears (`ballot/photo_choice.json`).
- Many campaign sites answer scripts with 429 or a CAPTCHA; those findings were deleted, never worked around.

## Minnesota, finished (v4.0.081), and how the next state is done

John's order (2026-10-01): finish Minnesota's state and local ballot page, publish it, then give every other state the
same treatment, outward from Minnesota. His three decisions change the earlier "name, office, party only" rule for
state and local candidates; the binding text is `ballot/found_local/RULES.md` (every agent reads it first):

- Shown for statewide offices, the Legislature, judges, county offices, mayors, councils and school boards: campaign
  website, a photo from the candidate's own campaign site (or the roster's official portrait), a birth year, offices
  held, issue headings, each with its source and kind (official, campaign, party, secondary). Township and small
  district candidates: what they filed, plus a filed campaign website. Never addresses, phones, e-mail, family,
  employers, health, views; never social media, people-search sites or voter files as a source.
- Lean is "the record, not a label": a party's own published endorsement, an earlier run or office under a party
  label, the candidate's own words (twelve words at most), and how the PLACE voted before, from official results.
  Nobody's politics is guessed. Parties' "letters of support" are kept apart and not shown.
- Streets on the map are OpenStreetMap tiles, off until the reader switches them on, with the credit and a sentence
  saying OpenStreetMap's servers see which map squares are asked for. No Google Maps.

The pieces, in the order they are run for a state (Minnesota's file names; another state gets its own):
1. `ballot/local_sites.py` (stages `localfacts`, `localfetch` of `run_ballot.py`): reads ONLY the campaign website
   cell of the state's candidate files into `sl_websites`; loads verified findings into `sl_found_facts`; fetches photo
   options (`sl_photo_options`) and issue headings (`sl_issues`, with a `FURNITURE` filter;
   `python -m ballot.local_sites headings` re-filters) from the campaign sites; applies
   `ballot/photo_choice_local.json` into `sl_photos`. Run long fetches as `cmd /c "... > log 2>&1"`: PowerShell's own
   redirection turns a Pillow warning into a failure and stops the run.
2. Scope and research: `ballot/found_local/mn_scope.json` (statewide, legislature, courts, every county office, and
   cities and school districts of about 10,000 people or more: 2,171 candidates in 73 parts), researched by one agent
   a part and re-opened by a second (`ballot/found_local/MN-<k>.json`; only `"verified": true` is loaded). The tiny
   workflow script `mn-research-batch` takes `{"n", "verify": [...], "find": [...]}`. Check afterwards that every part
   file exists: one part was reported done and never written.
3. The record of lean: `ballot/lean/mn_endorsements.json` (71 lists on the parties' own pages) and
   `ballot/mn_place_votes.py` -> `ballot/lean/mn_place_votes.json` (precinct results from the Minnesota Geospatial
   Commons added up to county, city or township and district, with control totals).
4. Geography: `ballot/mn_geo.py` -> `ballot_geo/mn/` (TopoJSON: one precinct file per county, 13 outline layers,
   school districts; ids match `sl_places` and `sl_races`; reader `ballot/mn_geo_reader.js`; a self-test of known
   points). Polling places: Minnesota sells its list (Secretary of State order form, $46): the builder shows them when
   `ballot_geo/mn/polling_places.json` exists, from a file John saves as
   `states_cache/mn_local/sos/pollingplaces/polling_place_list_20261103.txt`, and says why not when it does not.
5. Polls and markets: `ballot/polls/polls_mn_state_2026.json`, `ballot/odds_state_mn.json`; `ballot/odds.py` snapshots
   state markets into `ballot_cache/odds/odds_state_2026.json`. Where no market lists a statewide or county race the
   page says why that is usual, and gives no advice about starting or using one.
6. The page (`build_ballot_state_dev.py`): one Web Mercator map with twelve kinds of line, drag, wheel, pinch,
   keyboard and a Find box; "Use my location" drops a pin, finds the precinct on the device, names every zone and cuts
   the ballot to it (the exact spot is not kept; a copy rounded to about half a mile stays on the device until
   "Forget"); candidate facts with sources; the record section; polls and market tabs; ads in folds of five and sources
   folded by kind (also on the Congress pages).
7. The photo look (`ballot/photo_choice_local.json`, keys "race_id|name"): stricter than for Congress, because many are
   private citizens: one adult alone AND the picture's own address or file name says it is the candidate's portrait;
   anything else, none.
8. Land it: `localfacts`, `localfetch`, `headings`, `localfacts`, `python run_ballot.py odds`, `python run_ballot.py
   site`, `python quiet_pages.py site\dev`, `python -m ballot.scan_local_privacy <code>`, a look in the Browser pane,
   the smoke test, save, and (when John has said so) `publish_dev.ps1`, which retries the two things that fail here:
   git blocked from writing a file, and the router losing the lookup during a push.

Ohio (v4.0.087) taught four things. Its parties publish slate cards and "sample ballots" far more than endorsements:
only a page that itself says "endorsed" counts, the rest is kept apart under `other_support` and not shown. Two county
parties publish their endorsed lists as pictures; a second agent read both again without the first reading before any
was kept. ohiosos.gov refuses scripts, so the past-vote workbooks were read from the Internet Archive's captures taken
at the Secretary's own address (the source list says so, with each file's SHA-256, and the totals equal the official
canvass); John was told and can veto that route. A market is held back by the words "Ask John before showing" in its
note in `ballot/odds_state_<code>.json` (`HELD` in `build_ballot_state_dev.py`). And `past_party` needs the label on
the record (a primary or nomination, a ballot that printed the party, a seat in a body whose members sit by party, a
party committee's appointment): a news article calling someone a Democrat or a Republican is not one (RULES.md).
`state-page-only` now takes an optional `notes` argument (what the data stage reported) and keeps five states' built
data byte-identical.

Missouri (v4.0.090) taught these. Missouri sells its precinct results and publishes none, so past votes are by
county only (from the Secretary of State's county results), and the page says why a city has none. Fifty of its court
contests are retention votes: a retention race is one name and a yes-or-no question, on the card, the arena and the
comparison, in every state. A Democratic club is not a party committee: its picks are `other_support`, unshown. A
campaign page on a website builder that many candidates share (upballot.com) is a campaign website, but a photo
whose only claim is that builder's shared "candidates" folder is a pick resting on placement, so none. "In office
now": `_year(end=True)` in `ballot/local_sites.py` now reads "present (term expires 2026)", "current term ...",
"term expires January 2027" as held today, and the builder marks an office as held today when it is the ONE
open-ended office stated on the candidate's own official page and no other office on record began after it (a page
about a county legislator that also mentions an earlier school board seat settles nothing); 127 cards gained an
office this way, each read through. A scratch file named like a standard module (calendar.py in the scratchpad)
shadows Python's own when a script is run from that folder: name scratch files so they cannot collide.

State and local race pages use the Congress cards (v4.0.089; John, 2026-10-02: "cleanup the governor and statewide
type of elections + local levels so those cards look similar to the higher level ones"). `build_ballot_state_dev.py`
borrows from `build_ballot_dev.PAGE` by landmark (`borrow_ballot`; the build stops and names a missing landmark): the
reader's arrangement (one per race, `ballot:arr:<race id>` in localStorage, shared by cards and columns), `arenaCards`,
the comparison's frame and `wireArena`. Its own: what a card holds (age, office held today, ballot order; never
money), the comparison's sections (On the ballot; Who they are; The record, not a label; In office; each only when it
has rows; all closed to start) and their source lines. Differences from the Congress page, on purpose: "vs" only
between exactly two cards (a school board's names are not versus one another); a one-name race has no move or hide
controls; the controls sit in a row above the portrait; a card's height grows with its words and is evened within a
race by script. A small office (township, small district) gets the comparison only when a candidate filed a website.
"Forget my location and choices" also clears every `ballot:arr:` key. The comparison's "On the ballot" section shows
each candidate's list note (retention, unopposed, capitals, a replaced nominee); a scan found nothing sensitive in
them, and John can have the row dropped. Shell budgets are now 340 KB (lists alone) and 405 KB (with extras; Michigan
is at 400 KB, so the next growth needs a trim or a raise). Built by a builder, three reviewers (look, rules, code),
a fixer and a last check; before-copies were in the session scratchpad.

Michigan (v4.0.088) taught these. The Michigan Voter Information Center (mvic.sos.state.mi.us/votehistory) answers
scripts 403 and serves the Browser pane normally; its own download links give each election's precinct file
(`/VoteHistory/GetPrecinctResultsFile?electionId=` 699 for 2024, 691 for 2022, 683 for 2020: `<year>GEN.zip`) and
county file (`/VoteHistory/GetElectionResultFile?electionId=`), carried out of the pane into `states_cache/mi_local/`
(in-page fetch, returned as `ZIPB64:<name>:<len>:<base64>`, decoded from the saved tool result). The Bureau's old
host miboecfr.nictusa.com is now a people-search site: never request it. The 2024 tables begin with a UTF-8
byte-order mark. The precinct files do not always add up to the Bureau's county totals (2022: 68 counties differ,
most only in minor-party and write-in votes; 2020: ten, Clinton and Eaton by over a thousand), so
`ballot/mi_place_votes.py` gives a contest for a county, and the places in it, only where the county's precincts
equal the county file exactly, and lists every county left out with both figures. Supreme Court justices are
nominated at party conventions and printed without a party: an `other_support` record of kind "convention nominee" is
shown in its own words, apart from endorsements (every other `other_support` kind stays unshown). A market outcome
that names nobody on the November list is not drawn, and the tab says so. A PDF draws a letter its font lacks in
another font, which splits a name into pieces that touch ("Matea Č" + "aluk"): Ingham's reader now joins a piece
that begins exactly where the name cell ends. A county list's reading is cached for some days
(`ballot_cache/mi/local/<county>_2026_general_list.json`): after changing a reader, move that file aside or the old
reading is used again. The photo-look script's repair agent now runs only when asked (`"repair": true`). Research for
a big state goes out in halves (`parts` in the script's args), with a usage reading between them.

States finished this way: MN (v4.0.081), WI (.082), IA (.083), ND (.085), SD (.086), OH (.087), MI (.088). A candidate's page on a party's
own website is not their campaign website, whoever paid for it (RULES.md): `party_hosts(state)` in
`ballot/local_sites.py` reads the parties' hosts from `ballot/lean/<code>_endorsements.json`, and the findings loader
sets such a page aside, counts it and lists it on the state's review sheet (eight in North Dakota, all on
demnpl.com); no photo is taken from one. Do not start a state's data stage while a full rebuild or a publish is
running, or a half-written `ballot_geo/<code>/` gets built into the pages. The page shell for a state with a map is
350 to 366 KB (about 95 KB as the server sends it); the builder's warning line (`SHELL_LIMIT_EXTRAS`) was raised to
380 KB so that it means growth, not the settled size.

Usage, learned the hard way (2026-10-02): a CronCreate job does not run while a workflow runs, so it cannot guard
anything; a 110-agent max-effort wave ran through the session limit and spent $92.09 of John's paid extra usage. Run
agents in batches of about 10M tokens or less, read `get_usage` between batches, never start a batch above 40 percent
of the 5-hour window or 90 percent of the week, and stop at 99 percent of the week. Research at effort high and
verification at medium cost about a third of max.

## Optional: rate more bills with the Claude API

John runs this himself in a separate terminal where he has set `ANTHROPIC_API_KEY`, so the key never passes
through this session: `python run_all.py rate` (shows the bill count and cost estimate, then asks him to type YES),
and later `python run_all.py collect` (writes finished ratings and rebuilds the site). If he asks you about it,
explain those two commands; don't run them yourself, and never ask for or handle the key. Model ratings are
labeled "Automated rating, not yet reviewed" on the site until a person reviews them
(`python score_bills.py --db congress_119.sqlite --review-md review.md --where "..."` writes a review sheet).
