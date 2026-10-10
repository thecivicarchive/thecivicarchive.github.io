"""election/readers/_common_n11.py - what the six state-built readers share (civix, ca_api, fl_watch, pa_returns, nc_sbe,
la_portal): the races each may tie a contest to, matching a printed name to the name as filed, county names to their
five-digit codes, the crosswalk files, and the shape of a contest in a reading (election/store.py's run_checks says it).

Nothing here makes a request. The ballot databases are opened read only.

Which races a reader may tie a contest to (SCOPE): Congress (ballot_2026.sqlite), and from ballot_local_2026.sqlite the
statewide offices, the Legislature and the state's appellate and supreme courts. A contest of any other kind (a county
office, a city, a ballot question) is listed in the reading's "unmatched" with the reason, never shown.

A contest is tied to a race by what it is (its kind and district: "us_house:7", "governor", "state_senate:22"), which
the reader reads from the state's own title; then each line of the contest is tied to one candidate on the list by the
family name (and given names when two share one). A line that ties to nobody is kept, with its name as printed, and the
crosswalk lists it; nothing is guessed.
"""

import datetime as dt
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election import store  # noqa: E402

BALLOT_US = os.path.join(HERE, "ballot_2026.sqlite")
BALLOT_LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")
CROSSWALK_DIR = os.path.join(HERE, "election", "crosswalk")
FIXTURE_DIR = os.path.join(HERE, "election", "fixtures")
REPLAY_SOURCES = os.path.join(HERE, "election_cache", "replay", "sources")
COUNTY_ZIP = os.path.join(HERE, "states_cache", "census", "cb_2024_us_county_500k.zip")
NOV3 = "2026-11-03"
UTC = dt.timezone.utc

STATE_FIPS = {"TX": "48", "CA": "06", "FL": "12", "PA": "42", "NC": "37", "LA": "22"}
COURT_KINDS = {"supreme_court", "supreme_court_retention", "court_of_appeals", "court_of_appeals_retention",
               "court_of_criminal_appeals"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "md", "phd", "esq", "dr"}
WRITE_IN = re.compile(r"write[- ]?in", re.I)

# ---------------------------------------------------------------------------------------------- names


def fold(text):
    t = unicodedata.normalize("NFKD", str(text or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]+", " ", t.lower().replace("'", "")).split()


def name_words(name):
    """(given words, family name) of a printed or filed name: 'LAST, FIRST' or 'First "Nick" Last Jr.'; suffixes and an
    incumbent's mark "(I)" set aside; the family name is the last word (so 'Mucarsel-Powell' gives 'powell' on both sides)."""
    raw = str(name or "").split(" / ")[0]                                      # a ticket: "Governor / Lieutenant Governor"
    raw = re.sub(r"\((i|inc|incumbent)\)", " ", raw, flags=re.I)
    raw = re.sub(r"\((?:[A-Z]{2,6})\)\s*$", " ", raw)                          # a party tag: "(REP)"
    head, _, tail = raw.rpartition(",")
    if head and tail.strip() and all(w in SUFFIXES for w in fold(tail)):
        raw = head
    if "," in raw:
        last, _, first = raw.partition(",")
        fam = [w for w in fold(last) if w not in SUFFIXES]
        giv = [w for w in fold(first) if w not in SUFFIXES]
        return giv, (fam[-1] if fam else "")
    w = [x for x in fold(raw) if x not in SUFFIXES]
    return (w[:-1], w[-1]) if w else ([], "")


def name_key(name):
    giv, fam = name_words(name)
    return " ".join(giv + [fam]).strip()


def tie_names(printed, listed):
    """{printed name: the listed name it is, or None}. A printed name ties to the one listed name with the same family
    name; when several share it, to the one whose given names (or first letters) fit. Never two printed names to one."""
    out, used = {}, set()
    lw = {n: name_words(n) for n in listed}
    for p in printed:
        if WRITE_IN.search(p or "") and not re.search(r"\(write[- ]?in\)", p or "", re.I):
            out[p] = None                                       # the write-in line itself, not a person
            continue
        giv, fam = name_words(p)
        hits = [n for n, (g, f) in lw.items() if f == fam and fam]
        if len(hits) > 1:
            fit = [n for n in hits if set(giv) & set(lw[n][0])]
            if len(fit) != 1:
                fit = [n for n in hits if giv and lw[n][0] and giv[0][0] == lw[n][0][0]]
            hits = fit
        if not hits and len(fam) > 2:                           # a family name of two words printed together: "DE LA CRUZ"
            joined = "".join(fold(p))
            hits = [n for n, (g, f) in lw.items() if f and f in joined and any(x in fold(p) for x in g)]
        out[p] = hits[0] if len(hits) == 1 and hits[0] not in used else None
        if out[p]:
            used.add(out[p])
    return out


def choice_key(name):
    return store.slug(re.sub(r"\s*\((i|inc|incumbent)\)\s*", " ", str(name or ""), flags=re.I).strip())


def clean_printed(name):
    """The name as the state printed it, without the incumbent's mark and doubled spaces."""
    return re.sub(r"\s+", " ", re.sub(r"\s*\((i|inc|incumbent)\)\s*", " ", str(name or ""), flags=re.I)).strip()


# ---------------------------------------------------------------------------------------------- the races


def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def ballot_races(code, levels=("congress", "statewide", "legislature", "court"), court_kinds=COURT_KINDS):
    """{race id: {level, kind, office, district, seat, special, names: [[name as filed, party, order, write-in], ...]}}
    for the races of the state on the November 3 ballot that these readers may tie a contest to."""
    out = {}
    if "congress" in levels and os.path.exists(BALLOT_US):
        us = _ro(BALLOT_US)
        for rid, office, district, special in us.execute("SELECT race_id, office, district, special FROM races WHERE state=?", (code,)):
            kind = "us_senate" if "Senate" in office else "us_house"
            out[rid] = {"level": "congress", "kind": kind, "office": office, "district": (str(int(district)) if district and
                        str(district).isdigit() else district), "seat": None, "special": special or 0, "names": []}
        for rid, name, party, order, wi in us.execute("SELECT race_id, name, party, ballot_order, write_in FROM candidates WHERE race_id LIKE ? "
                                                      "AND election_date=? ORDER BY race_id, COALESCE(ballot_order, 999), name",
                                                      (f"2026-{code}-%", NOV3)):
            if rid in out:
                out[rid]["names"].append([name, party, order, wi or 0])
        us.close()
    if os.path.exists(BALLOT_LOCAL):
        lo = _ro(BALLOT_LOCAL)
        want = [lv for lv in levels if lv != "congress"]
        q = ",".join("?" * len(want))
        for rid, level, kind, office, district, seat, special in lo.execute(
                f"SELECT race_id, level, office_kind, office, district, seat, special FROM sl_races WHERE state=? AND level IN ({q})",
                (code, *want)):
            if level == "court" and kind not in court_kinds:
                continue
            out[rid] = {"level": level, "kind": kind, "office": office, "district": district, "seat": seat, "special": special or 0,
                        "names": []}
        for rid, name, party, order, wi in lo.execute("SELECT race_id, name, party, ballot_order, write_in FROM sl_candidates WHERE race_id LIKE ? "
                                                      "AND election_date=? ORDER BY race_id, COALESCE(ballot_order, 999), name",
                                                      (f"2026-{code}-%", NOV3)):
            if rid in out:
                out[rid]["names"].append([name, party, order, wi or 0])
        lo.close()
    return out


def num(s):
    """'07' -> '7', '22' -> '22', 'Place 3' -> '3', 'Seat 01' -> '1', None -> ''."""
    m = re.search(r"\d+", str(s or ""))
    return str(int(m.group(0))) if m else ""


def race_key(r):
    """The key a reader's contest key is compared with, from a race of ballot_races."""
    k = r["kind"]
    if k == "us_house":
        return f"us_house:{num(r['district'])}"
    if k == "us_senate":
        return "us_senate:special" if r["special"] else "us_senate"
    if k in ("state_house", "state_senate", "state_board_of_education", "board_of_equalization", "public_service_commissioner"):
        return f"{k}:{num(r['district'])}"
    if k in ("supreme_court", "court_of_criminal_appeals"):
        seat = "chief" if "chief" in str(r["seat"] or "").lower() else (num(r["seat"]) or num(r["district"]))
        return f"{k}:{seat}" + (":unexpired" if r["special"] else "")
    if k == "court_of_appeals":
        return f"{k}:{r['district'] or ''}:{(r['seat'] or '').lower()}" + (":unexpired" if r["special"] else "")
    if k.endswith("_retention"):                    # a yes-or-no vote on one judge: keyed by the judge's family name
        fam = name_words(r["names"][0][0])[1] if r.get("names") else ""
        return f"{k}:{fam}"
    return k


# ---------------------------------------------------------------------------------------------- counties


_COUNTIES = {}


def county_norm(name):
    w = fold(re.sub(r"\b(county|parish)\b", " ", str(name or ""), flags=re.I).replace("St.", "Saint").replace("Ste.", "Sainte"))
    w = ["saint" if x in ("st", "ste") else x for x in w]
    return "".join(w)


def counties(code):
    """{folded county name: five-digit code} for a state, from the Census Bureau's county file already on disk."""
    if code in _COUNTIES:
        return _COUNTIES[code]
    import shapefile
    fips = STATE_FIPS.get(code)
    out = {}
    with zipfile.ZipFile(COUNTY_ZIP) as z:
        base = next(n for n in z.namelist() if n.endswith(".dbf"))
        rdr = shapefile.Reader(dbf=io.BytesIO(z.read(base)))
        for rec in rdr.iterRecords():
            r = rec.as_dict()
            if r["STATEFP"] == fips:
                out[county_norm(r["NAME"])] = r["GEOID"]
    _COUNTIES[code] = out
    return out


def county_unit(code, name):
    return counties(code).get(county_norm(name))


# ---------------------------------------------------------------------------------------------- crosswalk files


def crosswalk_path(code):
    return os.path.join(CROSSWALK_DIR, f"{code.lower()}.json")


_CW = {}


def load_crosswalk(code):
    p = crosswalk_path(code)
    mt = os.path.getmtime(p) if os.path.exists(p) else None
    if code in _CW and _CW[code][0] == mt:
        return _CW[code][1]
    doc = json.load(open(p, encoding="utf-8")) if mt else {"races": {}, "keys": {}}
    _CW[code] = (mt, doc)
    return doc


def build_crosswalk(code, feed_name, describe, feed_contests=None, feed_note="", say=print,
                    levels=("congress", "statewide", "legislature", "court")):
    """crosswalk/<code>.json: every race in scope with its key and its candidates as filed; the key -> race map; and,
    when the state has posted its Nov 3 contest list (feed_contests: [{id, title, key, names}]), each posted contest
    tied to its race and its printed names tied to the list, with everything that did not tie listed."""
    races = ballot_races(code, levels=levels)
    keys, dup = {}, []
    for rid, r in sorted(races.items()):
        k = race_key(r)
        if k in keys:
            dup.append(f"{k}: {keys[k]} and {rid}")
            keys[k] = None
        else:
            keys[k] = rid
    posted, not_tied, lines_not_tied, scope_out = {}, [], [], []
    seen = set()
    for c in feed_contests or []:
        if not c.get("key"):
            scope_out.append({"id": c["id"], "title": c["title"], "why": c.get("why") or "not a contest these pages read (local office, question or other)"})
            continue
        rid = keys.get(c["key"])
        if not rid:
            not_tied.append({"id": c["id"], "title": c["title"], "key": c["key"],
                             "why": "two races share this key" if c["key"] in keys else "no race on the 2026 lists has this key"})
            continue
        seen.add(rid)
        tied = tie_names(c.get("names") or [], [n[0] for n in races[rid]["names"]])
        posted[str(c["id"])] = {"race": rid, "title": c["title"], "names": tied}
        for p, n in tied.items():
            if n is None and not WRITE_IN.search(p):
                lines_not_tied.append({"race": rid, "printed": p, "why": "no candidate on the list has this family name"})
    missing = [{"race": rid, "key": race_key(r), "why": ("one candidate filed for it (unopposed), so the state's list of contests "
                                                         "does not carry it" if len(r["names"]) == 1 else
                                                         "the state's posted contest list has no contest with this key")}
               for rid, r in sorted(races.items()) if feed_contests and rid not in seen]
    doc = {
        "_about": describe,
        "state": code,
        "election": NOV3,
        "built": dt.date.today().isoformat(),
        "feed": feed_name,
        "feed_note": feed_note,
        "order": ["what the contest is (its kind and district, read from the state's own title)", "the candidates' family names"],
        "counts": {"races": len(races), "by_level": {lv: sum(1 for r in races.values() if r["level"] == lv) for lv in
                                                     ("congress", "statewide", "legislature", "court")},
                   "posted_contests": len(feed_contests or []), "posted_tied": len(posted), "posted_not_tied": len(not_tied),
                   "posted_out_of_scope": len(scope_out), "races_not_in_posted_list": len(missing),
                   "printed_lines_not_tied": len(lines_not_tied)},
        "races": {rid: {"key": race_key(r), "level": r["level"], "kind": r["kind"], "office": r["office"], "district": r["district"],
                        "seat": r["seat"], "special": r["special"], "names": [[n[0], n[1]] for n in r["names"]]}
                  for rid, r in sorted(races.items())},
        "keys": {k: v for k, v in sorted(keys.items()) if v},
        "keys_shared": dup,
        "posted": posted,
        "posted_not_tied": not_tied,
        "races_not_in_posted_list": missing,
        "printed_lines_not_tied": lines_not_tied,
        "posted_out_of_scope": scope_out[:400],
    }
    os.makedirs(CROSSWALK_DIR, exist_ok=True)
    with open(crosswalk_path(code), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=0, separators=(",", ":"))
    _CW.pop(code, None)
    say(f"    {code} crosswalk: {len(races)} races in scope ({', '.join(f'{v} {k}' for k, v in doc['counts']['by_level'].items())}); "
        f"posted contests {len(feed_contests or [])}: {len(posted)} tied, {len(not_tied)} not tied, {len(scope_out)} out of scope; "
        f"races not in the posted list {len(missing)}; printed names not tied {len(lines_not_tied)}; shared keys {len(dup)}")
    return doc


# ---------------------------------------------------------------------------------------------- a contest in a reading


class Contests:
    """Collects a reading's contests. Each contest is tied to its race through the crosswalk's keys; on the Nov 3
    election each printed name is tied to the list (past elections, read for rehearsals, keep their printed names)."""

    def __init__(self, code, nov3=True):
        self.code, self.nov3 = code, nov3
        cw = load_crosswalk(code)
        self.keys, self.races = cw.get("keys", {}), cw.get("races", {})
        self.c, self.unmatched, self.problems, self.notes = {}, [], [], []
        self._listed = set()

    def _list(self, feed_key, title, why):
        if (str(feed_key), title) not in self._listed:
            self._listed.add((str(feed_key), title))
            self.unmatched.append({"key": str(feed_key), "office": title, "why": why})

    def race_for(self, key, title, feed_key):
        if not key:
            self._list(feed_key, title, "not a contest these pages read (local office, question or other)")
            return None
        rid = self.keys.get(key)
        if not rid and key == "us_senate":                  # the state's title does not say "unexpired term" for a special
            sen = [k for k in self.keys if k.startswith("us_senate")]
            rid = self.keys[sen[0]] if len(sen) == 1 else None
        if not rid and not key.endswith(":unexpired") and key + ":unexpired" in self.keys:
            rid = self.keys[key + ":unexpired"]             # the only race for that seat is for the rest of a term
        if not rid:
            why = ("not on the 2026 ballot (a past election's contest, read for a rehearsal)" if not self.nov3 else
                   "no race on the 2026 lists has this office and district")
            self._list(feed_key, title, why)
            return None
        return rid

    def contest(self, rid, feed_key, office, rule="plurality", unit_kind="county", seats=1):
        if rid in self.c:
            return self.c[rid]
        r = self.races.get(rid, {})
        c = {"race_id": rid, "key": str(feed_key), "office": office, "level": r.get("level"), "district": r.get("district"),
             "seats": seats, "rule": rule, "rcv": False, "unit_kind": unit_kind, "units_all": None,
             "choices": [], "units": [], "rows": [], "reporting": [], "stated": [], "controls": [],
             "_ck": {}, "_units": {}}
        self.c[rid] = c
        return c

    def choice(self, c, printed, party=None, order=None, write_in=None):
        """The choice key of a printed name in contest c (added once)."""
        name = clean_printed(printed)
        if name in c["_ck"]:
            return c["_ck"][name]
        key = choice_key(name)
        used = {ch["key"] for ch in c["choices"]}
        k, i = key, 2
        while k in used:
            k, i = f"{key}-{i}", i + 1
        listed = None
        filed_order = None
        wi = bool(write_in) if write_in is not None else bool(re.search(r"write[- ]?in", name, re.I))
        if self.nov3 and not (wi and not re.search(r"\(write[- ]?in\)", name, re.I)):
            names = self.races.get(c["race_id"], {}).get("names") or []
            tied = tie_names([name], [n[0] for n in names]).get(name)
            if tied:
                listed = tied
                filed_order = next((i for i, n in enumerate(names) if n[0] == tied), None)
            else:
                self.notes.append(f"{c['race_id']}: the printed name {name!r} ties to no candidate on the list")
        c["choices"].append({"key": k, "name": name, "party": party or None, "ballot_name": listed, "write_in": wi,
                             "order": (filed_order + 1) if filed_order is not None else order})
        c["_ck"][name] = k
        return k

    def unit(self, c, uid, kind, name=None, parent=None, map_id=None):
        if uid not in c["_units"]:
            c["_units"][uid] = {"id": uid, "kind": kind, "name": name, "parent": parent, "map_id": map_id}

    def row(self, c, unit, choice, votes, vtype="total"):
        c["rows"].append({"unit": unit, "choice": choice, "type": vtype, "votes": int(votes)})

    def report(self, c, unit, n_in, n_all, ballots=None, registered=None):
        c["reporting"].append({"unit": unit, "in": None if n_in is None else int(n_in), "all": None if n_all is None else int(n_all),
                               "ballots": ballots, "registered": registered})

    def reading(self, feed, source_time=None, source_version=None, test=False):
        """The reading, with each contest's county rows checked against its whole-contest rows when every county is in
        (a difference is noted, never hidden; the store keeps both)."""
        out = []
        for c in self.c.values():
            c["units"] = list(c.pop("_units").values())
            c.pop("_ck", None)
            whole_rep = next((r for r in c["reporting"] if r["unit"] == "all" and r.get("all") is not None), None)
            if whole_rep:                                   # the state counts precincts: "2,840 of 4,103 precincts"
                c["unit_kind"], c["units_all"] = "precinct", whole_rep["all"]
            else:                                           # no precinct count: the contest's units are its counties
                c["unit_kind"] = "county"
                c["units_all"] = sum(1 for u in c["units"] if u["kind"] == "county") or None
            whole = {}
            parts = {}
            kinds = {u["id"]: u["kind"] for u in c["units"]}
            for r in c["rows"]:
                if r["type"] != "total":
                    continue
                if r["unit"] == "all":
                    whole[r["choice"]] = whole.get(r["choice"], 0) + r["votes"]
                elif kinds.get(r["unit"]) == "county":
                    parts[r["choice"]] = parts.get(r["choice"], 0) + r["votes"]
            if whole and parts and parts != {k: v for k, v in whole.items() if k in parts or v}:
                diff = [k for k in whole if whole.get(k, 0) != parts.get(k, 0)]
                if diff:
                    self.notes.append(f"{c['race_id']}: county rows and the whole-contest figures differ for {len(diff)} lines "
                                      f"(the two parts of the file were written at different moments, or not every county is in)")
            out.append(c)
        rd = {"state": self.code, "feed": feed, "source_time": source_time, "source_version": source_version,
              "contests": out, "unmatched": self.unmatched, "problems": self.problems, "notes": self.notes}
        if test:
            rd["test"] = True
        return rd


# ---------------------------------------------------------------------------------------------- times and ids


def iso(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z") if t else None


def parse_iso(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None
    except ValueError:
        return None


def local_to_utc(naive, tz):
    """A wall-clock time in a US zone as UTC (election.live's offsets; no time zone database needed)."""
    from election.live import from_local
    return from_local(naive, tz)


def election_ids(entry, pattern=r"\d+"):
    """The election ids the registry entry names for the night (a rehearsal puts a past id there)."""
    v = str(((entry or {}).get("election") or {}).get("nov3_id") or "")
    return re.findall(pattern, v)


def is_nov3(entry, nov3_ids):
    ids = election_ids(entry)
    return bool(ids) and ids[0] in {str(x) for x in nov3_ids}


def file_named(files, *needles):
    """The body of the first file whose name (an address, a path or a bare file name) holds every needle."""
    for name, body in files:
        n = str(name)
        if all(x in n for x in needles):
            return name, body
    return None, None


def body_ok(resp, what):
    """Raises the right error for a response that is not usable data."""
    from election.source import Refused, SourceError
    if resp.refused:
        raise Refused(resp.url, resp.why)
    if not resp.ok:
        raise SourceError(f"{what}: answered {resp.status}")
    return resp.body
