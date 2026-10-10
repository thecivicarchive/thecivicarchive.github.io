"""election/source.py - the one gate every Election Night request goes through, live or replayed.

What it promises (ARCHITECTURE.md 3.4):
  - The kit's honest User-Agent (states/net.UA); never another identity.
  - One request at a time to a host, at least a second apart (two for a small state site), at most four hosts at once.
  - Patient address lookups (this router drops about one in three) and the kit's one certificate repair (a server that
    leaves its issuer's certificate out of the handshake; the chain must still end at a trusted root). Certificate
    checking is never switched off: a certificate that fails stays failed.
  - Conditional requests (ETag, Last-Modified) where a host supports them.
  - The never lists, refused before any request: every Minnesota Secretary of State host (*.sos.mn.gov), Kentucky's
    vrsws.sos.ky.gov, GDELT's search API, and every host a state's registry file lists under "never".
  - A 403, a 429, a challenge page or a CAPTCHA stops that host for the night. It is never retried under another
    identity and never worked around; the state then links to its own results.
  - Every request is logged (host, path, status, bytes, time taken); never a body.

Replays: Source(replay=...) serves answers from a callable or a folder instead of the internet, so a rehearsal runs
the night's own code. The never lists apply in a replay too.

    from election.source import Source, Refused
    src = Source()                       # live
    r = src.get("https://example.gov/results.json", state="XX", conditional=True)
    if r.not_modified: ...
"""

import datetime as dt
import fnmatch
import glob
import http.client
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from states import net  # noqa: E402

UA = net.UA
REGISTRY_DIR = os.path.join(HERE, "election", "registry")
STOPPED_FILE = os.path.join(HERE, "election_cache", "stopped_hosts.json")
LOG_DIR = os.path.join(HERE, "logs")

# Hosts no Election Night program ever asks, whatever a registry file says. "*.example.gov" also covers example.gov.
NEVER = (
    "*.sos.mn.gov",            # Minnesota Secretary of State: results, results files, candidates, main site, poll finder (CAPTCHA)
    "*.sos.state.mn.us",       # the Secretary's older host names
    "vrsws.sos.ky.gov",        # Kentucky's live results host: its Acceptable Use Policy limits scraping
    "api.gdeltproject.org",    # GDELT's search API answers this machine 429; the raw 15-minute files are used instead
    "miboecfr.nictusa.com",    # Michigan's old campaign-finance host, now a people-search site
    "*.arizona.vote",          # Arizona's results site and its data host cdn1.arizona.vote: John said no (D2, 2026-10-10)
)
SPACING = 1.0                  # seconds between requests to one host
SMALL_SPACING = 2.0            # for small state sites
MAX_HOSTS = 4
STOP_HOURS = 18                # "for the night"
# What makes an answer a challenge page (mended 2026-10-10). Ordinary pages carry these vendors' scripts all the time:
# a contact form's reCAPTCHA or hCaptcha, Cloudflare's background script under /cdn-cgi/challenge-platform/, an
# Imperva script. The mere presence of a script is never a refusal (that test stopped 983 campaign and state sites for
# 18 hours, vote.utah.gov and coloradosos.gov among them). A refusal is:
#   1. the status (403, 429; see _refusal), or a header the vendor sets on its challenge (Cloudflare's
#      cf-mitigated: challenge; AWS WAF's x-amzn-waf-action);
#   2. the challenge page's own title ("Just a moment...", "Attention Required! | Cloudflare", "Human Verification" ...);
#   3. a marker that only a challenge or block page carries (Cloudflare's challenge settings, Imperva's incident id, a
#      redirect to Radware's validator);
#   4. a page with next to no words of its own whose only content is a bot vendor's script (Imperva's 212-byte stub).
CHALLENGE_TITLE = re.compile(
    rb"\s*(just a moment\.*|attention required!? \| cloudflare|access denied|request unsuccessful.*|"
    rb"pardon our interruption|human verification|are you a robot\??|verify(ing)? (that )?you are (a )?human.*|"
    rb"security check|ddos-guard|.{0,40}\bcaptcha\b.{0,40}|radware.{0,60}|bot (manager|detection).{0,40})\s*", re.I | re.S)
CHALLENGE_MARK = re.compile(
    rb"(window\._cf_chl_opt|id=[\"']challenge-form[\"']|id=[\"']challenge-error-text[\"']|cf-browser-verification|"
    rb"incapsula incident id|request unsuccessful\. incapsula|validate\.perfdrive\.com|"
    rb"<h1[^>]*>\s*(verify you are human|human verification|are you a robot)\b)", re.I)
# Bot walls' own scripts (never a form's reCAPTCHA): counted only on a page with next to no words (rule 4).
VENDOR_SCRIPT = re.compile(rb"(_incapsula_resource|perfdrive|radware|cf-chl|captcha-delivery\.com|px-captcha)", re.I)
# Kept for readers that test a body themselves: the challenge page's own markers, never a vendor's script alone.
CHALLENGE = CHALLENGE_MARK
_TITLE = re.compile(rb"<title[^>]*>(.{0,300}?)</title>", re.I | re.S)
_DROP = re.compile(rb"<(script|style|noscript|template)\b.*?</\1\s*>|<!--.*?-->", re.I | re.S)
_TAG = re.compile(rb"<[^>]*>")
_ENTITY = re.compile(rb"&#?\w+;")


def visible_text_len(body):
    """How many characters of words a page shows a reader (scripts, styles, comments and tags taken out)."""
    text = _ENTITY.sub(b" ", _TAG.sub(b" ", _DROP.sub(b" ", body)))
    return len(b" ".join(text.split()))


def challenge_reason(status, headers, body, looks_html=True):
    """Why an answer is a real challenge or block page, or "" when it is not. Headers' names in lower case."""
    headers = headers or {}
    if "challenge" in (headers.get("cf-mitigated") or "").lower():
        return "a challenge page (Cloudflare said so)"
    if (headers.get("x-amzn-waf-action") or "").lower() in ("challenge", "captcha"):
        return "a challenge page (the firewall said so)"
    if not looks_html:
        return ""
    head = body[:200000]
    t = _TITLE.search(head)
    if t and CHALLENGE_TITLE.fullmatch(_ENTITY.sub(b" ", t.group(1))):
        return "a challenge or CAPTCHA page"
    if CHALLENGE_MARK.search(head):
        return "a challenge or CAPTCHA page"
    if len(body) < 20000 and VENDOR_SCRIPT.search(head) and visible_text_len(head) < 80:
        return "a challenge page (a bot check's script and nothing else)"
    return ""


class Refused(Exception):
    """A request that was never sent: the host is on a never list or stopped for the night."""

    def __init__(self, url, why):
        super().__init__(f"{why}: {url}")
        self.url, self.why = url, why


class SourceError(Exception):
    """The request was sent and failed (no answer, a certificate that does not verify)."""


@dataclass
class Response:
    url: str
    status: int
    body: bytes = b""
    headers: dict = field(default_factory=dict)
    elapsed: float = 0.0
    not_modified: bool = False
    refused: bool = False          # the host answered with a refusal (403, 429, a challenge); now stopped for the night
    why: str = ""

    @property
    def ok(self):
        return 200 <= self.status < 300 and not self.refused


def host_of(url):
    return (urlsplit(url).hostname or "").lower().rstrip(".")


def _matches(pattern, host, path):
    pattern = pattern.strip().lower()
    if not pattern:
        return False
    if "://" in pattern:
        pattern = pattern.split("://", 1)[1]
    phost, _, ppath = pattern.partition("/")
    if phost.startswith("*."):
        hit = host == phost[2:] or host.endswith(phost[1:])
    elif any(ch in phost for ch in "*?["):
        hit = fnmatch.fnmatch(host, phost)
    else:
        hit = host == phost
    return hit and (not ppath or path.lower().lstrip("/").startswith(ppath))


def registry_never(folder=REGISTRY_DIR):
    """Every pattern under "never" in the registry files (a list of host patterns, or of objects with a "host")."""
    out = []
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        for item in doc.get("never", []) if isinstance(doc, dict) else []:
            pat = item.get("host") if isinstance(item, dict) else item
            if isinstance(pat, str) and pat.strip():
                out.append(pat.strip())
    return out


def never_reason(url, extra=()):
    """The pattern that forbids this address, or None."""
    host, path = host_of(url), urlsplit(url).path or "/"
    for pat in tuple(NEVER) + tuple(extra):
        if _matches(pat, host, path):
            return pat
    return None


class _GatedRedirects(HTTPRedirectHandler):
    """Follows a redirect only to an address the gate would ask itself: a never-listed host or one stopped for the night
    is refused before the new request is sent, and every redirect is logged with the host it goes to. The gate (a
    Source) rides on the request as `_gate`, and is handed on to each redirected request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        gate = getattr(req, "_gate", None)
        if gate is not None:
            gate.log(f"-- redirect {code} {host_of(req.full_url)} -> {host_of(newurl)}{urlsplit(newurl).path or '/'}")
            gate.check(newurl)                         # raises Refused: the redirect is never followed
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            new._gate = gate
        return new


def urlopen(req, timeout=None, context=None):
    """urllib's urlopen with the gate's redirect check (the request carries its Source as `_gate`)."""
    handlers = [HTTPSHandler(context=context)] if context is not None else []
    return build_opener(*handlers, _GatedRedirects()).open(req, timeout=timeout)


class FolderReplay:
    """Answers from a folder laid out as <root>/<host>/<path> (a query string becomes part of the file name, with
    unsafe characters replaced). A missing file is a 404. A `clock` callable may pick a subfolder per moment."""

    def __init__(self, root, clock=None):
        self.root, self.clock = root, clock

    def path_for(self, url):
        s = urlsplit(url)
        rel = (s.path or "/").lstrip("/") or "index"
        if s.query:
            rel += "__" + re.sub(r"[^A-Za-z0-9._=-]+", "_", s.query)
        base = os.path.join(self.root, self.clock()) if self.clock else self.root
        return os.path.join(base, (s.hostname or "").lower(), *rel.split("/"))

    def __call__(self, url):
        p = self.path_for(url)
        if not os.path.isfile(p):
            return 404, b"", {}
        with open(p, "rb") as fh:
            return 200, fh.read(), {}


class Source:
    def __init__(self, replay=None, log=None, never_extra=None, stopped_file=STOPPED_FILE, small_hosts=(), now=None, timeout=60):
        """replay: None (live), a callable url -> (status, body, headers), or a folder (FolderReplay).
        log: a callable taking one line; default appends to logs/night_<date>.log.
        never_extra: more never patterns; default reads every registry file's "never" list.
        stopped_file: where hosts stopped for the night are kept (None: in memory only).
        timeout: seconds of silence before a request is given up (each of its two tries), unless a call names its own."""
        self.timeout = timeout
        if isinstance(replay, str):
            replay = FolderReplay(replay)
        self.replay = replay
        self.log = log or self._file_log
        self.never_extra = tuple(registry_never() if never_extra is None else never_extra)
        self.stopped_file = stopped_file
        self.small_hosts = {h.lower() for h in small_hosts}
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self._host_locks = {}
        self._last = {}
        self._lock = threading.Lock()
        self._hosts = threading.BoundedSemaphore(MAX_HOSTS)
        self._validators = {}          # url -> (etag, last-modified)
        self._stopped = self._load_stopped()

    # ------------------------------------------------------------------ the never lists and stopped hosts

    def _load_stopped(self):
        if not self.stopped_file or not os.path.exists(self.stopped_file):
            return {}
        try:
            with open(self.stopped_file, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            return {}
        out, cut = {}, self.now() - dt.timedelta(hours=STOP_HOURS)
        for host, v in doc.items():
            try:
                if dt.datetime.fromisoformat(v["at"]) > cut:
                    out[host] = v
            except (KeyError, ValueError, TypeError):
                continue
        return out

    def _save_stopped(self):
        if not self.stopped_file:
            return
        os.makedirs(os.path.dirname(self.stopped_file), exist_ok=True)
        tmp = self.stopped_file + ".part"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._stopped, fh, indent=1)
        os.replace(tmp, self.stopped_file)

    def stop_host(self, host, why):
        with self._lock:
            self._stopped[host] = {"at": self.now().isoformat(timespec="seconds"), "why": why}
            self._save_stopped()
        self.log(f"stopped {host} for the night: {why}")

    def stopped(self, host):
        v = self._stopped.get(host)
        if not v:
            return None
        try:
            if dt.datetime.fromisoformat(v["at"]) <= self.now() - dt.timedelta(hours=STOP_HOURS):
                return None
        except (KeyError, ValueError, TypeError):
            return None
        return v.get("why") or "stopped for the night"

    def check(self, url):
        """Raises Refused before anything is sent when the address may not be asked."""
        if not url.lower().startswith(("http://", "https://")):
            raise Refused(url, "not a web address")
        pat = never_reason(url, self.never_extra)
        if pat:
            raise Refused(url, f"on the never list ({pat})")
        why = self.stopped(host_of(url))
        if why:
            raise Refused(url, f"stopped for the night ({why})")

    # ------------------------------------------------------------------ politeness

    def _wait_turn(self, host, small):
        gap = SMALL_SPACING if (small or host in self.small_hosts) else SPACING
        last = self._last.get(host)
        if last is not None:
            wait = gap - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)

    def _host_lock(self, host):
        with self._lock:
            return self._host_locks.setdefault(host, threading.Lock())

    # ------------------------------------------------------------------ the request

    def get(self, url, state=None, accept="*/*", conditional=False, small=False, timeout=None, expect_html=False):
        """One polite GET. Never raises for an HTTP status (the Response carries it); raises Refused before sending
        when the host may not be asked, and SourceError when no answer came."""
        self.check(url)
        host = host_of(url)
        path = urlsplit(url).path or "/"
        headers = {"User-Agent": UA, "Accept": accept}
        if conditional and url in self._validators:
            etag, lm = self._validators[url]
            if etag:
                headers["If-None-Match"] = etag
            if lm:
                headers["If-Modified-Since"] = lm
        with self._hosts, self._host_lock(host):
            self._wait_turn(host, small)
            t0 = time.monotonic()
            try:
                status, body, rh = self._send(url, headers, timeout or self.timeout)
            finally:
                self._last[host] = time.monotonic()
            elapsed = time.monotonic() - t0
        rh = {k.lower(): v for k, v in (rh or {}).items()}
        resp = Response(url=url, status=status, body=body or b"", headers=rh, elapsed=elapsed)
        self.log(f"{state or '--'} GET {host}{path} {status} {len(resp.body)}B {elapsed:.2f}s")
        if status == 304:
            resp.not_modified = True
            return resp
        why = self._refusal(resp, expect_html)
        if why:
            resp.refused, resp.why = True, why
            self.stop_host(host, why)
            return resp
        if 200 <= status < 300 and conditional:
            self._validators[url] = (rh.get("etag"), rh.get("last-modified"))
        return resp

    def _refusal(self, resp, expect_html):
        if resp.status in (403, 429):
            return f"answered {resp.status}"
        ctype = resp.headers.get("content-type", "")
        head = resp.body[:200000]
        looks_html = "html" in ctype or head.lstrip()[:15].lower().startswith((b"<!doctype", b"<html"))
        why = challenge_reason(resp.status, resp.headers, resp.body, looks_html or resp.status == 503)
        if why:
            return why
        if looks_html and not expect_html and resp.status == 200 and len(resp.body) < 600 and b"<script" in head.lower():
            return "a script-only page where data was expected"
        return ""

    def _send(self, url, headers, timeout):
        if self.replay is not None:
            status, body, rh = self.replay(url)
            return status, body, rh
        net.patient_lookups()
        req = Request(url, headers=headers)
        last = None
        for attempt in range(2):
            try:
                return self._open(req, timeout)
            except HTTPError as e:
                try:
                    body = e.read()
                except Exception:  # noqa: BLE001
                    body = b""
                return e.code, body, dict(e.headers or {})
            except URLError as e:
                reason = getattr(e, "reason", None)
                if getattr(reason, "verify_code", None) is not None and getattr(reason, "verify_code") != 20:
                    raise SourceError(f"certificate did not verify ({reason}); checking stays on") from e
                last = e
            except (TimeoutError, OSError, http.client.HTTPException) as e:     # HTTPException: a file cut off midway (IncompleteRead)
                last = e
            time.sleep(3 + 3 * attempt)
        raise SourceError(f"no answer ({last.__class__.__name__}: {last})")

    def _open(self, req, timeout):
        req._gate = self
        try:
            with urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), dict(r.headers)
        except URLError as e:
            reason = getattr(e, "reason", None)
            if getattr(reason, "verify_code", None) != 20:                  # 20: the issuer's certificate was left out
                raise
            ctx = net._context_with_issuer(req.host)                       # the kit's one repair; still needs a trusted root
            if ctx is None:
                raise
            with urlopen(req, timeout=timeout, context=ctx) as r:
                return r.status, r.read(), dict(r.headers)

    # ------------------------------------------------------------------ the log

    def _file_log(self, line):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            day = dt.date.today().isoformat()
            with open(os.path.join(LOG_DIR, f"night_{day}.log"), "a", encoding="utf-8") as fh:
                fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {line}\n")
        except OSError:
            pass
