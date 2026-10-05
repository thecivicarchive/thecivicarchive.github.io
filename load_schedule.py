#!/usr/bin/env python3
"""
load_schedule.py - what Congress has said it will take up on the floor (John, 2026-10-05: "identify if there's
projected voting that will go on soon"). Only the chambers' own published schedules; nothing is predicted.

    python load_schedule.py [--out floor_schedule.json]

The House: the weekly floor schedule the Majority Leader and the Committee on Rules post at docs.house.gov/floor/
("Bills for the week"), read from its own XML file (docs.house.gov/floor/Download.aspx?file=/billsthisweek/<date>/
<date>.xml): every item still on the list, its number and the words the schedule uses. The Senate: the next meeting as
its own floor schedule page states it (senate.gov/legislative/schedule/floor_schedule.htm). Senate cloture motions,
which put a vote on the calendar within days, and bills placed on a House or Senate calendar come from the bills'
own actions when the page is built (build_site_dev.py), not from here.

Writes floor_schedule.json next to this script. Public domain records; one request at a time; an honest User-Agent.
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "PlainCongress/1.0 (personal legislative research; contact via github.com/thecivicarchive)"}
HOUSE_PAGE = "https://docs.house.gov/floor/"
HOUSE_XML = "https://docs.house.gov/floor/Download.aspx?file=/billsthisweek/{d}/{d}.xml"
SENATE_PAGE = "https://www.senate.gov/legislative/schedule/floor_schedule.htm"
TYPES = {"H.R.": "hr", "S.": "s", "H.J.Res.": "hjres", "S.J.Res.": "sjres", "H.Con.Res.": "hconres", "S.Con.Res.": "sconres",
         "H.Res.": "hres", "S.Res.": "sres"}


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def get(url, tries=10):
    """One request, asked again patiently when the router loses the address lookup (it drops one in three here)."""
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), context=_ctx(), timeout=40) as r:
                return r.read()
        except urllib.error.URLError as e:
            if i < tries - 1 and ("getaddrinfo" in str(e) or "timed out" in str(e)):
                time.sleep(4 + 3 * i)
                continue
            raise


def bill_key(num, congress):
    """'H.R. 309' -> 'hr309-119'."""
    m = re.match(r"^\s*((?:H|S)\.(?:(?:J|Con)\.)?(?:R\.|Res\.)?)\s*(\d+)\s*$", num.replace("H. R.", "H.R."))
    if not m:
        return ""
    t = TYPES.get(m.group(1))
    return f"{t}{m.group(2)}-{congress}" if t else ""


def house():
    page = get(HOUSE_PAGE).decode("utf-8", "replace")
    weeks = sorted(set(re.findall(r"billsthisweek/(\d{8})/\1\.xml", page)))
    if not weeks:
        return {"error": "the House page named no weekly schedule file", "url": HOUSE_PAGE}
    d = weeks[-1]
    url = HOUSE_XML.format(d=d)
    root = ET.fromstring(get(url))
    congress = root.get("congress-num") or "119"
    items, seen = [], set()
    for it in root.iter("floor-item"):
        if (it.get("remove-date") or "").strip():
            continue      # taken off the schedule
        num = re.sub(r"\s+", " ", (it.findtext("legis-num") or "")).strip()
        words = re.sub(r"\s+", " ", (it.findtext("floor-text") or "")).strip()
        if not num or num in seen:
            continue
        seen.add(num)
        items.append({"num": num, "words": words, "key": bill_key(num, congress)})
    return {"week": root.get("week-date") or f"{d[:4]}-{d[4:6]}-{d[6:]}", "updated": (root.get("update-date") or "")[:10],
            "items": items, "url": HOUSE_PAGE, "file": url}


def senate():
    page = get(SENATE_PAGE).decode("utf-8", "replace")
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S)))
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), [A-Z][a-z]{2} \d{1,2}, \d{4})\s+(.*?)\s+(?:Floor Webcast|Senate Calendar)", text)
    if not m:
        return {"error": "the Senate page's next meeting could not be read", "url": SENATE_PAGE}
    return {"day": m.group(1), "line": m.group(2).strip()[:300], "url": SENATE_PAGE}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "floor_schedule.json"))
    a = ap.parse_args()
    try:      # the kit's patient address lookups (asks again, and for an IPv4 address, before calling a lookup a failure)
        sys.path.insert(0, HERE)
        from states.net import patient_lookups
        patient_lookups()
    except Exception:
        pass
    out = {"fetched": dt.datetime.now().isoformat(timespec="seconds")}
    for name, fn in (("house", house), ("senate", senate)):
        try:
            out[name] = fn()
        except Exception as e:      # a chamber that cannot be read is said so on the page; the other still shows
            out[name] = {"error": f"{type(e).__name__}: {e}"[:200]}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    h, s = out["house"], out["senate"]
    print(f"Floor schedule: House week of {h.get('week', '?')} ({len(h.get('items', []))} items, updated {h.get('updated', '?')})"
          f"{' - ' + h['error'] if h.get('error') else ''}; Senate: {s.get('day', '?')}: {s.get('line', s.get('error', ''))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
