"""
ballot/match.py - ties each candidate on an official list to their FEC candidate number (for the money on their
card) and, when they serve in Congress today, to their Bioguide id (for their record).

A match needs the same state and office, the same family name, and a given name that fits (the same, one the start
of the other, or a common nickname, as the state money loaders use), and it must be the only fit. A House candidate
is looked for in their own district first, then anywhere in the state (after redistricting a campaign can be
registered under another number), but only if the name fits exactly one registration. A name kept on the ballot that
the FEC files among the given names (a professional or maiden name: ARENHOLZ, ASHLEY HINSON for Ashley Hinson) matches
only when it is the one such fit in the race. Anyone left unmatched is listed; nobody is guessed.
"""

import collections
import os
import sqlite3

from ballot.common import HERE, fold, name_parts
from states.money_mn import given_fits


def fec_name(raw):
    """The FEC writes 'LAST, FIRST MIDDLE SUFFIX'."""
    return name_parts(raw)


PARTICLES = {"de", "la", "del", "van", "von", "der", "den", "da", "di", "du", "le", "st", "san", "y"}


def fits(cand, reg, loose=False):
    """Same family name (a two-part name may be written with either part, Díaz-Balart or Balart, and a particle may
    sit with the given names on a ballot, Sandra Van Scotter for VAN SCOTTER, SANDRA), and a given name that fits one
    of the other's (the FEC sometimes adds a nickname after the legal names). Loose, used only when the family name is
    unique in the race: the given names need only begin with the same letter (Ami for Amerish, Ro for Rohit)."""
    (g1, f1), (g2, f2) = cand, reg
    w1, w2 = set(f1.split()) - PARTICLES, set(f2.split()) - PARTICLES
    if not (f1 == f2 or (w1 and w1 == w2) or (w1 & w2 and (len(w1) > 1 or len(w2) > 1))):
        return False
    if not g1 or not g2:
        return True
    if any(given_fits(a, b) for a in g1[:2] for b in g2):
        return True
    return loose and g1[0][:1] == g2[0][:1]


def link(con, record_db=os.path.join(HERE, "congress_119.sqlite"), say=print):
    rec = sqlite3.connect(f"file:{record_db}?mode=ro", uri=True)
    whose = dict(rec.execute("SELECT cand_id, bioguide_id FROM member_fec"))
    members = collections.defaultdict(list)      # (state, chamber) -> current members, for incumbents without an FEC match
    for bio, first, last, full, st, ch in rec.execute("SELECT bioguide_id, first_name, last_name, official_full, state, chamber FROM legislators WHERE is_current = 1"):
        members[(st, ch)].append((bio, name_parts(full or f"{first} {last}")))
    regs = collections.defaultdict(list)
    have_money = {r[0] for r in con.execute("SELECT cand_id FROM fec26_totals WHERE receipts > 0")}
    for cid, name, st, office, dist in con.execute("SELECT cand_id, name, state, office, district FROM fec26_candidates"):
        regs[(st, office)].append((cid, int(dist) if (dist or "").isdigit() else 0, fec_name(name)))
    races = {r[0]: r[1:] for r in con.execute("SELECT race_id, state, office, district FROM races")}
    updates, unmatched = [], []
    for race, election, name in con.execute("SELECT race_id, election, name FROM candidates").fetchall():
        st, office, dist = races[race]
        code = "H" if office == "U.S. House" else "S"
        me = name_parts(name)
        pool = regs.get((st, code), [])
        here = [r for r in pool if code == "S" or r[1] == int(dist or 0)]
        hits = [r for r in here if fits(me, r[2])]
        if not hits:      # the family name alone, when exactly one registration in the race carries it
            same = [r for r in here if fits(me, r[2], loose=True)]
            hits = same if len(same) == 1 and sum(1 for r in here if fits((None, me[1]), r[2])) == 1 else []
        if not hits:      # a name kept on the ballot that the FEC files among the given names (ARENHOLZ, ASHLEY HINSON for Ashley Hinson)
            kept = [r for r in here if me[0] and r[2][0] and me[1] in r[2][0] and given_fits(me[0][0], r[2][0][0])]
            hits = kept if len(kept) == 1 else []
        if not hits and code == "H":      # registered under another district number: one person, however many numbers
            hits = [r for r in pool if fits(me, r[2])]
            if len({(h[2][1], tuple(h[2][0][:1])) for h in hits}) > 1:
                hits = []
        if len(hits) > 1:      # the same person registered twice: take the number with money, then the lowest
            hits = sorted(hits, key=lambda h: (h[0] not in have_money, h[0]))[:1]
        fec = hits[0][0] if hits else None
        bio = whose.get(fec) if fec else None
        if not bio:
            chamber = "House" if code == "H" else "Senate"
            m = [b for b, parts in members.get((st, chamber), []) if fits(me, parts)] + \
                [b for b, parts in members.get((st, "House" if code == "S" else "Senate"), []) if fits(me, parts)]
            bio = m[0] if len(m) == 1 else None
        updates.append((fec, bio, race, election, name))
        if not fec:
            unmatched.append(f"{race} {name}")
    with con:
        con.executemany("UPDATE candidates SET fec_id = ?, bioguide_id = ? WHERE race_id = ? AND election = ? AND name = ?", updates)
    general = con.execute("SELECT COUNT(*), SUM(fec_id IS NOT NULL), SUM(bioguide_id IS NOT NULL) FROM candidates WHERE election = 'general'").fetchone()
    say(f"    Matched: {general[1] or 0} of {general[0]} November candidates to an FEC registration; {general[2] or 0} serve in Congress today")
    left = sorted({u for u in unmatched})
    if left:
        say(f"    No FEC registration found for {len(left)} (write-ins and small campaigns often have none): "
            + "; ".join(left[:12]) + (" ..." if len(left) > 12 else ""))
    return left
