#!/usr/bin/env python3
"""
ballot/save_fec_key.py
======================
Saves John's free api.data.gov key (the key the FEC's OpenFEC service takes) as the one line of fec_key.txt, next to
run_ballot.py. John runs this himself ("Save FEC key.bat"), so the key never passes through a chat. The key is pasted
without being shown, is never printed or logged, and the file is one git ignores.

On The Ballot uses it for one thing the FEC's bulk files do not carry: each campaign committee's own website, from its
Statement of Organization (Form 1), so a candidate's photo and their own words can be found on it. About one request
per campaign, at most one every four seconds.

    python -m ballot.save_fec_key
"""

import getpass
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "fec_key.txt")


def main():
    print("Your key arrives by e-mail a minute after you sign up at https://api.data.gov/signup/")
    print("(first name, last name and e-mail address; it is free). Copy the key from that e-mail, then come back here.")
    print()
    print("Paste it below (right-click in this window, or Ctrl+V) and press Enter.")
    print("Nothing will appear as you paste. That is on purpose, so the key never shows on screen.")
    print()
    for _ in range(3):
        key = re.sub(r"\s+", "", getpass.getpass("API key: ") or "")
        if not key:
            print("Nothing was entered. Try once more, or close this window to stop.")
            continue
        if not re.fullmatch(r"[0-9A-Za-z]{30,64}", key):
            print(f"That does not look like an api.data.gov key: it was {len(key)} characters long, and a key is letters and digits only")
            print("(theirs are 40). Copy just the key, with nothing before or after it, and try once more.")
            continue
        with open(PATH, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(key + "\n")
        print()
        print(f"Saved: {len(key)} characters, in fec_key.txt in this folder. It stays on this computer; git never uploads it.")
        return 0
    print("Nothing was saved.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
