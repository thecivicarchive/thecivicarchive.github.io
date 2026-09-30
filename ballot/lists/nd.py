"""
North Dakota: the Secretary of State's 2026 General Election Contest/Candidate List (vip.sos.nd.gov, election 348), a
search page: the loader asks it, as the page's own Search button does, for the contest "Representative in Congress"
(North Dakota has no Senate race in 2026) and reads the table it returns. Columns are taken by name, only Contest, Name
and Party; the table also carries mailing addresses, phones, e-mail and websites, which are never read. Parties are
printed as the list prints them ("Democratic-NPL", "independent nomination"). The June 9 primary is not loaded yet.
"""

import html as H
import json
import os
import re
import urllib.parse
from urllib.request import Request, urlopen

from ballot.common import house_id, party_code, record_source
from states import net

URL = "https://vip.sos.nd.gov/candidatelist.aspx?eid=348"
FORM = "ctl00$ContentPlaceHolder1$"
KEEP = ("Contest", "Name", "Party")


def search(contest_label):
    page = net.get(URL).decode("utf-8", "replace")
    if "2026 General Election" not in page:
        raise SystemExit("North Dakota: the candidate list page is no longer the 2026 General Election")
    fields = {m.group(1): H.unescape(m.group(2)) for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}
    contest = re.search(r'<option[^>]*value="(\d+)"[^>]*>\s*%s\s*</option>' % re.escape(contest_label), page)
    if not contest:
        raise SystemExit(f"North Dakota: the contest \"{contest_label}\" is not offered on the page")
    fields.update({FORM + "ddlJursdiction": "AL", FORM + "ddlDistrict": "0", FORM + "ddlContest": contest.group(1),
                   FORM + "ddlCandidate": "0", FORM + "btnSearch": "Search"})
    req = Request(URL, data=urllib.parse.urlencode(fields).encode(), method="POST",
                  headers={"User-Agent": net.UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": URL})
    with urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def table_rows(page):
    for tab in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S):
        heads = [H.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S)]
        if not all(k in heads for k in KEEP):
            continue
        idx = {k: max(i for i, h in enumerate(heads) if h == k) for k in KEEP}      # "Contest" is printed twice; the second is the office
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) == len(heads):
                yield {k: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", cells[i]))).strip() for k, i in idx.items()}


def load(con, cache, say=print):
    net.patient_lookups()
    listed = [r for r in table_rows(search("Representative in Congress")) if r["Contest"] == "Representative in Congress" and r["Name"]]
    if not listed:
        raise SystemExit("North Dakota: the search returned no candidates for Representative in Congress")
    path = os.path.join(cache, "nd", "nd_2026_general_congress.json")      # only the three columns kept
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(listed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    race = house_id("ND", 0)
    rows = [(race, "general", "2026-11-03", r["Name"], r["Party"], party_code(r["Party"]), i, 0, 0, None, None, None, None, None, "nd-sos-2026-candidate-list", None)
            for i, r in enumerate(listed, start=1)]
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-ND-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        record_source(con, "nd-sos-2026-candidate-list", path=path, level="federal", state="ND", kind="official candidate list",
                      agency="North Dakota Secretary of State", title="2026 General Election Contest/Candidate List: Representative in Congress",
                      url=URL, rows=len(rows), note="Read through the page's own search; Contest, Name and Party only, contact columns never read.")
    say(f"    North Dakota: the at-large House seat, {len(rows)} candidates on the November ballot (no Senate race in 2026)")
    return len(rows)
