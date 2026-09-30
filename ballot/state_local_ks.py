"""
ballot/state_local_ks.py - Kansas's state races on the November 3, 2026 ballot: all 125 seats of the Kansas House of
Representatives, the Kansas Senate seats on this year's ballot after a vacancy (the whole Senate is elected in presidential
years and was last elected in 2024), Governor with Lieutenant Governor (one ticket), Secretary of State, Attorney General,
State Treasurer, Commissioner of Insurance, the State Board of Education seats up this year, and the partisan District
Court and District Magistrate Judge seats, with the August 4 party primaries that chose the nominees. Written into
ballot_local_2026.sqlite (never ballot_2026.sqlite).

Sources, all the Kansas Secretary of State's own, the same ones the federal loader (ballot/lists/ks.py) reads:

  2026 Primary Election Official Vote Totals (PDF, "2026 Official Primary Election Results" on
      sos.ks.gov/elections/election-results.html). It holds race headings, party initials, ballot names, votes and
      percents only, so it is cached whole (ballot_cache/ks/, shared with the federal loader).
  Candidate List, 2026 General (the Candidate List page, sos.ks.gov/elections/elections_upcoming_candidate.aspx, with
      "2026 General" chosen). The site's CloudFront answers scripts on that page with 403, so it is never requested
      here: John saves the page in his own browser into ballot_cache/ks/ (see ballot/lists/ks.py), and this loader
      reads the newest saved page that shows "2026 General". Its table also carries home and mailing addresses,
      phones, e-mail and web addresses; columns are found from the heading cells and only Candidate (else First Name,
      Middle, Last Name, Suffix), Office, District, Division, Position, Party, and a Status or Ballot Order column if
      there is one, are ever turned into text. What was read is kept as a small JSON extract
      (ks_candidate_list_2026_general_state.json) with the saved page's SHA-256. Until a saved page is there, no
      November candidates are stored (the primary winners alone would leave off Libertarian and independent
      candidates and any nominee replaced since August); the races and the primary fields are stored, and the report
      says the list is waiting.

The Secretary had posted precinct workbooks for the 2026 primary for Congress only (the results page, read on
2026-09-30); none for the state offices. So the state totals are checked within themselves: every printed percent
must equal the candidate's votes over the party's listed candidates' votes (the totals give no count of other
write-ins), each party's percents must add up to 100, and no race or candidate may appear twice.

What the record does not say, the loader does not say:
  - Kansas elects the Governor and Lieutenant Governor on one ticket; the totals print "Governor / Lt. Governor"
    and each ticket as "Governor name / Lieutenant Governor name". There is one race, 2026-KS-GOV; the candidate is
    the name for Governor and the running mate is named in the candidate's note.
  - Today's holder comes from the Open States roster in state_ks.sqlite (legislators by chamber and district; the
    officials table for Governor, Secretary of State and Attorney General). The roster carries no Treasurer,
    Commissioner of Insurance, State Board of Education member or judge, so those races show no holder.
  - A candidate is marked as the sitting member only when the name fits the roster's holder of that same seat and no
    other person in the race fits.
  - The primary totals print no ballot order, and neither did the list as laid out in 2020; a ballot order is
    stored only if the saved list carries a Ballot Order column.
  - District court judge seats that are retention votes, and the Supreme Court and Court of Appeals retention votes,
    have no primary; they can only come from the November list, and an office on it the loader does not know is
    named in the report, never dropped silently.

Primaries: a party primary becomes a field when two or more names were printed on that party's ballot. Kansas nominates
the candidate with the most votes and has no runoff, so the leader advanced; once the November list is loaded, the
party's candidate on it must be the same person, and a row says so if not. Shares are of the listed candidates' votes,
as the totals print them. Libertarians nominate by convention and have no primary.
"""

import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.common import CACHE, HERE, fold, name_parts, party_code      # noqa: E402
from ballot.lists import ks as fed                                      # noqa: E402
from ballot.match import fits                                           # noqa: E402
from ballot.pdftext import lines                                        # noqa: E402
from states import net                                                 # noqa: E402

STATE, FIPS, NAME = "KS", "20", "Kansas"
GENERAL = "2026-11-03"
PRIMARY = fed.PRIMARY
ELECTION = fed.ELECTION
ROSTER_DB = os.path.join(HERE, "state_ks.sqlite")
JSON_NAME = "ks_candidate_list_2026_general_state.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

SRC_TOTALS = "ks-sos-2026-primary-vote-totals"
SRC_GENERAL = "ks-sos-2026-general-list"
SRC_ROSTER = "ks-openstates-roster"

# (pattern for the office as the totals or the list print it, key, level, office_kind, office shown, roster office)
# A pattern's group d is the district, s the seat within it (a judge's division); either may come from its own column.
OFFICES = [
    (r"Governor(?: / (?:Lt\.?|Lieutenant) Governor)?", "GOV", "statewide", "governor", "Governor and Lieutenant Governor", "governor"),
    (r"(?:Lt\.?|Lieutenant) Governor", "MATE", None, None, None, None),
    (r"Secretary of State", "SOS", "statewide", "secretary_of_state", "Secretary of State", "secretary of state"),
    (r"Attorney General", "AG", "statewide", "attorney_general", "Attorney General", "attorney general"),
    (r"(?:State )?Treasurer", "TREAS", "statewide", "state_treasurer", "State Treasurer", None),
    (r"Commissioner of Insurance|Insurance Commissioner", "INS", "statewide", "insurance_commissioner", "Commissioner of Insurance", None),
    (r"(?:Kansas (?:State )?Senat(?:e|or)|State Senat(?:e|or))(?: (?:District )?(?P<d>\d+))?", "SS", "legislature", "state_senate",
     "State Senator", "Senate"),
    (r"(?:Kansas House of Representatives|(?:Kansas )?State Representative)(?: (?:District )?(?P<d>\d+))?", "SH", "legislature",
     "state_house", "State Representative", "House"),
    (r"(?:Member, )?State Board of Education(?: (?:District )?(?P<d>\d+))?", "SBOE", "statewide", "state_board_of_education",
     "Member, State Board of Education", None),
    (r"District Court Judge(?: (?P<d>\d+)(?:-(?P<s>\d+))?)?", "DC", "court", "district_court", "District Court Judge", None),
    (r"District Magistrate Judge(?: (?P<d>\d+)(?:-(?P<s>\d+))?)?", "DM", "court", "district_magistrate", "District Magistrate Judge", None),
]
QUESTION = re.compile(r"^Constitutional Amendment\b")       # a ballot question, not a race: its lines are counted and passed over


class Unknown(Exception):
    """An office the loader does not know."""


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def digits(v):
    s = re.sub(r"\D", "", str(v or ""))
    return str(int(s)) if s else ""


def office_of(office, district="", division=""):
    """The race an office names: a dict, None for Congress, {"key": "MATE"} for a separate Lieutenant Governor row;
    Unknown for anything else, so a new office is noticed rather than dropped."""
    o = re.sub(r"\s*/\s*", " / ", re.sub(r"\s+", " ", office or "").strip())
    if fed.race_of(o, district):
        return None
    for pat, key, level, kind, shown, roster in OFFICES:
        m = re.fullmatch(pat, o, re.I)
        if not m:
            continue
        if key == "MATE":
            return {"key": "MATE"}
        gd = m.groupdict()
        d = digits(gd.get("d")) or digits(district)
        s = digits(gd.get("s")) or digits(division)
        info = {"key": key, "level": level, "office_kind": kind, "office": shown, "roster": roster, "district": None, "seat": None,
                "jurisdiction": NAME, "jurisdiction_id": FIPS, "special": 0, "chamber": None}
        if key in ("SS", "SH", "SBOE"):
            if not d:
                raise Unknown(f"{o} (no district)")
            info.update(race_id=f"2026-{STATE}-{key}{d}", district=d)
            if key != "SBOE":
                info["chamber"] = roster
            if key == "SS":
                info["special"] = 1        # the whole Senate is elected in presidential years; a 2026 seat follows a vacancy
        elif key in ("DC", "DM"):
            if not d:
                raise Unknown(f"{o} (no judicial district)")
            info.update(race_id=f"2026-{STATE}-{key}-{d}" + (f"-{s}" if s else ""), district=d, seat=f"{d}-{s}" if s else None,
                        jurisdiction=f"{ordinal(d)} Judicial District", jurisdiction_id=d)
        else:
            info["race_id"] = f"2026-{STATE}-{key}"
        return info
    raise Unknown(o)


# ---------- the August 4 primary: the Official Vote Totals ----------

def primary(path):
    """({race_id: {"info", "heading", "entries": [(party, name, votes, printed pct, write_in, mate)]}}, federal lines,
    ballot-question lines) from the Official Vote Totals, every section checked within itself."""
    L = lines(path)
    first = " ".join(t for p, _y, t in L if p == 1)
    if "2026 Primary Election" not in first or "Official Vote Totals" not in first:
        raise SystemExit("Kansas (state races): the file is not the 2026 Primary Election Official Vote Totals")
    out, race, n_fed, n_q, in_fed = {}, None, 0, 0, False
    for _p, _y, t in L:
        if fed.FURNITURE.match(t):
            continue
        if QUESTION.match(t):
            race, in_fed, n_q = None, False, n_q + 1
            continue
        m = fed.LINE.match(t)
        if not m:        # a race's heading
            try:
                info = office_of(t)
            except Unknown as e:
                raise SystemExit(f"Kansas (state races): a race in the Official Vote Totals the loader does not know: {e}")
            if info is None:
                race, in_fed = None, True
                continue
            if info["key"] == "MATE":
                raise SystemExit("Kansas (state races): the Official Vote Totals print a separate Lieutenant Governor race")
            race, in_fed = info["race_id"], False
            if race in out:
                raise SystemExit(f"Kansas (state races): the Official Vote Totals list {t!r} twice")
            out[race] = {"info": info, "heading": t, "entries": []}
            continue
        if race is None:
            if in_fed:
                n_fed += 1
                continue
            raise SystemExit(f"Kansas (state races): a candidate line before any race heading: {t!r}")
        if m.group("p") not in fed.INITIAL:
            raise SystemExit(f"Kansas (state races): a party initial the loader does not know under {race}: {m.group('p')!r}")
        name, wi, mate = m.group("name"), False, None
        w = re.fullmatch(r"(.+?) \(Write-in\)", name)
        if w:
            name, wi = w.group(1), True
        if out[race]["info"]["key"] == "GOV":
            parts = [x.strip() for x in name.split(" / ")]
            if len(parts) != 2 or not all(parts):
                raise SystemExit(f"Kansas (state races): a Governor line without its running mate: {t!r}")
            name, mate = parts
        out[race]["entries"].append((fed.INITIAL[m.group("p")], name, int(m.group("votes").replace(",", "")), float(m.group("pct")), wi, mate))
    problems = []
    for race, sec in out.items():
        if not sec["entries"]:
            problems.append(f"{race}: a heading with no candidates")
        by = defaultdict(list)
        for e in sec["entries"]:
            by[e[0]].append(e)
        for party, es in by.items():
            names = [fold(e[1]) for e in es]
            if len(set(names)) != len(names):
                problems.append(f"{race} {party}: a name printed twice")
            total = sum(e[2] for e in es)
            for e in es:
                if total and abs(100 * e[2] / total - e[3]) > 0.006:
                    problems.append(f"{race} {party} {e[1]}: printed {e[3]}%, votes give {100 * e[2] / total:.3f}%")
            if total and abs(sum(e[3] for e in es) - 100) > 0.02 * len(es):
                problems.append(f"{race} {party}: the printed percents add up to {sum(e[3] for e in es):.2f}")
    if problems:
        raise SystemExit("Kansas (state races): the Official Vote Totals do not add up: " + "; ".join(problems))
    return out, n_fed, n_q


# ---------- the November list, from a page John saved ----------

NAME_COL, PARTS = fed.NAME_COL, fed.PARTS
KEEP, OPTIONAL = ("Office", "District", "Party"), ("Division", "Position", "Status", "Ballot Order")


def list_rows(page, name):
    """(election shown, [state rows], Counter of offices not known) from a saved Candidate List page, or None when the
    page is not the 2026 General list. Columns are found from the heading cells; only the allowlisted cells of each
    row are ever turned into text (the address, phone, e-mail and web cells are never read)."""
    chosen = None
    for sel in re.findall(r"<select\b[^>]*>(.*?)</select>", page, re.S | re.I):
        m = re.search(r"<option\b[^>]*\bselected\b[^>]*>(.*?)</option>", sel, re.S | re.I)
        if m and re.search(r"\b20\d\d\b", fed.text(m.group(1))):
            chosen = fed.text(m.group(1))
            break
    if chosen is not None and chosen != ELECTION:
        return None
    trs = list(re.finditer(r"<tr\b[^>]*>(.*?)</tr>", page, re.S | re.I))
    head_at, head = None, None
    for i, tr in enumerate(trs):
        cells = [fed.text(c) for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr.group(1), re.S | re.I)]
        if all(k in cells for k in KEEP) and (NAME_COL in cells or all(k in cells for k in PARTS)):
            head_at, head = i, cells
            break
    if head is None:
        if chosen == ELECTION:
            raise SystemExit(f"Kansas (state races): {name} shows \"{ELECTION}\" but no table with the columns {', '.join(KEEP)} and a name")
        return None
    end = page.find("</table>", trs[head_at].end())
    end = len(page) if end < 0 else end
    if chosen is None:
        if ELECTION not in fed.text(page[:trs[head_at].start()] + page[end:]):
            return None
        chosen = ELECTION
    if re.search(r"Page\$(?:\d+|Next|Last)", fed.H.unescape(page)):
        raise SystemExit(f"Kansas (state races): {name} is one page of a list the site splits into several; save it with every row showing")
    ix = {k: head.index(k) for k in (NAME_COL,) + PARTS + KEEP + OPTIONAL if k in head}
    out, unknown = [], Counter()
    for tr in trs[head_at + 1:]:
        if tr.start() > end:
            break
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", tr.group(1), re.S | re.I)
        if len(cells) != len(head):
            if len(cells) <= 1:
                continue
            raise SystemExit(f"Kansas (state races): a row of {name} has {len(cells)} cells under {len(head)} headings; read the page again")
        rec = {k: fed.text(cells[i]) for k, i in ix.items()}      # the allowlisted cells only
        try:
            info = office_of(rec["Office"], rec["District"], rec.get("Division") or rec.get("Position"))
        except Unknown as e:
            unknown[str(e)] += 1
            continue
        if info is None:
            continue
        full = rec.get(NAME_COL) or " ".join(rec.get(k, "") for k in PARTS if rec.get(k))
        out.append({"office": rec["Office"], "district": rec["District"], "division": rec.get("Division", ""),
                    "position": rec.get("Position", ""), "name": full, "party": rec["Party"], "status": rec.get("Status", ""),
                    "order": rec.get("Ballot Order", "")})
    return chosen, out, unknown


def general_list(folder, extract_dir, say):
    """(meta, path it came from) for the November list's state rows: from the newest saved page that is the 2026 General
    list (kept as a JSON extract of the allowed columns), else from an extract kept earlier, else (None, None)."""
    jpath = os.path.join(extract_dir, JSON_NAME)
    skipped = []
    for path in fed.saved_pages(folder):
        raw, page = fed.page_html(path)
        got = list_rows(page, os.path.basename(path))
        if got is None:
            skipped.append(os.path.basename(path))
            continue
        shown_as, rows, unknown = got
        meta = {"url": fed.LIST_PAGE, "origin": "saved in a browser: " + os.path.basename(path), "election": shown_as,
                "sha256": hashlib.sha256(raw).hexdigest(), "saved": dt.date.fromtimestamp(os.path.getmtime(path)).isoformat(),
                "read": dt.date.today().isoformat(), "unknown_offices": dict(unknown), "rows": rows}
        del raw, page
        os.makedirs(extract_dir, exist_ok=True)
        with open(jpath, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)
        if skipped:
            say(f"    Kansas (state races): saved pages that are not the 2026 General list, not read: {len(skipped)}")
        return meta, path
    if os.path.exists(jpath):
        meta = json.load(open(jpath, encoding="utf-8"))
        return meta, jpath
    return None, None


# ---------- the roster ----------

def roster(path=ROSTER_DB):
    """Today's holders: {("Senate"|"House", district): row}, {roster office: row}, the roster's date. Only ids, names,
    party, seat and the start of service are read; the roster's contact columns are not."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats, offices = {}, {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, chamber, district, term_start "
                         "FROM legislators WHERE is_current = 1"):
        key = (r[5], digits(r[6]))
        if key in seats:
            raise SystemExit(f"Kansas (state races): the roster lists two sitting members for {key}")
        seats[key] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4], "since": r[7] or ""}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, office FROM officials"):
        offices[r[5]] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3] or f"{r[1]} {r[2]}", "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, offices, as_of


def holder_fits(name, h):
    cand = name_parts(name)
    return any(fits(cand, reg) for reg in ((fold(h["first"]).split(), fold(h["last"])), name_parts(h["full"] or "")) if reg[1])


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if path and os.path.exists(path) else ""


def bucket(info):
    return info["office_kind"] if info["level"] == "legislature" else info["level"]


# ---------- the load ----------

def load(db_path, say=print, list_folder=None, extract_dir=None):
    net.patient_lookups()
    folder = os.path.join(CACHE, "ks")
    list_folder = list_folder or folder
    extract_dir = extract_dir or folder
    os.makedirs(folder, exist_ok=True)
    paths, urls = fed.fetch_results(folder, say)
    secs, n_fed_lines, n_q_lines = primary(paths["totals"])
    meta, list_path = general_list(list_folder, extract_dir, say)
    seats, offices, as_of = roster()

    races = {rid: s["info"] for rid, s in secs.items()}

    # the November list (when saved): state rows only; running mates on rows of their own are paired by party
    general, mates, gone, seen = [], defaultdict(list), [], set()
    unknown = Counter((meta or {}).get("unknown_offices") or {})
    caps_n = 0
    if meta:
        for r in meta["rows"]:
            st = r["status"].strip().lower()
            if any(g in st for g in fed.GONE):
                gone.append(r)
                continue
            if st not in fed.ON:
                raise SystemExit(f"Kansas (state races): a candidate status the loader does not know: {r['status']!r}")
            info = office_of(r["office"], r["district"], r["division"] or r["position"])
            party = re.sub(r"\s+", " ", r["party"]).strip()
            parts = [x for x in re.split(r"\s+/\s+", r["name"].strip()) if x]
            name, caps = fed.shown(parts[0] if parts else "")
            caps_n += caps
            write_in = bool(re.search(r"write[- ]?in", party + " " + r["name"], re.I))
            if write_in:
                name = re.sub(r"\s*\(write[- ]?in\)\s*", " ", name, flags=re.I).strip()
                party = re.sub(r"\s*\(?write[- ]?in\)?\s*", " ", party, flags=re.I).strip()
            if info["key"] == "MATE":
                mates[party].append(name)
                continue
            mate = fed.shown(parts[1])[0] if info["key"] == "GOV" and len(parts) > 1 else None
            if mate:
                mates[party].append(mate)
            rid = info["race_id"]
            races.setdefault(rid, info)
            if (rid, fold(name)) in seen:
                raise SystemExit(f"Kansas (state races): {name} is on the November list twice for {rid}")
            seen.add((rid, fold(name)))
            order = int(r["order"]) if str(r["order"]).strip().isdigit() else None
            general.append({"race": rid, "name": name, "party": party, "order": order, "write_in": write_in, "caps": caps})
    has_list = meta is not None

    # the seats on the ballot
    kinds = defaultdict(list)
    for rid, i in races.items():
        kinds[i["key"]].append(int(i["district"]) if i["district"] else 0)
    checks = []
    if sorted(kinds["SH"]) != list(range(1, 126)):
        missing = sorted(set(range(1, 126)) - set(kinds["SH"]))
        checks.append(f"House districts without a race: {missing}")
    missing_sw = [k for k in ("GOV", "SOS", "AG", "TREAS", "INS") if not kinds[k]]
    if missing_sw:
        checks.append(f"statewide offices with no race: {missing_sw}")
    senate_up = sorted(kinds["SS"])
    for d in senate_up:
        h = seats.get(("Senate", str(d)))
        if h and h["since"] and h["since"] < "2025-01-13":
            checks.append(f"Senate {d} is on the 2026 ballot, but its senator has served since {h['since']}")

    # today's holders
    holders, notes = {}, defaultdict(list)
    for rid, i in races.items():
        h = None
        if i["chamber"]:
            h = seats.get((i["chamber"], i["district"]))
            if h is None:
                notes[rid].append(f"The Open States roster ({as_of}) lists no sitting member for this seat.")
        elif i["roster"]:
            h = offices.get(i["roster"])
        else:
            what = "judges" if i["level"] == "court" else "this office"
            notes[rid].append(f"The Open States roster this site uses does not carry {what}, so today's holder is not shown.")
        holders[rid] = h
        if i["key"] == "SS":
            since = f"; its senator today has served since {h['since']}" if h and h["since"] else ""
            notes[rid].insert(0, "The Kansas Senate is elected in full in presidential years, last in 2024, for four-year terms. This seat "
                                 f"is on the 2026 ballot after a vacancy{since}.")
        if i["key"] == "GOV":
            notes[rid].insert(0, "Kansas elects the Governor and Lieutenant Governor together, one ticket to a party; each candidate's "
                                 "running mate for Lieutenant Governor is named in the candidate's note.")
        if not has_list:
            notes[rid].append("Kansas's November candidate list is not loaded yet; until it is, this race shows only an August 4 party "
                              "primary with two or more candidates, if there was one.")

    # the sitting member on the ballot: one person in the race fits the holder
    names_in = defaultdict(set)
    for g in general:
        names_in[g["race"]].add(g["name"])
    for rid, s in secs.items():
        names_in[rid].update(e[1] for e in s["entries"])
    sitting = {}
    for rid, h in holders.items():
        if not h:
            continue
        fit = [n for n in names_in.get(rid, ()) if holder_fits(n, h)]
        if fit and all(fed.same(fit[0], n) for n in fit[1:]):
            sitting[rid] = ({fold(n) for n in fit}, h["id"])
    is_inc = lambda rid, name: rid in sitting and fold(name) in sitting[rid][0]

    # November rows
    cand, nominee = [], defaultdict(list)
    gov_mate = {}
    for p, ms in mates.items():
        if len(ms) == 1:
            gov_mate[p] = ms[0]
    unpaired = [f"{p}: {len(ms)} running mates" for p, ms in mates.items() if len(ms) != 1]
    primary_names = {(rid, e[0]): [x[1] for x in s["entries"] if x[0] == e[0]] for rid, s in secs.items() for e in s["entries"]}
    leader = {}
    for (rid, party), ns in primary_names.items():
        es = [e for e in secs[rid]["entries"] if e[0] == party]
        if sum(1 for e in es if not e[4]) >= 2:
            best = max(e[2] for e in es)
            top = [e[1] for e in es if e[2] == best]
            if len(top) == 1:
                leader[(rid, party)] = top[0]
    for g in general:
        rid, party = g["race"], g["party"]
        note = []
        if races[rid]["key"] == "GOV":
            if party in gov_mate:
                note.append(f"Running mate for Lieutenant Governor: {gov_mate[party]}.")
            else:
                unpaired.append(f"{party}: no running mate on the list")
        if g["caps"]:
            note.append(fed.CAPS_NOTE)
        if g["write_in"]:
            note.append(fed.WRITE_IN_NOTE)
        elif party in ("Republican", "Democratic"):
            nominee[(rid, party)].append(g["name"])
            ballot = primary_names.get((rid, party), [])
            if not any(fed.same(g["name"], n) for n in ballot):
                note.append(f"Not on the August 4 {party} primary ballot; nominated afterwards (the list does not say how).")
            elif leader.get((rid, party)) and not fed.same(g["name"], leader[(rid, party)]):
                note.append(f"Lost the August 4 {party} primary, but is this party's candidate on the November list (the list does "
                            "not say how the nomination was made).")
        inc = is_inc(rid, g["name"])
        cand.append((rid, "general", GENERAL, g["name"], party, party_code("write-in" if g["write_in"] and not party else party),
                     g["order"], int(inc), int(g["write_in"]), None, None, None, sitting[rid][1] if inc else None, SRC_GENERAL,
                     " ".join(note) or None))
    doubled = [f"{rid} {p}" for (rid, p), ns in nominee.items() if len(ns) > 1]
    if doubled:
        raise SystemExit(f"Kansas (state races): two November candidates under one party in {', '.join(doubled)}; read the list again")
    n_general = len(cand)

    # the primary fields
    fields, upset, n_state_lines, n_primary_rows = Counter(), [], 0, 0
    for rid, s in sorted(secs.items()):
        n_state_lines += len(s["entries"])
        by = defaultdict(list)
        for e in s["entries"]:
            by[e[0]].append(e)
        for party, es in sorted(by.items()):
            if sum(1 for e in es if not e[4]) < 2:
                continue
            fields[bucket(races[rid])] += 1
            total = sum(e[2] for e in es)
            best = max(e[2] for e in es)
            leaders = [e[1] for e in es if e[2] == best]
            if len(leaders) > 1:
                raise SystemExit(f"Kansas (state races): a tie for first in the {party} primary for {rid}; the loader cannot say who advanced")
            off_list = has_list and not any(fed.same(leaders[0], x) for x in nominee.get((rid, party), []))
            if off_list:
                upset.append(f"{rid} {party}")
            for _p, name, votes, _pct, wi, mate in es:
                won = name == leaders[0]
                note = [x for x in (f"Running mate for Lieutenant Governor: {mate}." if mate else None,
                                    fed.WRITE_IN_NOTE if wi else None, fed.NOT_ON_LIST if won and off_list else None) if x]
                inc = is_inc(rid, name)
                cand.append((rid, f"primary-{fed.CODE[party]}", PRIMARY, name, party, party_code(party), None, int(inc), int(wi), votes,
                             round(100 * votes / total, 1) if total else None, "advanced" if won else "lost",
                             sitting[rid][1] if inc else None, SRC_TOTALS, " ".join(note) or None))
                n_primary_rows += 1

    # every seat has its November candidates
    empty = sorted(rid for rid in races if not any(g["race"] == rid for g in general)) if has_list else []

    race_rows = []
    for rid, i in sorted(races.items()):
        h = holders[rid]
        race_rows.append((rid, STATE, i["level"], i["office_kind"], i["office"], i["jurisdiction"], i["jurisdiction_id"], None,
                          i["district"], i["seat"], i["special"], 1, h["id"] if h else None, h["full"] if h else None,
                          h["party"] if h else None, GENERAL, " ".join(notes[rid]) or None))

    pub = fed.file_date(paths["totals"])
    src = [(SRC_TOTALS, STATE, "official results", "Kansas Secretary of State, Elections Division",
            "2026 Primary Election Official Vote Totals (August 4, 2026)", urls["totals"], pub, mdate(paths["totals"]),
            sha_of(paths["totals"]), n_state_lines,
            f"Statewide votes for every candidate on each party's primary ballot for {len(secs)} state offices. The totals give no "
            "count of other write-in votes, so shares are of the listed candidates' votes, as the totals print them; every printed "
            "percent was checked against the votes. The page prints no date" + (f"; the file's own properties date it {pub}" if pub else "")
            + ". On 2026-09-30 the Secretary's results page had precinct workbooks for Congress only, so the state totals could not "
            "be checked against county sums. Congress and the constitutional amendment question are left to other pages."),
           (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
            "Kansas legislators and statewide officials, as loaded into state_ks.sqlite", "https://github.com/openstates/people",
            as_of, as_of, "", len(seats) + len(offices),
            "Today's holder of each seat and office: names, party and seat only. The roster carries no Treasurer, Commissioner of "
            "Insurance, State Board of Education member or judge. A candidate is marked as the sitting member only when the name "
            "fits the holder of that seat and no other person in the race fits.")]
    if has_list:
        src.append((SRC_GENERAL, STATE, "official candidate list", "Kansas Secretary of State, Elections Division",
                    f"Candidate List, {meta['election']} (the Candidate List page with \"{ELECTION}\" chosen, saved in a browser on "
                    f"{meta['saved']})", fed.LIST_PAGE, "", meta["read"], meta["sha256"], len(meta["rows"]),
                    "The site answers scripts on this page with 403 (CloudFront), so the page was saved in a browser. Office, district, "
                    "division, party and the candidate's name read (and status and ballot order if the list carries them); the address, "
                    "phone, e-mail and web columns are never read. " + ("A ballot order is stored as the list prints it." if any(
                        g["order"] for g in general) else "The list prints no ballot order, so none is stored.")
                    + f" Withdrawn or removed, left off: {len(gone)}."))

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-KS-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'KS'")
        con.execute("DELETE FROM sl_sources WHERE state = 'KS'")
        con.execute("DELETE FROM sl_places WHERE source_id LIKE 'ks-%'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # the report: counts only
    by = Counter(bucket(i) for i in races.values())
    gen_by = Counter(bucket(races[g["race"]]) for g in general)
    inc_by = Counter(bucket(races[rid]) for rid in sitting)
    sboe = sorted(kinds["SBOE"])
    say(f"    Kansas (state races): {by['state_house']} House seats, {by['state_senate']} Senate seats (vacancies: {senate_up}), "
        f"{by['statewide'] - len(sboe)} statewide offices, {len(sboe)} State Board of Education seats ({sboe}), {by['court']} partisan "
        f"judge seats; " + (f"{n_general} candidates on the November ballot (House {gen_by['state_house']}, Senate {gen_by['state_senate']}, "
                            f"statewide {gen_by['statewide']}, courts {gen_by['court']}; {len(gone)} withdrawn left off)" if has_list
                            else f"no November list yet (the Candidate List page answers scripts with 403: save it with \"{ELECTION}\" "
                                 f"chosen into {list_folder})")
        + f"; sitting member in the race: House {inc_by['state_house']}, Senate {inc_by['state_senate']}, statewide {inc_by['statewide']}; "
        f"primary fields: House {fields['state_house']}, Senate {fields['state_senate']}, statewide {fields['statewide']}, courts "
        f"{fields['court']} ({n_primary_rows} rows); {n_state_lines} state candidate lines in the Official Vote Totals, all percents "
        f"checked ({n_fed_lines} federal and {n_q_lines} ballot-question lines passed over)")
    for c in checks:
        say(f"    CHECK Kansas (state races): {c}")
    if empty:
        eb = Counter(bucket(races[rid]) for rid in empty)
        say(f"    CHECK Kansas (state races): no November candidate for {len(empty)} races ({dict(eb)}): {', '.join(empty[:12])}"
            + (" ..." if len(empty) > 12 else ""))
    if upset:
        say(f"    CHECK Kansas (state races): the primary's leader is not on the November list for {len(upset)} party primaries: "
            f"{', '.join(upset[:12])}" + (" ..." if len(upset) > 12 else ""))
    if unpaired:
        say(f"    CHECK Kansas (state races): running mates not paired: {unpaired}")
    if unknown:
        say(f"    CHECK Kansas (state races): offices on the saved list the loader does not read yet: {dict(unknown)}")
    vac = sorted(rid for rid, h in holders.items() if h is None and races[rid]["chamber"])
    if vac:
        say(f"    Kansas (state races): no sitting member in the roster for {', '.join(vac)}")
    return len(cand)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python ballot/state_local_ks.py <database file>")
    load(sys.argv[1])
