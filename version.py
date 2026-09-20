#!/usr/bin/env python3
"""Version control for the draft site, in plain steps.

Every build of the draft carries a number in the 4.x.xxx chain. The newest
heading in CHANGELOG.md names the version being worked on:

    ## v4.0.001 — 2026-09-20 — Short title

The last three digits go up with every saved build; the middle number goes
up when John signs off on a milestone. Every saved version is a git tag, so
any of them can be brought back.

    python version.py current                  the version named at the top of the changelog
    python version.py next patch|minor         what the next number would be
    python version.py new patch|minor "Title" [--note "bullet"]...
                                               start the next changelog entry
    python version.py save [--trailer LINE]... commit everything and tag it with the
                                               version at the top of the changelog
    python version.py list                     every saved version, newest first
    python version.py back 4.0.001             put every file back the way it was at
                                               that version, then start a new entry
                                               that says so; nothing is lost from history
"""
import argparse
import datetime as dt
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHANGELOG = os.path.join(HERE, "CHANGELOG.md")
HEADING = re.compile(r"^##\s+(?:v?(\d+\.\d+\.\d+)\s*[—\-]+\s*)?(\d{4}-\d{2}-\d{2})\s*[—\-]+\s*(.+?)\s*$")


def git(*args, check=True, capture=True):
    r = subprocess.run(["git", *args], cwd=HERE, text=True, encoding="utf-8",
                       capture_output=capture)
    if check and r.returncode:
        sys.exit((r.stderr or r.stdout or f"git {' '.join(args)} failed").strip())
    return (r.stdout or "").strip()


def parse(v):
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", v.strip())
    if not m:
        sys.exit(f"'{v}' is not a version like 4.0.001")
    return tuple(int(x) for x in m.groups())


def fmt(t):
    return f"{t[0]}.{t[1]}.{t[2]:03d}"


def top_entry():
    """(version, date, title) from the newest changelog heading, or None."""
    if not os.path.exists(CHANGELOG):
        return None
    for line in open(CHANGELOG, encoding="utf-8"):
        m = HEADING.match(line.rstrip())
        if m:
            return (m.group(1) or "", m.group(2), m.group(3))
    return None


def tags():
    out = git("tag", "-l", "v4.*")
    return sorted((parse(t) for t in out.split() if re.fullmatch(r"v4\.\d+\.\d+", t)), reverse=True)


def newest():
    """The highest version anyone has named: saved tags and the changelog top."""
    cands = tags()
    top = top_entry()
    if top and top[0]:
        cands.append(parse(top[0]))
    return max(cands) if cands else (4, 0, 0)


def bump(t, kind):
    if kind == "minor":
        return (t[0], t[1] + 1, 0)
    return (t[0], t[1], t[2] + 1)


def start_entry(version, title, notes):
    text = open(CHANGELOG, encoding="utf-8").read() if os.path.exists(CHANGELOG) else "# Changelog\n\n"
    lines = text.split("\n")
    entry = [f"## v{version} — {dt.date.today().isoformat()} — {title}", ""]
    entry += [f"- {n.strip()}" for n in notes if n.strip()]
    entry.append("")
    for i, line in enumerate(lines):
        if line.startswith("## "):
            lines[i:i] = entry
            break
    else:
        lines += entry
    open(CHANGELOG, "w", encoding="utf-8", newline="\n").write("\n".join(lines))


def cmd_current(a):
    top = top_entry()
    print(top[0] if top and top[0] else "(the changelog names no version yet)")


def cmd_next(a):
    print(fmt(bump(newest(), a.kind)))


def cmd_new(a):
    v = fmt(bump(newest(), a.kind))
    start_entry(v, a.title, a.note or [])
    print(f"Started v{v} — {a.title} at the top of CHANGELOG.md. Add bullets there, build, then save.")


def cmd_save(a):
    top = top_entry()
    if not top or not top[0]:
        sys.exit("The top entry of CHANGELOG.md has no version. Run: python version.py new patch \"Title\"")
    v = parse(top[0])
    if v in tags():
        sys.exit(f"v{fmt(v)} is already saved. Start a new entry first: python version.py new patch \"Title\"")
    highest = max(tags(), default=(4, 0, 0))
    if v <= highest:
        sys.exit(f"v{fmt(v)} is not newer than the last saved version v{fmt(highest)}. Fix the changelog heading.")
    git("add", "-A")
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=HERE).returncode == 1
    msg = f"v{fmt(v)} — {top[2]}"
    body = [msg, ""]
    for line in open(CHANGELOG, encoding="utf-8"):
        line = line.rstrip()
        if HEADING.match(line) and not line.startswith(f"## v{fmt(v)}"):
            break
        if line.startswith("- "):
            body.append(line)
    if a.trailer:
        body += [""] + list(a.trailer)
    if staged:
        git("commit", "-q", "-F", "-", check=True, capture=False) if False else subprocess.run(
            ["git", "commit", "-q", "-F", "-"], cwd=HERE, input="\n".join(body) + "\n", text=True, encoding="utf-8", check=True)
    git("tag", "-a", f"v{fmt(v)}", "-m", top[2])
    print(f"Saved v{fmt(v)} — {top[2]}" + ("" if staged else " (no file changes; tagged the current state)"))


def cmd_list(a):
    out = git("for-each-ref", "--sort=-creatordate",
              "--format=%(refname:short)  %(creatordate:short)  %(subject)", "refs/tags/v4.*")
    print(out or "(no saved versions yet)")


def cmd_back(a):
    v = parse(a.version)
    if v not in tags():
        sys.exit(f"v{fmt(v)} is not a saved version. See: python version.py list")
    if subprocess.run(["git", "diff", "--quiet"], cwd=HERE).returncode or \
       subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=HERE).returncode:
        sys.exit("There are unsaved changes. Save them first (python version.py save) so nothing is lost.")
    git("checkout", f"v{fmt(v)}", "--", ".")
    nxt = fmt(bump(newest(), "patch"))
    start_entry(nxt, f"Back to version {fmt(v)}", [f"Every file put back the way it was at version {fmt(v)}."])
    print(f"Files are now as they were at v{fmt(v)}, recorded as the start of v{nxt}.")
    print("Next: rebuild the draft (Preview dev site.bat), look at it, then Save this version.bat.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("current").set_defaults(fn=cmd_current)
    p = sub.add_parser("next"); p.add_argument("kind", choices=["patch", "minor"]); p.set_defaults(fn=cmd_next)
    p = sub.add_parser("new"); p.add_argument("kind", choices=["patch", "minor"]); p.add_argument("title")
    p.add_argument("--note", action="append"); p.set_defaults(fn=cmd_new)
    p = sub.add_parser("save"); p.add_argument("--trailer", action="append"); p.set_defaults(fn=cmd_save)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("back"); p.add_argument("version"); p.set_defaults(fn=cmd_back)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
