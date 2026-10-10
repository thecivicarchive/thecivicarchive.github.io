"""
election/registry.py - every state's results source for Election Night, one file a state in election/registry/<code>.json.

    python -m election.registry check      the checks (every state present and valid; no state marked live that a scout
                                           found blocked; every state has a results page to link to); exit 1 on failure
    python -m election.registry summary    one line a state: status, reader, Nov 3 id, certification
    python -m election.registry never      every host no program may request, with the reason

It reads the registry files (and, for the checks, the scouts' files in election/scout/) and writes nothing. It makes no
request of any kind.

A registry file (written 2026-10-10 from the scouts' files of 2026-10-09; each phase 3 reader agent then owns its
states' files) holds:
  code, name, status         status: live (a program may read the state's own feed), care (readable with conditions),
                             hand (John saves the files), link (the page links to the state's own results)
  status_why, approved, approval_note
  office                     who posts the figures, for "As reported by <office>"
  family, reader_agent       election/readers/<family>.py, and the agent that writes it
  results_page               {url, label, checked, source}: the state's own results page; every state has one
  other_pages                more of the state's or its counties' own pages, to link
  election                   {id, kind, date, nov3_id, posted, how_to_find}
  cadence                    {check_every_s, signal (the cheap "what's new" address), data_on_change, from, hosts (every
                             host the reader will request)}; null for a link state
  hand                       {folder, files, how} for a hand state
  feeds                      the scouts' feeds, each with its hosts and whether it answered a script (script_ok)
  units, precinct_level, races_in_feed, local
  how_counted                one plain sentence for the page: how the state counts
  count_order, vote_types    for the model's count-order blind spot
  decision                   {default, rules: [{applies, rule, note}]}: plurality, top_two, majority_runoff,
                             open_primary, ranked_choice, majority_or_legislature
  ranked_choice              false, or what the page says about first choices
  certify                    {body, rule, date (YYYY-MM-DD or null), date_kind (by, on, from, meets_by, meets_on, null),
                             local_rule, source, confirm (only when the body's name or date is not in the source read)}
  condition                  for a care state: the condition it is read under
  never, never_why           hosts no program may ever request for this state (source.py refuses them before asking)
  partial_sources, rehearsal, terms, scout_blocked, scout_plan, notes, to_do, sources
"""

import datetime as dt
import fnmatch
import glob
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REG_DIR = os.path.join(HERE, "registry")
SCOUT_DIR = os.path.join(HERE, "scout")

STATES = {
    "AK": "Alaska", "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DC": "District of Columbia", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "IA": "Iowa", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "MA": "Massachusetts", "MD": "Maryland", "ME": "Maine", "MI": "Michigan", "MN": "Minnesota",
    "MO": "Missouri", "MS": "Mississippi", "MT": "Montana", "NC": "North Carolina", "ND": "North Dakota",
    "NE": "Nebraska", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NV": "Nevada", "NY": "New York",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VA": "Virginia", "VT": "Vermont",
    "WA": "Washington", "WI": "Wisconsin", "WV": "West Virginia", "WY": "Wyoming",
}
# Minnesota's file is written by N1 (election/registry/mn.json) and checked here more lightly.
OWN_FILE_ELSEWHERE = {"MN"}

STATUSES = ("live", "care", "hand", "link")
MONTHS = ("Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.")
RULES = ("plurality", "top_two", "majority_runoff", "open_primary", "ranked_choice", "majority_or_legislature")
DATE_KINDS = ("by", "on", "from", "meets_by", "meets_on", None)
CERT_VERBS = {"by": "certifies the results by %s", "on": "certifies the results on %s",
              "from": "certifies the results no earlier than %s", "meets_by": "meets to certify the results by %s",
              "meets_on": "meets to certify the results on %s"}

# Hosts no program ever asks, whatever the state (ARCHITECTURE.md 3.4; CLAUDE.md). A pattern "*.x" also matches x.
GLOBAL_NEVER = {
    "sos.mn.gov": "Minnesota Secretary of State: shows this computer a CAPTCHA; John saves its files by hand",
    "*.sos.mn.gov": "Minnesota Secretary of State: results, results files, candidates, main site, poll finder",
    "vrsws.sos.ky.gov": "Kentucky State Board of Elections: its Acceptable Use Policy limits scraping",
    "api.gdeltproject.org": "GDELT's search API answered this machine 429; the raw 15-minute files are used instead",
}

REQUIRED = {
    "code": str, "name": str, "status": str, "status_why": str, "approved": bool, "office": str,
    "results_page": dict, "election": dict, "feeds": list, "how_counted": str, "decision": dict, "certify": dict,
    "never": list, "never_why": dict, "to_do": list,
}


# ---------------------------------------------------------------- loading

def path_for(code):
    return os.path.join(REG_DIR, code.lower() + ".json")


def load(code):
    """One state's registry entry, or None when its file is not written yet."""
    p = path_for(code)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def load_all():
    """{code: entry} for every registry file present."""
    out = {}
    for code in STATES:
        e = load(code)
        if e is not None:
            out[code] = e
    return out


def codes(status=None):
    """Codes whose file is present, optionally only those with one status (live, care, hand, link)."""
    return sorted(c for c, e in load_all().items() if status is None or e.get("status") == status)


# ---------------------------------------------------------------- hosts never asked

def host_of(url):
    u = url if "://" in url else "https://" + url
    h = (urllib.parse.urlsplit(u).hostname or "").lower().rstrip(".")
    return h


def _matches(host, pattern):
    pattern = pattern.lower()
    if pattern.startswith("*."):
        return host == pattern[2:] or fnmatch.fnmatchcase(host, pattern)
    return host == pattern


def never_hosts(code=None):
    """{pattern: reason}: the global list plus one state's list (or every state's when code is None)."""
    out = dict(GLOBAL_NEVER)
    entries = [load(code)] if code else list(load_all().values())
    for e in entries:
        if not e:
            continue
        for pat in e.get("never", []):
            out.setdefault(pat.lower(), "%s: %s" % (e.get("code"), e.get("never_why", {}).get(pat, "on its never list")))
    return out


def refused(url, code=None):
    """The reason a URL must never be requested, or None. Checks every state's list, not only the one named, so a host
    blocked for one state is never asked on behalf of another."""
    host = host_of(url)
    if not host:
        return "no host in the address"
    for pat, why in never_hosts(None).items():
        if _matches(host, pat):
            return why
    return None


# ---------------------------------------------------------------- words for pages

def certify_words(entry):
    """'the Georgia Secretary of State certifies the results by Nov. 20' (no date: 'certifies the results later')."""
    c = entry.get("certify") or {}
    body = c.get("body") or "the state"
    d = c.get("date")
    if not d:
        return "%s certifies the results after the canvass" % body
    day = dt.date.fromisoformat(d)
    when = "%s %d" % (MONTHS[day.month - 1], day.day)
    return "%s %s" % (body, CERT_VERBS.get(c.get("date_kind"), CERT_VERBS["on"]) % when)


def status_words(entry):
    s = entry.get("status")
    return {"live": "read live from the state's own results",
            "care": "read from the state's own results where its site allows",
            "hand": "copied from files saved from the state's own site",
            "link": "not read here: the state's own results are linked"}.get(s, "")


# ---------------------------------------------------------------- checks

def _scout():
    out = {}
    for f in sorted(glob.glob(os.path.join(SCOUT_DIR, "results_*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.items():
            if k != "_about":
                out[k] = (os.path.basename(f), v)
    return out


def _hosts_in(text):
    return [re.sub(r":\d+$", "", h.lower()) for h in re.findall(r"https?://([^/\s'\"),]+)", text or "")]


def validate(entry, light=False):
    """Problems with one entry, as plain sentences ([] when it is valid). light: only what source.py and the pages need
    (used for Minnesota, whose file another agent writes)."""
    p = []
    code = entry.get("code")
    need = ("code", "status", "results_page", "never") if light else REQUIRED
    for k in need:
        typ = REQUIRED[k]
        if k not in entry:
            p.append("%s: missing %s" % (code, k))
        elif not isinstance(entry[k], typ):
            p.append("%s: %s should be %s" % (code, k, typ.__name__))
    if p:
        return p
    if code not in STATES:
        p.append("%s: not a state code" % code)
    if entry["status"] not in STATUSES:
        p.append("%s: status %r is not one of %s" % (code, entry["status"], ", ".join(STATUSES)))
    rp = entry["results_page"]
    url = rp.get("url", "") if isinstance(rp, dict) else ""
    if not re.match(r"^https://[^\s/]+\.[a-z]{2,}(/|$)", url or ""):
        p.append("%s: results page %r is not an https address" % (code, url))
    for pat in entry["never"]:
        if not re.match(r"^(\*\.)?[a-z0-9.-]+\.[a-z]{2,}$", pat):
            p.append("%s: never-list entry %r is not a host pattern" % (code, pat))
    if light:
        return p
    if entry["name"] != STATES.get(code):
        p.append("%s: name %r should be %r" % (code, entry["name"], STATES.get(code)))
    for pat in entry["never"]:
        if pat not in entry["never_why"]:
            p.append("%s: no reason given for never-list entry %s" % (code, pat))
    if not isinstance(rp.get("label"), str) or not rp.get("label"):
        p.append("%s: results page has no label" % code)
    s = entry["status"]
    cad = entry.get("cadence")
    if s in ("live", "care"):
        if not entry.get("family"):
            p.append("%s: %s but no reader family" % (code, s))
        if not isinstance(cad, dict) or not cad.get("hosts") or not cad.get("check_every_s"):
            p.append("%s: %s but no cadence with hosts and an interval" % (code, s))
        elif cad["check_every_s"] < 60:
            p.append("%s: checks a state's site more often than once a minute" % code)
    if s == "care" and not entry.get("condition"):
        p.append("%s: care state without the condition it is read under" % code)
    if s == "hand":
        h = entry.get("hand") or {}
        if not h.get("folder") or not h.get("files"):
            p.append("%s: hand state without a folder and files" % code)
    if s == "link" and isinstance(cad, dict) and cad.get("hosts"):
        p.append("%s: link state that would request %s" % (code, cad["hosts"]))
    if not entry["approved"] and s in ("live", "care", "hand"):
        p.append("%s: not approved but status %s" % (code, s))
    d = entry["decision"]
    if d.get("default") not in RULES:
        p.append("%s: decision rule %r unknown" % (code, d.get("default")))
    for r in d.get("rules", []):
        if r.get("rule") not in RULES or not r.get("applies"):
            p.append("%s: decision rule entry %r incomplete" % (code, r))
    c = entry["certify"]
    if not c.get("body") or not c.get("rule") or not c.get("source"):
        p.append("%s: certification body, rule or source missing" % code)
    if c.get("date_kind") not in DATE_KINDS:
        p.append("%s: certification date kind %r unknown" % (code, c.get("date_kind")))
    if c.get("date"):
        try:
            day = dt.date.fromisoformat(c["date"])
            if not dt.date(2026, 11, 4) <= day <= dt.date(2027, 1, 31):
                p.append("%s: certification date %s outside Nov 4 to Jan 31" % (code, day))
        except ValueError:
            p.append("%s: certification date %r is not YYYY-MM-DD" % (code, c["date"]))
        if not c.get("date_kind"):
            p.append("%s: certification date without a kind (by, on, from)" % code)
    if not entry["how_counted"].strip().endswith("."):
        p.append("%s: how_counted should be a sentence" % code)
    if re.search(r"\b\w+\.(py|json|sqlite|bat|ps1)\b", entry["how_counted"] + " " + entry["office"]):
        p.append("%s: a file name in words meant for a page" % code)
    for f in entry["feeds"]:
        for k in ("id", "what", "address", "script_ok", "checked"):
            if k not in f:
                p.append("%s: feed %s lacks %s" % (code, f.get("id"), k))
    return p


def live_problems(e, sv):
    """Check 2 for one entry against its scout entry sv: a live or care reader asks only hosts the scout saw answer a
    script (care may rest on a stated condition instead), never a host on any never list; a live state needs at least
    one statewide or congressional feed that answered a script."""
    p = []
    code, s = e.get("code"), e.get("status")
    if s not in ("live", "care"):
        return p
    ok_hosts = set()
    for fe in sv.get("feeds", []):
        if fe.get("script_ok") is True:
            ok_hosts.update(_hosts_in(fe.get("address_pattern")))
    for h in (e.get("cadence") or {}).get("hosts", []):
        why = refused("https://%s/" % h)
        if why:
            p.append("%s: reader would ask %s, which is never asked (%s)" % (code, h, why))
        if s == "live" and h not in ok_hosts:
            p.append("%s: marked live but no scout feed on %s answered a script" % (code, h))
        elif s == "care" and h not in ok_hosts and not e.get("condition"):
            p.append("%s: marked care but no scout feed on %s answered a script, and no condition is noted" % (code, h))
    if s == "live" and not any(fe.get("script_ok") is True and fe.get("what") in ("statewide", "congress")
                               for fe in sv.get("feeds", [])):
        p.append("%s: marked live but no statewide or congressional feed answered a script" % code)
    return p


def run_checks(say=print):
    """Runs every check; returns the number of failures."""
    fails = []
    notes = []
    entries = load_all()
    scout = _scout()

    # 1. every state present and valid
    for code in sorted(STATES):
        e = entries.get(code)
        if code in OWN_FILE_ELSEWHERE:
            if e is None:
                notes.append("%s: registry file not written yet (another agent's file)" % code)
            else:
                for prob in validate(e, light=True):
                    notes.append("%s (another agent's file): %s" % (code, prob))
            continue
        if e is None:
            fails.append("%s: no registry file" % code)
            continue
        if e.get("code") != code:
            fails.append("%s: file holds code %r" % (code, e.get("code")))
        fails.extend(validate(e))
    say("check 1, every state present and valid: %d of %d files, %s" % (
        len([c for c in STATES if c in entries]), len(STATES),
        "PASS" if not fails else "FAIL (%d)" % len(fails)))
    n1 = len(fails)

    # 2. no state marked live that a scout found blocked
    for code, e in sorted(entries.items()):
        if code in OWN_FILE_ELSEWHERE:
            continue
        fails.extend(live_problems(e, scout.get(code, (None, {}))[1]))
    say("check 2, no state marked live that a scout found blocked: %s" % (
        "PASS" if len(fails) == n1 else "FAIL (%d)" % (len(fails) - n1)))
    n2 = len(fails)

    # 3. every state has a results page to link to (and it is not a page the pages would be wrong to send readers to)
    for code in sorted(STATES):
        e = entries.get(code)
        if e is None:
            if code not in OWN_FILE_ELSEWHERE:
                fails.append("%s: no results page (no file)" % code)
            continue
        url = (e.get("results_page") or {}).get("url") or ""
        if not url.startswith("https://"):
            fails.append("%s: no https results page" % code)
    say("check 3, every state has a results page to link to: %s" % (
        "PASS" if len(fails) == n2 else "FAIL (%d)" % (len(fails) - n2)))

    for f in fails:
        say("  FAIL " + f)
    for n in notes:
        say("  note " + n)
    tally = {}
    for code, e in entries.items():
        tally.setdefault(e.get("status"), []).append(code)
    say("statuses: " + "; ".join("%s %d (%s)" % (s, len(tally.get(s, [])), " ".join(sorted(tally.get(s, []))))
                                 for s in STATUSES))
    return len(fails)


def selftest(say=print):
    """No network. The never list refuses what it must and nothing it must not; the checks catch planted faults."""
    bad = 0
    must_refuse = ["https://electionresults.sos.mn.gov/results/Index?ErsElectionId=170", "http://sos.mn.gov/",
                   "https://electionresultsfiles.sos.mn.gov/x.txt", "https://pollfinder.sos.mn.gov/",
                   "https://vrsws.sos.ky.gov/liveresults/?id=112", "https://cdn1.arizona.vote/data/47/0/x.json",
                   "https://results.arizona.vote/", "https://results.okelections.us/OKER/?elecDate=20261103",
                   "https://enr.sos.mo.gov/", "https://liveresults.ohiosos.gov/", "https://WWW.SOS.NH.GOV/x",
                   "https://api.gdeltproject.org/api/v2/doc/doc?query=x", "https://elections.wi.gov/x"]
    must_allow = ["https://electionresults.iowa.gov/IA/elections.json", "https://api.sos.ca.gov/returns/status",
                  "https://results.enr.clarityelections.com/CO/122598/current_ver.txt", "https://er.ncsbe.gov/",
                  "https://data.gdeltproject.org/gdeltv2/lastupdate.txt", "https://www.sos.mo.gov/elections/results",
                  "https://sos.ks.gov/elections/election-results.html", "https://notsos.mn.gov.example.com/",
                  "https://electionresults.ri.gov/results/public/api/jurisdictions/RhodeIsland"]
    for u in must_refuse:
        if not refused(u):
            say("  FAIL not refused: " + u)
            bad += 1
    for u in must_allow:
        if refused(u):
            say("  FAIL refused: %s (%s)" % (u, refused(u)))
            bad += 1
    ia = load("IA")
    if ia:
        if validate(dict(ia, status="sometimes")) == []:
            say("  FAIL an unknown status passed validation")
            bad += 1
        if validate(dict(ia, results_page={"url": "http://x", "label": "x"})) == []:
            say("  FAIL a non-https results page passed validation")
            bad += 1
        if validate(dict(ia, cadence=dict(ia["cadence"], check_every_s=10))) == []:
            say("  FAIL a 10-second interval passed validation")
            bad += 1
        if not live_problems(dict(ia, cadence=dict(ia["cadence"], hosts=["elections.wi.gov"])), {}):
            say("  FAIL a live reader asking a walled host passed check 2")
            bad += 1
        wi = load("WI")
        if wi and not live_problems(dict(wi, status="live", cadence={"check_every_s": 120, "hosts": [
                "elections.wi.gov"]}), _scout().get("WI", (None, {}))[1]):
            say("  FAIL Wisconsin marked live passed check 2")
            bad += 1
    say("selftest: %s" % ("PASS" if not bad else "FAIL (%d)" % bad))
    return bad


def summary(say=print):
    for code, e in sorted(load_all().items()):
        c = e.get("certify") or {}
        say("%s %-5s %-16s nov3=%-28s cert=%s %s" % (
            code, e.get("status"), e.get("family") or "-", str((e.get("election") or {}).get("nov3_id"))[:28],
            c.get("date_kind") or "-", c.get("date") or "-"))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "check":
        return 1 if (selftest() + run_checks()) else 0
    if cmd == "selftest":
        return 1 if selftest() else 0
    if cmd == "summary":
        summary()
        return 0
    if cmd == "never":
        for pat, why in sorted(never_hosts().items()):
            print("%-32s %s" % (pat, why))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
