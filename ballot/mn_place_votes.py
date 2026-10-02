"""
ballot/mn_place_votes.py - how each Minnesota place voted in past partisan general elections, added up from the
Secretary of State's official precinct results, so a page can show the record of a county, a city or township, or a
district without anyone labelling a candidate.

    python ballot/mn_place_votes.py               reads (or downloads) the tables, writes ballot/lean/mn_place_votes.json
    python ballot/mn_place_votes.py --refresh     asks for everything again even when the cached copies are fresh
    python ballot/mn_place_votes.py --out x.json  writes somewhere else; --cache DIR keeps the downloads somewhere else
    python ballot/mn_place_votes.py --selftest    the arithmetic on a made-up table; downloads nothing

What it is, and is not
----------------------
For President and U.S. Senator in 2024, Governor in 2022, and President and U.S. Senator in 2020: the votes for the
Democratic-Farmer-Labor ticket, the Republican ticket, everyone else together (write-ins included) and the total, for
every county, every city, township and unorganized territory, every state Senate and House district, every judicial
district, county commissioner district, city ward and hospital district. It is how the people of a place voted then, on
the precinct and district lines in force at that election. It is not a prediction, it says nothing about any candidate
on a later ballot or about any voter, and it turns no nonpartisan office into a partisan one. No database is opened for
writing; ballot_local_2026.sqlite is opened read-only at the end, only to count how many of our places are covered.

Some places have a handful of voters (in 2024 a dozen had fewer than ten votes for President, and in eleven every vote
went to one ticket). There the split comes close to saying how particular people voted. The counts stay in the file,
because they are the official record and the sums must be checkable, but each such contest is listed in the place's
"too_few" (fewer than FEW votes, or every vote the same way) so that a page can leave the split out.

Where the numbers come from
---------------------------
The Minnesota Geospatial Commons (gis.data.mn.gov) carries the Secretary of State's "Minnesota General Election
Results, 2022-2030" and "2012-2020": one table per general election, one row per precinct, with the precinct's county,
city or township (MCD FIPS code), legislative, judicial, county commissioner and hospital districts and ward, and the
votes of every candidate for President, U.S. Senator and the constitutional offices. The Secretary's metadata says the
results are those certified by the State Canvassing Board. The tables are read from the Commons' own feature services
(enterprise.gisdata.mn.gov), attributes only, one polite request at a time, and cached in states_cache/mn_local/. The
Secretary of State's own websites are never requested (they answer this machine with a CAPTCHA).

  - The layer for a year is found by its name ("General Election Results By Precinct 2024"), never by its number: the
    newest election is layer 0, so the numbers move when a new election is added.
  - Which columns are the DFL and the Republican ticket is read from the Secretary's own column definitions (the item's
    metadata, www.arcgis.com/sharing/rest/content/items/<item>/info/metadata/metadata.xml), which name each ticket
    ("US President Democratic-Farmer-Labor Party candidate (Harris/Walz) votes"). Those surnames, saying which election
    this was, are the only names kept. Of the metadata only the title, dates, the accuracy statement, the two notices
    and the definitions are cached, not the agency's contact block.
  - A legislative, commissioner or ward district is given only for 2022 and 2024: those lines were drawn again for the
    2022 election, after the census, so a number in the 2020 table need not be the same district (nearly every
    precinct's legislative district changed, and about one in eleven precincts' commissioner district). Between 2022
    and 2024 a dozen precincts changed commissioner district and three their House district; each year is given on its
    own lines. School districts are not given: a precinct can lie in more than one, and the table does not say which.
  - A place is filed under the MCD code of that year's table. Where today's precinct table (the Secretary's "Voting
    Districts, Minnesota") no longer has a code, and exactly one of today's places in the same county has the same name
    and was not in that year's table (a township that became a city: Baldwin, Empire, Credit River; a township that
    became unorganized territory: Lima), the votes are filed under today's code and the place says so. A code with no
    such namesake stays under its old code, marked "former" (Lent and Honner townships, which the 2024 table no longer
    has; an unorganized area of St. Louis County whose code today's table no longer has). Where today's table gives a
    code another name than the earlier tables did (five unorganized territories of St. Louis County), the place says
    what it was named then: the code is the same, and whether the ground is exactly the same the tables do not say.

The control
-----------
Nothing is written unless all of this holds: every precinct's candidates add up to the precinct's own total; every
kind of place that covers the whole state adds up to the statewide sum; and the statewide sum equals the official
statewide totals, which the file states with their source:
  - President and U.S. Senator, 2024 and 2020: the Clerk of the U.S. House of Representatives, "Statistics of the
    Presidential and Congressional Election" (clerk.house.gov; compiled from official sources), the Minnesota page,
    read from the PDF at each run with ballot/pdftext.py.
  - Governor, 2022: the State Canvassing Board's Canvassing Report of November 29, 2022. The report is on the
    Secretary's website, which this kit does not request, so its figures are read as the Minnesota Historical Election
    Archive transcribes them (University of Minnesota Libraries Publishing; an academic compilation, not an official
    record, which cites the report's pages 55-60). From that page only each row's party and vote count are kept: the
    candidates' names, the gender column and the biographical notes there are never stored.
The figures this loader was checked against on 2026-10-01 are typed below (CHECKED); they are used, and the file says
so, when a document cannot be read again.

Found on 2026-10-01, for whoever checks this against the Blue Book: the totals rows of the Minnesota Legislative
Manual's election chapters, as the Legislative Reference Library archives them
(lrl.mn.gov/archive/sessions/electionresults/), equal these sums for the DFL and Republican tickets for President and
U.S. Senator in 2020 and 2024, and so does every county row that could be read from them (all 87 counties for
President in both years; 84 and 86 of 87 for U.S. Senator). But the 2023-2024 Manual's Governor table reads, in the
PDF's text, 1,312,313 and 1,119,906 in its totals row (36 and 35 fewer than the canvassing report; seven counties on
its second page differ by one to twelve votes) and carries the 2020 presidential figures in the first columns of its
first page (all 47 counties there), and the 2025-2026 Manual's presidential totals row repeats 1,119,906 under the
Libertarian ticket. So the Manual is not the control. Also: gis.data.mn.gov's robots.txt asks for 60 seconds between
requests (this loader does not need that host: its search, /api/search/v1/collections/all/items?q=, was used once to
find the items); ballot/pdftext.py cannot read the Commons' metadata PDF, which is why the XML is used.
"""

import argparse
import collections
import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402

METHOD = "1.0"                 # change how anything is added up or matched, and this goes up
CACHE = os.path.join(HERE, "states_cache", "mn_local")
OUT = os.path.join(HERE, "ballot", "lean", "mn_place_votes.json")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
MAX_AGE_DAYS = 30
STATE_FIPS = "27"
PAGE = 2000                    # the services' own limit on rows per request
FEW = 20                       # a contest with fewer votes than this in a place is marked too_few (see TOO_FEW)

COMMONS = "https://gis.data.mn.gov/datasets/"
SERVICES = "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_sos/"
METADATA = "https://www.arcgis.com/sharing/rest/content/items/{item}/info/metadata/metadata.xml"
ITEMS = {
    "2022-2030": {"item": "446a973217ce46da9cc96bf43120fbba", "service": SERVICES + "bdry_electionresults_2022_2030/FeatureServer",
                  "title": "Minnesota General Election Results, 2022-2030"},
    "2012-2020": {"item": "40bde6cc6dfc4623b665e6cdb0bda21c", "service": SERVICES + "bdry_electionresults_2012_2020/FeatureServer",
                  "title": "Minnesota General Election Results, 2012-2020"},
}
TABLE_ITEM = {2024: "2022-2030", 2022: "2022-2030", 2020: "2012-2020"}
TODAY = {"item": "6c2c813b33144d49ba993bd86b3a58ba", "service": SERVICES + "bdry_votingdistricts/FeatureServer", "title": "Voting Districts, Minnesota"}
AGENCY = "Office of the Minnesota Secretary of State, Elections Division; published on the Minnesota Geospatial Commons"

# what is read of each precinct besides the votes
PLACE_FIELDS = ["vtdid", "pctname", "mcdname", "mcdfips", "ctu_type", "countyname", "countyfips", "mnsendist", "mnlegdist", "ctycomdist",
                "juddist", "ward", "hospdist", "hospdist_n"]
TODAY_FIELDS = ["vtdid", "mcdname", "mcdfips", "ctu_type", "countyname", "countyfips"]

# The contests. "dfl" and "rep" are the tickets as the Secretary's column definitions name them; the definitions are
# read again at each run and must still name them, or the loader stops.
CONTESTS = [
    {"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President and Vice President of the United States",
     "prefix": "usprs", "dfl": "Harris/Walz", "rep": "Trump/Vance", "official": "clerk-statistics-2024", "section": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2024-us-senate", "year": 2024, "date": "2024-11-05", "office": "United States Senator",
     "prefix": "ussen", "dfl": "Klobuchar", "rep": "White", "official": "clerk-statistics-2024", "section": "FOR UNITED STATES SENATOR"},
    {"id": "2022-governor", "year": 2022, "date": "2022-11-08", "office": "Governor and Lieutenant Governor",
     "prefix": "mngov", "dfl": "Walz/Flanagan", "rep": "Jensen/Birk", "official": "umn-election-archive-governor-2022", "section": None},
    {"id": "2020-president", "year": 2020, "date": "2020-11-03", "office": "President and Vice President of the United States",
     "prefix": "usprs", "dfl": "Biden/Harris", "rep": "Trump/Pence", "official": "clerk-statistics-2020", "section": "FOR PRESIDENTIAL ELECTORS"},
    {"id": "2020-us-senate", "year": 2020, "date": "2020-11-03", "office": "United States Senator",
     "prefix": "ussen", "dfl": "Smith", "rep": "Lewis", "official": "clerk-statistics-2020", "section": "FOR UNITED STATES SENATOR"},
]

# The official statewide totals this loader was checked against on 2026-10-01, read from the documents named in
# OFFICIAL_DOCS. They stand in, and the file says so, only when a document cannot be read again.
CHECKED = {
    "2024-president": {"dfl": 1656979, "rep": 1519032, "other": 77909, "total": 3253920},
    "2024-us-senate": {"dfl": 1792441, "rep": 1291712, "other": 105170, "total": 3189323},
    "2022-governor": {"dfl": 1312349, "rep": 1119941, "other": 78371, "total": 2510661},
    "2020-president": {"dfl": 1717077, "rep": 1484065, "other": 76029, "total": 3277171},
    "2020-us-senate": {"dfl": 1566522, "rep": 1398145, "other": 249589, "total": 3214256},
}
OFFICIAL_DOCS = {
    "clerk-statistics-2024": {
        "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
        "title": "Statistics of the Presidential and Congressional Election from Official Sources for the Election of November 5, 2024",
        "url": "https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf", "file": "clerk_statistics2024.pdf"},
    "clerk-statistics-2020": {
        "kind": "official federal compilation", "agency": "Office of the Clerk, U.S. House of Representatives",
        "title": "Statistics of the Presidential and Congressional Election from Official Sources for the Election of November 3, 2020",
        "url": "https://clerk.house.gov/member_info/electionInfo/2020/statistics2020.pdf", "file": "clerk_statistics2020.pdf"},
    "umn-election-archive-governor-2022": {
        "kind": "academic compilation quoting the official canvassing report (not itself an official record)",
        "agency": "Minnesota Historical Election Archive, University of Minnesota Libraries Publishing",
        "title": "Governor, 2022 Election",
        "url": "https://mn.electionarchives.lib.umn.edu/election/2320221099920600", "file": "umn_election_archive_governor_2022.json",
        "document": "State of Minnesota Canvassing Report, State General Election of November 8, 2022, certified by the State Canvassing "
                    "Board on November 29, 2022",
        "why": "The canvassing report itself is on the Secretary of State's website, which this kit does not request (it answers with a "
               "CAPTCHA); the Archive gives the report's pages 55-60 and the write-in report as its source."},
}
MANUAL_NOTE = ("The Minnesota Legislative Manual 2023-2024, as the Legislative Reference Library archives it "
               "(https://www.lrl.mn.gov/archive/sessions/electionresults/2022-11-08-g-man.pdf), reads 1,312,313 and 1,119,906 in the totals row "
               "of its Governor table, 36 and 35 fewer than the canvassing report, and the table's first page carries the 2020 presidential "
               "figures in its first columns (read from the PDF's text on 2026-10-01). The Secretary's precinct table equals the canvassing "
               "report, so the Manual is not the control.")

# The kinds of place: (kind, first election year given, covers the whole state, what it is, what its key is)
KINDS = [
    ("county", 2020, True, "Counties", "five-digit county FIPS code: 27 and the three digits our Minnesota county ids use"),
    ("mcd", 2020, True, "Cities, townships and unorganized territories", "five-digit MCD FIPS code, as sl_places kind mcd"),
    ("senate", 2022, True, "State Senate districts of the 2022 plan", "district number, as sl_places kind senate"),
    ("house", 2022, True, "State House districts of the 2022 plan", "district number and letter, as sl_places kind house"),
    ("judicial", 2020, True, "Judicial districts", "JD and the district number, as sl_places kind judicial"),
    ("commissioner", 2022, True, "County commissioner districts", "five-digit county FIPS code, a hyphen, the district number"),
    ("ward", 2022, False, "City wards", "the city's MCD FIPS code, a hyphen, the ward as the table writes it without W- and leading zeros"),
    ("hospital", 2020, False, "Hospital districts", "HD and the Secretary's district code in five digits, as sl_places kind hospital"),
]
KIND_NAMES = [k[0] for k in KINDS]
REDRAWN = ("These lines were drawn again for the 2022 election, after the census, so a number in the 2020 table need not be the same district, "
           "and 2020 is not given.")
TYPES = {"city": "city", "township": "township", "town": "township", "unorganized territory": "unorganized territory",
         "unorganized": "unorganized territory"}

WHAT = ("How each Minnesota place voted in five contests of the 2020, 2022 and 2024 general elections: the votes for the "
        "Democratic-Farmer-Labor ticket, the Republican ticket, everyone else together (write-ins included) and the total, added up from the "
        "Minnesota Secretary of State's official precinct results.")
NOTE = ("What this is: how the people of a place voted in that election, in the Secretary of State's precinct results as the State "
        "Canvassing Board certified them, added up here by county, by city or township and by district, on the precinct and district lines "
        "in force at that election. What this is not: it is not a prediction of any election; it says nothing about any candidate on a "
        "later ballot or about any voter; a nonpartisan office stays nonpartisan; and a place is not its lines for ever: where land was "
        "annexed, a township became a city or a district was redrawn, the figures are for the lines of that year. The tickets are named, as "
        "the Secretary's own column definitions name them, only to say which election this was. In a place with very few voters the split "
        "would come close to saying how particular people voted; those contests are listed in the place's too_few, and a page should leave "
        "the split out.")
HOW_TO_READ = ("Each place's votes are four counts for each contest: dfl (the Democratic-Farmer-Labor ticket), rep (the Republican ticket), other "
               "(every other candidate and all write-ins) and total. A contest a place does not have was not held on its lines, or the place "
               "is newer than that election.")
TOO_FEW = (f"A place's too_few lists the contests in which it had fewer than {FEW} votes, or in which every vote went the same way. There the "
           "split comes close to saying how particular people voted, so a page should leave it out. The counts are the official record all the "
           "same, and are kept here so that the sums can be checked.")


class Stop(SystemExit):
    pass


# ---------------------------------------------------------------- small things

def _now():
    return dt.date.today().isoformat()


def _day(path):
    return dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _sha_file(path):
    with open(path, "rb") as fh:
        return _sha(fh.read())


def _fresh(path, refresh, days=MAX_AGE_DAYS):
    return (not refresh) and os.path.exists(path) and os.path.getsize(path) > 0 and (time.time() - os.path.getmtime(path)) < days * 86400


def _save(path, doc):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    os.replace(tmp, path)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(node):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", node or ""))).strip()


def rows_fingerprint(rows):
    """A SHA-256 of the rows as fetched, written one fixed way, so the same table always gives the same fingerprint."""
    return _sha(json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def place_base(name):
    """'Baldwin Twp' / 'Lima Unorg' / 'Baldwin' -> 'Baldwin' / 'Lima' / 'Baldwin': the name without the kind of place."""
    return re.sub(r"\s+(Twp|Unorg)\.?$", "", (name or "").strip(), flags=re.I)


def bare(name):
    """A name for comparing only: lower case, letters and digits, St. as Saint."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\bst\.?\s", "saint ", place_base(name).lower()))


def display(names, kind):
    return f"{' / '.join(sorted({place_base(n) for n in names if n}))} {kind}".strip()


def ward_label(w):
    return re.sub(r"^W-0*(?=.)", "", (w or "").strip(), flags=re.I)


# ---------------------------------------------------------------- the Commons' feature services

def _json(url):
    j = json.loads(net.get(url, accept="application/json"))
    if isinstance(j, dict) and "error" in j:
        raise OSError(f"{url.split('?')[0]}: {j['error']}")
    return j


def fetch_layer(service, pick, want, path, refresh, say, what):
    """Every row of one layer of a feature service, attributes only: the layer `pick` chooses from the service's own
    list, the fields `want` chooses from the layer's own list, page by page, one request at a time, cached as JSON.
    The row count is asked for separately and must agree. If the service cannot be reached and an older copy is on
    disk, the older copy is used and the caller is told."""
    if _fresh(path, refresh):
        return _load(path)
    try:
        layers = pick(_json(service + "?f=json").get("layers", []))
        if len(layers) != 1:
            raise OSError(f"{len(layers)} layers fit {what}, not one")
        lid, lname = layers[0]["id"], layers[0]["name"]
        time.sleep(1.0)
        info = _json(f"{service}/{lid}?f=json")
        fields = want([f["name"] for f in info.get("fields", [])])
        oid = info.get("objectIdField") or "objectid"
        time.sleep(1.0)
        count = _json(f"{service}/{lid}/query?where={quote('1=1')}&returnCountOnly=true&f=json").get("count")
        rows, offset = [], 0
        while True:
            time.sleep(1.0)
            j = _json(f"{service}/{lid}/query?where={quote('1=1')}&outFields={','.join(fields)}&returnGeometry=false"
                      f"&orderByFields={oid}&resultOffset={offset}&resultRecordCount={PAGE}&f=json")
            feats = j.get("features", [])
            rows += [f["attributes"] for f in feats]
            offset += len(feats)
            if not feats or not j.get("exceededTransferLimit"):
                break
        if count != len(rows):
            raise OSError(f"the service counts {count} rows and gave {len(rows)}")
        doc = {"service": service, "layer": lid, "layer_name": lname, "fields": fields, "fetched": _now(), "rows": rows}
        _save(path, doc)
        say(f"      {what}: {len(rows):,} rows fetched")
        return doc
    except (OSError, ValueError, KeyError) as e:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      {what}: could not be fetched ({e}); using the copy of {_day(path)}")
            return _load(path)
        raise Stop(f"    {what}: could not be fetched ({e}) and no copy is on disk. Wait a few minutes and run this again.")


def results_table(year, prefixes, cache, refresh, say):
    def pick(layers):
        return [l for l in layers if "results by precinct" in l["name"].lower() and l["name"].strip().endswith(str(year))]

    def want(have):
        missing = [f for f in PLACE_FIELDS if f not in have]
        votes = [f for f in have if any(f.startswith(p) for p in prefixes)]
        for p in prefixes:
            for need in (p + "dfl", p + "r", p + "total"):
                if need not in votes:
                    missing.append(need)
        if missing:
            raise OSError(f"the {year} table has no column {', '.join(missing)}")
        return PLACE_FIELDS + votes
    return fetch_layer(ITEMS[TABLE_ITEM[year]]["service"], pick, want, os.path.join(cache, f"sos_electionresults_{year}.json"), refresh, say,
                       f"{year} precinct results")


def today_table(cache, refresh, say):
    def want(have):
        missing = [f for f in TODAY_FIELDS if f not in have]
        if missing:
            raise OSError(f"today's precinct table has no column {', '.join(missing)}")
        return TODAY_FIELDS
    return fetch_layer(TODAY["service"], lambda layers: [l for l in layers if l["id"] == 0], want,
                       os.path.join(cache, "sos_votingdistricts_today.json"), refresh, say, "today's precinct table")


def read_metadata(key, cache, refresh, say):
    """What the Secretary's metadata says of one item: title, dates, the accuracy statement, the two notices, and each
    year's column definitions. Kept as a small extract; the agency's contact block is not kept. None if it cannot be
    read and no extract is on disk (the loader then goes by the tickets typed in CONTESTS, and the file says so)."""
    path = os.path.join(cache, f"sos_electionresults_{key.replace('-', '_')}_metadata.json")
    if _fresh(path, refresh):
        return _load(path)
    url = METADATA.format(item=ITEMS[key]["item"])
    try:
        raw = net.get(url)
        root = ET.fromstring(raw)
        find = lambda p: _text(root.findtext(p) or "")                                              # noqa: E731
        definitions = {}
        for d in root.iter("detailed"):
            m = re.search(r"(\d{4})$", (d.findtext("enttyp/enttypl") or "").strip())
            if m:
                definitions[m.group(1)] = {(a.findtext("attrlabl") or "").strip().upper(): _text(a.findtext("attrdef") or "") for a in d.iter("attr")}
        if not definitions:
            raise ValueError("no column definitions in it")
        doc = {"url": url, "fetched": _now(), "sha256": _sha(raw), "title": find("dataIdInfo/idCitation/resTitle"),
               "published": find("dataIdInfo/idCitation/date/pubDate"), "canvassed": _text(next((e.text for e in root.iter("tmPosition")), "")),
               "accuracy": next((_text(e.text) for e in root.iter("measDesc") if "certified" in (e.text or "").lower()), ""),
               "use": find("dataIdInfo/resConst/Consts/useLimit"), "disclaimer": find("dataIdInfo/resConst/LegConsts/useLimit"),
               "definitions": definitions}
        _save(path, doc)
        return doc
    except Exception as e:  # noqa: BLE001  a missing or changed metadata record must not stop the count; it is said instead
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      metadata of {ITEMS[key]['title']}: could not be read ({e}); using the extract of {_day(path)}")
            return _load(path)
        say(f"      metadata of {ITEMS[key]['title']}: could not be read ({e}); the tickets are taken as typed in this loader")
        return None


# ---------------------------------------------------------------- the official statewide totals

def split_official(lines, is_dfl, is_rep, what):
    dfl = [v for label, v in lines if is_dfl(label)]
    rep = [v for label, v in lines if is_rep(label)]
    if len(dfl) != 1 or len(rep) != 1:
        raise ValueError(f"{what}: {len(dfl)} DFL and {len(rep)} Republican lines, not one of each")
    total = sum(v for _label, v in lines)
    return {"dfl": dfl[0], "rep": rep[0], "other": total - dfl[0] - rep[0], "total": total}


def read_clerk(path):
    """The Minnesota page of the Clerk of the House's election statistics: {section heading: [(label, votes)]} for the
    presidential electors (by party) and United States Senator (candidate, party), and the page number printed on it."""
    from ballot import pdftext
    lines = pdftext.lines(path)
    start = next((i for i, (_p, _y, t) in enumerate(lines) if t.strip() == "MINNESOTA"), None)
    if start is None:
        raise ValueError("no MINNESOTA heading")
    page = lines[start][0]
    top = next(t.strip() for p, _y, t in lines if p == page)
    sections, section = {}, None
    for _p, _y, t in lines[start + 1:]:
        t = t.strip()
        if t.startswith("FOR UNITED STATES REPRESENTATIVE") or (t.isupper() and not t.startswith("FOR ") and section):
            break
        if t.startswith("FOR "):
            section = t
            sections[section] = []
            continue
        m = re.match(r"^(.*?)\s*\.{3,}\s*([\d,]+)$", t)
        if section and m:
            sections[section].append((m.group(1).strip(), int(m.group(2).replace(",", ""))))
        elif section and t:
            raise ValueError(f"a line under {section} is not a name, dots and a number")
    return {"printed_page": int(top) if top.isdigit() else None, "pdf_page": page, "sections": sections}


def clerk_official(doc, section):
    lines = doc["sections"].get(section) or []
    if section == "FOR PRESIDENTIAL ELECTORS":           # one line a party
        return split_official(lines, lambda s: s.lower().startswith("democratic"), lambda s: s == "Republican", section)
    party = lambda s: s.rsplit(",", 1)[-1].strip()                                                  # noqa: E731  "Amy Klobuchar, Democrat"
    return split_official(lines, lambda s: party(s).lower().startswith("democrat"), lambda s: party(s) == "Republican", section)


def read_umn(src, cache, refresh, say):
    """The University of Minnesota archive's page for Governor, 2022: each row's party and votes, and the sentence
    naming the canvassing report. Only those are kept (as a small extract); names, the gender column and the page's
    biographical notes are not."""
    path = os.path.join(cache, src["file"])
    if _fresh(path, refresh, 3650):
        return _load(path)
    try:
        raw = net.get(src["url"])
        t = raw.decode("utf-8", "replace")
        table = next((tb for tb in re.findall(r"(?is)<table.*?</table>", t) if re.search(r"(?i)<th[^>]*>\s*Votes", tb)), None)
        if table is None:
            raise ValueError("no table of votes on the page")
        rows = []
        for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", table):
            tds = re.findall(r"(?is)<td[^>]*>(.*?)</td>", tr)                   # candidate, gender, running mate, party, votes, ...
            if len(tds) >= 5 and re.sub(r"\D", "", _text(tds[4])):
                rows.append([_text(tds[3]), int(re.sub(r"\D", "", _text(tds[4])))])   # the party and the votes, nothing else
            del tds, tr
        m = re.search(r"(?is)<h3[^>]*>\s*Sources\s*</h3>\s*<ul>\s*<li>(.*?)</li>", t)
        cites = _text(m.group(1)) if m else ""
        if not rows or "canvassing report" not in cites.lower():
            raise ValueError("the page no longer gives rows of votes and the canvassing report as its source")
        doc = {"url": src["url"], "fetched": _now(), "sha256": _sha(raw), "rows": rows, "cites": cites}
        del raw, t, table
        _save(path, doc)
        return doc
    except Exception as e:  # noqa: BLE001  an extract already on disk still stands
        if os.path.exists(path) and os.path.getsize(path) > 0:
            say(f"      {src['title']}: could not be read again ({e}); using the extract of {_day(path)}")
            return _load(path)
        raise


def official_totals(contests, cache, refresh, say):
    """{contest id: {dfl, rep, other, total, source, where, read}} and the documents' own records for the sources list."""
    docs, out = {}, {}
    for sid, src in OFFICIAL_DOCS.items():
        if not any(c["official"] == sid for c in contests):
            continue
        path = os.path.join(cache, src["file"])
        rec = {"id": sid, "kind": src["kind"], "agency": src["agency"], "title": src["title"], "url": src["url"]}
        try:
            if sid.startswith("clerk-"):
                net.download(src["url"], path, 0 if refresh else 3650, tries=3, say=say)
                parsed = read_clerk(path)
                rec.update(fetched=_day(path), sha256=_sha_file(path),
                           where=f"Minnesota, page {parsed['printed_page']}" if parsed["printed_page"] else f"Minnesota, page {parsed['pdf_page']} of the PDF")
                docs[sid] = (rec, lambda c, parsed=parsed: clerk_official(parsed, c["section"]))
            else:
                parsed = read_umn(src, cache, refresh, say)
                rec.update(fetched=parsed["fetched"], sha256=parsed["sha256"], document=src["document"], why=src["why"], cites=parsed["cites"],
                           where="the page's table of votes; only each row's party and votes are kept")
                docs[sid] = (rec, lambda c, parsed=parsed: split_official(parsed["rows"], lambda s: s == "Democratic-Farmer-Labor",
                                                                         lambda s: s == "Republican", "Governor, 2022"))
        except Exception as e:  # noqa: BLE001  the control then runs on the typed figures, and the file says so
            say(f"      {src['title']}: could not be read again ({e}); the control uses the figures typed in on 2026-10-01")
            rec.update(unread=f"could not be read on {_now()}: {e}")
            if "document" in src:
                rec.update(document=src["document"], why=src["why"])
            docs[sid] = (rec, None)
    for c in contests:
        rec, reader = docs[c["official"]]
        typed = CHECKED.get(c["id"])
        got, read = None, None
        if reader:
            try:
                got, read = reader(c), f"from the document on {rec.get('fetched')}"
            except Exception as e:  # noqa: BLE001
                say(f"      {rec['title']}: {e}; the control uses the figures typed in on 2026-10-01")
        if got is None:
            if typed is None:
                raise Stop(f"    {c['id']}: no official total could be read and none is typed in this loader")
            got, read = dict(typed), "typed into the loader from the document on 2026-10-01; the document could not be read again today"
        elif typed is not None and got != typed:
            say(f"      {c['id']}: the document now reads {got}; this loader was checked against {typed}")
        out[c["id"]] = dict(got, source=c["official"], where=rec.get("where", ""), read=read)
    return out, [rec for rec, _reader in docs.values()]


# ---------------------------------------------------------------- adding up

def contest_columns(c, fields):
    p = c["prefix"]
    cols = [f for f in fields if f.startswith(p)]
    return {"dfl": p + "dfl", "rep": p + "r", "total": p + "total", "others": [f for f in cols if f not in (p + "dfl", p + "r", p + "total")]}


def _int(v, what):
    if isinstance(v, bool) or v is None or (isinstance(v, float) and v != int(v)) or not isinstance(v, (int, float)) or v < 0:
        raise Stop(f"    {what} is {v!r}, not a count of votes; stopping")
    return int(v)


def mcd_codes(rows):
    """{MCD code: {names, type, counties}} as one table writes them."""
    out = {}
    for r in rows:
        code = (r["mcdfips"] or "").strip()
        e = out.setdefault(code, {"names": set(), "types": set(), "counties": set()})
        e["names"].add((r["mcdname"] or "").strip())
        e["types"].add(TYPES.get((r["ctu_type"] or "").strip().lower(), (r["ctu_type"] or "").strip().lower()))
        e["counties"].add(STATE_FIPS + r["countyfips"].strip())
    return out


def carry_map(then, today):
    """{code of an earlier table: today's code} for a code today's precinct table no longer has, when exactly one of
    today's places has the same name in the same county and was not in that table."""
    out = {}
    for code, e in then.items():
        if code in today or len({bare(n) for n in e["names"]}) != 1:
            continue
        name = bare(next(iter(e["names"])))
        fits = [z for z, t in today.items() if z not in then and len({bare(n) for n in t["names"]}) == 1 and bare(next(iter(t["names"]))) == name
                and t["counties"] & e["counties"]]
        if name and len(fits) == 1:
            out[code] = fits[0]
    return out


def mcd_name(e):
    return display(e["names"], " / ".join(sorted(e["types"])))


def tally(tables, today_rows, contests):
    """Everything the tables say, added up. Returns (places, statewide sums, per-kind sums, what was carried, the
    contests each kind is given for)."""
    today = mcd_codes(today_rows) if today_rows is not None else None
    votes = {k: collections.defaultdict(dict) for k in KIND_NAMES}      # kind -> key -> contest id -> [dfl, rep, other, total]
    names = {k: {} for k in KIND_NAMES}
    state, carried, then_of = {}, collections.defaultdict(dict), {}
    first = {k[0]: k[1] for k in KINDS}
    given = {k: [c["id"] for c in contests if c["year"] >= first[k]] for k in KIND_NAMES}
    for year in sorted(tables, reverse=True):                           # newest first, so a place takes its newest name
        rows = tables[year]["rows"]
        if len({r["vtdid"] for r in rows}) != len(rows):
            raise Stop(f"    {year} precinct results: a precinct id appears twice; stopping")
        then = mcd_codes(rows)
        then_of[year] = then
        if "" in then:
            raise Stop(f"    {year} precinct results: a precinct has no MCD code; stopping")
        moved = carry_map(then, today) if today is not None else {}
        mine = [c for c in contests if c["year"] == year]
        cols = {c["id"]: contest_columns(c, tables[year]["fields"]) for c in mine}
        for r in rows:
            county = STATE_FIPS + r["countyfips"].strip()
            cname = (r["countyname"] or "").strip()
            old = r["mcdfips"].strip()
            mcd = moved.get(old, old)
            keys = {"county": county, "mcd": mcd, "judicial": f"JD{int(r['juddist'])}"}
            names["county"].setdefault(county, f"{cname} County")
            names["judicial"].setdefault(keys["judicial"], f"{ordinal(int(r['juddist']))} Judicial District")
            if year >= first["senate"]:
                keys["senate"] = str(int(r["mnsendist"]))
                keys["house"] = re.sub(r"^0+", "", r["mnlegdist"].strip().upper())
                keys["commissioner"] = f"{county}-{int(r['ctycomdist'])}"
                names["senate"].setdefault(keys["senate"], f"Senate District {keys['senate']}")
                names["house"].setdefault(keys["house"], f"House District {keys['house']}")
                names["commissioner"].setdefault(keys["commissioner"], f"{cname} County, Commissioner District {int(r['ctycomdist'])}")
                if (r["ward"] or "").strip():
                    keys["ward"] = f"{mcd}-{ward_label(r['ward'])}"
                    names["ward"].setdefault(keys["ward"], f"{mcd_name((today or then).get(mcd) or then[old])}, Ward {ward_label(r['ward'])}")
            if (r["hospdist"] or "").strip():
                keys["hospital"] = f"HD{int(r['hospdist']):05d}"
                names["hospital"].setdefault(keys["hospital"], (r["hospdist_n"] or "").strip())
            for c in mine:
                k = cols[c["id"]]
                where = f"{year} precinct {r['vtdid']} ({(r['pctname'] or '').strip()}), {c['office']}"
                dfl, rep, total = (_int(r[k[x]], where) for x in ("dfl", "rep", "total"))
                others = sum(_int(r[f], where) for f in k["others"])
                if dfl + rep + others != total:
                    raise Stop(f"    {where}: the candidates add up to {dfl + rep + others:,} and the table's total is {total:,}; stopping")
                v = (dfl, rep, others, total)
                s = state.setdefault(c["id"], [0, 0, 0, 0])
                for i in range(4):
                    s[i] += v[i]
                for kind, key in keys.items():
                    cur = votes[kind][key].setdefault(c["id"], [0, 0, 0, 0])
                    for i in range(4):
                        cur[i] += v[i]
                if old != mcd:
                    e = carried[mcd].setdefault(old, {"name": mcd_name(then[old]), "contests": []})
                    if c["id"] not in e["contests"]:
                        e["contests"].append(c["id"])

    pack = lambda d: {cid: dict(zip(("dfl", "rep", "other", "total"), d[cid])) for cid in (c["id"] for c in contests) if cid in d}  # noqa: E731

    def few(rec):
        """Marks the contests in which the split would come close to saying how particular people voted."""
        hold = [cid for cid, v in rec["votes"].items() if v["total"] < FEW or max(v["dfl"], v["rep"], v["other"]) == v["total"]]
        if hold:
            rec["too_few"] = hold
        return rec
    places = {k: {} for k in KIND_NAMES}
    for kind in KIND_NAMES:
        if kind == "mcd":
            continue
        for key in sorted(votes[kind], key=sort_key):
            places[kind][key] = few({"name": names[kind][key], "votes": pack(votes[kind][key])})
    years = sorted(tables, reverse=True)
    tables_of = lambda ys: f"{', '.join(str(y) for y in sorted(ys))} table{'s' if len(set(ys)) > 1 else ''}"                # noqa: E731
    for code in sorted(set(votes["mcd"]) | set(today or {})):
        e = (today or {}).get(code) or next(then_of[y][code] for y in years if code in then_of[y])
        rec = few({"name": mcd_name(e), "type": " / ".join(sorted(e["types"])), "counties": sorted(e["counties"]),
                   "votes": pack(votes["mcd"].get(code, {}))})
        notes = []
        renamed = {str(y): mcd_name(then_of[y][code]) for y in sorted(tables) if today is not None and code in today and code in then_of[y]
                   and {bare(n) for n in then_of[y][code]["names"]} != {bare(n) for n in today[code]["names"]}}
        if renamed:
            rec["named_then"] = renamed
            notes.append(f"The {tables_of(renamed)} named this code's precincts {' and '.join(sorted(set(renamed.values())))}; today's table "
                         f"names it {rec['name']}. The code is the same; whether the ground is exactly the same the tables do not say.")
        if code in carried:
            rec["earlier"] = {old: {"name": x["name"], "contests": sorted(x["contests"])} for old, x in sorted(carried[code].items())}
            was = "; ".join(f"filed as {x['name']} ({old}) in the {tables_of({cid[:4] for cid in x['contests']})}" for old, x in sorted(carried[code].items()))
            notes.append(f"The same place under an earlier code: {was}. Today's precinct table has no such code and has this one place of that "
                         "name in the same county; the votes are the earlier place's, on its lines of that year.")
        elif today is not None and code not in today:
            rec["former"] = True
            notes.append("Today's precinct table has no place under this code and no one place of this name in the same county; the name and "
                         f"the lines are those of the {tables_of([y for y in tables if code in then_of[y]])}.")
        elif not rec["votes"]:
            notes.append(f"No precinct carried this code in these elections: the place, or its code, is newer than {max(tables)}.")
        if notes:
            rec["note"] = " ".join(notes)
        places["mcd"][code] = rec
    sums = {kind: {cid: [sum(p["votes"][cid][x] for p in places[kind].values() if cid in p["votes"]) for x in ("dfl", "rep", "other", "total")]
                   for cid in given[kind]} for kind in KIND_NAMES}
    return places, state, sums, carried, given


def sort_key(key):
    return [int(p) if p.isdigit() else p for p in re.findall(r"\d+|\D+", key)]


def control(state, sums, official, contests, tables):
    """The control: statewide sums against the official totals, and each kind of place that covers the state against
    the statewide sums. Returns (the record for the file, the lines that failed)."""
    failed, per = [], {}
    names = ("dfl", "rep", "other", "total")
    for c in contests:
        mine = dict(zip(names, state[c["id"]]))
        off = official[c["id"]]
        theirs = {n: off[n] for n in names}
        diff = {n: mine[n] - theirs[n] for n in names if mine[n] != theirs[n]}
        per[c["id"]] = {"sum_of_precincts": mine, "official": theirs, "equal": not diff, "source": off["source"], "where": off["where"],
                        "read": off["read"]}
        if diff:
            per[c["id"]]["difference"] = diff
            failed.append(f"{c['id']}: the precincts add up to {mine} and the official totals ({off['source']}) are {theirs}; "
                          f"precincts minus official: {diff}")
    kinds = {}
    for kind, _first, covers, _what, _key in KINDS:
        if not covers:
            continue
        bad = [cid for cid, s in sums[kind].items() if s != state[cid]]
        kinds[kind] = "equal" if not bad else f"differs for {', '.join(bad)}"
        failed += [f"{kind}: its places add up to {sums[kind][cid]} for {cid}, and the precincts to {state[cid]}" for cid in bad]
    counts = {str(y): len(t["rows"]) for y, t in sorted(tables.items())}
    return {"result": "equal" if not failed else "differs",
            "statement": ("For every contest the precinct rows add up to the official statewide totals named here; in every precinct the "
                          "candidates add up to the precinct's own total; and every kind of place that covers the whole state adds up to the "
                          "statewide sum." if not failed else "The sums do not all agree; see the differences."),
            "precincts": counts, "contests": per, "kinds": kinds, "notes": [MANUAL_NOTE] if any(c["id"] == "2022-governor" for c in contests) else []}, failed


def expectations(places, tables, contests):
    """Counts that must hold for Minnesota, each a reason to stop."""
    out = []
    if len(places["county"]) != 87:
        out.append(f"{len(places['county'])} counties, not 87")
    if len(places["judicial"]) != 10:
        out.append(f"{len(places['judicial'])} judicial districts, not 10")
    if any(c["year"] >= 2022 for c in contests) and (len(places["senate"]) != 67 or len(places["house"]) != 134):
        out.append(f"{len(places['senate'])} Senate and {len(places['house'])} House districts, not 67 and 134")
    for y, t in tables.items():
        if not 3500 <= len(t["rows"]) <= 5000:
            out.append(f"{len(t['rows'])} precincts in {y}, not about 4,100")
    return out


# ---------------------------------------------------------------- the file

def contest_records(contests, tables, meta, state, official, given):
    out, typed = [], []
    for c in contests:
        k = contest_columns(c, tables[c["year"]]["fields"])
        defs = ((meta.get(TABLE_ITEM.get(c["year"])) or {}).get("definitions") or {}).get(str(c["year"])) or {}
        rec = {"id": c["id"], "date": c["date"], "office": c["office"], "table": f"mn-sos-results-{TABLE_ITEM.get(c['year'], c['year'])}",
               "kinds": [kind for kind in KIND_NAMES if c["id"] in given[kind]]}
        for side, party in (("dfl", "Democratic-Farmer-Labor"), ("rep", "Republican")):
            d = defs.get(k[side].upper(), "")
            if d and f"({c[side]})" not in d:
                raise Stop(f"    {c['id']}: the Secretary's metadata defines {k[side].upper()} as '{d}', not the {party} ticket ({c[side]}) "
                           "this loader was checked against; stopping")
            rec[side] = {"party": party, "ticket": c[side], "column": k[side].upper(), "definition": d or None}
            if not d:
                typed.append(c["id"])
        rec["other"] = {"what": "every other candidate and all write-ins, together",
                        "columns": [{"column": f.upper(), "definition": defs.get(f.upper()) or None} for f in k["others"]]}
        rec["total"] = {"column": k["total"].upper(), "definition": defs.get(k["total"].upper()) or None}
        rec["statewide"] = dict(zip(("dfl", "rep", "other", "total"), state[c["id"]]))
        rec["official_source"] = official[c["id"]]["source"]
        out.append(rec)
    return out, sorted(set(typed))


def source_records(tables, today, meta, official_docs):
    out = []
    for key, item in ITEMS.items():
        years = sorted(y for y in tables if TABLE_ITEM.get(y) == key)
        if not years:
            continue
        m = meta.get(key) or {}
        out.append({"id": f"mn-sos-results-{key}", "kind": "official results by precinct", "agency": AGENCY, "title": item["title"],
                    "url": COMMONS + item["item"], "service": item["service"], "published": m.get("published") or None,
                    "canvassed": m.get("canvassed") or None, "accuracy": m.get("accuracy") or None,
                    "tables": {str(y): {"layer": tables[y].get("layer_name"), "precincts": len(tables[y]["rows"]), "fetched": tables[y].get("fetched"),
                                        "rows_sha256": rows_fingerprint(tables[y]["rows"])} for y in years},
                    "metadata": {"url": m.get("url"), "fetched": m.get("fetched"), "sha256": m.get("sha256")} if m else None,
                    "use": m.get("use") or None, "disclaimer": m.get("disclaimer") or None,
                    "read": "Of each precinct: its id and name, county, city or township and MCD FIPS code, legislative, judicial, county "
                            "commissioner and hospital districts, ward, and the votes of every candidate in the contests named here."})
    if today is not None:
        out.append({"id": "mn-sos-voting-districts-today", "kind": "official precinct table (attributes)", "agency": AGENCY, "title": TODAY["title"],
                    "url": COMMONS + TODAY["item"], "service": TODAY["service"], "tables": {"today": {
                        "layer": today.get("layer_name"), "precincts": len(today["rows"]), "fetched": today.get("fetched"),
                        "rows_sha256": rows_fingerprint(today["rows"])}},
                    "read": "Of each precinct: its id, county, city or township and MCD FIPS code. Used only to say which places exist today, "
                            "and so which earlier code is the same place under a new one."})
    return out + official_docs


def build(tables, today, meta, official, official_docs, contests=CONTESTS):
    places, state, sums, carried, given = tally(tables, today["rows"] if today else None, contests)
    ctl, failed = control(state, sums, official, contests, tables)
    failed += expectations(places, tables, contests) if contests is CONTESTS else []
    records, typed = contest_records(contests, tables, meta, state, official, given)
    kinds = {}
    for kind, first, covers, what, key in KINDS:
        kinds[kind] = {"what": what, "key": key, "places": len(places[kind]), "contests": given[kind], "covers_the_state": covers,
                       "places_with_a_contest_too_few": sum(1 for p in places[kind].values() if p.get("too_few"))}
        if first > min(c["year"] for c in contests):
            kinds[kind]["why_not_2020"] = REDRAWN
    kinds["commissioner"]["note"] = "Numbered within each county as the Secretary's table numbers them in that year."
    kinds["ward"]["note"] = ("As the Secretary's table writes a precinct's ward (W-01, W-E). A city that names its council seats another way "
                             "(a district, a section, a precinct, two wards together) is not matched here.")
    newest = [c["id"] for c in contests if c["year"] == max(tables)]
    ended = sum(1 for p in places["hospital"].values() if not any(cid in p["votes"] for cid in newest))
    kinds["hospital"]["note"] = ("The precincts the Secretary's table puts in the district in that year"
                                 + (f"; {ended} of these districts {'is' if ended == 1 else 'are'} not in the {max(tables)} table." if ended else "."))
    former = {code: p["name"] for code, p in places["mcd"].items() if p.get("former")}
    doc = {"what": WHAT, "note": NOTE, "state": "MN", "generated": _now(), "method_version": METHOD, "how_to_read": HOW_TO_READ,
           "too_few": {"fewer_than": FEW, "why": TOO_FEW},
           "contests": records, "kinds": kinds, "control": ctl,
           "coverage": {"carried_to_todays_code": {new: {old: x["name"] for old, x in sorted(olds.items())} for new, olds in sorted(carried.items())},
                        "former_places": former,
                        "todays_places_without_votes": {code: p["name"] for code, p in places["mcd"].items() if not p["votes"]},
                        "not_given": "School districts: a precinct can lie in more than one, and the table does not say which."},
           "sources": source_records(tables, today, meta, official_docs), "places": places}
    if typed:
        doc["control"]["notes"].append("The Secretary's column definitions could not be read at this run for " + ", ".join(typed)
                                       + "; the tickets are named as this loader was checked against them on 2026-10-01.")
    return doc, failed


def write(path, doc):
    """The file: the short parts spread out to be read, the places one to a line."""
    head = json.dumps({k: v for k, v in doc.items() if k != "places"}, ensure_ascii=False, indent=1)
    kinds = []
    for kind, d in doc["places"].items():
        rows = ",\n".join(f"   {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, separators=(',', ':'))}" for k, v in d.items())
        kinds.append(f"  {json.dumps(kind)}: {{\n{rows}\n  }}")
    text = head[:head.rstrip().rfind("}")].rstrip() + ',\n "places": {\n' + ",\n".join(kinds) + "\n }\n}\n"
    json.loads(text)                                                    # it must read back
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def our_places(db):
    """{kind: ids} of our Minnesota places, read only; None when the database is not there."""
    if not db or not os.path.exists(db):
        return None
    con = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    try:
        out = collections.defaultdict(set)
        for kind, pid in con.execute("SELECT kind, id FROM sl_places WHERE source_id LIKE 'mn-%'"):
            out[kind].add(STATE_FIPS + pid if kind == "county" and len(pid) == 3 else pid)
        return dict(out)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def load(say=print, out=OUT, cache=CACHE, db=DB, refresh=False):
    say("    Minnesota place votes: the Secretary of State's official precinct results, from the Minnesota Geospatial Commons")
    net.patient_lookups()
    os.makedirs(cache, exist_ok=True)
    tables = {}
    for year in sorted({c["year"] for c in CONTESTS}, reverse=True):
        tables[year] = results_table(year, sorted({c["prefix"] for c in CONTESTS if c["year"] == year}), cache, refresh, say)
        say(f"      {year}: {len(tables[year]['rows']):,} precincts ({tables[year].get('layer_name')}; copy of {tables[year].get('fetched')})")
    today = today_table(cache, refresh, say)
    meta = {key: read_metadata(key, cache, refresh, say) for key in sorted(set(TABLE_ITEM.values()))}
    say("    the official statewide totals: Clerk of the U.S. House (President and U.S. Senator); the canvassing report as the "
        "University of Minnesota's archive transcribes it (Governor)")
    official, official_docs = official_totals(CONTESTS, cache, refresh, say)
    doc, failed = build(tables, today, meta, official, official_docs)

    p = doc["places"]
    say(f"    added up: {len(p['county'])} counties; {len(p['mcd']):,} cities, townships and unorganized territories; {len(p['senate'])} Senate and "
        f"{len(p['house'])} House districts; {len(p['judicial'])} judicial districts; {len(p['commissioner'])} commissioner districts; "
        f"{len(p['ward'])} wards; {len(p['hospital'])} hospital districts")
    for new, olds in doc["coverage"]["carried_to_todays_code"].items():
        say(f"      the same place under an earlier code: {'; '.join(f'{n} ({o})' for o, n in olds.items())} is filed under {p['mcd'][new]['name']} ({new})")
    if doc["coverage"]["former_places"]:
        say("      no longer places today (kept under their old codes): " + "; ".join(f"{n} ({c})" for c, n in doc["coverage"]["former_places"].items()))
    if doc["coverage"]["todays_places_without_votes"]:
        say("      today's places with no precinct in these elections: "
            + "; ".join(f"{n} ({c})" for c, n in doc["coverage"]["todays_places_without_votes"].items()))
    for c in doc["contests"]:
        ctl, s = doc["control"]["contests"][c["id"]], c["statewide"]
        say(f"    control, {c['id']}: DFL {s['dfl']:,}, Republican {s['rep']:,}, other {s['other']:,}, total {s['total']:,}: "
            + ("equal to" if ctl["equal"] else "DIFFERS from") + f" {ctl['source']} ({ctl['where']}; {ctl['read']})")
    for kind, result in doc["control"]["kinds"].items():
        if result != "equal":
            say(f"    control, {kind}: {result}")
    if failed:
        for line in failed:
            say(f"    CHECK: {line}")
        raise Stop(f"    Minnesota place votes: the control did not hold; {os.path.basename(out)} was not written. Nothing was changed to make it fit.")
    ours = our_places(db)
    if ours:
        covered = {}
        for kind in ("county", "mcd", "senate", "house", "judicial", "hospital"):
            ids = ours.get(kind, set())
            without = sorted(i for i in ids if not p[kind].get(i, {}).get("votes"))
            covered[kind] = {"places": len(ids), "with_votes": len(ids) - len(without), "without": without}
            say(f"      our {kind} places with votes: {len(ids) - len(without):,} of {len(ids):,}" + (f" (none for {', '.join(without[:12])})" if without else ""))
        doc["coverage"]["our_places"] = dict(covered, read=f"sl_places in {os.path.basename(db)}, opened read-only on {_now()}")
    write(out, doc)
    say(f"    Minnesota place votes: {len(doc['contests'])} contests, {sum(len(v) for v in p.values()):,} places, control {doc['control']['result']}; "
        f"{os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e6:.1f} MB)")
    return doc


# ---------------------------------------------------------------- the arithmetic on a made-up table

def selftest(say=print):
    def row(vtd, name, code, kind, county, cname, sen, leg, com, ward=" ", hosp=" ", **v):
        return dict({"vtdid": vtd, "pctname": name, "mcdname": name, "mcdfips": code, "ctu_type": kind, "countyname": cname, "countyfips": county,
                     "mnsendist": sen, "mnlegdist": leg, "ctycomdist": com, "juddist": "09", "ward": ward, "hospdist": hosp,
                     "hospdist_n": "Pine" if hosp.strip() else " "}, **v)

    def pres(r, dfl, lib, wi):
        return {"usprsr": r, "usprsdfl": dfl, "usprslib": lib, "usprswi": wi, "usprstotal": r + dfl + lib + wi}

    def gov(r, dfl, wi):
        return {"mngovr": r, "mngovdfl": dfl, "mngovwi": wi, "mngovtotal": r + dfl + wi}
    f24 = PLACE_FIELDS + ["usprsr", "usprsdfl", "usprslib", "usprswi", "usprstotal"]
    f22 = PLACE_FIELDS + ["mngovr", "mngovdfl", "mngovwi", "mngovtotal"]
    t24 = [row("270010005", "Alder W-1", "00001", "city", "001", "Aitkin", "01", "01A", "01", "W-01", **pres(10, 20, 1, 0)),
           row("270010010", "Alder W-E", "00001", "city", "001", "Aitkin", "01", "01A", "02", "W-E", **pres(5, 5, 0, 1)),
           row("270030005", "Alder (part)", "00001", "city", "003", "Anoka", "02", "02B", "01", "W-01", **pres(7, 3, 0, 0)),
           row("270030010", "Elm", "00012", "city", "003", "Anoka", "02", "02B", "01", hosp="0310", **pres(30, 40, 2, 3)),
           row("270010015", "Pine Lake Unorg", "00041", "unorganized territory", "001", "Aitkin", "01", "01A", "02", **pres(25, 0, 0, 0))]
    t22 = [row("270010005", "Alder W-1", "00001", "city", "001", "Aitkin", "01", "01A", "01", "W-01", **gov(9, 11, 0)),
           row("270030010", "Elm Twp", "00011", "township", "003", "Anoka", "02", "02B", "01", **gov(20, 10, 1)),
           row("270030015", "Fir Twp", "00021", "township", "003", "Anoka", "02", "02B", "02", **gov(4, 2, 0))]
    today = [{"vtdid": "270010005", "mcdname": "Alder", "mcdfips": "00001", "ctu_type": "city", "countyname": "Aitkin", "countyfips": "001"},
             {"vtdid": "270030005", "mcdname": "Alder", "mcdfips": "00001", "ctu_type": "city", "countyname": "Anoka", "countyfips": "003"},
             {"vtdid": "270030010", "mcdname": "Elm", "mcdfips": "00012", "ctu_type": "city", "countyname": "Anoka", "countyfips": "003"},
             {"vtdid": "270030020", "mcdname": "Gum Twp", "mcdfips": "00031", "ctu_type": "township", "countyname": "Anoka", "countyfips": "003"},
             {"vtdid": "270010015", "mcdname": "North Pine Unorg", "mcdfips": "00041", "ctu_type": "unorganized territory", "countyname": "Aitkin",
              "countyfips": "001"}]
    contests = [{"id": "2024-president", "year": 2024, "date": "2024-11-05", "office": "President", "prefix": "usprs", "dfl": "A/B", "rep": "C/D", "official": "x"},
                {"id": "2022-governor", "year": 2022, "date": "2022-11-08", "office": "Governor", "prefix": "mngov", "dfl": "E/F", "rep": "G/H", "official": "x"}]
    tables = {2024: {"fields": f24, "rows": t24, "layer_name": "made up", "fetched": "-"},
              2022: {"fields": f22, "rows": t22, "layer_name": "made up", "fetched": "-"}}
    official = {"2024-president": {"dfl": 68, "rep": 77, "other": 7, "total": 152, "source": "x", "where": "-", "read": "-"},
                "2022-governor": {"dfl": 23, "rep": 33, "other": 1, "total": 57, "source": "x", "where": "-", "read": "-"}}
    doc, failed = build(tables, {"rows": today, "layer_name": "made up", "fetched": "-"}, {}, official, [], contests)
    p, checks = doc["places"], []

    def check(what, got, want):
        checks.append(got == want)
        say(f"      {'ok  ' if got == want else 'FAIL'} {what}" + ("" if got == want else f": got {got!r}, expected {want!r}"))
    check("the control holds on the made-up table", (doc["control"]["result"], failed), ("equal", []))
    check("a city in two counties is one place", p["mcd"]["00001"]["votes"]["2024-president"], {"dfl": 28, "rep": 22, "other": 2, "total": 52})
    check("and reaches both counties", p["mcd"]["00001"]["counties"], ["27001", "27003"])
    check("a county adds up its precincts", p["county"]["27003"]["votes"]["2024-president"], {"dfl": 43, "rep": 37, "other": 5, "total": 85})
    check("a township that became a city is filed under today's code", p["mcd"]["00012"]["votes"]["2022-governor"], {"dfl": 10, "rep": 20, "other": 1, "total": 31})
    check("and says which code it was", list(p["mcd"]["00012"]["earlier"]), ["00011"])
    check("the old code is not kept beside it", "00011" in p["mcd"], False)
    check("a place with no namesake today stays under its code, marked former", p["mcd"]["00021"].get("former"), True)
    check("a place newer than the elections is listed without votes", p["mcd"]["00031"]["votes"], {})
    check("wards are keyed without W- and zeros", sorted(p["ward"]), ["00001-1", "00001-E"])
    check("a ward adds up across counties", p["ward"]["00001-1"]["votes"]["2024-president"]["total"], 41)
    check("commissioner districts are keyed by county", sorted(p["commissioner"]), ["27001-1", "27001-2", "27003-1", "27003-2"])
    check("house districts lose their leading zeros", sorted(p["house"]), ["1A", "2B"])
    check("a hospital district is keyed as our places are", list(p["hospital"]), ["HD00310"])
    check("a contest with fewer than twenty votes in a place is marked too_few", p["mcd"]["00021"].get("too_few"), ["2022-governor"])
    check("and so is one where every vote went the same way", p["mcd"]["00041"].get("too_few"), ["2024-president"])
    check("a place of twenty votes, not all one way, is not marked", p["mcd"]["00001"].get("too_few"), None)
    check("a code that today's table names differently says what it was named", p["mcd"]["00041"].get("named_then"), {"2024": "Pine Lake unorganized territory"})
    check("and takes today's name", p["mcd"]["00041"]["name"], "North Pine unorganized territory")
    wrong = dict(official, **{"2024-president": dict(official["2024-president"], dfl=69, total=153)})
    check("a wrong official total is caught", build(tables, {"rows": today}, {}, wrong, [], contests)[0]["control"]["result"], "differs")
    bad = [dict(t24[0], usprstotal=99)] + t24[1:]
    try:
        build({2024: dict(tables[2024], rows=bad), 2022: tables[2022]}, {"rows": today}, {}, official, [], contests)
        caught = False
    except Stop:
        caught = True
    check("a precinct whose candidates do not add up to its total stops the loader", caught, True)
    say(f"    self-test: {sum(checks)} of {len(checks)} checks passed")
    return all(checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="How each Minnesota place voted in past partisan general elections -> ballot/lean/mn_place_votes.json")
    ap.add_argument("--out", default=OUT, help="the file to write (default: ballot/lean/mn_place_votes.json)")
    ap.add_argument("--cache", default=CACHE, help="where downloads are kept (default: states_cache/mn_local)")
    ap.add_argument("--db", default=DB, help="the ballot database to count our places in, opened read-only (default: ballot_local_2026.sqlite)")
    ap.add_argument("--refresh", action="store_true", help="ask for every table and document again, even when the cached copies are fresh")
    ap.add_argument("--selftest", action="store_true", help="check the arithmetic on a made-up table; downloads and writes nothing")
    a = ap.parse_args(argv)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    load(out=a.out, cache=a.cache, db=a.db, refresh=a.refresh)


if __name__ == "__main__":
    main()
