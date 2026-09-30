"""
ballot/people.py - who each candidate is, as far as the records show: their age, the offices they have held and for
how long, and a photograph to recognise them by (John, 2026-09-29: "it'll help identify people better"; "put their age
on their card too, and how many years they've been in this current role or served in office for anything").

Sources, best first, each named on the page:
  Congress        a member of Congress today (or before): birth date, every term in either chamber and the official
                  portrait, from the congress-legislators roster and the Bioguide (public domain), already in
                  congress_119.sqlite
  State office    a sitting state legislator or statewide official in the candidate's own state: birth date, terms and
                  portrait from the Open States roster the state pages use (state_<code>.sqlite)
  Wikidata        for anyone else whose FEC candidate number Wikidata records (property P1839): birth date and offices,
                  labelled as not an official record (ballot/wikidata.py, not run yet)
  Campaign        a photograph from the candidate's own campaign website, credited and linked (ballot/campaign.py,
                  not run yet)
A match to a state roster needs the same state, the same family name and a fitting given name, and must be the only
fit. Nothing is guessed: a candidate with no record shows no age and no office.
"""

import datetime as dt
import json
import os
import sqlite3

from ballot.common import HERE, STATE_NAMES, name_parts
from ballot.match import fits
from states.places import PLACES


def state_chamber(st):
    """Each state's own names for its chambers: 'California Assembly', 'Florida House', 'Nebraska Legislature'."""
    p = PLACES.get(st.lower(), {})
    upper, lower = (p.get("upper") or {}).get("name"), (p.get("lower") or {}).get("name")
    name = STATE_NAMES.get(st, st)
    return lambda kind: f"{name} {upper or 'Legislature'}" if kind == "sen" or not lower else f"{name} {lower}"

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
  person TEXT PRIMARY KEY, name TEXT, bioguide_id TEXT, state_id TEXT, dob TEXT, dob_src TEXT,
  offices TEXT, photo BLOB, photo_src TEXT, photo_credit TEXT, photo_url TEXT, website TEXT);
"""
CHAMBER = {"rep": "U.S. House", "sen": "U.S. Senate"}


def person_key(fec, race, name):
    return fec or f"{race}|{name}"


def spans(rows, label_of):
    """Terms -> [{office, start, end, unsure}] with runs in the same office joined up. A term that has not ended has an
    empty end, or its scheduled end in the future. A run whose first start date is missing starts, "at least", at the
    earliest date the record does give (the end of that first term), and is marked unsure."""
    out = []
    for kind, start, end in sorted(rows, key=lambda r: (r[1] or "0000", r[2] or "9999")):
        office = label_of(kind) or "Legislature"
        if out and out[-1][0] == office and (not start or not out[-1][2] or start <= out[-1][2]):
            out[-1][2] = end or ""
            out[-1][3] = out[-1][3] or not start
            continue
        out.append([office, start or "", end or "", not start])
    today = dt.date.today().isoformat()
    result = []
    for o, s, e, u in out:
        if not s:      # the earliest date the record gives for this run
            known = sorted(d for k, a, b in rows if (label_of(k) or "Legislature") == o for d in (a, b) if d)
            s = known[0] if known else ""
        result.append({"office": o, "start": s, "end": "" if (not e or e > today) else e, "unsure": u})
    return result


def build(con, record_db=os.path.join(HERE, "congress_119.sqlite"), say=print):
    con.executescript(SCHEMA)
    rec = sqlite3.connect(f"file:{record_db}?mode=ro", uri=True)
    births = dict(rec.execute("SELECT bioguide_id, birthday FROM legislators WHERE birthday IS NOT NULL AND birthday <> ''"))
    fed_terms = {}
    for bio, kind, start, end, st in rec.execute("SELECT bioguide_id, type, start, end, state FROM member_terms"):
        fed_terms.setdefault(bio, []).append((kind, start, end))
    old = {r[0]: r[1:] for r in rec.execute("SELECT bioguide_id, chamber, first_term_start, term_end, terms_count FROM legislators WHERE is_current = 0")}
    fed_photos = {r[0]: r[1] for r in rec.execute("SELECT bioguide_id, webp FROM photos WHERE webp IS NOT NULL")}
    states = {}      # state -> (roster rows, terms, photos, officials)
    rows, counts = [], {"age": 0, "office": 0, "photo": 0, "state": 0}
    cands = con.execute("SELECT DISTINCT c.fec_id, c.race_id, c.name, c.bioguide_id, r.state, c.party_code FROM candidates c JOIN races r USING (race_id)").fetchall()
    seen, matched = set(), []
    for fec, race, name, bio, st, pc in cands:
        key = person_key(fec, race, name)
        if key in seen:
            continue
        seen.add(key)
        dob = dob_src = photo = photo_src = credit = url = state_id = None
        offices = []
        if bio:      # a member of Congress, today or before
            dob, dob_src = births.get(bio), "Congress"
            if bio in fed_terms:
                offices += [dict(s, src="Congress") for s in spans(fed_terms[bio], CHAMBER.get)]
            elif bio in old:
                ch, first, last, n = old[bio]
                offices.append({"office": "U.S. " + ("Senate" if ch == "Senate" else "House"), "start": first or "", "end": last or "",
                                "unsure": False, "terms": n, "src": "Congress"})
            if bio in fed_photos:
                photo, photo_src, credit = fed_photos[bio], "Congress", "Official portrait, public domain (unitedstates/images)"
        db = os.path.join(HERE, f"state_{st.lower()}.sqlite")
        if os.path.exists(db):
            if st not in states:
                s = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                roster = [(r[0], name_parts(r[1] or f"{r[2]} {r[3]}"), r[4], r[5], (r[6] or "")[:1].upper()) for r in s.execute(
                    "SELECT bioguide_id, official_full, first_name, last_name, birthday, chamber, party FROM legislators WHERE is_current = 1")]
                terms = {}
                for sid, kind, start, end in s.execute("SELECT bioguide_id, type, start, end FROM member_terms"):
                    terms.setdefault(sid, []).append((kind, start, end))
                photos = {r[0]: (r[1], r[2]) for r in s.execute("SELECT bioguide_id, webp, source_url FROM photos WHERE webp IS NOT NULL")}
                officials = [(r[0], name_parts(r[1] or f"{r[2]} {r[3]}"), r[4], r[5]) for r in s.execute(
                    "SELECT bioguide_id, official_full, first_name, last_name, office_label, term_start FROM officials")] \
                    if s.execute("SELECT 1 FROM sqlite_master WHERE name = 'officials'").fetchone() else []
                states[st] = (roster, terms, photos, officials)
            roster, terms, photos, officials = states[st]
            me = name_parts(name)
            hit = [r for r in roster if fits(me, r[1])] if not bio else []
            same_party = lambda p: not p or pc not in ("R", "D") or p == pc or p not in ("R", "D")
            if len(hit) == 1 and same_party(hit[0][4]):      # a sitting state legislator in the candidate's own state, of the same party
                sid, _, birthday, chamber, _p = hit[0]
                state_id = f"{st}:{sid}"
                counts["state"] += 1
                matched.append(f"{race} {name} = {st} {chamber} roster {sid}")
                if not dob and birthday:
                    dob, dob_src = birthday, "State roster"
                offices += [dict(s, src="State roster") for s in spans(terms.get(sid, []), state_chamber(st))]
                if not photo and sid in photos:
                    photo, photo_src, credit, url = photos[sid][0], "State roster", "Official legislature portrait, via Open States", photos[sid][1]
            off = [r for r in officials if fits(me, r[1])] if not bio else []
            if len(off) == 1:      # a statewide official today
                matched.append(f"{race} {name} = {st} {off[0][2]}")
                sid, _, label, start = off[0]
                offices.append({"office": f"{STATE_NAMES.get(st, st)} {label}", "start": start or "", "end": "", "unsure": not start, "src": "State roster"})
                state_id = state_id or f"{st}:{sid}"
        counts["age"] += bool(dob)
        counts["office"] += bool(offices)
        counts["photo"] += bool(photo)
        rows.append((key, name, bio, state_id, dob, dob_src, json.dumps(offices) if offices else None, photo, photo_src, credit, url, None))
    with con:
        con.execute("DELETE FROM people")
        con.executemany("INSERT OR REPLACE INTO people VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    from ballot.campaign import apply_choices      # websites and reviewed campaign photos are kept apart, and put back here
    apply_choices(con, say=lambda *_: None)
    say(f"    People: {len(rows):,} candidates; age on record for {counts['age']:,}, offices for {counts['office']:,}, "
        f"a photo for {counts['photo']:,}; {counts['state']:,} sit in their state's legislature today")
    for m in matched:      # every state-roster match is listed, so each can be read by eye
        say(f"      {m}")
    return counts
