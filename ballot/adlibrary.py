"""
ballot/adlibrary.py - the ads themselves, as Google's public ad library holds them, tied to the 2026 candidates. The
page links to each ad where Google hosts it and never copies one.

Source: Google's Political Ads Transparency Report bundle (public, keyless, about 307 MB), downloaded once a week into
ballot_cache/adlibrary/ and read in place with zipfile, one row at a time. Only these of its columns are read:

  google-political-ads-advertiser-stats.csv  Advertiser_ID, Advertiser_Name, Public_IDs_List (the FEC number, tax number
                                             or state registration Google verified the advertiser under), Regions
  google-political-ads-creative-stats.csv    Ad_ID, Ad_URL, Ad_Type, Regions, Advertiser_ID, Advertiser_Name,
                                             Date_Range_Start, Date_Range_End, Impressions, Geo_Targeting_Included,
                                             Geo_Targeting_Excluded, Spend_Range_Min_USD, Spend_Range_Max_USD
  advertiser_id_mapping.csv                  OldAdvertiserId, NewAdvertiserId (an ad filed under a retired number)
  google-political-ads-updated.csv           when Google last refreshed the report

The age and gender targeting, the campaign lists, the other currencies and the declared-stats file (which carries
promoters' addresses) are never read.

How an ad is tied to a candidate, and what its label rests on:

  campaign  the advertiser is the candidate's own principal or authorized committee: Google verified it under that
            committee's FEC number (checked against the 2026 committee file, or the latest of the 2016-2024 committee
            files load_donors keeps in fec_cache/, for a number Google has held since an earlier race), or under the
            candidate's own FEC candidate number; or, when Google gives no FEC number the FEC's files know, its name is
            the committee's name as the FEC files it, or the candidate's full name with "for Congress", "for Senate" or
            "for <state>", and no other 2026 candidate shares that name. An advertiser whose FEC number points to some
            other committee or candidate number (a member's House committee, when the race is for the Senate) is never
            tied by name. Stance is left empty: it is the campaign's own ad.
  outside   the advertiser is a committee that reported independent spending in the race to the FEC (ad_spenders,
            from ballot/ads.py): tied by the FEC number Google verified it under, or, when Google gives none, by the
            committee's name as the FEC files it. That committee's FEC number is kept in ad_links.spender, so the page
            can quote its own filings. The ad is linked to each candidate in the race that the committee
            reported spending for or against, and the stance is the committee's own FEC declaration toward that
            candidate ("for", "against", or "for and against" when it reported both), with the amounts in the basis.
            Which candidate a particular outside ad is about is not in either record, and is never guessed. Where
            Google's targeting names states and the race's state is not among them, the ad ran elsewhere and is not
            linked to that race.

Only ads that ran in the United States from 2025-01-01 on. states holds the two-letter codes of the states Google's
targeting names, "US" when the ad was aimed at the whole country, or "" when the record names no state (a media
market, or nothing). Advertisers are named when they are committees, parties, candidates or organizations; a private
person who is not a candidate is stored as "a person (not named here)", as the donor rule has it.
"""

import csv
import io
import os
import re
import unicodedata
import zipfile
from collections import defaultdict

from ballot.common import CACHE, HERE, STATE_NAMES, name_parts, record_source
from states import net

URL = "https://storage.googleapis.com/political-csv/google-political-ads-transparency-bundle.zip"
FOLDER = os.path.join(CACHE, "adlibrary")
BUNDLE = os.path.join(FOLDER, "google-political-ads-transparency-bundle.zip")
SINCE = "2025-01-01"
PERSON = "a person (not named here)"
HONORIFICS = {"hon", "honorable", "rev", "sen", "rep", "gen", "col", "maj", "capt", "prof"}
FEC_CACHE = os.path.join(HERE, "fec_cache")                  # load_donors' committee files, read here and never fetched
AD_HOST = "https://adstransparency.google.com/"
STATE_CODE = {v: k for k, v in STATE_NAMES.items()} | {"District of Columbia": "DC"}
CREATIVE_COLS = ("Ad_ID", "Ad_URL", "Ad_Type", "Regions", "Advertiser_ID", "Advertiser_Name", "Date_Range_Start", "Date_Range_End",
                 "Impressions", "Geo_Targeting_Included", "Geo_Targeting_Excluded", "Spend_Range_Min_USD", "Spend_Range_Max_USD")
ORG_WORDS = re.compile(r"\b(PAC|COMMITTEE|FUND|FOR|FRIENDS|PARTY|ACTION|VICTORY|COUNCIL|ASSOCIATION|ALLIANCE|COALITION|PROJECT|"
                       r"AMERICA|AMERICANS|UNION|FEDERATION|LEAGUE|NETWORK|CENTER|INSTITUTE|FOUNDATION|VOTERS|CAUCUS|CAMPAIGN|"
                       r"INC|LLC|CORP|COMPANY|GROUP|MAJORITY|FUTURE|DEMOCRATS|REPUBLICANS|CONSERVATIVES|PROGRESS|SOCIETY)\b")
SCHEMA = """
CREATE TABLE IF NOT EXISTS ad_library (ad_id TEXT PRIMARY KEY, url TEXT, ad_type TEXT, advertiser TEXT, advertiser_id TEXT,
  first_shown TEXT, last_shown TEXT, spend_low INTEGER, spend_high INTEGER, impressions TEXT, states TEXT);
CREATE TABLE IF NOT EXISTS ad_links (ad_id TEXT, cand_id TEXT, race_id TEXT, relation TEXT, stance TEXT, basis TEXT,
  spender TEXT, PRIMARY KEY (ad_id, cand_id));
CREATE INDEX IF NOT EXISTS idx_ad_links_race ON ad_links (race_id, relation);
"""


def norm(name):
    """For matching names only: capitals, accents folded, '&' as AND, bracketed asides and punctuation out, one PAC spelling."""
    t = unicodedata.normalize("NFKD", name or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).upper()
    t = re.sub(r"\([^)]*\)", " ", t).replace("&", " AND ")
    t = re.sub(r"[^A-Z0-9]+", " ", t)
    t = re.sub(r"\bU S\b", "US", t)
    t = re.sub(r"\bPOLITICAL ACTION COMMITTEE\b", "PAC", t)
    t = re.sub(r"^\s*THE\s+", "", t)
    t = re.sub(r"\s+(INC|INCORPORATED|LLC|CORP|CORPORATION)\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip()


def whole_names(printed, fec_name):
    """A candidate's full name as a committee title would write it: from the ballot's spelling and the FEC's."""
    out = set()
    for nm in (printed, fec_name):
        given, family = name_parts(nm)
        given = [g for g in given if g not in HONORIFICS]
        if not given or not family:
            continue
        long_given = [g for g in given if len(g) > 1]                     # middle initials dropped
        for g in (given, long_given, given[:1]):
            if g:
                out.add(norm(" ".join(g) + " " + family))
    return out


def forms_for(printed, fec_name, office, state):
    tails = ["FOR CONGRESS", "FOR US CONGRESS", "FOR " + norm(STATE_NAMES.get(state, state))]
    if office == "S":
        tails += ["FOR SENATE", "FOR US SENATE", "FOR UNITED STATES SENATE"]
    return {f"{w} {t}" for w in whole_names(printed, fec_name) for t in tails}


def geo_states(included, excluded):
    """('US', a comma-separated list of two-letter codes, or '') and the whole states excluded, from Google's targeting
    lists. Items are joined by ', ' and end in ',United States' ('23237,Virginia,United States', 'Virginia,United
    States', 'United States'); a media market's name has commas of its own ('Washington, DC (Hagerstown, MD),United
    States'), so pieces are gathered until the country closes the item. A place inside a state counts for that state;
    a media market counts for the states its name gives (DC and MD there), and only those: Charlotte, NC reaches into
    South Carolina, but its name does not say so. Only a whole state excluded takes a state off; a ZIP code left out
    does not."""
    def read(text):
        whole, found, entire, held = False, set(), set(), []
        for tok in (text or "").split(", "):
            held.append(tok)
            if tok != "United States" and not tok.endswith(",United States"):
                continue
            item, held = ", ".join(held)[:-len("United States")].rstrip(", "), []
            if tok == "United States":
                whole = True
                continue
            parts = [p.strip() for p in item.split(",")]
            if parts[-1] in STATE_CODE:
                found.add(STATE_CODE[parts[-1]])
                if len(parts) == 1:
                    entire.add(STATE_CODE[parts[-1]])
            else:                                            # a media market, named by its cities and its states' codes
                found |= {c for c in re.findall(r"\b([A-Z]{2})\b", item) if c in STATE_NAMES or c == "DC"}
        return whole, found, entire
    whole, inc, _ = read(included)
    _, _, exc = read(excluded)
    if whole:
        return "US", exc
    return ",".join(sorted(inc - exc)), exc


def committee_files():
    """Every committee in the FEC's committee files for 2016 through 2026 that load_donors keeps in fec_cache/: the
    latest cycle's name, designation and candidate number. Only those columns: never the treasurer or the address."""
    master = {}
    for year in range(16, 28, 2):
        path = os.path.join(FEC_CACHE, f"cm{year}.zip")
        if not os.path.exists(path):
            continue
        with zipfile.ZipFile(path) as z:
            name = next((n for n in z.namelist() if n.lower().endswith(".txt")), None)
            if not name:
                continue
            with z.open(name) as fh:
                for line in io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline=""):
                    f = line.rstrip("\r\n").split("|")
                    if len(f) >= 15:
                        master[f[0]] = (2000 + year, f[1], f[8], f[14])
    return master


def whole_dollars(text):
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def rows(z, member, cols=None):
    """One CSV inside the bundle, streamed; with cols, each row is a tuple of only those columns."""
    with z.open(member) as fh:
        rd = csv.reader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline=""))
        head = next(rd)
        at = [head.index(c) for c in cols] if cols else None
        for r in rd:
            if at is None:
                yield r
            elif len(r) > max(at):
                yield tuple(r[i] for i in at)


def load(con, say=print):
    con.executescript(SCHEMA)
    if "spender" not in {r[1] for r in con.execute("PRAGMA table_info(ad_links)")}:      # a table made before the column
        con.execute("ALTER TABLE ad_links ADD COLUMN spender TEXT")
    csv.field_size_limit(1 << 30)                         # a list of ZIP codes can run to megabytes in one cell
    net.download(URL, BUNDLE, max_age_days=7, say=say)
    z = zipfile.ZipFile(BUNDLE)
    updated = next(rows(z, "google-political-ads-updated.csv"), [""])[0]

    # our side: 2026 candidates with an FEC number, their races and committees, and the outside spenders' declarations
    cand_race, cand_name, cand_state, cand_office = {}, {}, {}, {}
    for cand, race, name, election in con.execute(
            "SELECT fec_id, race_id, name, election FROM candidates WHERE fec_id IS NOT NULL ORDER BY election <> 'general', race_id"):
        cand_race.setdefault(cand, race)
        cand_name.setdefault(cand, name)
        cand_state.setdefault(cand, race.split("-")[1])
        cand_office.setdefault(cand, "S" if "-S" in race else "H")
    fec_name = {c: n for c, n in con.execute("SELECT cand_id, name FROM fec26_candidates") if c in cand_race}
    cmte_name = dict(con.execute("SELECT cmte_id, name FROM fec26_committees"))
    own = defaultdict(set)                                   # committee -> our candidates it is the principal or authorized committee of
    for cm, cand in con.execute("SELECT cmte_id, cand_id FROM fec26_committees WHERE designation IN ('P', 'A') AND cand_id IS NOT NULL"):
        if cand in cand_race:
            own[cm].add(cand)
    for cand, pcc in con.execute("SELECT cand_id, pcc FROM fec26_candidates WHERE pcc IS NOT NULL AND pcc <> ''"):
        if cand in cand_race:
            own[pcc].add(cand)
    decl = defaultdict(list)                                 # (spender, race) -> [(cand, stance, election, amount)]
    spender_name = {}
    for cand, sp, name, stance, election, amt in con.execute(
            "SELECT cand_id, spender, name, stance, election, amount FROM ad_spenders WHERE spender <> 'people-and-groups'"):
        if cand in cand_race:
            decl[(sp, cand_race[cand])].append((cand, stance, election, amt))
            spender_name[sp] = name or cmte_name.get(sp) or sp
    spender_races = defaultdict(set)
    for sp, race in decl:
        spender_races[sp].add(race)

    # names to match by, each kept only when it points to one candidate (or one spender)
    ambiguous = []
    by_cmte_name = defaultdict(set)
    for cm, cands in own.items():
        if cmte_name.get(cm):
            for cand in cands:
                by_cmte_name[norm(cmte_name[cm])].add((cm, cand))
    by_form = defaultdict(set)
    for cand in cand_race:
        for f in forms_for(cand_name[cand], fec_name.get(cand, ""), cand_office[cand], cand_state[cand]):
            by_form[f].add(cand)
    by_spender_name = defaultdict(set)
    for sp, nm in spender_name.items():
        by_spender_name[norm(nm)].add(sp)
    for index, what in ((by_cmte_name, "committee name"), (by_form, "candidate-name form"), (by_spender_name, "spender name")):
        for key in [k for k, v in index.items() if len({x[1] if isinstance(x, tuple) else x for x in v}) > 1]:
            ambiguous.append(f"{what} {key!r} fits {len(index[key])} of ours; not used")
            del index[key]

    # Google's register of advertisers: tie each one we can, by the FEC number Google verified it under, else by name
    master = committee_files()
    master_names = defaultdict(set)
    for cm, (_, nm, _, _) in master.items():
        master_names[norm(nm)].add(cm)
    campaign = defaultdict(dict)                             # advertiser -> {cand: basis}
    outside = defaultdict(dict)                              # advertiser -> {spender: how}
    register, conflicts = {}, []
    for aid, aname, public, regions in rows(z, "google-political-ads-advertiser-stats.csv",
                                             ("Advertiser_ID", "Advertiser_Name", "Public_IDs_List", "Regions")):
        if "US" not in regions.split(","):
            continue
        register[aid] = (aname, public)
        ids = re.findall(r"FEC ID ([CHSP][0-9A-Z]{8})\b", public)
        for i in ids:
            if i.startswith("C"):
                for cand in own.get(i, ()):
                    campaign[aid][cand] = (f"Google verified the advertiser under FEC ID {i}, which the FEC lists as a campaign committee "
                                           f"({cmte_name.get(i, i)}) of {cand_name[cand]} ({cand}).")
                year, old_name, dsgn, old_cand = master.get(i, (0, "", "", ""))
                if i not in own and dsgn in ("P", "A") and old_cand in cand_race:
                    campaign[aid][old_cand] = (f"Google verified the advertiser under FEC ID {i}, which the FEC's {year} committee file lists "
                                               f"as a campaign committee ({old_name}) of {cand_name[old_cand]} ({old_cand}).")
                if i in spender_name:
                    outside[aid][i] = f"Google verified the advertiser under FEC ID {i}"
            elif i in cand_race:
                campaign[aid][i] = f"Google verified the advertiser under {cand_name[i]}'s own FEC candidate number ({i})."
        n = norm(aname)
        known = [i for i in ids if not i.startswith("C") or i in master]
        if campaign[aid] or outside[aid] or known:           # the record names the committee or candidate; a name never overrides it
            if not campaign[aid] and not outside[aid] and (n in by_cmte_name or n in by_form or n in by_spender_name):
                k = known[0]
                said = (f"{master[k][1]}, designation {master[k][2] or '-'}, candidate {master[k][3] or 'none'}" if k in master
                        else "a candidate number that is not one of ours")
                conflicts.append(f"{aname!r}: the name fits one of ours, but Google's FEC ID {k} is {said}; not tied")
            continue
        unknown = (f" Google lists FEC ID {', '.join(ids)} for it, a number not in the FEC committee files for 2016 through 2026."
                   if ids else " Google's record gives no FEC number for it.")
        fits = {c for _, c in by_cmte_name.get(n, ())} | by_form.get(n, set())
        others = {cm for cm in master_names.get(n, ()) if master[cm][3] not in fits and cm not in own and cm not in by_spender_name.get(n, ())}
        if others and (fits or n in by_spender_name):        # the same name belongs to another committee in the FEC's files: a name cannot settle it
            ambiguous.append(f"advertiser {aname!r} fits one of ours by name, but the FEC's files also give that name to "
                             f"{', '.join(sorted(others)[:3])}{' and more' if len(others) > 3 else ''}; not tied")
            continue
        for cm, cand in by_cmte_name.get(n, ()):
            campaign[aid][cand] = (f"The advertiser's name matches {cmte_name[cm]} ({cm}), which the FEC lists as a campaign committee of "
                                   f"{cand_name[cand]} ({cand}).{unknown}")
        for cand in by_form.get(n, ()):
            campaign[aid].setdefault(cand, f"The advertiser's name is {cand_name[cand]}'s full name with the office or state "
                                           f"({aname}), and no other 2026 candidate has that name.{unknown}")
        for sp in by_spender_name.get(n, ()):
            outside[aid][sp] = f"The advertiser's name matches {spender_name[sp]} ({sp}) as the FEC files it.{unknown[:-1]}"
    campaign = {a: v for a, v in campaign.items() if v}
    outside = {a: v for a, v in outside.items() if v}
    tied = set(campaign) | set(outside)
    renumbered = {old: new for old, new in rows(z, "advertiser_id_mapping.csv", ("OldAdvertiserId", "NewAdvertiserId"))
                  if new in tied and old not in register}

    def shown(aid, aname):
        """Committees, parties, candidates and organizations by name; a private person, never."""
        public = register.get(aid, ("", ""))[1]
        if aid in campaign or aid in outside or re.search(r"FEC ID|EIN|Registered in", public) or ORG_WORDS.search(norm(aname)):
            return aname
        return PERSON

    # the ads: every one of a tied advertiser's that ran in the United States from 2025 on
    library, links = {}, {}
    seen = kept = 0
    for (ad, url, kind, regions, aid, aname, start, end, imp, inc, exc, lo, hi) in rows(z, "google-political-ads-creative-stats.csv", CREATIVE_COLS):
        seen += 1
        aid = renumbered.get(aid, aid)
        if aid not in tied or "US" not in regions.split(",") or (end or "") < SINCE:
            continue
        kept += 1
        states, excluded = geo_states(inc, exc)
        library[ad] = (ad, url if url.startswith(AD_HOST) else "", kind, shown(aid, aname), aid, start, end,
                       whole_dollars(lo), whole_dollars(hi), imp, states)
        for cand, basis in campaign.get(aid, {}).items():
            links[(ad, cand)] = (ad, cand, cand_race[cand], "campaign", "", basis, None)
        for sp, how in outside.get(aid, {}).items():
            for race in spender_races[sp]:
                st = race.split("-")[1]
                if st in excluded or (states not in ("US", "") and st not in states.split(",")):
                    continue                                 # Google's targeting says it ran elsewhere
                items = sorted(decl[(sp, race)], key=lambda x: -x[3])
                said = "; ".join(f"${amt:,.0f} {stance} {cand_name[c]} ({el})" for c, stance, el, amt in items)
                where = ("Google's targeting names the whole country" if states == "US" else
                         f"Google's targeting names {', '.join(STATE_NAMES.get(s, s) for s in states.split(','))}" if states else
                         "Google's record names no state for it")
                basis = (f"{how}. {spender_name[sp]} reported to the FEC, in this race: {said}. {where}. "
                         "Neither record says which candidate this ad is about.")
                for cand in {c for c, *_ in items}:
                    if (ad, cand) in links and links[(ad, cand)][3] == "campaign":
                        continue
                    stances = {s for c, s, *_ in items if c == cand}
                    stance = "for and against" if stances >= {"for", "against"} else stances.pop()
                    links[(ad, cand)] = (ad, cand, race, "outside", stance, basis, sp)
    linked_ads = {k[0] for k in links}
    library = {ad: row for ad, row in library.items() if ad in linked_ads}

    with con:
        con.execute("DELETE FROM ad_library")
        con.execute("DELETE FROM ad_links")
        con.executemany("INSERT INTO ad_library VALUES (?,?,?,?,?,?,?,?,?,?,?)", library.values())
        con.executemany("INSERT INTO ad_links (ad_id, cand_id, race_id, relation, stance, basis, spender) VALUES (?,?,?,?,?,?,?)",
                        links.values())
        record_source(con, "google-political-ads", path=BUNDLE, level="federal", state="US", kind="ads", agency="Google",
                      title="Political Ads Transparency Report, data bundle", url=URL, published=updated, rows=len(library),
                      note="Ads link to Google's own pages; nothing is copied. Only the columns named in ballot/adlibrary.py are read.")
    per = defaultdict(set)
    for (ad, cand), row in links.items():
        per[row[3]].add(ad)
    stats = {"updated": updated, "creatives_read": seen, "us_2025_ads_of_tied_advertisers": kept, "ads": len(library), "links": len(links),
             "campaign_ads": len(per["campaign"]), "outside_ads": len(per["outside"]),
             "candidates_with_ads": len({k[1] for k in links}),
             "campaign_advertisers": len(campaign), "outside_advertisers": len(outside), "renumbered": len(renumbered),
             "ambiguous": ambiguous, "conflicts": conflicts}
    stats["advertisers_with_ads"] = len({row[4] for row in library.values()})
    say(f"    Ad library (Google, refreshed {updated}): {len(library):,} ads from {stats['advertisers_with_ads']:,} advertisers tied to 2026 candidates; "
        f"{len(per['campaign']):,} the campaigns' own, {len(per['outside']):,} by outside spenders; "
        f"{stats['candidates_with_ads']:,} candidates have at least one")
    for line in ambiguous + conflicts:
        say("      " + line)
    return stats
