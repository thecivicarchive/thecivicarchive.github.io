"""
ballot/state_local_ct.py - Connecticut's state races on the November 3, 2026 ballot: all 36 seats of the State Senate
and all 151 of the House of Representatives (Connecticut elects its whole General Assembly every two years, so no seat
is skipped), and the five statewide offices elected every four years in the Governor's year: Governor and Lieutenant
Governor (one vote for the pair in November), Secretary of the State, Treasurer, Comptroller and Attorney General; with
the party primaries that had a field and their official votes. Written into ballot_local_2026.sqlite (never
ballot_2026.sqlite), Connecticut's rows only. Congress is left to the federal loader (ballot/lists/ct.py), and Judge of
Probate and Registrar of Voters, which share the ballot, are not read.

Sources: the Secretary of the State's own, the same two the federal loader reads for Congress.

  November ballot   "November 3, 2026, State Election, Sample Town Ballots" (portal.ct.gov/sots, town-ballots/
                    2026-november-town-election-ballots): one PDF per town, posted town by town as each town's ballot is
                    approved (19 of 169 towns on 2026-09-30). Every ballot face is one voting district's ballot, headed
                    with its Congressional, Senatorial and Assembly District, and laid out as Connecticut's party-row grid
                    (a numbered column per office, a lettered row per party, each filled cell marked "2A", the party's
                    name at the left of its row). The loader finds the columns headed Governor and Lieutenant Governor,
                    Secretary of the State, Treasurer, Comptroller, Attorney General, State Senator and State
                    Representative, and for every row above "Write-in Votes" reads the party's name and the name printed
                    in each of those cells, using ballot/lists/ct.py's own word and line reading. Controls: every face
                    of every posted town must print the same statewide lines; every face carrying a Senatorial or
                    Assembly District must print the same lines for it; a town's ballot laid out in a way this reading
                    does not follow is set aside and named, never guessed at. A district none of whose towns has a
                    ballot posted yet gets its race row with a note saying so, and no November candidates.
                    The PDFs are kept in ballot_cache/ct/sl_ballots/ (a sample ballot prints names, parties and offices
                    and nothing else; a file the federal loader already holds at the same revision is copied, not
                    downloaded again), with what was read from them in sl_ct_2026_ballots_read.json.
  primaries         the Election Management System's public reporting (ctemspublic.pcctg.net, linked from the Secretary's
                    Election Results page): every 2026 party primary (08/11/2026 Democratic and Republican, and the
                    09/01/2026 Democratic primary for the 58th Assembly District), read from the JSON files its own page
                    loads (Elections.json; election/<id>/Version.json; that version's Lookupdata, stateVotes, townVotes,
                    townStatus and officePrecincts). The candidate records also carry an address field ("AD") and
                    another ("CO"): only the printed name ("NM") and party ("P") are ever read, and the cache
                    (sl_ct_2026_primaries_state.json) keeps only the state contests' names, parties, votes, town figures
                    and statuses. Controls: the towns' figures add up to each candidate's total, no town reports a
                    candidate without a total, and each share the file prints ("TO") matches the one worked out here.
                    A total is stored only when every town that voted in the contest is marked "( Official Results )"
                    and all its precincts are in. Connecticut primary ballots have no write-in line, so a field's total
                    is its candidates' votes. The top vote-getter advanced; where the district's November ballot is
                    posted, the winner must be on that party's line, or the row says so.
  holders           state_ct.sqlite (the Open States roster the state pages use): sitting legislators by chamber and
                    district, and the statewide officials it carries (Governor, Lieutenant Governor, Secretary of the
                    State, Attorney General; not the Treasurer or the Comptroller). Only ids, names, parties, chambers,
                    districts and offices are selected; the roster's contact columns are never read.

What is stored. 2026-CT-GOV, -SOS, -TREAS, -COMP, -AG; 2026-CT-SS<n> (State Senator, Senatorial District n) and
2026-CT-SH<n> (State Representative, Assembly District n). Names are as printed, first name first, the given names and
the family name on two lines of the cell joined. The Governor's cell prints the ticket, "Ned Lamont and Susan
Bysiewicz": the Governor is the candidate's name and the running mate is named in the row's note (as for Maryland).
Parties are as printed ("Democratic Party", "Working Families Party", "Independent Party", "Petitioning Candidate"). A
candidate nominated by several parties (cross-endorsement) is listed once with every line held, in row order, coloured by
the first major party among them, as the federal loader does; ballot order is the order of the candidates' first rows.
Registered write-in candidates are not printed on the ballot and are not stored. A candidate is the incumbent
(incumbent 1, state_member_id) only when the name fits the one sitting member of that chamber and district (or the
statewide officer) and that member fits no other candidate in the race; a sitting legislator running for another office
is given their roster id (not incumbent) when the name fits exactly one legislator of the same party.

Privacy: from every source only office, district, candidate name, party, ballot order and votes are read; nothing else
from any file is printed, logged, cached or stored.

    python -m ballot.state_local_ct <path to a test database> [--refresh]
"""

import datetime as dt
import hashlib
import html as H
import json
import os
import re
import sqlite3
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ballot.common import CACHE, fold, name_parts  # noqa: E402
from ballot.lists import ct as CT  # noqa: E402
from ballot.match import fits  # noqa: E402
from ballot.pdftext import PDF, page_runs  # noqa: E402
from states import net  # noqa: E402

STATE, FIPS = "CT", "09"
GENERAL = "2026-11-03"
ROSTER = os.path.join(HERE, "state_ct.sqlite")
TOWNS = 169
SENATE_SEATS, HOUSE_SEATS, CONGRESS_SEATS = 36, 151, 5
READER = 1                                            # bump when state_columns reads a page differently
INDEX, PRIMS = "sl_ct_2026_ballots_read.json", "sl_ct_2026_primaries_state.json"
FED_INDEX = "ct_2026_ballots_read.json"
SRC_ROSTER = "ct-openstates-roster"
AGENCY = "Connecticut Secretary of the State"

# (key, the column heading as printed, office, office_kind)
OFFICES = (
    ("GOV", re.compile(r"\bGovernor and Lieutenant Governor\b"), "Governor and Lieutenant Governor", "governor"),
    ("SOS", re.compile(r"\bSecretary of the State\b"), "Secretary of the State", "secretary_of_state"),
    ("TREAS", re.compile(r"(?<!Town )\bTreasurer\b"), "Treasurer", "state_treasurer"),
    ("COMP", re.compile(r"\bComptroller\b"), "Comptroller", "comptroller"),
    ("AG", re.compile(r"\bAttorney General\b"), "Attorney General", "attorney_general"),
    ("SS", re.compile(r"\bState Senat(?:or|e)\b"), "State Senator", "state_senate"),      # Canterbury prints "State Senate"
    ("SH", re.compile(r"\bState Representative\b"), "State Representative", "state_house"),
)
OFFICE = {k: (title, kind) for k, _rx, title, kind in OFFICES}
OFFICE["LTG"] = ("Lieutenant Governor", "lieutenant_governor")                 # only if a party primary is held for it
STATEWIDE = ("GOV", "SOS", "TREAS", "COMP", "AG")
ROSTER_OFFICE = {"GOV": "governor", "SOS": "secretary of state", "AG": "attorney general", "LTG": "lt_governor"}
SENATE_HEAD = re.compile(r"\bSenatorial District(?:/[^\d]*?)?\s(\d{1,2})\b")
ASSEMBLY_HEAD = re.compile(r"\bAssembly District(?:/[^\d]*?)?\s(\d{1,3})\b")
HEADS = (("cd", CT.HEADING, "congressional", CONGRESS_SEATS), ("sd", SENATE_HEAD, "senatorial", SENATE_SEATS),
         ("ad", ASSEMBLY_HEAD, "assembly", HOUSE_SEATS))
# the state offices as the Management System names them
PRIMARY_OFFICE = ((re.compile(r"Governor"), "GOV"), (re.compile(r"Lieutenant Governor"), "LTG"),
                  (re.compile(r"Secretary of the State"), "SOS"), (re.compile(r"Treasurer"), "TREAS"),
                  (re.compile(r"Comptroller"), "COMP"), (re.compile(r"Attorney General"), "AG"),
                  (re.compile(r"State Senator (\d{1,2})"), "SS"), (re.compile(r"State Representative (\d{1,3})"), "SH"))
PRIMARY_NAME = re.compile(r"(\d\d)/(\d\d)/2026 -- (.*\bPrimary\b.*)")
CODES = {"Democratic Party": "DEM", "Republican Party": "REP", "Libertarian Party": "LIB", "Green Party": "GRE",
         "Working Families Party": "WFP", "Independent Party": "IND"}
MAJOR = {"Democratic Party": "D", "Republican Party": "R"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL,
  office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0,
  partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT,
  party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL,
  outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT,
  fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT,
  PRIMARY KEY (kind, id));
"""

GOV_NOTE = ("Connecticut elects the Governor and Lieutenant Governor together in November: one vote for the pair, both names "
            "printed in one box on each party's line. Each party nominates the two separately, by convention or primary.")
NO_ROSTER = "The Open States roster this site uses does not carry the {office}, so today's holder is not shown."


class Unreadable(Exception):
    """A town's ballot laid out in a way this loader does not read: that town is set aside and named, never guessed at."""


# ------------------------------------------------------------------------------------------------ fetching

def fetch(url, accept="*/*", say=print):
    """One request, asked at most twice more on a refusal or a server error; a bot check stops the loader."""
    for attempt in range(3):
        try:
            raw = net.get(url, accept=accept)
        except HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == 2:
                raise
            say(f"      {url.rsplit('/', 1)[-1][:60]}: HTTP {e.code}; asking again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))
            continue
        head = raw[:4000].lower()
        if b"captcha" in head or b"challenge-platform" in head or b"incapsula" in head or b"cf-chl" in head:
            raise SystemExit(f"Connecticut (state races): {url} answered with a bot check; it was not worked around. A person in a "
                             "browser would have to fetch it.")
        return raw


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""


def mtime(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""


# ------------------------------------------------------------------------------------------------ the sample ballots

def state_columns(path, town):
    """[{"pages": [n], "cd": d, "sd": d, "ad": d, "cols": {key: [[row, party, name]]}}] for a town's ballot, identical
    faces merged. Only the seven state offices' cells and the party names are read."""
    pdf = PDF(open(path, "rb").read())
    found = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        ws = CT.words(page_runs(pdf, page, res))
        lines = CT.text_lines(ws)
        top_row = next((y for y, t in lines if len(t.split()) >= 2 and t.split() == [str(k) for k in range(1, len(t.split()) + 1)]), None)
        if top_row is None:
            continue                                  # not a ballot face (instructions, a blank back)
        where = f"{town}'s ballot, page {n}"
        face = {"pages": [n]}
        for key, rx, words_, top in HEADS:
            got = {int(m.group(1)) for _y, t in lines for m in [rx.search(t)] if m}
            if len(got) != 1 or not 1 <= min(got) <= top:
                raise Unreadable(f"{where} does not name one {words_} district ({sorted(got)})")
            face[key] = min(got)
        labels = [(int(m.group(1)), m.group(2), w) for w in ws for m in [CT.LABEL.match(w["t"])] if m and w["y"] < top_row - 10]
        cols, rows = {}, {}
        for c, r, w in labels:
            cols.setdefault(c, []).append(w["x0"])
            rows.setdefault(r, []).append(w["y"])
        if sorted(cols) != list(range(1, len(cols) + 1)) or len(cols) < 2:
            raise Unreadable(f"{where}: the office columns are not numbered 1 to N ({sorted(cols)})")
        if any(max(v) - min(v) > 4 for v in cols.values()) or any(max(v) - min(v) > 2 for v in rows.values()):
            raise Unreadable(f"{where}: the cell marks do not line up in columns and rows")
        centre = {c: sum(xs) / len(xs) + 5 for c, xs in cols.items()}
        order = sorted(rows, key=lambda r: -sum(rows[r]) / len(rows[r]))
        if order != sorted(order):
            raise Unreadable(f"{where}: the party rows are not lettered from the top ({order})")
        rowy = {r: sum(v) / len(v) for r, v in rows.items()}
        cs = sorted(centre)
        band = {}
        for i, c in enumerate(cs):
            lo = (centre[cs[i - 1]] + centre[c]) / 2 if i else centre[c] - (centre[cs[1]] - centre[c]) / 2
            hi = (centre[cs[i + 1]] + centre[c]) / 2 if i + 1 < len(cs) else centre[c] + (centre[c] - centre[cs[i - 1]]) / 2
            band[c] = (lo, hi)
        first = rowy[order[0]]
        heads = {c: " ".join(t for _y, t in CT.text_lines([w for w in ws if lo <= w["xc"] < hi and first + 4 < w["y"] < top_row + 4]))
                 for c, (lo, hi) in band.items()}
        mine = {}
        for key, rx, title, _kind in OFFICES:
            hit = [c for c, h in heads.items() if rx.search(h)]
            if len(hit) != 1:
                raise Unreadable(f"{where}: {len(hit)} columns headed {title}")
            mine[key] = hit[0]
        if len(set(mine.values())) != len(mine):
            raise Unreadable(f"{where}: two offices read from one column")
        party_edge = band[1][0] + 1
        filled = {(cc, r) for cc, r, _w in labels}
        got, write_in_row = {key: [] for key in mine}, False
        for k, r in enumerate(order):
            below = rowy[order[k + 1]] + 3 if k + 1 < len(order) else rowy[r] - 60
            party = CT.english(" ".join(t for _y, t in CT.text_lines([w for w in ws if w["x1"] <= party_edge and below < w["y"] <= rowy[r] + 3])))
            if party.startswith("Write-in"):
                write_in_row = True
                break
            for key, c in mine.items():
                lo, hi = band[c]
                cell = [t for _y, t in CT.text_lines([w for w in ws if lo <= w["xc"] < hi and below < w["y"] < rowy[r] - 2])]
                if (c, r) not in filled:
                    if cell:
                        raise Unreadable(f"{where}: words in the {OFFICE[key][0]} column of row {r} with no cell mark")
                    continue
                if not party or not cell:
                    raise Unreadable(f"{where}: cell {c}{r} has no {'party' if not party else 'name'}")
                name = re.sub(r"\s+", " ", " ".join(cell)).strip()
                if name == name.upper():
                    raise Unreadable(f"{where} prints a name in capitals, which this loader does not yet show")
                if re.match(r"(?i)and\b", name) or re.search(r"(?i)\band$", name):
                    raise Unreadable(f"{where}: cell {c}{r} begins or ends with 'and' (a ticket split across columns)")
                if key == "GOV" and not re.search(r"\sand\s", name):
                    raise Unreadable(f"{where}: cell {c}{r} does not print a Governor and a Lieutenant Governor")
                got[key].append([r, party, name])
        if not write_in_row:
            raise Unreadable(f"{where}: no Write-in Votes row found")
        face["cols"] = got
        for f in found:
            if all(f[x] == face[x] for x in ("cd", "sd", "ad", "cols")):
                f["pages"].append(n)
                break
        else:
            found.append(face)
    if not found:
        raise Unreadable(f"no ballot faces read in {town}'s sample ballot")
    return found


def ballots(folder, say, refresh=False):
    """Every posted town's sample ballot, kept once per revision and read once: ({file: {...}}, index path, listing date)."""
    index_path = os.path.join(folder, INDEX)
    old = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else {}
    if old and not refresh and time.time() - os.path.getmtime(index_path) < 86400 and all(v.get("reader") == READER for v in old.values()):
        return old, index_path
    page = fetch(CT.BALLOT_PAGE, "text/html", say).decode("utf-8", "replace")
    links = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href = H.unescape(m.group(1))
        hit = CT.BALLOT_LINK.search(href)
        if hit:
            town = re.sub(r"<[^>]+>|\s+", " ", H.unescape(m.group(2))).strip()
            rev = re.search(r"[?&]rev=([0-9A-Fa-f]+)", href)
            links[hit.group(1).lower()] = (town, urljoin(CT.BALLOT_PAGE, href), rev.group(1) if rev else "")
    if not links:
        raise SystemExit("Connecticut (state races): the Sample Town Ballots page links no town ballots")
    mine_dir, fed_dir = os.path.join(folder, "sl_ballots"), os.path.join(folder, "ballots")
    os.makedirs(mine_dir, exist_ok=True)
    fed_path = os.path.join(folder, FED_INDEX)
    fed = json.load(open(fed_path, encoding="utf-8")) if os.path.exists(fed_path) else {}

    def read(path, town):
        try:
            return {"faces": state_columns(path, town), "unreadable": None}
        except Unreadable as e:
            return {"faces": [], "unreadable": str(e)}

    index, fetched, copied = {}, 0, 0
    for fname, (town, url, rev) in sorted(links.items()):
        path = os.path.join(mine_dir, fname)
        prev = old.get(fname)
        if prev and prev.get("rev") == rev and os.path.exists(path) and sha(path) == prev.get("sha256"):
            if prev.get("reader") != READER:                  # the reading changed: read the kept file again, nothing downloaded
                prev = dict(prev, reader=READER, **read(path, town))
            index[fname] = prev
            continue
        theirs, their_path = fed.get(fname), os.path.join(fed_dir, fname)
        if theirs and theirs.get("rev") == rev and os.path.exists(their_path) and sha(their_path) == theirs.get("sha256"):
            raw, when = open(their_path, "rb").read(), theirs.get("fetched") or mtime(their_path)
            copied += 1
        else:
            raw, when = fetch(url, "application/pdf", say), dt.date.today().isoformat()
            fetched += 1
            time.sleep(1.0)
        entry = {"town": town, "url": url.split("?")[0], "rev": rev, "sha256": hashlib.sha256(raw).hexdigest(), "fetched": when, "reader": READER}
        if not raw.startswith(b"%PDF"):
            index[fname] = dict(entry, faces=[], unreadable=f"{town}'s sample ballot did not come back as a PDF")
            continue
        with open(path, "wb") as fh:
            fh.write(raw)
        index[fname] = dict(entry, **read(path, town))
    for gone in sorted(set(os.listdir(mine_dir)) - set(links)):
        if gone.lower().endswith(".pdf"):
            os.remove(os.path.join(mine_dir, gone))          # a ballot the Secretary took down: never read again
    json.dump(index, open(index_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      sample ballots: {len(index)} of {TOWNS} towns posted; {fetched} downloaded, {copied} copied from the federal loader's cache")
    return index, index_path


# ------------------------------------------------------------------------------------------------ the primaries

def ints(text):
    t = str(text or "").replace(",", "").strip()
    return int(t) if t else 0


def official_contest(c):
    """Every town that voted in the contest has its return marked official, and every precinct is in."""
    m = re.fullmatch(r"(\d+) of (\d+) \(100%\)", c["precincts"])
    return bool(m) and m.group(1) == m.group(2) and bool(c["status"]) and all(s == CT.OFFICIAL for s in c["status"].values())


def office_key(title):
    """('SS', '13') for 'State Senator 13', ('GOV', '') for 'Governor'; (None, None) for an office not read here."""
    t = re.sub(r"\s+", " ", title).strip()
    for rx, key in PRIMARY_OFFICE:
        m = rx.fullmatch(t)
        if m:
            return key, (str(int(m.group(1))) if m.groups() else "")
    return None, None


def primaries(say):
    """The state contests of every 2026 party primary: names, parties, votes, town figures and statuses only."""
    def get(path):
        return json.loads(fetch(CT.CTEMS_DATA + path, "application/json", say).decode("utf-8-sig"))

    out = []
    for e in get("Elections.json"):
        m = PRIMARY_NAME.fullmatch(e.get("Name", "").strip())
        if not m or re.search(r"Presidential|Municipal|Town Committee", m.group(3), re.I):
            continue
        eid = e["ID"]
        version = int(get(f"election/{eid}/Version.json")["Version"])
        base = f"election/{eid}/{version}/"
        look = get(base + "Lookupdata.json")
        el = look["election"]
        if el.get("ET") != "P":
            continue
        party = el["P"]
        offices, skipped = {}, []
        for group in look["officeList"]:
            for oid, o in group.items():
                key, district = office_key(o["NM"])
                if key is None:
                    skipped.append(re.sub(r"\s+", " ", o["NM"]).strip())
                    continue
                if district and str(o.get("D", "")).strip() != district:
                    raise SystemExit(f"Connecticut: the Management System files {o['NM']!r} under district {o.get('D')!r}")
                offices[oid] = (key, district, re.sub(r"\s+", " ", o["NM"]).strip())
        contests = {}
        if offices:
            state = get(base + "stateVotes_Electiondata.json")
            towns = get(base + "townVotes_Electiondata.json")
            status = get(base + "townStatus_Electiondata.json")
            precincts = get(base + "officePrecincts_Electiondata.json")
            parties = {pid: p["NM"] for pid, p in look["partyIds"].items()}
            for oid, (key, district, title) in offices.items():
                cands = {}
                for cell in state.get(oid, []):
                    for cid, v in cell.items():
                        rec = look["candidateIds"][cid]                   # only the printed name and the party are read
                        cands[cid] = {"name": re.sub(r"\s+", " ", rec["NM"]).strip(), "party": parties.get(rec["P"], rec["P"]),
                                      "votes": ints(v["V"]), "share": str(v.get("TO", "")).strip()}
                by_town = {tid: {cid: ints(v["V"]) for cell in offs[oid] for cid, v in cell.items()} for tid, offs in towns.items() if oid in offs}
                contests[oid] = {"key": key, "district": district, "office": title, "candidates": cands, "towns": by_town,
                                 "precincts": precincts.get(oid, ""), "status": {tid: status.get(tid, {}).get("TS", "") for tid in by_town},
                                 "town_names": {tid: look["townIds"].get(tid, tid) for tid in by_town}}
        out.append({"id": eid, "name": e["Name"].strip(), "date": f"2026-{m.group(1)}-{m.group(2)}", "party": party, "version": version,
                    "contests": contests, "skipped": sorted(skipped)})
        time.sleep(1.0)
    if not out:
        raise SystemExit("Connecticut: the Election Management System lists no 2026 party primary")
    say(f"      Election Management System: {len(out)} 2026 primaries read ({sum(len(e['contests']) for e in out)} state contests)")
    return {"fetched": dt.date.today().isoformat(), "elections": out}


def kept_primaries(folder, say, refresh=False):
    path = os.path.join(folder, PRIMS)
    prim = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
    age = time.time() - os.path.getmtime(path) if prim else None
    settled = prim and all(official_contest(c) for e in prim["elections"] for c in e["contests"].values())
    if refresh or not prim or age > 30 * 86400 or (not settled and age > 86400):     # returns not yet official are asked for daily
        try:
            prim = primaries(say)
        except (HTTPError, OSError) as e:
            if not prim:
                raise
            say(f"      could not refresh the primaries ({e}); using the copy read earlier")
            return prim, path
        json.dump(prim, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return prim, path


# ------------------------------------------------------------------------------------------------ who holds each seat

def roster(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legs = [dict(zip(("id", "first", "last", "full", "other", "code", "party", "chamber", "district"), r)) for r in con.execute(
        "SELECT bioguide_id, first_name, last_name, official_full, other_names, party, party_name, chamber, district FROM legislators "
        "WHERE is_current = 1")]
    offs = {r[1]: dict(zip(("id", "office", "full", "first", "last", "code", "party"), r)) for r in con.execute(
        "SELECT bioguide_id, office, official_full, first_name, last_name, party, party_name FROM officials")}
    con.close()
    return legs, offs


def person_fits(name, p):
    """A printed name fits a roster person: same family name and a given name that fits (their roster name or a full
    form the roster keeps)."""
    cand = name_parts(name)
    forms = [(fold(p["first"] or "").split(), " ".join(fold(p["last"] or "").split()))]
    forms += [name_parts(o.strip()) for o in (p.get("other") or "").split(";") if o.strip() and "," not in o and "." not in o]
    return any(f[1] and fits(cand, f) for f in forms)


def names_fit(a, b):
    return person_fits(a, {"first": " ".join(name_parts(b)[0]), "last": name_parts(b)[1]})


def chamber_words(p):
    return f"{'State Senate, Senatorial' if p['chamber'] == 'Senate' else 'House of Representatives, Assembly'} District {p['district']}"


def line_code(lines):
    """The colour of a candidate on several lines: the first major party among them, else the first line's."""
    first = next((p for p in lines if p in MAJOR), lines[0])
    return CT.code(first)


# ------------------------------------------------------------------------------------------------ the loader

def load(db_path, say=print, cache=CACHE, roster_db=ROSTER, refresh=False):
    net.patient_lookups()
    folder = os.path.join(cache, "ct")
    os.makedirs(folder, exist_ok=True)
    index, index_path = ballots(folder, say, refresh)
    prim, ppath = kept_primaries(folder, say, refresh)
    legs, offs = roster(roster_db)
    listed_on = mtime(index_path)
    report = []

    # the seats: every one on the ballot, by law and by the roster
    senate = sorted({int(p["district"]) for p in legs if p["chamber"] == "Senate"})
    house = sorted({int(p["district"]) for p in legs if p["chamber"] == "House"})
    if senate != list(range(1, SENATE_SEATS + 1)) or house != list(range(1, HOUSE_SEATS + 1)):
        report.append(f"the roster's seats are not Senate 1-{SENATE_SEATS} and House 1-{HOUSE_SEATS} "
                      f"({len(senate)} Senate, {len(house)} House districts with a sitting member)")

    # ---- the November ballot: each office's party lines, which every face carrying it must print alike
    unreadable = sorted((rec["town"], rec["unreadable"]) for rec in index.values() if rec.get("unreadable"))
    seen = {}
    for fname, rec in sorted(index.items()):
        for face in rec["faces"]:
            for key, lines in face["cols"].items():
                d = "" if key in STATEWIDE else str(face["sd"] if key == "SS" else face["ad"])
                seen.setdefault((key, d), []).append((fname, face["pages"], [(p, n) for _r, p, n in lines]))
    ballot = {}                                                   # (key, district) -> {"src": fname, "pages", "checked", "people"}
    spellings = {}                                                # (key, district) -> ["Coventry, Harwinton print Jennifer S Tooker"]
    for (key, d), got in sorted(seen.items()):
        (fname, pages, lines), others = got[0], got[1:]
        variants = {}
        for f2, p2, l2 in others:
            if [(p, " ".join(fold(n).split())) for p, n in l2] != [(p, " ".join(fold(n).split())) for p, n in lines]:
                raise SystemExit(f"Connecticut: {OFFICE[key][0]}{' ' + d if d else ''}: {index[f2]['town']}'s ballot (pages {p2}) does not "
                                 f"print the same lines as {index[fname]['town']}'s (pages {pages})")
            for (_p, n1), (_p2, n2) in zip(lines, l2):
                if n1 != n2:                              # the same letters, other punctuation ("Jennifer S Tooker")
                    variants.setdefault((n1, n2), set()).add(index[f2]["town"])
        for (n1, n2), towns in sorted(variants.items()):
            report.append(f"{OFFICE[key][0]}{' ' + d if d else ''}: {', '.join(sorted(towns))} print{'s' if len(towns) == 1 else ''} "
                          f"{n2!r} where {index[fname]['town']} prints {n1!r} (kept as {index[fname]['town']} prints it)")
            spellings.setdefault((key, d), []).append(f"{', '.join(sorted(towns))} print{'s' if len(towns) == 1 else ''} {n2}")
        people, order, on_line = {}, [], {}
        for p, n in lines:
            if key == "GOV":
                parts = re.split(r"\s+and\s+", n)
                if len(parts) != 2:
                    raise SystemExit(f"Connecticut: a Governor's box that is not one Governor and one Lieutenant Governor ({n!r})")
                gov, mate = parts[0].strip(), parts[1].strip()
            else:
                gov, mate = n, None
            k = fold(gov)
            if k not in people:
                people[k] = {"name": gov, "mate": mate, "lines": []}
                order.append(k)
            elif people[k]["name"] != gov or people[k]["mate"] != mate:
                raise SystemExit(f"Connecticut: {OFFICE[key][0]}{' ' + d if d else ''}: one candidate printed two ways ({people[k]['name']!r} "
                                 f"with {people[k]['mate']!r}, {gov!r} with {mate!r})")
            if p in people[k]["lines"] or p in on_line:
                raise SystemExit(f"Connecticut: {OFFICE[key][0]}{' ' + d if d else ''}: the {p} line is printed twice")
            people[k]["lines"].append(p)
            on_line[p] = gov
        towns_checked = sorted({index[f2]["town"] for f2, _p, _l in others} - {index[fname]["town"]})
        ballot[(key, d)] = {"src": fname, "pages": pages, "checked": towns_checked, "people": [people[k] for k in order], "on_line": on_line}

    # ---- the races
    races, cands = {}, []

    def race_id(key, d):
        return f"2026-{STATE}-{key}{d}" if key in ("SS", "SH") else f"2026-{STATE}-{key}"

    def holder_of(key, d):
        if key in ("SS", "SH"):
            hs = [p for p in legs if p["chamber"] == ("Senate" if key == "SS" else "House") and str(p["district"]) == d]
            return hs[0] if len(hs) == 1 else None
        return offs.get(ROSTER_OFFICE.get(key, ""))

    def add_race(key, d):
        rid = race_id(key, d)
        if rid in races:
            return rid
        title, kind = OFFICE[key]
        h = holder_of(key, d)
        note = []
        if key in ("SS", "SH"):
            jur, jid, level = (f"Senatorial District {d}" if key == "SS" else f"Assembly District {d}"), f"{STATE}-{d}", "legislature"
            if h is None:
                note.append("The roster shows no sitting member for this seat.")
                report.append(f"{rid}: no single sitting member in the roster")
        else:
            jur, jid, level = "Connecticut", FIPS, "statewide"
            if key == "GOV":
                note.append(GOV_NOTE)
            if key == "LTG":
                note.append("Nominated in a party primary of its own; in November the Lieutenant Governor is elected jointly with the "
                            "Governor, on the tickets listed under 2026-CT-GOV.")
            if h is None and key not in ROSTER_OFFICE:
                note.append(NO_ROSTER.format(office=title))
        if (key, d) not in ballot and key != "LTG":
            note.append(f"No town in this district has had its November ballot posted by the Secretary of the State yet "
                        f"({len(index)} of {TOWNS} towns posted when the list was read, {listed_on}); the candidates appear once one is.")
        races[rid] = [rid, STATE, level, kind, title, jur, jid, None, d or None, None, 0, 1, h["id"] if h else None,
                      h["full"] if h else None, h["party"] if h else None, GENERAL, " ".join(note) or None]
        return rid

    for key in STATEWIDE:
        add_race(key, "")
    for d in range(1, SENATE_SEATS + 1):
        add_race("SS", str(d))
    for d in range(1, HOUSE_SEATS + 1):
        add_race("SH", str(d))
    for (key, d) in ballot:
        if race_id(key, d) not in races:
            raise SystemExit(f"Connecticut: a ballot names {OFFICE[key][0]} {d}, which is not a seat")

    def identify(key, d, name, pcode, pool_names):
        """(incumbent, state_member_id, note) for one printed name; pool_names are the other names in the same election."""
        h = holder_of(key, d)
        if h is not None and person_fits(name, h):
            if sum(1 for n in pool_names if person_fits(n, h)) == 1:
                return 1, h["id"], None
            report.append(f"{race_id(key, d)}: the holder {h['full']} fits more than one name; no incumbent marked")
            return 0, None, None
        pool = [p for p in legs if person_fits(name, p) and p["code"] == pcode]
        if len(pool) == 1 and not (h is not None and pool[0]["id"] == h["id"]):
            return 0, pool[0]["id"], f"Serves today in the {chamber_words(pool[0])}."
        return 0, None, None

    def src_ballot(fname):
        return f"ct-sots-2026-sl-ballot-{CT.slug(fname)}"

    for (key, d), b in sorted(ballot.items(), key=lambda kv: (["GOV", "SOS", "TREAS", "COMP", "AG", "SS", "SH"].index(kv[0][0]), int(kv[0][1] or 0))):
        rid = race_id(key, d)
        names = [x["name"] for x in b["people"]]
        for k, x in enumerate(b["people"], start=1):
            held = x["lines"]
            code = line_code(held)
            major = next((MAJOR[p] for p in held if p in MAJOR), CT.code(held[0]))
            inc, mid, n2 = identify(key, d, x["name"], major, names)
            note = []
            if x["mate"]:
                note.append(f"On one ticket with {x['mate']} for Lieutenant Governor, as the ballot prints it.")
            if len(held) > 1:
                note.append(f"On the ballot on {len(held)} party lines: {', '.join(held)}.")
            if n2:
                note.append(n2)
            cands.append([rid, "general", GENERAL, x["name"], ", ".join(held), code, k, inc, 0, None, None, None, mid, src_ballot(b["src"]),
                          " ".join(note) or None])

    # ---- the primaries: fields of two or more, official votes only
    fields, unofficial, not_on, unopposed, skipped = 0, [], [], 0, set()
    for e in prim["elections"]:
        skipped |= set(e.get("skipped", []))
        party = e["party"]
        pcode = CODES.get(party)
        if not pcode:
            raise SystemExit(f"Connecticut: a primary of a party that is not read ({party!r})")
        mmdd = e["date"][5:].replace("-", "")
        src = f"ct-sots-2026-sl-primary-{pcode.lower()}-{mmdd}"
        e["_src"] = src
        for oid, c in e["contests"].items():
            key, d, cs = c["key"], c["district"], c["candidates"]
            where = f"{c['office']} ({e['name']})"
            for cid, v in cs.items():
                if v["party"] != party:
                    raise SystemExit(f"Connecticut: {v['name']} is filed under {v['party']} in the {party} primary")
                summed = sum(t.get(cid, 0) for t in c["towns"].values())
                if summed != v["votes"]:
                    raise SystemExit(f"Connecticut: {v['name']}, {where}: the towns add up to {summed}, the total is {v['votes']}")
            if {cid for t in c["towns"].values() for cid in t} - set(cs):
                raise SystemExit(f"Connecticut: {where} has town figures for candidates with no total")
            total = sum(v["votes"] for v in cs.values())
            for v in cs.values():
                m = re.fullmatch(r"([\d.]+)%", v.get("share", ""))
                if total and m and abs(float(m.group(1)) - 100 * v["votes"] / total) > 0.01:
                    raise SystemExit(f"Connecticut: {v['name']}, {where}: the file prints {v['share']}, the votes give "
                                     f"{100 * v['votes'] / total:.2f}%")
            if len(cs) < 2:
                unopposed += 1
                continue
            if key in ("SS", "SH") and not 1 <= int(d) <= (SENATE_SEATS if key == "SS" else HOUSE_SEATS):
                raise SystemExit(f"Connecticut: {where} names a district that is not a seat")
            rid = add_race(key, d)
            fields += 1
            if e["date"] != CT.PRIMARY:                    # the 58th Assembly District's Democrats: a special primary on September 1
                day = dt.date.fromisoformat(e["date"])
                extra = f"The {party}'s nomination was decided in a separate primary on {day.strftime('%B')} {day.day}, {day.year}."
                races[rid][16] = " ".join(x for x in (races[rid][16], extra) if x)
            official = official_contest(c)
            if not official:
                unofficial.append(where)
            ranked = sorted(cs.values(), key=lambda v: (-v["votes"], v["name"]))
            if official and ranked[0]["votes"] == ranked[1]["votes"]:
                raise SystemExit(f"Connecticut: {where} is tied at the top")
            b = ballot.get((key, d)) if key != "LTG" else None
            listed = b["on_line"].get(party) if b else None
            names = [v["name"] for v in ranked]
            for v in ranked:
                if official:
                    won = v is ranked[0]
                else:
                    won = None if listed is None else names_fit(v["name"], listed)
                note = []
                if won and b and (listed is None or not names_fit(v["name"], listed)):
                    note.append("Won the primary but is not on the November ballot." if listed is None else
                                f"Won the primary; the November ballot prints {listed} on the {party} line instead.")
                    not_on.append(f"{v['name']} ({rid}, {party})")
                elif won and key != "LTG" and not b:
                    note.append("Won the primary; no November ballot for this district has been posted yet to show the party's line.")
                if not official:
                    note.append("The primary's official returns are not all in, so no votes are shown.")
                major = MAJOR.get(party, CT.code(party))
                inc, mid, n2 = identify(key, d, v["name"], major, names)
                if n2:
                    note.append(n2)
                cands.append([rid, f"primary-{pcode}", e["date"], v["name"], party, CT.code(party), None, inc, 0,
                              v["votes"] if official else None, round(100 * v["votes"] / total, 1) if official and total else None,
                              None if won is None else ("advanced" if won else "lost"), mid, src, " ".join(note) or None])

    seen_keys = set()
    for c in cands:
        k = (c[0], c[1], c[3])
        if k in seen_keys:
            raise SystemExit(f"Connecticut: {c[3]} is listed twice in {c[0]} {c[1]}")
        seen_keys.add(k)

    # ---- write
    general = [c for c in cands if c[1] == "general"]
    primary_rows = [c for c in cands if c[1] != "general"]
    used = {}
    for (key, d), b in ballot.items():
        used.setdefault(b["src"], []).append((key, d))
    sources = []
    for fname, keys in sorted(used.items()):
        rec = index[fname]
        path = os.path.join(folder, "sl_ballots", fname)
        state_part = [OFFICE[k][0] for k, _d in keys if k in STATEWIDE]
        seats = [f"{'Senatorial' if k == 'SS' else 'Assembly'} District {d}" for k, d in sorted(keys, key=lambda x: (x[0], int(x[1] or 0))) if d]
        checked = sorted({t for kd in keys for t in ballot[kd]["checked"]})
        rows_n = sum(1 for c in general if c[13] == src_ballot(fname))
        variants = [s for kd in keys for s in spellings.get(kd, [])]
        sources.append((src_ballot(fname), STATE, "official sample ballot", AGENCY,
                        f"November 3, 2026, State Election, Sample Town Ballots: {rec['town']}", rec["url"], "", rec.get("fetched") or mtime(path),
                        rec["sha256"], rows_n,
                        f"Listed on {CT.BALLOT_PAGE}. Read here for: {', '.join(state_part + seats)}. The party-row ballot is read by its cell "
                        f"marks, column by office heading; a sample ballot prints names, parties and offices only. "
                        + (f"Checked against the same columns on the ballots of {', '.join(checked)}, which agree. " if checked else
                           "No other posted town's ballot carries these districts yet. ")
                        + (f"Only the punctuation differs on some ({'; '.join(variants)}); names are kept as this town prints them. " if variants else "")
                        + "Registered write-in candidates are not printed on the ballot and are not stored."))
    for e in prim["elections"]:
        if not e["contests"]:
            continue
        n = sum(1 for c in primary_rows if c[13] == e["_src"])
        towns = len({t for c in e["contests"].values() for t in c["towns"]})
        sources.append((e["_src"], STATE, "official results", AGENCY,
                        f"Election Management System public reporting: {e['name']}, state offices", f"{CT.CTEMS}#/home",
                        e["date"], prim["fetched"], sha(ppath), n,
                        f"Data: {CT.CTEMS_DATA}election/{e['id']}/{e['version']}/ (data version {e['version']}). Contests read: "
                        f"{', '.join(sorted(c['office'] for c in e['contests'].values()))}. Each candidate's total (stateVotes) is checked "
                        f"against the sum of the town returns (townVotes, {towns} towns) and against the share the file prints; a total is "
                        f"stored only when every town is marked \"( Official Results )\" and all precincts are in. Only the printed name and "
                        f"party of each candidate record are read (it also carries an address field, never read). Connecticut primary "
                        f"ballots have no write-in line; a contest with one candidate is not stored as a field. The SHA-256 is of the "
                        f"loader's own JSON of the figures read."))
    sources.append((SRC_ROSTER, STATE, "roster", "Open States people project (CC0), as loaded into state_ct.sqlite",
                    "Sitting legislators and statewide officials", "https://github.com/openstates/people", "", mtime(roster_db), sha(roster_db),
                    len(legs) + len(offs),
                    "Who holds each seat today, by chamber and district; the roster carries the Governor, Lieutenant Governor, Secretary of "
                    "the State and Attorney General, not the Treasurer or the Comptroller. Only ids, names, parties, chambers, districts "
                    "and offices are read. Also the source of the district places (36 Senatorial, 151 Assembly)."))
    places = [("senate", f"{STATE}-{d}", f"Senatorial District {d}", None, SRC_ROSTER) for d in range(1, SENATE_SEATS + 1)] + \
             [("house", f"{STATE}-{d}", f"Assembly District {d}", None, SRC_ROSTER) for d in range(1, HOUSE_SEATS + 1)]

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?)", (STATE,))
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE ?", (f"2026-{STATE}-%",))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_places WHERE source_id LIKE ?", (STATE.lower() + "-%",))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(races.values()))
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", sources)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", places)
    con.close()

    # ---- say what was done, and what is still missing
    def count(kind, rows):
        return sum(1 for c in rows if races[c[0]][3] == kind)
    have = {k: sum(1 for (kk, _d) in ballot if kk == k) for k in ("SS", "SH")}
    missing_sw = [OFFICE[k][0] for k in STATEWIDE if (k, "") not in ballot]
    say(f"    Connecticut: {len(races)} races ({SENATE_SEATS} Senate, {HOUSE_SEATS} House, {len(races) - SENATE_SEATS - HOUSE_SEATS} statewide); "
        f"November candidates from the sample ballots of {len(index) - len(unreadable)} of {TOWNS} towns: statewide "
        f"{sum(1 for c in general if races[c[0]][2] == 'statewide')} ({5 - len(missing_sw)} of 5 offices), Senate {count('state_senate', general)} "
        f"({have['SS']} of {SENATE_SEATS} districts), House {count('state_house', general)} ({have['SH']} of {HOUSE_SEATS} districts); "
        f"{sum(1 for c in general if c[14] and 'party lines' in c[14])} on more than one party line; {fields} primary fields "
        f"({len(primary_rows)} rows, {unopposed} one-candidate contests not stored), votes from the official returns"
        + (f"; not yet official: {', '.join(unofficial)}" if unofficial else "")
        + (f"; primary winners not on the November ballot: {', '.join(not_on)}" if not_on else ""))
    if skipped:
        say(f"      primary contests not read here (other loaders or not loaded): {', '.join(sorted(skipped))}")
    for c in cands:
        if c[12]:
            say(f"      matched: {c[0]} {c[1]}: {c[3]} -> {c[12]}{' (holds this seat)' if c[7] else ''}")
    for town, why in unreadable:
        say(f"      check: set aside, {why}")
    if missing_sw:
        say(f"      check: no posted ballot read for {', '.join(missing_sw)}")
    for k, n in (("SS", SENATE_SEATS), ("SH", HOUSE_SEATS)):
        gap = [str(d) for d in range(1, n + 1) if (k, str(d)) not in ballot]
        if gap:
            say(f"      check: {len(gap)} {'Senatorial' if k == 'SS' else 'Assembly'} districts have no posted town ballot yet: {', '.join(gap)}")
    for line in report:
        say(f"      check: {line}")
    return len(general)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: python -m ballot.state_local_ct <database> [--refresh]")
    load(args[0], refresh="--refresh" in sys.argv)
