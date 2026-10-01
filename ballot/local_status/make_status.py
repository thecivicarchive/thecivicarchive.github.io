"""Writes ballot_local_status.md in the project: where each state's county and local ballot stands, and what waits on John."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = r"C:\Users\16516\plain-congress"
SCOUT = os.path.join(HERE, "scout_all.json")
if not os.path.exists(SCOUT):      # kept in the project as ballot/local_scout.json, one folder up from ballot/local_status/
    SCOUT = os.path.join(HERE, "..", "local_scout.json")
have = json.load(open(SCOUT, encoding="utf-8"))
state = json.load(open(os.path.join(HERE, "status_state.json"), encoding="utf-8"))

NAMES = {"al": "Alabama", "ak": "Alaska", "az": "Arizona", "ar": "Arkansas", "ca": "California", "co": "Colorado", "ct": "Connecticut", "de": "Delaware",
         "fl": "Florida", "ga": "Georgia", "hi": "Hawaii", "id": "Idaho", "il": "Illinois", "in": "Indiana", "ia": "Iowa", "ks": "Kansas", "ky": "Kentucky",
         "la": "Louisiana", "me": "Maine", "md": "Maryland", "ma": "Massachusetts", "mi": "Michigan", "mn": "Minnesota", "ms": "Mississippi",
         "mo": "Missouri", "mt": "Montana", "ne": "Nebraska", "nv": "Nevada", "nh": "New Hampshire", "nj": "New Jersey", "nm": "New Mexico",
         "ny": "New York", "nc": "North Carolina", "nd": "North Dakota", "oh": "Ohio", "ok": "Oklahoma", "or": "Oregon", "pa": "Pennsylvania",
         "ri": "Rhode Island", "sc": "South Carolina", "sd": "South Dakota", "tn": "Tennessee", "tx": "Texas", "ut": "Utah", "vt": "Vermont",
         "va": "Virginia", "wa": "Washington", "wv": "West Virginia", "wi": "Wisconsin", "wy": "Wyoming"}
GROUPS = [("A", "One statewide list a script can read", "nd sd ky ok id wv nc va wa md al la nm sc de vt hi me tx"),
          ("B", "A statewide list exists but needs John's browser first", "in ga ri nh ma nv"),
          ("C", "The state lists part of the local ballot; the rest is county by county", "mi mo ne wy co ut ar or il fl ct"),
          ("D", "County by county only", "wi ia oh mt tn ks az ms nj ca ny ak pa")]
FIRST = ["in", "ga", "ri", "nh", "ma"]      # one save unlocks a whole state


def cell(t):
    return (t or "").replace("|", "/").replace("\n", " ").strip()


out = ["# County and local races on the ballot: where each state stands", "",
       f"Updated {state['updated']}. Saved version: {state['version']}. Minnesota is loaded in full (4,395 county and local races).", "",
       "This file is kept by Claude during the build. The first part is the list of things only your own browser can get;",
       "the second is the state-by-state picture from the scouting pass (2026-09-30) and what has been loaded since.", "",
       "## Waiting on you", "",
       "Save each file into the folder named (make the folder if it is not there). Never mind the ones marked optional.",
       "The loaders read whatever is there the next time they run; nothing else is needed from you.", "",
       "### First: one save each unlocks a whole state", ""]


BUILT = os.path.join(HERE, "build_all.json")
built = json.load(open(BUILT, encoding="utf-8")) if os.path.exists(BUILT) else {}


def items(code):
    rows = []
    if code in built:       # once a state's loader is written, its own list of what it waits for replaces the scout's
        needs = built[code].get("needs_john", [])
    else:
        needs = have.get(code, {}).get("needs_john", [])
    for n in needs:
        rows.append(f"- **{NAMES[code]}**: <{n['url']}>\n  - What to do: {n['action']}\n  - Save as: `{n['save_as']}`")
    return rows


for code in FIRST:
    out += items(code)
out += ["", "### Later: single counties, needed when that state's county-by-county wave comes", ""]
for code in sorted(have, key=lambda c: NAMES[c]):
    if code not in FIRST:
        out += items(code)
out += ["", "### Still waiting from before (the Congress and state pages)", "",
        "Tennessee (four files), Kansas (Candidate List page), Georgia (Qualified Candidates.csv), Arizona, Nevada, Massachusetts, Rhode Island and",
        "New Hampshire browser saves; Indiana's broken list link; Minnesota's August 11 primary results files; confirming Minnesota House 26A",
        "(Aaron Repinski = Ripper Repinski); whether to set up a Meta Ad Library token; the api.data.gov key (`Save FEC key.bat`).", ""]

out += ["## State by state", ""]
for letter, title, codes in GROUPS:
    out += [f"### {title}", "", "| State | Loaded? | On the November 3 ballot | The official source | Size |", "| --- | --- | --- | --- | --- |"]
    for code in codes.split():
        r = have[code]
        out.append(f"| {NAMES[code]} | {cell(state['loaded'].get(code, 'not yet'))} | {cell(r['on_nov_ballot'])} | {cell(r['source'])} | {cell(r['est_size'])} |")
    out.append("")
out += ["## What the scouts said about elections held at another time", ""]
for code in sorted(have, key=lambda c: NAMES[c]):
    out.append(f"- **{NAMES[code]}**: {cell(have[code]['not_on_nov_ballot'])}")
out.append("")
path = os.path.join(PROJECT, "ballot_local_status.md")
open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out))
print(path, len("\n".join(out)), "characters")
