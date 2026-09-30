"""
Pennsylvania: the Department of State's Election Information page for the 2026 General Election on PA Voter Services
(pavoterservices.pa.gov/ElectionInfo/ElectionInfo.aspx). The page carries every candidate for the election as data in
one hidden field (dataJson): name, party, office, district, status (Approved), how the candidate got there (Petition,
a party primary; Paper, nomination papers for minor parties and independents), and whether they won the May 19
primary. The November ballot is every approved Paper candidate and every Petition candidate who won the primary; a
party's primary field is its Petition candidates for the district, winners marked.

The rows also give each candidate's municipality and county of residence; those are never read. Names are written
"LAST, FIRST M" in capitals; the page shows them first name first in ordinary capitals (a sitting member as the
congress-legislators roster spells them) and says so. Vote counts for the primary are not loaded yet.
"""

import hashlib
import html as H
import json
import os
import re
import sqlite3

from ballot.common import HERE, house_id, party_code, record_source
from ballot.lists.tx import proper
from states import net

URL = "https://www.pavoterservices.pa.gov/ElectionInfo/ElectionInfo.aspx"
PRIMARY = "2026-05-19"
SUFFIX = re.compile(r"^(JR|SR|II|III|IV)\.?$")


def first_last(raw):
    """ARRIAGA, JESSICA -> JESSICA ARRIAGA; ALLEN JR , BRYAN F -> BRYAN F ALLEN JR"""
    last, _, first = raw.partition(",")
    words = last.split()
    suffix = [w for w in words if SUFFIX.match(w)]
    family = [w for w in words if not SUFFIX.match(w)]
    return " ".join(first.split() + family + suffix)


def load(con, cache, say=print):
    net.patient_lookups()
    page = net.get(URL).decode("utf-8", "replace")
    m = re.search(r"id='dataJson'[^>]*value='(.*?)'\s*/?>", page, re.S) or re.search(r'id="dataJson"[^>]*value="(.*?)"\s*/?>', page, re.S)
    if not m:
        raise SystemExit("Pennsylvania: the Election Information page no longer carries its dataJson field")
    raw = H.unescape(m.group(1))
    rows = json.loads(raw)
    path = os.path.join(cache, "pa_electioninfo_2026_general.json")
    kept = [{k: r.get(k) for k in ("CandidateIDNum", "CandidateName", "PartyName", "CandidateStatusValue", "CandidateTypeValue",
                                   "OfficeName", "DistrictName", "ElectionName", "PrimaryResult", "GeneralResult")} for r in rows]
    json.dump(kept, open(path, "w", encoding="utf-8"), ensure_ascii=False)      # the residence columns are not kept
    elections = {r["ElectionName"] for r in kept}
    if elections != {"2026 General Election"}:
        raise SystemExit(f"Pennsylvania: expected the 2026 General Election, the page gave {sorted(elections)}")
    rec = sqlite3.connect(f"file:{os.path.join(HERE, 'congress_119.sqlite')}?mode=ro", uri=True)
    def key_of(name):      # first name and family name, suffixes and initials set aside
        w = [x for x in re.sub(r"[^A-Z ]", "", name.upper()).split() if not SUFFIX.match(x)]
        return (w[0], w[-1]) if len(w) >= 2 else tuple(w)
    fixed, clash = {}, set()
    for full, first, last in rec.execute("SELECT official_full, first_name, last_name FROM legislators WHERE is_current = 1 AND state = 'PA'"):
        k = key_of(f"{first} {last}")
        if k in fixed and fixed[k] != full:
            clash.add(k)
        fixed[k] = full
    for k in clash:
        fixed.pop(k, None)
    out, fields = [], {}
    for r in kept:
        if (r["OfficeName"] or "").strip() != "REPRESENTATIVE IN CONGRESS" or r["CandidateStatusValue"] != "Approved":
            continue
        d = re.match(r"(\d+)", r["DistrictName"] or "")
        if not d:
            continue
        race = house_id("PA", int(d.group(1)))
        caps = first_last(r["CandidateName"])
        name = fixed.get(key_of(caps)) or proper(caps)
        party = r["PartyName"] or ""
        won = str(r["PrimaryResult"]).lower() == "true"
        paper = r["CandidateTypeValue"] == "Paper"
        if paper or won:
            out.append((race, "general", "2026-11-03", name, party, party_code(party), None, 0, 0, None, None, None, None, None, "pa-dos-2026-electioninfo",
                        "Pennsylvania's list writes names in capitals, family name first; they are shown here first name first."))
        if not paper:
            fields.setdefault((race, party), []).append((name, party, won))
    for (race, party), cands in fields.items():
        if len(cands) < 2:
            continue
        code = {"Democratic": "DEM", "Republican": "REP"}.get(party, party[:3].upper())
        for name, p, won in cands:
            out.append((race, f"primary-{code}", PRIMARY, name, p, party_code(p), None, 0, 0, None, None, "advanced" if won else "lost",
                        None, None, "pa-dos-2026-electioninfo", None))
    with con:
        con.execute("DELETE FROM candidates WHERE race_id LIKE '2026-PA-%'")
        con.executemany("INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out)
        record_source(con, "pa-dos-2026-electioninfo", path=path, level="federal", state="PA", kind="official candidate list",
                      agency="Pennsylvania Department of State", title="PA Voter Services, Election Information: 2026 General Election",
                      url=URL, rows=len(kept), note=f"Read from the page's own candidate data (SHA-256 of the data {hashlib.sha256(raw.encode()).hexdigest()[:16]}...); "
                                                    "residence columns not kept. Primary vote counts not loaded yet.")
    general = [r for r in out if r[1] == "general"]
    say(f"    Pennsylvania: {len({r[0] for r in general})} House districts, {len(general)} candidates on the November ballot, "
        f"{len(out) - len(general)} in {sum(1 for v in fields.values() if len(v) > 1)} party primaries")
    return len(general)
