"""
ballot/odds.py - what the two prediction markets John chose, Polymarket and Kalshi, are trading on a race: information
only, never advice (John's answers, 2026-09-29). Each outcome's price, the amount traded and when the snapshot was taken,
read from the markets' public data (no account, no key) into ballot_cache/odds/odds_2026.json, which the page reads.

A race is listed in MARKETS only after its markets were found by hand and checked to be that race and that election;
nothing is matched from titles. The page shows the prices apart from the record, labelled as what bettors are paying
(not a poll, a forecast or an official record), and opens a market only through a notice: that these are bets, the
age limits, that their legality is disputed in some states, and the national and state problem-gambling helplines.
No referral codes, ever.

State races (John, 2026-10-01; Minnesota first). The markets a person found for a state's own races are kept in a file
for that state, ballot/odds_state_<code>.json ({race id in ballot_local_2026.sqlite: {"polymarket": slug or null,
"kalshi": ticker or null, "checked": day, "note": what was checked}}), and the same run reads them into a snapshot of
their own, ballot_cache/odds/odds_state_2026.json, which the state ballot pages read. The Congress snapshot is written
exactly as before, so nothing the Congress pages count or show changes. Two things are different for the state races,
because their markets are small: a Polymarket outcome that is not open for trading (the "Person A", "Other"
placeholders an event is created with, which report a price of 0.5 nobody has paid) is left out; and a Kalshi outcome
nobody has traded yet has no price at all (its last price reads 0), so it is named under "quiet" and given no row.

    python -m ballot.odds state        only the state races (a handful of requests)
"""

import datetime as dt
import glob
import json
import os
import sys

from ballot.common import CACHE
from states import net

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_SNAPSHOT = os.path.join(CACHE, "odds", "odds_state_2026.json")

MARKETS = {      # race -> Polymarket event slug and Kalshi event ticker, each checked by hand against the market's own title
    "2026-MN-S2": {"polymarket": "minnesota-senate-election-winner", "kalshi": "SENATEMN-26", "checked": "2026-09-30"},
    "2026-MI-S2": {"polymarket": "michigan-senate-election-winner", "kalshi": "SENATEMI-26", "checked": "2026-09-30"},
    "2026-IA-S2": {"polymarket": "iowa-senate-election-winner", "kalshi": "SENATEIA-26", "checked": "2026-09-30"},
    "2026-SD-S2": {"polymarket": "south-dakota-senate-election-winner", "kalshi": "SENATESD-26", "checked": "2026-09-30"},
    "2026-OH-S3": {"polymarket": "ohio-senate-election-winner", "kalshi": "SENATEOHS-26", "checked": "2026-09-30"},      # the special election
    "2026-NE-S2": {"polymarket": "nebraska-senate-election-winner", "kalshi": "SENATENE-26", "checked": "2026-09-30"},
    "2026-MT-S2": {"polymarket": "montana-senate-election-winner", "kalshi": "SENATEMT-26", "checked": "2026-09-30"},
    "2026-WY-S2": {"polymarket": "wyoming-senate-election-winner", "kalshi": "SENATEWY-26", "checked": "2026-09-30"},
    "2026-TN-S2": {"polymarket": "tennessee-senate-election-winner", "kalshi": "SENATETN-26", "checked": "2026-09-30"},
    "2026-CO-S2": {"polymarket": "colorado-senate-election-winner", "kalshi": "SENATECO-26", "checked": "2026-09-30"},
    "2026-KY-S2": {"polymarket": "kentucky-senate-election-winner", "checked": "2026-09-30"},      # Kalshi lists no Kentucky Senate market
    "2026-OK-S2": {"polymarket": "oklahoma-senate-election-winner", "kalshi": "SENATEOK-26", "checked": "2026-09-30"},
    "2026-AR-S2": {"polymarket": "arkansas-senate-election-winner", "kalshi": "SENATEAR-26", "checked": "2026-09-30"},
    "2026-KS-S2": {"polymarket": "kansas-senate-election-winner", "kalshi": "SENATEKS-26", "checked": "2026-09-30"},
    "2026-ID-S2": {"polymarket": "idaho-senate-election-winner", "kalshi": "SENATEID-26", "checked": "2026-09-30"},
    "2026-WV-S2": {"polymarket": "west-virginia-senate-election-winner", "kalshi": "SENATEWV-26", "checked": "2026-09-30"},
    "2026-GA-S2": {"polymarket": "georgia-senate-election-winner", "kalshi": "SENATEGA-26", "checked": "2026-09-30"},
    "2026-NC-S2": {"polymarket": "north-carolina-senate-election-winner", "kalshi": "SENATENC-26", "checked": "2026-09-30"},
    "2026-VA-S2": {"polymarket": "virginia-senate-election-winner", "kalshi": "SENATEVA-26", "checked": "2026-09-30"},
    "2026-AL-S2": {"kalshi": "SENATEAL-26", "checked": "2026-09-30"},      # no Polymarket event found
    "2026-LA-S2": {"polymarket": "louisiana-senate-election-winner", "checked": "2026-09-30"},      # Kalshi's SENATELA-26 is titled "Kentucky Senate winner?"
    "2026-OR-S2": {"polymarket": "oregon-senate-election-winner", "kalshi": "SENATEOR-26", "checked": "2026-09-30"},
    "2026-MS-S2": {"polymarket": "mississippi-senate-election-winner", "kalshi": "SENATEMS-26", "checked": "2026-09-30"},
    "2026-NM-S2": {"polymarket": "new-mexico-senate-election-winner", "kalshi": "SENATENM-26", "checked": "2026-09-30"},
    "2026-NJ-S2": {"polymarket": "new-jersey-senate-election-winner", "kalshi": "SENATENJ-26", "checked": "2026-09-30"},
    "2026-MA-S2": {"polymarket": "massachusetts-senate-election-winner", "kalshi": "SENATEMA-26", "checked": "2026-09-30"},
    "2026-SC-S2": {"polymarket": "south-carolina-senate-election-winner", "kalshi": "SENATESC-26", "checked": "2026-09-30"},
    "2026-NH-S2": {"polymarket": "new-hampshire-senate-election-winner", "kalshi": "SENATENH-26", "checked": "2026-09-30"},
    "2026-ME-S2": {"polymarket": "maine-senate-election-winner", "kalshi": "SENATEME-26", "checked": "2026-09-30"},
    "2026-RI-S2": {"polymarket": "rhode-island-senate-election-winner", "kalshi": "SENATERI-26", "checked": "2026-09-30"},
    "2026-DE-S2": {"polymarket": "delaware-senate-election-winner", "kalshi": "SENATEDE-26", "checked": "2026-09-30"},
    "2026-AK-S2": {"polymarket": "alaska-senate-election-winner", "kalshi": "SENATEAK-26", "checked": "2026-09-30"},
    "2026-AK-H00": {"kalshi": "HOUSEAKAL-26", "checked": "2026-09-30"},      # "Alaska House winner?" (at large)
    "2026-TX-S2": {"polymarket": "texas-senate-election-winner", "kalshi": "SENATETX-26", "checked": "2026-09-30"},
    "2026-IL-S2": {"polymarket": "illinois-senate-election-winner", "kalshi": "SENATEIL-26", "checked": "2026-09-30"},
    "2026-FL-S3": {"polymarket": "florida-senate-election-winner", "kalshi": "SENATEFLS-26", "checked": "2026-09-30"},      # the special election
    **{f"2026-{st}-H{int(d):02d}": {"kalshi": f"HOUSE{st}{d}-26", "checked": "2026-09-30"}      # "MN-02 House winner?" and the like
       for st, d in (("MN", 2), ("WI", 1), ("WI", 3), ("IA", 1), ("IA", 3), ("MI", 3), ("MI", 4), ("MI", 7), ("MI", 8), ("MI", 10),
                                  ("OH", 1), ("OH", 9), ("OH", 13), ("IN", 1), ("NE", 2), ("MT", 1), ("CO", 3), ("CO", 8),
                                  ("NC", 1), ("VA", 1), ("VA", 2), ("VA", 7), ("WA", 3), ("AZ", 1), ("AZ", 2), ("AZ", 6), ("OR", 5),
                                  ("NV", 1), ("NV", 3), ("NV", 4), ("NM", 2),
                                  ("NJ", 5), ("NJ", 7), ("NJ", 9), ("CT", 5), ("NH", 1), ("ME", 2),
                                  ("CA", 3), ("CA", 9), ("CA", 13), ("CA", 21), ("CA", 22), ("CA", 27), ("CA", 41), ("CA", 45), ("CA", 47),
                                  ("CA", 49), ("TX", 15), ("TX", 28), ("TX", 34), ("FL", 13), ("FL", 23), ("NY", 3), ("NY", 4), ("NY", 17),
                                  ("NY", 18), ("NY", 19), ("NY", 22), ("PA", 1), ("PA", 7), ("PA", 8), ("PA", 10), ("PA", 17), ("IL", 17))},
}


def polymarket(slug, open_only=False):
    """open_only (the state races): an outcome that is not open for trading is left out. An event is created with
    placeholders ("Person A", "Person B", "Other") that report a price of 0.5 before anyone can trade them."""
    ev = json.loads(net.get(f"https://gamma-api.polymarket.com/events?slug={slug}", accept="application/json"))[0]
    rows = []
    for m in ev.get("markets") or []:
        prices = json.loads(m.get("outcomePrices") or "null")
        if not prices or m.get("closed"):
            continue
        if open_only and (m.get("active") is False or m.get("acceptingOrders") is False):
            continue
        rows.append([m.get("groupItemTitle") or m.get("question"), round(float(prices[0]), 3), round(float(m.get("volume") or 0))])
    return {"title": ev.get("title"), "url": f"https://polymarket.com/event/{slug}", "rows": rows, "volume": round(float(ev.get("volume") or 0))}


def kalshi(ticker, traded_only=False):
    """traded_only (the state races): an outcome nobody has traded has no price (its last price reads 0), so it gets no
    row; it is named under "quiet", so a page can say the market lists it."""
    d = json.loads(net.get(f"https://api.elections.kalshi.com/trade-api/v2/events/{ticker}?with_nested_markets=true", accept="application/json"))
    ev = d.get("event", {})
    rows = sorted([[m.get("yes_sub_title") or m.get("title"), round(float(m.get("last_price_dollars") or 0), 3), round(float(m.get("volume_fp") or 0))]
                   for m in ev.get("markets") or d.get("markets") or [] if m.get("status") == "active"], key=lambda r: -r[1])
    out = {"title": ev.get("title"), "url": f"https://kalshi.com/markets/{ev.get('series_ticker', ticker.split('-')[0]).lower()}", "rows": rows,
           "volume": sum(r[2] for r in rows), "unit": "contracts"}
    if traded_only:
        out["rows"] = [r for r in rows if r[2] > 0]
        quiet = [r[0] for r in rows if r[2] <= 0]
        if quiet:
            out["quiet"] = quiet
    return out


def state_markets():
    """{race id: {"polymarket", "kalshi", "checked", "note"}} for every state's own races a person found markets for:
    the ballot/odds_state_<code>.json files, each race checked by hand against the market's own title."""
    out = {}
    for path in sorted(glob.glob(os.path.join(HERE, "odds_state_*.json"))):
        try:
            found = json.load(open(path, encoding="utf-8"))
        except ValueError:
            continue
        for race, m in found.items():
            if isinstance(m, dict) and m.get("checked") and (m.get("polymarket") or m.get("kalshi")):
                out[race] = m
    return out


def load_state(say=print):
    """The state races' markets, into their own snapshot (the Congress snapshot is not touched)."""
    net.patient_lookups()
    listed, out = state_markets(), {}
    for race, m in listed.items():
        got = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "checked": m["checked"]}
        for key, fn in (("polymarket", lambda s: polymarket(s, open_only=True)), ("kalshi", lambda t: kalshi(t, traded_only=True))):
            if not m.get(key):
                continue
            try:
                got[key] = fn(m[key])
            except Exception as e:      # a market that cannot be read is left out, never guessed
                say(f"    {race}: {key} could not be read ({e})")
        out[race] = got
    os.makedirs(os.path.dirname(STATE_SNAPSHOT), exist_ok=True)
    json.dump(out, open(STATE_SNAPSHOT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"    Odds: {len(out)} state race(s) read into {os.path.relpath(STATE_SNAPSHOT)}"
        + (f" ({', '.join(sorted({r.split('-')[1] for r in out}))})" if out else ""))
    return out


def load(con=None, say=print):
    net.patient_lookups()
    out = {}
    for race, m in MARKETS.items():
        got = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "checked": m["checked"]}
        for key, fn in (("polymarket", polymarket), ("kalshi", kalshi)):
            if key not in m:
                continue
            try:
                got[key] = fn(m[key])
            except Exception as e:      # a market that cannot be read is left out, never guessed
                say(f"    {race}: {key} could not be read ({e})")
        out[race] = got
    path = os.path.join(CACHE, "odds", "odds_2026.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"    Odds: {len(out)} race(s) read from Polymarket and Kalshi into {os.path.relpath(path)}")
    try:      # the states' own races, into a snapshot of their own; nothing here can undo the Congress snapshot above
        load_state(say)
    except Exception as e:  # noqa: BLE001
        say(f"    Odds: the state races could not be read ({e}); the Congress snapshot is written")
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["state"]:
        load_state()
    else:
        load()
