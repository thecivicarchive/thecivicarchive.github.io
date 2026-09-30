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
  three-second fireworks for the way back. The fireworks are red, white and blue by word, CLICK TO SEE in silver.
- Betting-market odds (John's answers, 2026-09-29): Polymarket and Kalshi, as information only, labelled "what
  bettors are paying: not a poll, a forecast or an official record", with trading volume and the time. A click opens a
  calm notice box: gambling disclaimer, age limits, a state-law warning (availability is disputed in some states),
  the national problem-gambling helpline and the reader's own state's (from the state they picked or their location,
  worked out on the device), and "Go to the market" or "Stay here". No slot machine, no referral codes. Not built yet.
- Next, in order: more states' lists, largest first (NY, PA, IL, OH, GA, NC, MI ...); campaign websites and photos once
  the key is saved; betting-market odds; Florida's primary votes; the California certified-list check; ads (the FEC's
  independent expenditure file, whose purpose column gives the medium; ad library links); polls (AAPOR's list); share
  pages for races; then state and local ballots.

## Optional: rate more bills with the Claude API

John runs this himself in a separate terminal where he has set `ANTHROPIC_API_KEY`, so the key never passes
through this session: `python run_all.py rate` (shows the bill count and cost estimate, then asks him to type YES),
and later `python run_all.py collect` (writes finished ratings and rebuilds the site). If he asks you about it,
explain those two commands; don't run them yourself, and never ask for or handle the key. Model ratings are
labeled "Automated rating, not yet reviewed" on the site until a person reviews them
(`python score_bills.py --db congress_119.sqlite --review-md review.md --where "..."` writes a review sheet).
