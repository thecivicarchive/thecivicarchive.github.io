"""
Indiana: the Indiana Election Division's own lists and results. Indiana has nine House seats and no Senate race in
2026; the districts are the 2024 lines.

  November ballot   the Election Division's "2026 General Election Candidate List", a workbook linked from its
                    Candidate Information page (in.gov/sos/elections/candidate-information). The page is read first
                    and the link followed, so a corrected address is picked up by itself. As of 2026-09-30 the link
                    (.../files/Candidate_List_Abbreviated_2026..9.11.xlsx) is answered with in.gov's "Page Not Found"
                    page, most likely because of the two dots in the file's name; a copy of the workbook saved by hand
                    as ballot_cache/in/in_candidate_list_2026_general.xlsx is read instead when one is there. Without
                    the list no November candidates are stored: the primary winners alone would leave off the
                    Libertarian and independent candidates, and a ballot vacancy filled since May.
  primary fields    the Election Division's certified results of the May 5, 2026 primary, from its election results
                    site (enr.indianavoters.in.gov): settings.json says which election the site holds and whether it
                    is certified; statewideElectionsC names the office category for US Representative; its OffCatC
                    file gives, per district, every candidate's name as on the ballot, party, votes and whether they
                    won. The results carry no write-in line. A field is a party primary with two candidates or more;
                    pct is the share of that party's primary vote in the district.
  cross-check       the Election Division's "2026 Primary Candidate List" workbook (dated 3.25.26): every candidate on
                    the results must be on the list for the same district and party, and the other way round.

Both workbooks have one heading row naming the election, then the columns OFFICE, CANDIDATE NAME, POLITICAL PARTY,
DISTRICT and DATE FILED. Columns are taken by name: OFFICE, CANDIDATE NAME, POLITICAL PARTY and DISTRICT, and a STATUS
or BALLOT ORDER column if the general list carries one; nothing else is read. The results' party numbers are turned
into names with the site's own party table (1020 Democratic, 1021 Republican). Only the US Representative rows are
kept, as JSON in ballot_cache/in/, with the SHA-256 of the file they came from; the workbooks themselves (every office
in the state, down to precinct committeemen) are not kept. Names are printed first name first in ordinary capitals;
a name in capitals or written "Last, First" would be turned round and noted.
"""

import datetime as dt
import hashlib
import html as H
import io
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

import openpyxl

from ballot.common import house_id, party_code, record_source
from ballot.lists.tx import proper
from states import net

PAGE = "https://www.in.gov/sos/elections/candidate-information/"
ENR = "https://enr.indianavoters.in.gov/site/data/"
ENR_SITE = "https://enr.indianavoters.in.gov/site/index.html"
PRIMARY = "2026-05-05"
GENERAL_LABEL = "2026 General Election Candidate List"
PRIMARY_LABEL = "2026 Primary Candidate List"
KEEP = ("OFFICE", "CANDIDATE NAME", "POLITICAL PARTY", "DISTRICT")
OPTIONAL = ("STATUS", "CANDIDATE STATUS", "BALLOT ORDER")
ORDINAL = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9}
SUFFIX = re.compile(r"(JR|SR|II|III|IV|V)\.?", re.I)
GONE = ("withdr", "disqual", "remov", "denied", "deceas", "vacan", "inactive")
CAPS_NOTE = "Indiana's list prints names in capitals; they are shown here in ordinary capitals."
WRITE_IN_NOTE = "Write-in candidate: the name is not printed on the ballot."


def district_of(text):
    """'United States Representative, Eighth District' or '... (8) District' -> 8"""
    t = (text or "").strip()
    m = re.search(r"\((\d+)\) District$", t) or re.search(r"\b(\d+)(?:st|nd|rd|th)? District$", t)
    if m:
        return int(m.group(1))
    m = re.search(r",\s*(\w+) District$", t)
    return ORDINAL.get(m.group(1).lower()) if m else None


def shown(raw):
    """(name as shown, whether it was printed in capitals). 'Hall, Thomas' -> 'Thomas Hall'; 'Thomas D. Hall, Jr.' stays."""
    name = re.sub(r"\s+", " ", str(raw or "")).strip()
    last, sep, rest = name.partition(",")
    if sep and rest.strip() and not SUFFIX.fullmatch(rest.strip()):
        words = last.split()
        name = " ".join(rest.split() + [w for w in words if not SUFFIX.fullmatch(w)] + [w for w in words if SUFFIX.fullmatch(w)])
    caps = any(c.isalpha() for c in name) and name == name.upper()
    return (proper(name) if caps else name), caps


def links(page):
    """{label: absolute address} for every link on the Candidate Information page."""
    out = {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        label = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", m.group(2)))).strip()
        if label and label not in out:
            out[label] = urljoin(PAGE, H.unescape(m.group(1)))
    return out


def fetch_workbook(url, say):
    """The workbook's bytes, or None when the address does not give one (in.gov answers a missing file with its
    Page Not Found page and status 200, so the bytes themselves are checked)."""
    try:
        data = net.get(url, accept="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*")
    except (HTTPError, URLError, OSError) as e:
        say(f"      {url}: {e}")
        return None
    if data[:2] != b"PK":
        say(f"      {url}: in.gov answered with a web page (\"{'Page Not Found' if b'Page Not Found' in data[:4000] else 'not a workbook'}\"), not the workbook")
        return None
    return data


def workbook_rows(data, election):
    """(heading, [rows]) from one of the Division's candidate list workbooks: the heading row must name the election;
    the columns are taken by name (KEEP, and OPTIONAL where present), and only the US Representative rows are kept."""
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    heading, heads = None, None
    for i, r in enumerate(rows):
        cells = [str(c).strip() if c is not None else "" for c in r]
        if heading is None and any(cells):
            heading = " ".join(c for c in cells if c)
        if all(k in cells for k in KEEP):
            heads = cells
            break
        if i > 20:
            break
    if not heads:
        raise SystemExit(f"Indiana: the candidate list's columns changed (no row with {', '.join(KEEP)})")
    if election not in (heading or "").upper():
        raise SystemExit(f"Indiana: the candidate list is not the {election} (its heading reads {heading!r})")
    idx = {k: heads.index(k) for k in KEEP + OPTIONAL if k in heads}
    out = []
    for r in rows:
        rec = {k: (str(r[i]).strip() if i < len(r) and r[i] is not None else "") for k, i in idx.items()}
        if re.sub(r"[^A-Z]", "", rec["OFFICE"].upper()) in ("USREPRESENTATIVE", "UNITEDSTATESREPRESENTATIVE"):
            out.append(rec)
    return heading, out


def dated(url):
    """The date the Division writes into a list's file name (Primary-Candidate-List-3.25.26, ..._2026..9.11)."""
    m = re.search(r"(?:^|[^\d])(\d{1,2})\.(\d{1,2})(?:\.(\d{2}))?\.xlsx", url)
    if not m:
        return ""
    return f"20{m.group(3) or '26'}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"


def list_json(folder, kind, url, say, max_age_days, election, hand=None):
    """A candidate list's federal rows, as JSON in the cache: fetched afresh when older than max_age_days, else read
    back. A workbook saved by hand (hand) is read when the address gives none. Returns the JSON's path, or None."""
    path = os.path.join(folder, f"in_{kind}_list_2026_federal.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        return path
    data = fetch_workbook(url, say) if url else None
    origin = url
    if data is None and hand and os.path.exists(hand):
        data, origin = open(hand, "rb").read(), "saved by hand: " + os.path.basename(hand)
        if data[:2] != b"PK":
            raise SystemExit(f"Indiana: {hand} is not a workbook")
    if data is None:
        if os.path.exists(path):
            say(f"      using the copy of the {kind} list read earlier")
            return path
        return None
    heading, rows = workbook_rows(data, election)
    meta = {"url": url, "origin": origin, "sha256": hashlib.sha256(data).hexdigest(), "heading": heading,
            "published": dated(url) if origin == url else "", "read": dt.date.today().isoformat(), "rows": rows}
    json.dump(meta, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def enr_json(name):
    return json.loads(net.get(ENR + name + ".json", accept="application/json").decode("utf-8-sig"))


def primary_results(folder, say):
    """The certified May 5 results for US Representative, as JSON in the cache (kept fields only). The results site
    will turn to the November election; the copy on disk is used once it no longer holds the primary."""
    path = os.path.join(folder, "in_2026_primary_results_congress.json")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 30 * 86400:
        return path
    settings = enr_json("settings")
    settings = settings.get("Root", settings)
    if settings.get("CurrentElection") != "05/05/2026" or settings.get("ElectionType") != "P":
        if os.path.exists(path):
            say("      the results site no longer holds the May 5 primary; using the copy read earlier")
            return path
        raise SystemExit(f"Indiana: the results site holds the election of {settings.get('CurrentElection')}, not the May 5, 2026 primary")
    if settings.get("Certified") != "T":
        raise SystemExit("Indiana: the May 5 primary results are not marked certified on the results site")
    parties = settings["PolParties"]["PolParty"]
    parties = {p["POLITICALPARTYID"]: p["PARTY_NAME"] for p in (parties if isinstance(parties, list) else [parties])}
    version = settings["VersionType"]
    offices = enr_json(f"statewideElectionsC_{version}")
    offices = offices.get("Root", offices)
    cat = [it["OFFICECATEGORYID"] for grp in offices["List"] for it in ((grp.get("Items") or {}).get("Item") or [])
           if it.get("OFFICE_CATEGORY_NAME") == "US Representative"]
    if len(cat) != 1:
        raise SystemExit("Indiana: the results site does not list one office category for US Representative")
    data = enr_json(f"OffCatC_{cat[0]}_{version}")
    data = data.get("Root", data)
    races = []
    for race in data["StatewideSummary"]["Race"]:
        cands = race["Candidates"]["Candidate"]
        cands = cands if isinstance(cands, list) else [cands]
        races.append({"office": race["OFFICE_TITLE"], "sort": race["SubSortOrder"], "seats": race["NumofSeats"],
                      "candidates": [{"name": c["NAME_ON_BALLOT"], "party": parties.get(c["POLITICALPARTYID"], c["PARTY"]),
                                      "votes": int(c["TOTAL"]), "winner": c["isWinner"] == "T"} for c in cands]})
    keep = {"election": settings["CurrentElection"], "certified": settings["Certified"], "version": settings["VersionCode"],
            "written": data.get("WriteTime"), "category": cat[0], "version_type": version, "races": races}
    json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "in")
    os.makedirs(folder, exist_ok=True)
    page = net.get(PAGE).decode("utf-8", "replace")
    found = links(page)
    general_url, primary_url = found.get(GENERAL_LABEL), found.get(PRIMARY_LABEL)
    if not primary_url:
        raise SystemExit(f"Indiana: the Candidate Information page no longer links \"{PRIMARY_LABEL}\"")
    if not general_url:
        say(f"      the Candidate Information page no longer links \"{GENERAL_LABEL}\"")
    hand = os.path.join(folder, "in_candidate_list_2026_general.xlsx")
    gpath = list_json(folder, "general", general_url, say, 2, "2026 GENERAL ELECTION", hand=hand)
    ppath = list_json(folder, "primary", primary_url, say, 30, "2026 PRIMARY ELECTION")
    rpath = primary_results(folder, say)
    results = json.load(open(rpath, encoding="utf-8"))
    plist = json.load(open(ppath, encoding="utf-8"))

    rows = []
    # the primary fields, from the certified results
    listed = {}
    for r in plist["rows"]:
        d = district_of(r["DISTRICT"])
        listed.setdefault((house_id("IN", d), r["POLITICAL PARTY"]), set()).add(shown(r["CANDIDATE NAME"])[0])
    fields, seen, differ = {}, {}, []
    for race in results["races"]:
        d = district_of(race["office"])
        if d != district_of(race["sort"]) or not d:
            raise SystemExit(f"Indiana: could not read the district of {race['office']!r}")
        rid = house_id("IN", d)
        for c in race["candidates"]:
            fields.setdefault((rid, c["party"]), []).append(c)
            seen.setdefault((rid, c["party"]), set()).add(shown(c["name"])[0])
    for key in sorted(set(listed) | set(seen)):
        if listed.get(key, set()) != seen.get(key, set()):
            differ.append(f"{key[0]} {key[1]}: list {sorted(listed.get(key, set()) - seen.get(key, set()))}, "
                          f"results {sorted(seen.get(key, set()) - listed.get(key, set()))}")
    nfields = 0
    for (rid, party), cands in sorted(fields.items()):
        winners = [c for c in cands if c["winner"]]
        if len(winners) != 1:
            raise SystemExit(f"Indiana: {rid} {party} primary has {len(winners)} winners marked")
        if len(cands) < 2:
            continue
        nfields += 1
        total = sum(c["votes"] for c in cands)
        code = {"Democratic": "DEM", "Republican": "REP"}.get(party, party[:3].upper())
        for c in cands:
            name, caps = shown(c["name"])
            rows.append((rid, f"primary-{code}", PRIMARY, name, party, party_code(party), None, 0, 0, c["votes"],
                         round(100 * c["votes"] / total, 1) if total else None, "advanced" if c["winner"] else "lost",
                         None, None, "in-ied-2026-primary-results", CAPS_NOTE if caps else None))

    # the November ballot, from the general list
    general, gone = [], []
    glist = json.load(open(gpath, encoding="utf-8")) if gpath else None
    if glist:
        order = {}
        for r in glist["rows"]:
            d = district_of(r["DISTRICT"])
            if not d:
                raise SystemExit(f"Indiana: could not read the district of {r['DISTRICT']!r} on the general list")
            status = (r.get("STATUS") or r.get("CANDIDATE STATUS") or "").lower()
            if any(g in status for g in GONE):
                gone.append(r)
                continue
            rid = house_id("IN", d)
            name, caps = shown(r["CANDIDATE NAME"])
            party = r["POLITICAL PARTY"]
            write_in = int("write" in (party + " " + r["OFFICE"]).lower())
            order[rid] = order.get(rid, 0) + 1
            given = r.get("BALLOT ORDER", "")
            note = " ".join(n for n in (CAPS_NOTE if caps else "", WRITE_IN_NOTE if write_in else "") if n) or None
            general.append((rid, "general", "2026-11-03", name, party, party_code(party),
                            int(given) if str(given).isdigit() else order[rid], 0, write_in, None, None, None, None, None,
                            "in-ied-2026-general-list", note))
        rows = general + rows

    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-IN-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        if glist:
            record_source(con, "in-ied-2026-general-list", path=gpath, level="federal", state="IN", kind="official candidate list",
                          agency="Indiana Election Division", title=f"2026 General Election Candidate List ({glist['heading']})",
                          url=glist["url"] or PAGE, published=glist["published"], rows=len(glist["rows"]),
                          note=f"Workbook SHA-256 {glist['sha256'][:16]}...; {'saved by hand' if glist['origin'] != glist['url'] else 'fetched from the link on the Candidate Information page'}. "
                               f"US Representative rows kept (office, name, party, district); list order within each district. "
                               f"Withdrawn or removed, left off: {len(gone)}.")
        record_source(con, "in-ied-2026-primary-list", path=ppath, level="federal", state="IN", kind="official candidate list",
                      agency="Indiana Election Division", title=f"2026 Primary Candidate List ({plist['heading']})",
                      url=plist["url"], published=plist["published"], rows=len(plist["rows"]),
                      note=f"Workbook SHA-256 {plist['sha256'][:16]}...; US Representative rows kept (office, name, party, district). "
                           "Used to check the primary results: " + ("every candidate agrees." if not differ else "differences: " + "; ".join(differ)))
        record_source(con, "in-ied-2026-primary-results", path=rpath, level="federal", state="IN", kind="official results",
                      agency="Indiana Election Division", title="Indiana Election Results: May 5, 2026 Primary Election, US Representative (certified)",
                      url=ENR + f"OffCatC_{results['category']}_{results.get('version_type', 'A')}.json", rows=sum(len(r["candidates"]) for r in results["races"]),
                      note=f"From the Division's election results site ({ENR_SITE}), marked certified; version {results['version']}. "
                           "Votes as the site gives them; the results carry no write-in line, so each field's total is the sum of its candidates' votes.")
    n = len(general)
    if glist:
        say(f"    Indiana: {len({r[0] for r in general})} House districts, {n} candidates on the November ballot ({len(gone)} withdrawn left off); "
            f"{nfields} party primaries with a field, votes from the certified results")
    else:
        say(f"    Indiana: the November list could not be read: the Election Division's page links \"{GENERAL_LABEL}\" to {general_url}, "
            f"which in.gov answers with its Page Not Found page. Save the workbook as {hand} if a copy can be had. "
            f"{nfields} party primaries with a field stored, votes from the certified results")
    if differ:
        say("      the primary candidate list and the results differ: " + "; ".join(differ))
    return n
