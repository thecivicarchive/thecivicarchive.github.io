"""
ballot/merge_photo_choices_local.py - folds the reviewers' part files (ballot/photo_choices_local/*.json) into
ballot/photo_choice_local.json, the one file the state and local pages' photo choices are read from.

    python -m ballot.merge_photo_choices_local

A choice already in photo_choice_local.json is never replaced. Keys are "race_id|name"; a value is
{"pick": "a" | "b" | "c" | "none", "note": "..."}. It prints counts only. Run `python run_ballot.py localfacts`
afterwards: that stage puts the chosen pictures on the candidates.
"""

import glob
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHOICE = os.path.join(HERE, "ballot", "photo_choice_local.json")
PARTS = os.path.join(HERE, "ballot", "photo_choices_local", "*.json")


def main():
    choice = json.load(open(CHOICE, encoding="utf-8")) if os.path.exists(CHOICE) else {}
    before, added, picked = len(choice), 0, 0
    for path in sorted(glob.glob(PARTS)):
        for key, c in json.load(open(path, encoding="utf-8")).items():
            if key in choice:
                continue
            pick = (c or {}).get("pick", "none")
            choice[key] = {"pick": pick if pick in ("a", "b", "c") else "none", "note": (c or {}).get("note", "")}
            added += 1
            picked += choice[key]["pick"] != "none"
    with open(CHOICE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(choice, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"local photo choices: {before} before, {added} added ({picked} with a photo, {added - picked} with none); {len(choice)} in all")


if __name__ == "__main__":
    main()
