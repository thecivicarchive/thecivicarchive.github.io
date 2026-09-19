#!/usr/bin/env python3
"""
score_bills.py
==============
Rates bills from a congress_catalog.py SQLite database against rubric_v1.md and writes the
results to the `ratings` table with full provenance (rubric version, model, input hash).

The model never sees sponsor names, parties, cosponsor counts or vote tallies: the prompt is
built blind. Party backing is computed from the vote record instead (rubric section 4).

Python 3.9+, standard library only. Needs ANTHROPIC_API_KEY in the environment for live calls.

Usage
-----
  # 1. See exactly what the model would be asked, without calling anything
  python score_bills.py --db congress_119.sqlite --test-set enacted:25 --dry-run

  # 2. Score the calibration set (first 25 enacted laws), synchronously
  python score_bills.py --db congress_119.sqlite --test-set enacted:25

  # 3. Score everything at half price with the Batch API, then collect the results later
  python score_bills.py --db congress_119.sqlite --all --batch
  python score_bills.py --db congress_119.sqlite --collect msgbatch_xxxxxxxx

  # 4. Party-label swap test on 30 bills (rubric section 10.2)
  python score_bills.py --db congress_119.sqlite --test-set enacted:30 --bias-check

  # 5. Load human-review corrections or ratings produced elsewhere; export for the website
  python score_bills.py --db congress_119.sqlite --import review.json --rater "J. reviewer"
  python score_bills.py --db congress_119.sqlite --export-json site_ratings.json
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com")
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"
AXES_FROM_MODEL = ("income", "households_business", "timing", "rights", "plain_language")
RIGHTS_FLAGS = {"preempts_state_law", "limits_lawsuits", "expands_lawsuits", "requires_arbitration",
                "delegates_to_agency", "blocks_agency_rule", "expands_detention_or_penalties", "expands_enforcement_power",
                "shifts_costs_to_states", "changes_benefit_eligibility", "retroactive", "emergency_or_waiver_power"}
MAGNITUDES = {"none", "small", "moderate", "large", "major"}
JARGON = re.compile(r"\b(leverage|framework|stakeholders?|reconciliation|means-tested|CRA)\b", re.I)


def log(*a):
    print(*a, flush=True)


# ----------------------------------------------------------------------------- selection
def select_bills(con, args):
    if args.bill:
        q = f"SELECT bill_key FROM bills WHERE bill_key IN ({','.join('?' * len(args.bill))})"
        return [r[0] for r in con.execute(q, args.bill)]
    if args.test_set:
        kind, _, n = args.test_set.partition(":")
        n = int(n or 25)
        if kind == "enacted":
            rows = con.execute("SELECT bill_key, law_number FROM bills WHERE law_number <> ''").fetchall()
            rows.sort(key=lambda r: [int(x) for x in re.findall(r"\d+", r[1])])   # by P.L. number
            return [r[0] for r in rows[:n]]
        if kind == "floor":
            return [r[0] for r in con.execute(
                "SELECT bill_key FROM bills WHERE passed_house = 1 OR passed_senate = 1 "
                "ORDER BY latest_action_date DESC LIMIT ?", (n,))]
        sys.exit("--test-set must be enacted:N or floor:N")
    if args.where:
        return [r[0] for r in con.execute(f"SELECT bill_key FROM bills WHERE {args.where}")]
    if args.all:
        return [r[0] for r in con.execute("SELECT bill_key FROM bills ORDER BY bill_type, number")]
    sys.exit("Choose bills with --test-set, --bill, --where or --all")


# ----------------------------------------------------------------------------- blinded input
def bill_input(con, key, max_chars):
    b = con.execute("SELECT * FROM bills WHERE bill_key = ?", (key,)).fetchone()
    if b is None:
        return None, None
    cols = [d[0] for d in con.execute("SELECT * FROM bills LIMIT 0").description]
    b = dict(zip(cols, b))
    summ = con.execute("SELECT version_code, action_date, action_desc, text_plain FROM summaries "
                       "WHERE bill_key = ? ORDER BY action_date DESC, version_code DESC LIMIT 1", (key,)).fetchone()
    subjects = [r[0] for r in con.execute("SELECT subject FROM subjects WHERE bill_key = ? ORDER BY subject", (key,))]
    committees = [r[0] for r in con.execute(
        "SELECT DISTINCT committee FROM committee_actions WHERE bill_key = ? AND committee <> ''", (key,))]
    cbo = [r for r in con.execute("SELECT pub_date, title, url FROM cbo_estimates WHERE bill_key = ?", (key,))]
    text = summ[3] if summ else ""
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars] + "\n[summary truncated for length]"
    # Blinding: no sponsor, no party, no cosponsor counts, no vote tallies, no member names.
    lines = [
        f"Measure: {b['display_id']} ({b['kind']}, {b['congress']}th Congress)",
        f"Title: {b['title']}",
        f"Status: {b['status']}  |  Outcome: {b['outcome']}" + (f"  |  Law: {b['law_kind']} Law {b['law_number']}" if b['law_number'] else ""),
        f"Introduced: {b['introduced_date']}   Latest action: {b['latest_action_date']} - {b['latest_action']}",
        f"Policy area: {b['policy_area'] or 'n/a'}",
        f"CRS subject terms: {', '.join(subjects) if subjects else 'none'}",
        f"Committees: {'; '.join(committees) if committees else 'none recorded'}",
        f"Official cost estimates on file: " + ("; ".join(f"CBO {d} - {t} ({u})" for d, t, u in cbo) if cbo else "none"),
        "",
        f"Latest CRS summary ({summ[2]}, {summ[1]})" if summ else "CRS summary: none available",
        text or "(no summary text)",
    ]
    return b, "\n".join(lines) + ("\n\n[Note: summary was truncated]" if truncated else "")


def system_prompt(rubric_text):
    return (
        "You rate U.S. federal legislation for a public, non-partisan website. Follow the rubric "
        "below exactly. You are deliberately not told who sponsored the bill, which party supported "
        "it, or how the votes went; do not use or guess at that information, and do not mention "
        "parties, members or the President. Judge only the bill's provisions and their likely "
        "effects. Respond with a single JSON object matching section 9 of the rubric and nothing "
        "else: no preamble, no markdown fences.\n\n=== RUBRIC ===\n" + rubric_text)


def input_hash(system_text, user_text, model):
    return hashlib.sha256(f"{model}\n{system_text}\n{user_text}".encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------- API
def api_headers():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY is not set (use --dry-run to see the prompts without calling the API)")
    return {"x-api-key": key, "anthropic-version": API_VERSION, "content-type": "application/json"}


def api_call(path, payload=None, method=None, retries=4):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(f"{API}{path}", data=data, headers=api_headers(), method=method or ("POST" if data else "GET"))
    last = None
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code in (400, 401, 403, 404):
                sys.exit(f"API error {e.code}: {body[:500]}")
            last = f"{e.code}: {body[:300]}"
        except (URLError, TimeoutError, OSError) as e:
            last = str(e)
        time.sleep(3 * 2 ** attempt)
    raise RuntimeError(f"API call failed after retries: {last}")


def message_params(model, system_text, user_text, max_tokens=3000):
    return {"model": model, "max_tokens": max_tokens, "temperature": 0,
            "system": [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user_text}]}


def extract_json(resp):
    text = "".join(c.get("text", "") for c in resp.get("content", []) if c.get("type") == "text").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def score_one(model, system_text, user_text):
    resp = api_call("/v1/messages", message_params(model, system_text, user_text))
    try:
        return extract_json(resp), resp.get("usage", {})
    except (ValueError, json.JSONDecodeError):
        fix = message_params(model, system_text, user_text)
        fix["messages"] += [{"role": "assistant", "content": "".join(
            c.get("text", "") for c in resp.get("content", []))},
            {"role": "user", "content": "That was not valid JSON. Return only the JSON object."}]
        resp2 = api_call("/v1/messages", fix)
        return extract_json(resp2), resp2.get("usage", {})


# ----------------------------------------------------------------------------- validation
def clamp(v, lo=-100, hi=100):
    if v is None:
        return None
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return None


def fk_grade(text):
    """Flesch-Kincaid grade level (rough; good enough to flag jargon-heavy sentences)."""
    words = re.findall(r"[A-Za-z']+", text or "")
    sentences = max(1, len(re.findall(r"[.!?]+", text or "")) or 1)
    if not words:
        return 0.0
    syl = sum(max(1, len(re.findall(r"[aeiouy]+", w.lower()))) for w in words)
    return round(0.39 * len(words) / sentences + 11.8 * syl / len(words) - 15.59, 1)


def validate(obj):
    """Normalize the model's JSON into ratings rows; returns (rows_by_axis, problems)."""
    problems, rows = [], {}
    for axis in ("income", "households_business"):
        a = obj.get(axis) or {}
        grade = str(a.get("evidence_grade", "N")).upper()[:1]
        if grade not in "ABCN":
            problems.append(f"{axis}: bad evidence grade {grade!r}")
            grade = "C"
        conf = clamp(a.get("confidence"), 0, 1) or 0.0
        if grade == "C":
            conf = min(conf, 0.6)
        pos = None if grade == "N" else clamp(a.get("position"))
        row = {"position": pos, "position_low": clamp(a.get("position_low")), "position_high": clamp(a.get("position_high")),
               "position2": clamp(a.get("position2")) if axis == "households_business" else None,
               "magnitude_label": (a.get("magnitude_label") or "none") if a.get("magnitude_label") in MAGNITUDES else "none",
               "magnitude_note": a.get("magnitude_note", ""), "evidence_grade": grade, "confidence": conf,
               "justification": a.get("justification", ""), "sources_json": json.dumps(a.get("sources", [])),
               "flags_json": json.dumps({"business_tag": a.get("business_tag")} if axis == "households_business" else {}),
               "plain_json": None}
        if grade != "N" and len(row["justification"]) < 40:
            problems.append(f"{axis}: justification missing or too short")
        if JARGON.search(row["justification"]):
            problems.append(f"{axis}: jargon in justification ({JARGON.search(row['justification']).group(0)})")
        rows[axis] = row
    t = obj.get("timing") or {}
    tp = t.get("plain_json") or {}
    if "sunset" not in tp:
        problems.append("timing: sunset not stated")
    rows["timing"] = {"position": None, "position_low": None, "position_high": None, "position2": None,
                      "magnitude_label": None, "magnitude_note": "", "evidence_grade": str(t.get("evidence_grade", "C"))[:1],
                      "confidence": None, "justification": t.get("justification", ""), "sources_json": "[]",
                      "flags_json": "{}", "plain_json": json.dumps(tp)}
    r = obj.get("rights") or {}
    flags = [f for f in (r.get("flags") or []) if isinstance(f, dict) and f.get("flag") in RIGHTS_FLAGS]
    bad = [f.get("flag") for f in (r.get("flags") or []) if isinstance(f, dict) and f.get("flag") not in RIGHTS_FLAGS]
    if bad:
        problems.append(f"rights: unknown flags dropped {bad}")
    rows["rights"] = {"position": None, "position_low": None, "position_high": None, "position2": None,
                      "magnitude_label": None, "magnitude_note": "", "evidence_grade": str(r.get("evidence_grade", "C"))[:1],
                      "confidence": None, "justification": r.get("justification", ""), "sources_json": "[]",
                      "flags_json": json.dumps({"flags": flags, "election_rules": bool(r.get("election_rules"))}),
                      "plain_json": None}
    p = (obj.get("plain_language") or {}).get("plain_json") or {}
    ify = p.get("if_you_are") or {}
    for who in ("worker", "parent", "retiree", "small_business_owner", "disability"):
        if not ify.get(who):
            problems.append(f"plain_language: if_you_are.{who} missing")
    one = p.get("one_sentence", "")
    all_plain = " ".join([one, p.get("what_it_does_not_do", "")] + [str(v) for v in ify.values()])
    grade_level = fk_grade(all_plain)
    if len(one.split()) > 34:
        problems.append("plain_language: one_sentence over 30 words")
    if grade_level > 10:
        problems.append(f"plain_language: reading level {grade_level} across the plain-language fields (target <= 8)")
    rows["plain_language"] = {"position": None, "position_low": None, "position_high": None, "position2": None,
                              "magnitude_label": None, "magnitude_note": "", "evidence_grade": None, "confidence": None,
                              "justification": "", "sources_json": "[]",
                              "flags_json": json.dumps({"readability_grade": grade_level}), "plain_json": json.dumps(p)}
    return rows, problems


# ----------------------------------------------------------------------------- backing (computed)
def party_rates(split):
    """'D 220-1, R 0-212' -> {'D': (220, 1), 'R': (0, 212)}; Independents fold into D."""
    out = {}
    for m in re.finditer(r"\b([A-Z])\w*\s+(\d+)\s*-\s*(\d+)", split or ""):
        p, y, n = m.group(1), int(m.group(2)), int(m.group(3))
        p = "D" if p in ("D", "I") else ("R" if p == "R" else None)
        if p:
            oy, on = out.get(p, (0, 0))
            out[p] = (oy + y, on + n)
    return out


def member_vote_split(con, vote_id):
    """Party split from member-level votes (preferred): 'D 46-156, R 217-0' or '' when none loaded."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'member_votes'").fetchone():
        return ""
    tally = {}
    for party, pos in con.execute("SELECT party, position FROM member_votes WHERE vote_id = ?", (vote_id,)):
        p = "D" if party in ("D", "I", "ID") else ("R" if party == "R" else None)
        if p and pos in ("Yea", "Nay", "Aye", "No"):
            tally[(p, pos in ("Yea", "Aye"))] = tally.get((p, pos in ("Yea", "Aye")), 0) + 1
    return ", ".join(f"{p} {tally.get((p, True), 0)}-{tally.get((p, False), 0)}" for p in ("D", "R")
                     if tally.get((p, True), 0) + tally.get((p, False), 0))


def compute_backing(con, key):
    votes = [(c, member_vote_split(con, vid) or split, d) for vid, c, split, d in con.execute(
        "SELECT vote_id, chamber, party_split, vote_date FROM floor_votes WHERE bill_key = ? AND key_vote = 1 "
        "AND category = 'Passage' AND result IN ('Passed', 'Agreed to', 'Failed') ORDER BY vote_date", (key,))]
    votes = [v for v in votes if v[1]]
    positions, used, minority = [], [], []
    for chamber, split, date in votes:
        rates = party_rates(split)
        if "D" in rates and "R" in rates and sum(rates["D"]) and sum(rates["R"]):
            r = rates["R"][0] / sum(rates["R"])
            d = rates["D"][0] / sum(rates["D"])
            positions.append(100 * (r - d))
            minority.append(min(r, d))
            used.append(f"{chamber} {date}: R {rates['R'][0]}-{rates['R'][1]}, D {rates['D'][0]}-{rates['D'][1]}")
    note, grade = "", "A"
    if positions:
        pos = sum(positions) / len(positions)
        m = sum(minority) / len(minority)
        label = "bipartisan" if m >= 0.5 else ("one party plus crossover" if m >= 0.15 else "party-line")
    elif any(v for v in con.execute("SELECT yeas, nays FROM floor_votes WHERE bill_key = ? AND key_vote = 1 AND category = 'Passage' "
                                    "AND yeas IS NOT NULL AND nays IS NOT NULL AND yeas + nays > 0 AND yeas * 1.0 / (yeas + nays) >= 0.85", (key,))):
        # A recorded passage vote with 85%+ in favor needs majorities of both parties in a closely divided chamber.
        tallies = "; ".join(f"{c} {d}: {y}-{n}" for c, d, y, n in con.execute(
            "SELECT chamber, vote_date, yeas, nays FROM floor_votes WHERE bill_key = ? AND key_vote = 1 AND category = 'Passage' AND yeas IS NOT NULL", (key,)))
        return {"position": 0.0, "position_low": None, "position_high": None, "position2": None, "magnitude_label": None,
                "magnitude_note": f"near-unanimous recorded vote ({tallies}); party split not loaded", "evidence_grade": "C", "confidence": 0.7,
                "justification": "bipartisan: a recorded passage vote with at least 85 percent in favor requires most of both parties.",
                "sources_json": json.dumps([{"type": "roll call", "ref": tallies}]), "flags_json": json.dumps({"label": "bipartisan"}), "plain_json": None}
    else:
        cos = con.execute("SELECT m.party, COUNT(*) FROM sponsorships s JOIN members m ON m.bioguide_id = s.bioguide_id "
                          "WHERE s.bill_key = ? AND s.withdrawn_date = '' GROUP BY m.party", (key,)).fetchall()
        tally = {"D": 0, "R": 0}
        for p, n in cos:
            if p in ("D", "I"):
                tally["D"] += n
            elif p == "R":
                tally["R"] += n
        if tally["D"] + tally["R"] == 0:
            return None
        pos = 100 * (tally["R"] - tally["D"]) / (tally["D"] + tally["R"])
        note, grade = f"cosponsor-based (R {tally['R']}, D+I {tally['D']}; no party split on a recorded passage vote)", "C"
        m = min(tally["R"], tally["D"]) / (tally["D"] + tally["R"])
        label = "bipartisan" if m >= 0.3 else ("one party plus crossover" if m >= 0.1 else "party-line")
    return {"position": round(pos, 1), "position_low": None, "position_high": None, "position2": None,
            "magnitude_label": None, "magnitude_note": note or "; ".join(used), "evidence_grade": grade, "confidence": 0.95 if grade == "A" else 0.5,
            "justification": f"{label}: each party's yes-rate on the recorded passage vote(s), R minus D." if grade == "A"
            else f"{label} (cosponsor mix; no party-level vote record available).",
            "sources_json": json.dumps([{"type": "roll call", "ref": u} for u in used]), "flags_json": json.dumps({"label": label}),
            "plain_json": None}


# ----------------------------------------------------------------------------- writing
def open_run(con, method_version, model, rater, scope, notes=""):
    run_id = f"run_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    con.execute("INSERT INTO rating_runs VALUES (?,?,?,?,?,?,?,?)",
                (run_id, method_version, model, rater, dt.datetime.now().isoformat(timespec="seconds"), None, scope, notes))
    return run_id


def write_rating(con, key, axis, row, method_version, run_id, rater, ihash):
    now = dt.datetime.now().isoformat(timespec="seconds")
    cur = con.execute(
        "INSERT INTO ratings (bill_key, axis, method_version, run_id, rater, rated_at, position, position_low, position_high, "
        "position2, position2_low, position2_high, magnitude_label, magnitude_note, evidence_grade, confidence, justification, "
        "sources_json, flags_json, plain_json, input_hash, superseded_by, is_current) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,1)",
        (key, axis, method_version, run_id, rater, now, row.get("position"), row.get("position_low"), row.get("position_high"),
         row.get("position2"), row.get("position2_low"), row.get("position2_high"), row.get("magnitude_label"),
         row.get("magnitude_note"), row.get("evidence_grade"), row.get("confidence"), row.get("justification"),
         row.get("sources_json"), row.get("flags_json"), row.get("plain_json"), ihash))
    new_id = cur.lastrowid
    con.execute("UPDATE ratings SET is_current = 0, superseded_by = ? WHERE bill_key = ? AND axis = ? "
                "AND rating_id <> ? AND is_current = 1", (new_id, key, axis, new_id))
    return new_id


def already_current(con, key, axis, ihash):
    return con.execute("SELECT 1 FROM ratings WHERE bill_key = ? AND axis = ? AND is_current = 1 AND input_hash = ?",
                       (key, axis, ihash)).fetchone() is not None


# ----------------------------------------------------------------------------- import / export
def import_ratings(con, path, method_version, rater):
    """JSON list of {"bill_key":..., "income": {...}, ...} in the rubric's output contract."""
    data = json.load(open(path, encoding="utf-8"))
    run_id = open_run(con, method_version, "import", rater, f"import:{os.path.basename(path)}")
    n = 0
    for item in data:
        key = item["bill_key"]
        if con.execute("SELECT 1 FROM bills WHERE bill_key = ?", (key,)).fetchone() is None:
            stub = item.get("bill_stub") or {}
            con.execute("INSERT INTO bills (bill_key, congress, bill_type, number, display_id, kind, title, outcome, status, "
                        "law_kind, law_number, policy_area, congress_url, loaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (key, stub.get("congress"), stub.get("bill_type"), stub.get("number"), stub.get("display_id", key),
                         stub.get("kind"), stub.get("title"), stub.get("outcome"), stub.get("status"), stub.get("law_kind"),
                         stub.get("law_number"), stub.get("policy_area"), stub.get("congress_url"),
                         dt.datetime.now().isoformat(timespec="seconds")))
        rows, problems = validate(item)
        if "backing" in item:
            b = item["backing"]
            rows["backing"] = {"position": clamp(b.get("position")), "position_low": None, "position_high": None, "position2": None,
                               "magnitude_label": None, "magnitude_note": b.get("magnitude_note", ""),
                               "evidence_grade": b.get("evidence_grade", "A"), "confidence": b.get("confidence"),
                               "justification": b.get("justification", ""), "sources_json": json.dumps(b.get("sources", [])),
                               "flags_json": json.dumps({"label": b.get("label", "")}), "plain_json": None}
        else:
            bk = compute_backing(con, key)
            if bk:
                rows["backing"] = bk
        ihash = hashlib.sha256(json.dumps(item, sort_keys=True).encode("utf-8")).hexdigest()
        for axis, row in rows.items():
            write_rating(con, key, axis, row, method_version, run_id, item.get("rater", rater), ihash)
        n += 1
        if problems:
            log(f"  {key}: " + "; ".join(problems))
    con.execute("UPDATE rating_runs SET finished_at = ? WHERE run_id = ?", (dt.datetime.now().isoformat(timespec="seconds"), run_id))
    con.commit()
    log(f"Imported ratings for {n} bills (run {run_id})")


def backing_pass(con, method_version):
    """Party-backing axis from the roll calls for every measure with a recorded passage vote. No API calls.
    Cosponsor-only estimates are skipped here; they appear only on bills that carry a full rating."""
    keys = [r[0] for r in con.execute("SELECT DISTINCT bill_key FROM floor_votes WHERE key_vote = 1 AND category = 'Passage' "
                                      "AND result IN ('Passed', 'Agreed to', 'Failed') ORDER BY bill_key")]
    run_id = open_run(con, method_version, "none", "computed:roll-calls", "backing-only")
    wrote = kept = skipped = 0
    for key in keys:
        bk = compute_backing(con, key)
        if not bk or (bk["evidence_grade"] != "A" and "near-unanimous" not in (bk["magnitude_note"] or "")):
            skipped += 1
            continue
        ihash = hashlib.sha256(json.dumps(bk, sort_keys=True).encode("utf-8")).hexdigest()
        if already_current(con, key, "backing", ihash):
            kept += 1
            continue
        write_rating(con, key, "backing", bk, method_version, run_id, "computed:roll-calls", ihash)
        wrote += 1
    con.execute("UPDATE rating_runs SET finished_at = ? WHERE run_id = ?", (dt.datetime.now().isoformat(timespec="seconds"), run_id))
    con.commit()
    log(f"Party backing from roll calls: {wrote:,} written, {kept:,} unchanged, {skipped:,} without a usable party split "
        f"({len(keys):,} measures with a recorded passage vote)")


def review_sheet(con, keys, path):
    """Markdown sheet a reviewer fills in: one block per bill, one row per axis, agree/disagree columns."""
    rcols = [d[0] for d in con.execute("SELECT * FROM ratings LIMIT 0").description]
    out = ["# Rating review sheet", "", f"Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}. "
           "Mark each row Agree / Disagree, give a corrected value where you disagree, and note why. "
           "Return the file and load it with `--import` after converting, or record decisions in the ratings table.", ""]
    for key in keys:
        b = con.execute("SELECT display_id, title, status, law_number, congress_url FROM bills WHERE bill_key = ?", (key,)).fetchone()
        if not b:
            continue
        rows = [dict(zip(rcols, r)) for r in con.execute(
            "SELECT * FROM ratings WHERE bill_key = ? AND is_current = 1 ORDER BY CASE axis WHEN 'income' THEN 1 WHEN 'backing' THEN 2 "
            "WHEN 'households_business' THEN 3 WHEN 'timing' THEN 4 WHEN 'rights' THEN 5 ELSE 6 END", (key,))]
        out += [f"## {b[0]} - {b[1]}", f"*{b[2]}*" + (f" - [Congress.gov]({b[4]})" if b[4] else ""), ""]
        if not rows:
            out += ["_No ratings yet._", ""]
            continue
        out += ["| Axis | Rating | Grade / conf. | Justification | Reviewer: Agree? | Corrected value | Why |",
                "|---|---|---|---|---|---|---|"]
        for r in rows:
            ax = r["axis"]
            if ax in ("income", "backing"):
                val = "n/a" if r["position"] is None else f"{r['position']:+.0f}"
                if r["position_low"] is not None and r["position_high"] is not None:
                    val += f" (range {r['position_low']:+.0f} to {r['position_high']:+.0f})"
                if ax == "backing":
                    try:
                        val += " " + json.loads(r["flags_json"] or "{}").get("label", "")
                    except ValueError:
                        pass
                if r["magnitude_label"]:
                    val += f"; {r['magnitude_label']}"
                just = (r["justification"] or "") + (f" _{r['magnitude_note']}_" if r["magnitude_note"] else "")
            elif ax == "households_business":
                h = "n/a" if r["position"] is None else f"{r['position']:+.0f}"
                if r["position_low"] is not None and r["position_high"] is not None:
                    h += f" (range {r['position_low']:+.0f} to {r['position_high']:+.0f})"
                bz = "n/a" if r["position2"] is None else f"{r['position2']:+.0f}"
                if r["position2_low"] is not None and r["position2_high"] is not None:
                    bz += f" (range {r['position2_low']:+.0f} to {r['position2_high']:+.0f})"
                try:
                    tag = json.loads(r["flags_json"] or "{}").get("business_tag") or ""
                except ValueError:
                    tag = ""
                val = f"households {h} / business {bz}" + (f" ({tag})" if tag else "")
                just = (r["justification"] or "") + (f" _{r['magnitude_note']}_" if r["magnitude_note"] else "")
            elif ax == "timing":
                try:
                    pj = json.loads(r["plain_json"] or "{}")
                except ValueError:
                    pj = {}
                val = f"effective: {pj.get('effective', '?')}; sunset: {pj.get('sunset', '?')}; delayed cost: {pj.get('delayed_cost', '?')}"
                just = pj.get("plain", "") + (" " + r["justification"] if r["justification"] else "")
            elif ax == "rights":
                try:
                    fl = json.loads(r["flags_json"] or "{}").get("flags", [])
                except ValueError:
                    fl = []
                val = "; ".join(f"`{f['flag']}`" for f in fl) or "no flags"
                just = " ".join(f.get("plain", "") for f in fl) or (r["justification"] or "")
            else:
                try:
                    pj = json.loads(r["plain_json"] or "{}")
                except ValueError:
                    pj = {}
                val = pj.get("one_sentence", "")
                ify = pj.get("if_you_are") or {}
                just = "; ".join(f"**{k}**: {v}" for k, v in ify.items()) + (f" **Not**: {pj['what_it_does_not_do']}" if pj.get("what_it_does_not_do") else "")
            gc = (r["evidence_grade"] or "") + (f" / {r['confidence']:.2f}" if r["confidence"] is not None else "")
            cell = lambda t: (t or "").replace("|", "\\|").replace("\n", " ")
            out.append(f"| {ax} | {cell(val)} | {gc} | {cell(just)} |  |  |  |")
        out.append("")
    open(path, "w", encoding="utf-8").write("\n".join(out))
    log(f"Wrote review sheet for {len(keys)} bill(s) to {path}")


def export_json(con, path):
    cols = [d[0] for d in con.execute("SELECT * FROM bill_cards LIMIT 0").description]
    cards = [dict(zip(cols, r)) for r in con.execute("SELECT * FROM bill_cards")]
    rcols = [d[0] for d in con.execute("SELECT * FROM ratings LIMIT 0").description]
    by_bill = {}
    for r in con.execute("SELECT * FROM ratings WHERE is_current = 1"):
        d = dict(zip(rcols, r))
        for j in ("sources_json", "flags_json", "plain_json"):
            if d.get(j):
                try:
                    d[j] = json.loads(d[j])
                except ValueError:
                    pass
        by_bill.setdefault(d["bill_key"], {})[d["axis"]] = d
    for c in cards:
        c["ratings"] = by_bill.get(c["bill_key"], {})
        for j in ("plain_json", "timing_json", "rights_flags"):
            if c.get(j):
                try:
                    c[j] = json.loads(c[j])
                except ValueError:
                    pass
    json.dump({"generated": dt.datetime.now().isoformat(timespec="seconds"), "bills": cards}, open(path, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    log(f"Exported {len(cards)} bill cards to {path}")


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--rubric", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "rubric_v1.md"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--test-set", help="enacted:N (first N public laws) or floor:N (last N with floor passage)")
    ap.add_argument("--bill", nargs="*", help="bill keys, e.g. hr1-119 s5-119")
    ap.add_argument("--where", help="SQL condition on the bills table")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="write the blinded prompts to ./scoring_prompts and stop")
    ap.add_argument("--batch", action="store_true", help="submit through the Message Batches API (50%% cheaper)")
    ap.add_argument("--collect", help="fetch a finished batch by id and write its ratings")
    ap.add_argument("--bias-check", action="store_true", help="party-label swap test on the selected bills")
    ap.add_argument("--force", action="store_true", help="re-score even when the input has not changed")
    ap.add_argument("--max-summary-chars", type=int, default=14000)
    ap.add_argument("--import", dest="import_path", help="load ratings from a JSON file (human review or other rater)")
    ap.add_argument("--rater", default="", help="name recorded for imported ratings")
    ap.add_argument("--export-json", help="write bill cards + current ratings for the website")
    ap.add_argument("--review-md", help="write a human review sheet (Markdown) for the selected bills' current ratings")
    ap.add_argument("--backing-only", action="store_true",
                    help="compute the party-backing axis from roll calls for every measure with a recorded passage vote (no API)")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys = OFF")
    rubric = open(args.rubric, encoding="utf-8").read()
    m = re.search(r"method_version:\s*(v[\d.]+)", rubric)
    method_version = m.group(1) if m else "v?"
    sys_text = system_prompt(rubric)

    if args.import_path:
        import_ratings(con, args.import_path, method_version, args.rater or "import")
    if args.backing_only:
        backing_pass(con, method_version)
    if args.export_json:
        export_json(con, args.export_json)
    if args.review_md:
        review_sheet(con, select_bills(con, args), args.review_md)
    if args.import_path or args.export_json or args.review_md or args.backing_only:
        if not (args.test_set or args.bill or args.where or args.all or args.collect) or args.review_md:
            return

    if args.collect:
        collect_batch(con, args.collect, method_version, args.model)
        return

    keys = select_bills(con, args)
    log(f"{len(keys)} bill(s) selected; rubric {method_version}; model {args.model}")

    if args.bias_check:
        bias_check(con, keys, sys_text, args)
        return

    prompts = []
    for key in keys:
        b, user_text = bill_input(con, key, args.max_summary_chars)
        if b is None:
            continue
        ihash = input_hash(sys_text, user_text, args.model)
        if not args.force and not args.dry_run and all(already_current(con, key, ax, ihash) for ax in AXES_FROM_MODEL):
            log(f"  {key}: unchanged input, skipping (use --force to re-score)")
            continue
        prompts.append((key, user_text, ihash))

    if args.dry_run:
        os.makedirs("scoring_prompts", exist_ok=True)
        open(os.path.join("scoring_prompts", "_system_prompt.txt"), "w", encoding="utf-8").write(sys_text)
        for key, user_text, ihash in prompts:
            open(os.path.join("scoring_prompts", f"{key}.txt"), "w", encoding="utf-8").write(user_text)
        est_in = sum(len(sys_text) // 4 + len(u) // 4 for _k, u, _h in prompts)
        log(f"Wrote {len(prompts)} prompt(s) to ./scoring_prompts (system prompt shared, ~{len(sys_text) // 4:,} tokens; "
            f"per-bill input ~{est_in // max(1, len(prompts)):,} tokens on average). Nothing was sent to the API.")
        return

    if not prompts:
        log("Nothing to score.")
        return
    run_id = open_run(con, method_version, args.model, f"model:{args.model}",
                      args.test_set or ("all" if args.all else "selection"), "batch" if args.batch else "sync")
    con.commit()

    if args.batch:
        reqs = [{"custom_id": key, "params": message_params(args.model, sys_text, user_text)} for key, user_text, _h in prompts]
        for i in range(0, len(reqs), 10000):
            resp = api_call("/v1/messages/batches", {"requests": reqs[i:i + 10000]})
            open("batches.log", "a", encoding="utf-8").write(json.dumps(
                {"batch_id": resp.get("id"), "run_id": run_id, "submitted": dt.datetime.now().isoformat(timespec="seconds"),
                 "hashes": {k: h for k, _u, h in prompts[i:i + 10000]}}) + "\n")
            log(f"Submitted batch {resp.get('id')} with {min(10000, len(reqs) - i)} requests; "
                f"collect later with --collect {resp.get('id')}")
        return

    usage_in = usage_out = 0
    for n, (key, user_text, ihash) in enumerate(prompts, 1):
        obj, usage = score_one(args.model, sys_text, user_text)
        rows, problems = validate(obj)
        bk = compute_backing(con, key)
        if bk:
            rows["backing"] = bk
        for axis, row in rows.items():
            write_rating(con, key, axis, row, method_version, run_id, f"model:{args.model}", ihash)
        con.commit()
        usage_in += usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
        usage_out += usage.get("output_tokens", 0)
        inc = rows["income"]
        log(f"  [{n}/{len(prompts)}] {key}: income {inc['position']} ({inc['evidence_grade']}), "
            f"households {rows['households_business']['position']} / business {rows['households_business']['position2']}"
            + (f"  | issues: {'; '.join(problems)}" if problems else ""))
    con.execute("UPDATE rating_runs SET finished_at = ?, notes = ? WHERE run_id = ?",
                (dt.datetime.now().isoformat(timespec="seconds"), f"tokens in {usage_in:,} / out {usage_out:,}", run_id))
    con.commit()
    log(f"Done: {len(prompts)} bills rated (run {run_id}); tokens in {usage_in:,}, out {usage_out:,}")


def collect_batch(con, batch_id, method_version, model):
    status = api_call(f"/v1/messages/batches/{batch_id}")
    if status.get("processing_status") != "ended":
        log(f"Batch {batch_id} is {status.get('processing_status')}; counts: {status.get('request_counts')}. Try again later.")
        return
    hashes, run_id = {}, None
    if os.path.exists("batches.log"):
        for line in open("batches.log", encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("batch_id") == batch_id:
                hashes, run_id = rec.get("hashes", {}), rec.get("run_id")
    run_id = run_id or open_run(con, method_version, model, f"model:{model}", f"batch:{batch_id}")
    req = Request(status["results_url"], headers=api_headers())
    with urlopen(req, timeout=600) as r:
        lines = r.read().decode("utf-8").splitlines()
    ok = bad = 0
    for line in lines:
        item = json.loads(line)
        key, result = item["custom_id"], item["result"]
        if result.get("type") != "succeeded":
            bad += 1
            log(f"  {key}: {result.get('type')} - {json.dumps(result.get('error', ''))[:200]}")
            continue
        try:
            obj = extract_json(result["message"])
        except (ValueError, json.JSONDecodeError):
            bad += 1
            log(f"  {key}: response was not valid JSON; re-run this bill synchronously with --bill {key} --force")
            continue
        rows, problems = validate(obj)
        bk = compute_backing(con, key)
        if bk:
            rows["backing"] = bk
        for axis, row in rows.items():
            write_rating(con, key, axis, row, method_version, run_id, f"model:{model}", hashes.get(key, ""))
        ok += 1
        if problems:
            log(f"  {key}: " + "; ".join(problems))
    con.execute("UPDATE rating_runs SET finished_at = ? WHERE run_id = ?", (dt.datetime.now().isoformat(timespec="seconds"), run_id))
    con.commit()
    log(f"Collected batch {batch_id}: {ok} rated, {bad} failed (run {run_id})")


def bias_check(con, keys, sys_text, args):
    """Rubric 10.2: does adding a party label move the income or households/business score?"""
    variants = {"blind": "", "dem": "\nSponsor's party: Democratic\n", "rep": "\nSponsor's party: Republican\n"}
    shifts = {"income": [], "households": [], "business": []}
    for key in keys:
        b, user_text = bill_input(con, key, args.max_summary_chars)
        if b is None:
            continue
        got = {}
        for name, extra in variants.items():
            obj, _u = score_one(args.model, sys_text, user_text + extra)
            rows, _p = validate(obj)
            got[name] = (rows["income"]["position"], rows["households_business"]["position"], rows["households_business"]["position2"])
        for i, ax in enumerate(("income", "households", "business")):
            vals = [got[v][i] for v in variants if got[v][i] is not None]
            if len(vals) == 3:
                shifts[ax].append(max(abs(got["dem"][i] - got["blind"][i]), abs(got["rep"][i] - got["blind"][i])))
        log(f"  {key}: blind/dem/rep income = {got['blind'][0]}/{got['dem'][0]}/{got['rep'][0]}; "
            f"households = {got['blind'][1]}/{got['dem'][1]}/{got['rep'][1]}")
    for ax, vals in shifts.items():
        if vals:
            mean = sum(vals) / len(vals)
            log(f"{ax}: mean absolute shift {mean:.1f} points over {len(vals)} bills -> {'PASS' if mean <= 10 else 'FAIL (rubric 10.2)'}")


if __name__ == "__main__":
    main()
