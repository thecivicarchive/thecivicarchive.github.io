#!/usr/bin/env python3
"""
quiet_pages.py - a last pass over built pages before they are published (John, 2026-10-01: the public pages should
carry no hint of the files and programs the site is put together with).

    python quiet_pages.py docs/dev          (Publish dev site.bat runs this after it copies the draft)
    python quiet_pages.py site/dev --check  (only count what it would change)

The builders already leave these names out of what a reader sees. This pass also takes them out of the pages' own
script and comments, where a reader who opens "view source" would find them: the names of the kit's programs
(something_like_this.py), command lines that start "python", and the names of its database files. It touches only
.html files, rewrites a file only when something changed, and prints counts, never the text. A page's sources, methods,
formulas and data are not touched.
"""

import os
import re
import sys

RULES = [
    (re.compile(r'"python [\w.]+\.py[^"\n]*"'), '""'),                       # a command line handed to a note that no longer shows it
    (re.compile(r"<code>python [^<]*</code>"), "the same steps"),
    (re.compile(r"\bdistrict_shapes\.py\b"), "the shape measuring"),
    (re.compile(r"\bdistrict_people\.py\b"), "the people counting"),
    (re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\.py\b"), "a build step"),          # build_state_dev.py, load_counties.py and the like
    (re.compile(r"\b[\w-]+\.sqlite\b"), "the site's records"),
]


def quiet(text):
    n = 0
    for pat, repl in RULES:
        text, k = pat.subn(repl, text)
        n += k
    return text, n


def main(argv=None):
    args = [a for a in (argv if argv is not None else sys.argv[1:]) if not a.startswith("--")]
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    if not args:
        raise SystemExit(__doc__)
    root = os.path.abspath(args[0])
    files = changed = hits = 0
    for d, _dirs, names in os.walk(root):
        for name in names:
            if not name.endswith(".html"):
                continue
            path = os.path.join(d, name)
            files += 1
            with open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
                text = fh.read()
            if ".py" not in text and ".sqlite" not in text:
                continue
            new, n = quiet(text)
            if n:
                hits += n
                changed += 1
                if not check:
                    with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                        fh.write(new)
    print(f"quiet_pages: {files:,} pages read under {os.path.relpath(root)}; {hits:,} mention(s) of the kit's own files "
          f"{'found' if check else 'taken out'} in {changed:,} page(s)")
    return hits


if __name__ == "__main__":
    main()
