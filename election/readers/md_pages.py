"""election/readers/md_pages.py - Maryland, from the State Board of Elections' results pages (ARCHITECTURE.md 5.3,
section 7: care).

Where the figures are
  The Board posts each election's results as plain pages in a folder of its 2026 site: the June 23 primary's are in
  elections.maryland.gov/elections/2026/primary_results/. index.html lists the offices, each with one page holding every
  district (gen_results_2026_<n>.html: 1 Governor / Lt. Governor, 2 Comptroller, 3 Attorney General, 4 Representative in
  Congress, 5 State Senator, 6 House of Delegates in the primary; the numbers are read from the index, never assumed).
  A page says "Official" or "Unofficial ... Results" and "Last refreshed: MM/DD/YYYY hh:mm:ss AM" (Eastern time). The
  general election's folder is not posted yet: the registry names the folder to look for (election.nov3_id), and the
  afternoon of November 3 is when to confirm it (one request).

What is read (an allowlist): on the index, the office links; on an office page, the headings (office, "District 1A",
"<party> Candidates - Vote for N") and each table's Name, Party, Early Voting, Election Day, Mail-In Ballot,
Provisional and Total cells, and the Totals row. Nothing else.

Maryland counts mail-in ballots for days after the election: the pages carry each ballot type apart, and the store
keeps them (early, election_day, mail, provisional).

Checks made here: each candidate's ballot types add up to the Total; the candidates add up to the Totals row in every
column (a problem holds the snapshot); every table sits under an office and a district heading.

    python -m election.readers.md_pages --crosswalk     (re)build election/crosswalk/md.json from the ballot databases
    python -m election.readers.md_pages --selftest      no network: the fixture (the primary's Congress page)
    python -m election.readers.md_pages --replay        the June 23 primary's official pages against official totals
"""

import collections
import datetime as dt
import hashlib
import html as H
import json
import os
import re
import sqlite3
import sys
import unicodedata

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATE = "MD"
FEED = "md-pages"
FAMILY = "md_pages"
BASE = "https://elections.maryland.gov/elections/2026/{folder}/"
CROSSWALK = os.path.join(HERE, "election", "crosswalk", "md.json")
FIXTURE = os.path.join(HERE, "election", "fixtures", "md")
REPLAY = os.path.join(HERE, "election_cache", "md", "replay", "2026_primary")
BALLOT_US = os.path.join(HERE, "ballot_2026.sqlite")
BALLOT_LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")
OFFICES = {"Governor / Lt. Governor": "governor", "Comptroller": "comptroller", "Attorney General": "attorney_general",
           "Representative in Congress": "us_house", "State Senator": "state_senate", "House of Delegates": "state_house"}
TYPES = (("Early Voting", "early"), ("Election Day", "election_day"), ("Mail-In Ballot", "mail"), ("Provisional", "provisional"))
VOTE_TYPE_WORDS = {"early": "early voting", "election_day": "Election Day", "mail": "mail-in ballots", "provisional": "provisional ballots"}
PARTIES = {"Democratic": "DEM", "Republican": "REP", "Green": "GRN", "Libertarian": "LIB", "Unaffiliated": "UNA",
           "Working Class Party": "WCP"}
SUFFIX = {"JR", "SR", "II", "III", "IV", "V"}


def fold(s):
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(ch))


def family(name):
    n = re.sub(r"\s+and\s+.*$", "", fold(name))
    n = re.sub(r'"[^"]*"|\([^)]*\)|“[^”]*”', " ", n)
    toks = [re.sub(r"[^A-Za-z]", "", t).upper() for t in n.split()]
    toks = [t for t in toks if t and t not in SUFFIX]
    return toks[-1] if toks else ""


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", fold(name).lower()).strip("-")[:48] or "unnamed"


def text(fragment):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def ints(cell):
    t = re.sub(r"[^\d]", "", cell or "")
    return int(t) if t else 0


def eastern_to_utc(stamp):
    """'07/23/2026 11:05:33 AM' (Eastern time) -> UTC."""
    m = re.fullmatch(r"(\d\d)/(\d\d)/(\d{4}) (\d{1,2}):(\d\d):(\d\d) ([AP]M)", (stamp or "").strip())
    if not m:
        return None
    mo, d, y, h, mi, s, ap = m.groups()
    t = dt.datetime(int(y), int(mo), int(d), int(h) % 12 + (12 if ap == "PM" else 0), int(mi), int(s))

    def sunday(month, nth):
        x = dt.date(t.year, month, 1)
        x += dt.timedelta(days=(6 - x.weekday()) % 7)
        return dt.datetime.combine(x + dt.timedelta(weeks=nth - 1), dt.time(2))
    off = 4 if sunday(3, 2) <= t < sunday(11, 1) else 5
    return (t + dt.timedelta(hours=off)).isoformat(timespec="seconds") + "Z"


# ============================================================================================== the crosswalk (offline)

def build_crosswalk(path=CROSSWALK, say=print):
    races = {}
    us = sqlite3.connect(f"file:{BALLOT_US}?mode=ro", uri=True)
    for rid, district in us.execute("SELECT race_id, district FROM races WHERE state=?", (STATE,)):
        races[rid] = {"cls": "us_house", "district": str(int(district)) if district else None, "level": "congress", "names": {}}
    for rid, el, name, party, wi in us.execute("SELECT race_id, election, name, party, write_in FROM candidates WHERE race_id LIKE ?",
                                               (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, int(wi or 0)])
    loc = sqlite3.connect(f"file:{BALLOT_LOCAL}?mode=ro", uri=True)
    for rid, level, kind, district in loc.execute(
            "SELECT race_id, level, office_kind, district FROM sl_races WHERE state=? AND level IN ('statewide','legislature')", (STATE,)):
        races[rid] = {"cls": kind, "district": str(district).upper() if district else None, "level": level, "names": {}}
    for rid, el, name, party, wi in loc.execute("SELECT race_id, election, name, party, write_in FROM sl_candidates WHERE race_id LIKE ?",
                                                (f"2026-{STATE}-%",)):
        if rid in races:
            races[rid]["names"].setdefault(el, []).append([name, party, int(wi or 0)])
    doc = {"_about": "Maryland's 2026 races for Congress, the statewide offices and the General Assembly (read only from the ballot "
                     "databases) and what ties a table of the Board's results pages to each: the office class, the district, and "
                     "the candidates' names as filed for each 2026 election.",
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


def resolve(cw, cls, district):
    d = re.sub(r"^0+(?=\d)", "", (district or "").upper()) or None
    got = [r for r, e in cw["races"].items() if e["cls"] == cls and (e["district"] or None) == d]
    return (got[0], "") if len(got) == 1 else (None, f"{len(got)} 2026 races fit this office and district")


# ============================================================================================== reading pages

def office_links(index):
    """[(office title, page name)] of the offices read, from the index page."""
    out = []
    for m in re.finditer(r'(?s)<a[^>]+href="(gen_results_\d{4}_\d+\.html)"[^>]*>(.*?)</a>', index.decode("utf-8", "replace")):
        t = text(m.group(2))
        if t in OFFICES and (t, m.group(1)) not in out:
            out.append((t, m.group(1)))
    return out


def page_tables(raw, problems, label):
    """[{office, district, party, seats, heads, rows: [cells], totals: cells}] in page order; and the page's stamp."""
    page = raw.decode("utf-8", "replace")
    stamp = re.search(r"Last refreshed:\s*([\d/]+ [\d:]+ [AP]M)", page)
    official = re.search(r"\b(Unofficial|Official)\b[^<]{0,80}Results", page)
    out = []
    office = district = party = county = None
    seats = 1
    for m in re.finditer(r"(?is)<h(\d)[^>]*>(.*?)</h\1>|<table.*?</table>", page):
        if m.group(1):
            t = text(m.group(2))
            if t in OFFICES:
                office, district = t, None
            elif re.fullmatch(r"District \w+", t):
                district, party, county = t.split()[1], None, None
            elif re.fullmatch(r"[A-Z][A-Za-z'. ]+ County|Baltimore City", t):
                county = t                                  # a seat tied to a county of residence (District 36, 2026)
            else:
                mm = re.match(r"(?:(.+?) )?Candidates - Vote for (?:up to )?(\d+)", t)
                if mm:
                    party, seats = mm.group(1), int(mm.group(2))
            continue
        heads, rows, totals = None, [], None
        for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", m.group(0)):
            cells = [text(c) for c in re.findall(r"(?is)<t[hd][^>]*>(.*?)</t[hd]>", tr)]
            if cells and cells[0] == "Name":
                heads = cells
                continue
            if not heads or len(cells) != len(heads):
                continue
            row = dict(zip(heads, cells))
            (rows.append(row) if row["Name"] != "Totals" else None)
            if row["Name"] == "Totals":
                totals = row
        if heads is None:
            continue
        need = ["Name", "Party", "Total"] + [k for k, _t in TYPES]
        if any(k not in heads for k in need):
            problems.append(f"{label}: a results table without the columns {[k for k in need if k not in heads]}")
            continue
        if office is None:
            problems.append(f"{label}: a results table under no office heading")
            continue
        out.append({"office": office, "district": district, "party": party, "seats": seats, "rows": rows, "totals": totals,
                    "county": county})
    return out, (stamp.group(1) if stamp else None), (official.group(1) if official else None)


def read(files, entry):
    cw = crosswalk()
    problems, notes = [], []
    tables, stamps, words = [], [], set()
    election = None
    for name, raw in files:
        if not re.search(r"gen_results_\d{4}_\d+\.html$", name):
            continue
        t, stamp, word = page_tables(raw, problems, os.path.basename(name))
        tables += t
        if stamp:
            stamps.append(stamp)
        if word:
            words.add(word)
        if b"Primary Election Results" in raw:
            election = "primary"
    election = election or "general"
    contests, unmatched, seen = [], [], set()
    for t in tables:
        label = t["office"] + (f", District {t['district']}" if t["district"] else "") + (f" ({t['party']})" if t["party"] else "")
        cls = OFFICES[t["office"]]
        if t.get("county"):
            unmatched.append({"key": label + " " + t["county"], "office": f"{label}, {t['county']}",
                              "why": "a seat tied to a county of residence; the ballot lists hold the district as one race"})
            continue
        rid, why = resolve(cw, cls, t["district"])
        if not rid:
            unmatched.append({"key": label, "office": label, "why": why})
            continue
        race = cw["races"][rid]
        code = PARTIES.get(t["party"] or "", (t["party"] or "NP")[:3].upper())
        el = f"primary-{code}" if election == "primary" else "general"
        if election == "primary":
            rid = f"{rid}-{code.lower()}-primary"
        if rid in seen:
            unmatched.append({"key": label, "office": label, "why": "a second table tied to the same race"})
            continue
        seen.add(rid)
        filed = collections.defaultdict(list)
        for n, _p, wi in race["names"].get(el) or race["names"].get("general", []):
            filed[family(n)].append(n)
        choices, rows = [], []
        sums = collections.Counter()
        for r in t["rows"]:
            name = r["Name"]
            wi = name.lower().startswith("write-in") or name.lower() == "other write-ins"
            key = "write-in" if wi else slug(name)
            f = filed.get(family(name)) or []
            choices.append({"key": key, "name": name, "party": None if wi else (r["Party"] or None),
                            "ballot_name": f[0] if len(f) == 1 and not wi else None, "write_in": wi, "order": None})
            parts = {vt: ints(r[col]) for col, vt in TYPES}
            total = ints(r["Total"])
            if sum(parts.values()) != total:
                problems.append(f"{label}: {name}'s ballot types do not add up to the Total")
            rows.append({"unit": "all", "choice": key, "type": "total", "votes": total})
            for vt, v in parts.items():
                rows.append({"unit": "all", "choice": key, "type": vt, "votes": v})
            sums["Total"] += total
            for col, vt in TYPES:
                sums[col] += parts[vt]
        if t["totals"]:
            bad = [k for k in ["Total"] + [c for c, _v in TYPES] if ints(t["totals"][k]) != sums[k]]
            if bad:
                problems.append(f"{label}: the candidates do not add up to the Totals row ({', '.join(bad)})")
        if len({c["key"] for c in choices}) != len(choices):
            problems.append(f"{label}: two lines make the same key")
        contests.append({"race_id": rid, "key": label, "office": t["office"], "level": race["level"], "district": t["district"],
                         "seats": t["seats"], "rule": "plurality", "rcv": False, "unit_kind": "race", "units_all": None,
                         "choices": choices, "units": [{"id": "all", "kind": "race", "name": "the whole contest", "parent": None, "map_id": None}],
                         "rows": rows, "reporting": [], "stated": [{"unit": "all", "total": ints(t["totals"]["Total"])}] if t["totals"] else [],
                         "controls": []})
    newest = max((eastern_to_utc(s) for s in stamps if eastern_to_utc(s)), default=None)
    return {"state": STATE, "feed": FEED, "source_time": newest, "source_version": newest, "official": words == {"Official"},
            "contests": contests, "unmatched": unmatched, "problems": problems, "notes": notes}


# ============================================================================================== the night's requests

def base_url(entry):
    folder = (entry.get("election") or {}).get("nov3_id") or "general_results"
    if not re.fullmatch(r"[a-z_]+", folder):
        folder = "general_results"
    return BASE.format(folder=folder)


def _get(src, url):
    from election.source import Refused, SourceError
    r = src.get(url, state=STATE, accept="text/html", expect_html=True)
    if r.refused:
        raise Refused(url, r.why)
    return r


def check(src, entry):
    """The folder's index: None while it is not posted (404) or lists no office read here; else its stamp."""
    from election.source import SourceError
    url = base_url(entry) + "index.html"
    r = _get(src, url)
    if r.status == 404:
        return None
    if r.status != 200:
        raise SourceError(f"{url} answered {r.status}")
    if not office_links(r.body):
        return None
    m = re.search(rb"Last refreshed:\s*([\d/]+ [\d:]+ [AP]M)", r.body)
    stamp = m.group(1).decode() if m else hashlib.sha256(r.body).hexdigest()[:16]
    return {"version": stamp, "time": eastern_to_utc(stamp) if m else None}


def fetch(src, entry, version):
    from election.source import SourceError
    base = base_url(entry)
    r = _get(src, base + "index.html")
    if r.status != 200:
        raise SourceError(f"the index answered {r.status}")
    out = [(base + "index.html", r.body)]
    for _office, page in office_links(r.body):
        x = _get(src, base + page)
        if x.status != 200:
            raise SourceError(f"{page} answered {x.status}")
        out.append((base + page, x.body))
    return out


# ============================================================================================== tests

def _official(rid, el):
    out = []
    for db, table in ((BALLOT_US, "candidates"), (BALLOT_LOCAL, "sl_candidates")):
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        out += [v for (v,) in con.execute(f"SELECT votes FROM {table} WHERE race_id=? AND election=? AND votes IS NOT NULL", (rid, el))]
    return sorted(out)


def _store_checks(reading, say):
    from election import store
    con = store.connect(":memory:")
    checks = store.run_checks(con, reading)
    for n, p, d in checks:
        say(f"      {'ok  ' if p else 'FAIL'} {n}: {d[:150]}")
    return all(p for n, p, _d in checks if n in store.HARD)


def _files(folder):
    return [(BASE.format(folder="primary_results") + n, open(os.path.join(folder, n), "rb").read())
            for n in sorted(os.listdir(folder)) if n.endswith(".html")]


def make_fixture(say=print):
    os.makedirs(FIXTURE, exist_ok=True)
    for n in ("index.html", "gen_results_2026_4.html"):
        open(os.path.join(FIXTURE, n), "wb").write(open(os.path.join(REPLAY, n), "rb").read())
    say(f"    fixture written: {os.path.relpath(FIXTURE, HERE)}")


def _compare(rd):
    compared, same, diffs = 0, 0, []
    for c in rd["contests"]:
        base, party = re.match(r"(.+)-([a-z]+)-primary$", c["race_id"]).groups()
        off = _official(base, f"primary-{party.upper()}")
        if not off:
            continue
        compared += 1
        mine = sorted(r["votes"] for r in c["rows"] if r["type"] == "total" and r["choice"] != "write-in")
        (diffs.append(c["race_id"]) if mine != off else None)
        same += mine == off
    return compared, same, diffs


def selftest(say=print):
    ok = True

    def expect(c, what):
        nonlocal ok
        say(f"      {'ok  ' if c else 'FAIL'} {what}")
        ok = ok and bool(c)

    idx = open(os.path.join(FIXTURE, "index.html"), "rb").read()
    expect([o for o, _p in office_links(idx)][:4] == ["Governor / Lt. Governor", "Comptroller", "Attorney General", "Representative in Congress"],
           "the index's office links are read")
    rd = read(_files(FIXTURE), {})
    expect(len(rd["contests"]) == 16 and not rd["unmatched"], f"16 Congress primaries tied ({len(rd['contests'])}, {len(rd['unmatched'])} listed)")
    expect(rd["source_time"] == "2026-07-23T15:05:33Z" and rd["official"], f"the page's stamp in UTC ({rd['source_time']})")
    expect(_store_checks(rd, say), "the store's hard checks pass")
    n, same, diffs = _compare(rd)
    expect(n >= 12 and not diffs, f"every contested Congress primary equals the official totals ({same} of {n})")
    raw = re.sub(rb"19,821", b"19,822", open(os.path.join(FIXTURE, "gen_results_2026_4.html"), "rb").read(), count=1)
    rb = read([("x/gen_results_2026_4.html", raw)], {})
    expect(any("do not add up" in p for p in rb["problems"]), "a line that does not add up is a problem (held)")
    expect(eastern_to_utc("11/03/2026 09:42:00 PM") == "2026-11-04T02:42:00Z", "Eastern standard time on election night")
    return ok


def replay_test(say=print):
    """The June 23 primary's official pages (fetched once, 2026-10-10): every Congress primary equals the official totals
    the ballot database holds (from the Board's official data files); every table adds up to its Totals row."""
    rd = read(_files(REPLAY), {})
    good = _store_checks(rd, lambda s: None)
    n, same, diffs = _compare(rd)
    say(f"    2026 primary: {len(rd['contests'])} tables tied, {len(rd['unmatched'])} listed; store checks {'pass' if good else 'FAIL'}; "
        f"{same} of {n} equal the official totals" + (f"; differ: {diffs[:6]}" if diffs else "")
        + (f"; problems: {rd['problems'][:3]}" if rd["problems"] else ""))
    for w, k in collections.Counter(u["why"] for u in rd["unmatched"]).most_common():
        say(f"        listed, not shown: {k} x {w}")
    return good and not diffs and not rd["problems"] and n > 0


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
        print("    Maryland reader self-test")
        good = selftest() and good
    if a.replay:
        print("    Maryland replay test")
        good = replay_test() and good
    print("    PASS" if good else "    FAIL")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
