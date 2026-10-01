"""
ballot/campaign.py - each campaign's own website, and a photo of the candidate from it (John, 2026-09-29: "maybe they
have something on their website ... that way it'll help identify people better").

Websites come from the FEC's OpenFEC service: the committee's Statement of Organization (Form 1) names its website.
One request per principal campaign committee, at most one every four seconds, with John's free api.data.gov key in
fec_key.txt (saved by "Save FEC key.bat"; never printed or logged). Only the website is kept; the committee's
e-mail and its treasurer's name are never stored. Answers are cached in ballot_cache/openfec/ for a week.

Photos come from the candidate's own website and nowhere else, credited and linked on the page. The rules:
  1. images the site itself labels with the candidate's family name (alt or title text, or the file name), or names
     like a portrait (headshot, portrait); if the home page has none, also its first "about" page;
  2. the site's own sharing image (og:image);
  3. at least 150 pixels on the short side; a wide photo only when the site calls it a headshot or portrait.
Campaign sites carry many photos (family, events, scenery), so no rule can pick the portrait by itself. Up to three
options per candidate are kept (photo_options) and shown on numbered contact sheets (ballot_cache/campaign/); each is
looked at, and ballot/photo_choice.json records the option that is a photograph of the candidate alone, or "none",
with a note. Only a chosen photo reaches the page. Nobody's likeness is recognised or matched: the options are the
images the candidate's own campaign labels and publishes, and the choice is only which of them shows one person.
"""

import glob
import hashlib
import html as H
import io
import json
import os
import re
import time
import urllib.parse
from urllib.request import Request, urlopen

from ballot.common import CACHE, HERE, name_parts
from states import net

KEY_FILE = os.path.join(HERE, "fec_key.txt")
CHOICE = os.path.join(HERE, "ballot", "photo_choice.json")
OPTIONS = """CREATE TABLE IF NOT EXISTS photo_options (
  person TEXT NOT NULL, opt TEXT NOT NULL, url TEXT, site TEXT, webp BLOB, PRIMARY KEY (person, opt));
CREATE TABLE IF NOT EXISTS websites (person TEXT PRIMARY KEY, url TEXT NOT NULL, source TEXT);"""
API = "https://api.open.fec.gov/v1/committee/{}/?api_key={}"
BAD = re.compile(r"logo|icon|flag|banner|donate|contribut|vote|sprite|seal|button|badge|arrow|social|facebook|twitter|instagram|youtube|"
                 r"placeholder|blank|pixel|spinner|loader|background|bg[-_]|pattern|texture|map|capitol|dome", re.I)
PORTRAIT = re.compile(r"headshot|head-shot|portrait|candidate|about|meet|profile|bio", re.I)


def have_key():
    return os.path.exists(KEY_FILE)


def _key():
    return open(KEY_FILE, encoding="utf-8").read().strip()


def list_websites(con, say=print):
    """Campaign websites that a state's official candidate list gives (Minnesota's does), saved by the list loaders as
    ballot_cache/lists_websites/<code>.json {"race|name": address}, put on the person the candidate was matched to."""
    con.executescript(OPTIONS)
    n = 0
    for path in sorted(glob.glob(os.path.join(CACHE, "lists_websites", "*.json"))):
        code = os.path.basename(path)[:2].upper()
        for key, url in json.load(open(path, encoding="utf-8")).items():
            race, name = key.split("|", 1)
            row = con.execute("SELECT fec_id FROM candidates WHERE race_id = ? AND name = ? AND election = 'general'", (race, name)).fetchone()
            if not row:
                continue
            url = url.strip()
            url = url if re.match(r"(?i)https?://", url) else "https://" + url.lower()
            con.execute("INSERT OR REPLACE INTO websites VALUES (?,?,?)", (row[0] or key, url, f"the {code} Secretary of State's candidate list"))
            n += 1
    con.commit()
    say(f"    Campaign websites from the states' own candidate lists: {n}")
    return n


def websites(con, say=print, pause=4.0):
    """Ask OpenFEC for each principal campaign committee's website; store it on the person."""
    if not have_key():
        say("    No FEC key yet, so campaign websites are not looked up. John's step: double-click \"Save FEC key.bat\".")
        return 0
    net.patient_lookups()
    con.executescript(OPTIONS)
    os.makedirs(os.path.join(CACHE, "openfec"), exist_ok=True)
    key, found, asked = _key(), 0, 0
    rows = con.execute("""SELECT DISTINCT c.fec_id, f.pcc FROM candidates c JOIN fec26_candidates f ON f.cand_id = c.fec_id
                          WHERE c.election = 'general' AND f.pcc <> ''""").fetchall()
    for fec, pcc in rows:
        path = os.path.join(CACHE, "openfec", f"{pcc}.json")
        if not (os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * 86400):
            try:
                with urlopen(Request(API.format(pcc, key), headers={"User-Agent": net.UA, "Accept": "application/json"}), timeout=60) as r:
                    res = (json.loads(r.read()).get("results") or [{}])[0]
            except Exception as e:  # noqa: BLE001
                say(f"      {pcc}: {str(e).replace(key, '***')}")
                continue
            keep = {k: res.get(k) for k in ("name", "website", "designation", "candidate_ids")}      # no e-mail, no treasurer
            json.dump(keep, open(path, "w", encoding="utf-8"))
            asked += 1
            time.sleep(pause)
        site = (json.load(open(path, encoding="utf-8")).get("website") or "").strip()
        if site:
            site = site.lower() if site.upper() == site else site
            site = site if re.match(r"(?i)^https?://", site) else "https://" + site
            con.execute("INSERT OR REPLACE INTO websites VALUES (?,?,?)", (fec, site, "FEC Form 1 (Statement of Organization), via OpenFEC"))
            con.execute("UPDATE people SET website = ? WHERE person = ?", (site, fec))
            found += 1
    con.commit()
    say(f"    Websites: {found} of {len(rows)} campaigns name one on their Form 1 ({asked} asked of the FEC this run)")
    return found


def _fetch(url, limit=4_000_000, timeout=30):
    req = Request(url, headers={"User-Agent": net.UA, "Accept": "text/html,image/*;q=0.9,*/*;q=0.5"})
    with urlopen(req, timeout=timeout) as r:
        data = r.read(limit + 1)
        return data[:limit], r.geturl(), r.headers.get("Content-Type", "")


ISSUES = "CREATE TABLE IF NOT EXISTS issues (person TEXT PRIMARY KEY, url TEXT, topics TEXT, fetched TEXT);"
ISSUE_LINK = re.compile(r"^(?:the )?(issues?|priorities|where (?:i|she|he|they|we) stands?|platform|policy|policies|agenda|plans?|positions?|my plan)$", re.I)
NOT_TOPIC = re.compile(r"donate|volunteer|sign ?up|contact|subscribe|paid for|menu|follow|join|news|events?$|about|home|shop|store|privacy|search|cookie|©|"
                       r"copyright|rights reserved|contribut|mailed|ready to go|chip in|endorse|yard sign|press|get involved|^media$|support .*(fight|campaign)|"
                       r"^(issues?|priorities|platform|policies|what we stand for|where (i|she|he|they|we) stands?|my plan|the plan)$", re.I)


def topic(t):
    """A heading as a topic: numbering like '#1' set aside, all capitals written in ordinary capitals; None when it is a
    sentence (it ends with a full stop or runs past nine words) or is the site's furniture."""
    t = re.sub(r"^#?\d+[.):]?\s+", "", t).strip()
    if len(t) < 4 or t.endswith(".") or len(t.split()) > 9 or NOT_TOPIC.search(t):
        return None
    return t[:1] + t[1:].lower() if t.isupper() else t


def issues(con, say=print, pause=1.5, only=None):
    """Each campaign's own page of issues, found from its home page's links ("Issues", "Priorities", "Where I Stand" and
    the like), and the topics it lists as headings there. Only the headings are kept, a few words each, and the page
    links to the campaign's own words; nothing longer is copied, and nothing is summarized or characterized."""
    con.executescript(ISSUES)
    net.patient_lookups()      # the home router drops some address lookups; ask again rather than give up on a site
    got, failed = 0, 0
    for person, site, name in con.execute("SELECT person, website, name FROM people WHERE website IS NOT NULL").fetchall():
        if only is not None and person not in only:      # a trial on a few people (run_ballot.py --only)
            continue
        family = (name_parts(name)[1].split() or [""])[-1]
        try:
            page, final, _ = _fetch(site)
            text = page.decode("utf-8", "replace")
            link = None
            for m in re.finditer(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', text, re.S | re.I):
                label = re.sub(r"<[^>]+>|\s+", " ", H.unescape(m.group(2))).strip()
                if label and ISSUE_LINK.match(label):
                    link = urllib.parse.urljoin(final, H.unescape(m.group(1)))
                    break
            if not link:
                continue
            time.sleep(pause)
            ipage, ifinal, _ = _fetch(link)
            seen, topics = set(), []
            for h in re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>", ipage.decode("utf-8", "replace"), re.S | re.I):
                t = topic(re.sub(r"<[^>]+>|\s+", " ", H.unescape(h)).strip().strip(":"))
                if t and len(t) <= 60 and t.lower() not in seen and not (family and family.lower() in t.lower()):      # an appeal naming the candidate is not a topic
                    seen.add(t.lower())
                    topics.append(t)
            if topics:
                con.execute("INSERT OR REPLACE INTO issues VALUES (?,?,?,date('now'))", (person, ifinal, json.dumps(topics[:10], ensure_ascii=False)))
                got += 1
        except Exception:  # noqa: BLE001  a site that cannot be read is left without topics, never guessed
            failed += 1
            continue
        time.sleep(pause)
    con.commit()
    say(f"    Issue pages: topics read for {got} campaigns, from their own sites ({failed} sites did not answer)")
    return got


def _images(page, base, family):
    """Every image on a page with a score: labelled with the family name, named like a portrait, or the sharing image."""
    out = []
    for prop in ("og:image", "twitter:image"):
        for m in re.finditer(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']+)' % prop, page, re.I):
            out.append((2, urllib.parse.urljoin(base, H.unescape(m.group(1))), "og"))
    for tag in re.findall(r"<img\b[^>]*>", page, re.I):
        attrs = dict((k.lower(), H.unescape(v)) for k, _, v in re.findall(r'([\w:-]+)\s*=\s*(["\'])(.*?)\2', tag, re.S))
        src = attrs.get("data-src") or attrs.get("data-lazy-src") or attrs.get("src") or ""
        if attrs.get("srcset"):      # the largest candidate in a srcset
            best = max((p.strip().split(" ") for p in attrs["srcset"].split(",") if p.strip()),
                       key=lambda p: int(re.sub(r"\D", "", p[1]) or 0) if len(p) > 1 else 0)
            src = best[0] or src
        if not src or src.startswith("data:"):
            continue
        words = " ".join(attrs.get(k, "") for k in ("alt", "title")) + " " + src
        score = 0
        if family and family in re.sub(r"[^a-z]+", " ", words.lower()):
            score += 5
        if PORTRAIT.search(words):
            score += 3
        if BAD.search(words):
            score -= 6
        out.append((score, urllib.parse.urljoin(base, src), "headshot" if re.search(r"headshot|head-shot|portrait", words, re.I) else "img"))
    return out


def _portrait(data, headshot=False):
    """A usable portrait photo from image bytes, as a 160 by 195 WebP, or None. A wide photo (a scene, a banner) is
    used only when the site calls it a headshot or portrait: cropped to a card, a person in a scene is too small."""
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # noqa: BLE001
        return None
    w, h = im.size
    if min(w, h) < 150 or w > 1.6 * h or (w > 1.15 * h and not headshot):
        return None
    im = im.convert("RGB")
    target = 160 / 195
    if w / h > target:      # too wide: keep the middle
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:      # too tall: keep the top, where a face usually is
        nh = int(w / target)
        top = int(max(0, min(h - nh, (h - nh) * 0.2)))
        im = im.crop((0, top, w, top + nh))
    im = im.resize((160, 195), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=80, method=6)
    return buf.getvalue()


def photos(con, say=print, pause=1.5, refresh=False, only=None):
    """For each candidate with a website and no photo from an official record, keep up to three options from their site."""
    net.patient_lookups()
    con.executescript(OPTIONS)
    have = {r[0] for r in con.execute("SELECT DISTINCT person FROM photo_options")}
    rows = con.execute("SELECT person, name, website FROM people WHERE website IS NOT NULL AND (photo IS NULL OR photo_src = 'Campaign')").fetchall()
    got, tried = 0, 0
    for person, name, site in rows:
        if (person in have and not refresh) or (only is not None and person not in only):
            continue
        family = name_parts(name)[1].split()[-1] if name_parts(name)[1] else ""
        tried += 1
        try:
            page, final, _ = _fetch(site)
        except Exception as e:  # noqa: BLE001
            say(f"      {name}: the website did not answer ({str(e)[:80]})")
            continue
        text = page.decode("utf-8", "replace")
        cands = _images(text, final, family)
        if not any(s >= 5 for s, _, _ in cands):      # nothing labelled on the home page: try its first "about" page
            about = next((urllib.parse.urljoin(final, H.unescape(u)) for u in re.findall(r'<a[^>]+href=["\']([^"\'#]+)', text, re.I)
                          if re.search(r"about|meet|bio", u, re.I) and urllib.parse.urlparse(urllib.parse.urljoin(final, u)).netloc == urllib.parse.urlparse(final).netloc), None)
            if about:
                try:
                    apage, afinal, _ = _fetch(about)
                    cands += [(s + 1, u, k) for s, u, k in _images(apage.decode("utf-8", "replace"), afinal, family)]
                except Exception:  # noqa: BLE001
                    pass
        options, seen = [], set()
        for score, url, kind in sorted(cands, key=lambda c: -c[0])[:12]:
            if score < 2 or len(options) == 3:
                break
            if url in seen:
                continue
            seen.add(url)
            try:
                data, _, ctype = _fetch(url, limit=8_000_000)
            except Exception:  # noqa: BLE001
                continue
            img = _portrait(data, headshot=(kind == "headshot"))
            if img and hashlib.sha1(img).hexdigest() not in {hashlib.sha1(o[1]).hexdigest() for o in options}:
                options.append((url, img))
            time.sleep(0.3)
        con.execute("DELETE FROM photo_options WHERE person = ?", (person,))
        host = urllib.parse.urlparse(final).netloc
        con.executemany("INSERT INTO photo_options VALUES (?,?,?,?,?)", [(person, "abc"[i], u, host, w) for i, (u, w) in enumerate(options)])
        got += bool(options)
        time.sleep(pause)
    con.commit()
    say(f"    Campaign photos: options kept for {got} of {tried} campaign websites looked at this run")
    return got


def apply_choices(con, say=print):
    """Put each campaign website and each reviewed photo choice on the person; unreviewed options never reach the page."""
    con.executescript(OPTIONS)
    con.execute("UPDATE people SET website = (SELECT url FROM websites w WHERE w.person = people.person) WHERE website IS NULL")
    choice = json.load(open(CHOICE, encoding="utf-8")) if os.path.exists(CHOICE) else {}
    con.execute("UPDATE people SET photo = NULL, photo_src = NULL, photo_credit = NULL, photo_url = NULL WHERE photo_src = 'Campaign'")
    used = 0
    for person, c in choice.items():
        opt = (c or {}).get("pick", "none")
        row = con.execute("SELECT url, site, webp FROM photo_options WHERE person = ? AND opt = ?", (person, opt)).fetchone()
        if not row:
            continue
        con.execute("UPDATE people SET photo = ?, photo_src = 'Campaign', photo_credit = ?, photo_url = ? WHERE person = ? AND (photo IS NULL OR photo_src = 'Campaign')",
                    (row[2], f"From the campaign's own website, {row[1]}", row[0], person))
        used += 1
    con.commit()
    waiting = con.execute("SELECT COUNT(DISTINCT person) FROM photo_options").fetchone()[0] - len(choice)
    say(f"    Campaign photos on the page: {used}; {max(0, waiting)} candidates' options still to be looked at")
    return used


def contact_sheet(con, out_dir=os.path.join(CACHE, "campaign"), per_sheet=36, only_new=True):
    """Every candidate's photo options on numbered sheets (7a, 7b, 7c), so each can be looked at before any is used."""
    from PIL import Image, ImageDraw
    con.executescript(OPTIONS)
    os.makedirs(out_dir, exist_ok=True)
    done = set(json.load(open(CHOICE, encoding="utf-8"))) if (only_new and os.path.exists(CHOICE)) else set()
    people = [r for r in con.execute("SELECT DISTINCT o.person, p.name FROM photo_options o JOIN people p USING (person) ORDER BY o.person") if r[0] not in done]
    sheets, index = [], []
    per_row = 3      # one candidate a row: their three options side by side
    for s in range(0, len(people), per_sheet // per_row):
        chunk = people[s:s + per_sheet // per_row]
        sheet = Image.new("RGB", (per_row * 170 + 200, len(chunk) * 225), "white")
        draw = ImageDraw.Draw(sheet)
        for r, (person, name) in enumerate(chunk):
            n = s + r + 1
            draw.text((5, r * 225 + 90), f"{n}. {name[:26]}", fill="black")
            for opt, webp in con.execute("SELECT opt, webp FROM photo_options WHERE person = ? ORDER BY opt", (person,)):
                x = 200 + "abc".index(opt) * 170
                sheet.paste(Image.open(io.BytesIO(webp)).convert("RGB"), (x, r * 225 + 5))
                draw.text((x, r * 225 + 203), f"{n}{opt}", fill="black")
            index.append((n, person, name))
        path = os.path.join(out_dir, f"contact-{len(sheets) + 1}.png")
        sheet.save(path)
        sheets.append(path)
    return sheets, index
