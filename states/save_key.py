#!/usr/bin/env python3
"""
states/save_key.py
==================
Saves John's LegiScan API key as the one line of legiscan_key.txt, next to run_states.py. John runs this himself
("Save LegiScan key.bat"), so the key never passes through a chat. The key is typed or pasted without being shown,
is never printed or logged, and the file is one git ignores.

    python -m states.save_key
"""

import getpass
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "legiscan_key.txt")


def main():
    print("Your LegiScan API key is on the page https://legiscan.com/legiscan once you are logged in.")
    print("Copy it there, then come back to this window.")
    print()
    print("Paste it below (right-click in this window, or Ctrl+V) and press Enter.")
    print("Nothing will appear as you paste. That is on purpose, so the key never shows on screen.")
    print()
    for _ in range(3):
        key = re.sub(r"\s+", "", getpass.getpass("API key: ") or "")
        if not key:
            print("Nothing was entered. Try once more, or close this window to stop.")
            continue
        if not re.fullmatch(r"[0-9A-Za-z]{20,64}", key):
            print(f"That does not look like an API key: it was {len(key)} characters long, and a key is letters and digits only")
            print("(LegiScan's are 32). Copy just the key, with nothing before or after it, and try once more.")
            continue
        with open(PATH, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(key + "\n")
        print()
        print(f"Saved: {len(key)} characters, in legiscan_key.txt in this folder. It stays on this computer; git never uploads it.")
        return 0
    print("Nothing was saved.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
