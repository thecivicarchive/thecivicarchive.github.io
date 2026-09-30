"""
Connecticut: the Secretary of the State's sample ballots for the November 3, 2026 State Election, and the official
returns of the August 11, 2026 party primaries from the Secretary's Election Management System. Connecticut has five
House seats on the 2022 lines and no Senate race in 2026. Most nominations are made by party convention; a primary is
held only where a challenger qualified, and in 2026 that was the Democratic primary in District 1 and the Republican
primaries in Districts 4 and 5.

  November ballot   "November 3, 2026, State Election, Sample Town Ballots" (portal.ct.gov/sots, town-ballots/
                    2026-november-town-election-ballots): one PDF per town ("<town>_sample.pdf"), posted town by town as
                    each town's ballot is approved (19 of 169 towns on 2026-09-30). Every page is the ballot of one voting
                    district, headed "Congressional District N" (bilingual towns: "Congressional District/Distrito
                    Congresional N"), and laid out as Connecticut's party-row grid: a column per office, numbered 1 to N
                    along the top, a row per party (Democratic, Republican, Working Families, Independent, then minor
                    parties and petitioning candidates), each filled cell marked with its column and row ("2A"), and the
                    party's name printed at the left of its row. The loader finds the column whose heading reads
                    "Representative in Congress", and for every row above "Write-in Votes" reads the party's name and the
                    name printed in that cell. Every posted page of every posted town is read; for each district, every
                    page that carries it must print the same names on the same party lines in the same order, and the
                    first town in alphabetical order is recorded as the source, the others as checks. A town's ballot
                    laid out in a way this reading does not follow is set aside and named in the run's output, never
                    guessed at. A district whose towns have no ballot posted yet goes in list_gaps.
  primaries         the Election Management System's public reporting (ctemspublic.pcctg.net, linked from the Secretary's
                    Election Results page): the "08/11/2026 -- Democratic Primary" and "08/11/2026 -- Republican Primary"
                    elections, read from the JSON files its own page loads (ng-app/data/Elections.json, then
                    election/<id>/Version.json and the files of that version: Lookupdata for the offices, the candidates'
                    printed names and parties and the towns; stateVotes for each candidate's total; townVotes for every
                    town's figures; townStatus for each town's status; officePrecincts for precincts reported). A total
                    is stored only when every town that voted in that contest has its return marked "( Official
                    Results )" and all its precincts are in; the towns' figures must add up to each candidate's total.
                    Connecticut primary ballots have no write-in line, so a field's total is its candidates' votes. The
                    winner is the top vote-getter, and must be that party's candidate on the November ballot, or the row
                    says plainly that the nominee is not on it.

The sample ballots print names, parties and offices only. The Management System's candidate records also carry an
address field ("AD") and another field ("CO"); only the printed name ("NM") and party ("P") are read, and the cache
(ballot_cache/ct/) keeps the ballot PDFs (no contact details on them), what was read from them, and, from the
Management System, only the congressional contests' names, parties, votes and town statuses, as JSON.

Names are printed first name first, in ordinary capitals, the given names on one line of the cell and the family name
on the next; they are shown as printed, the lines joined. Parties are printed in full ("Democratic Party", "Working
Families Party", "Independent Party", "Green Party", "Petitioning Candidate") and kept as printed; the Independent Party
of Connecticut is a party, coloured as the kit colours an independent, and a petitioning candidate (on the ballot by
voters' petition, with no party) likewise. Connecticut lets several parties nominate one candidate (cross-endorsement):
as for New York, a candidate is listed once, with every line held, in ballot order, ordered by the first line, and
coloured by the first major party among them. Ballot order is the order of the rows. Withdrawn candidates are not
printed on a ballot, so none are left off here; registered write-in candidates (registration closes 14 days before the
election) are never printed on the ballot and the Secretary's list of them is not read, so none are stored.
"""

import datetime as dt
import hashlib
import html as H
import json
import os
import re
import time
from urllib.parse import urljoin

from ballot.common import fold, house_id, party_code, record_source
from ballot.pdftext import PDF, page_runs
from states import net

BALLOT_PAGE = "https://portal.ct.gov/sots/election-services/town-ballots/2026-november-town-election-ballots"
BALLOT_LINK = re.compile(r"/town_ballots/2026/nov-2026/([^/?#]+\.pdf)", re.I)
CTEMS = "https://ctemspublic.pcctg.net/"
CTEMS_DATA = CTEMS + "ng-app/data/"
PRIMARY = "2026-08-11"
PRIMARY_NAME = re.compile(r"^08/11/2026 -- (Democratic|Republican|Libertarian|Green) Primary$")
DISTRICTS = range(1, 6)
CODES = {"Democratic Party": "DEM", "Republican Party": "REP", "Libertarian Party": "LIB", "Green Party": "GRE"}
OFFICIAL = "( Official Results )"
LABEL = re.compile(r"^(\d{1,2})([A-Z])$")
HEADING = re.compile(r"Congressional District(?:/Distrito Congresional)? (\d)\b")
READER = 1                                            # bump when congress_column reads a page differently


class Unreadable(Exception):
    """A town's ballot laid out in a way this loader does not read: that town is set aside and named, never guessed at."""


def code(party):
    """party_code, with a petitioning candidate (no party) coloured as an independent."""
    return "I" if party.strip().lower().startswith("petitioning") else party_code(party)


def slug(fname):
    """bloomfield_sample.pdf -> bloomfield: the town's part of a source id."""
    return re.sub(r"(_sample)?\.pdf$", "", fname.lower())


def english(label):
    """A party's name as printed, its Spanish half (bilingual ballots) set aside."""
    label = re.split(r"\s*/\s*|\s+(?=Partido\b)", label)[0]
    return re.sub(r"\s+", " ", label).strip()


# ---------- the sample ballots ----------

def words(runs):
    """A page's letters put back into words: letters on one line that touch (a gap of a point or less) are one word."""
    out = []
    for r in sorted(runs, key=lambda r: (-round(r[1], 1), r[0])):
        w = out[-1] if out else None
        if w and abs(w["y"] - r[1]) <= 1.0 and -1.0 <= r[0] - w["x1"] <= 1.0 and abs(r[2] - w["size"]) < 0.2:
            w["t"] += r[3]
            w["x1"] = max(w["x1"], r[4])
        else:
            out.append({"x0": r[0], "x1": r[4], "y": r[1], "size": r[2], "t": r[3]})
    for w in out:
        w["t"] = re.sub(r"\s+", " ", w["t"]).strip()
        w["xc"] = (w["x0"] + w["x1"]) / 2
    return [w for w in out if w["t"]]


def text_lines(ws):
    """Words grouped into printed lines, top to bottom: [(y, text)]."""
    out = []
    for w in sorted(ws, key=lambda w: (-w["y"], w["x0"])):
        if out and abs(out[-1][0] - w["y"]) <= 1.5:
            out[-1][1].append(w)
        else:
            out.append([w["y"], [w]])
    return [(y, " ".join(x["t"] for x in sorted(line, key=lambda w: w["x0"]))) for y, line in out]


def congress_column(path, town):
    """[{"pages": [n], "district": d, "lines": [[row, party, name]]}] for a town's ballot, identical pages merged."""
    pdf = PDF(open(path, "rb").read())
    found = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        ws = words(page_runs(pdf, page, res))
        lines = text_lines(ws)
        top_row = next((y for y, t in lines if len(t.split()) >= 2 and t.split() == [str(k) for k in range(1, len(t.split()) + 1)]), None)
        if top_row is None:
            continue                                  # not a ballot face (instructions, a blank back)
        where = f"{town}'s ballot, page {n}"
        districts = {int(m.group(1)) for _y, t in lines for m in [HEADING.search(t)] if m}
        if len(districts) != 1 or not districts <= set(DISTRICTS):
            raise Unreadable(f"{where} does not name one congressional district ({sorted(districts)})")
        labels = [(int(m.group(1)), m.group(2), w) for w in ws for m in [LABEL.match(w["t"])] if m and w["y"] < top_row - 10]
        cols, rows = {}, {}
        for c, r, w in labels:
            cols.setdefault(c, []).append(w["x0"])
            rows.setdefault(r, []).append(w["y"])
        if sorted(cols) != list(range(1, len(cols) + 1)) or len(cols) < 2:
            raise Unreadable(f"{where}: the office columns are not numbered 1 to N ({sorted(cols)})")
        if any(max(v) - min(v) > 4 for v in cols.values()) or any(max(v) - min(v) > 2 for v in rows.values()):
            raise Unreadable(f"{where}: the cell marks do not line up in columns and rows")
        centre = {c: sum(xs) / len(xs) + 5 for c, xs in cols.items()}         # about the middle of the column's marks
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
        heads = {c: " ".join(t for _y, t in text_lines([w for w in ws if lo <= w["xc"] < hi and first + 4 < w["y"] < top_row + 4]))
                 for c, (lo, hi) in band.items()}
        mine = [c for c, h in heads.items() if re.search(r"\bRepresentative in Congress\b", h)]
        if len(mine) != 1:
            raise Unreadable(f"{where}: {len(mine)} columns headed Representative in Congress")
        c = mine[0]
        lo, hi = band[c]
        party_edge = band[1][0] + 1
        filled = {(cc, r) for cc, r, _w in labels}
        got, write_in_row = [], False
        for k, r in enumerate(order):
            below = rowy[order[k + 1]] + 3 if k + 1 < len(order) else rowy[r] - 60
            party = english(" ".join(t for _y, t in text_lines([w for w in ws if w["x1"] <= party_edge and below < w["y"] <= rowy[r] + 3])))
            if party.startswith("Write-in"):
                write_in_row = True
                break
            cell = [t for _y, t in text_lines([w for w in ws if lo <= w["xc"] < hi and below < w["y"] < rowy[r] - 2])]
            if (c, r) not in filled:
                if cell:
                    raise Unreadable(f"{where}: words in the Representative in Congress column of row {r} with no cell mark")
                continue
            if not party or not cell:
                raise Unreadable(f"{where}: cell {c}{r} has no {'party' if not party else 'name'}")
            name = re.sub(r"\s+", " ", " ".join(cell)).strip()
            if name == name.upper():
                raise Unreadable(f"{where} prints a name in capitals, which this loader does not yet show")
            got.append([r, party, name])
        if not write_in_row:
            raise Unreadable(f"{where}: no Write-in Votes row found")
        for f in found:
            if f["district"] == min(districts) and f["lines"] == got:
                f["pages"].append(n)
                break
        else:
            found.append({"pages": [n], "district": min(districts), "lines": got})
    if not found:
        raise Unreadable(f"no ballot faces read in {town}'s sample ballot")
    return found


def ballots(folder, say):
    """Every posted town's sample ballot, downloaded once per revision and read once: {file: {...}}."""
    index_path = os.path.join(folder, "ct_2026_ballots_read.json")
    old = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else {}
    if old and time.time() - os.path.getmtime(index_path) < 86400:
        return old, index_path
    page = net.get(BALLOT_PAGE, accept="text/html").decode("utf-8", "replace")
    links = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href = H.unescape(m.group(1))
        hit = BALLOT_LINK.search(href)
        if hit:
            town = re.sub(r"<[^>]+>|\s+", " ", H.unescape(m.group(2))).strip()
            rev = re.search(r"[?&]rev=([0-9A-Fa-f]+)", href)
            links[hit.group(1).lower()] = (town, urljoin(BALLOT_PAGE, href), rev.group(1) if rev else "")
    if not links:
        raise SystemExit("Connecticut: the Sample Town Ballots page links no town ballots")
    os.makedirs(os.path.join(folder, "ballots"), exist_ok=True)

    def read(path, town):
        try:
            return {"faces": congress_column(path, town), "unreadable": None}
        except Unreadable as e:
            return {"faces": [], "unreadable": str(e)}

    index, fetched = {}, 0
    for fname, (town, url, rev) in sorted(links.items()):
        path = os.path.join(folder, "ballots", fname)
        prev = old.get(fname)
        if prev and prev.get("rev") == rev and os.path.exists(path):
            if prev.get("reader") != READER:                  # the reading changed: read the kept file again, nothing downloaded
                prev = dict(prev, reader=READER, **read(path, town))
            index[fname] = prev
            continue
        raw = net.get(url, accept="application/pdf")
        time.sleep(1.0)
        entry = {"town": town, "url": url.split("?")[0], "rev": rev, "sha256": hashlib.sha256(raw).hexdigest(),
                 "fetched": dt.date.today().isoformat(), "reader": READER}
        if not raw.startswith(b"%PDF"):
            index[fname] = dict(entry, faces=[], unreadable=f"{town}'s sample ballot did not come back as a PDF (it begins {raw[:8]!r})")
            continue
        with open(path, "wb") as fh:
            fh.write(raw)
        fetched += 1
        index[fname] = dict(entry, **read(path, town))
    os.makedirs(folder, exist_ok=True)
    json.dump(index, open(index_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"      sample ballots: {len(index)} towns posted, {fetched} downloaded afresh")
    return index, index_path


# ---------- the primaries ----------

def ints(text):
    t = str(text or "").replace(",", "").strip()
    return int(t) if t else 0


def official_contest(c):
    """Every town that voted in the contest has its return marked official, and every precinct is in."""
    m = re.fullmatch(r"(\d+) of (\d+) \(100%\)", c["precincts"])
    return bool(m) and m.group(1) == m.group(2) and bool(c["status"]) and all(s == OFFICIAL for s in c["status"].values())


def ctems_json(path):
    return json.loads(net.get(CTEMS_DATA + path, accept="application/json").decode("utf-8-sig"))


def primaries(say):
    """The congressional contests of the August 11 primaries, only the figures read: names, parties, votes, statuses."""
    elections = ctems_json("Elections.json")
    out = []
    for e in elections:
        if not PRIMARY_NAME.match(e.get("Name", "")):
            continue
        eid = e["ID"]
        version = int(ctems_json(f"election/{eid}/Version.json")["Version"])
        base = f"election/{eid}/{version}/"
        look = ctems_json(base + "Lookupdata.json")
        party = look["election"]["P"]
        if party not in CODES:
            raise SystemExit(f"Connecticut: a primary of a party that is not read ({party!r})")
        offices = {}
        for group in look["officeList"]:
            for oid, o in group.items():
                m = re.fullmatch(r"Representative in Congress (\d)", o["NM"].strip())
                if m:
                    offices[oid] = int(m.group(1))
        state = ctems_json(base + "stateVotes_Electiondata.json")
        towns = ctems_json(base + "townVotes_Electiondata.json")
        status = ctems_json(base + "townStatus_Electiondata.json")
        precincts = ctems_json(base + "officePrecincts_Electiondata.json")
        parties = {pid: p["NM"] for pid, p in look["partyIds"].items()}
        contests = {}
        for oid, d in offices.items():
            cands = {}
            for cell in state.get(oid, []):
                for cid, v in cell.items():
                    rec = look["candidateIds"][cid]                   # only the printed name and the party are read
                    cands[cid] = {"name": re.sub(r"\s+", " ", rec["NM"]).strip(), "party": parties.get(rec["P"], rec["P"]), "votes": ints(v["V"])}
            by_town = {}
            for tid, offs in towns.items():
                if oid in offs:
                    by_town[tid] = {cid: ints(v["V"]) for cell in offs[oid] for cid, v in cell.items()}
            contests[oid] = {"district": d, "candidates": cands, "towns": by_town, "precincts": precincts.get(oid, ""),
                             "status": {tid: status.get(tid, {}).get("TS", "") for tid in by_town},
                             "town_names": {tid: look["townIds"].get(tid, tid) for tid in by_town}}
        out.append({"id": eid, "name": e["Name"], "party": party, "version": version, "contests": contests})
        time.sleep(1.0)
    if not out:
        raise SystemExit("Connecticut: the Election Management System lists no August 11, 2026 primary")
    say(f"      Election Management System: {len(out)} August 11 primaries read")
    return {"fetched": dt.date.today().isoformat(), "elections": out}


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "ct")
    index, index_path = ballots(folder, say)

    # the November ballot: each district's party lines, which every page carrying it must print alike
    seen, unreadable = {}, []
    for fname, rec in sorted(index.items()):
        if rec.get("unreadable"):
            unreadable.append(rec["unreadable"])
        for face in rec["faces"]:
            seen.setdefault(face["district"], []).append((fname, face))
    rows, general, source_of, checked, nominee = [], {}, {}, {}, {}
    for d in DISTRICTS:
        if d not in seen:
            continue
        (fname, face), others = seen[d][0], seen[d][1:]
        lines_ = [(p, n) for _r, p, n in face["lines"]]
        for f2, face2 in others:
            if [(p, n) for _r, p, n in face2["lines"]] != lines_:
                raise SystemExit(f"Connecticut: District {d}: {index[f2]['town']}'s ballot (pages {face2['pages']}) does not print the same "
                                 f"Representative in Congress lines as {index[fname]['town']}'s")
        source_of[d] = fname
        checked[d] = sorted({index[f2]["town"] for f2, _x in others} - {index[fname]["town"]})
        people, order = {}, []
        for p, n in lines_:
            key = fold(n)
            if key not in people:
                people[key] = {"name": n, "lines": []}
                order.append(key)
            elif people[key]["name"] != n:
                raise SystemExit(f"Connecticut: District {d}: one candidate printed two ways ({people[key]['name']!r}, {n!r})")
            if p in people[key]["lines"]:
                raise SystemExit(f"Connecticut: District {d}: {n} printed twice on the {p} line")
            people[key]["lines"].append(p)
            if p in CODES:
                if (d, p) in nominee:
                    raise SystemExit(f"Connecticut: District {d}: two candidates on the {p} line")
                nominee[(d, p)] = n
        race = house_id("CT", d)
        general[race] = []
        for k, key in enumerate(order, start=1):
            held = people[key]["lines"]
            first_major = next((p for p in held if code(p) in ("D", "R")), held[0])
            note = f"On the ballot on {len(held)} party lines: {', '.join(held)}." if len(held) > 1 else None
            rows.append((race, "general", "2026-11-03", people[key]["name"], ", ".join(held), code(first_major), k, 0, 0,
                         None, None, None, None, None, f"ct-sots-2026-ballot-{slug(fname)}", note))
            general[race].append(people[key]["name"])

    # the primaries
    ppath = os.path.join(folder, "ct_2026_primaries_congress.json")
    prim = json.load(open(ppath, encoding="utf-8")) if os.path.exists(ppath) else None
    age = time.time() - os.path.getmtime(ppath) if prim else None
    settled = prim and all(official_contest(c) for e in prim["elections"] for c in e["contests"].values())
    if not prim or age > 30 * 86400 or (not settled and age > 86400):          # returns not yet official are asked for again daily
        prim = primaries(say)
        os.makedirs(folder, exist_ok=True)
        json.dump(prim, open(ppath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fields, not_on, unofficial = 0, [], []
    for e in prim["elections"]:
        pcode, party = CODES[e["party"]], e["party"]
        for oid, c in e["contests"].items():
            d, cands = c["district"], c["candidates"]
            for cid, v in cands.items():
                if v["party"] != party:
                    raise SystemExit(f"Connecticut: {v['name']} is filed under {v['party']} in the {party} primary")
                summed = sum(t.get(cid, 0) for t in c["towns"].values())
                if summed != v["votes"]:
                    raise SystemExit(f"Connecticut: {v['name']} (District {d}, {party} primary): the towns add up to {summed}, the total is {v['votes']}")
            extra = {cid for t in c["towns"].values() for cid in t} - set(cands)
            if extra:
                raise SystemExit(f"Connecticut: the District {d} {party} primary has town figures for candidates with no total")
            if len(cands) < 2:
                continue
            fields += 1
            official = official_contest(c)
            if not official:
                unofficial.append(f"District {d} {party}")
            race = house_id("CT", d)
            total = sum(v["votes"] for v in cands.values())
            ranked = sorted(cands.values(), key=lambda v: (-v["votes"], v["name"]))
            if ranked[0]["votes"] == ranked[1]["votes"]:
                raise SystemExit(f"Connecticut: the District {d} {party} primary is tied at the top")
            listed = nominee.get((d, party))
            for v in ranked:
                if official:
                    won = v is ranked[0]
                else:
                    won = None if listed is None else fold(listed).split()[-1] == fold(v["name"]).split()[-1]
                note = None
                if won and race in general and (listed is None or fold(listed).split()[-1] != fold(v["name"]).split()[-1]):
                    note = "Won the primary but is not on the November ballot." if listed is None else \
                        f"Won the primary; the November ballot prints {listed} on the {party} line instead."
                    not_on.append(f"{v['name']} (District {d}, {party})")
                elif won and race not in general:
                    note = "Won the primary; no sample ballot for this district has been posted yet to show the November line."
                if not official:
                    note = "; ".join(x for x in (note, "The primary's official returns are not all in, so no votes are shown; "
                                                       + ("the outcome is read from the November ballot." if listed else
                                                          "no November ballot for this district is posted yet to show who advanced.")) if x)
                rows.append((race, f"primary-{pcode}", PRIMARY, v["name"], party, code(party), None, 0, 0,
                             v["votes"] if official else None, round(100 * v["votes"] / total, 1) if official and total else None,
                             None if won is None else "advanced" if won else "lost", None, None, f"ct-sots-2026-primary-{pcode.lower()}", note))

    races = [r for (r,) in con.execute("SELECT race_id FROM races WHERE state = 'CT' ORDER BY race_id")]
    missing = [r for r in races if r not in general]
    general_rows = [r for r in rows if r[1] == "general"]
    with con:
        con.execute("DELETE FROM list_gaps WHERE state = 'CT'")
        con.executemany("INSERT INTO list_gaps VALUES (?, 'CT', ?)",
                        [(r, "the Secretary of the State has not yet posted a sample ballot for any town in this district") for r in missing])
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-CT-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        for d, fname in sorted(source_of.items()):
            rec = index[fname]
            pages = next(f["pages"] for f in rec["faces"] if f["district"] == d)
            others = checked[d]
            record_source(con, f"ct-sots-2026-ballot-{slug(fname)}", path=os.path.join(folder, "ballots", fname), level="federal",
                          state="CT", kind="official sample ballot", agency="Connecticut Secretary of the State",
                          title=f"November 3, 2026, State Election, Sample Town Ballots: {rec['town']} (Congressional District {d})",
                          url=rec["url"], rows=sum(1 for r in general_rows if r[0] == house_id("CT", d)),
                          note=f"Listed on {BALLOT_PAGE}. The Representative in Congress column of the party-row ballot, read by the cell "
                               f"marks (voting-district pages {', '.join(map(str, pages))}); names, parties and offices only are printed. "
                               + (f"Checked against the same column on {len(others)} other town{'s' if len(others) > 1 else ''}' ballots, "
                                  f"which agree: {', '.join(others)}. " if others else "No other posted town's ballot carries this district yet. ")
                               + "Registered write-in candidates are not printed on the ballot and are not stored.")
        for e in prim["elections"]:
            pcode = CODES[e["party"]]
            n = sum(len(c["candidates"]) for c in e["contests"].values())
            towns = sum(len(c["towns"]) for c in e["contests"].values())
            record_source(con, f"ct-sots-2026-primary-{pcode.lower()}", path=ppath, level="federal", state="CT", kind="official results",
                          agency="Connecticut Secretary of the State",
                          title=f"Election Management System public reporting: {e['name']}, Representative in Congress",
                          url=f"{CTEMS}#/home (data: {CTEMS_DATA}election/{e['id']}/{e['version']}/)", rows=n,
                          note=f"Each candidate's statewide total (stateVotes), checked against the sum of {towns} town returns (townVotes); a "
                               f"total is stored only when every town that voted in the contest is marked \"( Official Results )\" and all its "
                               f"precincts are in. Only the printed name and party of each candidate record are read (it also carries an "
                               f"address field, never read). Connecticut primaries have no write-in line. Data version {e['version']}.")
    say(f"    Connecticut: 5 House districts (no Senate race in 2026), {len(general_rows)} candidates on the November ballot from the "
        f"sample ballots of {len(index) - len(unreadable)} towns ({sum(1 for r in general_rows if r[15])} on more than one party line); "
        f"{fields} party primaries with a field, votes from the Secretary of the State's official returns"
        + (f"; not yet official: {', '.join(unofficial)}" if unofficial else "")
        + (f"; primary winners not on the November ballot: {', '.join(not_on)}" if not_on else "")
        + (f"; no sample ballot posted yet for {', '.join(missing)}" if missing else "")
        + (f"; {len(unreadable)} town ballot{'s' if len(unreadable) > 1 else ''} set aside as unreadable" if unreadable else ""))
    for u in unreadable:
        say(f"      check: set aside, {u}")
    return len(general_rows)
