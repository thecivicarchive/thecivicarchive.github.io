"""
Alabama: the Secretary of State's own files. Alabama has seven House seats and the Senate seat of class 2 (Tommy
Tuberville, who is running for Governor) on the ballot in 2026. The House seats are on the 2023 map, which the U.S.
Supreme Court's order of June 2, 2026 put back in effect after the May 19 primary had been held on the 2024 lines, so
the 1st, 2nd, 6th and 7th districts chose their nominees again in special primaries on August 11. Every file below is
linked from the Secretary's 2026 Election Information page (sos.alabama.gov/alabama-votes/voter/election-information/
2026) or its Elections Data Downloads page (.../voter/election-data).

  November ballot   the Secretary of State's "2026 General Election Sample Ballots": one PDF per county, 67 in all
                    (posted September 10, 2026), each drawing every ballot style the county will use. The lists the
                    ballot is printed from (the State Certification of Republican, Democratic and Independent
                    Candidates of August 26, 2026, and the parties' certifications and amendments) are posted only as
                    scanned pictures of paper, with no text to read; the sample ballots are typeset and carry their
                    text. On each sample the county's ballot styles are laid over one another, so the text is read in
                    the order it is drawn (ballot/pdftext.page_runs), a style at a time: the date heading, then the
                    contests "FOR UNITED STATES SENATOR" and "FOR UNITED STATES REPRESENTATIVE, nTH CONGRESSIONAL
                    DISTRICT", each candidate's name in capitals with the party printed beneath it in small type, and
                    the Write-in line. Only styles dated NOVEMBER 3, 2026 count: a few counties' files (Bibb, Blount,
                    Marengo and Wilcox in September 2026) also carry one style of the 2022 ballot drawn beneath, which
                    is set aside and counted. Every 2026 style of every county must print a race identically, or the
                    race is left out and named. The order is the ballot's own (Democrat, then Republican, the same in
                    every county). Parties are printed in full (Democrat, Republican; Jefferson County prints them in
                    capitals) and kept as printed. The kept contests and each file's SHA-256 are cached as JSON in
                    ballot_cache/al/. A sample ballot shows only who is printed on it: no withdrawn candidates can be
                    seen or counted; no independent or minor-party candidate is printed in any federal race (the State
                    Certification of Independent Candidate concerns another office); declared write-in candidates are
                    listed nowhere official, so none are loaded.

  primary fields    The May 19 primary and the June 16 runoff: the Secretary of State's precinct results files
                    (2026_Primary_Election.zip and 2026_PRIMARY_RUNOFF_ELECTION.zip on Elections Data Downloads, posted
                    July 31, 2026): one old-format Excel file (.xls) per county, read with the small reader below
                    (Contest Title, Party, Candidate, then a column per precinct and the ABSENTEE and PROVISIONAL
                    columns). A candidate's votes are the sum of those columns over the 67 counties; the Over Votes and
                    Under Votes lines are kept out of the share. They are checked against the parties' certified vote
                    totals posted with the certifications of results (the Democratic Party's workbooks for the primary
                    and the runoff, the Republican Party's for the primary; the Republican runoff's certification is a
                    scan only). The precinct files are used where the two disagree, because the Democratic workbooks
                    leave out counties in the Senate race (no figures for Lee in the primary; Dallas far short in the
                    runoff); every difference is named in the source note. Alabama prints only contested primaries, so
                    every federal contest is a field; a nominee needs a majority of the votes, and without one the top
                    two go to the runoff. The May 19 Republican contests for the 1st and 6th districts, held on the
                    2024 lines, were replaced by the special primaries (the 1st's runoff was never held); they are not
                    stored, and the source note says so.

                    The August 11 special primaries: the Republican Party's return of the votes, certified to the
                    Secretary of State on August 20, 2026 and posted on Elections Data Downloads as "Republication
                    Results From The Special Congressional Election" (an .xlsx: district totals, and a sheet per county
                    that must add up to them). Its candidates must be exactly those on the Secretary's "2026 Special
                    Primary Election Sample Ballots" (one PDF per county and party, read as above). The Democratic
                    Party's certified results are posted only as a scan, so its one field (the 6th district) is taken
                    from the Democratic sample ballots with no votes, and the winner is the party's candidate on the
                    November ballot. The special primary calendar sets no runoff, and each winner had a majority.

Names are printed in capitals on the sample ballots and shown here in ordinary capitals (each such row says so); the
results files print names in ordinary capitals and are kept as printed. None of these files carries an address,
telephone, e-mail or website: only names, parties, offices, precinct vote columns and totals are read.
"""

import datetime as dt
import hashlib
import html as H
import json
import os
import re
import struct
import time
import zipfile
from collections import defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote

import openpyxl

from ballot.common import fold, house_id, name_parts, party_code, record_source, senate_id
from ballot.lists.tx import proper
from ballot.pdftext import PDF, page_runs
from states import net

SOS = "https://www.sos.alabama.gov"
INFO_PAGE = SOS + "/alabama-votes/voter/election-information/2026"
DATA_PAGE = SOS + "/alabama-votes/voter/election-data"
SAMPLE_PAGES = {"general": SOS + "/alabama-votes/2026-general-election-sample-ballots",
                "special": SOS + "/alabama-votes/2026-special-primary-election-sample-ballots"}
# key -> (address on the Secretary's site, name in the cache)
FILES = {"primary": ("/sites/default/files/election-data/2026-07/2026_Primary_Election.zip", "al_2026_primary_precinct_results.zip"),
         "runoff": ("/sites/default/files/election-data/2026-07/2026_PRIMARY_RUNOFF_ELECTION.zip",
                    "al_2026_primary_runoff_precinct_results.zip"),
         "special_rep": ("/sites/default/files/election-data/2026-09/Republication%20Results%20From%20The%20Special%20Congressional"
                         "%20Election.xlsx", "al_2026_special_primary_rep_results.xlsx"),
         "dem_primary": ("/sites/default/files/election-2026/2026%20Democratic%20Primary%20Election%20Results.xlsx",
                         "al_2026_primary_dem_certified_results.xlsx"),
         "rep_primary": ("/sites/default/files/05-29-2026/GOP%20Results.xlsx", "al_2026_primary_rep_certified_results.xlsx"),
         "dem_runoff": ("/sites/default/files/election-2026/2026%20Democratic%20Primary%20Runoff%20Election%20Results.xlsx",
                        "al_2026_runoff_dem_certified_results.xlsx")}
DEM_SPECIAL_SCAN = SOS + "/sites/default/files/election-2026/DemocraticCertificationofResultsforSpecialPrimary.pdf"
REP_RUNOFF_SCAN = SOS + "/sites/default/files/election-2026/CertificationofResults-RepublicanParty-PrimaryRunoff.pdf"
GENERAL, PRIMARY, RUNOFF, SPECIAL = "2026-11-03", "2026-05-19", "2026-06-16", "2026-08-11"
SPECIAL_DISTRICTS = {1, 2, 6, 7}
PARTY = {"REP": "Republican", "DEM": "Democrat"}                     # as the ballot prints them
PARTY_OF = {"REP": "Republican", "DEM": "Democratic"}                 # as an adjective: "the Democratic primary"
COUNTIES = 67
PRINTED = {"democrat": "Democrat", "republican": "Republican", "libertarian": "Libertarian", "independent": "Independent"}
MONTHS = ("JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER")
DATE = re.compile(r"^(%s) (\d{1,2}), (20\d\d)$" % "|".join(MONTHS))
NAME = re.compile(r"^[^\W\d_][^\d]*$")                                  # a candidate's line: begins with a letter, no digits
FED_TITLE = re.compile(r"^UNITED STATES (SENATOR|REPRESENTATIVE, (\d+)(?:ST|ND|RD|TH) CONGRESSIONAL DISTRICT) \((REP|DEM)\)$")
SPECIAL_HEAD = re.compile(r"^U\.S\. Congress\s*[—–-]+\s*Congressional District (\d+)$")
CAPS = "Alabama's list prints names in capitals; they are shown here in ordinary capitals."
RUNOFF_NOTE = "No candidate had a majority; the top two went to the June 16 runoff."
SPECIAL_NOTE = ("Special primary of August 11, 2026, on the 2023 district lines that the U.S. Supreme Court's order of June 2, 2026 "
                "put back in effect; it replaced the May 19 nomination for this seat.")
NO_VOTES_NOTE = ("The Democratic Party's certified results of this special primary are posted only as a scanned document, so no votes "
                 "are shown; the winner is the party's candidate on the November ballot.")


# ---------- old-format Excel (.xls): BIFF8 inside an OLE2 compound file, cell values only ----------

def _ole_workbook(data):
    """The Workbook stream of an OLE2 compound file."""
    if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("not an old-format Excel file")
    ssz = 1 << struct.unpack_from("<H", data, 0x1E)[0]
    msz = 1 << struct.unpack_from("<H", data, 0x20)[0]
    nfat, dir1 = struct.unpack_from("<II", data, 0x2C)
    cutoff, mfat1, nmfat, difat1, ndifat = struct.unpack_from("<IIIII", data, 0x38)

    def sector(i):
        return data[ssz * (i + 1):ssz * (i + 2)]

    difat, s = list(struct.unpack_from("<109I", data, 0x4C)), difat1
    for _ in range(ndifat):
        if s >= 0xFFFFFFFA:
            break
        vals = struct.unpack("<%dI" % (ssz // 4), sector(s))
        difat, s = difat + list(vals[:-1]), vals[-1]
    fat = []
    for s in difat[:nfat]:
        fat += struct.unpack("<%dI" % (ssz // 4), sector(s))

    def chain(start):
        out, s, seen = [], start, set()
        while s < 0xFFFFFFFA and s not in seen:
            seen.add(s)
            out.append(sector(s))
            s = fat[s]
        return b"".join(out)

    dirs, entries = chain(dir1), []
    for o in range(0, len(dirs) - 127, 128):
        e = dirs[o:o + 128]
        nlen = struct.unpack_from("<H", e, 64)[0]
        entries.append((e[:max(0, nlen - 2)].decode("utf-16-le", "replace"), e[66]) + struct.unpack_from("<II", e, 116))
    root = next(e for e in entries if e[1] == 5)
    for name, kind, start, size in entries:
        if kind != 2 or name.lower() not in ("workbook", "book"):
            continue
        if size >= cutoff:
            return chain(start)[:size]
        mini, raw = chain(root[2]), chain(mfat1) if nmfat else b""
        mfat = struct.unpack("<%dI" % (len(raw) // 4), raw)
        out, s = [], start
        while s < 0xFFFFFFFA:
            out.append(mini[s * msz:(s + 1) * msz])
            s = mfat[s]
        return b"".join(out)[:size]
    raise ValueError("no Workbook stream")


def _rk(v):
    if v & 2:
        n = float((v >> 2) - (1 << 30) if v & 0x80000000 else v >> 2)
    else:
        n = struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
    return n / 100 if v & 1 else n


def _short_string(buf, pos, lenbytes):
    cch = buf[pos] if lenbytes == 1 else struct.unpack_from("<H", buf, pos)[0]
    flags = buf[pos + lenbytes]
    pos += lenbytes + 1
    return buf[pos:pos + 2 * cch].decode("utf-16-le", "replace") if flags & 1 else buf[pos:pos + cch].decode("latin-1")


def _shared_strings(parts):
    """The SST record and its CONTINUE records; a string's characters may run on into the next record, which then
    begins with a fresh flags byte."""
    unique = struct.unpack_from("<I", parts[0], 4)[0]
    out, pi, pos = [], 0, 8
    for _ in range(unique):
        if pos >= len(parts[pi]):
            pi, pos = pi + 1, 0
        buf = parts[pi]
        cch, flags = struct.unpack_from("<H", buf, pos)[0], buf[pos + 2]
        pos += 3
        rich = ext = 0
        if flags & 8:
            rich = struct.unpack_from("<H", buf, pos)[0]
            pos += 2
        if flags & 4:
            ext = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
        wide, left, chars = flags & 1, cch, []
        while left:
            if pos >= len(parts[pi]):
                pi += 1
                wide, pos = parts[pi][0] & 1, 1
            buf = parts[pi]
            take = min(left, (len(buf) - pos) // (2 if wide else 1))
            chars.append(buf[pos:pos + 2 * take].decode("utf-16-le", "replace") if wide else buf[pos:pos + take].decode("latin-1"))
            pos += take * (2 if wide else 1)
            left -= take
        skip = rich * 4 + ext
        while skip:
            if pos >= len(parts[pi]):
                pi, pos = pi + 1, 0
                continue
            k = min(skip, len(parts[pi]) - pos)
            pos, skip = pos + k, skip - k
        out.append("".join(chars))
    return out


def xls_sheets(data):
    """{sheet name: rows}, each row a list of cell values (text or number; None where empty)."""
    wb = _ole_workbook(data)
    recs, i = [], 0
    while i + 4 <= len(wb):
        t, ln = struct.unpack_from("<HH", wb, i)
        recs.append((i, t, wb[i + 4:i + 4 + ln]))
        i += 4 + ln
    starts, sst, k = {}, [], 0
    while k < len(recs):
        off, t, d = recs[k]
        if t == 0x85:                                             # BOUNDSHEET: where each sheet's records begin
            starts[struct.unpack_from("<I", d, 0)[0]] = _short_string(d, 6, 1)
        elif t == 0xFC:                                           # SST, and the CONTINUE records after it
            parts = [d]
            while k + 1 < len(recs) and recs[k + 1][1] == 0x3C:
                k += 1
                parts.append(recs[k][2])
            sst = _shared_strings(parts)
        k += 1
    sheets, cur = {}, None
    for off, t, d in recs:
        if t == 0x809 and off in starts:                          # BOF of a worksheet
            cur = sheets.setdefault(starts[off], {})
        elif cur is None:
            continue
        elif t == 0x0A:                                           # EOF
            cur = None
        elif t == 0xFD:                                           # LABELSST
            r, c, _x, n = struct.unpack_from("<HHHI", d, 0)
            cur[(r, c)] = sst[n]
        elif t == 0x203:                                          # NUMBER
            r, c, _x, v = struct.unpack_from("<HHHd", d, 0)
            cur[(r, c)] = v
        elif t == 0x27E:                                          # RK
            r, c, _x, v = struct.unpack_from("<HHHI", d, 0)
            cur[(r, c)] = _rk(v)
        elif t == 0xBD:                                           # MULRK
            r, c = struct.unpack_from("<HH", d, 0)
            for j in range(struct.unpack_from("<H", d, len(d) - 2)[0] - c + 1):
                cur[(r, c + j)] = _rk(struct.unpack_from("<I", d, 6 + 6 * j)[0])
        elif t == 0x204:                                          # LABEL
            r, c, _x = struct.unpack_from("<HHH", d, 0)
            cur[(r, c)] = _short_string(d, 6, 2)
        elif t == 0x06 and d[12:14] != b"\xff\xff":               # FORMULA with a number cached
            r, c, _x = struct.unpack_from("<HHH", d, 0)
            cur[(r, c)] = struct.unpack_from("<d", d, 6)[0]
    out = {}
    for name, cells in sheets.items():
        nr = max((r for r, _c in cells), default=-1) + 1
        nc = max((c for _r, c in cells), default=-1) + 1
        rows = [[None] * nc for _ in range(nr)]
        for (r, c), v in cells.items():
            rows[r][c] = v
        out[name] = rows
    return out


# ---------- downloads ----------

def fresh(path, days):
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400


def fetch(url, path, magic, what, say, days=30):
    """One file into the cache (kept for `days`), refused unless it starts as the kind of file it should be. Two more
    tries at most after a refusal; a copy on disk is used if the site cannot be reached."""
    try:
        net.download(url, path, max_age_days=days, tries=3, say=say)
    except (HTTPError, URLError, OSError) as e:
        raise SystemExit(f"Alabama: {what} could not be fetched from {url} ({e})")
    with open(path, "rb") as fh:
        head = fh.read(8)
    if not head.startswith(magic):
        os.remove(path)
        raise SystemExit(f"Alabama: {url} did not give {what} (it began {head!r}); nothing was kept")
    return path


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------- the sample ballots ----------

def ballot_lines(path):
    """A sample ballot's text as lines in the order it is drawn: runs on one baseline, in one size, that follow each
    other are one line. [(x, y, size, text)]"""
    pdf = PDF(open(path, "rb").read())
    out = []
    for page, res in pdf.pages():
        cur = None
        for x0, y, size, t, x1 in page_runs(pdf, page, res):
            if cur and abs(cur[1] - y) < 0.6 and abs(cur[2] - size) < 0.6 and -2 <= x0 - cur[4] <= 0.9 * size:
                space = x0 - cur[4] > 0.18 * size and not cur[3].endswith(" ") and not t.startswith(" ")
                cur[3] += (" " if space else "") + t
                cur[4] = max(cur[4], x1)
                continue
            if cur:
                out.append(cur[:4])
            cur = [x0, y, size, t, x1]
        if cur:
            out.append(cur[:4])
    return [(x, y, s, re.sub(r"\s+", " ", t).strip()) for x, y, s, t in out if t.strip()]


def race_of_heading(text):
    t = re.sub(r"\s+", " ", text.replace(" ,", ",")).strip()
    if t == "FOR UNITED STATES SENATOR":
        return senate_id("AL", 2)
    m = re.fullmatch(r"FOR UNITED STATES REPRESENTATIVE,? (\d+)[A-Z]{0,2} CONGRESSIONAL DISTRICT", t)     # the ordinal's letters: ND, TH, "2N" (Covington draws the D apart)
    if m:
        return house_id("AL", int(m.group(1)))
    raise SystemExit(f"Alabama: a federal contest on a sample ballot could not be read: {t!r}")


def ballot_contests(path):
    """Every federal contest drawn on one sample ballot, with the date heading of the style it belongs to:
    [(date, race, [[name, party], ...], write-in line)]. Parties are None on a primary ballot."""
    L = ballot_lines(path)
    out, when, i = [], None, 0
    while i < len(L):
        t = L[i][3]
        m = DATE.match(t)
        if m:
            when = f"{m.group(3)}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"
        if not t.startswith("FOR UNITED STATES"):
            i += 1
            continue
        head, j = [t], i + 1
        while j < len(L) and not L[j][3].startswith("(Vote for") and j - i < 4:
            head.append(L[j][3])
            j += 1
        if j >= len(L) or not L[j][3].startswith("(Vote for"):
            raise SystemExit(f"Alabama: {os.path.basename(path)}: a federal contest has no '(Vote for One)' line")
        race, cands, x0, size0 = race_of_heading(" ".join(head)), [], None, None
        j += 1
        while j < len(L) and not L[j][3].startswith("Write-in"):
            x, _y, size, name = L[j]
            if x0 is None:
                x0, size0 = x, size
            elif abs(x - x0) > 1.5 or abs(size - size0) > 0.3:
                break
            if not NAME.match(name) or name.startswith("SAMPLE"):
                break
            party = None
            if j + 1 < len(L) and abs(L[j + 1][0] - x0) <= 1.5 and L[j + 1][2] < 0.8 * size0 and not L[j + 1][3].startswith("Write-in"):
                party = L[j + 1][3]
                j += 1
            cands.append([name, party])
            j += 1
        out.append((when, race, cands, j < len(L) and L[j][3].startswith("Write-in")))
        i = j
    return out


def sample_links(kind):
    """[(county, party code or None, file name, address)] from one of the Secretary's sample ballot pages."""
    page = net.get(SAMPLE_PAGES[kind], accept="text/html").decode("utf-8", "replace")
    out = {}
    for m in re.finditer(r'<a[^>]+href="([^"]*/sample-ballots/2026/[^"]+\.pdf)"', page, re.I):
        href = H.unescape(m.group(1))
        file = unquote(href.rsplit("/", 1)[1])
        if kind == "general":
            mm = re.fullmatch(r"(.+?)[-_ ]Sample\.pdf", file, re.I)             # Autauga-Sample.pdf, Macon_Sample.pdf
            if not mm:
                continue                                          # the statewide back of the ballot (the amendments)
            county, party = mm.group(1).strip(), None
        else:
            mm = re.fullmatch(r"(.+?)\s*-\s*(Dem|Rep)\s*\.pdf", file, re.I)
            if not mm:
                raise SystemExit(f"Alabama: a special primary sample ballot's name could not be read: {file!r}")
            county, party = mm.group(1).strip(), mm.group(2).upper()
        out[file] = (county, party, file, href if href.startswith("http") else SOS + quote(unquote(href)))
    return sorted(out.values())


def sample_ballots(folder, kind, say):
    """The federal contests of one election's sample ballots, as JSON in the cache (read afresh after 14 days)."""
    path = os.path.join(folder, f"al_2026_{kind}_sample_ballots_federal.json")
    if fresh(path, 14):
        return path
    try:
        links = sample_links(kind)
    except (HTTPError, URLError, OSError) as e:
        if os.path.exists(path):
            say(f"      the {kind} sample ballot page could not be read ({e}); using the ballots read earlier")
            return path
        raise SystemExit(f"Alabama: the {kind} sample ballot page could not be read ({e})")
    if not links:
        raise SystemExit(f"Alabama: no sample ballots are linked from {SAMPLE_PAGES[kind]}")
    pdfs = os.path.join(folder, f"sample_{kind}")
    os.makedirs(pdfs, exist_ok=True)
    files = []
    for county, party, file, url in links:
        pdf = fetch(url, os.path.join(pdfs, file), b"%PDF-", f"the {county} County sample ballot", say, days=14)
        groups = {}
        for when, race, cands, write_in in ballot_contests(pdf):
            key = json.dumps([when, race, cands, write_in])
            groups[key] = groups.get(key, 0) + 1
        files.append({"county": county, "party": party, "file": file, "url": url, "sha256": sha256(pdf), "bytes": os.path.getsize(pdf),
                      "contests": [dict(zip(("date", "race", "cands", "write_in"), json.loads(k)), drawn=n) for k, n in groups.items()]})
    raw = json.dumps(files, sort_keys=True).encode("utf-8")
    json.dump({"page": SAMPLE_PAGES[kind], "read": dt.date.today().isoformat(), "sha256_files": hashlib.sha256(raw).hexdigest(),
               "files": files}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def agreed(data, date, party=None):
    """{race: [[name, party], ...]} where every style of that date, in every county, prints the race the same way;
    also the races whose counties disagree, and the contests of other dates set aside {(county, date): times drawn}."""
    seen, other, counties = defaultdict(dict), defaultdict(int), defaultdict(set)
    for f in data["files"]:
        if party and f["party"] != party:
            continue
        for k in f["contests"]:
            if k["date"] != date:
                other[(f["county"], k["date"])] += k["drawn"]
                continue
            cands = []
            for name, printed in k["cands"]:
                if printed is not None:
                    if printed.lower() not in PRINTED:
                        raise SystemExit(f"Alabama: {f['county']} County's sample ballot prints an unknown party {printed!r}")
                    printed = PRINTED[printed.lower()]
                cands.append((name, printed))
            key = (tuple(cands), bool(k["write_in"]))
            seen[k["race"]].setdefault(key, set()).add(f["county"])
            counties[k["race"]].add(f["county"])
    races, split = {}, {}
    for race, versions in seen.items():
        if len(versions) == 1:
            (cands, write_in), = versions
            races[race] = (list(cands), write_in, len(counties[race]))
        else:
            split[race] = {"; ".join(f"{n} ({p})" if p else n for n, p in c): sorted(v) for (c, _w), v in versions.items()}
    return races, split, other


# ---------- the results ----------

def county_key(name):
    return re.sub(r"[^a-z]", "", fold(name.replace("_", " ")))


def number(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    f = float(v)
    if f != int(f):
        raise SystemExit(f"Alabama: a vote count is not a whole number: {v!r}")
    return int(f)


def precinct_results(path):
    """The federal contests of one precinct results zip: {(race, code): {candidate: votes}}, the over and under votes,
    {(race, code, candidate, county): votes} and the counties read."""
    totals, blanks, by_county, counties = defaultdict(dict), defaultdict(int), defaultdict(int), []
    with zipfile.ZipFile(path) as z:
        for n in sorted(z.namelist()):
            m = re.fullmatch(r"2026_PRIMARY(?:_RUNOFF)?_ELECTION-(.+)\.xls", n)
            if not m:
                raise SystemExit(f"Alabama: an unexpected file in {os.path.basename(path)}: {n}")
            county = m.group(1).replace("_", " ")
            counties.append(county)
            for sheet, rows in xls_sheets(z.read(n)).items():
                if not rows:
                    continue
                if [str(c or "").strip() for c in rows[0][:3]] != ["Contest Title", "Party", "Candidate"]:
                    raise SystemExit(f"Alabama: {n} ({sheet}) does not begin Contest Title, Party, Candidate")
                for r in rows[1:]:
                    title = re.sub(r"\s+", " ", str(r[0] or "")).strip()
                    mm = FED_TITLE.match(title)
                    if not mm:
                        if re.search(r"UNITED STATES|CONGRESS", title):
                            raise SystemExit(f"Alabama: a federal contest in {n} could not be read: {title!r}")
                        continue
                    race = senate_id("AL", 2) if mm.group(1) == "SENATOR" else house_id("AL", int(mm.group(2)))
                    code, cand = mm.group(3), re.sub(r"\s+", " ", str(r[2] or "")).strip()
                    if str(r[1] or "").strip() != code:
                        raise SystemExit(f"Alabama: {n}: {title} lists a candidate of party {r[1]!r}")
                    votes = number(sum(v for v in r[3:] if isinstance(v, float)))
                    if cand in ("Over Votes", "Under Votes"):
                        blanks[(race, code, cand)] += votes
                        continue
                    totals[(race, code)][cand] = totals[(race, code)].get(cand, 0) + votes
                    by_county[(race, code, cand, county_key(county))] += votes
    return totals, blanks, by_county, counties


def dem_workbook(path):
    """The Democratic Party's certified vote totals (sheet Candidates: Office, District, Place, Ballot Name, a column
    per county, TOTAL): {(race, name): ({county: votes}, total)} for the federal rows."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = wb["Candidates"].iter_rows(values_only=True)
    head = [str(c or "").strip() for c in next(rows)]
    if head[:4] != ["Office", "District/Jurisdiction", "Place", "Ballot Name"] or head[-1] != "TOTAL":
        raise SystemExit(f"Alabama: {os.path.basename(path)} does not have the columns it had")
    out = {}
    for r in rows:
        office = str(r[0] or "").strip()
        if office == "United States Senator":
            race = senate_id("AL", 2)
        elif office == "United States Representative":
            race = house_id("AL", number(r[1]))
        else:
            continue
        out[(race, str(r[3]).strip())] = ({county_key(head[i]): number(r[i]) for i in range(4, len(head) - 1)}, number(r[len(head) - 1]))
    wb.close()
    return out


def rep_workbook(path):
    """The Republican Party's certified vote totals (a Summary sheet and one per county, each a run of blocks: the
    office with "Votes" and "Percentage", a row per candidate, a Total row): {(race, name): ({county: votes}, total)}."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = defaultdict(lambda: [{}, None])
    for ws in wb.worksheets:
        race = None
        for r in ws.iter_rows(values_only=True):
            a = str(r[0] or "").strip() if r else ""
            b = str(r[1] or "").strip() if len(r) > 1 else ""
            if b == "Votes":
                m = re.fullmatch(r"U\.?\s?S\.? Representative,? (\d+)(?:st|nd|rd|th) Congressional District", a, re.I)
                race = senate_id("AL", 2) if re.fullmatch(r"(?:U\.?\s?S\.?\s+|United States\s+)?Senator", a, re.I) else (
                    house_id("AL", int(m.group(1))) if m else None)
                continue
            if a == "Total":
                race = None
                continue
            if not race or not a:
                continue
            if ws.title == "Summary":
                out[(race, a)][1] = number(b)
            else:
                out[(race, a)][0][county_key(ws.title)] = number(b)
    wb.close()
    return {k: tuple(v) for k, v in out.items()}


def special_workbook(path):
    """The Republican Party's return of the August 11 special primary: {race: {candidate: votes}} from the Summary
    sheet, and the problems found checking it (each block's Total Votes, and the county sheets adding up)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    totals, counties, problems = {}, defaultdict(lambda: defaultdict(int)), []
    for ws in wb.worksheets:
        grid = [list(r) for r in ws.iter_rows(values_only=True)]

        def cell(i, c):
            return grid[i][c] if i < len(grid) and c < len(grid[i]) else None
        for i, row in enumerate(grid):
            for c, v in enumerate(row):
                m = SPECIAL_HEAD.match(str(v or "").strip())
                if not m:
                    continue
                race, j = house_id("AL", int(m.group(1))), i + 1
                while j < len(grid) and str(cell(j, c) or "").strip() != "Candidate":
                    j += 1
                cands, stated, j = {}, None, j + 1
                while j < len(grid):
                    name = str(cell(j, c) or "").strip()
                    if not name:
                        break
                    if name.startswith("Total"):
                        stated = number(cell(j, c + 1))
                        break
                    try:
                        cands[name] = number(cell(j, c + 1))
                    except ValueError:
                        if ws.title == "Summary":
                            raise SystemExit(f"Alabama: the special primary return's district total for {name} is {cell(j, c + 1)!r}")
                        problems.append(f"{ws.title} County sheet, {race}: {name}'s votes are written {cell(j, c + 1)!r} (taken as none)")
                        cands[name] = 0
                    j += 1
                if stated != sum(cands.values()):
                    problems.append(f"{ws.title} {race}: candidates add up to {sum(cands.values()):,}, the sheet says {stated}")
                if ws.title == "Summary":
                    totals[race] = cands
                else:
                    for name, n in cands.items():
                        counties[race][name] += n
    wb.close()
    for race, cands in totals.items():
        for name, n in cands.items():
            if counties[race].get(name) != n:
                problems.append(f"{race} {name}: the county sheets add up to {counties[race].get(name, 0):,}, the district total is {n:,}")
    return totals, problems


def compare(sos, sos_county, cert, code, stage, counties):
    """Where a party's certified workbook differs from the Secretary's precinct files, in words."""
    out, names = [], {county_key(c): c for c in counties}
    for (race, c), cands in sorted(sos.items()):
        if c != code:
            continue
        label = f"{'U.S. Senate' if race.endswith('S2') else 'U.S. House District ' + str(int(race[-2:]))}, {PARTY_OF[code]} {stage}"
        diffs, where = [], set()
        for name, votes in cands.items():
            if (race, name) not in cert:
                diffs.append(f"{name} missing")
                continue
            counts, total = cert[(race, name)]
            if total != votes:
                diffs.append(f"{name} {total if total is None else format(total, ',')} against {votes:,}")
            for county, n in counts.items():
                if (n or 0) != sos_county.get((race, code, name, county), 0):
                    where.add(names.get(county, county))
        extra = [n for (r, n) in cert if r == race and n not in cands]
        if extra:
            diffs.append("the workbook also names " + ", ".join(extra))
        if diffs or where:
            out.append(f"{label}: the party's workbook gives {'; '.join(diffs) or 'the same totals'}"
                       + (f" (counties that differ: {', '.join(sorted(where))})" if where else ""))
    return out


def same_person(a, b):
    """Two printings of one name: the same letters, or the same family name and first given name."""
    if fold(a) == fold(b):
        return True
    (ga, fa), (gb, fb) = name_parts(a), name_parts(b)
    return bool(fa and fa == fb and ga and gb and ga[0] == gb[0])


def label(race):
    return "the Senate" if race.endswith("S2") else f"District {int(race[-2:])}"


def load(con, cache, say=print):
    net.patient_lookups()
    folder = os.path.join(cache, "al")
    os.makedirs(folder, exist_ok=True)
    paths = {k: fetch(SOS + url, os.path.join(folder, name), b"PK", f"the file {name}", say) for k, (url, name) in FILES.items()}
    gpath = sample_ballots(folder, "general", say)
    spath = sample_ballots(folder, "special", say)
    gdata = json.load(open(gpath, encoding="utf-8"))
    sdata = json.load(open(spath, encoding="utf-8"))

    want = [senate_id("AL", 2)] + [house_id("AL", d) for d in range(1, 8)]
    problems, gaps = [], {}

    # the November ballot
    general, split, older = agreed(gdata, GENERAL)
    rows, nominees = [], {}
    for race in want:
        if race in split:
            gaps[race] = "The counties' sample ballots do not print this race the same way; it is left out until they agree."
            problems.append(f"{race}: the counties' sample ballots disagree: {split[race]}")
            continue
        if race not in general:
            gaps[race] = "No county's sample ballot for November 3 prints this race."
            continue
        cands, write_in, _n = general[race]
        if not write_in:
            problems.append(f"{race}: no Write-in line on the sample ballots")
        for order, (name, printed) in enumerate(cands, start=1):
            if not printed:
                raise SystemExit(f"Alabama: {race}: {name} has no party printed beneath the name")
            if printed in nominees.get(race, {}):
                raise SystemExit(f"Alabama: {race}: two {printed} candidates on the sample ballots")
            nominees.setdefault(race, {})[printed] = proper(name)
            rows.append((race, "general", GENERAL, proper(name), printed, party_code(printed), order, 0, 0, None, None, None, None, None,
                         "al-sos-2026-general-sample-ballots", CAPS))
    if len(gdata["files"]) != COUNTIES:
        problems.append(f"{len(gdata['files'])} county sample ballots are linked, not {COUNTIES}")
    if senate_id("AL", 2) in general and general[senate_id("AL", 2)][2] != len(gdata["files"]):
        problems.append(f"the Senate race is printed on {general[senate_id('AL', 2)][2]} of {len(gdata['files'])} counties' sample ballots")
    stray = sorted(r for r in general if r not in want)
    if stray:
        raise SystemExit(f"Alabama: the sample ballots print federal races that were not expected: {stray}")
    set_aside = defaultdict(int)
    for (county, date), n in older.items():
        set_aside[date] += n
        if date is None:
            problems.append(f"{county} County's sample ballot draws a federal contest before any date heading")

    def nominee(race, code):
        return nominees.get(race, {}).get(PARTY[code])

    # the May 19 primary and the June 16 runoff: the Secretary's precinct files
    ptot, pblank, pcounty, pcounties = precinct_results(paths["primary"])
    rtot, rblank, rcounty, rcounties = precinct_results(paths["runoff"])
    fields = {"primary": 0, "runoff": 0, "special": 0}
    replaced = []
    for (race, code), cands in sorted(ptot.items()):
        if race.startswith("2026-AL-H") and int(race[-2:]) in SPECIAL_DISTRICTS:
            lead = sorted(cands, key=lambda n: -cands[n])
            held = "" if 2 * cands[lead[0]] > sum(cands.values()) else (
                f"; its runoff between {lead[0]} and {lead[1]} was " + ("held" if (race, code) in rtot else "not held"))
            replaced.append(f"the {PARTY_OF[code]} primary for {label(race)} ({len(cands)} candidates; {lead[0]} led{held})")
            continue
        if len(cands) < 2:
            continue
        fields["primary"] += 1
        total = sum(cands.values())
        ranked = sorted(cands, key=lambda n: -cands[n])
        runoff = 2 * cands[ranked[0]] <= total
        won = ranked[:2] if runoff else ranked[:1]
        final = nominee(race, code)
        if runoff:
            pair = rtot.get((race, code), {})
            if {fold(n) for n in pair} != {fold(n) for n in won}:
                problems.append(f"{race} {code}: the runoff lists {sorted(pair)}, the primary's top two were {won}")
        elif final and not same_person(won[0], final):
            problems.append(f"{race} {code}: the primary's winner ({won[0]}) is not the party's candidate on the sample ballots ({final})")
        for name in ranked:
            note = RUNOFF_NOTE if runoff and name in won else None
            if name in won and not runoff and not final:
                note = f"Won the {PARTY_OF[code]} nomination but is not on the November sample ballots."
            rows.append((race, f"primary-{code}", PRIMARY, name, PARTY[code], party_code(PARTY[code]), None, 0, 0, cands[name],
                         round(100 * cands[name] / total, 1), "advanced" if name in won else "lost", None, None,
                         "al-sos-2026-primary-precinct-results", note))
    for (race, code), cands in sorted(rtot.items()):
        if race.startswith("2026-AL-H") and int(race[-2:]) in SPECIAL_DISTRICTS:
            replaced.append(f"the {PARTY_OF[code]} runoff for {label(race)}")
            continue
        if len(cands) < 2:
            continue
        fields["runoff"] += 1
        total = sum(cands.values())
        ranked = sorted(cands, key=lambda n: -cands[n])
        final = nominee(race, code)
        if final and not same_person(ranked[0], final):
            problems.append(f"{race} {code}: the runoff's winner ({ranked[0]}) is not the party's candidate on the sample ballots ({final})")
        for name in ranked:
            note = None if final or name != ranked[0] else f"Won the {PARTY_OF[code]} nomination but is not on the November sample ballots."
            rows.append((race, f"runoff-{code}", RUNOFF, name, PARTY[code], party_code(PARTY[code]), None, 0, 0, cands[name],
                         round(100 * cands[name] / total, 1), "advanced" if name == ranked[0] else "lost", None, None,
                         "al-sos-2026-runoff-precinct-results", note))

    # the parties' certified workbooks, as a check on the precinct files
    checks = {"primary": compare(ptot, pcounty, dem_workbook(paths["dem_primary"]), "DEM", "primary", pcounties)
              + compare({k: v for k, v in ptot.items() if not (k[0].startswith("2026-AL-H") and int(k[0][-2:]) in SPECIAL_DISTRICTS)},
                        pcounty, rep_workbook(paths["rep_primary"]), "REP", "primary", pcounties),
              "runoff": compare(rtot, rcounty, dem_workbook(paths["dem_runoff"]), "DEM", "runoff", rcounties)}

    # the August 11 special primaries
    special, sproblems = special_workbook(paths["special_rep"])
    problems += sproblems
    sballots = {code: agreed(sdata, SPECIAL, code) for code in ("REP", "DEM")}
    for code in ("REP", "DEM"):
        _races, ssplit, _older = sballots[code]
        for race, versions in ssplit.items():
            problems.append(f"{race} {code}: the special primary sample ballots disagree: {versions}")
    for race, cands in sorted(special.items()):
        printed = [n for n, _p in sballots["REP"][0].get(race, ([], None, 0))[0]]
        if len(printed) != len(cands) or not all(sum(same_person(n, p) for p in printed) == 1 for n in cands):
            problems.append(f"{race} REP: the special primary return names {sorted(cands)}, the sample ballots "
                            f"{sorted(printed) or 'none'}")
        if len(cands) < 2:
            continue
        fields["special"] += 1
        total = sum(cands.values())
        ranked = sorted(cands, key=lambda n: -cands[n])
        final = nominee(race, "REP")
        if 2 * cands[ranked[0]] <= total:
            problems.append(f"{race} REP: the special primary's leader ({ranked[0]}) had no majority")
        if final and not same_person(ranked[0], final):
            problems.append(f"{race} REP: the special primary's winner ({ranked[0]}) is not the party's candidate on the sample ballots ({final})")
        for name in ranked:
            note = SPECIAL_NOTE if final or name != ranked[0] else SPECIAL_NOTE + " Won the Republican nomination but is not on the November sample ballots."
            rows.append((race, "primary-REP", SPECIAL, name, "Republican", party_code("Republican"), None, 0, 0, cands[name], round(100 * cands[name] / total, 1),
                         "advanced" if name == ranked[0] else "lost", None, None, "al-gop-2026-special-primary-results", note))
    dem_special = {}
    for race, (cands, _wi, ncounties) in sorted(sballots["DEM"][0].items()):
        if len(cands) < 2:
            continue
        fields["special"] += 1
        final = nominee(race, "DEM")
        names = [proper(n) for n, _p in cands]
        won = [n for n in names if final and same_person(n, final)]
        if len(won) != 1:
            problems.append(f"{race} DEM: the party's candidate on the November ballot ({final}) is not one of the special primary's {names}")
        dem_special[race] = (names, ncounties)
        for name in names:
            rows.append((race, "primary-DEM", SPECIAL, name, "Democrat", party_code("Democrat"), None, 0, 0, None, None,
                         ("advanced" if name in won else "lost") if len(won) == 1 else None, None, None,
                         "al-sos-2026-special-primary-sample-ballots", f"{SPECIAL_NOTE} {NO_VOTES_NOTE} {CAPS}"))

    for race in want:
        if race not in gaps and not any(r[0] == race and r[1] == "general" for r in rows):
            gaps[race] = "No candidates could be read for this race."

    counted = {r[0] for r in rows if r[1] == "general"}
    n = sum(1 for r in rows if r[1] == "general")
    older_note = (", ".join(f"{times} federal contests dated {date}" for date, times in sorted(set_aside.items(), key=str))
                  + " (in " + ", ".join(sorted({c for c, _d in older})) + ")") if older else "none"
    blank_note = "; ".join(f"the {PARTY_OF[c]} primary for {label(r)}: {pblank.get((r, c, 'Over Votes'), 0):,} over and "
                           f"{pblank.get((r, c, 'Under Votes'), 0):,} under" for (r, c) in sorted(ptot)
                           if not (r.startswith("2026-AL-H") and int(r[-2:]) in SPECIAL_DISTRICTS))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-AL-%'")
        con.execute("DELETE FROM list_gaps WHERE state = 'AL'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO list_gaps VALUES (?, 'AL', ?)", sorted(gaps.items()))
        record_source(con, "al-sos-2026-general-sample-ballots", path=gpath, level="federal", state="AL", kind="official sample ballots",
                      agency="Alabama Secretary of State, Elections Division",
                      title="2026 General Election Sample Ballots, November 3, 2026 (federal contests, every county)",
                      url=SAMPLE_PAGES["general"], rows=n,
                      note=f"Read {gdata['read']}: {len(gdata['files'])} county sample ballots (PDF, one page each, every ballot style of the "
                           "county drawn one over another); the federal contests were read in drawing order and every 2026 style of every "
                           f"county prints each race identically. Contests of an older ballot drawn beneath, set aside: {older_note}. The State "
                           "Certifications of Republican, Democratic and Independent Candidates (August 26, 2026) and the parties' "
                           "certifications are scans with no text, so the typeset sample ballots are read instead. A ballot shows no "
                           "withdrawn candidates, so none can be counted; no independent or minor-party candidate is printed in any "
                           "federal race; no declared write-in candidates are listed. Ballot order as printed (Democrat, then "
                           "Republican). Names printed in capitals are shown in ordinary capitals.")
        record_source(con, "al-sos-2026-primary-precinct-results", path=paths["primary"], level="federal", state="AL", kind="official results",
                      agency="Alabama Secretary of State, Elections Division",
                      title="2026 Primary Election, May 19, 2026: precinct results by county (federal contests)", url=DATA_PAGE,
                      published="2026-07-31", rows=sum(len(v) for v in ptot.values()),
                      note=f"{SOS + FILES['primary'][0]}: {len(pcounties)} county files (.xls; Contest Title, Party, Candidate, a column "
                           "per precinct, ABSENTEE, PROVISIONAL), summed over the counties. Over and under votes are not counted in a "
                           f"candidate's share ({blank_note}). Replaced by the August 11 special primaries and not stored: "
                           f"{'; '.join(replaced) or 'none'}. Checked against the parties' "
                           "certified vote totals (the Democratic and Republican workbooks posted with their certifications of results, "
                           "June 2, 2026): " + ("; ".join(checks["primary"]) + "." if checks["primary"] else "they agree."))
        record_source(con, "al-sos-2026-runoff-precinct-results", path=paths["runoff"], level="federal", state="AL", kind="official results",
                      agency="Alabama Secretary of State, Elections Division",
                      title="2026 Primary Runoff Election, June 16, 2026: precinct results by county (federal contests)", url=DATA_PAGE,
                      published="2026-07-31", rows=sum(len(v) for v in rtot.values()),
                      note=f"{SOS + FILES['runoff'][0]}: {len(rcounties)} county files, read as the primary's. Checked against the "
                           "Democratic Party's certified workbook (July 1, 2026): " + ("; ".join(checks["runoff"]) + "." if checks["runoff"]
                                                                                        else "they agree.")
                           + f" The Republican Party's certification of the runoff (June 24, 2026, {REP_RUNOFF_SCAN}) is a scan with no "
                             "text, so the Republican runoff is checked only against the November ballot.")
        record_source(con, "al-gop-2026-special-primary-results", path=paths["special_rep"], level="federal", state="AL", kind="official results",
                      agency="Alabama Republican Party (return of the votes certified to the Secretary of State on August 20, 2026), "
                             "published by the Alabama Secretary of State",
                      title="Results From The Special Congressional Election: Republican special primary, August 11, 2026",
                      url=SOS + FILES["special_rep"][0], published="2026-09-01", rows=sum(len(v) for v in special.values()),
                      note="District totals from the Summary sheet; each district's county sheets add up to them"
                           + (" except: " + "; ".join(sproblems) if sproblems else "") + ". The candidates are those on the "
                           "Secretary of State's special primary sample ballots. Districts 1, 2, 6 and 7 only.")
        record_source(con, "al-sos-2026-special-primary-sample-ballots", path=spath, level="federal", state="AL", kind="official sample ballots",
                      agency="Alabama Secretary of State, Elections Division",
                      title="2026 Special Primary Election Sample Ballots, August 11, 2026 (congressional districts 1, 2, 6 and 7)",
                      url=SAMPLE_PAGES["special"], rows=sum(len(v[0]) for v in dem_special.values()),
                      note=f"Read {sdata['read']}: {len(sdata['files'])} sample ballots, one per county and party. The Democratic ballots "
                           "give the Democratic special primary's candidates ("
                           + "; ".join(f"{label(r)}: {', '.join(v[0])}, the same in {v[1]} counties" for r, v in dem_special.items())
                           + f"); the party's certified results ({DEM_SPECIAL_SCAN}) are a scan with no text, so no votes are stored and the "
                             "winner is the party's candidate on the November ballot. The Republican ballots are a check on the "
                             "Republican Party's return.")
        for key, sid, title in (("dem_primary", "al-dem-2026-primary-certified-totals", "Certification of Results, Democratic Party: vote "
                                 "totals, 2026 Primary Election, May 19, 2026 (certified by the party June 2, 2026)"),
                                ("rep_primary", "al-gop-2026-primary-certified-totals", "Certification of Results, Republican Party: vote "
                                 "totals, 2026 Primary Election, May 19, 2026 (certified by the party June 2, 2026)"),
                                ("dem_runoff", "al-dem-2026-runoff-certified-totals", "Certification of Results, Democratic Party: vote "
                                 "totals, 2026 Primary Runoff Election, June 16, 2026 (certified by the party July 1, 2026)")):
            record_source(con, sid, path=paths[key], level="federal", state="AL", kind="official results (a check)",
                          agency="Alabama " + ("Democratic" if key.startswith("dem") else "Republican") + " Party, posted by the Alabama "
                                 "Secretary of State", title=title, url=SOS + FILES[key][0],
                          note="Used only to check the Secretary of State's precinct files; the differences are named in their notes.")
    say(f"    Alabama: 7 House districts and the Senate race, {n} candidates on the November ballot (from {len(gdata['files'])} counties' "
        f"sample ballots; none withdrawn can be counted); {fields['primary']} party primaries with a field on May 19, {fields['runoff']} "
        f"runoffs on June 16, {fields['special']} special primary fields on August 11 (votes from the Secretary's precinct files and the "
        f"Republican Party's return; the Democratic special primary in {', '.join(label(r) for r in dem_special) or 'no district'} "
        f"without votes, scan only)")
    for c in checks["primary"] + checks["runoff"]:
        say(f"      check: {c}")
    for p in problems:
        say(f"      problem: {p}")
    for race, why in sorted(gaps.items()):
        say(f"      {race} not loaded: {why}")
    if counted != set(want) - set(gaps):
        say(f"      races with candidates: {sorted(counted)}")
    return n
