"""election/feeds/accounts.py - the official social accounts whose posts the feed may show, each with two anchors.

    python -m election.feeds.accounts discover [--limit N] [--only outlets|offices|candidates]
                                          read each official website once, politely, and keep the Bluesky, Mastodon
                                          and YouTube accounts it links AND that point back to it (resumable)
    python -m election.feeds.accounts check     the checks: every account has two anchors and a date; nothing about
                                                anyone else is stored; posts stay unshown until the contact address
                                                exists; exit 1 on failure
    python -m election.feeds.accounts summary   counts by platform and owner

Who may be shown (ARCHITECTURE.md 4.5; John's rule of 2026-10-09): newsrooms, election offices and candidates'
official accounts, and only when two anchors tie the account to the organization or campaign:
  1. the organization's own website (an address already in the kit's tables: the outlets' home pages, the state
     election offices' sites, the campaign websites in the ballot databases) links to the account; and
  2. the account points back: a Bluesky handle that is the site's own domain (or under it), or a profile that names
     the domain; a Mastodon profile field for the domain carrying Mastodon's own verified mark (verified_at, its
     two-way link check); a YouTube channel whose own page links or names the domain.
Nothing is guessed from names. An account that fails either anchor is not stored at all (not even its handle); only
counts of what was set aside are kept, per site.

State and local candidates: only for the offices whose campaign websites RULES.md lets the pages show in full
(statewide offices, the Legislature, judges, county offices, mayors and councils, school boards); township, soil and
water, hospital and other small district candidates are not read here.

Shown or not: no post is shown until John has chosen the site's public contact address (decision D8; Bluesky's
developer guidelines ask for one). Until then `posts_may_be_shown()` is False and the feed shows headlines and counts.

Requests go through election/source.py (the kit's honest User-Agent, one at a time, at least a second apart, two for
state sites; the never lists; a 403, 429 or challenge stops that host). This module keeps its own list of stopped
hosts (election_cache/feeds/stopped_hosts.json), so that a campaign site's refusal never touches the results updater's.
Pages are read for their links only and are not kept. Progress is kept in election_cache/feeds/accounts_progress.json
(per site: when, the answer, and counts; never a handle that was set aside).
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from urllib.parse import quote, unquote, urlsplit

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election.feeds import CACHE, connect, ro  # noqa: E402
from election.feeds.outlets import registered_domain  # noqa: E402

BALLOT = os.path.join(HERE, "ballot_2026.sqlite")
LOCAL = os.path.join(HERE, "ballot_local_2026.sqlite")
PROGRESS = os.path.join(CACHE, "accounts_progress.json")
STOPPED = os.path.join(CACHE, "stopped_hosts.json")

# John's decision D8: the site's public contact address. None until he has created it and said so; then the main
# session writes it here, and only then may an official post be shown.
CONTACT_ADDRESS = None


def posts_may_be_shown():
    """False until the site has a public contact address that someone reads (Bluesky's guidelines; John's D8)."""
    return bool(CONTACT_ADDRESS)


# The state election offices' own sites, each host taken from the kit's own tables (ballot_sources, sl_sources and
# election/registry/<code>.json). Portal hosts that speak for a whole state government (portal.ct.gov, www.in.gov,
# www.maine.gov, www.nj.gov, oklahoma.gov) are left out: their accounts are the state's, not the election office's.
# Results and data hosts are left out too. Hosts on a never list (Minnesota's, New York's, Rhode Island's ...) are
# refused by source.py before any request.
OFFICES = {
    "AK": ("Alaska Division of Elections", "https://www.elections.alaska.gov/"),
    "AL": ("Alabama Secretary of State", "https://www.sos.alabama.gov/"),
    "AR": ("Arkansas Secretary of State", "https://www.sos.arkansas.gov/"),
    "CO": ("Colorado Secretary of State", "https://www.coloradosos.gov/"),
    "DE": ("Delaware Department of Elections", "https://elections.delaware.gov/"),
    "FL": ("Florida Division of Elections", "https://dos.elections.myflorida.com/"),
    "HI": ("Hawaii Office of Elections", "https://elections.hawaii.gov/"),
    "IA": ("Iowa Secretary of State", "https://sos.iowa.gov/"),
    "ID": ("Idaho Secretary of State", "https://voteidaho.gov/"),
    "IL": ("Illinois State Board of Elections", "https://www.elections.il.gov/"),
    "KS": ("Kansas Secretary of State", "https://sos.ks.gov/"),
    "KY": ("Kentucky State Board of Elections", "https://elect.ky.gov/"),
    "MD": ("Maryland State Board of Elections", "https://elections.maryland.gov/"),
    "MO": ("Missouri Secretary of State", "https://www.sos.mo.gov/"),
    "MS": ("Mississippi Secretary of State", "https://www.sos.ms.gov/"),
    "MT": ("Montana Secretary of State", "https://sosmt.gov/"),
    "NE": ("Nebraska Secretary of State", "https://sos.nebraska.gov/"),
    "TX": ("Texas Secretary of State", "https://www.sos.texas.gov/"),
    "UT": ("Utah Lieutenant Governor's Office of Elections", "https://vote.utah.gov/"),
    "VA": ("Virginia Department of Elections", "https://www.elections.virginia.gov/"),
    "WA": ("Washington Secretary of State", "https://www.sos.wa.gov/"),
    "WY": ("Wyoming Secretary of State", "https://sos.wyo.gov/"),
}

LOCAL_LEVELS = ("statewide", "legislature", "court", "county", "city", "school")
LOCAL_KINDS_LEFT_OUT = {"county_park", "county_surveyor"}   # small boards inside the county level

# Hosts that use /@name addresses but are not Mastodon servers (and networks the feed does not read).
NOT_MASTODON = re.compile(r"(^|\.)(tiktok|threads|medium|youtube|instagram|x|twitter|facebook|linktr|linkedin|substack|"
                          r"truthsocial|gettr|parler|rumble|spotify|apple|venmo|cash|flickr|pinterest|soundcloud|vimeo|"
                          r"twitch|reddit|snapchat|bsky|google|mailchimp|eventbrite|actblue|winred|ngpvan|"
                          r"anedot|squarespace|wixsite|wordpress|github|patreon|paypal|gofundme|nextdoor)\.[a-z.]+$")
KNOWN_MASTODON = {"mastodon.social", "mastodon.online", "mastodon.world", "mas.to", "universeodon.com", "journa.host",
                  "newsie.social", "mstdn.social", "hachyderm.io", "mastodon.sdf.org", "infosec.exchange",
                  "masto.ai", "toot.community", "fosstodon.org", "sfba.social", "c.im", "mstdn.party",
                  "kolektiva.social", "zirk.us", "techhub.social", "mastodon.nz", "social.coop", "federate.social",
                  "mastodon.lol", "indieweb.social", "historians.social", "vmst.io", "beige.party", "baraag.net"}

TAG = re.compile(r"<(a|link)\b([^>]*)>", re.I)
HREF = re.compile(r"""\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I)
REL_ME = re.compile(r"""\brel\s*=\s*["']?[^"'>]*\bme\b""", re.I)
BSKY = re.compile(r"^https?://(?:www\.)?bsky\.app/profile/([A-Za-z0-9._:%-]+)/?(?:[?#].*)?$", re.I)
YT = re.compile(r"^https?://(?:www\.|m\.)?youtube\.com/(?:(channel)/(UC[\w-]{22})|(@)([\w.%-]+)|(c)/([\w.%-]+)|"
                r"(user)/([\w.%-]+))/?(?:[?#].*)?$", re.I)
MASTO = re.compile(r"^https?://([a-z0-9.-]+\.[a-z]{2,})/@([A-Za-z0-9_]{1,30})/?(?:[?#].*)?$", re.I)

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  account_id TEXT PRIMARY KEY,     -- platform:platform_id
  platform TEXT NOT NULL,          -- bluesky, mastodon, youtube
  account TEXT NOT NULL,           -- the handle (bluesky), user@server (mastodon), or the channel's @name or id
  platform_id TEXT NOT NULL,       -- the DID, the server's account id, the UC... channel id
  owner_kind TEXT NOT NULL,        -- newsroom, election office, candidate
  owner TEXT NOT NULL,             -- the outlet, the office, or the candidate's name as filed
  owner_ref TEXT,                  -- outlet key, state code, or race_id|name
  state TEXT,                      -- two letters, or US
  race_id TEXT,                    -- the candidate's race
  site TEXT NOT NULL,              -- the official website (anchor 1's site)
  linked_from TEXT NOT NULL,       -- the page that links the account
  link_kind TEXT,                  -- "a link on the page" or "rel=me link"
  proof TEXT NOT NULL,             -- how the account points back (anchor 2)
  feed TEXT,                       -- what a collector reads: the DID for Bluesky's stream, the channel's RSS address
  checked_on TEXT NOT NULL,        -- the date both anchors were checked
  active INTEGER NOT NULL DEFAULT 1,
  shown INTEGER NOT NULL DEFAULT 0 -- 0 until John's contact address exists (D8); then the feed page may show posts
);
CREATE TABLE IF NOT EXISTS account_sites (
  site TEXT PRIMARY KEY, owner_kind TEXT, owner TEXT, owner_ref TEXT, state TEXT, race_id TEXT, checked TEXT,
  answer TEXT,                     -- ok, refused (403, 429, a challenge), failed (no answer), not asked (a never list)
  bluesky_links INTEGER, mastodon_links INTEGER, youtube_links INTEGER,
  verified INTEGER, set_aside INTEGER, note TEXT
);
"""


# ---------------------------------------------------------------------------------------------------- the sites

def sites(only=None):
    """[{site, owner_kind, owner, owner_ref, state, race_id, small}] from the kit's own tables. Nothing invented."""
    out = []
    if only in (None, "outlets"):
        con = connect()
        seen = set()
        for name, key, state, home in con.execute(
                "SELECT name, outlet_key, home_state, home FROM outlets WHERE home IS NOT NULL ORDER BY home_state, name"):
            if home in seen:
                continue
            seen.add(home)
            out.append({"site": home, "owner_kind": "newsroom", "owner": name, "owner_ref": key, "state": state,
                        "race_id": None, "small": False})
        con.close()
    if only in (None, "offices"):
        for code, (name, url) in sorted(OFFICES.items()):
            out.append({"site": url, "owner_kind": "election office", "owner": name, "owner_ref": code,
                        "state": code, "race_id": None, "small": True})
    if only in (None, "candidates"):
        fed = ro(BALLOT)
        rows = fed.execute(
            "SELECT DISTINCT c.race_id, c.name, r.state, w.url FROM websites w JOIN candidates c "
            "ON (w.person = c.race_id || '|' || c.name OR w.person = c.fec_id) "
            "JOIN races r ON r.race_id = c.race_id WHERE c.election IN ('general','open-primary') "
            "ORDER BY r.state, c.race_id, c.name").fetchall()
        fed.close()
        loc = ro(LOCAL)
        rows += loc.execute(
            "SELECT DISTINCT w.race_id, w.name, r.state, w.url FROM sl_websites w JOIN sl_races r USING (race_id) "
            "JOIN sl_candidates c ON c.race_id = w.race_id AND c.name = w.name AND c.election = 'general' "
            f"WHERE (r.state = 'MN' AND r.level IN ({','.join('?' * len(LOCAL_LEVELS))}) "
            f"AND r.office_kind NOT IN ({','.join('?' * len(LOCAL_KINDS_LEFT_OUT))})) OR r.level = 'statewide' "
            "ORDER BY r.state, w.race_id, w.name", LOCAL_LEVELS + tuple(LOCAL_KINDS_LEFT_OUT)).fetchall()
        loc.close()
        seen = set()
        for rid, name, state, url in rows:
            url = (url or "").strip()
            if not url.lower().startswith(("http://", "https://")):
                url = "https://" + url.lstrip("/") if url else ""
            if not url or (rid, name) in seen:
                continue
            seen.add((rid, name))
            out.append({"site": url, "owner_kind": "candidate", "owner": name, "owner_ref": f"{rid}|{name}",
                        "state": state, "race_id": rid, "small": False})
    return out


# ---------------------------------------------------------------------------------------------------- reading links

def links_on(body, base_host):
    """{platform: [(address, rel_me)]} from a page's <a> and <link> tags. Only addresses are read, never text."""
    text = body.decode("utf-8", "replace")
    found = {"bluesky": {}, "mastodon": {}, "youtube": {}}
    for _tag, attrs in TAG.findall(text):
        m = HREF.search(attrs)
        if not m:
            continue
        href = html.unescape(next(g for g in m.groups() if g is not None)).strip()
        if href.startswith("//"):
            href = "https:" + href
        relme = bool(REL_ME.search(attrs))
        if BSKY.match(href):
            found["bluesky"].setdefault(href.split("?")[0].split("#")[0].rstrip("/"), relme)
        elif YT.match(href):
            found["youtube"].setdefault(href.split("?")[0].split("#")[0].rstrip("/"), relme)
        else:
            mm = MASTO.match(href)
            if mm:
                host = mm.group(1).lower()
                if NOT_MASTODON.search(host) or host.endswith(base_host) or base_host.endswith(host):
                    continue
                if relme or host in KNOWN_MASTODON or re.search(r"mast|mstdn|toot|social", host):
                    found["mastodon"][href.split("?")[0].split("#")[0].rstrip("/")] = relme or found["mastodon"].get(href, False)
    return {k: list(v.items()) for k, v in found.items()}


def _json(resp):
    try:
        return json.loads(resp.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _names_domain(text, domain):
    t = unquote((text or "").lower())
    return bool(domain) and re.search(r"(^|[^a-z0-9.-])(www\.)?" + re.escape(domain) + r"($|[^a-z0-9-])", t) is not None


def verify_bluesky(src, href, domain):
    actor = unquote(BSKY.match(href).group(1))
    r = src.get("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor=" + quote(actor, safe=":"),
                accept="application/json", timeout=25)
    doc = _json(r) if r.ok else None
    if not doc or not doc.get("did") or not doc.get("handle"):
        return None, "no profile"
    handle, did = doc["handle"].lower(), doc["did"]
    if handle == domain or handle.endswith("." + domain):
        proof = f"the account's handle is the site's own domain ({handle})"
    elif _names_domain(doc.get("description"), domain):
        proof = f"the profile names the site's domain ({domain})"
    else:
        return None, "does not point back"
    return {"platform": "bluesky", "account": handle, "platform_id": did, "proof": proof, "feed": did}, ""


def verify_mastodon(src, href, domain):
    m = MASTO.match(href)
    host, user = m.group(1).lower(), m.group(2)
    r = src.get(f"https://{host}/api/v1/accounts/lookup?acct={quote(user)}", accept="application/json", timeout=25)
    doc = _json(r) if r.ok else None
    if not isinstance(doc, dict) or not doc.get("id") or not doc.get("acct"):
        return None, "no profile"
    for f in doc.get("fields") or []:
        if f.get("verified_at") and _names_domain(re.sub(r"<[^>]+>", " ", f.get("value") or "") + " " +
                                                   " ".join(re.findall(r'href="([^"]+)"', f.get("value") or "")), domain):
            acct = doc["acct"] if "@" in doc["acct"] else f"{doc['acct']}@{host}"
            return {"platform": "mastodon", "account": acct, "platform_id": f"{host}/{doc['id']}",
                    "proof": f"Mastodon's own two-way link check marks the profile's link to {domain} verified "
                             f"({f['verified_at'][:10]})",
                    "feed": f"https://{host}/users/{doc.get('username') or user}.rss"}, ""
    return None, "does not point back"


def verify_youtube(src, href, domain):
    m = YT.match(href)
    url = "https://www.youtube.com/" + href.split("youtube.com/", 1)[1]
    r = src.get(url, accept="text/html", timeout=30, expect_html=True)
    if not r.ok:
        return None, "no channel page"
    body = r.body.decode("utf-8", "replace")
    cid = None
    for pat in (r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
                r'"externalId":"(UC[\w-]{22})"', r'<meta itemprop="identifier" content="(UC[\w-]{22})"'):
        mm = re.search(pat, body)
        if mm:
            cid = mm.group(1)
            break
    if not cid or (m.group(2) and m.group(2) != cid):
        return None, "no channel id"
    enc = quote(domain, safe="")
    if not (_names_domain(body, domain) or enc.lower() in body.lower()):
        return None, "does not point back"
    handle = m.group(4) and "@" + unquote(m.group(4))
    return {"platform": "youtube", "account": handle or cid, "platform_id": cid,
            "proof": f"the channel's own page links or names {domain}",
            "feed": f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"}, ""


VERIFY = {"bluesky": verify_bluesky, "mastodon": verify_mastodon, "youtube": verify_youtube}


# ---------------------------------------------------------------------------------------------------- discovery

def _load_progress():
    try:
        with open(PROGRESS, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_progress(doc):
    os.makedirs(CACHE, exist_ok=True)
    tmp = PROGRESS + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=0, ensure_ascii=False)
    os.replace(tmp, PROGRESS)


PROFILE_PATH = re.compile(r"(/@|/channel/|/c/|/user/|/profile/)[^\s/]+")


def _log(line):
    """The night log (host, path, status, bytes, time; never a body), with any profile's name taken out of the path,
    so an account that is set aside leaves no trace."""
    try:
        os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
        with open(os.path.join(HERE, "logs", f"night_{dt.date.today().isoformat()}.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')} feeds {PROFILE_PATH.sub(r'\1(account)', line)}\n")
    except OSError:
        pass


def discover(limit=None, only=None, say=print, src=None, recheck=False):
    from election.source import Refused, Source, SourceError
    src = src or Source(stopped_file=STOPPED, log=_log)
    con = connect()
    con.executescript(SCHEMA)
    prog = _load_progress()
    every = sites(only)
    # A domain behind more than one candidate (a website builder's shared domain, or one site for two races) proves
    # nothing about which of them an account belongs to: such sites are read for counts only.
    owners_of = {}
    for s in sites("candidates") if only in (None, "candidates") else []:
        owners_of.setdefault(registered_domain(urlsplit(s["site"]).hostname or ""), set()).add(s["owner_ref"])
    shared = {d for d, refs in owners_of.items() if len(refs) > 1}
    todo = [s for s in every if recheck or s["site"] + "|" + (s["owner_ref"] or "") not in prog]
    if limit:
        todo = todo[:limit]
    say(f"accounts: {len(todo)} sites to read ({len(prog)} done before)")
    today = dt.date.today().isoformat()
    n_ok = n_ver = 0
    for i, s in enumerate(todo, 1):
        key = s["site"] + "|" + (s["owner_ref"] or "")
        rec = {"checked": today, "answer": "", "bluesky": 0, "mastodon": 0, "youtube": 0, "verified": 0, "set_aside": 0,
               "note": ""}
        domain = registered_domain(urlsplit(s["site"]).hostname or "")
        try:
            r = src.get(s["site"], accept="text/html,application/xhtml+xml", small=s["small"], timeout=25,
                        expect_html=True)
            if r.refused:
                rec["answer"], rec["note"] = "refused", r.why
            elif not r.ok:
                rec["answer"], rec["note"] = "failed", f"answered {r.status}"
            else:
                rec["answer"] = "ok"
                n_ok += 1
        except Refused as e:
            rec["answer"], rec["note"] = "not asked", e.why
        except SourceError as e:
            rec["answer"], rec["note"] = "failed", str(e)[:120]
        if rec["answer"] == "ok" and s["owner_kind"] == "candidate" and domain in shared:
            rec["note"] = "a domain shared by more than one candidate: no account can be tied to one of them"
            rec["answer"] = "shared domain"
        if rec["answer"] == "ok":
            found = links_on(r.body, (urlsplit(s["site"]).hostname or "").lower())
            for plat, items in found.items():
                rec[plat] = len(items)
                for href, relme in items[:4]:
                    try:
                        acc, why = VERIFY[plat](src, href, domain)
                    except (Refused, SourceError, AttributeError, KeyError, TypeError) as e:  # noqa: PERF203
                        acc, why = None, type(e).__name__
                    if not acc:
                        rec["set_aside"] += 1
                        continue
                    rec["verified"] += 1
                    n_ver += 1
                    with con:
                        con.execute(                     # the first owner found keeps it (CBS News before WCCO)
                            "INSERT OR IGNORE INTO accounts (account_id, platform, account, platform_id, owner_kind, "
                            "owner, owner_ref, state, race_id, site, linked_from, link_kind, proof, feed, checked_on, "
                            "active, shown) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,0)",
                            (f"{acc['platform']}:{acc['platform_id']}", acc["platform"], acc["account"],
                             acc["platform_id"], s["owner_kind"], s["owner"], s["owner_ref"], s["state"], s["race_id"],
                             s["site"], s["site"], "rel=me link" if relme else "a link on the page", acc["proof"],
                             acc["feed"], today))
        with con:
            con.execute("INSERT OR REPLACE INTO account_sites VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (s["site"], s["owner_kind"], s["owner"], s["owner_ref"], s["state"], s["race_id"], today,
                         rec["answer"], rec["bluesky"], rec["mastodon"], rec["youtube"], rec["verified"],
                         rec["set_aside"], rec["note"]))
        prog[key] = rec
        if i % 25 == 0 or i == len(todo):
            _save_progress(prog)
            say(f"accounts: {i} of {len(todo)} sites read; {n_ok} answered; {n_ver} accounts with two anchors")
    _save_progress(prog)
    con.close()
    return n_ver


# ---------------------------------------------------------------------------------------------------- checks

def run_checks(con=None, say=print):
    own = con is None
    con = con or connect()
    con.executescript(SCHEMA)
    ok = True

    def check(cond, line):
        nonlocal ok
        say(("PASS " if cond else "FAIL ") + line)
        ok = ok and bool(cond)

    n = con.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    bad = con.execute("SELECT COUNT(*) FROM accounts WHERE site IS NULL OR site='' OR linked_from IS NULL OR "
                      "linked_from='' OR proof IS NULL OR proof='' OR checked_on IS NULL OR checked_on=''").fetchone()[0]
    check(bad == 0, f"every account ({n}) has two anchors (the page that links it, the proof it points back) and a date")
    kinds = con.execute("SELECT COUNT(*) FROM accounts WHERE owner_kind NOT IN "
                        "('newsroom','election office','candidate')").fetchone()[0]
    check(kinds == 0, "every account belongs to a newsroom, an election office or a candidate")
    sites_known = {s["site"] for s in sites()}
    stray = [r[0] for r in con.execute("SELECT site FROM accounts") if r[0] not in sites_known]
    check(not stray, "every account's site is an address from the kit's own tables" + (f"; not {stray[:3]}" if stray else ""))
    shown = con.execute("SELECT COUNT(*) FROM accounts WHERE shown=1").fetchone()[0]
    check(posts_may_be_shown() or shown == 0,
          "no account is marked shown while there is no public contact address (D8)")
    domains_ok = 0
    for plat, acct, site, proof in con.execute("SELECT platform, account, site, proof FROM accounts"):
        d = registered_domain(urlsplit(site).hostname or "")
        domains_ok += 1 if (d and d in proof) else 0
    check(domains_ok == n, "every proof names the site's own domain")
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as fh:
            raw = fh.read()
        leaked = [h for h in re.findall(r"bsky\.app/profile/[^\"\s]+|@[A-Za-z0-9_]+@[a-z0-9.-]+", raw)]
        check(not leaked, "the progress file holds counts only (no handle of any account, kept or set aside)")
    sites_n = con.execute("SELECT COUNT(*), SUM(answer='ok') FROM account_sites").fetchone()
    say(f"     {sites_n[0] or 0} sites read, {sites_n[1] or 0} answered")
    if own:
        con.close()
    return ok


def summary(say=print):
    con = connect()
    con.executescript(SCHEMA)
    for row in con.execute("SELECT owner_kind, platform, COUNT(*) FROM accounts GROUP BY owner_kind, platform "
                           "ORDER BY owner_kind, platform"):
        say(f"{row[0]:<16} {row[1]:<9} {row[2]}")
    for row in con.execute("SELECT owner_kind, answer, COUNT(*), SUM(bluesky_links), SUM(mastodon_links), "
                           "SUM(youtube_links), SUM(verified), SUM(set_aside) FROM account_sites "
                           "GROUP BY owner_kind, answer ORDER BY owner_kind, answer"):
        say(f"sites {row[0]:<16} {row[1]:<10} {row[2]:>5}  links b/m/y {row[3]}/{row[4]}/{row[5]}  "
            f"kept {row[6]}  set aside {row[7]}")
    con.close()


def main(argv):
    ap = argparse.ArgumentParser(prog="accounts")
    ap.add_argument("cmd", choices=["discover", "check", "summary"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", choices=["outlets", "offices", "candidates"])
    a = ap.parse_args(argv)
    if a.cmd == "discover":
        discover(limit=a.limit, only=a.only, say=lambda s: print(s, flush=True))
        return 0
    if a.cmd == "check":
        return 0 if run_checks() else 1
    summary()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
