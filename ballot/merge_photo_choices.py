"""
ballot/merge_photo_choices.py - folds the reviewers' part files (ballot/photo_choices/part-*.json) into
ballot/photo_choice.json and puts the choices on the people table.

    python -m ballot.merge_photo_choices [--hold KEY ...]

A choice already in photo_choice.json is never replaced. A key named with --hold, and every key in HELD below, is
recorded as "none" with a note saying a person should look: those picks rested on where the site placed the picture
and nothing else, so they stay off the page until someone has looked. It prints counts only.
"""

import glob
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHOICE = os.path.join(HERE, "ballot", "photo_choice.json")
PARTS = os.path.join(HERE, "ballot", "photo_choices", "part-*.json")
# 2026-10-01: picks the reviewers themselves flagged as resting on placement alone, or as hard to see
HELD = {"H2UT02506", "H6WI07207", "H2MI12198", "H0WV03193", "S6MT00287", "H6UT03174", "H6PA14200"}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    held = set(HELD) | {a for a in argv if not a.startswith("--")}
    choice = json.load(open(CHOICE, encoding="utf-8")) if os.path.exists(CHOICE) else {}
    before, added, picked, none, kept_back = len(choice), 0, 0, 0, 0
    for path in sorted(glob.glob(PARTS)):
        for person, c in json.load(open(path, encoding="utf-8")).items():
            if person in choice:
                continue
            pick = (c or {}).get("pick", "none")
            note = (c or {}).get("note", "")
            if person in held and pick != "none":
                pick, note, kept_back = "none", "Held for a person to look at (the reviewer's pick rested on placement alone or the face was small): " + note, kept_back + 1
            choice[person] = {"pick": pick, "note": note}
            added += 1
            picked += pick != "none"
            none += pick == "none"
    with open(CHOICE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(choice, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"photo choices: {before} before, {added} added ({picked} with a photo, {none} with none, {kept_back} of those held for a person to look at); {len(choice)} in all")
    sys.path.insert(0, HERE)
    from ballot import campaign
    con = sqlite3.connect(os.path.join(HERE, "ballot_2026.sqlite"))
    campaign.apply_choices(con)
    con.close()


if __name__ == "__main__":
    main()
