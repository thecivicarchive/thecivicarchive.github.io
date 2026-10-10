"""election/readers/ak_csv.py - Alaska, from the Division of Elections' own results files (ARCHITECTURE.md 5.3, section 7:
care).

Where the figures are
  The Division's results page for an election, www.elections.alaska.gov/election-results/e/?id=<code> (26genr for
  November 3, 2026; 26prim was the August 18 primary), states "Results Status: Unofficial" or "Official" and "Page last
  updated <date> at <time>", and links the night's files once the count starts:
    "Results Per Precinct"  a CSV, one row per precinct (or batch), contest and candidate (GA_ENR_Precinct_State_of_
                            Alaska.csv for the 2026 primary)
    "Summary"               the Election Summary Report PDF: each contest's "Precincts Reported: X of Y", "Times Cast"
                            and every candidate's total
  The host leaves its issuer's certificate out of the handshake; election/source.py uses the kit's one repair, which
  still requires a trusted root. Nothing here turns checking off.

What is read (an allowlist, by column name): Precinct_name, Pct_Id, Contest_title, candidate_name, Candidate_Type,
Party_Code, total_ballots, total_votes, and the votes of each ballot type (Election Day, Absentee, Early Voting,
Question, Remote). Registered-voter counts, under and over votes and every other column are not read.

Units: each precinct (its Pct_Id, "01-600"), each batch the Division counts apart (rows named "District 1 - Absentee",
"District 1 - Question", "HD99 Fed Overseas Absentee": ballots added on later count days), and the whole contest, which
is the sum of every row. Alaska has no counties; its precincts are kept in the database with no county, so no county
file is published for them.

Ranked choice: the general election's contests are ranked-choice; the files carry first choices only on the night. The
Division counts the rounds about two weeks later (the page says so). Retention votes are yes-or-no questions.

Checks made here: each row's ballot-type votes add up to its total; when the Summary was made at the same moment as the
CSV (its "Times Cast" equals the CSV's ballots for that contest), every contest's candidate totals must equal the
Summary's, or the snapshot is held; when they were made at different moments the comparison waits for the next file.

    python -m election.readers.ak_csv --crosswalk      (re)build election/crosswalk/ak.json from the ballot databases
    python -m election.readers.ak_csv --selftest       no network: a small fixture cut from the 2026 primary
    python -m election.readers.ak_csv --replay         the 2026 primary's official files against the official totals
"""

import collections
import csv
import datetime as dt
import hashlib
import html as H
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATE = "AK"
FEED = "ak-csv"
FAMILY = "ak_csv"
PAGE = "https://www.elections.alaska.gov/election-results/e/?id={id}"
CROSSWALK = os.path.join(HERE, "election", "crosswalk", "ak.json")
FIXTURE = os.path.join(HERE, "election", "fixtures", "ak")
CACHED_CSV = os.path.join(HERE, "ballot_cache", "ak", "ak_2026_primary_precinct.csv")
CACHED_PDF = os.path.join(HERE, "ballot_cache", "ak", "ak_2026_primary_summary.pdf")
CACHED_REC = os.path.join(HERE, "ballot_cache", "ak", "ak_2026_primary_results_record.json")
BALLOT_US = os.path.join(HERE, "ballot_2026.sqlite")
BALLOT_LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")

KEEP = ("Precinct_name", "Pct_Id", "Contest_title", "candidate_name", "Candidate_Type", "Party_Code", "total_ballots", "total_votes")
TYPES = (("Election Day_votes", "election_day"), ("Absentee_votes", "absentee"), ("Early Voting_votes", "early"),
         ("Question_votes", "provisional"), ("Remote_votes", "other"))
VOTE_TYPE_WORDS = {"election_day": "Election Day", "absentee": "absentee", "early": "early voting",
                   "provisional": "questioned ballots", "other": "remote"}
PRECINCT = re.compile(r"\d\d-\d{3}")
SUFFIX = {"JR", "SR", "II", "III", "IV", "V"}
COURT = (("supreme", "supreme_court_retention"), ("appeals", "court_of_appeals_retention"),
         ("superior", "superior_court_retention"), ("district", "district_court_retention"))


# ============================================================================================== small helpers

def fold(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def family(name):
    """'Sullivan, Dan S.' and 'Dan S. Sullivan' -> 'SULLIVAN'; 'Sullivan, Daniel J. Jr.' -> 'SULLIVAN'; a ticket
    ('Begich/Hnilicka') by its first name."""
    n = re.sub(r"\s*[/|].*$", "", fold(name))
    n = re.sub(r'"[^"]*"|\([^)]*\)|“[^”]*”', " ", n)
    if "," in n:
        head, tail = n.split(",", 1)
        if re.sub(r"[^A-Za-z]", "", tail).upper() not in SUFFIX:
            n = head
    toks = [re.sub(r"[^A-Za-z]", "", t).upper() for t in n.split()]
    toks = [t for t in toks if t and t not in SUFFIX]
    return toks[-1] if toks else ""


def initials(name):
    """The given names' initials, to tell apart two candidates of one family name ('Sullivan, Dan S.' -> 'DS')."""
    n = re.sub(r'"[^"]*"|\([^)]*\)|“[^”]*”', " ", fold(name))
    if "," in n:
        head, tail = n.split(",", 1)
        if re.sub(r"[^A-Za-z]", "", tail).upper() not in SUFFIX:
            n = tail
        else:
            n = head
    else:
        n = " ".join([t for t in n.split() if re.sub(r"[^A-Za-z]", "", t).upper() not in SUFFIX][:-1])
    toks = [re.sub(r"[^A-Za-z]", "", t).upper() for t in n.split()]
    return "".join(t[0] for t in toks if t and t not in SUFFIX)


def filed_name(filed, nm):
    """The name as filed for a printed name: the one list name of its family, or of its family and initials."""
    f = filed.get(family(nm)) or []
    if len(f) > 1:
        f = [x for x in f if initials(x) == initials(nm)]
    return f[0] if len(f) == 1 else None


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", fold(name).lower()).strip("-")[:48] or "unnamed"


def plain(page):
    page = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S | re.I)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", page))).strip()


def _sunday(y, m, nth):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(6 - d.weekday()) % 7)
    return d + dt.timedelta(weeks=nth - 1)


def alaska_to_utc(text):
    """'November 3, 2026 at 9:42 pm' (Alaska time) -> '2026-11-04T06:42:00Z'. Daylight time from the second Sunday of
    March to the first Sunday of November (2 a.m.)."""
    m = re.search(r"([A-Z][a-z]+ \d{1,2}, 20\d\d) at (\d{1,2}):(\d\d)\s*([ap])\.?m", text or "", re.I)
    if not m:
        return None
    day = dt.datetime.strptime(m.group(1), "%B %d, %Y")
    h = int(m.group(2)) % 12 + (12 if m.group(4).lower() == "p" else 0)
    t = day.replace(hour=h, minute=int(m.group(3)))
    dst = dt.datetime.combine(_sunday(t.year, 3, 2), dt.time(2)) <= t < dt.datetime.combine(_sunday(t.year, 11, 1), dt.time(2))
    return (t + dt.timedelta(hours=8 if dst else 9)).isoformat(timespec="seconds") + "Z"


def pdf_lines(raw):
    """(page, y, text) of a PDF given as bytes, with the kit's reader."""
    from ballot.pdftext import PDF, join, rows
    pdf = PDF(raw)
    out = []
    for n, (page, res) in enumerate(pdf.pages(), start=1):
        for y, rs in rows(pdf, page, res):
            t = join(rs)
            if t:
                out.append((n, round(y, 1), t))
    return out


# ============================================================================================== the crosswalk (offline)

def build_crosswalk(path=CROSSWALK, say=print):
    """Alaska's 2026 races (read only from the ballot databases) and what ties a contest title to each."""
    races = {}
    us = sqlite3.connect(f"file:{BALLOT_US}?mode=ro", uri=True)
    for rid, office in us.execute("SELECT race_id, office FROM races WHERE state=?", (STATE,)):
        races[rid] = {"cls": "us_senate" if office == "U.S. Senate" else "us_house", "district": None, "level": "congress",
                      "office": office, "judge": None, "names": {}}
    for rid, el, name, party, wi in us.execute("SELECT race_id, election, name, party, write_in FROM candidates WHERE race_id LIKE ?",
                                               (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, int(wi or 0)])
    loc = sqlite3.connect(f"file:{BALLOT_LOCAL}?mode=ro", uri=True)
    for rid, level, kind, office, district in loc.execute("SELECT race_id, level, office_kind, office, district FROM sl_races WHERE state=?", (STATE,)):
        judge = rid.rsplit("-", 1)[1] if kind.endswith("_retention") else None
        races[rid] = {"cls": kind, "district": str(district).upper() if district else None, "level": level, "office": office,
                      "judge": judge, "names": {}}
    for rid, el, name, party, wi in loc.execute("SELECT race_id, election, name, party, write_in FROM sl_candidates WHERE race_id LIKE ?",
                                                (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, int(wi or 0)])
    doc = {"_about": "Alaska's 2026 races (Congress from ballot_2026.sqlite, state from ballot_local_2026.sqlite, both read only) and "
                     "what ties a contest title of the Division's results files to each: the office class, the district (a House "
                     "number or a Senate letter), a retention's judge, and the candidates' names as filed for each 2026 election.",
           "state": STATE, "built": dt.date.today().isoformat(), "races": races}
    with open(path + ".part", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(path + ".part", path)
    say(f"    crosswalk: {len(races)} races -> {os.path.relpath(path, HERE)}")
    return doc


_CW = {"mtime": None, "doc": None}


def crosswalk(path=CROSSWALK):
    m = os.path.getmtime(path)
    if _CW["mtime"] != m:
        _CW["doc"], _CW["mtime"] = json.load(open(path, encoding="utf-8")), m
    return _CW["doc"]


def resolve(cw, title):
    """(race id or None, why) for a contest title."""
    t = " ".join(fold(title).split())
    low = t.lower()
    if re.match(r"(bm|ballot measure)\s*#?\s*\d", low) or "ballot measure" in low or "constitutional convention" in low:
        return None, "a ballot question, not a contest between people"
    want = None
    if low in ("u.s. senator", "united states senator"):
        want = ("us_senate", None)
    elif low in ("u.s. representative", "united states representative"):
        want = ("us_house", None)
    elif low.startswith("governor"):
        want = ("governor", None)
    else:
        m = re.fullmatch(r"(house|senate) district (\w+)", low)
        if m:
            want = ("state_house" if m.group(1) == "house" else "state_senate", m.group(2).upper())
    if want:
        got = [r for r, e in cw["races"].items() if e["cls"] == want[0] and (want[1] is None or e["district"] == want[1])]
        return (got[0], "") if len(got) == 1 else (None, f"{len(got)} 2026 races fit this title")
    kind = next((k for w, k in COURT if w in low), None)
    if kind:
        words = set(re.sub(r"[^A-Z ]", " ", t.upper()).split())
        got = [r for r, e in cw["races"].items() if e["cls"] == kind and e["judge"] and e["judge"] in words]
        return (got[0], "") if len(got) == 1 else (None, f"a retention question; {len(got)} judges on the list fit its title")
    return None, "no 2026 race on the lists has this title"


# ============================================================================================== the night's requests

def page_url(entry):
    return PAGE.format(id=(entry.get("election") or {}).get("nov3_id") or "26genr")


def _links(page_bytes, base):
    page = page_bytes.decode("utf-8", "replace")
    out = {}
    for href, lab in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        out.setdefault(plain(lab), urljoin(base, H.unescape(href)))
    return out


def _signal(page_bytes):
    p = plain(page_bytes.decode("utf-8", "replace"))
    status = re.search(r"Results Status:\s*(\w+)", p)
    upd = re.search(r"Page last updated ([A-Z][a-z]+ \d{1,2}, 20\d\d at \d{1,2}:\d\d\s*[ap]\.?m\.?(?:\s*\(step \d+\))?)", p, re.I)
    return (status.group(1) if status else None), (upd.group(1).strip() if upd else None)


def _get(src, url, accept, expect_html=False):
    from election.source import Refused, SourceError
    r = src.get(url, state=STATE, accept=accept, expect_html=expect_html)
    if r.refused:
        raise Refused(url, r.why)
    if r.status != 200:
        raise SourceError(f"{url} answered {r.status}")
    return r


def check(src, entry):
    """The results page: None until it links the precinct file; else its version (status and last-updated words)."""
    url = page_url(entry)
    r = _get(src, url, "text/html", expect_html=True)
    links = _links(r.body, url)
    if "Results Per Precinct" not in links:
        return None
    status, upd = _signal(r.body)
    return {"version": f"{status}|{upd}|{links['Results Per Precinct']}", "time": alaska_to_utc(upd)}


def fetch(src, entry, version):
    """The page, the precinct CSV and the Summary PDF (when linked)."""
    url = page_url(entry)
    page = _get(src, url, "text/html", expect_html=True)
    links = _links(page.body, url)
    out = [(url, page.body)]
    if "Results Per Precinct" not in links:
        return []
    out.append((links["Results Per Precinct"], _get(src, links["Results Per Precinct"], "text/csv,*/*").body))
    if "Summary" in links:
        out.append((links["Summary"], _get(src, links["Summary"], "application/pdf,*/*").body))
    return out


# ============================================================================================== reading

def summary(raw):
    """{title: {"in", "all", "cast", "figures": sorted votes, "total"}} from the Summary PDF; {} when it does not read."""
    try:
        got = pdf_lines(raw)
    except Exception:  # noqa: BLE001 - an optional control: the CSV is read without it
        return {}
    out, cur = {}, None
    for _p, _y, t in got:
        m = re.fullmatch(r"(.+?) \(Vote for (\d+)\)", t)
        if m:
            cur = out.setdefault(m.group(1).strip(), {"in": None, "all": None, "cast": None, "figures": [], "total": None})
            continue
        if cur is None:
            continue
        m = re.search(r"Precincts Reported: ([\d,]+) of ([\d,]+)", t)
        if m and cur["in"] is None:
            cur["in"], cur["all"] = (int(x.replace(",", "")) for x in m.groups())
            continue
        m = re.match(r"Times Cast ([\d,]+) /", t)
        if m:
            cur["cast"] = int(m.group(1).replace(",", ""))
            continue
        m = re.fullmatch(r"Total Votes ([\d,]+)", t)
        if m:
            cur["total"] = int(m.group(1).replace(",", ""))
            cur = None
            continue
        m = re.search(r"(?:^| )([\d,]+) (\d{1,3}\.\d\d)%$", t)
        if m and not t.startswith(("Times Cast", "Precincts Reported", "Voters Cast")):
            cur["figures"].append(int(m.group(1).replace(",", "")))
    return out


def read(files, entry):
    """The reading of one fetch: [(address, bytes)] (the page, the CSV, the Summary)."""
    cw = crosswalk()
    problems, notes = [], []
    page = next((b for n, b in files if "election-results/e/" in n), None)
    csv_raw = next((b for n, b in files if b.lstrip(b"\xef\xbb\xbf")[:14] == b"Precinct_name,"), None)
    pdf_raw = next((b for n, b in files if b[:4] == b"%PDF"), None)
    status, upd = _signal(page) if page else (None, None)
    nov3 = (entry.get("election") or {}).get("nov3_id") or "26genr"
    election = "primary" if nov3.endswith("prim") else "general"
    if csv_raw is None:
        return {"state": STATE, "feed": FEED, "contests": [], "unmatched": [], "problems": ["no precinct results file among the files"]}
    rd = csv.reader(io.StringIO(csv_raw.decode("utf-8-sig", "replace")))
    heads = [h.strip() for h in next(rd)]
    missing = [k for k in KEEP + tuple(c for c, _t in TYPES) if heads.count(k) != 1]
    if missing:
        return {"state": STATE, "feed": FEED, "contests": [], "unmatched": [],
                "problems": [f"the precinct file's columns changed: {', '.join(missing)} not found once"]}
    idx = {k: heads.index(k) for k in KEEP + tuple(c for c, _t in TYPES)}
    by = collections.defaultdict(list)
    for n, r in enumerate(rd, 2):
        if not r or not any(x.strip() for x in r):
            continue
        try:
            row = {k: r[i].strip() for k, i in idx.items()}
            for k in ("total_ballots", "total_votes") + tuple(c for c, _t in TYPES):
                row[k] = int(row[k] or 0)
        except (IndexError, ValueError):
            problems.append(f"precinct file line {n}: not the file's layout")
            continue
        if sum(row[c] for c, _t in TYPES) != row["total_votes"]:
            problems.append(f"precinct file line {n}: the ballot types' votes do not add up to the row's total")
        if row["Candidate_Type"] not in ("C", "W"):
            problems.append(f"precinct file line {n}: a candidate type not known here ({row['Candidate_Type']!r})")
        by[row["Contest_title"]].append(row)
    summ = summary(pdf_raw) if pdf_raw else {}
    if pdf_raw and not summ:
        notes.append("the Summary did not read; the precinct file is read without it")
    contests, unmatched = [], []
    for title, rows in sorted(by.items()):
        rid, why = resolve(cw, title)
        if not rid:
            unmatched.append({"key": title, "office": title, "why": why})
            continue
        race = cw["races"][rid]
        el = "primary" if election == "primary" else "general"
        filed = collections.defaultdict(list)
        for n_, _p, wi in race["names"].get(el) or race["names"].get("general", []):
            filed[family(n_)].append(n_)
        choices, keys = {}, {}
        for r in rows:
            nm = re.sub(r"\s+", " ", r["candidate_name"]).strip()
            wi = r["Candidate_Type"] == "W" or nm.lower().startswith("write-in")
            k = "write-in" if wi and nm.lower().startswith("write") else slug(nm)
            keys[r["candidate_name"]] = k
            if k not in choices:
                choices[k] = {"key": k, "name": nm, "party": r["Party_Code"] or None, "ballot_name": filed_name(filed, nm),
                              "write_in": wi, "order": None}
        units, vals, typed, ballots = {}, collections.Counter(), collections.Counter(), collections.defaultdict(int)
        units["all"] = {"id": "all", "kind": "race", "name": "the whole contest", "parent": None, "map_id": None}
        for r in rows:
            real = bool(PRECINCT.fullmatch(r["Pct_Id"]))
            uid = r["Pct_Id"] if real else "AK-" + slug(r["Precinct_name"])
            units.setdefault(uid, {"id": uid, "kind": "precinct" if real else "batch", "name": r["Precinct_name"], "parent": None, "map_id": None})
            k = keys[r["candidate_name"]]
            vals[(uid, k)] += r["total_votes"]
            vals[("all", k)] += r["total_votes"]
            for c, t in TYPES:
                typed[(k, t)] += r[c]
            ballots[uid] = max(ballots[uid], r["total_ballots"])
        real_units = [u for u, x in units.items() if x["kind"] == "precinct"]
        p_in = sum(1 for u in real_units if ballots[u] > 0)
        s = summ.get(title)
        rep_all = (s["in"], s["all"]) if s and s["in"] is not None else (p_in, len(real_units))
        if s and s["cast"] is not None:
            if s["cast"] == sum(ballots.values()):
                mine = sorted(v for (u, _k), v in vals.items() if u == "all")
                if sorted(s["figures"]) != mine:
                    problems.append(f"{title}: the precinct file's totals differ from the Summary's made at the same moment")
            else:
                notes.append(f"{title}: the Summary and the precinct file were made at different moments; not compared this time")
        out_rows = [{"unit": u, "choice": k, "type": "total", "votes": v} for (u, k), v in sorted(vals.items())]
        out_rows += [{"unit": "all", "choice": k, "type": t, "votes": v} for (k, t), v in sorted(typed.items())]
        reporting = [{"unit": "all", "in": rep_all[0], "all": rep_all[1], "ballots": sum(ballots.values())}]
        reporting += [{"unit": u, "in": 1 if ballots[u] > 0 else 0, "all": 1, "ballots": ballots[u]} for u in sorted(real_units)]
        rcv = election == "general" and race["cls"] in ("us_senate", "us_house", "governor", "state_house", "state_senate")
        contests.append({"race_id": rid, "key": title, "office": title, "level": race["level"], "district": race["district"], "seats": 1,
                         "rule": "ranked_choice" if rcv else "plurality", "rcv": rcv, "unit_kind": "precinct",
                         "units_all": rep_all[1], "choices": list(choices.values()), "units": list(units.values()),
                         "rows": out_rows, "reporting": reporting, "stated": [], "controls": []})
    return {"state": STATE, "feed": FEED, "source_time": alaska_to_utc(upd), "source_version": upd, "official": status == "Official",
            "contests": contests, "unmatched": unmatched, "problems": problems, "notes": notes}


# ============================================================================================== rehearsals

def units(files):
    """[(unit id, None, ballots)] of the final files, for a replay's reporting order."""
    raw = next((b for n, b in files.items() if b.lstrip(b"\xef\xbb\xbf")[:14] == b"Precinct_name,"), b"")
    rd = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", "replace")))
    size = collections.defaultdict(int)
    for r in rd:
        size[r["Precinct_name"]] = max(size[r["Precinct_name"]], int(r["total_ballots"] or 0))
    return [(u, None, n) for u, n in sorted(size.items())]


def reveal(files, keep, step):
    """The final files as they would have stood with only the units in `keep` counted: other rows' figures are zero, the
    Summary is left out (its totals are the final ones), and the page's last-updated words carry the step."""
    out = {}
    for rel, b in files.items():
        if b[:4] == b"%PDF":
            continue
        if b.lstrip(b"\xef\xbb\xbf")[:14] == b"Precinct_name,":
            rd = csv.reader(io.StringIO(b.decode("utf-8-sig", "replace")))
            heads = next(rd)
            num = [i for i, h in enumerate(heads) if h.endswith(("_ballots", "_votes"))]
            bio = io.StringIO()
            w = csv.writer(bio, lineterminator="\r\n")
            w.writerow(heads)
            for r in rd:
                if r and r[0] not in keep:
                    r = [("0" if i in num else x) for i, x in enumerate(r)]
                w.writerow(r)
            out[rel] = bio.getvalue().encode("utf-8")
        elif b"Page last updated" in b:
            out[rel] = re.sub(rb"(Page last updated [^<]*?[ap]\.?m\.?)", lambda m: m.group(1) + f" (step {step})".encode(), b, count=1)
        else:
            out[rel] = b
    return out


# ============================================================================================== tests

def _official(rid, el="primary"):
    """The official figures the ballot databases hold for a race, as a sorted list of votes."""
    out = []
    for db, table in ((BALLOT_US, "candidates"), (BALLOT_LOCAL, "sl_candidates")):
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        out += [v for (v,) in con.execute(f"SELECT votes FROM {table} WHERE race_id=? AND election=? AND votes IS NOT NULL", (rid, el))]
    return sorted(out)


def _totals(c):
    return sorted(r["votes"] for r in c["rows"] if r["unit"] == "all" and r["type"] == "total")


def _store_checks(reading, say):
    from election import store
    con = store.connect(":memory:")
    checks = store.run_checks(con, reading)
    for n, p, d in checks:
        say(f"      {'ok  ' if p else 'FAIL'} {n}: {d[:150]}")
    return all(p for n, p, _d in checks if n in store.HARD)


def _primary_files():
    rec = json.load(open(CACHED_REC, encoding="utf-8"))
    page = (b"<html><body>2026 Primary Election - August 18, 2026 Results Status: Official Page last updated August 31, 2026 at 2:53 pm "
            b'<a href="' + rec["csv"].encode() + b'">Results Per Precinct</a> <a href="' + rec["pdf"].encode() + b'">Summary</a></body></html>')
    return [(PAGE.format(id="26prim"), page), (rec["csv"], open(CACHED_CSV, "rb").read()), (rec["pdf"], open(CACHED_PDF, "rb").read())]


def make_fixture(say=print):
    """House District 1's rows of the 2026 primary's official file (public results), with the U.S. Senate and ballot
    measure rows of that district's precincts and batches, in the columns the reader takes only; and a page."""
    os.makedirs(FIXTURE, exist_ok=True)
    files = _primary_files()
    rd = csv.reader(io.StringIO(files[1][1].decode("utf-8-sig")))
    heads = [h.strip() for h in next(rd)]
    cols = [heads.index(k) for k in KEEP + tuple(c for c, _t in TYPES)]
    bio = io.StringIO()
    w = csv.writer(bio, lineterminator="\r\n")
    w.writerow([heads[i] for i in cols])
    for r in rd:
        d1 = r[2].startswith("01-") or r[0].startswith("District 1 -")
        if r[8] == "House District 1" or (d1 and r[8] in ("U.S. Senator", "BM#1 23RCF2")):
            w.writerow([r[i] for i in cols])
    open(os.path.join(FIXTURE, "precinct.csv"), "w", encoding="utf-8", newline="").write(bio.getvalue())
    open(os.path.join(FIXTURE, "page.html"), "wb").write(files[0][1])
    say(f"    fixture written: {os.path.relpath(FIXTURE, HERE)}")


def selftest(say=print):
    """No network: the fixture's page is read for its signal, its rows are tied to races, and a row whose ballot types do
    not add up holds the snapshot."""
    ok = True

    def expect(c, what):
        nonlocal ok
        say(f"      {'ok  ' if c else 'FAIL'} {what}")
        ok = ok and bool(c)

    page = open(os.path.join(FIXTURE, "page.html"), "rb").read()
    body = open(os.path.join(FIXTURE, "precinct.csv"), "rb").read()
    st, upd = _signal(page)
    expect(st == "Official" and alaska_to_utc(upd) == "2026-08-31T22:53:00Z", f"the page's status and time ({st}, {alaska_to_utc(upd)})")
    expect(alaska_to_utc("November 3, 2026 at 9:42 pm") == "2026-11-04T06:42:00Z", "Alaska standard time on election night")
    entry = {"election": {"nov3_id": "26prim"}}
    rd = read([(PAGE.format(id="26prim"), page), ("x.csv", body)], entry)
    ids = sorted(c["race_id"] for c in rd["contests"])
    expect(ids == ["2026-AK-S2", "2026-AK-SH1"], f"contests tied to their races ({ids})")
    expect([u["why"] for u in rd["unmatched"]] == ["a ballot question, not a contest between people"], "the ballot measure is listed, not shown")
    expect(_store_checks(rd, say), "the store's hard checks pass")
    sen = next(c for c in rd["contests"] if c["race_id"] == "2026-AK-S2")
    hd1 = next(c for c in rd["contests"] if c["race_id"] == "2026-AK-SH1")
    expect(_totals(hd1) == _official("2026-AK-SH1"), "House District 1's primary totals equal the official figures")
    expect(all(ch["ballot_name"] for ch in sen["choices"]), "each line carries its name as filed, the two Sullivans apart")
    lines = body.decode("utf-8").splitlines(True)
    cells = next(csv.reader([lines[1]]))
    cells[7] = str(int(cells[7]) + 3)                                       # total_votes
    bad = (lines[0] + ",".join(f'"{x}"' for x in cells) + "\n" + "".join(lines[2:])).encode()
    rb = read([(PAGE.format(id="26prim"), page), ("x.csv", bad)], entry)
    expect(any("do not add up" in p for p in rb["problems"]), "a row whose ballot types do not add up is a problem (held)")
    rv = reveal({"p": page, "c": body}, set(), 3)
    expect(b"(step 3)" in rv["p"] and _signal(rv["p"])[1].endswith("(step 3)"), "a rehearsal step changes the page's version")
    return ok


def replay_test(say=print):
    """The 2026 primary's official files (cached by the ballot loader from the Division's page): every contest tied to a
    race equals the official totals the ballot databases hold (read from the Division's official Summary), and the
    Summary control passes."""
    entry = {"election": {"nov3_id": "26prim"}}
    rd = read(_primary_files(), entry)
    good = _store_checks(rd, lambda s: None)
    compared, same, diffs = 0, 0, []
    for c in rd["contests"]:
        off = _official(c["race_id"])
        if not off:
            continue
        compared += 1
        if _totals(c) == off:
            same += 1
        else:
            diffs.append(c["race_id"])
    say(f"    26prim: {len(rd['contests'])} contests tied, {len(rd['unmatched'])} listed; store checks {'pass' if good else 'FAIL'}; "
        f"{same} of {compared} equal the official totals" + (f"; differ: {diffs[:6]}" if diffs else "")
        + (f"; problems: {rd['problems'][:3]}" if rd["problems"] else "") + (f"; notes: {rd['notes'][:2]}" if rd["notes"] else ""))
    for u in rd["unmatched"]:
        say(f"        listed, not shown: {u['office']} ({u['why']})")
    return good and not diffs and not rd["problems"] and compared > 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for f in ("crosswalk", "fixture", "selftest", "replay"):
        ap.add_argument("--" + f, action="store_true")
    a = ap.parse_args(argv)
    good = True
    if a.crosswalk:
        build_crosswalk()
    if a.fixture:
        make_fixture()
    if a.selftest:
        print("    Alaska reader self-test")
        good = selftest() and good
    if a.replay:
        print("    Alaska replay test")
        good = replay_test() and good
    print("    PASS" if good else "    FAIL")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
