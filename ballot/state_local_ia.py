"""
ballot/state_local_ia.py - Iowa's state races on the November 3, 2026 ballot: the Iowa Senate seats up this year (the
25 odd-numbered districts), all 100 Iowa House seats, and the statewide offices (Governor with Lieutenant Governor,
Secretary of State, Auditor of State, Treasurer of State, Secretary of Agriculture, Attorney General), with the June 2
party primaries that chose the nominees. Written into ballot_local_2026.sqlite (never ballot_2026.sqlite).

Sources, all the Iowa Secretary of State's own, the same three files the federal loader (ballot/lists/ia.py) reads:

  Candidate List, November 3, 2026 General Election (PDF, linked as "candidate list" from sos.iowa.gov/general-election)
  Candidate List, June 2, 2026 Primary Election (PDF, the same layout, linked from sos.iowa.gov/primary-election)
  Election Canvass Summary, 2026 Primary Election (PDF, "Official Canvass by County" on the Election Results page)

The two candidate lists carry each candidate's address, phone, e-mail and filing date beside the office, party and
ballot name. Only the first three columns are ever turned into text; the others stay inside the file and are never
read, printed, logged or stored. When the federal loader's cached copy of a list is fresh it is read from there;
otherwise the list is fetched into memory and never written to disk whole. What was read (office, party, name) is kept
as a small JSON extract with the file's SHA-256. The canvass holds only names and vote counts, so it is cached whole.

What the record does not say, the loader does not say:
  - The lists do not state a ballot order, and their order is not strictly by party (State Senator District 9 and 23
    print the Democrat first), so no ballot order is stored. County auditors print the ballots.
  - Iowa elects the Governor and Lieutenant Governor together on one vote; the list names each party's candidate for
    Lieutenant Governor on a row of its own. There is one race, 2026-IA-GOV, and each governor candidate's running
    mate (same party, the only one listed) is named in the candidate's note.
  - Today's holder comes from the Open States roster in state_ia.sqlite (legislators by chamber and district; the
    officials table for Governor, Attorney General and Secretary of State). The roster does not carry the Auditor, the
    Treasurer or the Secretary of Agriculture, so those races show no holder.
  - A candidate is marked as the sitting member only when the name fits the roster's holder of that same seat and no
    other candidate in the race fits.

Primaries: a party primary becomes a field when two or more candidates were on that party's ballot. Shares are of the
candidates' votes plus write-ins (write-ins are not listed; under and over votes are left out). Iowa nominates the
leader only with at least 35 percent; otherwise a party convention chooses, and the candidate on the November list for
that party is the one who advanced. Every canvass section is checked: county rows add up to the statewide Total,
Election Day plus Absentee equals it, and candidates, write-ins, under and over votes add up to its Total column.
"""

import datetime as dt
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
from collections import Counter

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ballot.common import CACHE, HERE, fold, name_parts, party_code          # noqa: E402
from ballot.lists import ia as fed                                          # noqa: E402
from ballot.match import fits                                               # noqa: E402
from ballot.pdftext import PDF, join, lines, rows as pdf_rows              # noqa: E402
from states import net                                                     # noqa: E402

STATE, FIPS, NAME = "IA", "19", "Iowa"
GENERAL = "2026-11-03"
PRIMARY = fed.PRIMARY
ROSTER_DB = os.path.join(HERE, "state_ia.sqlite")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL, office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT, special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT, election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0, votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT, published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT, PRIMARY KEY (kind, id));
"""

# statewide offices as the lists print them: (race key, office_kind, office shown, roster office)
STATEWIDE = {
    "Governor": ("GOV", "governor", "Governor and Lieutenant Governor", "governor"),
    "Secretary of State": ("SOS", "secretary_of_state", "Secretary of State", "secretary of state"),
    "Auditor of State": ("AUD", "state_auditor", "Auditor of State", None),
    "Treasurer of State": ("TREAS", "state_treasurer", "Treasurer of State", None),
    "Secretary of Agriculture": ("AGR", "secretary_of_agriculture", "Secretary of Agriculture", None),
    "Attorney General": ("AG", "attorney_general", "Attorney General", "attorney general"),
}
RUNNING_MATE = "Lieutenant Governor"
LEGISLATURE = [(re.compile(r"State Senator District (\d+)"), "SS", "state_senate", "State Senator", "Senate"),
               (re.compile(r"State Representative District (\d+)"), "SH", "state_house", "State Representative", "House")]

# A few counties tallied a write-in line by name ("Tommy Hexter") or as "Blank"; the canvass then prints an extra column
# between Write-in and Under Votes. Those columns are write-ins and are added to the write-in total.
COLUMNS_EXTRA = re.compile(r"^Write-in (?P<extra>.+) Under Votes Over Votes Total$")

NOBODY = re.compile(r"^[-–—]+$")      # the lists print "--" where a party has no candidate

SRC_GENERAL = "ia-sos-2026-candidate-list"
SRC_PRIMARY_LIST = "ia-sos-2026-primary-candidate-list"
SRC_CANVASS = "ia-sos-2026-primary-canvass"
SRC_ROSTER = "ia-openstates-roster"
SRC_COUNTIES = "ia-census-cb-2024-county"


def office_of(text):
    """{race_id, level, office_kind, office, district, chamber, roster} for an office the list or canvass names; None for
    Congress; a SystemExit for anything else, so a new office on the list is noticed rather than dropped."""
    if text.startswith("United States "):
        return None
    if text in STATEWIDE:
        key, kind, office, roster = STATEWIDE[text]
        return {"race_id": f"2026-{STATE}-{key}", "level": "statewide", "office_kind": kind, "office": office,
                "district": None, "chamber": None, "roster": roster}
    for pat, key, kind, office, chamber in LEGISLATURE:
        m = pat.fullmatch(text)
        if m:
            d = str(int(m.group(1)))
            return {"race_id": f"2026-{STATE}-{key}{d}", "level": "legislature", "office_kind": kind, "office": office,
                    "district": d, "chamber": chamber, "roster": None}
    raise SystemExit(f"Iowa (state races): an office the loader does not know: {text!r}")


# ---------- the candidate lists: office, party and ballot name only ----------

def read_list(data):
    """(title lines, [(office, party, name)]) from a candidate list's bytes. Cells from the fourth column on (address,
    phone, e-mail, filing date) are never joined into text. The title lines are only tested, never stored or printed."""
    pdf = PDF(data)
    title, body = [], []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        head = False
        for _y, runs in pdf_rows(pdf, page, res):
            if not head:
                head = "Ballot Name(s)" in join([r for r in runs if r[0] < 300])
                if n == 1 and not head:
                    title.append(join(runs))
                continue
            body.append(fed.cells(runs))
    if not body:
        raise SystemExit("Iowa (state races): the candidate list's column headings were not found")
    full = Counter(tuple(round(x) for x, _rs in row[:4]) for row in body if len(row) >= 4 and row[0][0] < 50)
    if not full:
        raise SystemExit("Iowa (state races): no row of the candidate list names an office")
    edges = list(full.most_common(1)[0][0])
    col = lambda x: next((i for i in range(len(edges) - 1, -1, -1) if x >= edges[i] - 1.5), 0)
    office, out = None, []
    for row in body:
        got = {}
        for x, rs in row:
            k = col(x)
            if k < 3:
                got[k] = join(rs)
        party, name = got.get(1, ""), got.get(2, "")
        if not (party and name):      # a footnote or a wrapped line: neither an office nor a candidate
            continue
        if got.get(0):
            office = got[0]
        if office is None:
            raise SystemExit("Iowa (state races): a candidate row before any office")
        out.append((office, party, name))
    return title, out


def get_list(which, page_url, title_words, max_age_days, extract_dir, say):
    """Read one candidate list: the federal loader's cached copy when fresh, else fetched into memory (never saved
    whole). Returns (rows, url, sha256, fetched date, how)."""
    url = None
    for attempt in range(3):
        try:
            url = fed.list_url(page_url, which.title() + " Election")
            break
        except (Exception, SystemExit) as e:          # list_url raises SystemExit when the page stops linking a list
            if attempt == 2:
                say(f"    Iowa (state races): could not read {page_url} ({e}); using the linking page as the address")
            else:
                time.sleep(2)
    cached = os.path.join(CACHE, "ia", f"ia_candidate_list_2026_{which}.pdf")
    extract = os.path.join(extract_dir, f"sl_ia_{which}_list.json")
    data, fetched, how = None, None, None
    if os.path.exists(cached) and time.time() - os.path.getmtime(cached) < max_age_days * 86400:
        data = open(cached, "rb").read()
        fetched, how = dt.date.fromtimestamp(os.path.getmtime(cached)).isoformat(), "the federal loader's cached copy"
    elif url:
        data = net.get(url)
        fetched, how = dt.date.today().isoformat(), "fetched into memory"
    if data is None:
        if not os.path.exists(extract):
            raise SystemExit(f"Iowa (state races): the {which} candidate list could not be read")
        ex = json.load(open(extract, encoding="utf-8"))
        say(f"    Iowa (state races): using the saved extract of the {which} list ({ex['fetched']})")
        return [tuple(r) for r in ex["rows"]], ex["url"], ex["sha256"], ex["fetched"], "the saved extract"
    title, rows = read_list(data)
    if title_words not in title:
        raise SystemExit(f"Iowa (state races): the {which} candidate list is not the one for the {title_words}")
    sha = hashlib.sha256(data).hexdigest()
    del data
    url = url or page_url
    os.makedirs(extract_dir, exist_ok=True)
    with open(extract, "w", encoding="utf-8") as fh:        # office, party and ballot name only
        json.dump({"url": url, "sha256": sha, "fetched": fetched, "title": title_words, "rows": rows}, fh, indent=0)
    return rows, url, sha, fetched, how


# ---------- the primary canvass ----------

def canvass(path):
    """(published, {(office, party): {names, votes, write_in, under, over, total, code, places}}) for every section of
    the canvass summary, from its statewide rows, each checked against the county rows. A section with nobody on the
    ballot (write-ins only) has no names and no party line."""
    L = lines(path)
    first = " ".join(t for p, _y, t in L if p == 1)
    when = re.search(r"Canvass date: (\d\d)/(\d\d)/(\d{4})", first)
    if "2026 Primary Election held on Tuesday, June 02, 2026" not in first or not when:
        raise SystemExit("Iowa (state races): the canvass summary is not the June 2, 2026 primary's")
    published = f"{when.group(3)}-{when.group(1)}-{when.group(2)}"
    out, sec = {}, None

    def close(s):
        if s is None:
            return
        where = f"the canvass section {s['title']!r}"
        st = s["state"]
        if set(st) != {"Election Day", "Absentee", "Total"}:
            raise SystemExit(f"Iowa (state races): {where} has no statewide TOTAL rows")
        if [a + b for a, b in zip(st["Election Day"], st["Absentee"])] != st["Total"]:
            raise SystemExit(f"Iowa (state races): in {where}, Election Day plus Absentee is not the statewide Total")
        if s["counties"] != st["Total"]:
            raise SystemExit(f"Iowa (state races): in {where}, the county Total rows add up to {s['counties']}, not {st['Total']}")
        t = st["Total"]
        if sum(t[:-1]) != t[-1]:
            raise SystemExit(f"Iowa (state races): in {where}, the columns do not add up to the Total column")
        n, e = len(s["names"]), s["n_extra"] or 0
        key = (s["office"], s["party"])
        if key in out:
            raise SystemExit(f"Iowa (state races): {where} appears twice")
        out[key] = {"names": s["names"], "votes": t[:n], "write_in": sum(t[n:n + 1 + e]), "under": t[n + 1 + e],
                    "over": t[n + 2 + e], "total": t[n + 3 + e], "code": s["code"], "places": s["places"],
                    "extra": s["extra"]}

    for page, _y, text in L:
        h = fed.HEADING.match(text)
        if h:
            close(sec)
            if h.group("party") not in fed.CANVASS_PARTY:
                raise SystemExit(f"Iowa (state races): a primary for a party the loader does not know: {text!r}")
            party, code = fed.CANVASS_PARTY[h.group("party")]
            sec = {"title": text, "office": h.group("office"), "party": party, "code": code, "names": None, "buf": [],
                   "want": "names", "page": page, "state": {}, "statewide": False, "counties": None, "places": [],
                   "extra": None, "n_extra": None}
            continue
        if sec is None or fed.FURNITURE.match(text):
            continue
        if page != sec["page"]:      # every page of a section repeats the names, the column headings and the parties
            sec["page"], sec["buf"], sec["want"] = page, [], "names"
        if sec["want"] == "names":
            x = COLUMNS_EXTRA.match(text)
            if text == fed.COLUMNS or x:
                label = x.group("extra") if x else None
                if sec["names"] is not None and label != sec["extra"]:
                    raise SystemExit(f"Iowa (state races): {sec['title']!r} has different columns on page {page}")
                sec["extra"] = label
                names = fed.names_of(" ".join(sec["buf"]))
                if sec["names"] is None:
                    sec["names"] = names
                elif names != sec["names"]:
                    raise SystemExit(f"Iowa (state races): {sec['title']!r} names different candidates on page {page}")
                sec["want"] = "parties" if names else "rows"
            else:
                sec["buf"].append(text)
            continue
        if sec["want"] == "parties":
            codes = text.split()
            if len(codes) != len(sec["names"]) or set(codes) != {sec["code"]}:
                raise SystemExit(f"Iowa (state races): under {sec['title']!r} the party line reads {text!r}")
            sec["want"] = "rows"
            continue
        m = fed.ROW.match(text)
        if not m:
            raise SystemExit(f"Iowa (state races): a line in {sec['title']!r} the loader does not recognise: {text!r}")
        nums = [int(v.replace(",", "")) for v in m.group("nums").split()]
        e = len(nums) - len(sec["names"]) - 4
        if (e != 0 if sec["extra"] is None else e < 1) or (sec["n_extra"] is not None and e != sec["n_extra"]):
            raise SystemExit(f"Iowa (state races): a row of {sec['title']!r} has {len(nums)} numbers for {len(sec['names'])} candidates")
        sec["n_extra"] = e
        place = m.group("place")
        if place == "TOTAL":
            sec["statewide"] = True
        if sec["statewide"]:
            sec["state"][m.group("kind")] = nums
        else:
            if place and m.group("kind") == "Election Day":
                sec["places"].append(place)
            if m.group("kind") == "Total":
                sec["counties"] = nums if sec["counties"] is None else [a + b for a, b in zip(sec["counties"], nums)]
    close(sec)
    return published, out


def get_canvass(say):
    path = os.path.join(CACHE, "ia", "ia_canvass_summary_2026_primary.pdf")
    url = None
    try:
        url = fed.canvass_url()
    except (Exception, SystemExit) as e:
        say(f"    Iowa (state races): could not read the results page ({e}); using it as the address")
    if url:
        net.download(url, path, max_age_days=30, say=say)       # names and votes only: safe to keep whole
    if not os.path.exists(path):
        raise SystemExit("Iowa (state races): the primary canvass could not be read")
    return path, url or fed.RESULTS


# ---------- the roster and the counties ----------

def roster(path=ROSTER_DB):
    """Today's holders: {("Senate"|"House", district): row} and {roster office: row}, plus the roster's date."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    seats, offices = {}, {}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, chamber, district "
                         "FROM legislators WHERE is_current = 1"):
        key = (r[5], str(r[6]))
        if key in seats:
            raise SystemExit(f"Iowa (state races): the roster lists two sitting members for {key}")
        seats[key] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3], "party": r[4]}
    for r in con.execute("SELECT bioguide_id, first_name, last_name, official_full, party_name, office FROM officials"):
        offices[r[5]] = {"id": r[0], "first": r[1], "last": r[2], "full": r[3], "party": r[4]}
    as_of = (con.execute("SELECT max(updated_at) FROM legislators").fetchone()[0] or "")[:10]
    con.close()
    return seats, offices, as_of


def counties(path=COUNTY_ZIP):
    """{folded county name: (GEOID, "Adair County")} for Iowa from the Census Bureau's cartographic county file."""
    import shapefile                                   # pyshp
    z = zipfile.ZipFile(path)
    base = next(n[:-4] for n in z.namelist() if n.endswith(".dbf"))
    rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")))
    fields = [f[0] for f in rdr.fields[1:]]
    out = {}
    for rec in rdr.iterRecords():
        rec = dict(zip(fields, rec))
        if str(rec.get("STATEFP")) == FIPS:
            out[fold(str(rec["NAME"]))] = (str(rec["GEOID"]), str(rec["NAMELSAD"]))
    if len(out) != 99:
        raise SystemExit(f"Iowa (state races): the county file gives {len(out)} Iowa counties, not 99")
    return out


def holder_fits(name, h):
    cand = name_parts(name)
    return any(fits(cand, reg) for reg in ((fold(h["first"]).split(), fold(h["last"])), name_parts(h["full"] or "")) if reg[1])


def same_name(a, b):
    return fold(a) == fold(b) or fold(a).replace(" ", "") == fold(b).replace(" ", "")


def sha_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else ""


def mdate(path):
    return dt.date.fromtimestamp(os.path.getmtime(path)).isoformat() if os.path.exists(path) else ""


# ---------- the load ----------

def load(db_path, say=print, extract_dir=os.path.join(CACHE, "ia")):
    net.patient_lookups()
    g_rows, g_url, g_sha, g_fetched, g_how = get_list("general", fed.PAGE, "November 3, 2026 General Election", 2, extract_dir, say)
    p_rows, p_url, p_sha, p_fetched, p_how = get_list("primary", fed.PRIMARY_PAGE, "June 2, 2026 Primary Election", 30, extract_dir, say)
    c_path, c_url = get_canvass(say)
    published, counted = canvass(c_path)
    seats, offices, as_of = roster()
    cmap = counties()

    # the November list: the state races, and each party's running mate for Lieutenant Governor
    races, general, mates = {}, [], {}
    empty = Counter()
    for office, party, name in g_rows:
        if NOBODY.match(name):
            empty["general"] += 1
            continue
        if office == RUNNING_MATE:
            mates.setdefault(party, []).append(name)
            continue
        o = office_of(office)
        if o is None:
            continue
        races.setdefault(o["race_id"], o)
        general.append((o["race_id"], party, name))
    n_state_listed = len(general)

    # the June 2 primary list, by race and party
    ballots = {}
    for office, party, name in p_rows:
        o = office_of(office)
        if o is None:
            continue
        if NOBODY.match(name):
            empty["primary"] += 1
            continue
        if o["race_id"] not in races:
            raise SystemExit(f"Iowa (state races): {office} was on the primary ballot but is not on the November list")
        ballots.setdefault((o["race_id"], party), []).append(name)

    # canvass sections for state offices, by race and party
    sections, places = {}, {}
    for (office, party), c in counted.items():
        o = office_of(office)
        if o is None:
            continue
        if o["race_id"] not in races:
            raise SystemExit(f"Iowa (state races): the canvass has {office}, which is not on the November list")
        sections[(o["race_id"], party)] = c
        places.setdefault(o["race_id"], set()).update(c["places"])
    for key, names in ballots.items():
        c = sections.get(key)
        if c is None:
            raise SystemExit(f"Iowa (state races): {key} was on the primary list but has no canvass section")
        if sorted(fold(n).replace(" ", "") for n in names) != sorted(fold(n).replace(" ", "") for n in c["names"]):
            raise SystemExit(f"Iowa (state races): {key}: the primary list and the canvass name different candidates")
    for key, c in sections.items():
        if c["names"] and key not in ballots:
            raise SystemExit(f"Iowa (state races): the canvass names candidates for {key}, the primary list nobody")

    # checks on which seats are on the ballot
    sen = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_senate")
    hou = sorted(int(r["district"]) for r in races.values() if r["office_kind"] == "state_house")
    if hou != list(range(1, 101)):
        raise SystemExit(f"Iowa (state races): the November list has House districts {hou}, not all 100")
    if sen != list(range(1, 50, 2)):
        say(f"    CHECK Iowa (state races): Senate districts on the list are {sen}, not the 25 odd-numbered ones")
    missing_statewide = sorted(set(v[0] for v in STATEWIDE.values()) - {r["race_id"].split("-")[-1] for r in races.values()})
    if missing_statewide:
        say(f"    CHECK Iowa (state races): statewide offices not on the November list: {missing_statewide}")

    # today's holders and the sitting member on the ballot
    holders, notes = {}, {}
    for rid, r in races.items():
        h = None
        if r["chamber"]:
            h = seats.get((r["chamber"], r["district"]))
            if h is None:
                notes[rid] = f"The Open States roster ({as_of}) lists no sitting member for this seat."
        elif r["roster"]:
            h = offices.get(r["roster"])
        else:
            notes[rid] = "The Open States roster this site uses does not carry this office, so today's holder is not shown."
        holders[rid] = h
    if "2026-IA-GOV" in races:
        notes["2026-IA-GOV"] = ("Iowa elects the Governor and Lieutenant Governor together, on one vote. The Secretary of "
                                "State's list names each party's candidate for Lieutenant Governor on a row of its own; "
                                "each is named here in the note of the same party's candidate for Governor.")

    names_in = {}
    for rid, party, name in general:
        names_in.setdefault(rid, set()).add(name)
    for (rid, party), names in ballots.items():
        names_in[rid].update(names)
    sitting, party_differs = {}, []
    for rid, h in holders.items():
        if not h:
            continue
        fit = {fold(n) for n in names_in.get(rid, ()) if holder_fits(n, h)}
        if len(fit) == 1:
            sitting[rid] = (fit.pop(), h["id"])
    for rid, party, name in general:
        if rid in sitting and fold(name) == sitting[rid][0] and holders[rid]["party"] and holders[rid]["party"] != party:
            party_differs.append(rid)

    # rows
    cand = []
    mate_note, unpaired = {}, []
    gov_parties = [p for rid, p, _n in general if rid == "2026-IA-GOV"]
    for party, ms in mates.items():
        if len(ms) == 1 and gov_parties.count(party) == 1:
            mate_note[party] = f"Running mate for Lieutenant Governor: {ms[0]}."
        else:
            unpaired.extend(f"{party}: {m}" for m in ms)
    for p in gov_parties:
        if p not in mates:
            unpaired.append(f"{p}: no running mate on the list")
    nominee = {(rid, party): fold(name) for rid, party, name in general}
    for rid, party, name in general:
        inc = rid in sitting and fold(name) == sitting[rid][0]
        note = []
        if rid == "2026-IA-GOV" and party in mate_note:
            note.append(mate_note[party])
        if party in ("Republican", "Democratic") and not any(same_name(name, n) for n in ballots.get((rid, party), [])):
            note.append(f"Not on the June 2 {party} primary ballot; nominated afterwards (the list does not say how).")
        cand.append((rid, "general", GENERAL, name, party, party_code(party), None, 1 if inc else 0, 0, None, None, None,
                     sitting[rid][1] if inc else None, SRC_GENERAL, " ".join(note) or None))

    fields, convention, odd = Counter(), [], []
    for (rid, party), names in sorted(ballots.items()):
        if len(names) < 2:
            continue
        c = sections[(rid, party)]
        fields[races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"] += 1
        votes = {fold(n).replace(" ", ""): v for n, v in zip(c["names"], c["votes"])}
        total = sum(c["votes"]) + c["write_in"]
        top = max(votes, key=votes.get)
        if list(votes.values()).count(votes[top]) > 1:
            raise SystemExit(f"Iowa (state races): {rid} {party}: a tie at the top of the primary")
        outright = bool(total) and 100 * votes[top] / total >= fed.THRESHOLD
        pick = nominee.get((rid, party))
        chosen = top if outright else (pick.replace(" ", "") if pick else None)
        swapped = outright and (pick is None or pick.replace(" ", "") != top)
        if not outright:
            convention.append(f"{rid} {party}")
        elif swapped:
            odd.append(f"{rid} {party}")
        for name in names:
            k = fold(name).replace(" ", "")
            v = votes[k]
            inc = rid in sitting and fold(name) == sitting[rid][0]
            note = None
            if not outright:
                note = "No candidate won the 35 percent of the vote Iowa law requires, so a party convention chose the nominee."
            elif swapped and k == top:
                note = "Won the primary, but is not on the November list for this party."
            elif swapped and pick and k == pick.replace(" ", ""):
                note = ("Lost the primary, but is this party's candidate on the November list "
                        "(the list does not say how the nomination was made).")
            cand.append((rid, f"primary-{c['code']}", PRIMARY, name, party, party_code(party), None, 1 if inc else 0, 0, v,
                         round(100 * v / total, 1) if total else None, "advanced" if k == chosen else "lost",
                         sitting[rid][1] if inc else None, SRC_CANVASS, note))

    race_rows = []
    for rid, r in sorted(races.items()):
        h = holders[rid]
        cids = None
        if r["level"] == "legislature":
            got = places.get(rid, set())
            unknown = sorted(p for p in got if fold(p) not in cmap)
            if unknown:
                raise SystemExit(f"Iowa (state races): county names in the canvass not in the Census file: {unknown}")
            if not got:
                raise SystemExit(f"Iowa (state races): no county rows in the canvass for {rid}")
            cids = ",".join(sorted(cmap[fold(p)][0] for p in got))
        race_rows.append((rid, STATE, r["level"], r["office_kind"], r["office"], NAME, FIPS, cids, r["district"], None, 0, 1,
                          h["id"] if h else None, h["full"] if h else None, h["party"] if h else None, GENERAL, notes.get(rid)))

    place_rows = [("county", geoid, full, None, SRC_COUNTIES) for geoid, full in sorted(cmap.values())]
    n_primary_listed = sum(len(v) for v in ballots.values())
    n_sections = len(sections)

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id LIKE '2026-IA-%'")
        con.execute("DELETE FROM sl_races WHERE state = 'IA'")
        con.execute("DELETE FROM sl_sources WHERE state = 'IA'")
        con.execute("DELETE FROM sl_places WHERE kind = 'county' AND id GLOB '19[0-9][0-9][0-9]'")
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cand)
        con.executemany("INSERT INTO sl_places VALUES (?,?,?,?,?)", place_rows)
        src = [
            (SRC_GENERAL, STATE, "official candidate list", "Iowa Secretary of State",
             "Candidate List, November 3, 2026 General Election", g_url, "", g_fetched, g_sha, n_state_listed + sum(len(v) for v in mates.values()),
             "Office, party and ballot name read (from " + g_how + "); the address, phone, e-mail and filing-date columns are never "
             "read. The list does not state a ballot order and its order is not strictly by party, so no ballot order is stored. "
             "Rows for Lieutenant Governor are named in the notes of the same party's candidate for Governor."),
            (SRC_PRIMARY_LIST, STATE, "official candidate list", "Iowa Secretary of State",
             "Candidate List, June 2, 2026 Primary Election", p_url, "", p_fetched, p_sha, n_primary_listed,
             "Who was on each party's primary ballot for the state offices, and the names as printed; office, party and ballot "
             "name read (from " + p_how + "), the address, phone, e-mail and filing-date columns never read."),
            (SRC_CANVASS, STATE, "official results", "Iowa Secretary of State",
             f"Election Canvass Summary, 2026 Primary Election held on Tuesday, June 02, 2026 (canvass date "
             f"{published[5:7]}/{published[8:]}/{published[:4]})", c_url, published, mdate(c_path), sha_of(c_path),
             sum(len(c["names"]) for c in sections.values()),
             f"Statewide totals of {n_sections} state-office party primaries, each checked against its county rows. Shares are of "
             "the candidates' votes plus write-ins; write-ins are not listed, under and over votes are left out. The counties "
             "listed under each legislative district are the race's county_ids. "
             + (f"Went to a party convention (no one reached 35 percent): {', '.join(convention)}." if convention
                else "Every state-office primary with a field was won outright (35 percent or more).")
             + (f" Primary winner not on the November list: {', '.join(odd)}." if odd else "")),
            (SRC_ROSTER, STATE, "roster", "Open States people project (CC0)",
             "Iowa legislators and statewide officials, as loaded into state_ia.sqlite", "https://github.com/openstates/people",
             as_of, as_of, "", len(seats) + len(offices),
             "Today's holder of each seat and office. The roster does not carry the Auditor, the Treasurer or the Secretary of "
             "Agriculture. A candidate is marked as the sitting member only when the name fits the holder of that seat and no "
             "other candidate in the race fits."),
            (SRC_COUNTIES, STATE, "boundaries", "U.S. Census Bureau",
             "Cartographic boundary file, counties, 2024, 1:500,000 (cb_2024_us_county_500k)",
             "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "", mdate(COUNTY_ZIP),
             sha_of(COUNTY_ZIP), len(place_rows), "Iowa's 99 counties: names and GEOIDs only."),
        ]
        con.executemany("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", src)
    con.close()

    # the report: counts only
    by = Counter(r["office_kind"] if r["level"] == "legislature" else "statewide" for r in races.values())
    gen_by = Counter(races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide" for rid, _p, _n in general)
    one = Counter(races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide"
                  for rid, k in Counter(rid for rid, _p, _n in general).items() if k == 1)
    inc_by = Counter(races[rid]["office_kind"] if races[rid]["level"] == "legislature" else "statewide" for rid in sitting)
    say(f"    Iowa (state races): {by['state_senate']} Senate seats (odd districts), {by['state_house']} House seats, "
        f"{by['statewide']} statewide offices; {len(general)} candidates on the November ballot "
        f"(Senate {gen_by['state_senate']}, House {gen_by['state_house']}, statewide {gen_by['statewide']}; "
        f"one candidate only: Senate {one['state_senate']}, House {one['state_house']}, statewide {one['statewide']}); "
        f"sitting member on the ballot: Senate {inc_by['state_senate']}, House {inc_by['state_house']}, statewide {inc_by['statewide']}; "
        f"primary fields: Senate {fields['state_senate']}, House {fields['state_house']}, statewide {fields['statewide']}; "
        f"{n_sections} canvass sections reconciled")
    say(f"    Iowa (state races): \"--\" (no candidate) on the November list {empty['general']} times, on the primary list "
        f"{empty['primary']} times (state offices); {n_primary_listed} state candidates on the primary list")
    if convention:
        say(f"    Iowa (state races): to a convention: {', '.join(convention)}")
    if odd:
        say(f"    CHECK Iowa (state races): primary winner not on the November list: {', '.join(odd)}")
    if unpaired:
        say(f"    CHECK Iowa (state races): running mates not paired: {unpaired}")
    if party_differs:
        say(f"    CHECK Iowa (state races): sitting member listed under another party: {party_differs}")
    vac = [rid for rid, h in holders.items() if h is None and races[rid]["level"] == "legislature"]
    if vac:
        say(f"    Iowa (state races): no sitting member in the roster for {', '.join(vac)}")
    return len(cand)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python ballot/state_local_ia.py <database file>")
    load(sys.argv[1])
