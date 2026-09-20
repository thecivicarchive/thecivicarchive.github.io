"""Polite, patient downloads shared by the state loaders: an honest User-Agent, one file at a time, a disk cache,
and address lookups that are asked again when a home router drops them (it drops about one in three here)."""

import os
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA = "congress-catalog/1.0 (personal legislative research; thecivicarchive.github.io)"
_patient = False


def patient_lookups(tries=24):
    """Ask again, a little slower each time, before calling an address lookup a failure."""
    global _patient
    if _patient:
        return
    _patient = True
    plain = socket.getaddrinfo

    def lookup(host, port, family=0, *rest, **kw):
        last = None
        for i in range(tries):
            try:
                return plain(host, port, family if (family or i % 2) else socket.AF_INET, *rest, **kw)
            except socket.gaierror as e:
                last = e
                time.sleep(min(3.0, 0.3 + i * 0.25))
        raise last
    socket.getaddrinfo = lookup


def get(url, timeout=120, accept="*/*"):
    patient_lookups()
    with urlopen(Request(url, headers={"User-Agent": UA, "Accept": accept}), timeout=timeout) as r:
        return r.read()


def download(url, path, max_age_days, tries=6, say=print):
    """One file, streamed to disk; kept until it is older than max_age_days. Returns True when fetched afresh.
    If the refresh fails and an older copy exists, the older copy is used and the caller is told."""
    patient_lookups()
    if os.path.exists(path) and os.path.getsize(path) > 0 and (time.time() - os.path.getmtime(path)) < max_age_days * 86400:
        return False
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    part = path + ".part"
    for attempt in range(tries):
        try:
            with urlopen(Request(url, headers={"User-Agent": UA, "Accept": "*/*"}), timeout=180) as r, open(part, "wb") as fh:
                got = told = 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
                    got += len(chunk)
                    if got - told >= 16 << 20:
                        told = got
                        say(f"      {os.path.basename(path)}: {got / 1e6:,.0f} MB")
            os.replace(part, path)
            time.sleep(1.0)
            return True
        except (HTTPError, URLError, OSError) as e:
            if attempt == tries - 1:
                if os.path.exists(path):
                    say(f"      could not refresh {os.path.basename(path)} ({e}); using the copy on disk")
                    return False
                raise
            say(f"      {os.path.basename(path)}: {e}; trying again in {10 * (attempt + 1)} s")
            time.sleep(10 * (attempt + 1))
