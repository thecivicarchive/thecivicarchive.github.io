#!/usr/bin/env python3
"""
congress_catalog.py
===================
Builds a complete, spreadsheet-ready catalog of every bill and resolution in a
Congress from the official Bill Status bulk data that GPO and the Library of
Congress publish (the same data that powers Congress.gov).

Default scope: the 119th Congress (convened Jan 3, 2025), which is every
measure introduced since January 1, 2025.

For every measure it captures:
  * Sponsor and every cosponsor (party, state, date joined, original y/n, withdrawn)
  * Every committee / subcommittee it was referred to and what happened there
    (hearings, markups, "ordered reported" votes with tallies where published)
  * Every House and Senate floor vote (recorded tallies, voice votes, unanimous
    consent), with links to the official roll-call records
  * Status: became law / vetoed / failed / passed one chamber / pending, plus
    the Public Law number
  * Related measures that became law - flags bills whose text was likely enacted
    inside another vehicle (the bill itself still reads "Pending")
  * Links: Congress.gov bill page, text tab, all-actions tab, cosponsors tab,
    and the latest official text (PDF) on GovInfo

No API key needed. Python 3.9+. Only third-party dependency: openpyxl.

Usage
-----
    pip install openpyxl
    python congress_catalog.py                     # H.R., S., H.J.Res., S.J.Res. (can become law)
    python congress_catalog.py --types all         # + simple & concurrent resolutions
    python congress_catalog.py --party-breakdown   # + party split on every roll call (slower)
    python congress_catalog.py --refresh           # re-download (the source updates daily)
    python congress_catalog.py --local-dir ./xml   # parse BILLSTATUS XML files you already have
    python congress_catalog.py --csv               # also write one CSV per sheet
    python congress_catalog.py --db congress_119.sqlite   # + a normalized SQLite database (14 tables,
                                                   #   incl. CRS summaries and empty ratings tables for score_bills.py)

Output: congress_119_catalog.xlsx, plus ./billstatus_cache/ (downloaded source files)
"""

import argparse
import csv
import hashlib
import html as html_mod
import sqlite3
import datetime as dt
import glob
import json
import os
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BULK = "https://www.govinfo.gov/bulkdata"
UA = "Mozilla/5.0 (compatible; congress-catalog/1.0; personal legislative research)"

TYPE_INFO = OrderedDict([
    # code: (display prefix, congress.gov URL slug, origin chamber, kind)
    ("hr", ("H.R.", "house-bill", "House", "Bill")),
    ("s", ("S.", "senate-bill", "Senate", "Bill")),
    ("hjres", ("H.J.Res.", "house-joint-resolution", "House", "Joint resolution")),
    ("sjres", ("S.J.Res.", "senate-joint-resolution", "Senate", "Joint resolution")),
    ("hconres", ("H.Con.Res.", "house-concurrent-resolution", "House", "Concurrent resolution")),
    ("sconres", ("S.Con.Res.", "senate-concurrent-resolution", "Senate", "Concurrent resolution")),
    ("hres", ("H.Res.", "house-resolution", "House", "Simple resolution")),
    ("sres", ("S.Res.", "senate-resolution", "Senate", "Simple resolution")),
])
LAW_CAPABLE = ["hr", "s", "hjres", "sjres"]

# Floor-vote categories that decide a measure's fate (shown in the Bills sheet summaries).
KEY_CATEGORIES = ("Passage", "Resolve differences", "Conference report", "Veto override",
                  "Cloture", "Motion to proceed")
SUCCESS = ("Passed", "Agreed to", "Invoked")
FAILURE = ("Failed", "Not agreed to", "Rejected", "Not invoked")

# Topic lenses (title + policy area + CRS subject terms). Keyword screens, not legal conclusions.
LENSES = OrderedDict([
    ("Tax", (re.compile(r"\btax|internal revenue|\birs\b|\btariff|\bexcise", re.I), {"Taxation"})),
    ("Employment", (re.compile(r"employ|worker|workforce|\bwages?\b|\blabor\b|workplace|overtime|"
                               r"labor union|collective bargaining|\bosha\b|pension|\berisa\b|"
                               r"retirement|apprentice|paid leave|family and medical leave", re.I),
                    {"Labor and Employment"})),
    ("Disability", (re.compile(r"disabilit|disabled|\bada\b|accessib|\bssdi\b|supplemental security income|"
                               r"special education|autism|\bblind|\bdeaf", re.I), set())),
])


# ----------------------------------------------------------------------------- helpers
def log(*a):
    print(*a, flush=True)


def http_get(url, retries=4, timeout=90, accept=None):
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    last = None
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as r:
                return r.read()
        except HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                raise
        except (URLError, TimeoutError, ConnectionError, OSError) as e:
            last = e
        time.sleep(2 ** attempt)
    raise last


def ordinal(n):
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def cg_url(congress, btype, number, tab=""):
    base = f"https://www.congress.gov/bill/{ordinal(congress)}-congress/{TYPE_INFO[btype][1]}/{number}"
    return f"{base}/{tab}" if tab else base


def txt(e, path, default=""):
    if e is None:
        return default
    v = e.findtext(path)
    return v.strip() if v and v.strip() else default


def items(e, path):
    if e is None:
        return []
    node = e.find(path)
    return list(node.findall("item")) if node is not None else []


def committee_items(e):
    """Committee <item>s in both the current and the pre-2020 (<billCommittees>) layouts."""
    node = e.find("committees") if e is not None else None
    if node is None:
        return []
    direct = node.findall("item")
    return direct if direct else [i for child in node for i in child.findall("item")]


def short_date(s):
    return (s or "")[:10]


def session_for(congress, date_str):
    """Session number of a Congress for a YYYY-MM-DD date (1st session ends Jan 3 of year two)."""
    start_year = 1789 + 2 * (int(congress) - 1)
    try:
        year, month_day = int(date_str[:4]), date_str[5:10]
    except (TypeError, ValueError):
        return 1
    if year <= start_year or (year == start_year + 1 and month_day < "01-03"):
        return 1
    return 2


# ----------------------------------------------------------------------------- download
def list_folder(congress, btype):
    """Return [{link, folder}] for a GovInfo bulk-data folder (JSON listing, XML fallback)."""
    url = f"{BULK}/json/BILLSTATUS/{congress}/{btype}"
    try:
        data = json.loads(http_get(url, accept="application/json").decode("utf-8"))
        files = data.get("files", []) if isinstance(data, dict) else data
        if isinstance(files, dict):
            files = files.get("file", [])
        out = [{"link": f.get("link", ""), "folder": str(f.get("folder")).lower() == "true"}
               for f in files if isinstance(f, dict) and f.get("link")]
        if out:
            return out
    except Exception as e:  # noqa: BLE001 - fall back to the XML listing
        log(f"    JSON listing unavailable ({e}); trying XML listing")
    raw = http_get(f"{BULK}/xml/BILLSTATUS/{congress}/{btype}", accept="application/xml")
    root = ET.fromstring(raw)
    return [{"link": (f.findtext("link") or "").strip(), "folder": (f.findtext("folder") or "") == "true"}
            for f in root.iter("file") if (f.findtext("link") or "").strip()]


def fetch_type(congress, btype, cache_root, refresh=False, workers=8):
    """Yield (filename, xml_bytes) for every BILLSTATUS file of one measure type."""
    cdir = os.path.join(cache_root, str(congress), btype)
    os.makedirs(cdir, exist_ok=True)
    try:
        listing = list_folder(congress, btype)
    except Exception as e:  # noqa: BLE001 - offline / GovInfo hiccup: fall back to the local cache
        cached = sorted(glob.glob(os.path.join(cdir, "*.zip"))) or sorted(glob.glob(os.path.join(cdir, "*.xml")))
        if not cached:
            raise
        log(f"    listing unavailable ({e}); using {len(cached):,} cached file(s) in {cdir}")
        listing, refresh = [{"link": p, "folder": False} for p in cached], False

    zips = [f["link"] for f in listing if f["link"].lower().endswith(".zip")]
    if zips:
        zpath = os.path.join(cdir, zips[0].rsplit("/", 1)[-1])
        try:
            if refresh or not os.path.exists(zpath):
                log(f"    downloading {zips[0]}")
                data = http_get(zips[0], timeout=900)
                with open(zpath, "wb") as fh:
                    fh.write(data)
            with zipfile.ZipFile(zpath) as z:
                for name in z.namelist():
                    if name.lower().endswith(".xml"):
                        yield name.rsplit("/", 1)[-1], z.read(name)
            return
        except Exception as e:  # noqa: BLE001 - fall back to per-file downloads
            log(f"    zip route failed ({e}); downloading files individually")

    links = [f["link"] for f in listing if f["link"].lower().endswith(".xml")]
    log(f"    {len(links):,} files listed")

    def grab(link):
        path = os.path.join(cdir, link.rsplit("/", 1)[-1])
        if refresh or not os.path.exists(path):
            try:
                data = http_get(link)
            except Exception as e:  # noqa: BLE001
                return f"{link}: {e}"
            with open(path, "wb") as fh:
                fh.write(data)
        return None

    errors = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, err in enumerate(pool.map(grab, links), 1):
            if err:
                errors.append(err)
            if i % 1000 == 0:
                log(f"    {i:,}/{len(links):,} downloaded")
    if errors:
        log(f"    WARNING: {len(errors)} files failed to download (first: {errors[0]})")
    for link in links:
        path = os.path.join(cdir, link.rsplit("/", 1)[-1])
        if os.path.exists(path):
            with open(path, "rb") as fh:
                yield os.path.basename(path), fh.read()


def local_files(folder):
    for path in sorted(glob.glob(os.path.join(folder, "**", "*.xml"), recursive=True)):
        with open(path, "rb") as fh:
            yield os.path.basename(path), fh.read()


# ----------------------------------------------------------------------------- parsing
LOC_PREFIX = re.compile(r"^(?:Passed/agreed to in (House|Senate)|Failed of passage/not agreed to in "
                        r"(House|Senate)|Resolving differences -- (House|Senate) actions)\s*:\s*", re.I)
HOUSE_TALLY = re.compile(r"(?:Yeas and Nays|recorded vote)\s*:?\s*(?:\(\d/\d required\)\s*:?\s*)?(\d+)\s*-\s*(\d+)"
                         r"(?:\s*,\s*(\d+)\s*Present)?", re.I)
SENATE_TALLY = re.compile(r"Yea-Nay(?:\s+Vote)?\.?\s*(\d+)\s*-\s*(\d+)", re.I)
ROLL = re.compile(r"Roll no\.\s*(\d+)|Record Vote (?:Number|No)\.?\s*:?\s*(\d+)", re.I)
DEEMED = re.compile(r"(?:is|are|be) (?:considered|deemed) (?:as )?(?:to have )?(?:been )?"
                    r"(?:passed|agreed to|adopted)", re.I)
AMENDED = re.compile(r"with (?:an )?amendments?\b|\bas amended\b", re.I)
LONG_TITLE = re.compile(r"^(To |A bill |A joint resolution|A concurrent resolution|A resolution|An original|Providing for|Proposing|"
                        r"Making |Expressing|Recognizing|Authorizing|Designating|Condemning|Supporting|Calling|Directing|Amending|"
                        r"Establishing|Requiring|Disapproving|Approving|Provides for)", re.I)


def parse_method(text):
    """-> (method, yeas, nays, present, roll_number)"""
    method, yeas, nays, present = "", None, None, None
    m = HOUSE_TALLY.search(text) or SENATE_TALLY.search(text)
    if m:
        method, yeas, nays = "Recorded vote", int(m.group(1)), int(m.group(2))
        if m.re is HOUSE_TALLY and m.group(3):
            present = int(m.group(3))
    elif re.search(r"voice vote", text, re.I):
        method = "Voice vote"
    elif re.search(r"unanimous consent|without objection", text, re.I):
        method = "Unanimous consent"
    elif DEEMED.search(text):
        method = "Deemed passed by rule"
    r = ROLL.search(text)
    roll = int(r.group(1) or r.group(2)) if r else None
    return method, yeas, nays, present, roll


def vote_result(text):
    t = text.lower()
    for pattern, result in ((r"\bnot invoked\b", "Not invoked"), (r"\binvoked\b", "Invoked"),
                            (r"\bnot agreed to\b", "Not agreed to"), (r"\bfailed\b", "Failed"),
                            (r"\brejected\b", "Rejected"), (r"\bpassed\b", "Passed"),
                            (r"\bagreed to\b", "Agreed to"), (r"\bconcurred\b", "Agreed to"),
                            (r"\badopted\b", "Agreed to")):
        if re.search(pattern, t):
            return result
    return ""


def vote_category(text):
    t = text.lower().strip()
    if "motion to reconsider" in t or "laid on the table" in t:
        return None
    if re.search(r"cloture motion .*\b(presented|withdrawn|filed)\b", t):
        return None
    if re.search(r"objections of the president|over (the )?(president'?s )?veto|notwithstanding", t):
        return "Veto override"
    if "veto message" in t:
        return "Other"
    if "cloture" in t:
        return "Cloture"
    if "conference report" in t:
        return "Conference report"
    if re.match(r"[sh]\.? ?amdt", t) or re.search(r"\bamendment (no\.|sa\b|\(a\d+)|on agreeing to the [^.]*amendment", t):
        return "Amendment"
    if re.search(r"house (agree|concur)|agree (to|in) the senate amendment|agree in senate amendment|"
                 r"concur in the senate amendment|senate (agreed|concurred) (to|in) the house amendment|"
                 r"senate agreed to house amendment", t):
        return "Resolve differences"
    if re.search(r"\btable\b|\btabled\b", t):
        return "Motion to table"
    if "motion to proceed" in t:
        return "Motion to proceed"
    if re.search(r"recommit|to commit\b|commit to", t):
        return "Motion to (re)commit"
    if "previous question" in t:
        return "Previous question"
    if "motion to discharge" in t:
        return "Discharge motion"
    if re.search(r"on passage|suspend the rules and (pass|agree)|on agreeing to the (joint |concurrent )?resolution|"
                 r"passed senate|passed house|failed of passage|resolution (not )?agreed to in senate|"
                 r"considered,? and (not )?agreed to|agreed to in senate|resolution agreed to|"
                 r"(considered|deemed) (as )?(to have )?(been )?(passed|agreed to|adopted)", t):
        return "Passage"
    if re.search(r"\bamendment\b", t):
        return "Amendment"
    return "Other"


def committee_activity(text):
    t = text.lower()
    if "forwarded by subcommittee" in t:
        return "Forwarded by subcommittee"
    if "ordered to be reported" in t or "ordered reported" in t:
        return "Ordered reported"
    if "referred to" in t or "re-referred" in t:
        return "Referred"
    if "mark-up" in t or "markup" in t:
        return "Markup held"
    if "hearing" in t:
        return "Hearing held"
    if "discharged" in t:
        return "Discharged"
    if re.search(r"\breported\b", t):
        return "Reported"
    return "Other"


def is_committee_action(src, atype, text):
    s, t = src.lower(), text.lower()
    if s == "library of congress":
        return False
    if s == "house committee actions":
        return True
    if atype in ("Committee", "Discharge"):
        return True
    if s == "senate" and t.startswith(("committee on", "select committee", "special committee")):
        return True
    return False


def lens_flags(title, policy_area, subjects):
    """'Tax' = title/policy-area hit (strong); 'Tax (subj.)' = only a CRS subject term matched (weaker)."""
    out = []
    for name, (rx, areas) in LENSES.items():
        if policy_area in areas or rx.search(f"{title} {policy_area}"):
            out.append(name)
        elif any(rx.search(s) for s in subjects):
            out.append(f"{name} (subj.)")
    return "; ".join(out)


def vote_links(chamber, congress, date_str, roll):
    """Human-readable page + XML for a roll call, built from official URL patterns."""
    if not roll:
        return "", ""
    year = date_str[:4]
    if chamber == "House":
        return (f"https://clerk.house.gov/Votes/{year}{roll}",
                f"https://clerk.house.gov/evs/{year}/roll{int(roll):03d}.xml")
    sess = session_for(congress, date_str)
    stem = f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{sess}/vote_{congress}_{sess}_{int(roll):05d}"
    return f"{stem}.htm", f"{stem}.xml"


def parse_billstatus(xml_bytes):
    root = ET.fromstring(xml_bytes)
    bill = root.find("bill")
    if bill is None:
        return None
    btype = (txt(bill, "type") or txt(bill, "billType")).lower()
    number = txt(bill, "number") or txt(bill, "billNumber")
    congress = txt(bill, "congress")
    if btype not in TYPE_INFO or not number:
        return None
    prefix, _, origin, kind = TYPE_INFO[btype]
    bill_id = f"{prefix} {number}"
    title = txt(bill, "title")
    # Short title, only when the display title is a long official title ("To amend...", "Providing for..."):
    # prefer the enrolled version's short title, then passed, reported, introduced (first listed at that rank).
    short_title, best = "", 99
    if LONG_TITLE.match(title):
        for t in items(bill, "titles"):
            tt, val = txt(t, "titleType"), txt(t, "title")
            if not tt.lower().startswith("short title") or not val or LONG_TITLE.match(val):
                continue
            rank = 0 if "ENR" in tt else 1 if "Passed" in tt else 2 if "Reported" in tt else 3
            if rank < best:
                short_title, best = val, rank
    policy_area = txt(bill, "policyArea/name") or txt(bill, "primarySubject/name")          # pre-2020 layout
    subjects = [txt(i, "name") for i in items(bill, "subjects/legislativeSubjects")] or \
        [txt(i, "name") for i in items(bill, "subjects/billSubjects/otherSubjects")]

    # -- related measures: companions, and measures whose text may have moved in another vehicle
    related = []                                   # (bill id, "identical"/"related", law label)
    for rb in items(bill, "relatedBills"):
        rtype, rnum, rcong = txt(rb, "type").lower(), txt(rb, "number"), txt(rb, "congress")
        rels = {txt(d, "type") for d in items(rb, "relationshipDetails")}
        if rtype not in TYPE_INFO or not rnum or (rels and rels <= {"Procedurally-related"}):
            continue                               # skip rules and other purely procedural links
        rid = f"{TYPE_INFO[rtype][0]} {rnum}" + (f" ({ordinal(rcong)})" if rcong and rcong != congress else "")
        lm = re.search(r"Became (Public|Private) Law No:\s*([\d-]+)", txt(rb, "latestAction/text"))
        law = (("P.L. " if lm.group(1) == "Public" else "Pvt.L. ") + lm.group(2)) if lm else ""
        related.append((rid, "identical" if "Identical bill" in rels else "related", law))

    # -- CRS summaries (every version), CBO cost estimates, committee reports: inputs for the ratings layer
    summaries = []
    snode = bill.find("summaries")
    for s in (snode.findall("summary") + snode.findall("item") + snode.findall("billSummaries/item")) if snode is not None else []:
        raw = txt(s, "text") or html_mod.unescape(txt(s, "cdata/text"))
        plain = html_mod.unescape(re.sub(r"<[^>]+>", " ", raw))
        plain = re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", plain)).strip()
        summaries.append({"version_code": txt(s, "versionCode"), "action_date": short_date(txt(s, "actionDate")),
                          "action_desc": txt(s, "actionDesc"), "text_html": raw, "text_plain": plain})
    summaries.sort(key=lambda s: (s["action_date"], s["version_code"]))
    cbo = [{"pub_date": short_date(txt(c, "pubDate") or txt(c, "rptPubDate")), "title": txt(c, "title") or txt(c, "rptTitle"),
            "url": txt(c, "url") or txt(c, "rptUrl"), "description": txt(c, "description")}
           for c in items(bill, "cboCostEstimates")]
    cbo = [c for c in cbo if c["url"] or c["title"]]
    rnode = bill.find("committeeReports")
    reports = [txt(r, "citation") for r in (list(rnode) if rnode is not None else []) if txt(r, "citation")]

    # -- sponsor / cosponsors
    sp = items(bill, "sponsors")
    sponsor = txt(sp[0], "fullName") if sp else ""
    def name_tag(name):
        """'Rep. Gabbard, Tulsi [D-HI-2]' -> ('D', 'HI', '2'); pre-2020 files carry party/state only here."""
        m = re.search(r"\[([A-Z]+)-([A-Z]{2})(?:-(\d+|At Large))?\]", name or "")
        return (m.group(1), m.group(2), m.group(3) or "") if m else ("", "", "")

    sponsor_party = (txt(sp[0], "party") or name_tag(sponsor)[0]) if sp else ""
    sponsor_state = (txt(sp[0], "state") or name_tag(sponsor)[1]) if sp else ""
    sponsor_bioguide = txt(sp[0], "bioguideId") if sp else ""
    bill_key = f"{btype}{number}-{congress}"

    def member_rec(m):
        name = txt(m, "fullName")
        p, st, d = name_tag(name)
        return {"bioguide_id": txt(m, "bioguideId"), "full_name": name, "first_name": txt(m, "firstName"),
                "last_name": txt(m, "lastName"), "party": txt(m, "party") or p, "state": txt(m, "state") or st,
                "district": txt(m, "district") or d,
                "chamber": "Senate" if name.startswith("Sen.") else ("House" if name.startswith("Rep.") else "")}
    members = [member_rec(sp[0])] if sp else []
    cos_rows, party_count = [], Counter()
    for c in items(bill, "cosponsors"):
        members.append(member_rec(c))
        withdrawn = txt(c, "sponsorshipWithdrawnDate")
        original = txt(c, "isOriginalCosponsor").lower() == "true"
        party = txt(c, "party") or name_tag(txt(c, "fullName"))[0]
        if not withdrawn:
            party_count[party] += 1
        cos_rows.append(OrderedDict([
            ("Bill ID", bill_id), ("Cosponsor", txt(c, "fullName")), ("Party", party),
            ("State", txt(c, "state") or name_tag(txt(c, "fullName"))[1]),
            ("District", txt(c, "district") or name_tag(txt(c, "fullName"))[2]),
            ("Date joined", short_date(txt(c, "sponsorshipDate"))),
            ("Original cosponsor", "Y" if original else "N"),
            ("Withdrawn date", short_date(withdrawn)), ("Bioguide ID", txt(c, "bioguideId")),
            ("Bill sponsor", sponsor)]))
    active = [r for r in cos_rows if not r["Withdrawn date"]]
    n_original = sum(1 for r in active if r["Original cosponsor"] == "Y")
    bipartisan = "Y" if any(p and sponsor_party and p != sponsor_party for p in party_count) else "N"

    # -- committee path (from the committees structure)
    committee_names, path_parts = [], []
    for cm in committee_items(bill):
        chamber = txt(cm, "chamber") or {"h": "House", "s": "Senate", "j": "Joint"}.get(txt(cm, "systemCode")[:1], "")
        label = f"{chamber[:1]}-{txt(cm, 'name')}" if chamber else txt(cm, "name")
        committee_names.append(label)
        acts = sorted(((short_date(txt(a, "date")), re.sub(r"\s+(to|by|from)$", "", txt(a, "name")))
                       for a in items(cm, "activities")))
        piece = label + ": " + " -> ".join(f"{n} {d}" for d, n in acts)
        subs = []
        for sub in items(cm, "subcommittees"):
            sacts = sorted(((short_date(txt(a, "date")), re.sub(r"\s+(to|by|from)$", "", txt(a, "name")))
                            for a in items(sub, "activities")))
            if sacts:
                subs.append(txt(sub, "name") + ": " + " -> ".join(f"{n} {d}" for d, n in sacts))
        if subs:
            piece += " [" + " | ".join(subs) + "]"
        path_parts.append(piece)

    # -- actions: committee actions, floor votes, status events
    actions = bill.find("actions")
    action_items = list(actions.findall("item")) if actions is not None else []
    rv_urls = {}
    parsed = []
    for a in action_items:
        text = txt(a, "text")
        src = txt(a, "sourceSystem/name")
        atype = txt(a, "type")
        date = txt(a, "actionDate")
        for v in a.findall("recordedVotes/recordedVote"):
            ch, roll, url = txt(v, "chamber"), txt(v, "rollNumber"), txt(v, "url")
            if ch and roll and url:
                rv_urls[(ch.title(), int(roll))] = url
        cms = [txt(c, "name") for c in committee_items(a)] or ([txt(a, "committee/name")] if a.find("committee") is not None else [])
        parsed.append((date, txt(a, "actionTime"), text, src, atype, cms))
    parsed.sort(key=lambda x: (x[0], x[1]))

    committee_rows, vote_rows, seen, seen_c = [], [], set(), set()
    law_number, law_kind, vetoed, presented = "", "Public", False, False
    for date, _time, text, src, atype, cms in parsed:          # status events + committee steps
        m = re.search(r"Became (Public|Private) Law No:\s*([\d-]+)", text)
        if m and not law_number:
            law_number, law_kind = m.group(2), m.group(1)
        if re.search(r"Vetoed by President", text, re.I):
            vetoed = True
        if re.search(r"Presented to President|Cleared for White House", text, re.I):
            presented = True
        if is_committee_action(src, atype, text):
            ckey = (date, re.sub(r"\W+", "", text.lower())[:80])
            if ckey in seen_c:
                continue
            seen_c.add(ckey)
            activity = committee_activity(text)
            is_vote = activity in ("Ordered reported", "Forwarded by subcommittee")
            method, y, n, _p, _r = parse_method(text)
            if is_vote and not method:
                method = "Tally not stated in Congress.gov data"
            m = re.match(r"^((?:Senate )?(?:Select |Special )?Committee on [^.]+)\.", text)
            committee = "; ".join(c for c in cms if c) or (m.group(1) if m else "")
            chamber = "House" if src.lower().startswith("house") else ("Senate" if src.lower() == "senate" else "")
            committee_rows.append(OrderedDict([
                ("Bill ID", bill_id), ("Chamber", chamber), ("Committee", committee), ("Date", date),
                ("Activity", activity), ("Vote method", method if is_vote else ""),
                ("Yeas", y if is_vote else None), ("Nays", n if is_vote else None), ("Action text", text)]))

    # floor votes: chamber-native records first, Library-of-Congress restatements only as fallback
    for pass_ in ("native", "loc"):
        for date, _time, text, src, atype, cms in parsed:
            if is_committee_action(src, atype, text):
                continue
            loc = LOC_PREFIX.match(text)
            s = src.lower()
            if pass_ == "native":
                if loc:
                    continue
                if s == "house floor actions" and (text.startswith("On ") or DEEMED.search(text)):
                    chamber = "House"
                elif s == "senate" and not re.match(r"(Measure laid before|Senate Committee .* discharged|"
                                                    r"The committee substitute)", text):
                    chamber = "Senate"
                else:
                    continue
                clean = text
            else:
                if not loc:
                    continue
                chamber = (loc.group(1) or loc.group(2) or loc.group(3)).title()
                clean = text[loc.end():]
            category = vote_category(clean)
            if category is None:
                continue
            method, y, n, p, roll = parse_method(clean)
            if not method or (method != "Recorded vote" and category not in KEY_CATEGORIES):
                continue
            key = (chamber, roll) if roll else (chamber, date, re.sub(r"\W+", "", clean.lower())[:60])
            if key in seen:
                continue
            seen.add(key)
            page, xml_url = vote_links(chamber, congress, date, roll)
            if roll and (chamber, roll) in rv_urls:
                xml_url = rv_urls[(chamber, roll)]
            vote_rows.append(OrderedDict([
                ("Bill ID", bill_id), ("Chamber", chamber), ("Date", date), ("Category", category),
                ("Key vote", "Y" if category in KEY_CATEGORIES else "N"), ("Result", vote_result(clean)),
                ("Method", method), ("Yeas", y), ("Nays", n), ("Present", p),
                ("Roll/Record no.", roll), ("Action text", clean.strip()),
                ("Roll call page", page), ("Roll call XML", xml_url), ("Party split (Yea-Nay)", "")]))

    rank = {"Motion to proceed": 0, "Cloture": 1, "Passage": 3, "Resolve differences": 4,
            "Conference report": 5, "Veto override": 6}
    vote_rows.sort(key=lambda r: (r["Date"], rank.get(r["Category"], 2),
                                  0 if r["Chamber"] == origin else 1, r["Roll/Record no."] or 0))
    for lw in items(bill, "laws"):
        if not law_number:
            law_number = txt(lw, "number")
            law_kind = "Private" if "private" in txt(lw, "type").lower() else "Public"

    # -- status logic (chronological walk of the key votes)
    passed = {"House": False, "Senate": False}
    failed = {"House": False, "Senate": False}
    conf = {"House": False, "Senate": False}
    pending_diff, override = False, ""
    for r in vote_rows:
        ch, cat, res = r["Chamber"], r["Category"], r["Result"]
        ok, bad = res in SUCCESS, res in FAILURE
        other = "Senate" if ch == "House" else "House"
        if cat == "Passage":
            if ok:
                if passed[other] and AMENDED.search(r["Action text"]):
                    pending_diff = True          # second chamber changed the text
                passed[ch], failed[ch] = True, False
            elif bad and not passed[ch]:
                failed[ch] = True
        elif cat == "Resolve differences" and ok:
            passed[ch] = True
            pending_diff = bool(re.search(r"with an amendment|with amendments", r["Action text"], re.I))
        elif cat == "Conference report" and ok:
            passed[ch], conf[ch] = True, True
            pending_diff = not (conf["House"] and conf["Senate"])
        elif cat == "Veto override":
            override = "override succeeded" if ok else ("override failed" if bad else override)

    reported = any(r["Activity"] in ("Ordered reported", "Reported", "Discharged") for r in committee_rows) or \
        any(re.search(r"Placed on (the )?(Union|House|Senate Legislative) Calendar|Reported by|Reported to Senate", t)
            for _d, _t, t, *_ in parsed)
    one_chamber = btype in ("hres", "sres")
    both = passed["House"] and passed["Senate"]
    if law_number:
        status = f"Became law ({'P.L.' if law_kind == 'Public' else 'Pvt.L.'} {law_number})"
        outcome = "Passed - became law"
    elif vetoed:
        status, outcome = "Vetoed" + (f" - {override}" if override else ""), "Vetoed"
    elif one_chamber and passed[origin]:
        status, outcome = f"Agreed to in {origin}", "Adopted (resolution)"
    elif both and (not pending_diff or presented):
        if kind == "Concurrent resolution":
            status, outcome = "Agreed to by both chambers", "Adopted (resolution)"
        elif "constitution" in title.lower() and kind == "Joint resolution":
            status, outcome = "Passed both chambers (constitutional amendment - to the states)", "Passed Congress"
        else:
            status = "Presented to President" if presented else "Passed both chambers"
            outcome = "Passed Congress - awaiting President"
    elif both:
        status, outcome = "Passed both chambers - differences unresolved", "Pending (passed both, not reconciled)"
    elif failed["House"] or failed["Senate"]:
        where = " & ".join(c for c in ("House", "Senate") if failed[c])
        extra = " (passed " + " & ".join(c for c in ("House", "Senate") if passed[c]) + ")" if any(passed.values()) else ""
        status, outcome = f"Failed floor vote in {where}{extra}", "Failed (floor vote)"
    elif passed["House"] or passed["Senate"]:
        status, outcome = f"Passed {'House' if passed['House'] else 'Senate'} only", "Pending (passed one chamber)"
    elif reported:
        status, outcome = "Reported by committee / on calendar", "Pending"
    elif committee_names:
        status, outcome = "In committee", "Pending"
    else:
        status, outcome = "Introduced", "Pending"

    def floor_summary(chamber):
        parts = []
        for r in vote_rows:
            if r["Chamber"] != chamber or r["Key vote"] != "Y":
                continue
            tally = f"{r['Yeas']}-{r['Nays']}" if r["Yeas"] is not None else r["Method"].lower()
            roll = f", {'Roll' if chamber == 'House' else 'Vote'} {r['Roll/Record no.']}" if r["Roll/Record no."] else ""
            parts.append(f"{r['Category']}: {r['Result'] or '?'} {tally} ({r['Date']}{roll})")
        return "; ".join(parts)

    cm_votes = "; ".join(
        f"{r['Committee'] or r['Chamber']} {r['Date']}: {r['Activity']} - "
        + (f"{r['Yeas']}-{r['Nays']}" if r["Yeas"] is not None else r["Vote method"])
        for r in committee_rows if r["Activity"] in ("Ordered reported", "Forwarded by subcommittee"))

    # -- text versions
    versions = []
    for tv in items(bill, "textVersions"):
        urls = [txt(f, "url") for f in items(tv, "formats")]
        versions.append((txt(tv, "date"), txt(tv, "type"), urls))
    versions.sort(key=lambda v: v[0], reverse=True)
    text_rows = [{"version_date": short_date(d), "version_type": vt, "url": (u[0] if u else "")}
                 for d, vt, u in versions]
    latest_version, latest_pdf = "", ""
    if versions:
        d, vtype, urls = versions[0]
        latest_version = f"{vtype} ({short_date(d)})" if d else vtype
        for u in urls:
            m = re.search(r"(BILLS-\d+[a-z]+\d+[a-z]+|PLAW-\d+p(?:ub|v)l\d+)", u)
            if m:
                pkg = m.group(1)
                latest_pdf = f"https://www.govinfo.gov/content/pkg/{pkg}/pdf/{pkg}.pdf"
                break
        if not latest_pdf:
            latest_pdf = next((u for u in urls if u.lower().endswith(".pdf")), urls[0] if urls else "")

    row = OrderedDict([
        ("Bill ID", bill_id), ("Congress", int(congress) if congress.isdigit() else congress),
        ("Type", btype.upper()), ("Number", int(number)), ("Kind", kind),
        ("Title", title), ("Short title", short_title), ("Introduced", txt(bill, "introducedDate")), ("Origin chamber", origin),
        ("Sponsor", sponsor), ("Sponsor party", sponsor_party), ("Sponsor state", sponsor_state),
        ("Cosponsors (active)", len(active)), ("Original cosponsors", n_original),
        ("Cosponsors by party", " | ".join(f"{p or '?'} {c}" for p, c in sorted(party_count.items()))),
        ("Bipartisan cosponsorship", bipartisan), ("Policy area", policy_area),
        ("Committees referred", "; ".join(committee_names)), ("Committee path", " || ".join(path_parts)),
        ("Committee votes (ordered reported)", cm_votes),
        ("House floor (key votes)", floor_summary("House")), ("Senate floor (key votes)", floor_summary("Senate")),
        ("Passed House", "Y" if passed["House"] else "N"), ("Passed Senate", "Y" if passed["Senate"] else "N"),
        ("Status", status), ("Outcome", outcome), ("Public/Private Law", law_number),
        ("Related bill enacted", "; ".join(f"{rid} ({law}; {tag})" for rid, tag, law in related if law)),
        ("Identical bills", "; ".join(rid for rid, tag, _law in related if tag == "identical")),
        ("Related bills (#)", len(related)),
        ("Latest action date", txt(bill, "latestAction/actionDate")), ("Latest action", txt(bill, "latestAction/text")),
        ("Lens flags", lens_flags(title, policy_area, subjects)),
        ("Congress.gov page", cg_url(congress, btype, number)),
        ("Bill text (Congress.gov)", cg_url(congress, btype, number, "text")),
        ("Latest text version", latest_version), ("Latest text PDF (GovInfo)", latest_pdf),
        ("All actions & votes", cg_url(congress, btype, number, "all-actions")),
        ("Cosponsors page", cg_url(congress, btype, number, "cosponsors")),
        ("Committees page", cg_url(congress, btype, number, "committees")),
    ])
    row["_bill_key"] = bill_key          # underscore keys are for the database export only
    row["_sponsor_bioguide"] = sponsor_bioguide
    row["_source_update"] = txt(bill, "updateDate")
    return {"bill": row, "cosponsors": cos_rows, "committee": committee_rows, "votes": vote_rows,
            "congress": congress, "related": related, "members": members, "summaries": summaries,
            "subjects": subjects, "text_versions": text_rows, "cbo": cbo, "reports": reports,
            "votes_meta": {"bill_key": bill_key}}


# ----------------------------------------------------------------------------- party splits
def roll_call_members(xml_url):
    """-> list of {member_key, name, party, state, position} for one House (EVS) or Senate (LIS) roll call."""
    raw = http_get(xml_url, retries=2, timeout=60)
    root = ET.fromstring(raw)
    out = []
    for rv in root.iter("recorded-vote"):                       # House: clerk.house.gov EVS
        leg, vote = rv.find("legislator"), (rv.findtext("vote") or "").strip()
        if leg is not None:
            out.append({"member_key": leg.get("name-id", ""), "name": (leg.text or "").strip(),
                        "party": leg.get("party", ""), "state": leg.get("state", ""), "position": vote})
    if out:
        return out
    for m in root.iter("member"):                               # Senate: LIS roll_call_vote
        out.append({"member_key": (m.findtext("lis_member_id") or "").strip(),
                    "name": (m.findtext("member_full") or "").strip(), "party": (m.findtext("party") or "").strip(),
                    "state": (m.findtext("state") or "").strip(), "position": (m.findtext("vote_cast") or "").strip()})
    return out


def party_split(xml_url):
    raw = http_get(xml_url, retries=2, timeout=60)
    root = ET.fromstring(raw)
    if root.tag == "rollcall-vote" or root.find(".//totals-by-party") is not None:
        parts = []
        for t in root.iter("totals-by-party"):
            party = (t.findtext("party") or "").strip()
            if party:
                parts.append(f"{party[:1]} {t.findtext('yea-total', '0').strip()}-{t.findtext('nay-total', '0').strip()}")
        return ", ".join(parts)
    tally = Counter()
    for m in root.iter("member"):
        tally[((m.findtext("party") or "?").strip(), (m.findtext("vote_cast") or "").strip())] += 1
    parties = sorted({p for p, _ in tally})
    return ", ".join(f"{p} {tally[(p, 'Yea')]}-{tally[(p, 'Nay')]}" for p in parties)


# ----------------------------------------------------------------------------- database export
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
  bill_key TEXT PRIMARY KEY, congress INTEGER, bill_type TEXT, number INTEGER, display_id TEXT, kind TEXT,
  title TEXT, short_title TEXT, introduced_date TEXT, origin_chamber TEXT, sponsor_bioguide TEXT, policy_area TEXT,
  committees_referred TEXT, committee_path TEXT, committee_votes TEXT,
  house_floor_summary TEXT, senate_floor_summary TEXT, passed_house INTEGER, passed_senate INTEGER,
  status TEXT, outcome TEXT, law_kind TEXT, law_number TEXT, latest_action_date TEXT, latest_action TEXT,
  lens_flags TEXT, related_enacted TEXT, identical_bills TEXT,
  cosponsors_active INTEGER, original_cosponsors INTEGER, cosponsors_by_party TEXT, bipartisan INTEGER,
  congress_url TEXT, text_url TEXT, latest_text_version TEXT, latest_text_pdf TEXT,
  actions_url TEXT, cosponsors_url TEXT, committees_url TEXT, source_update TEXT, loaded_at TEXT
);
CREATE TABLE IF NOT EXISTS members (
  bioguide_id TEXT PRIMARY KEY, full_name TEXT, first_name TEXT, last_name TEXT, party TEXT, state TEXT,
  district TEXT, chamber TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS sponsorships (
  bill_key TEXT, bioguide_id TEXT, role TEXT, date_joined TEXT, is_original INTEGER, withdrawn_date TEXT,
  PRIMARY KEY (bill_key, bioguide_id, role)
);
CREATE TABLE IF NOT EXISTS committee_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, bill_key TEXT, chamber TEXT, committee TEXT, action_date TEXT,
  activity TEXT, vote_method TEXT, yeas INTEGER, nays INTEGER, action_text TEXT
);
CREATE TABLE IF NOT EXISTS floor_votes (
  vote_id TEXT PRIMARY KEY, bill_key TEXT, chamber TEXT, vote_date TEXT, category TEXT, key_vote INTEGER,
  result TEXT, method TEXT, yeas INTEGER, nays INTEGER, present INTEGER, roll_number INTEGER,
  action_text TEXT, roll_call_url TEXT, roll_call_xml TEXT, party_split TEXT
);
CREATE TABLE IF NOT EXISTS member_votes (
  vote_id TEXT, member_key TEXT, member_name TEXT, party TEXT, state TEXT, position TEXT,
  PRIMARY KEY (vote_id, member_key)
);
CREATE TABLE IF NOT EXISTS related_bills (
  bill_key TEXT, related_display TEXT, relationship TEXT, related_law TEXT,
  PRIMARY KEY (bill_key, related_display, relationship)
);
CREATE TABLE IF NOT EXISTS subjects (bill_key TEXT, subject TEXT, PRIMARY KEY (bill_key, subject));
CREATE TABLE IF NOT EXISTS summaries (
  bill_key TEXT, version_code TEXT, action_date TEXT, action_desc TEXT, text_html TEXT, text_plain TEXT,
  PRIMARY KEY (bill_key, version_code, action_date)
);
CREATE TABLE IF NOT EXISTS text_versions (
  bill_key TEXT, version_date TEXT, version_type TEXT, url TEXT, PRIMARY KEY (bill_key, version_type, version_date)
);
CREATE TABLE IF NOT EXISTS cbo_estimates (
  bill_key TEXT, pub_date TEXT, title TEXT, url TEXT, description TEXT, PRIMARY KEY (bill_key, url)
);
CREATE TABLE IF NOT EXISTS committee_reports (bill_key TEXT, citation TEXT, PRIMARY KEY (bill_key, citation));
CREATE TABLE IF NOT EXISTS rating_runs (
  run_id TEXT PRIMARY KEY, method_version TEXT, model TEXT, rater TEXT, started_at TEXT, finished_at TEXT,
  scope TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS ratings (
  rating_id INTEGER PRIMARY KEY AUTOINCREMENT, bill_key TEXT NOT NULL, axis TEXT NOT NULL,
  method_version TEXT NOT NULL, run_id TEXT, rater TEXT, rated_at TEXT,
  position REAL, position_low REAL, position_high REAL, position2 REAL, position2_low REAL, position2_high REAL,
  magnitude_label TEXT, magnitude_note TEXT, evidence_grade TEXT, confidence REAL,
  justification TEXT, sources_json TEXT, flags_json TEXT, plain_json TEXT,
  input_hash TEXT, superseded_by INTEGER, is_current INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_ratings_bill ON ratings (bill_key, axis, is_current);
CREATE INDEX IF NOT EXISTS ix_bills_outcome ON bills (outcome);
CREATE INDEX IF NOT EXISTS ix_bills_policy ON bills (policy_area);
CREATE INDEX IF NOT EXISTS ix_sponsorships_member ON sponsorships (bioguide_id);
CREATE INDEX IF NOT EXISTS ix_member_votes_member ON member_votes (member_key);
CREATE TABLE IF NOT EXISTS load_log (loaded_at TEXT, congress TEXT, measures INTEGER, source TEXT);
CREATE VIEW IF NOT EXISTS current_ratings AS SELECT * FROM ratings WHERE is_current = 1;
CREATE VIEW IF NOT EXISTS bill_cards AS
  SELECT b.bill_key, b.display_id, b.title, b.outcome, b.status, b.law_number, b.policy_area,
         MAX(CASE WHEN r.axis = 'income' THEN r.position END)              AS income_position,
         MAX(CASE WHEN r.axis = 'income' THEN r.evidence_grade END)        AS income_grade,
         MAX(CASE WHEN r.axis = 'backing' THEN r.position END)             AS backing_position,
         MAX(CASE WHEN r.axis = 'households_business' THEN r.position END)  AS households_position,
         MAX(CASE WHEN r.axis = 'households_business' THEN r.position2 END) AS business_position,
         MAX(CASE WHEN r.axis = 'plain_language' THEN r.plain_json END)    AS plain_json,
         MAX(CASE WHEN r.axis = 'timing' THEN r.plain_json END)            AS timing_json,
         MAX(CASE WHEN r.axis = 'rights' THEN r.flags_json END)            AS rights_flags
  FROM bills b LEFT JOIN ratings r ON r.bill_key = b.bill_key AND r.is_current = 1
  GROUP BY b.bill_key;
"""

BILL_COLS = [  # (db column, Bills-sheet column or callable)
    ("congress", lambda r, c: int(c)), ("bill_type", lambda r, c: r["Type"].lower()), ("number", "Number"),
    ("display_id", "Bill ID"), ("kind", "Kind"), ("title", "Title"), ("short_title", "Short title"), ("introduced_date", "Introduced"),
    ("origin_chamber", "Origin chamber"), ("sponsor_bioguide", "_sponsor_bioguide"), ("policy_area", "Policy area"),
    ("committees_referred", "Committees referred"), ("committee_path", "Committee path"),
    ("committee_votes", "Committee votes (ordered reported)"), ("house_floor_summary", "House floor (key votes)"),
    ("senate_floor_summary", "Senate floor (key votes)"),
    ("passed_house", lambda r, c: 1 if r["Passed House"] == "Y" else 0),
    ("passed_senate", lambda r, c: 1 if r["Passed Senate"] == "Y" else 0),
    ("status", "Status"), ("outcome", "Outcome"),
    ("law_kind", lambda r, c: ("Private" if "Pvt.L." in r["Status"] else "Public") if r["Public/Private Law"] else ""),
    ("law_number", "Public/Private Law"), ("latest_action_date", "Latest action date"), ("latest_action", "Latest action"),
    ("lens_flags", "Lens flags"), ("related_enacted", "Related bill enacted"), ("identical_bills", "Identical bills"),
    ("cosponsors_active", "Cosponsors (active)"), ("original_cosponsors", "Original cosponsors"),
    ("cosponsors_by_party", "Cosponsors by party"),
    ("bipartisan", lambda r, c: 1 if r["Bipartisan cosponsorship"] == "Y" else 0),
    ("congress_url", "Congress.gov page"), ("text_url", "Bill text (Congress.gov)"),
    ("latest_text_version", "Latest text version"), ("latest_text_pdf", "Latest text PDF (GovInfo)"),
    ("actions_url", "All actions & votes"), ("cosponsors_url", "Cosponsors page"), ("committees_url", "Committees page"),
    ("source_update", "_source_update"),
]


def vote_key(bill_key, r):
    tail = str(r["Roll/Record no."]) if r["Roll/Record no."] else hashlib.sha1(
        f"{r['Date']}|{r['Action text']}".encode("utf-8")).hexdigest()[:10]
    return f"{bill_key}|{r['Chamber'][:1]}|{r['Date']}|{tail}"


def write_sqlite(path, records, member_votes=None):
    """Load every parsed measure into a normalized SQLite database (re-runs refresh in place)."""
    con = sqlite3.connect(path)
    con.executescript(DB_SCHEMA)
    now = dt.datetime.now().isoformat(timespec="seconds")
    cur = con.cursor()
    for rec in records:
        b, key, congress = rec["bill"], rec["bill"]["_bill_key"], rec["congress"]
        for t in ("sponsorships", "committee_actions", "floor_votes", "related_bills", "subjects", "summaries",
                  "text_versions", "cbo_estimates", "committee_reports"):
            cur.execute(f"DELETE FROM {t} WHERE bill_key = ?", (key,))
        cur.execute("DELETE FROM member_votes WHERE vote_id IN (SELECT vote_id FROM floor_votes WHERE bill_key = ?)", (key,))
        vals = [key] + [(f(b, congress) if callable(f) else b.get(f)) for _c, f in BILL_COLS] + [now]
        cols = ["bill_key"] + [c for c, _f in BILL_COLS] + ["loaded_at"]
        cur.execute(f"INSERT OR REPLACE INTO bills ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)
        for m in rec["members"]:
            if m["bioguide_id"]:
                cur.execute("INSERT OR REPLACE INTO members VALUES (?,?,?,?,?,?,?,?,?)",
                            (m["bioguide_id"], m["full_name"], m["first_name"], m["last_name"], m["party"],
                             m["state"], m["district"], m["chamber"], now))
        if b["_sponsor_bioguide"]:
            cur.execute("INSERT OR REPLACE INTO sponsorships VALUES (?,?,?,?,?,?)",
                        (key, b["_sponsor_bioguide"], "sponsor", b["Introduced"], 1, ""))
        for c in rec["cosponsors"]:
            if c["Bioguide ID"]:
                cur.execute("INSERT OR REPLACE INTO sponsorships VALUES (?,?,?,?,?,?)",
                            (key, c["Bioguide ID"], "cosponsor", c["Date joined"],
                             1 if c["Original cosponsor"] == "Y" else 0, c["Withdrawn date"]))
        for c in rec["committee"]:
            cur.execute("INSERT INTO committee_actions (bill_key, chamber, committee, action_date, activity, "
                        "vote_method, yeas, nays, action_text) VALUES (?,?,?,?,?,?,?,?,?)",
                        (key, c["Chamber"], c["Committee"], c["Date"], c["Activity"], c["Vote method"],
                         c["Yeas"], c["Nays"], c["Action text"]))
        for v in rec["votes"]:
            vid = vote_key(key, v)
            cur.execute("INSERT OR REPLACE INTO floor_votes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (vid, key, v["Chamber"], v["Date"], v["Category"], 1 if v["Key vote"] == "Y" else 0,
                         v["Result"], v["Method"], v["Yeas"], v["Nays"], v["Present"], v["Roll/Record no."] or None,
                         v["Action text"], v["Roll call page"], v["Roll call XML"], v.get("Party split (Yea-Nay)", "")))
            for mv in (member_votes or {}).get(v["Roll call XML"], []):
                if mv["member_key"]:
                    cur.execute("INSERT OR REPLACE INTO member_votes VALUES (?,?,?,?,?,?)",
                                (vid, mv["member_key"], mv["name"], mv["party"], mv["state"], mv["position"]))
        for rid, tag, law in rec["related"]:
            cur.execute("INSERT OR REPLACE INTO related_bills VALUES (?,?,?,?)", (key, rid, tag, law))
        for s in rec["subjects"]:
            cur.execute("INSERT OR REPLACE INTO subjects VALUES (?,?)", (key, s))
        for s in rec["summaries"]:
            cur.execute("INSERT OR REPLACE INTO summaries VALUES (?,?,?,?,?,?)",
                        (key, s["version_code"], s["action_date"], s["action_desc"], s["text_html"], s["text_plain"]))
        for tv in rec["text_versions"]:
            cur.execute("INSERT OR REPLACE INTO text_versions VALUES (?,?,?,?)",
                        (key, tv["version_date"], tv["version_type"], tv["url"]))
        for c in rec["cbo"]:
            cur.execute("INSERT OR REPLACE INTO cbo_estimates VALUES (?,?,?,?,?)",
                        (key, c["pub_date"], c["title"], c["url"], c["description"]))
        for rpt in rec["reports"]:
            cur.execute("INSERT OR REPLACE INTO committee_reports VALUES (?,?)", (key, rpt))
    cur.execute("INSERT INTO load_log VALUES (?,?,?,?)",
                (now, records[0]["congress"] if records else "", len(records), "congress_catalog.py"))
    con.commit()
    con.close()


# ----------------------------------------------------------------------------- output
LINK_COLS = {"Congress.gov page", "Bill text (Congress.gov)", "Latest text PDF (GovInfo)",
             "All actions & votes", "Cosponsors page", "Committees page", "Roll call page", "Roll call XML"}
WIDTHS = {"Bill ID": 13, "Title": 60, "Sponsor": 30, "Committees referred": 40, "Committee path": 60,
          "Committee votes (ordered reported)": 45, "House floor (key votes)": 55,
          "Senate floor (key votes)": 55, "Status": 30, "Outcome": 28, "Latest action": 50,
          "Action text": 70, "Cosponsor": 32, "Committee": 36, "Cosponsors by party": 18,
          "Policy area": 26, "Latest text version": 28, "Bill sponsor": 30}


def write_workbook(path, sheets, meta):
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook(write_only=True)
    head_font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    head_fill = PatternFill("solid", fgColor="1F3864")
    body_font = Font(name="Arial", size=10)
    link_font = Font(name="Arial", size=10, color="0563C1", underline="single")

    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        cols = list(rows[0].keys()) if rows else ["(no rows)"]
        for i, c in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = WIDTHS.get(c, 12 if c not in LINK_COLS else 11)
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{max(2, len(rows) + 1)}"
        header = []
        for c in cols:
            cell = WriteOnlyCell(ws, value=c)
            cell.font, cell.fill = head_font, head_fill
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            header.append(cell)
        ws.append(header)
        for r in rows:
            out = []
            for c in cols:
                v = r.get(c)
                cell = WriteOnlyCell(ws, value=("Open" if (c in LINK_COLS and v) else v))
                if c in LINK_COLS and v:
                    cell.hyperlink, cell.font = v, link_font
                else:
                    cell.font = body_font
                out.append(cell)
            ws.append(out)

    # Summary sheet with live formulas against the Bills sheet
    bills = sheets.get("Bills", [])
    cols = list(bills[0].keys()) if bills else []
    ws = wb.create_sheet("Summary", 0)
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 14
    bold = Font(name="Arial", bold=True, size=10)

    def put(label, formula=None, is_head=False):
        a = WriteOnlyCell(ws, value=label)
        a.font = bold if is_head else body_font
        b = WriteOnlyCell(ws, value=formula)
        b.font = body_font
        ws.append([a, b])

    put(f"{ordinal(meta['congress'])} Congress catalog - generated {meta['generated']}", is_head=True)
    put("Source: GovInfo Bill Status bulk data (GPO / Library of Congress)")
    put("")
    if cols:
        def col(c):
            return get_column_letter(cols.index(c) + 1)
        n = len(bills) + 1
        put("Measures in catalog", f"=COUNTA(Bills!A2:A{n})", True)
        put("")
        put("By outcome", None, True)
        for o in sorted({b["Outcome"] for b in bills}):
            put(o, f'=COUNTIF(Bills!{col("Outcome")}2:{col("Outcome")}{n},"{o}")')
        put("")
        put("By measure type", None, True)
        for t in [k.upper() for k in TYPE_INFO if any(b["Type"] == k.upper() for b in bills)]:
            put(t, f'=COUNTIF(Bills!{col("Type")}2:{col("Type")}{n},"{t}")')
        put("")
        put("Floor action", None, True)
        put("Passed House", f'=COUNTIF(Bills!{col("Passed House")}2:{col("Passed House")}{n},"Y")')
        put("Passed Senate", f'=COUNTIF(Bills!{col("Passed Senate")}2:{col("Passed Senate")}{n},"Y")')
        put("")
        put("Vehicle check", None, True)
        oc, rc = col("Outcome"), col("Related bill enacted")
        put("Not enacted itself, but a related measure became law",
            f'=COUNTIFS(Bills!{oc}2:{oc}{n},"<>Passed - became law",Bills!{rc}2:{rc}{n},"?*")')
        put("")
        put("Lens flags (keyword screen)", None, True)
        for lens in LENSES:
            put(lens, f'=COUNTIF(Bills!{col("Lens flags")}2:{col("Lens flags")}{n},"*{lens}*")')
    try:
        wb.calculation.fullCalcOnLoad = True
    except Exception:  # noqa: BLE001
        pass

    about = wb.create_sheet("About")
    about.column_dimensions["A"].width = 120
    for line in meta["notes"]:
        c = WriteOnlyCell(about, value=line)
        c.font = body_font
        about.append([c])
    wb.save(path)


NOTES = [
    "HOW TO READ THIS CATALOG",
    "Bills: one row per measure. Cosponsors: one row per cosponsor. Committee_Actions: every committee step.",
    "Build one workbook per Congress: Bill ID is the join key across sheets and repeats across Congresses (H.R. 1 exists in every one).",
    "Floor_Votes: every recorded House/Senate vote, plus voice votes and unanimous consent on key questions.",
    "",
    "Outcome definitions",
    "  Passed - became law: has a Public (or Private) Law number.",
    "  Vetoed: President vetoed; see Status for whether an override was attempted.",
    "  Failed (floor vote): a passage vote failed and the measure has not passed that chamber since.",
    "  Pending: still alive. Every pending measure dies when the Congress ends (Jan 3, 2027 for the 119th).",
    "  Adopted (resolution): simple or concurrent resolution agreed to (these do not go to the President).",
    "",
    "Known data limits",
    "  House committee votes usually include the tally ('Ordered to be Reported ... by the Yeas and Nays: 26 - 21').",
    "  Senate committee tallies are usually NOT in Congress.gov data; check the committee report or committee website.",
    "  Voice votes and unanimous consent have no individual tallies by design.",
    "  'Failed' is a fact about a vote, not always the end of a bill - a failed measure can be revived or folded into another bill.",
    "  Vehicles: a bill's own Outcome can read 'Pending' or 'Passed House only' even though its text became law inside",
    "  another measure (e.g., a standalone tax bill folded into a reconciliation act). 'Related bill enacted' lists related",
    "  measures (Library of Congress / CRS relationship data) that became law - a lead to verify against the enacted text,",
    "  not proof this bill's provisions were included. 'identical' = companion text in the other chamber.",
    "  Lens flags are keyword screens, not legal conclusions. 'Tax' = hit in the title or CRS policy area (strong);",
    "  'Tax (subj.)' = hit only in CRS subject terms (weaker - large omnibus bills carry hundreds of subject terms).",
    "",
    "Sources",
    "  Bill Status XML: https://www.govinfo.gov/bulkdata/BILLSTATUS (updated daily by GPO / Library of Congress)",
    "  House roll calls: https://clerk.house.gov   Senate roll calls: https://www.senate.gov/legislative/votes_new.htm",
]


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--congress", type=int, default=119)
    ap.add_argument("--types", default="law", help="'law' (hr,s,hjres,sjres), 'all', or comma list e.g. hr,s")
    ap.add_argument("--since", default="2025-01-01", help="keep measures introduced on/after this date")
    ap.add_argument("--local-dir", help="parse BILLSTATUS XML already on disk instead of downloading")
    ap.add_argument("--cache", default="billstatus_cache")
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    ap.add_argument("--party-breakdown", action="store_true", help="fetch each roll call for party splits")
    ap.add_argument("--limit", type=int, default=0, help="stop after N measures (testing)")
    ap.add_argument("--out", default="")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--db", default="", help="also load everything into this SQLite file (e.g. congress_119.sqlite)")
    ap.add_argument("--no-xlsx", action="store_true", help="skip the Excel workbook (database/CSV only)")
    args = ap.parse_args()

    types = LAW_CAPABLE if args.types == "law" else list(TYPE_INFO) if args.types == "all" else \
        [t.strip().lower() for t in args.types.split(",") if t.strip()]
    out = args.out or f"congress_{args.congress}_catalog.xlsx"
    bills, cosp, cmte, votes, rel_info, records = [], [], [], [], [], []
    congress_box = [str(args.congress)]

    def ingest(stream):
        for fname, data in stream:
            try:
                rec = parse_billstatus(data)
            except ET.ParseError as e:
                log(f"    skip {fname}: {e}")
                continue
            if not rec or rec["bill"]["Introduced"] < args.since:
                continue
            congress_box[0] = rec["congress"] or congress_box[0]
            bills.append(rec["bill"])
            rel_info.append((rec["congress"], rec["related"]))
            records.append(rec)
            cosp.extend(rec["cosponsors"])
            cmte.extend(rec["committee"])
            votes.extend(rec["votes"])
            if args.limit and len(bills) >= args.limit:
                return True
        return False

    if args.local_dir:
        log(f"Parsing local files in {args.local_dir}")
        ingest(local_files(args.local_dir))
    else:
        for t in types:
            log(f"[{t}] {ordinal(args.congress)} Congress")
            try:
                if ingest(fetch_type(args.congress, t, args.cache, args.refresh)):
                    break
            except Exception as e:  # noqa: BLE001
                log(f"    ERROR fetching {t}: {e}")
            log(f"    running total: {len(bills):,} measures")

    if not bills:
        sys.exit("No measures parsed - check your connection or --local-dir path.")

    # Cross-check related measures against this catalog's own outcomes (fresher than the
    # related-bill snapshot embedded in each source file).
    law_by_key = {(cong, b["Bill ID"]): ("Pvt.L. " if "Pvt.L." in b["Status"] else "P.L. ") + b["Public/Private Law"]
                  for b, (cong, _rel) in zip(bills, rel_info) if b["Public/Private Law"]}
    for b, (cong, rel) in zip(bills, rel_info):
        add = [f"{rid} ({law_by_key[(cong, rid)]}; {tag})" for rid, tag, law in rel
               if not law and (cong, rid) in law_by_key]
        if add:
            b["Related bill enacted"] = "; ".join(x for x in [b["Related bill enacted"]] + add if x)
    type_order = {k.upper(): i for i, k in enumerate(TYPE_INFO)}
    order = sorted(range(len(bills)), key=lambda i: (type_order.get(bills[i]["Type"], 99), bills[i]["Number"]))
    bills, rel_info, records = [bills[i] for i in order], [rel_info[i] for i in order], [records[i] for i in order]

    if args.party_breakdown:
        uniq = {r["Roll call XML"] for r in votes if r["Roll call XML"]}
        log(f"Fetching party splits for {len(uniq):,} roll calls ...")
        splits, fails = {}, 0

        member_votes = {}

        def one(u):
            try:
                members = roll_call_members(u)
                if members:
                    tally = Counter((m["party"] or "?", m["position"]) for m in members)
                    parties = sorted({p for p, _ in tally})
                    yes, no = ("Yea", "Aye"), ("Nay", "No")
                    split = ", ".join(f"{p} {sum(tally[(p, y)] for y in yes)}-{sum(tally[(p, n)] for n in no)}"
                                      for p in parties)
                    return u, split, members
                return u, party_split(u), []
            except Exception:  # noqa: BLE001
                return u, None, []
        with ThreadPoolExecutor(max_workers=6) as pool:
            for u, s, members in pool.map(one, sorted(uniq)):
                if s is None:
                    fails += 1
                else:
                    splits[u], member_votes[u] = s, members
        for r in votes:
            r["Party split (Yea-Nay)"] = splits.get(r["Roll call XML"], "")
        if fails:
            log(f"    {fails} roll calls could not be fetched (site blocked or unavailable); left blank")

    meta = {"congress": congress_box[0], "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "notes": NOTES}
    public = [OrderedDict((k, v) for k, v in b.items() if not k.startswith("_")) for b in bills]
    sheets = OrderedDict([("Bills", public), ("Cosponsors", cosp), ("Committee_Actions", cmte), ("Floor_Votes", votes)])
    if args.db:
        write_sqlite(args.db, records, member_votes if args.party_breakdown else None)
        log(f"Loaded {len(records):,} measures into {args.db}")
    if not args.no_xlsx:
        write_workbook(out, sheets, meta)
    log(f"\n{'Wrote ' + out + ': ' if not args.no_xlsx else ''}{len(bills):,} measures | {len(cosp):,} cosponsorships | "
        f"{len(cmte):,} committee actions | {len(votes):,} floor votes")
    outcomes = Counter(b["Outcome"] for b in bills)
    for k, v in outcomes.most_common():
        log(f"    {k:<42} {v:>7,}")

    if args.csv:
        stem = os.path.splitext(out)[0]
        for name, rows in sheets.items():
            if rows:
                with open(f"{stem}_{name}.csv", "w", newline="", encoding="utf-8-sig") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    w.writerows(rows)
        log(f"CSVs written with prefix {stem}_")


if __name__ == "__main__":
    main()
