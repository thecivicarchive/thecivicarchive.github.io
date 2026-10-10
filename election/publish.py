"""election/publish.py - sends Election Night's live figures to the second public repository (John's D1, option B in
ARCHITECTURE.md 3.5).

How it works: the updater writes the live figures into site/night-live/ (now.json, the snapshot folders s/<seq>/, the
history files h/, and rehearsal/ during a rehearsal). The publisher keeps a plain copy of that folder in election_live/
(a git repository whose only remote is the live repository), copies the folder over it, makes ONE fresh commit with
no history and force-pushes it. The live repository therefore always holds one snapshot's worth of files (about 30 MB
at most), its GitHub Pages site serves them at https://thecivicarchive.github.io/night-live/, and the main site and its
history are never touched.

SWITCHED OFF until John names the repository he created (D1). Then the main session sets LIVE_REPO below, for example
    LIVE_REPO = "thecivicarchive/night-live"
and runs `python run_night.py publish --setup` once (it prepares election_live/ and sends the first copy). Until then
every publish is a no-op that says why; the figures are still written on this computer, where `run_night.py preview`
shows them.

Rules kept here:
  - Retried every 20 seconds up to 6 times (the router's lost lookups, Windows briefly locking a file); each try sends
    the newest figures, so a dropped connection catches up with the newest snapshot, never a backlog.
  - At most one push every 6 minutes (GitHub's soft limit is 10 builds an hour), except the last one when the updater
    stops, which says "updates paused".
  - A push only ever goes to LIVE_REPO, or, for tests, to a repository on this computer. Never anywhere else.
  - Git's own credential helper does the signing in (the same as every other publish on this computer); no key or
    password passes through this program, and nothing git prints is copied into the log beyond its first line.
  - After each push (when publishing is on) the live address is asked for now.json once a minute, for up to 15
    minutes, until it shows the snapshot just sent: that is the measured delay from snapshot to published page.
"""

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------------------------- John's switch (D1)
LIVE_REPO = None                       # e.g. "thecivicarchive/night-live": set only after John names it
LIVE_URL = "https://thecivicarchive.github.io/night-live/"
SOURCE = os.path.join(HERE, "site", "night-live")
CLONE = os.path.join(HERE, "election_live")

MIN_GAP = 360                          # seconds between pushes (10 an hour at most)
TRIES = 6
RETRY_WAIT = 20
GIT_TIMEOUT = 180
GC_EVERY = 12                          # pushes between clean-ups of the local copy's old commits
KEEP_OUT = {".git", ".nojekyll"}       # never copied over or deleted in the local copy


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if t else None


def repo_url(repo=None):
    repo = repo if repo is not None else LIVE_REPO
    return f"https://github.com/{repo}.git" if repo else None


def is_local(remote):
    """A repository on this computer (a folder, or a file:// address): the only other place a test may push to."""
    if not remote:
        return False
    if remote.startswith("file://"):
        return True
    return "://" not in remote and not re.match(r"^[\w.-]+@[\w.-]+:", remote) and os.path.isabs(remote)


def allowed(remote):
    return bool(remote) and (is_local(remote) or remote == repo_url())


# ---------------------------------------------------------------------------------------------- the local copy

def mirror(source, dest):
    """Makes dest hold exactly the files of source (dest's .git and .nojekyll aside). Returns (copied, deleted, files,
    bytes). Files are compared by size and modification time; copy2 keeps the time, so an unchanged file is skipped."""
    copied = deleted = files = total = 0
    os.makedirs(dest, exist_ok=True)
    seen = set()
    for root, dirs, names in os.walk(source):
        dirs[:] = [d for d in dirs if d not in KEEP_OUT and not d.startswith(".tmp-")]
        rel = os.path.relpath(root, source)
        rel = "" if rel == "." else rel
        for n in names:
            if n in KEEP_OUT or n.endswith(".part"):
                continue
            s = os.path.join(root, n)
            r = os.path.join(rel, n)
            seen.add(os.path.normcase(r))
            d = os.path.join(dest, r)
            try:
                st = os.stat(s)
            except FileNotFoundError:
                continue                    # pruned while being copied: the next copy has it right
            files += 1
            total += st.st_size
            try:
                dt_ = os.stat(d)
                if n != "now.json" and dt_.st_size == st.st_size and dt_.st_mtime_ns == st.st_mtime_ns:
                    continue
            except FileNotFoundError:
                pass
            os.makedirs(os.path.dirname(d), exist_ok=True)
            try:
                shutil.copy2(s, d)
                copied += 1
            except FileNotFoundError:
                continue
    for root, dirs, names in os.walk(dest, topdown=False):
        rel = os.path.relpath(root, dest)
        rel = "" if rel == "." else rel
        if rel.split(os.sep)[0] in KEEP_OUT:
            continue
        for n in names:
            r = os.path.join(rel, n)
            if n in KEEP_OUT and not rel:
                continue
            if os.path.normcase(r) not in seen:
                try:
                    os.remove(os.path.join(root, n))
                    deleted += 1
                except OSError:
                    pass
        if rel and not os.listdir(root):
            try:
                os.rmdir(root)
            except OSError:
                pass
    nj = os.path.join(dest, ".nojekyll")             # GitHub Pages serves the files as they are, and builds faster
    if not os.path.exists(nj):
        open(nj, "w").close()
    return copied, deleted, files, total


class Git:
    def __init__(self, folder, log):
        self.folder, self.log = folder, log

    def run(self, *args, timeout=GIT_TIMEOUT, ok=(0,)):
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
        try:
            p = subprocess.run(["git", "-C", self.folder] + list(args), capture_output=True, text=True, timeout=timeout, env=env,
                               encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return 124, "git took too long"
        except OSError as e:
            return 127, f"git could not be started ({e.__class__.__name__})"
        first = ((p.stderr or "").strip().splitlines() or (p.stdout or "").strip().splitlines() or [""])[0]
        first = re.sub(r"https?://[^\s]*@", "https://", first)[:200]      # never a credential, if one were ever in an address
        return p.returncode, first


def main_repo_identity():
    """The name and e-mail the main repository commits under, so the live commits carry the same."""
    out = {}
    for k in ("user.name", "user.email"):
        try:
            p = subprocess.run(["git", "-C", HERE, "config", k], capture_output=True, text=True, timeout=20)
            if p.returncode == 0 and p.stdout.strip():
                out[k] = p.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return out


def prepare(clone, remote, log):
    """election_live/ as a git repository whose origin is the live repository. Downloads nothing: the live repository's
    history is replaced on every push, so there is nothing to fetch."""
    if not allowed(remote):
        raise RuntimeError("that repository is not the one named in publish.py (or one on this computer)")
    os.makedirs(clone, exist_ok=True)
    g = Git(clone, log)
    # Only this program uses the copy, and prepare() runs once as it starts: a git lock file left now was left by a run
    # that was closed in the middle of a publish (the window closed, the computer stopped). It would block every push.
    for root, _dirs, names in os.walk(os.path.join(clone, ".git")):
        for n in names:
            if n.endswith(".lock"):
                try:
                    os.remove(os.path.join(root, n))
                    log(f"publish: removed a lock file a stopped run left in the local copy ({n})")
                except OSError:
                    pass
    if not os.path.isdir(os.path.join(clone, ".git")):
        code, msg = g.run("init", "-q")
        if code:
            raise RuntimeError(f"git init failed: {msg}")
    code, cur = g.run("remote", "get-url", "origin")
    if code:
        g.run("remote", "add", "origin", remote)
    elif cur.strip() != remote:
        g.run("remote", "set-url", "origin", remote)
    for k, v in main_repo_identity().items():
        g.run("config", k, v)
    g.run("config", "core.autocrlf", "false")
    g.run("config", "core.safecrlf", "false")
    g.run("config", "gc.auto", "0")
    return g


# ---------------------------------------------------------------------------------------------- the publisher

class Publisher:
    """Publishes the newest live figures, in a thread of its own, so that reading results never waits for a push.

    request(seq) asks for the newest figures to go out; publish_now(seq, ...) does it at once and waits (once, stop).
    lock: held while the updater writes a snapshot or prunes, and while the copy is made, so a push never carries a
    half-written snapshot."""

    def __init__(self, source=SOURCE, clone=CLONE, remote=None, lock=None, log=None, say=None, min_gap=MIN_GAP, tries=TRIES,
                 retry_wait=RETRY_WAIT, watch=None, watch_path="now.json", history=None, src=None):
        self.source, self.clone = source, clone
        self.remote = remote if remote is not None else repo_url()
        self.lock = lock or threading.Lock()
        self.log = log or (lambda line: None)
        self.say = say or (lambda line: None)
        self.min_gap, self.tries, self.retry_wait = min_gap, tries, retry_wait
        self.watch = (LIVE_URL if watch is None and self.remote == repo_url() else watch)   # where to look for the result
        self.watch_path = watch_path
        self.history_path = history
        self.src = src
        self._cond = threading.Condition()
        self._pending = None
        self._stop = False
        self._thread = None
        self._git = None
        self._pushes = 0
        self._one = threading.Lock()           # one publish at a time
        self.last = {}
        self.inflight = set()                  # snapshots copied and not yet pushed: never pruned meanwhile
        self.recent = []                       # [(seq, wall time pushed)] for the pruning rule
        self.measured = []                     # [{seq, written, pushed, seen, ...}]
        self._load_history()

    # ------------------------------------------------------------------ on or off
    @property
    def enabled(self):
        return allowed(self.remote)

    @property
    def why_off(self):
        if self.enabled:
            return ""
        if not self.remote:
            return "publishing is off until John names the live repository (D1); the figures are written on this computer only"
        return "publishing is off: the repository named is neither the one in publish.py nor one on this computer"

    def describe(self):
        if not self.enabled:
            return self.why_off
        where = "a test repository on this computer" if is_local(self.remote) else self.remote.replace("https://github.com/", "").replace(".git", "")
        return f"publishing to {where}" + (f", seen at {self.watch}" if self.watch else "")

    # ------------------------------------------------------------------ history
    def _load_history(self):
        if not self.history_path or not os.path.exists(self.history_path):
            return
        cut = utcnow() - dt.timedelta(minutes=60)
        try:
            with open(self.history_path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("ok") and e.get("pushed") and e.get("seq") is not None:
                        t = dt.datetime.fromisoformat(e["pushed"].replace("Z", "+00:00"))
                        if t > cut:
                            self.recent.append((int(e["seq"]), t))
                        self.last = e
        except OSError:
            pass

    def _note(self, e):
        self.last = e
        if self.history_path:
            try:
                os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
                with open(self.history_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(e) + "\n")
            except OSError:
                pass

    def recent_seqs(self, minutes=30):
        cut = utcnow() - dt.timedelta(minutes=minutes)
        return {s for s, t in self.recent if t > cut} | set(self.inflight)

    # ------------------------------------------------------------------ the thread
    def start(self):
        if self.enabled and self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="publisher", daemon=True)
            self._thread.start()
        return self

    def request(self, seq, written=None):
        if not self.enabled:
            return False
        with self._cond:
            self._pending = {"seq": seq, "written": written or utcnow()}
            self._cond.notify()
        return True

    def busy(self):
        with self._cond:
            return self._pending is not None

    def _loop(self):
        while True:
            with self._cond:
                while self._pending is None and not self._stop:
                    self._cond.wait(5)
                if self._stop and self._pending is None:
                    return
                job = self._pending
            gap = self.min_gap - ((utcnow() - self._last_push_time()).total_seconds() if self._last_push_time() else 10 ** 9)
            if gap > 0:
                # wait out the gap; a newer request simply replaces the pending one
                end = time.monotonic() + gap
                with self._cond:
                    while not self._stop and time.monotonic() < end:
                        self._cond.wait(min(5, max(0.1, end - time.monotonic())))
                    if self._stop:
                        return
                    job = self._pending
            with self._cond:
                self._pending = None
            if job:
                self._publish(job["seq"], job["written"])

    def _last_push_time(self):
        return self.recent[-1][1] if self.recent else None

    def stop(self, wait=True, timeout=600):
        with self._cond:
            self._stop = True
            self._cond.notify()
        if wait and self._thread is not None:
            self._thread.join(timeout)

    # ------------------------------------------------------------------ one publish (retried)
    def publish_now(self, seq, written=None, label=""):
        """Publishes at once and waits (the updater's last publish when it stops, `once --publish`). Returns the record."""
        if not self.enabled:
            e = {"seq": seq, "ok": False, "off": True, "why": self.why_off}
            return e
        with self._cond:
            self._pending = None              # this publish carries the newest figures anyway
        return self._publish(seq, written or utcnow(), label=label)

    def _publish(self, seq, written, label=""):
        with self._one:
            return self._publish_one(seq, written, label)

    def _publish_one(self, seq, written, label=""):
        t0 = utcnow()
        e = {"seq": seq, "written": iso(written), "started": iso(t0), "ok": False, "tries": 0}
        for attempt in range(1, self.tries + 1):
            e["tries"] = attempt
            try:
                if self._git is None:
                    self._git = prepare(self.clone, self.remote, self.log)
                with self.lock:                                   # never copy a half-written snapshot
                    copied, deleted, files, total = mirror(self.source, self.clone)
                    seq_now = self._seq_in_source()
                    self.inflight = {s for s in (seq_now, seq) if s is not None}
                e.update(copied=copied, deleted=deleted, files=files, bytes=total, seq=seq_now if seq_now is not None else seq)
                ok, why = self._commit_push(e["seq"], label)
            except (RuntimeError, OSError) as ex:
                ok, why = False, f"{ex.__class__.__name__}: {ex}"[:200]
            if ok:
                e["ok"] = True
                e["pushed"] = iso(utcnow())
                e["seconds"] = round((utcnow() - written).total_seconds(), 1)
                self.recent.append((e["seq"], utcnow()))
                self.recent = self.recent[-60:]
                self.inflight = set()
                self._pushes += 1
                if self._pushes % GC_EVERY == 0:
                    self._git.run("reflog", "expire", "--expire=now", "--all")
                    self._git.run("gc", "-q", "--prune=now")
                self.log(f"publish seq {e['seq']}: pushed on try {attempt}; {e['files']} files, {e['bytes'] / 1e6:.1f} MB "
                         f"({e['copied']} copied, {e['deleted']} removed); {e['seconds']} s after the snapshot was written")
                self._note(e)
                if self.watch:
                    threading.Thread(target=self._watch, args=(dict(e),), name="watch-live", daemon=True).start()
                return e
            e["why"] = why
            self.log(f"publish seq {seq}: try {attempt} of {self.tries} failed ({why})")
            if attempt < self.tries:
                time.sleep(self.retry_wait)
        e["failed"] = iso(utcnow())
        self.inflight = set()
        self.say(f"Publishing did not go through after {self.tries} tries ({e.get('why')}); the next publish sends the newest figures.")
        self._note(e)
        return e

    def _seq_in_source(self):
        try:
            # the pointer this publisher stands for: rehearsal/now.json in a rehearsal, never the live one beside it
            with open(os.path.join(self.source, *self.watch_path.split("/")), encoding="utf-8") as fh:
                return json.load(fh).get("seq")
        except (OSError, ValueError):
            return None

    def _commit_push(self, seq, label):
        g = self._git
        code, msg = g.run("checkout", "-q", "--orphan", "live-next")
        if code:
            g.run("branch", "-D", "live-next")
            code, msg = g.run("checkout", "-q", "--orphan", "live-next")
            if code:
                return False, f"git checkout: {msg}"
        for i in range(4):                      # Windows briefly blocks a new file now and then (a scan): ask again soon
            code, msg = g.run("add", "-A")
            if not code:
                break
            time.sleep(2 + 2 * i)
        if code:
            return False, f"git add: {msg}"
        text = f"Live figures, snapshot {seq} ({iso(utcnow())})" + (f", {label}" if label else "")
        code, msg = g.run("commit", "-q", "--no-verify", "-m", text)
        if code:
            return False, f"git commit: {msg}"
        g.run("branch", "-D", "main")
        code, msg = g.run("branch", "-m", "main")
        if code:
            return False, f"git branch: {msg}"
        code, msg = g.run("push", "-q", "--force", "origin", "main")
        if code:
            return False, f"git push: {msg}"
        return True, ""

    # ------------------------------------------------------------------ the measured delay
    def _watch(self, e):
        """Asks the live address for now.json once a minute until it shows this snapshot (at most 15 minutes)."""
        if not self.watch or self.src is None:
            return
        url = self.watch.rstrip("/") + "/" + self.watch_path
        written = dt.datetime.fromisoformat(e["written"].replace("Z", "+00:00"))
        for _i in range(15):
            time.sleep(60)
            try:
                r = self.src.get(url, state="--", accept="application/json")
                seq = json.loads(r.body.decode("utf-8")).get("seq") if r.ok else None
            except Exception:  # noqa: BLE001 - a failed look is only a missed measurement
                seq = None
            if seq is not None and int(seq) >= int(e["seq"]):
                m = {"seq": e["seq"], "written": e["written"], "pushed": e["pushed"], "seen": iso(utcnow()),
                     "minutes": round((utcnow() - written).total_seconds() / 60, 1)}
                self.measured.append(m)
                self.log(f"publish seq {e['seq']}: seen at the live address {m['minutes']} minutes after the snapshot was written")
                return
        self.log(f"publish seq {e['seq']}: not yet seen at the live address after 15 minutes (its cache keeps a file 10 minutes)")


# ---------------------------------------------------------------------------------------------- self-test

def selftest(tmp, say=print):
    """No network: publishes a small folder to a repository made on this computer, twice, then once with the
    repository out of reach and once after it comes back; checks the remote holds one commit with the newest files."""
    import tempfile
    ok = True

    def expect(c, what):
        nonlocal ok
        say(f"      {'ok  ' if c else 'FAIL'} {what}")
        ok = ok and bool(c)

    base = tempfile.mkdtemp(prefix="pub_", dir=tmp)
    src, clone, bare = (os.path.join(base, x) for x in ("live", "clone", "remote.git"))
    os.makedirs(os.path.join(src, "s", "000001"))
    code = subprocess.run(["git", "init", "-q", "--bare", bare], capture_output=True).returncode
    expect(code == 0, "a test repository was made on this computer")
    for n, body in (("now.json", '{"v":1,"seq":1}'), ("s/000001/mn.json", '{"v":1}')):
        with open(os.path.join(src, *n.split("/")), "w") as fh:
            fh.write(body)
    lines = []
    p = Publisher(source=src, clone=clone, remote=bare, log=lines.append, min_gap=0, tries=2, retry_wait=1)
    expect(p.enabled and not Publisher(source=src, clone=clone, remote="https://example.com/x.git").enabled,
           "it pushes only to the named repository or one on this computer")
    expect(not Publisher(source=src, clone=clone, remote=None).enabled if LIVE_REPO is None else True,
           "with no repository named, publishing is off")
    e1 = p.publish_now(1)
    expect(e1.get("ok"), f"first publish ({e1.get('why', 'pushed')})")
    os.makedirs(os.path.join(src, "s", "000002"))
    with open(os.path.join(src, "s", "000002", "mn.json"), "w") as fh:
        fh.write('{"v":1,"n":2}')
    with open(os.path.join(src, "now.json"), "w") as fh:
        fh.write('{"v":1,"seq":2}')
    shutil.rmtree(os.path.join(src, "s", "000001"))
    os.rename(bare, bare + ".away")                         # the connection drops
    e2 = p.publish_now(2)
    expect(not e2.get("ok") and e2.get("tries") == 2, "with the repository out of reach, the publish fails after its tries")
    os.rename(bare + ".away", bare)                         # and comes back
    with open(os.path.join(src, "now.json"), "w") as fh:
        fh.write('{"v":1,"seq":3}')
    e3 = p.publish_now(3)
    expect(e3.get("ok") and e3.get("seq") == 3, "the next publish sends the newest figures")
    log = subprocess.run(["git", "--git-dir", bare, "log", "--oneline", "main"], capture_output=True, text=True).stdout.strip().splitlines()
    files = subprocess.run(["git", "--git-dir", bare, "ls-tree", "-r", "--name-only", "main"], capture_output=True, text=True).stdout.split()
    now = subprocess.run(["git", "--git-dir", bare, "show", "main:now.json"], capture_output=True, text=True).stdout
    expect(len(log) == 1, f"the live repository holds one commit ({len(log)})")
    expect(sorted(files) == [".nojekyll", "now.json", "s/000002/mn.json"], f"with exactly the newest files ({files})")
    expect('"seq":3' in now, "and the newest now.json")
    shutil.rmtree(base, ignore_errors=True)
    return ok
