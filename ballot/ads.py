"""
ballot/ads.py - what each campaign, and everyone spending apart from it, has reported spending on ads, by kind: TV,
digital and streaming, print and mail, radio, and the rest (texts and calls, door-knocking, production, media buys
whose medium the filing does not state). From the FEC's bulk files, no key needed:

  independent_expenditure_2026.csv  outside spending for or against a candidate (Schedule E and the 24- and 48-hour
                                    reports), with the spender, the amount, the date and a purpose line
  oppexp26.zip                      every committee's operating expenditures, with a purpose line; read for the
                                    candidates' own committees only

The kind is read from the purpose line the spender wrote ("DIGITAL ADS", "DIRECT MAIL: PRINTING AND POSTAGE"); a line
that names no medium ("MEDIA PLACEMENT") is counted as a media buy whose medium is not stated, never guessed. An
expense reported twice, in a quick 24- or 48-hour report and again in a regular report, counts once (same spender,
candidate, side, date and amount); memo lines are left out, as the FEC's totals leave them out. Outside spenders are
named only when they are committees; the FEC's "person or group" filers are counted, never named. Payees are never
read into the database: the page shows kinds of spending and spenders, not the vendors or people paid.
"""

import csv
import datetime as dt
import io
import os
import re
import zipfile
from collections import defaultdict

from ballot.common import CACHE
from states import net

FEC = "https://www.fec.gov/files/bulk-downloads/2026/"
TODAY = dt.date.today().isoformat()
MEDIUM = [      # the first that fits, in this order
    ("digital", re.compile(r"STREAM|\bCTV\b|\bOTT\b|CONNECTED TV|DIGITAL|ONLINE|INTERNET|SOCIAL|\bWEB|E-?MAIL|FACEBOOK|GOOGLE|YOUTUBE|\bMETA\b|SEARCH ADS|PROGRAMMATIC")),
    ("tv", re.compile(r"\bTV\b|TELEVISION|BROADCAST|\bCABLE\b")),
    ("radio", re.compile(r"RADIO|AUDIO|PODCAST")),
    ("texts", re.compile(r"\bTEXT|\bSMS\b|PHONE|CALLS?\b|ROBO|\bIVR\b|PEER.TO.PEER")),
    ("print", re.compile(r"MAIL|POSTAGE|PRINT|LITERATURE|POSTCARD|BILLBOARD|NEWSPAPER|\bSIGNS?\b|DOOR ?HANGER|FLYER|BROCHURE|YARD")),
    ("doors", re.compile(r"CANVASS|FIELD|DOOR|VOTER CONTACT|GOTV|GET OUT THE VOTE")),
    ("production", re.compile(r"PRODUCTION|CREATIVE|VIDEO|FILMING|EDITING")),
    ("buys", re.compile(r"MEDIA|ADVERTIS|\bAD\b|\bADS\b|\bAD BUY|PLACEMENT")),
]
KIND_WORDS = {"tv": "TV", "digital": "Digital and streaming", "print": "Print and mail", "radio": "Radio", "texts": "Texts and calls",
              "doors": "Door-knocking", "production": "Ad production", "buys": "Media buys, medium not stated", "other": "Other"}
SCHEMA = """
DROP TABLE IF EXISTS ad_money;
DROP TABLE IF EXISTS ad_spenders;
CREATE TABLE ad_money (cand_id TEXT NOT NULL, who TEXT NOT NULL, stance TEXT NOT NULL, election TEXT NOT NULL, medium TEXT NOT NULL,
  amount REAL NOT NULL, n INTEGER NOT NULL, last_date TEXT, PRIMARY KEY (cand_id, who, stance, election, medium));
CREATE TABLE ad_spenders (cand_id TEXT NOT NULL, spender TEXT NOT NULL, name TEXT, stance TEXT NOT NULL, election TEXT NOT NULL,
  amount REAL NOT NULL, PRIMARY KEY (cand_id, spender, stance, election));
"""


def medium(purpose):
    p = (purpose or "").upper()
    return next((k for k, rx in MEDIUM if rx.search(p)), "other")


MONTHS = {m: i for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), start=1)}


def iso(text):
    """05/15/2026, 05152026 (the itemized files) or 15-MAY-26 (the independent expenditure file) -> 2026-05-15"""
    t = (text or "").strip().upper()
    m = re.match(r"(\d{1,2})-([A-Z]{3})-(\d{2,4})$", t)
    if m and m.group(2) in MONTHS:
        y = int(m.group(3))
        return f"{2000 + y if y < 100 else y}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", t) or re.match(r"(\d{2})(\d{2})(\d{4})$", t)
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""


def amount(text):
    try:
        return float(str(text).replace(",", "").replace("$", ""))
    except ValueError:
        return 0.0


def load(con, say=print):
    con.executescript(SCHEMA)
    net.patient_lookups()
    folder = os.path.join(CACHE, "fec")
    ie, opp = os.path.join(folder, "independent_expenditure_2026.csv"), os.path.join(folder, "oppexp26.zip")
    net.download(FEC + "independent_expenditure_2026.csv", ie, max_age_days=2, say=say)
    net.download(FEC + "oppexp26.zip", opp, max_age_days=7, say=say)
    ours = {r[0] for r in con.execute("SELECT cand_id FROM fec26_candidates")}      # every 2026 candidate, so a list loaded later needs no rerun
    kinds = dict(con.execute("SELECT cmte_id, type FROM fec26_committees"))
    names = dict(con.execute("SELECT cmte_id, name FROM fec26_committees"))
    money, spenders = defaultdict(lambda: [0.0, 0, ""]), defaultdict(float)

    # outside spending: the latest copy of each transaction, then one count per spender, candidate, side, date and amount
    latest = {}
    for r in csv.DictReader(open(ie, encoding="utf-8", errors="replace")):
        if r["cand_id"] not in ours or r["sup_opp"] not in ("S", "O"):
            continue
        key = (r["spe_id"], r["tran_id"] or r["image_num"])
        if key not in latest or int(r["file_num"] or 0) > int(latest[key]["file_num"] or 0):
            latest[key] = r
    seen = set()
    for r in latest.values():
        when = iso(r["exp_date"] or r["dissem_dt"])
        dup = (r["spe_id"], r["cand_id"], r["sup_opp"], when, round(amount(r["exp_amo"]), 2))
        if dup in seen:
            continue
        seen.add(dup)
        stance, amt = ("for" if r["sup_opp"] == "S" else "against"), amount(r["exp_amo"])
        el = {"P": "primary", "G": "general"}.get((r["ele_type"] or "")[:1], "other")
        m = money[(r["cand_id"], "outside", stance, el, medium(r["pur"]))]
        m[0] += amt
        m[1] += 1
        m[2] = max(m[2], when) if when <= TODAY else m[2]      # a date typed in the future (2028) is not a report date
        named = r["spe_id"] if kinds.get(r["spe_id"]) not in (None, "I") else "people-and-groups"      # a person or group is never named
        spenders[(r["cand_id"], named, stance, el)] += amt
    # the campaigns' own spending: their principal and authorized committees' operating expenditures
    cmte_cand = {c: k for c, k in con.execute("SELECT cmte_id, cand_id FROM fec26_committees WHERE designation IN ('P', 'A') AND cand_id IS NOT NULL") if k in ours}
    cmte_cand.update({p: c for c, p in con.execute("SELECT cand_id, pcc FROM fec26_candidates WHERE pcc IS NOT NULL") if c in ours})
    best = {}
    with zipfile.ZipFile(opp) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".txt"))
        with z.open(name) as fh:
            for line in io.TextIOWrapper(fh, encoding="latin-1"):
                f = line.rstrip("\r\n").split("|")
                if len(f) < 25 or f[0] not in cmte_cand or f[18] == "X":      # someone else's committee, or a memo line
                    continue
                key = (f[0], f[23] or f[21])
                if key not in best or int(f[22] or 0) > int(best[key][22] or 0):
                    best[key] = f
    for f in best.values():
        m = money[(cmte_cand[f[0]], "campaign", "", "cycle", medium(f[15]))]
        m[0] += amount(f[13])
        m[1] += 1
        m[2] = max(m[2], iso(f[12])) if iso(f[12]) <= TODAY else m[2]
    with con:
        con.execute("DELETE FROM ad_money")
        con.execute("DELETE FROM ad_spenders")
        con.executemany("INSERT INTO ad_money VALUES (?,?,?,?,?,?,?,?)", [(*k, round(v[0], 2), v[1], v[2]) for k, v in money.items() if abs(v[0]) >= 1])
        con.executemany("INSERT INTO ad_spenders VALUES (?,?,?,?,?,?)",
                        [(c, s, None if s == "people-and-groups" else names.get(s), st, el, round(a, 2)) for (c, s, st, el), a in spenders.items() if a >= 1])
    outside = sum(v[0] for k, v in money.items() if k[1] == "outside")
    say(f"    Ads: {len({k[0] for k in money})} candidates with spending on record; outside spending ${outside:,.0f} for and against them "
        f"({len(seen)} expenses after duplicates were set aside); campaigns' own spending read from {len(best):,} expenses")
