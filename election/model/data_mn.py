"""election/model/data_mn.py - Minnesota's past results for the model: the Secretary of State's certified precinct
tables 2012-2024, MEDSL's public-domain precinct files (secondary, labelled), the official totals every contest is
checked against, and every past precinct carried onto today's precinct lines (model.md 1.1-1.2; ARCHITECTURE.md 4.1).

    python -m election.model.data_mn            fetch what is missing (once), check every contest, print the result
    python -m election.model.data_mn --selftest the arithmetic on made-up rows; downloads nothing

SOURCES
  official   "Minnesota General Election Results, 2012-2020" and "2022-2030" (Office of the Minnesota Secretary of State,
             published on the Minnesota Geospatial Commons; the metadata says the results are those certified by the State
             Canvassing Board and the statistics by the county canvassing boards): one table per general election, one row
             per precinct, read from the feature services at enterprise.gisdata.mn.gov, attributes only (the allowlist
             below), cached in election_cache/model/mn/commons/. The Secretary's own sites (*.sos.mn.gov) are never asked.
  official   Office of the Clerk, U.S. House of Representatives, "Statistics of the Presidential and Congressional
             Election" 2012-2024 (clerk.house.gov; compiled from official sources): the control for President, U.S.
             Senate and U.S. House. The 2020 and 2024 copies are the kit's own (states_cache/mn_local/, read only).
  academic   Minnesota Historical Election Archive (University of Minnesota Libraries Publishing), which transcribes the
             State Canvassing Board's reports: the control for the constitutional offices and the Legislature. Only each
             row's party and votes, the page's title and the election date are kept; names, gender and biographies never.
  secondary  MIT Election Data and Science Lab, Minnesota precinct files 2018, 2022, 2024 (CC0; compiled from the
             Secretary's results files): judges, county offices and soil and water for the model, and a second look at
             the Legislature. Fields allowlisted (MEDSL_KEEP); never the authority.

THE CHECK (`check_contests`): for every contest of every table 2012-2024 (one per office and district), each precinct's
candidates must add up to the precinct's own total, and the precincts must add up to the official total of every line
(DFL, Republican, all candidates and write-ins) in the source named above. A contest with no reachable official total is
listed with the reason. Nothing is changed to make a sum fit.

TODAY'S LINES (`on_today_lines`): every past precinct carried onto today's precincts, through the Census Bureau's 2020
voting districts and blocks where the record allows, else by name, else within its city or township by 2020
population; votes with nowhere to go are counted and listed (the function's own notes say how). Method version
LINES_METHOD.
"""

import argparse
import csv
import html
import io
import json
import os
import re
import sys
import time
import zipfile
from urllib.parse import quote

from election.model import HERE, cache_dir, fetch, load_json, save_json, sha_bytes, sha_file, source, FetchError

DATA_METHOD = "mn-data-1.0"
LINES_METHOD = "lines-2.0"
YEARS = (2012, 2014, 2016, 2018, 2020, 2022, 2024)
DATES = {2012: "2012-11-06", 2014: "2014-11-04", 2016: "2016-11-08", 2018: "2018-11-06", 2020: "2020-11-03", 2022: "2022-11-08",
         2024: "2024-11-05"}
SERVICES = "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_sos/"
ITEM_OF = {y: ("bdry_electionresults_2022_2030" if y >= 2022 else "bdry_electionresults_2012_2020") for y in YEARS}
KIT_META = {y: os.path.join(HERE, "states_cache", "mn_local",
                            "sos_electionresults_2022_2030_metadata.json" if y >= 2022 else "sos_electionresults_2012_2020_metadata.json") for y in YEARS}
TODAY = os.path.join(HERE, "states_cache", "mn_local", "sos_votingdistricts_today.json")
PAGE = 2000

PLACE = ["vtdid", "pctname", "pctcode", "mcdname", "mcdfips", "ctu_type", "countyname", "countycode", "countyfips", "congdist",
         "mnsendist", "mnlegdist", "ctycomdist", "juddist", "swcdist", "ward", "hospdist", "parkdist"]
STATS = ["reg7am", "edr", "signatures", "ab_mb", "regmilovab", "fedonlyab", "presonlyab", "totvoting", "mailballot", "tabmodel",
         "tabsystem"]
# column prefix: (office, which column names the district, office class for roll-off, archive office code)
OFFICES = {
    "usprs": ("President", None, "top", "10"), "ussen": ("U.S. Senate", None, "federal", "11"),
    "ussse": ("U.S. Senate, special", None, "federal", "11"), "usrep": ("U.S. House", "congdist", "federal", "12"),
    "mngov": ("Governor", None, "statewide", "20"), "mnsos": ("Secretary of State", None, "statewide", "22"),
    "mnag": ("Attorney General", None, "statewide", "23"), "mnaud": ("State Auditor", None, "statewide", "24"),
    "mnsen": ("State Senate", "mnsendist", "legislature", "70"), "mnleg": ("State House", "mnlegdist", "legislature", "71"),
    "mnca1": ("Constitutional amendment 1", None, "question", None), "mnca2": ("Constitutional amendment 2", None, "question", None),
}
QUESTION_PARTS = ("yes", "no")

CLERK_KIT = {2020: os.path.join(HERE, "states_cache", "mn_local", "clerk_statistics2020.pdf"),
             2024: os.path.join(HERE, "states_cache", "mn_local", "clerk_statistics2024.pdf")}
CLERK_URLS = ["https://clerk.house.gov/member_info/electionInfo/{y}/statistics{y}.pdf",
              "https://clerk.house.gov/member_info/electionInfo/{y}election.pdf"]
ARCHIVE = "https://mn.electionarchives.lib.umn.edu/election/{id}/"

MEDSL = {
    2018: ("https://raw.githubusercontent.com/MEDSL/2018-elections-official/master/individual_states/2018-mn-precinct-general.zip",
           "2018-mn-precinct-general.zip"),
    2022: ("https://raw.githubusercontent.com/MEDSL/2022-elections-official/main/individual_states/2022-mn-local-precinct-general.zip",
           "2022-mn-local-precinct-general.zip"),
    2024: ("https://raw.githubusercontent.com/MEDSL/2024-elections-official/main/individual_states/mn24.zip", "mn24.zip"),
}
MEDSL_NOT_READ = {2020: "MEDSL's 2020 Minnesota file sits on Harvard Dataverse behind a guestbook form that asks for personal "
                        "details before download (checked 2026-10-10); it is not read. 2016's is part of an 82 MB national file "
                        "not needed here."}
MEDSL_KEEP = ["precinct", "office", "party_detailed", "party_simplified", "mode", "votes", "county_name", "county_fips",
              "jurisdiction_name", "jurisdiction_fips", "candidate", "district", "magnitude", "stage", "special", "writein", "date"]


class Stop(SystemExit):
    pass


def _say_default(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- the Commons' precinct tables

def _json_get(url):
    r = source().get(url, state="MN", accept="application/json", timeout=120)
    if r.refused or not r.ok:
        raise FetchError(f"{url.split('?')[0]}: {r.why or r.status}")
    j = json.loads(r.body)
    if isinstance(j, dict) and "error" in j:
        raise FetchError(f"{url.split('?')[0]}: {j['error']}")
    return j


def keep_field(f):
    f = f.lower()
    if f in PLACE or f in STATS or f == "vtd":            # 2012's table calls the precinct code "vtd"
        return True
    return any(f.startswith(p) for p in OFFICES) and not f.endswith("est")


def table(year, say=_say_default):
    """One general election's precinct table: {"rows": [...], "fields": [...], "sha256", "fetched", "service", "layer"}."""
    path = os.path.join(cache_dir("mn", "commons"), f"precinct_{year}.json")
    if os.path.exists(path):
        return load_json(path)
    service = SERVICES + ITEM_OF[year] + "/FeatureServer"
    layers = [l for l in _json_get(service + "?f=json").get("layers", []) if l["name"].strip() == f"General Election Results By Precinct {year}"]
    if len(layers) != 1:
        raise Stop(f"    {year}: {len(layers)} layers carry that year's name, not one")
    lid = layers[0]["id"]
    info = _json_get(f"{service}/{lid}?f=json")
    fields = [f["name"] for f in info.get("fields", []) if keep_field(f["name"])]
    oid = info.get("objectIdField") or "objectid"
    count = _json_get(f"{service}/{lid}/query?where={quote('1=1')}&returnCountOnly=true&f=json").get("count")
    rows, offset = [], 0
    while True:
        j = _json_get(f"{service}/{lid}/query?where={quote('1=1')}&outFields={','.join(fields)}&returnGeometry=false"
                      f"&orderByFields={oid}&resultOffset={offset}&resultRecordCount={PAGE}&f=json")
        feats = j.get("features", [])
        rows += [{("vtdid" if k.lower() == "vtd" else k.lower()): v for k, v in f["attributes"].items()} for f in feats]
        offset += len(feats)
        if not feats or not j.get("exceededTransferLimit"):
            break
    if count != len(rows):
        raise Stop(f"    {year}: the service counts {count} rows and gave {len(rows)}")
    rows.sort(key=lambda r: r["vtdid"])
    doc = {"service": service, "layer": lid, "layer_name": layers[0]["name"],
           "fields": [("vtdid" if f.lower() == "vtd" else f.lower()) for f in fields],
           "fetched": time.strftime("%Y-%m-%d"), "sha256": sha_bytes(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()),
           "rows": rows}
    save_json(path, doc)
    say(f"    {year} precinct table: {len(rows):,} rows, {len(fields)} columns")
    return doc


def definitions(year):
    """The Secretary's column definitions for one year (the kit's extract of the metadata; read only)."""
    doc = load_json(KIT_META[year])
    return {k.lower(): v for k, v in doc["definitions"].get(str(year), {}).items()}, doc


def _dist(v):
    v = ("" if v is None else str(v)).strip()
    return re.sub(r"^0+(?=\d)", "", v)


def contests(year, doc=None):
    """[{id, year, prefix, office, class, district, parties: {code: column}, total, by_precinct: {vtdid: {code: votes, total}}}]"""
    doc = doc or table(year)
    fields = doc["fields"]
    out = {}
    for prefix, (office, dcol, klass, _code) in OFFICES.items():
        tcol = prefix + "total" if prefix + "total" in fields else prefix + "tot"      # 2020's table writes "tot"
        cols = [f for f in fields if f.startswith(prefix) and f != tcol and f not in PLACE and f not in STATS]
        if not cols or tcol not in fields:
            continue
        parties = {f[len(prefix):]: f for f in cols}
        for r in doc["rows"]:
            tot = r.get(tcol) or 0
            vals = {p: (r.get(c) or 0) for p, c in parties.items()}
            if not tot and not any(vals.values()):
                continue
            d = _dist(r.get(dcol)) if dcol else "state"
            cid = f"{year}-{prefix}-{d}"
            c = out.setdefault(cid, {"id": cid, "year": year, "prefix": prefix, "office": office, "class": klass, "district": d,
                                     "parties": parties, "by_precinct": {}})
            c["by_precinct"][r["vtdid"]] = dict(vals, total=tot)
    return sorted(out.values(), key=lambda c: (c["prefix"], c["district"].zfill(4)))


def internal_checks(c):
    """Precincts whose candidate columns add up to more than the precinct's own total, and the votes the total holds
    for candidates the table gives no column of their own (a third candidate in some years)."""
    bad, unnamed, where = [], 0, 0
    for v, rec in c["by_precinct"].items():
        s = sum(n for p, n in rec.items() if p != "total")
        if s > rec["total"]:
            bad.append({"vtdid": v, "candidates": s, "total": rec["total"]})
        elif s < rec["total"]:
            unnamed += rec["total"] - s
            where += 1
    return {"over_total": bad, "votes_without_a_column": unnamed, "precincts_with_such_votes": where}


def sums(c):
    s = {"total": 0, "dfl": 0, "r": 0, "yes": 0, "no": 0}
    for rec in c["by_precinct"].values():
        s["total"] += rec["total"]
        for p in ("dfl", "r", "yes", "no"):
            s[p] += rec.get(p, 0)
    return s


# ---------------------------------------------------------------- official totals: the Clerk of the House

def clerk_pdf(year, say=_say_default):
    if year in CLERK_KIT and os.path.exists(CLERK_KIT[year]):
        return CLERK_KIT[year], "https://clerk.house.gov/member_info/electionInfo/{y}/statistics{y}.pdf".format(y=year)
    path = os.path.join(cache_dir("mn", "official"), f"clerk_statistics{year}.pdf")
    if os.path.exists(path):
        return path, load_json(path + ".json")["url"]
    last = None
    for pattern in CLERK_URLS:
        url = pattern.format(y=year)
        try:
            body = fetch(url, path, say=say)
            if body[:5] != b"%PDF-":
                os.remove(path)
                raise FetchError(f"{url}: not a PDF")
            save_json(path + ".json", {"url": url, "fetched": time.strftime("%Y-%m-%d")})
            return path, url
        except FetchError as e:
            last = e
    raise FetchError(f"Clerk statistics {year}: {last}")


def read_clerk(path):
    """The Minnesota page(s): [(section heading, district or None, [(label, votes)])]."""
    from ballot import pdftext
    lines = pdftext.lines(path)
    start = next((i for i, (_p, _y, t) in enumerate(lines) if t.strip() == "MINNESOTA"), None)
    if start is None:
        raise ValueError("no MINNESOTA heading")
    out, section, dist = [], None, None
    for _p, _y, t in lines[start + 1:]:
        t = t.strip()
        if not t:
            continue
        if t.startswith("FOR "):
            section, dist = t, None
            if not t.startswith("FOR UNITED STATES REPRESENTATIVE"):
                out.append([section, None, []])
            continue
        if section and section.startswith("FOR UNITED STATES SENATOR") and t.startswith("(For "):
            kind = "UNEXPIRED" if "unexpired" in t.lower() else "FULL"
            if out and out[-1][0] == section and not out[-1][2]:
                out[-1][0] = f"{section} ({kind})"
            else:
                out.append([f"{section} ({kind})", None, []])
            continue
        if t.isupper() and section and not t.startswith("FOR "):
            break                                    # the next state's heading
        m = re.match(r"^(?:(\d+)\.\s+)?(.*?)\s*\.{3,}\s*([\d,]+)$", t)
        if not m:
            if section and out and re.match(r"^\d+$", t):
                break                                # the summary page's figures
            continue
        if section is None:
            continue
        if m.group(1):
            dist = m.group(1)
            out.append([section, dist, []])
        elif section.startswith("FOR UNITED STATES REPRESENTATIVE") and dist is None:
            continue
        out[-1][2].append((m.group(2).strip(), int(m.group(3).replace(",", ""))))
    return out


def _party_of(label):
    party = label.rsplit(",", 1)[-1].strip() if "," in label else label.strip()
    p = party.lower()
    if p.startswith("democrat"):
        return "dfl"
    if p == "republican":
        return "r"
    return "other"


def clerk_totals(year, say=_say_default):
    """{contest id: {"total", "dfl", "r"}} for President, U.S. Senate (and the special) and U.S. House."""
    path, url = clerk_pdf(year, say)
    out = {}
    senate_seen = 0
    for section, dist, lines in read_clerk(path):
        if section.startswith("FOR PRESIDENTIAL ELECTORS"):
            cid = f"{year}-usprs-state"
        elif section.startswith("FOR UNITED STATES SENATOR"):
            special = "UNEXPIRED" in section.upper() or "SPECIAL" in section.upper()
            cid = f"{year}-{'ussse' if special else 'ussen'}-state"
            senate_seen += 1
        elif section.startswith("FOR UNITED STATES REPRESENTATIVE"):
            cid = f"{year}-usrep-{dist}"
        else:
            continue
        t = {"total": 0, "dfl": 0, "r": 0}
        for label, v in lines:
            t["total"] += v
            k = _party_of(label)
            if k in ("dfl", "r"):
                t[k] += v
        out[cid] = t
    return out, {"input": f"clerk-statistics-{year}", "source": f"{url} (file {os.path.relpath(path, HERE)})", "sha256": sha_file(path),
                 "as_of": DATES[year], "kind": "official",
                 "note": "Clerk of the U.S. House, Statistics of the Presidential and Congressional Election, Minnesota page"}


# ---------------------------------------------------------------- official totals: the archive's transcriptions

def archive_id(year, prefix, district, special=False):
    code = OFFICES[prefix][3]
    if code is None:
        return None
    if prefix == "mnleg":
        m = re.match(r"^(\d+)([A-Z])$", district)
        d = f"{int(m.group(1)):02d}{m.group(2)}"
    elif prefix in ("mnsen", "usrep"):
        d = f"{int(district):02d}"
    else:
        d = "600"
    return f"23{year}{'2' if special else '1'}0999{code}{d}"


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def archive_rows(eid, say=_say_default):
    """{"title", "date", "stage", "rows": [[party, votes]], "sha256", "url"} or {"missing": status}. Kept small."""
    path = os.path.join(cache_dir("mn", "official", "archive"), f"{eid}.json")
    if os.path.exists(path):
        return load_json(path)
    url = ARCHIVE.format(id=eid)
    r = source().get(url, state="MN", small=True, expect_html=True, timeout=60)
    if r.refused:
        raise Stop(f"    the archive refused a request ({r.why}); it is not asked again tonight")
    if r.status == 404:
        doc = {"url": url, "missing": 404}
        save_json(path, doc)
        return doc
    if not r.ok:
        raise FetchError(f"{url}: {r.status}")
    t = r.body.decode("utf-8", "replace")
    title = _text((re.search(r"(?is)<title>(.*?)</title>", t) or [None, ""])[1]).split("|")[0].strip()
    tb = next((x for x in re.findall(r"(?is)<table.*?</table>", t) if re.search(r"(?i)<th[^>]*>\s*Votes", x)), None)
    rows = []
    if tb:
        heads = [_text(h).lower() for h in re.findall(r"(?is)<th[^>]*>(.*?)</th>", tb)]
        ip, iv = heads.index("party"), heads.index("votes")
        for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", tb):
            tds = re.findall(r"(?is)<td[^>]*>(.*?)</td>", tr)
            if len(tds) > max(ip, iv) and re.sub(r"\D", "", _text(tds[iv])):
                rows.append([_text(tds[ip]), int(re.sub(r"\D", "", _text(tds[iv])))])     # party and votes only
    body = _text(t)
    dates = re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", body)
    stage = "general" if re.search(r"\bGeneral\b", body) else ("special" if re.search(r"\bSpecial\b", body) else "")
    cites = _text((re.search(r"(?is)<h3[^>]*>\s*Sources\s*</h3>\s*<ul>(.*?)</ul>", t) or [None, ""])[1])
    doc = {"url": url, "title": title, "date": dates[0] if dates else None, "stage": stage, "rows": rows, "sha256": sha_bytes(r.body),
           "cites": cites[:400], "fetched": time.strftime("%Y-%m-%d")}
    save_json(path, doc)
    return doc


def archive_totals(c, say=_say_default):
    """The archive's totals for one contest, or (None, reason)."""
    special = c["prefix"] == "ussse" or (c["prefix"] == "mnsen" and c["year"] in (2014, 2018, 2024))   # no regular Senate election then
    eid = archive_id(c["year"], c["prefix"], c["district"], special)
    if eid is None:
        return None, "no official total for this office is reachable without the Secretary of State's own site", None
    doc = archive_rows(eid, say)
    if doc.get("missing"):
        return None, f"the archive has no page {eid}", doc["url"]
    want_date = "/".join([DATES[c["year"]][5:7], DATES[c["year"]][8:10], DATES[c["year"]][:4]])
    if str(c["year"]) not in doc["title"] or (doc.get("date") and doc["date"] != want_date):
        return None, f"the archive's page {eid} is '{doc['title']}' of {doc.get('date')}, not this contest", doc["url"]
    t = {"total": 0, "dfl": 0, "r": 0}
    for party, v in doc["rows"]:
        t["total"] += v
        if party == "Democratic-Farmer-Labor":
            t["dfl"] += v
        elif party == "Republican":
            t["r"] += v
    return t, None, doc["url"]


# ---------------------------------------------------------------- the check

def check_contests(say=_say_default, archive=True):
    """Every contest 2012-2024 against its official total. Returns (results, inputs)."""
    results, inputs = [], []
    for year in YEARS:
        doc = table(year, say)
        inputs.append({"input": f"commons-precincts-{year}", "source": f"{doc['service']}/{doc['layer']} ({doc['layer_name']})",
                       "sha256": doc["sha256"], "as_of": DATES[year], "kind": "official",
                       "note": f"Secretary of State's certified precinct table, fetched {doc['fetched']}"})
        try:
            clerk, rec = clerk_totals(year, say)
            inputs.append(rec)
        except (FetchError, ValueError) as e:
            clerk = {}
            say(f"    Clerk statistics {year}: {e}")
        n_arch = 0
        for c in contests(year, doc):
            s = sums(c)
            res = {"id": c["id"], "office": c["office"], "district": c["district"], "precincts": len(c["by_precinct"]),
                   "precinct_sum": s, "internal": internal_checks(c)}
            if c["prefix"] in ("usprs", "ussen", "ussse", "usrep"):
                off = clerk.get(c["id"])
                res.update(source="Clerk of the U.S. House, Statistics of the Presidential and Congressional Election "
                                  f"{year}", source_kind="official")
                why = None if off else "not found on the Clerk's Minnesota page"
                if archive and (off is None or any(s[k] != off[k] for k in ("total", "dfl", "r"))):
                    # a second reading of the canvass: the archive's transcription of the State Canvassing Board's report
                    arch, why2, url = archive_totals(c, say)
                    res["clerk"] = off
                    res["archive"] = arch
                    if arch:
                        res["archive_url"] = url
                    if arch and not any(s[k] != arch[k] for k in ("total", "dfl", "r")):
                        off, why = arch, None
                        res.update(source="Minnesota Historical Election Archive, transcribing the State Canvassing Board's report "
                                          "(the Clerk's figures differ; both kept)", source_kind="academic transcription of the official report")
                    elif off is None:
                        off, why = arch, why2
            elif OFFICES[c["prefix"]][3] and archive:
                off, why, url = archive_totals(c, say)
                n_arch += 1
                res.update(source="Minnesota Historical Election Archive, transcribing the State Canvassing Board's report",
                           source_kind="academic transcription of the official report", url=url)
                if n_arch % 100 == 0:
                    say(f"      {year}: {n_arch} archive pages read")
            else:
                off, why = None, ("a ballot question: no official total is reachable without the Secretary of State's own site"
                                  if c["class"] == "question" else "not checked this run")
            if off:
                diff = {k: s[k] - off[k] for k in ("total", "dfl", "r")}
                res.update(official=off, diff=diff, holds=not any(diff.values()) and not res["internal"]["over_total"])
            else:
                res.update(official=None, holds=None, why=why)
            results.append(res)
        say(f"    {year}: {sum(1 for r in results if r['id'].startswith(str(year)))} contests")
    return results, inputs


# ---------------------------------------------------------------- MEDSL

def medsl_rows(year, say=_say_default):
    """MEDSL's Minnesota precinct rows for one year, allowlisted fields only (cached as JSON)."""
    if year not in MEDSL:
        return [], None
    url, name = MEDSL[year]
    raw_path = os.path.join(cache_dir("mn", "medsl"), name)
    body = fetch(url, raw_path, say=say)
    out_path = os.path.join(cache_dir("mn", "medsl"), f"medsl_{year}_mn.json")
    if os.path.exists(out_path):
        doc = load_json(out_path)
        if doc.get("sha256") == sha_bytes(body):
            return doc["rows"], doc
    if name.endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(body))
        member = next(n for n in z.namelist() if n.lower().endswith((".csv", ".tab", ".txt")) and "readme" not in n.lower())
        text = z.read(member).decode("utf-8", "replace")
    else:
        text = body.decode("utf-8", "replace")
    delim = "\t" if text.split("\n", 1)[0].count("\t") > text.split("\n", 1)[0].count(",") else ","
    rd = csv.DictReader(io.StringIO(text), delimiter=delim)
    keep = [k for k in MEDSL_KEEP if k in (rd.fieldnames or [])]
    rows = []
    for r in rd:
        rec = {k: r[k] for k in keep}
        try:
            rec["votes"] = int(float(rec.get("votes") or 0))
        except ValueError:
            rec["votes"] = 0
        rows.append(rec)
    doc = {"url": url, "file": name, "sha256": sha_bytes(body), "fields": keep, "rows": rows,
           "licence": "CC0 1.0 (MIT Election Data and Science Lab)", "kind": "secondary"}
    save_json(out_path, doc)
    say(f"    MEDSL {year}: {len(rows):,} rows, {len({r['office'] for r in rows})} offices")
    return rows, doc


def _pct_norm(s):
    s = (s or "").upper().replace("&", "AND")
    s = re.sub(r"\bTOWNSHIP\b", "TWP", s)
    s = re.sub(r"\bPRECINCT\b|\bPCT\b", "P", s)
    s = re.sub(r"\bWARD\b", "W", s)
    s = re.sub(r"\bSAINT\b|\bST\.?(?=\s)", "ST", s)
    s = re.sub(r"(\d+)", lambda m: str(int(m.group(1))), s)
    return re.sub(r"[^A-Z0-9]", "", s)


def medsl_by_vtdid(year, say=_say_default):
    """MEDSL's rows for one year with the precinct's VTDID of that year's table added ("vtdid", None when no single
    precinct fits), and how many precincts matched. 2024 gives the precinct code; 2018 and 2022 give the name, matched
    within the county by spelling (numbers without leading zeros; Township, Ward, Precinct shortened; a trailing "City"
    or "Twp" tried both ways); a name that fits two precincts is left unmatched."""
    rows, _doc = medsl_rows(year, say)
    t = table(year)["rows"]
    by_name, by_code = {}, {}
    for r in t:
        c = (r.get("countyfips") or "").strip()
        by_name.setdefault((c, _pct_norm(r.get("pctname"))), []).append(r["vtdid"])
        by_code[(c, (r.get("pctcode") or "").strip())] = r["vtdid"]
    memo, unmatched = {}, set()
    for r in rows:
        key = (r["county_fips"][-3:], r["precinct"].strip())
        if key not in memo:
            v = None
            if year >= 2024 and key[1].isdigit():
                v = by_code.get((key[0], key[1].zfill(4)))
            else:
                n = _pct_norm(key[1])
                for cand in (n, re.sub(r"CITY$", "", n), n + "TWP", re.sub(r"TWP$", "", n)):
                    hit = by_name.get((key[0], cand), [])
                    if len(hit) == 1:
                        v = hit[0]
                        break
            memo[key] = v
            if v is None:
                unmatched.add(key)
        r["vtdid"] = memo[key]
    return rows, {"precincts": len(memo), "matched": len(memo) - len(unmatched), "unmatched": sorted(unmatched)[:200]}


def medsl_check(results, say=_say_default):
    """A second look: MEDSL's sum for each legislative and statewide contest against the precinct table's (secondary)."""
    by_id = {r["id"]: r for r in results}
    names = {"STATE HOUSE": "mnleg", "STATE SENATE": "mnsen", "GOVERNOR": "mngov", "SECRETARY OF STATE": "mnsos",
             "ATTORNEY GENERAL": "mnag", "STATE AUDITOR": "mnaud"}
    out = {}
    for year in MEDSL:
        rows, _doc = medsl_rows(year, say)
        tot = {}
        for r in rows:
            prefix = names.get(r["office"].upper().strip())
            if not prefix or (r.get("stage") or "GEN").upper() not in ("GEN", ""):
                continue
            d = "state" if prefix in ("mngov", "mnsos", "mnag", "mnaud") else _dist(r.get("district"))
            d = re.sub(r"^0+(?=\d)", "", d)
            cid = f"{year}-{prefix}-{d}"
            tot[cid] = tot.get(cid, 0) + r["votes"]
        same = differ = 0
        diffs = []
        for cid, v in tot.items():
            r = by_id.get(cid)
            if not r:
                continue
            if r["precinct_sum"]["total"] == v:
                same += 1
            else:
                differ += 1
                diffs.append({"id": cid, "medsl": v, "precinct_table": r["precinct_sum"]["total"]})
        out[year] = {"contests_equal": same, "contests_differ": differ, "differences": diffs[:50]}
    return out


# ---------------------------------------------------------------- onto today's precinct lines

def _bare(name):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+(twp|unorg)\.?$", "", (name or "").strip().lower()))


TODAY_SHAPES = os.path.join(HERE, "states_cache", "mn_local", "sos_votingdistricts_geometry_4326.json.gz")


def _name_key(r):
    """A precinct's name for matching across years: county, then the name spelled one way (numbers without leading
    zeros; Township, Ward and Precinct shortened; a trailing City dropped, as the 2022 tables began writing it)."""
    return ((r.get("countyfips") or "").strip(), re.sub(r"CITY(?=(W\d|P\d|$))", "", _pct_norm(r.get("pctname"))))


def today_precincts():
    """Today's precincts with their names: [{vtdid, pctname, mcdfips, mcdname, countyfips, countyname}] (the kit's copy
    of "Voting Districts, Minnesota", attributes only)."""
    import gzip
    with gzip.open(TODAY_SHAPES, "rt", encoding="utf-8") as fh:
        doc = json.load(fh)
    keep = ("vtdid", "pctname", "mcdfips", "mcdname", "countyfips", "countyname")
    return [{k: a.get(k) for k in keep} for a, _rings in doc["rows"]]


def _unique(rows, key):
    seen = {}
    for r in rows:
        seen.setdefault(key(r), []).append(r["vtdid"])
    return {k: v[0] for k, v in seen.items() if len(v) == 1}


def on_today_lines(year, pop2020, doc=None, columns=None, vtd=None, t2020=None, today=None):
    """{today's VTDID: {column: value}} for one year's numeric columns, the way each precinct got its figures, and a
    report. Precinct codes are reused for other ground (a city renumbers its precincts; Washington County's codes moved
    between places), so a code alone is never trusted. In order:
      1. 2020 and earlier, through 2020 geography: a precinct of that year that is the 2020 precinct of the same county
         and name (2020 itself: every precinct) is shared among today's precincts by the 2020 people of the Census
         voting district with that 2020 code (the Bureau's 2020 voting districts are the state's 2020 precincts),
         by its blocks when nobody lived there.
      2. The precinct of today with the same county and name, if just one has it.
      3. The same code, when the city or township is the same and today has no other precinct of that name.
      4. Today's precincts of the same city or township left without figures, by 2020 population.
      5. Otherwise the votes have nowhere to go: counted and listed.
    pop2020: {today's VTDID: 2020 people}; vtd: census.vtd2020(); t2020: the 2020 table's rows; today: today_precincts()."""
    doc = doc or table(year)
    today = today or today_precincts()
    tids = {r["vtdid"] for r in today}
    tby = {r["vtdid"]: r for r in today}
    cols = columns or [f for f in doc["fields"] if f not in PLACE and f not in ("mailballot", "tabmodel", "tabsystem")]
    old = {r["vtdid"]: r for r in doc["rows"]}
    out, how = {}, {}
    placed = {}

    def give(n, v, share, why):
        acc = out.setdefault(n, {c: 0 for c in cols})
        for c in cols:
            acc[c] += share * (old[v].get(c) or 0)
        how.setdefault(n, set()).add(why)
        placed[v] = why

    # 1. through 2020 geography
    if vtd and year <= 2020:
        if year == 2020:
            equiv = {v: v for v in old}
        else:
            k2020 = _unique(t2020 or table(2020)["rows"], _name_key)
            kyear = _unique(doc["rows"], _name_key)
            equiv = {v: k2020[k] for k, v in kyear.items() if k in k2020}
        for v, e in equiv.items():
            parts = vtd.get(e) or {}
            tw = sum(p for p, _b in parts.values())
            tb = sum(b for _p, b in parts.values())
            if not tb:
                continue
            for n, (p, b) in parts.items():
                share = (p / tw) if tw else (b / tb)
                if share:
                    give(n, v, share, "2020 geography" if year == 2020 else "2020 geography, by name")
        # 1b. a precinct whose name 2020 does not have, but whose code 2020 has in the same city or township
        if year < 2020:
            r2020 = {r["vtdid"]: r for r in (t2020 or table(2020)["rows"])}
            for v, r in old.items():
                e = r2020.get(v)
                if v in placed or not e or (e.get("mcdfips") or "").strip() != (r.get("mcdfips") or "").strip():
                    continue
                parts = vtd.get(v) or {}
                tw = sum(p for p, _b in parts.values())
                tb = sum(b for _p, b in parts.values())
                for n, (p, b) in parts.items():
                    share = (p / tw) if tw else ((b / tb) if tb else 0)
                    if share:
                        give(n, v, share, "2020 geography, by code in the same city or township")
    # 2. same county and name
    ktoday = _unique(today, _name_key)
    for v, r in old.items():
        if v in placed:
            continue
        n = ktoday.get(_name_key(r))
        if n and n not in out:
            give(n, v, 1.0, "same name")
    # 3. same code, same city or township
    names_today = {}
    for r in today:
        names_today.setdefault(_name_key(r), 0)
        names_today[_name_key(r)] += 1
    for v, r in old.items():
        if v in placed or v not in tids or v in out:
            continue
        t = tby[v]
        if (t.get("mcdfips") or "").strip() == (r.get("mcdfips") or "").strip():
            give(v, v, 1.0, "same code in the same city or township")
    # 4. same city or township, by 2020 population
    groups = {}
    for r in today:
        if r["vtdid"] not in out:
            groups.setdefault(((r.get("countyfips") or "").strip(), (r.get("mcdfips") or "").strip()), []).append(r["vtdid"])
            groups.setdefault(((r.get("countyfips") or "").strip(), "name:" + _bare(r.get("mcdname"))), []).append(r["vtdid"])
    every = {}
    for r in today:
        every.setdefault(((r.get("countyfips") or "").strip(), (r.get("mcdfips") or "").strip()), []).append(r["vtdid"])
        every.setdefault(((r.get("countyfips") or "").strip(), "name:" + _bare(r.get("mcdname"))), []).append(r["vtdid"])
    lost = {c: 0 for c in cols}
    lost_precincts = []
    for v, r in old.items():
        if v in placed:
            continue
        k1 = ((r.get("countyfips") or "").strip(), (r.get("mcdfips") or "").strip())
        k2 = ((r.get("countyfips") or "").strip(), "name:" + _bare(r.get("mcdname")))
        new = groups.get(k1) or groups.get(k2) or []
        why = "same city or township, by 2020 population"
        if not new:
            new = every.get(k1) or every.get(k2) or []        # 4b. the whole city or township, by 2020 population
            why = "added across its city or township, by 2020 population"
        if not new:
            for c in cols:
                lost[c] += old[v].get(c) or 0
            lost_precincts.append({"vtdid": v, "precinct": r.get("pctname"), "county": r.get("countyname"), "ballots": r.get("totvoting")})
            continue
        tw = sum(pop2020.get(n, 0) for n in new)
        for n in new:
            give(n, v, (pop2020.get(n, 0) / tw) if tw else 1 / len(new), why)
    how = {n: "; ".join(sorted(w)) for n, w in how.items()}
    total = sum((r.get("totvoting") or 0) for r in old.values())
    carried = sum(x.get("totvoting", 0) for x in out.values())
    kinds = {}
    for w in placed.values():
        kinds[w] = kinds.get(w, 0) + 1
    report = {"method": LINES_METHOD, "precincts_then": len(old), "placed_by": kinds, "today_with_figures": len(out),
              "today_without_figures": sorted(tids - set(out)), "gone_unplaced": lost_precincts,
              "control": {"ballots_in_table": total, "carried": round(carried, 3), "unplaced": lost.get("totvoting", 0),
                          "holds": abs(total - carried - lost.get("totvoting", 0)) < 0.01}}
    return out, how, report


# ---------------------------------------------------------------- self-test

def selftest(say=_say_default):
    ok = True

    def check(what, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        say(f"    {'ok ' if good else 'BAD'} {what}: {got!r}" + ("" if good else f" (expected {want!r})"))
    doc = {"fields": ["vtdid", "mnlegdist", "mnlegr", "mnlegdfl", "mnlegwi", "mnlegtotal", "usprsr", "usprsdfl", "usprstotal"],
           "rows": [{"vtdid": "270010005", "mnlegdist": "10A", "mnlegr": 5, "mnlegdfl": 3, "mnlegwi": 1, "mnlegtotal": 9,
                     "usprsr": 6, "usprsdfl": 4, "usprstotal": 10},
                    {"vtdid": "270010010", "mnlegdist": "10A", "mnlegr": 2, "mnlegdfl": 2, "mnlegwi": 0, "mnlegtotal": 5,
                     "usprsr": 1, "usprsdfl": 1, "usprstotal": 3}]}
    cs = contests(2024, doc)
    check("two contests found", [c["id"] for c in cs], ["2024-mnleg-10A", "2024-usprs-state"])
    check("a district contest's sum", sums(cs[0])["total"], 14)
    check("votes the total holds for a candidate with no column are counted", internal_checks(cs[1])["votes_without_a_column"], 1)
    doc["rows"][0]["mnlegr"] = 9
    check("columns adding to more than the total are caught", [b["vtdid"] for b in internal_checks(contests(2024, doc)[0])["over_total"]],
          ["270010005"])
    check("2018's two Senate races on the Clerk's page", _party_of("Tina Smith, Democrat"), "dfl")
    today = [{"vtdid": "270010001", "pctname": "Exton P-1", "mcdfips": "11111", "mcdname": "Exton", "countyfips": "001"},
             {"vtdid": "270010002", "pctname": "Exton P-2", "mcdfips": "11111", "mcdname": "Exton", "countyfips": "001"}]
    then = {"fields": ["vtdid", "pctname", "mcdfips", "mcdname", "countyfips", "totvoting"],
            "rows": [{"vtdid": "270010001", "pctname": "EXTON P-02", "mcdfips": "11111", "mcdname": "Exton", "countyfips": "001", "totvoting": 70},
                     {"vtdid": "270010009", "pctname": "Exton P-9", "mcdfips": "11111", "mcdname": "Exton", "countyfips": "001", "totvoting": 30}]}
    out, how, rep = on_today_lines(2022, {"270010001": 100, "270010002": 300}, then, today=today)
    check("a reused code follows the name, not the number", round(out["270010002"]["totvoting"]), 70)
    check("a gone precinct goes to its city's precinct left without figures", round(out["270010001"]["totvoting"], 1), 30.0)
    check("every ballot is placed or counted as unplaced", rep["control"]["holds"], True)
    check("archive id for House 1A, 2012", archive_id(2012, "mnleg", "1A"), "232012109997101A")
    check("archive id for Governor, 2022", archive_id(2022, "mngov", "state"), "2320221099920600")
    check("archive id for Senate 45 special, 2024", archive_id(2024, "mnsen", "45", True), "232024209997045")
    check("Clerk party of 'Angie Craig, Democrat'", _party_of("Angie Craig, Democrat"), "dfl")
    check("Clerk party of 'Democratic' (electors)", _party_of("Democratic"), "dfl")
    check("Clerk party of 'Write-in'", _party_of("Write-in"), "other")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-archive", action="store_true", help="skip the archive's pages (federal contests only)")
    a = ap.parse_args(argv)
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    results, _inputs = check_contests(archive=not a.no_archive)
    held = sum(1 for r in results if r["holds"])
    failed = [r for r in results if r["holds"] is False]
    unchecked = [r for r in results if r["holds"] is None]
    print(f"    contests {len(results)}: equal {held}, differ {len(failed)}, no official total {len(unchecked)}")
    for r in failed[:40]:
        print(f"      differs: {r['id']} {r['precinct_sum']} vs {r['official']} internal {len(r['internal'])}")


if __name__ == "__main__":
    main()
