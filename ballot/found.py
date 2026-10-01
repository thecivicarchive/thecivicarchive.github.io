"""
ballot/found.py - what the open-web sweep found and a second reader confirmed (John, 2026-10-01), brought into the
ballot database with the page that states each fact.

The sweep wrote ballot/found/<ST>-<k>.json: for candidates on the November lists, a campaign website, a birth year,
offices held, and "review" items where a source disagrees with our record. A second agent re-opened every source and
marked what it confirmed "verified": true. Only those are read here, and each is tied to a candidate by race and exact
name as the official list prints it; a finding whose candidate has left the list is counted and skipped.

  websites      the table ballot/campaign.py reads (person, url, source). A found site's source begins with MARK and
                carries the sentence saying what ties the site to the race. A site the state's list or the FEC gave is
                never replaced: the same site is counted as confirmed, a different one is written to REVIEW.md.
  found_facts   race_id, name, field ('born' or 'office'), year, date, office, from_year, to_year, source, url, kind,
                verified_on. kind is official (a government's own page), campaign (the candidate's own site) or
                secondary (Wikipedia with a citation, or a named news organization). A birth DATE is kept only from an
                official or campaign page; from a secondary source the year alone. to_year is a year, the word 'now'
                when the source says the office is held today, or empty when the source does not say. An election
                year ("elected 2018") is not a start year and is not stored as one.

Official records stay the first source (ballot/people.py and its people table are not changed, apart from the website
address the campaign stage also puts there): a found birth year or office is stored only where the official records
give none for that person. Review items are never loaded; they are written, one a line, to ballot/found/REVIEW.md for
a person to read. Nothing else in the files is read: no address, family, health, religion, employer or view.

The stage deletes and rewrites only its own rows, so it can be run again and gives the same result.
"""

import glob
import json
import os
import re
import urllib.parse

from ballot import campaign
from ballot.common import HERE

DIR = os.path.join(HERE, "ballot", "found")
REVIEW = os.path.join(DIR, "REVIEW.md")
MARK = "Found on the open web"
KINDS = ("official", "campaign", "secondary")
NOVEMBER = ("general", "open-primary")      # Louisiana's House contest on November 3 is an open primary
SCHEMA = """CREATE TABLE IF NOT EXISTS found_facts (
  race_id TEXT NOT NULL, name TEXT NOT NULL, field TEXT NOT NULL, year INTEGER, date TEXT, office TEXT,
  from_year INTEGER, to_year, source TEXT, url TEXT, kind TEXT, verified_on TEXT);
CREATE INDEX IF NOT EXISTS idx_found_facts ON found_facts (race_id, name);"""


def _web(url):
    url = (url or "").strip()
    return url if re.match(r"(?i)^https?://[^\s/]+\.[^\s/]+", url) else None


def _host(url):
    return re.sub(r"^www\.", "", urllib.parse.urlparse(url).netloc.lower())


def _line(text):
    return re.sub(r"\s+", " ", str(text or "")).replace("|", "/").strip()


def _year(text, end=False):
    """A year from the sweep's 'from' or 'to': '2019', '2019 (elected 2018)' -> 2019; 'now' (an end only) -> 'now';
    'elected 2018', 'not stated' and blanks -> None, since an election year is not the year a term began."""
    t = (text or "").strip().lower()
    if end and t in ("now", "present", "today"):
        return "now"
    m = re.match(r"^(\d{4})\b", t)
    return int(m.group(1)) if m and 1900 <= int(m.group(1)) <= 2026 else None


def load(con, say=print, folder=DIR):
    con.executescript(SCHEMA + campaign.OPTIONS)
    has_people = bool(con.execute("SELECT 1 FROM sqlite_master WHERE name = 'people'").fetchone())
    with con:      # only this stage's own rows
        if has_people:
            con.execute("UPDATE people SET website = NULL WHERE person IN (SELECT person FROM websites WHERE source LIKE ?)", (MARK + "%",))
        con.execute("DELETE FROM websites WHERE source LIKE ?", (MARK + "%",))
        con.execute("DELETE FROM found_facts")
    n = {"files": 0, "gone": 0, "site": 0, "confirmed": 0, "unverified": 0}
    by = {"born": dict.fromkeys(KINDS, 0), "office": dict.fromkeys(KINDS, 0)}
    review, differs, on_record, facts, sites = [], [], [], [], {}
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        d = json.load(open(path, encoding="utf-8"))
        n["files"] += 1
        checked = str(d.get("verified_on") or "")[:10]
        for c in d.get("candidates") or []:
            race, name = c.get("race_id"), c.get("name")
            rows = con.execute(f"SELECT fec_id FROM candidates WHERE race_id = ? AND name = ? AND election IN ({','.join('?' * len(NOVEMBER))})",
                               (race, name) + NOVEMBER).fetchall()
            if not rows:
                n["gone"] += 1
                continue
            person = rows[0][0] or f"{race}|{name}"
            rec = con.execute("SELECT dob, offices FROM people WHERE person = ?", (person,)).fetchone() if has_people else None
            dob, offices = rec or (None, None)
            w = c.get("website")
            if isinstance(w, dict):
                url = _web(w.get("url"))
                if w.get("verified") is not True or not url:
                    n["unverified"] += 1
                else:
                    had = con.execute("SELECT url, source FROM websites WHERE person = ?", (person,)).fetchone()
                    if had and _host(had[0]) == _host(url):
                        n["confirmed"] += 1
                    elif had:
                        differs.append(f"- {race} | {_line(name)} | our record shows: {had[0]} ({_line(had[1])}) | the sweep found: {url} | {_line(w.get('how'))}")
                    else:
                        sites[person] = (url, f"{MARK} and checked {checked}: {_line(w.get('how'))}")
            b = c.get("born")
            if isinstance(b, dict):
                year, kind, src = b.get("year"), b.get("kind"), _web(b.get("url"))
                if b.get("verified") is not True or kind not in KINDS or not src or not isinstance(year, int) or not 1900 <= year <= 2008:
                    n["unverified"] += 1
                elif dob:
                    on_record.append(f"- {race} | {_line(name)} | birth year {year} | our record already gives a birth date | {src}")
                else:
                    date = b.get("date") if kind in ("official", "campaign") else None      # a full date only from the record or the candidate
                    date = date if isinstance(date, str) and re.fullmatch(rf"{year}-\d\d-\d\d", date) else None
                    facts.append((race, name, "born", year, date, None, None, None, _line(b.get("source")), src, kind, checked))
                    by["born"][kind] += 1
            for o in c.get("offices") or []:
                kind, src, office = o.get("kind"), _web(o.get("url")), _line(o.get("office"))
                if o.get("verified") is not True or kind not in KINDS or not src or not office:
                    n["unverified"] += 1
                elif offices:
                    on_record.append(f"- {race} | {_line(name)} | {office}, {_line(o.get('from')) or 'start not stated'} to {_line(o.get('to')) or 'end not stated'} "
                                     f"({kind}: {_line(o.get('source'))}) | our record already gives offices from official records | {src}")
                else:
                    facts.append((race, name, "office", None, None, office, _year(o.get("from")), _year(o.get("to"), end=True),
                                  _line(o.get("source")), src, kind, checked))
                    by["office"][kind] += 1
            for r in c.get("review") or []:
                if r.get("verified") is True:
                    review.append(f"- {race} | {_line(name)} | our record shows: {_line(r.get('shows'))} | the source says: {_line(r.get('problem'))} | {_line(r.get('url'))}")
    with con:
        con.executemany("INSERT OR REPLACE INTO websites VALUES (?,?,?)", [(p, u, s) for p, (u, s) in sorted(sites.items())])
        con.executemany("INSERT INTO found_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", facts)
        if has_people:
            con.execute("UPDATE people SET website = (SELECT url FROM websites w WHERE w.person = people.person) WHERE website IS NULL")
    n["site"] = len(sites)
    lines = ["# Found on the open web: for a person to read", "",
             "Written by `python run_ballot.py found` from ballot/found/*.json. Nothing on this sheet is loaded into the database or shown on a page.",
             "", f"## Where a source disagrees with our record ({len(review)})", "",
             "race | name | what our record shows | what the source says | address", ""] + review
    lines += ["", f"## A website that differs from the one the state's list or the FEC gives ({len(differs)}; ours is kept)", ""] + differs
    lines += ["", f"## Found, but an official record already covers it ({len(on_record)}; not loaded, since a found fact fills a blank only)", ""] + on_record
    open(REVIEW if folder == DIR else os.path.join(folder, "REVIEW.md"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    kinds = lambda f: ", ".join(f"{by[f][k]} {k}" for k in KINDS)
    say(f"    Found on the open web ({n['files']} files): {n['site']} websites added, {n['confirmed']} confirmed one already given, {len(differs)} differ (ours kept); "
        f"{sum(by['born'].values())} birth years ({kinds('born')}); {sum(by['office'].values())} offices ({kinds('office')}); "
        f"{len(on_record)} left out where an official record already speaks; {n['gone']} candidates no longer on a November list; "
        f"{n['unverified']} findings not verified or malformed; {len(review)} review items written to ballot/found/REVIEW.md")
    return {"websites": n["site"], "born": by["born"], "office": by["office"], "review": len(review), "gone": n["gone"]}
