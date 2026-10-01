"""
ballot/scan_local_privacy.py - a last look for contact details where the county and local ballot work keeps things:
the local caches (ballot_cache/<code>/local/), the local ballot database, and the built ballot pages.

    python -m ballot.scan_local_privacy [codes ...]        (no codes: every state with a local cache or local rows)

It prints counts and file or row ids only, never the text that matched. In a cache it looks for e-mail addresses and
phone numbers anywhere, and for the names of contact columns (address, phone, e-mail, zip, website) used as keys or
headings; a raw PDF or workbook kept whole is listed so a person can confirm it has no contact columns. Street-like
text is counted apart, because office titles and place names trip it ("District 3 Court").
"""

import collections
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(HERE, "ballot_cache")
DB = os.path.join(HERE, "ballot_local_2026.sqlite")
SITE = os.path.join(HERE, "site", "dev", "ballot")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b")
STREET = re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9.' -]{1,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Hwy|Highway)\b\.?", re.I)
POBOX = re.compile(r"\bP\.?\s?O\.?\s+Box\b", re.I)
KEY = re.compile(r"\"[^\"]{0,30}(address|phone|e-?mail|zip|website|mailing|residence)[^\"]{0,30}\"\s*:", re.I)
TEXT_EXT = (".json", ".csv", ".txt", ".tsv", ".htm", ".html", ".xml", ".md")


def scan_text(t):
    return {"email": len(EMAIL.findall(t)), "phone": len(PHONE.findall(t)), "zip": len(ZIP.findall(t)), "po box": len(POBOX.findall(t)),
            "street-like": len(STREET.findall(t)), "contact key": len(KEY.findall(t))}


def scan_caches(codes, say):
    bad = 0
    for code in codes:
        root = os.path.join(CACHE, code, "local")
        if not os.path.isdir(root):
            continue
        files, raw = 0, []
        for d, _dirs, names in os.walk(root):
            for n in names:
                p = os.path.join(d, n)
                files += 1
                if not n.lower().endswith(TEXT_EXT):
                    raw.append(os.path.relpath(p, root))
                    continue
                hits = {k: v for k, v in scan_text(open(p, encoding="utf-8", errors="replace").read()).items() if v}
                hard = {k: v for k, v in hits.items() if k != "street-like"}
                if hits:
                    say(f"    {code} cache {os.path.relpath(p, root)}: " + ", ".join(f"{k} {v}" for k, v in hits.items()))
                bad += bool(hard)
        say(f"    {code}: {files} cached file(s); kept whole (not text): {', '.join(raw) if raw else 'none'}")
    return bad


def scan_db(codes, say):
    if not os.path.exists(DB):
        return 0
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    bad = 0
    for code in codes:
        ST = code.upper()
        tally = collections.Counter()
        for rid, *cells in con.execute("SELECT c.race_id, c.name, c.party, c.note FROM sl_candidates c JOIN sl_races r USING (race_id) WHERE r.state = ?", (ST,)):
            for v in cells:
                if v:
                    for k, n in scan_text(str(v)).items():
                        if n and k != "contact key":
                            tally["candidates " + k] += 1
        for rid, *cells in con.execute("SELECT race_id, office, jurisdiction, district, seat FROM sl_races WHERE state = ?", (ST,)):
            for v in cells:
                if v:
                    for k, n in scan_text(str(v)).items():
                        if n and k != "contact key":
                            tally["races " + k] += 1
        if tally:
            say(f"    {code} database: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
            bad += sum(v for k, v in tally.items() if "street-like" not in k)
    con.close()
    return bad


def scan_site(codes, say):
    bad = 0
    for code in codes:
        root = os.path.join(SITE, code)
        if not os.path.isdir(root):
            continue
        tally = collections.Counter()
        for d, _dirs, names in os.walk(root):
            for n in names:
                if n.endswith(".json") and n != "districts.json":
                    t = open(os.path.join(d, n), encoding="utf-8", errors="replace").read()
                    tally["email"] += len(EMAIL.findall(t))
                    tally["phone"] += len(PHONE.findall(t))
                    tally["po box"] += len(POBOX.findall(t))
        hits = {k: v for k, v in tally.items() if v}
        if hits:
            say(f"    {code} built page data: " + ", ".join(f"{k} {v}" for k, v in hits.items()))
            bad += 1
    return bad


def main(argv=None, say=print):
    codes = [c.lower() for c in (argv if argv is not None else sys.argv[1:])]
    if not codes:
        codes = sorted(c for c in os.listdir(CACHE) if os.path.isdir(os.path.join(CACHE, c, "local")))
    say(f"== privacy scan of the county and local ballot work: {' '.join(codes)}")
    bad = scan_caches(codes, say) + scan_db(codes, say) + scan_site(codes, say)
    say("    nothing that looks like an e-mail address, a phone number, a ZIP code or a contact column" if not bad
        else f"    {bad} place(s) to look at (listed above)")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
