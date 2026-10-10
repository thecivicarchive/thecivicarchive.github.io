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
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

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
)
SPACING = 1.0                  # seconds between requests to one host
SMALL_SPACING = 2.0            # for small state sites
MAX_HOSTS = 4
STOP_HOURS = 18                # "for the night"
CHALLENGE = re.compile(rb"(just a moment\.\.\.|cf-chl|challenge-platform|_incapsula_resource|incapsula incident|"
                       rb"captcha|attention required! \| cloudflare|radware|perfdrive|request unsuccessful\. incapsula|"
                       rb"access denied</title>|bot detection|are you a robot|human verification)", re.I)


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
    def __init__(self, replay=None, log=None, never_extra=None, stopped_file=STOPPED_FILE, small_hosts=(), now=None):
        """replay: None (live), a callable url -> (status, body, headers), or a folder (FolderReplay).
        log: a callable taking one line; default appends to logs/night_<date>.log.
        never_extra: more never patterns; default reads every registry file's "never" list.
        stopped_file: where hosts stopped for the night are kept (None: in memory only)."""
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

    def get(self, url, state=None, accept="*/*", conditional=False, small=False, timeout=60, expect_html=False):
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
                status, body, rh = self._send(url, headers, timeout)
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
        if looks_html and CHALLENGE.search(head):
            return "a challenge or CAPTCHA page"
        if resp.status == 503 and CHALLENGE.search(head):
            return "a challenge page (503)"
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
            except (TimeoutError, OSError) as e:
                last = e
            time.sleep(3 + 3 * attempt)
        raise SourceError(f"no answer ({last})")

    def _open(self, req, timeout):
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
