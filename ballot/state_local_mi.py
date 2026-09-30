"""
Michigan: the state offices on the November 3, 2026 ballot, from the same two reports the federal loader reads
(ballot/lists/mi.py): the Department of State's Official Candidate Listing for the General Election and for the August 4
Primary, published from the Bureau of Elections' filing system (mi-boe.entellitrak.com, "All State and Judicial
Offices"). Each report is one HTML page: a heading per office, then a row per candidate with five cells: a status mark
(DISQ disqualified, WITHD withdrawn, blank otherwise), "Party / Incumbent" (the party; a judge's incumbency mark), the
name written "Last, First", the filing date and the filing method. The report carries no addresses, telephones,
websites or e-mail; this loader reads only the heading, the status mark, the party and the name, and uses the date cell
only to recognise a candidate row (it is never kept).

Read here: Governor and Lieutenant Governor (elected together, written as the ticket, governor first), Secretary of
State, Attorney General, the State Board of Education and the three university boards (all partisan in Michigan, two
seats each), every State Senate seat (all 38: four-year terms, all elected in 2026) and every State House seat (all 110),
and the two state courts elected statewide or by appeals district (Justice of Supreme Court, Judge of Court of Appeals;
nonpartisan on the ballot, so the party is "Nonpartisan office", and the listing's own incumbency mark is kept). Circuit,
district and probate judges are local and left for the county pages.

The November ballot is every candidate without a status mark, in the listing's order (by party, as the ballot prints
them); a nonpartisan race gets no ballot order, since the listing does not say how the ballot orders those names. A
party's primary field is its unmarked candidates on the August listing (two or more); the one on the November listing
for that party advanced. The Department's results site refuses scripts, so the fields say who advanced and carry no
votes. Sitting members come from state_mi.sqlite (the Open States roster): the member for the same chamber and district
whose name fits exactly one candidate is marked incumbent.

Writes only rows for Michigan (state = 'MI') in the database it is given; never touches ballot_2026.sqlite.
"""

import datetime as dt
import hashlib
import os
import re
import sqlite3
import html as H

from ballot.common import HERE, fold, name_parts, party_code
from ballot.lists.mi import BASE, first_last
from ballot.match import fits
from states import net

STATE = "MI"
GENERAL = "2026-11-03"
PRIMARY = "2026-08-04"
CACHE = os.path.join(HERE, "ballot_cache")
ROSTER = os.path.join(HERE, "state_mi.sqlite")
SRC_GEN = "mi-sos-2026-general-listing"
SRC_PRI = "mi-sos-2026-primary-listing"
SRC_ROSTER = "mi-openstates-roster"
PRIMARY_CODE = {"Democratic Party": "DEM", "Republican Party": "REP"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sl_races (race_id TEXT PRIMARY KEY, state TEXT NOT NULL, level TEXT NOT NULL, office_kind TEXT NOT NULL,
  office TEXT NOT NULL, jurisdiction TEXT, jurisdiction_id TEXT, county_ids TEXT, district TEXT, seat TEXT,
  special INTEGER NOT NULL DEFAULT 0, partisan INTEGER NOT NULL, holder_id TEXT, holder_name TEXT, holder_party TEXT,
  election_date TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS sl_candidates (race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL,
  party TEXT, party_code TEXT, ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0,
  votes INTEGER, pct REAL, outcome TEXT, state_member_id TEXT, source_id TEXT, note TEXT, PRIMARY KEY (race_id, election, name));
CREATE TABLE IF NOT EXISTS sl_sources (source_id TEXT PRIMARY KEY, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT,
  published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS sl_places (kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, county_ids TEXT, source_id TEXT,
  PRIMARY KEY (kind, id));
"""

# heading -> (race key, level, office_kind, office, partisan); district offices take the district from the heading
STATEWIDE = [
    (r"^Governor / Lt\. Governor\b", "GOV", "statewide", "governor", "Governor and Lieutenant Governor", 1),
    (r"^Secretary of State\b", "SOS", "statewide", "secretary_of_state", "Secretary of State", 1),
    (r"^Attorney General\b", "AG", "statewide", "attorney_general", "Attorney General", 1),
    (r"^Member of the State Board of Education\b", "SBOE", "statewide", "state_board_of_education", "Member of the State Board of Education", 1),
    (r"^Regent of the University of Michigan\b", "UMREG", "statewide", "university_board", "Regent of the University of Michigan", 1),
    (r"^Trustee of Michigan State University\b", "MSUTR", "statewide", "university_board", "Trustee of Michigan State University", 1),
    (r"^Governor of Wayne State University\b", "WSUGOV", "statewide", "university_board", "Governor of Wayne State University", 1),
    (r"^Justice of Supreme Court\b", "SC", "court", "supreme_court", "Justice of Supreme Court", 0),
]
ORD = r"(\d+)(?:st|nd|rd|th) District"
NUMBER = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}
LOCAL_COURTS = re.compile(r"Judge of (Circuit|District|Probate) Court\b")
OUT_OF_SCOPE = re.compile(r"Representative in Congress|^U\.S\. Senate")


def classify(head):
    """One heading of the report -> a race dict, or None (federal offices and local courts are not read here)."""
    seats = re.search(r"\((\d+)\) Positions?\b", head)
    seats = int(seats.group(1)) if seats else 1
    term = re.search(r"(\d+) Year Terms?", head)
    partial = re.search(r"Partial Term(?: - \d+ Years)? Ending (\d\d/\d\d/\d{4})", head)
    bits = []
    if term and not partial:
        bits.append(f"{term.group(1)}-year term")
    if partial:
        bits.append(f"Partial term ending {partial.group(1)}")
    if seats > 1:
        bits.append(f"{NUMBER.get(seats, seats)} seats; each voter may choose up to {seats}")
    race = None
    m = re.match(ORD + r" State Senator\b", head)
    if m:
        d = str(int(m.group(1)))
        race = dict(key=f"SS{d}", level="legislature", office_kind="state_senate", office="State Senator", district=d, partisan=1, chamber="Senate")
    m = m or re.match(ORD + r" Representative in State Legislature\b", head)
    if m and not race:
        d = str(int(m.group(1)))
        race = dict(key=f"SH{d}", level="legislature", office_kind="state_house", office="Representative in State Legislature", district=d,
                    partisan=1, chamber="House")
    if not race:
        m = re.match(ORD + r" Judge of Court of Appeals (Incumbent|Non-Incumbent)\b", head)
        if m:
            d = str(int(m.group(1)))
            key = f"COA{d}" + ("-NI" if m.group(2) == "Non-Incumbent" else "") + ("-PT" if partial else "")
            bits.insert(0, f"{m.group(2)} position" + ("s" if seats > 1 else ""))
            race = dict(key=key, level="court", office_kind="court_of_appeals", office="Judge of Court of Appeals", district=d, partisan=0)
    if not race:
        for pat, key, level, kind, office, partisan in STATEWIDE:
            if re.match(pat, head):
                race = dict(key=key + ("-PT" if partial else ""), level=level, office_kind=kind, office=office, district=None, partisan=partisan)
                break
    if not race:
        return None
    if race["key"] == "GOV":
        bits.append("Governor and Lieutenant Governor are elected together; each ticket is written governor first")
    race.update(seats=seats, special=1 if partial else 0, note="; ".join(bits) or None, heading=head)
    return race


def read_listing(path):
    """[(heading, status, party cell, name)] for every candidate row, in the report's order. Only these cells are read."""
    text = open(path, encoding="utf-8", errors="replace").read()
    if "Official Candidate Listing" not in text:
        raise SystemExit(f"Michigan: {os.path.basename(path)} is not the Official Candidate Listing report")
    total = re.search(r"(\d+) Candidates as of (\w{3}) (\w{3}) (\d\d) ", text)
    head, out = None, []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        h = re.search(r'<a id="[^"]*"></a><span[^>]*>([^<]+)</span>', tr)
        if h:
            head = re.sub(r"\s+", " ", H.unescape(h.group(1))).strip()
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) != 8:
            continue
        clean = lambda i: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cells[i])).replace("\xa0", " ")).strip()
        if not re.fullmatch(r"\d\d/\d\d/\d{4}", clean(5)):        # the column-heading row; the date itself is not kept
            continue
        out.append((head, clean(1), clean(3), clean(4)))
    published = ""
    if total:
        month = dt.datetime.strptime(total.group(3), "%b").month
        published = f"2026-{month:02d}-{int(total.group(4)):02d}"
    return out, (int(total.group(1)) if total else None), published


def ballot_name(raw):
    """'Benson, Jocelyn  / Brinks, Winnie' -> 'Jocelyn Benson / Winnie Brinks'; 'Gilchrist II, Garlin' -> 'Garlin Gilchrist II'."""
    return " / ".join(re.sub(r"\s+", " ", first_last(part.strip())) for part in raw.split(" / "))


def roster():
    """Sitting legislators by (chamber, district) and statewide officials by office. Names, party and id only."""
    con = sqlite3.connect(f"file:{ROSTER}?mode=ro", uri=True)
    members = {}
    for mid, full, first, last, party, district, chamber in con.execute(
            "SELECT bioguide_id, official_full, first_name, last_name, party_name, district, chamber FROM legislators WHERE is_current = 1"):
        members.setdefault((chamber, str(district)), []).append(dict(id=mid, name=full or f"{first} {last}", first=first, last=last, party=party))
    officials = {}
    for oid, full, office, party in con.execute("SELECT bioguide_id, official_full, office, party_name FROM officials"):
        officials[office] = dict(id=oid, name=full, party=party)
    con.close()
    return members, officials


def member_parts(m):
    g, f = name_parts(m["name"])
    if m.get("last"):
        f = fold(m["last"])
        g = [w for w in fold(m.get("first") or "").split()] or g
    return g, f


LOOSE = []      # (race, candidate, member) matched by the looser rule, printed for reading


def find_incumbent(names, member, rid=None):
    """The one name in the race that fits the member, or None (none fit, or more than one). When no name fits, a
    candidate whose family name is the member's and unique in the race, with given names that begin with the same two
    letters, is taken (Jasper for Jaz, Timothy for Timmy), and listed for reading."""
    if not member:
        return None
    mp = member_parts(member)
    parts = {n: name_parts(n.split(" / ")[0]) for n in names}
    hits = [n for n in names if fits(parts[n], mp)]
    if not hits:
        same = [n for n in names if parts[n][1] == mp[1]]
        if len(same) == 1 and parts[same[0]][0] and mp[0] and parts[same[0]][0][0][:2] == mp[0][0][:2]:
            hits = same
            LOOSE.append((rid, same[0], member["name"]))
    return hits[0] if len(hits) == 1 else None


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def fetched(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def load(db_path, say=print, cache=CACHE, fetch=True):
    paths = {k: os.path.join(cache, f"mi_candidate_listing_2026_{k.lower()}.html") for k in ("GEN", "PRI")}
    if fetch:
        net.patient_lookups()
        for k, p in paths.items():
            net.download(BASE + k, p, max_age_days=2, say=say)
    gen, gen_total, gen_pub = read_listing(paths["GEN"])
    pri, pri_total, pri_pub = read_listing(paths["PRI"])
    problems, left_out = [], {}
    LOOSE.clear()

    # the report's own count: a ticket counts as two candidates
    for label, rows, total in (("General", gen, gen_total), ("Primary", pri, pri_total)):
        counted = sum(1 + r[3].count(" / ") for r in rows)
        if total is not None and counted != total:
            problems.append(f"{label} listing: {counted} candidates read, the report says {total}")

    members, officials = roster()
    races, cands = {}, []
    gen_by_race, off_ballot = {}, []
    for head, status, party, raw in gen:
        race = classify(head)
        if not race:
            if not OUT_OF_SCOPE.search(head or ""):
                left_out[("local court" if LOCAL_COURTS.search(head or "") else "other")] = left_out.get(
                    "local court" if LOCAL_COURTS.search(head or "") else "other", 0) + 1
            continue
        rid = f"2026-{STATE}-{race['key']}"
        races.setdefault(rid, race)
        name = ballot_name(raw)
        rec = dict(status=status, party=party, name=name)
        gen_by_race.setdefault(rid, []).append(rec)
        if status:
            off_ballot.append((rid, status, name))

    race_rows = []
    for rid, race in races.items():
        holder = None
        if race.get("chamber"):
            sitting = members.get((race["chamber"], race["district"]), [])
            holder = sitting[0] if len(sitting) == 1 else None
            if len(sitting) != 1:
                problems.append(f"{rid}: {len(sitting)} sitting members on the roster for this seat")
        elif race["key"] == "GOV":
            holder = officials.get("governor")
        elif race["key"] == "SOS":
            holder = officials.get("secretary of state")
        elif race["key"] == "AG":
            holder = officials.get("attorney general")
        note = race["note"]
        if race["key"] == "GOV" and officials.get("lt_governor"):
            note = (note + "; " if note else "") + f"Lieutenant Governor today: {officials['lt_governor']['name']}"
        race["holder"] = holder
        race_rows.append((rid, STATE, race["level"], race["office_kind"], race["office"], None if race["district"] else "Michigan",
                          None if race["district"] else "26", None, race["district"], None, race["special"], race["partisan"],
                          holder["id"] if holder else None, holder["name"] if holder else None, holder["party"] if holder else None,
                          GENERAL, note))

        on = [c for c in gen_by_race[rid] if not c["status"]]
        if not on:
            problems.append(f"{rid}: no candidate on the November ballot")
        inc_name = find_incumbent([c["name"] for c in on], holder, rid) if race.get("chamber") or race["key"] in ("SOS", "AG") else None
        order = 0
        seen = set()
        for c in on:
            if race["partisan"]:
                if not c["party"] or c["party"] == "INCUMBENT":
                    problems.append(f"{rid}: a candidate with no party on the listing ({c['name']})")
                order += 1
                party, code, inc = c["party"], party_code(c["party"]), int(c["name"] == inc_name)
                bo = order
            else:
                party, code, bo = "Nonpartisan office", "N", None
                inc = int(c["party"] == "INCUMBENT")
            if c["name"] in seen:
                problems.append(f"{rid}: the same name twice on the November list ({c['name']})")
            seen.add(c["name"])
            cands.append((rid, "general", GENERAL, c["name"], party, code, bo, inc, 0, None, None, None,
                          holder["id"] if inc and holder and race["partisan"] else None, SRC_GEN, None))

    # primary fields: unmarked candidates on the August list, two or more for one party in one race
    fields, pri_off, pri_counts = {}, 0, {}
    for head, status, party, raw in pri:
        race = classify(head)
        if not race:
            continue
        rid = f"2026-{STATE}-{race['key']}"
        if status:
            pri_off += 1
            continue
        if rid not in races:
            problems.append(f"{rid}: on the August list but not the November list")
            continue
        fields.setdefault((rid, party), []).append(ballot_name(raw))
        pri_counts[rid] = pri_counts.get(rid, 0) + 1
    n_fields = 0
    for (rid, party), names in fields.items():
        if len(names) < 2:
            continue
        if party not in PRIMARY_CODE:
            problems.append(f"{rid}: a primary field for {party!r}, which has no code here")
            continue
        n_fields += 1
        race = races[rid]
        nominees = [c["name"].split(" / ")[0] for c in gen_by_race[rid] if c["party"] == party]
        won = [n for n in names if any(fold(n) == fold(x) or fits(name_parts(n), name_parts(x)) for x in nominees)]
        if len(won) != 1:
            problems.append(f"{rid} {PRIMARY_CODE[party]} primary: {len(won)} of {len(names)} names found on the November list "
                            f"({'nominee not in the field: nominated another way' if nominees and not won else 'read again'})")
        inc_name = find_incumbent(names, race["holder"], rid) if race.get("chamber") else None
        for name in names:
            outcome = "advanced" if name in won and len(won) == 1 else ("lost" if len(won) == 1 or (nominees and not won) else None)
            inc = int(name == inc_name)
            cands.append((rid, f"primary-{PRIMARY_CODE[party]}", PRIMARY, name, party, party_code(party), None, inc, 0, None, None, outcome,
                          race["holder"]["id"] if inc else None, SRC_PRI, None))

    # checks against the seats that must be on the ballot
    for chamber, key, seats in (("Senate", "SS", 38), ("House", "SH", 110)):
        missing = [str(d) for d in range(1, seats + 1) if f"2026-{STATE}-{key}{d}" not in races]
        extra = [r for r in races if r.startswith(f"2026-{STATE}-{key}") and not (1 <= int(r.split(key)[1]) <= seats)]
        if missing or extra:
            problems.append(f"{chamber}: districts missing from the November list {missing}; unexpected {extra}")
    keys = [(c[0], c[1], c[3]) for c in cands]
    if len(keys) != len(set(keys)):
        problems.append("two candidate rows share race, election and name")

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        con.execute("DELETE FROM sl_candidates WHERE race_id IN (SELECT race_id FROM sl_races WHERE state = ?) OR race_id LIKE ?",
                    (STATE, f"2026-{STATE}-%"))
        con.execute("DELETE FROM sl_races WHERE state = ?", (STATE,))
        con.execute("DELETE FROM sl_sources WHERE state = ?", (STATE,))
        con.executemany("INSERT INTO sl_races VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", race_rows)
        con.executemany("INSERT INTO sl_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", cands)
        n_gen = sum(len(v) for v in gen_by_race.values())
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_GEN, STATE, "official candidate list", "Michigan Department of State, Bureau of Elections",
            "Official Candidate Listing, All State and Judicial Offices, General Election, Tuesday, November 3, 2026", BASE + "GEN",
            gen_pub, fetched(paths["GEN"]), sha(paths["GEN"]), n_gen,
            f"Read: the state offices, both chambers and the Supreme Court and Court of Appeals ({n_gen} rows); marked disqualified or "
            f"withdrawn and left off: {len(off_ballot)}. Local judges ({left_out.get('local court', 0)} rows) are for the county pages. "
            "Nonpartisan races carry no ballot order. Only the office, status, party and name cells are read."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_PRI, STATE, "official candidate list", "Michigan Department of State, Bureau of Elections",
            "Official Candidate Listing, All State and Judicial Offices, Primary Election, Tuesday, August 4, 2026", BASE + "PRI",
            pri_pub, fetched(paths["PRI"]), sha(paths["PRI"]), sum(pri_counts.values()),
            "Who advanced is read from the November listing; the primary's vote counts are not loaded (the Department's results "
            "site refuses scripts)."))
        con.execute("INSERT INTO sl_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            SRC_ROSTER, STATE, "member roster", "Open States people project (CC0), via state_mi.sqlite",
            "Sitting Michigan legislators and statewide officials", "https://github.com/openstates/people",
            "", fetched(ROSTER), "", sum(len(v) for v in members.values()) + len(officials),
            "Used for who holds each seat today and to mark incumbents; names, party and ids only. The holder is the member "
            "elected for that district number (Senate 2022, House 2024); where lines have been redrawn since, the same number may "
            "cover different ground."))
    con.close()

    gen_rows = [c for c in cands if c[1] == "general"]
    ss = sum(1 for c in gen_rows if "-SS" in c[0])
    sh = sum(1 for c in gen_rows if "-SH" in c[0])
    other = len(gen_rows) - ss - sh
    say(f"    Michigan state offices: {len(races)} races, {len(gen_rows)} candidates on the November ballot "
        f"(Senate {ss} in {sum(1 for r in races if '-SS' in r)} seats, House {sh} in {sum(1 for r in races if '-SH' in r)} seats, "
        f"statewide and courts {other}); {len(off_ballot)} disqualified or withdrawn left off; {n_fields} party primaries with a field")
    for rid, cand, member in sorted(set(LOOSE)):
        say(f"    incumbent by the looser rule (read it): {rid} {cand} = {member}")
    for p in problems:
        say(f"    CHECK {p}")
    return dict(races=len(races), general=len(gen_rows), senate=ss, house=sh, other=other, off=off_ballot, fields=n_fields,
                problems=problems, left_out=left_out, primary_off=pri_off)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the state-and-local ballot database to write Michigan's rows into")
    ap.add_argument("--no-fetch", action="store_true", help="use the cached listings as they are")
    a = ap.parse_args()
    load(a.db, fetch=not a.no_fetch)
