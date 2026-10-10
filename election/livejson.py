"""election/livejson.py - the live figures' files: snapshot folders, the pointer file now.json, the history files, and
pruning (ARCHITECTURE.md 2.6 and 3.5; the files' layout is night_common.py's account of the live figures).

GitHub's servers keep every file for 10 minutes and ignore anything after a "?" in an address, so a file at a fixed
address can be 10 minutes old for a reader. Hence:
  - now.json, the only file at a fixed address (at most 4 KB), says which snapshot folder is newest;
  - s/<seq>/, a snapshot folder, is never changed once written (it is written whole under a temporary name and then
    renamed), so a page reading now.json and then the folder never mixes two snapshots;
  - h/<code>/<race>.json, each race's forecast history, at fixed addresses (a few minutes' delay is harmless there);
  - rehearsal/ holds the same layout for a rehearsal (the pages read it only with #rehearsal in the address).

What a snapshot folder holds (each file only when its section has something to say):
  us.json                  every race for Congress, governor and the other statewide offices that a state's file
                           carries: the state files' own short form (election.store.compact_page), without the county
                           figures, so that the US page needs one file. Long form:
                           {"v":1, "state":"US", "at": <newest figure's time>, "r": {race id: {"t", "p", "ch", "v", "off"}}}
                           It also carries a partial source's contests ("2026-MI-S2@26125", level "partial": one
                           county's own count of a statewide race, where the state publishes none), which the pages
                           show as that county's part, never as the state's count.
  <code>.json              a state's figures (election.store.page_json)
  <code>/c/<county>.json, <code>/c/<county>-court.json   a county's precinct rows (election.store.county_json; names
                           from election.store.county_file), both files for every county with precincts
  fc/<code>.json           a state's latest forecasts (election.model.runs.page_json), once the model is there
  feed/us.json, feed/<code>.json   the feed and the boards (election.feeds.measures.page_json), once the feed is there

now.json (night_common.py's account, plus "fc" and "fd" from ARCHITECTURE.md 2.6):
  {"v":1, "seq":184, "at":<when this pointer was written>, "next":<when the next is due, or null>,
   "run":"running"|"paused"|"stopped", "rehearsal":false, "practice":false, "label":<what a rehearsal replays, or null>,
   "base":"s/000184/", "st":{"MN":{"s":<status word>, "t":<time of the state's figures>, "f":"mn.json", "by":"hand"|"feed"},
   "KY":{"s":"link"}, "MI":{"s":"counting", "t":..., "f":"mi.json", "by":"feed", "pt":"26125"}, ...}, "fc":{"t":..., "m":...},
   "fd":{"t":...}}
  "pt" marks a state whose figures are one county's own (a partial source): the pages show them as that county's, and
  the state as partly read.
When nothing in the figures has changed since the last snapshot, no new folder is written: now.json is written again
with the same "seq" and "base" and a new "at", so that pages know the updater is still running.

Pruning keeps the newest four snapshot folders, and every folder a published now.json named in the last 30 minutes
(a reader's now.json can be up to 10 minutes old in GitHub's cache).
"""

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election import store  # noqa: E402

LIVE_ROOT = os.path.join(HERE, "site", "night-live")
FORMAT = 1
KEEP = 4
KEEP_PUBLISHED_MINUTES = 30
# ARCHITECTURE.md 2.6: size budgets (bytes). Over a budget is said in the log and the status file; the figures still go out.
BUDGET = {"now": 4_000, "us": 150_000, "state": 800_000, "county": 150_000, "fc": 300_000, "feed": 200_000, "snapshot": 8_000_000}
SEQ_DIR = re.compile(r"^\d{6}$")
FEDERAL_LEVELS = {"congress", "federal", "statewide"}


def iso(t):
    return t.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if t else None


def dumps(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


def _write_text(path, text):
    tmp = path + ".part"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    for i in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:                   # Windows: a reader (the preview server, a virus scan) holds the file
            time.sleep(0.25 * (i + 1))
    os.replace(tmp, path)


# ---------------------------------------------------------------------------------------------- what a snapshot holds

def results_files(con, codes):
    """({relative path: text}, {code: summary}) for the results: each state's file and its county files, and us.json.
    Only states the store has contests for (a state whose only files were test files has none). A state's summary:
    {"at": its figures' time, "units": [in, all] of the race that reaches the most units, "races", "done": every race's
    units in, "official": every race certified}."""
    out, summ = {}, {}
    us = {"v": FORMAT, "state": "US", "at": None, "r": {}}
    for code in codes:
        has = con.execute("SELECT COUNT(*) FROM contests WHERE state=?", (code,)).fetchone()[0]
        if not has:
            continue
        long = store.page_json(con, code, compact=False)
        out[f"{code.lower()}.json"] = dumps(store.compact_page(long))
        widest, done, official = None, True, True
        for e in long["r"].values():
            p = e.get("p")
            if p and p[1] and (widest is None or p[1] > widest[1]):
                widest = list(p)
            if not (p and p[1] and (p[0] or 0) >= p[1]):
                done = False
            if not e.get("off"):
                official = False
        summ[code] = {"at": long.get("at"), "units": widest, "races": len(long["r"]), "done": done and bool(long["r"]),
                      "official": official and bool(long["r"])}
        for cu in store.county_units(con, code):
            if not re.fullmatch(r"\d{5}", str(cu)):
                continue
            for part in store.COUNTY_PARTS:
                out[store.county_file(code, cu, part)] = dumps(store.county_json(con, code, cu, part))
        levels = {rid: lv for rid, lv in con.execute("SELECT race_id, level FROM contests WHERE state=?", (code,))}
        for rid, e in long["r"].items():
            if levels.get(rid) in FEDERAL_LEVELS or levels.get(rid) == "partial" or re.fullmatch(r"\d{4}-[A-Z]{2}-(H\d+|S\d)", rid):
                us["r"][rid] = {k: v for k, v in e.items() if k != "k"}
                if e.get("t") and (us["at"] is None or e["t"] > us["at"]):
                    us["at"] = e["t"]
    if us["r"]:
        out["us.json"] = dumps(store.compact_page(us))
    return out, summ


def budget_of(rel):
    if rel == "us.json":
        return "us", BUDGET["us"]
    if rel.startswith("fc/"):
        return "fc", BUDGET["fc"]
    if rel.startswith("feed/"):
        return "feed", BUDGET["feed"]
    if "/c/" in rel:
        return "county", BUDGET["county"]
    return "state", BUDGET["state"]


def over_budget(files):
    """[(file, size, budget)] for every file over its budget, and the snapshot as a whole."""
    out, total = [], 0
    for rel, text in files.items():
        n = len(text.encode("utf-8")) if isinstance(text, str) else len(text)
        total += n
        _k, b = budget_of(rel)
        if n > b:
            out.append((rel, n, b))
    if total > BUDGET["snapshot"]:
        out.append(("(the whole snapshot)", total, BUDGET["snapshot"]))
    return out


def content_hash(files):
    h = hashlib.sha256()
    for rel in sorted(files):
        t = files[rel]
        h.update(rel.encode("utf-8") + b"\0" + (t.encode("utf-8") if isinstance(t, str) else t) + b"\0")
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------- the live folder

class LiveRoot:
    """One live folder (site/night-live, or its rehearsal/ beside the live figures, or a test folder)."""

    def __init__(self, root=LIVE_ROOT, keep=KEEP, log=None):
        self.root = root
        self.keep = keep
        self.log = log or (lambda line: None)
        self.seq = 0
        self.base = None
        self.hash = None
        self.now = None
        self.load()

    # ------------------------------------------------------------------ where things stand
    def seqs(self):
        d = os.path.join(self.root, "s")
        if not os.path.isdir(d):
            return []
        return sorted(int(n) for n in os.listdir(d) if SEQ_DIR.match(n) and os.path.isdir(os.path.join(d, n)))

    def load(self):
        """The newest snapshot from the folder itself (a restart resumes from here): its number, and the hash of its
        files, so an unchanged next snapshot is not written twice. Half-written folders from a stop are removed."""
        sdir = os.path.join(self.root, "s")
        if os.path.isdir(sdir):
            for n in os.listdir(sdir):
                if n.startswith(".tmp-"):
                    shutil.rmtree(os.path.join(sdir, n), ignore_errors=True)
        try:
            with open(os.path.join(self.root, "now.json"), encoding="utf-8") as fh:
                self.now = json.load(fh)
        except (OSError, ValueError):
            self.now = None
        have = self.seqs()
        self.seq = max(have + [int((self.now or {}).get("seq") or 0)])
        if have:
            self.base = f"s/{have[-1]:06d}/"
            self.hash = self._hash_folder(have[-1])
        return self

    def _hash_folder(self, seq):
        folder = os.path.join(self.root, "s", f"{seq:06d}")
        files = {}
        for root, _d, names in os.walk(folder):
            for n in names:
                p = os.path.join(root, n)
                rel = os.path.relpath(p, folder).replace(os.sep, "/")
                with open(p, "rb") as fh:
                    files[rel] = fh.read().decode("utf-8", "replace")
        return content_hash(files)

    # ------------------------------------------------------------------ writing
    def write_snapshot(self, files):
        """Writes a new snapshot folder when the figures changed. Returns (seq, base, new: bool)."""
        h = content_hash(files)
        if self.base and h == self.hash:
            return self.seq, self.base, False
        seq = self.seq + 1
        sdir = os.path.join(self.root, "s")
        tmp = os.path.join(sdir, f".tmp-{seq:06d}")
        final = os.path.join(sdir, f"{seq:06d}")
        if os.path.exists(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
        for rel, text in files.items():
            p = os.path.join(tmp, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w" if isinstance(text, str) else "wb", **({"encoding": "utf-8", "newline": "\n"} if isinstance(text, str) else {})) as fh:
                fh.write(text)
        if not files:
            os.makedirs(tmp, exist_ok=True)
        for i in range(10):
            try:
                os.rename(tmp, final)
                break
            except PermissionError:
                time.sleep(0.3 * (i + 1))
        else:
            os.rename(tmp, final)
        self.seq, self.base, self.hash = seq, f"s/{seq:06d}/", h
        return seq, self.base, True

    def write_now(self, doc):
        text = dumps(doc)
        if len(text.encode("utf-8")) > BUDGET["now"]:
            self.log(f"now.json is {len(text.encode('utf-8')):,} bytes, over its {BUDGET['now']:,}-byte budget")
        _write_text(os.path.join(self.root, "now.json"), text)
        self.now = doc
        return len(text.encode("utf-8"))

    def write_history(self, files):
        """h/<code>/<race>.json at fixed addresses, written only when changed. Returns how many were written."""
        n = 0
        for rel, text in files.items():
            p = os.path.join(self.root, "h", *rel.split("/"))
            try:
                with open(p, encoding="utf-8") as fh:
                    if fh.read() == text:
                        continue
            except OSError:
                pass
            _write_text(p, text)
            n += 1
        return n

    def prune(self, keep_also=()):
        """Removes all but the newest `keep` snapshot folders and those named in `keep_also` (folders a published
        now.json named in the last 30 minutes). Returns the numbers removed."""
        have = self.seqs()
        keep = set(have[-self.keep:]) | {int(s) for s in keep_also}
        gone = []
        for s in have:
            if s not in keep:
                shutil.rmtree(os.path.join(self.root, "s", f"{s:06d}"), ignore_errors=True)
                if not os.path.exists(os.path.join(self.root, "s", f"{s:06d}")):
                    gone.append(s)
        return gone


def now_doc(seq, base, at, next_at, run, states, rehearsal=False, label=None, fc=None, fd=None):
    doc = {"v": FORMAT, "seq": seq, "at": iso(at), "next": iso(next_at) if next_at else None, "run": run, "rehearsal": bool(rehearsal),
           "practice": False, "label": label, "base": base, "st": states}
    if fc:
        doc["fc"] = fc
    if fd:
        doc["fd"] = fd
    return doc


# ---------------------------------------------------------------------------------------------- checking a live folder

def verify(root, races=None, say=print, counties="all"):
    """Reads a live folder back as a page would: now.json, the folder it names, each state's file and its county files,
    against night_common.py's account. Returns a list of problems (empty when sound)."""
    import night_common as N
    out = []
    try:
        now = json.load(open(os.path.join(root, "now.json"), encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"now.json does not read ({e.__class__.__name__})"]
    if now.get("v") != FORMAT or not isinstance(now.get("st"), dict):
        out.append("now.json is not version 1 with a state list")
    size = os.path.getsize(os.path.join(root, "now.json"))
    if size > BUDGET["now"]:
        out.append(f"now.json is {size} bytes, over 4 KB")
    for code, s in (now.get("st") or {}).items():
        if s.get("s") not in N.STATUS:
            out.append(f"{code}: status {s.get('s')!r} is not a known word")
    base = now.get("base")
    if not base:
        return out
    folder = os.path.join(root, *base.strip("/").split("/"))
    if not os.path.isdir(folder):
        return out + [f"now.json names {base}, which is not there"]
    for code, s in (now.get("st") or {}).items():
        f = s.get("f")
        if not f:
            continue
        p = os.path.join(folder, f)
        try:
            doc = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            out.append(f"{code}: {f} is missing or does not read")
            continue
        out += [f"{code}: {x}" for x in N.check_state_live(doc, (races or {}).get(code))]
        long = store.expand_page(doc)
        lines = {rid: len(e["ch"]) for rid, e in long["r"].items()}
        cdir = os.path.join(folder, code.lower(), "c")
        names = sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []
        if counties != "all":
            names = names[:counties]
        for n in names:
            try:
                cdoc = json.load(open(os.path.join(cdir, n), encoding="utf-8"))
            except (OSError, ValueError):
                out.append(f"{code}: county file {n} does not read")
                continue
            out += [f"{code} {n}: {x}" for x in N.check_county_live(cdoc, lines)]
    return out
