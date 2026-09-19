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
| `python run_all.py` | Full build: check, roster, catalog, rollcalls, photos, districts, ratings, build, verify | 30 to 60 min the first time |
| `python run_all.py refresh` | Weekly update: re-downloads the catalog, then everything after it | 15 to 30 min |
| `python run_all.py <stage>` | One stage: `roster`, `catalog`, `rollcalls`, `photos`, `districts`, `ratings`, `build`, `verify` | varies |

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
- **Check stage FAILs on a website**: confirm the machine is online; a work VPN or firewall can block government
  sites. Try again off the VPN.
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

## Files

| File | Purpose |
| --- | --- |
| `START_HERE.txt` | The plain-words walkthrough John follows; `Start Claude Code (Mac).command` and `Start Claude Code (Windows).bat` open this folder in Claude Code with one double-click (installing Claude Code the first time) |
| `run_all.py` | Orchestrator: stages, private environment, logs, verify report |
| `congress_catalog.py` | Downloads GovInfo Bill Status XML and loads the database (and Excel copy) |
| `load_legislators.py` | Loads the member roster: age, years in Congress, phone, website, Senate ID crosswalk |
| `load_roll_calls.py` | Loads every linked House and Senate roll call, member by member, with a disk cache |
| `load_photos.py` | Official member portraits (public domain, unitedstates/images) as 2 KB WebP thumbnails in the database |
| `load_districts.py`, `albers_usa.py` | House district lines for the map's zoom-in view: Census cartographic file for the current Congress when reachable, else the 2016 lines from GitHub; projected into the map's Albers space |
| `us_districts_albers.json` | The district lines the site embeds (the kit ships the 2016 fallback; the districts stage replaces it with the current Census lines) |
| `score_bills.py` | Ratings: import, party backing from roll calls (`--backing-only`, free), optional Claude API scoring |
| `build_site.py` | Builds the one-file website from the database |
| `rubric_v1.md` | The rating rubric (read-only) |
| `seed/seed_ratings_119.json` | Ten hand-applied preview ratings for current bills |
| `us_states_albers.json` | State map shapes (public domain, from the us-atlas package) |
| `schema_postgres.sql` | The same database schema for Postgres, for a hosted version later |
| `tests/samples/` | Eight real 2025-26 bills for the offline smoke test |

## Optional: rate more bills with the Claude API

John runs this himself in a separate terminal where he has set `ANTHROPIC_API_KEY`, so the key never passes
through this session: `python run_all.py rate` (shows the bill count and cost estimate, then asks him to type YES),
and later `python run_all.py collect` (writes finished ratings and rebuilds the site). If he asks you about it,
explain those two commands; don't run them yourself, and never ask for or handle the key. Model ratings are
labeled "Automated rating, not yet reviewed" on the site until a person reviews them
(`python score_bills.py --db congress_119.sqlite --review-md review.md --where "..."` writes a review sheet).
