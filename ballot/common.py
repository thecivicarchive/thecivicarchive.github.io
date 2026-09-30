"""
ballot/common.py - the parts every On The Ballot loader shares: the database layout, race keys, party codes, names
and the record of where each list came from.

The database is ballot_2026.sqlite, apart from congress_119.sqlite: the record of the 119th Congress is never
touched by the ballot pipeline. Tables:

  races            one row per race on the ballot: the office, the state, the district (House) or the class
                   (Senate), whether it is a special election for the rest of a term, and who holds the seat today
  candidates       one row per candidate per election in a race: the general election, and the primaries or
                   runoffs that chose the nominees, with the name and party exactly as the official list prints
                   them, ballot order where the list gives it, votes where official results give them, and the
                   candidate's FEC number and Bioguide id where they can be matched
  ballot_sources   every file a list or a result came from: the agency, its title, its address, when it was
                   published and fetched, its SHA-256 and how many rows it gave
  state_notes      what a reader should know about a state's ballot this year (new district lines, primaries moved)
  fec26_*          the 2026 cycle from the FEC's bulk files, for every House and Senate candidate (see fec26.py)

No address, telephone number, e-mail or treasurer's name from any file is ever stored.
"""

import datetime as dt
import hashlib
import os
import re
import sqlite3
import unicodedata

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "ballot_2026.sqlite")
CACHE = os.path.join(HERE, "ballot_cache")
CYCLE = 2026
GENERAL = "2026-11-03"

SCHEMA = """
CREATE TABLE IF NOT EXISTS races (
  race_id TEXT PRIMARY KEY, level TEXT NOT NULL, office TEXT NOT NULL, state TEXT NOT NULL, district TEXT,
  seat_class INTEGER, special INTEGER NOT NULL DEFAULT 0, holder TEXT, holder_name TEXT, holder_party TEXT,
  general_date TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS candidates (
  race_id TEXT NOT NULL, election TEXT NOT NULL, election_date TEXT, name TEXT NOT NULL, party TEXT, party_code TEXT,
  ballot_order INTEGER, incumbent INTEGER NOT NULL DEFAULT 0, write_in INTEGER NOT NULL DEFAULT 0,
  votes INTEGER, pct REAL, outcome TEXT, fec_id TEXT, bioguide_id TEXT, source_id TEXT, note TEXT,
  PRIMARY KEY (race_id, election, name));
CREATE INDEX IF NOT EXISTS idx_candidates_fec ON candidates (fec_id);
CREATE TABLE IF NOT EXISTS ballot_sources (
  source_id TEXT PRIMARY KEY, level TEXT, state TEXT, kind TEXT, agency TEXT, title TEXT, url TEXT,
  published TEXT, fetched TEXT, sha256 TEXT, rows INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS list_gaps (
  race_id TEXT PRIMARY KEY, state TEXT NOT NULL, reason TEXT);
CREATE TABLE IF NOT EXISTS state_notes (
  state TEXT PRIMARY KEY, lines_changed INTEGER NOT NULL DEFAULT 0, note TEXT, source_title TEXT, source_url TEXT, as_of TEXT);
CREATE TABLE IF NOT EXISTS fec26_candidates (
  cand_id TEXT PRIMARY KEY, name TEXT, party TEXT, office TEXT, state TEXT, district TEXT, ici TEXT, status TEXT, pcc TEXT);
CREATE TABLE IF NOT EXISTS fec26_totals (
  cand_id TEXT PRIMARY KEY, receipts REAL, from_individuals REAL, from_committees REAL, from_party REAL, from_candidate REAL,
  candidate_loans REAL, other_loans REAL, transfers_in REAL, disbursements REAL, cash_on_hand REAL, coverage_end TEXT);
CREATE TABLE IF NOT EXISTS fec26_committees (
  cmte_id TEXT PRIMARY KEY, name TEXT, designation TEXT, type TEXT, party TEXT, org_type TEXT, connected_org TEXT, cand_id TEXT);
CREATE TABLE IF NOT EXISTS fec26_gifts (
  sub_id INTEGER PRIMARY KEY, cmte_id TEXT NOT NULL, cand_id TEXT NOT NULL, kind TEXT NOT NULL, fec_type TEXT, election TEXT,
  date TEXT, amount REAL NOT NULL, earmark INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_fec26_gifts_cand ON fec26_gifts (cand_id, kind);
"""

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}


def connect(path=DB):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def house_id(state, district):
    """2026-TX-H07; an at-large seat is district 00."""
    return f"{CYCLE}-{state}-H{int(district or 0):02d}"


def senate_id(state, seat_class):
    return f"{CYCLE}-{state}-S{int(seat_class)}"


def party_code(label):
    """A one-letter code for colour only; the page always prints the party exactly as the official list does."""
    t = (label or "").strip().lower()
    if not t:
        return "O"
    if "write" in t:
        return "W"
    if "democrat" in t or t in ("dem", "d", "dfl"):
        return "D"
    if "republican" in t or t in ("rep", "r", "gop"):
        return "R"
    if "libertarian" in t or t in ("lib", "lpf", "l"):
        return "L"
    if "green" in t or t in ("grn", "g"):
        return "G"
    if "no party" in t or "independent" in t or "nonpartisan" in t or t in ("npp", "npa", "ind", "i", "una", "unaffiliated", "none"):
        return "I"
    return "O"


def fold(text):
    """Letters only, lower case, accents folded: for matching names, never for showing them."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]+", " ", t.lower()).strip()


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "2nd", "3rd", "4th", "nd", "rd", "th", "md", "phd", "esq", "dds", "dr", "mr", "mrs", "ms"}


def name_parts(name):
    """(given names, family name) from a name written 'First M. Last', 'LAST, FIRST M' or 'Last Jr.'; suffixes set aside."""
    raw = (name or "").strip()
    if "," in raw:
        last, _, first = raw.partition(",")
        words = [w for w in fold(first).split() if w not in SUFFIXES]
        family = [w for w in fold(last).split() if w not in SUFFIXES]
        return words, " ".join(family)
    words = [w for w in fold(raw).split() if w not in SUFFIXES]
    if not words:
        return [], ""
    return words[:-1], words[-1]


def record_source(con, source_id, *, path, level, state, kind, agency, title, url, published="", rows=0, note=""):
    """Say exactly which file a list came from: its address, when it was published and fetched, and its fingerprint."""
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest() if path and os.path.exists(path) else ""
    fetched = dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d") if path and os.path.exists(path) else ""
    con.execute("INSERT OR REPLACE INTO ballot_sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (source_id, level, state, kind, agency, title, url, published, fetched, digest, rows, note))
