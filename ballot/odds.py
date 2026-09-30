"""
ballot/odds.py - what the two prediction markets John chose, Polymarket and Kalshi, are trading on a race: information
only, never advice (John's answers, 2026-09-29). Each outcome's price, the amount traded and when the snapshot was taken,
read from the markets' public data (no account, no key) into ballot_cache/odds/odds_2026.json, which the page reads.

A race is listed in MARKETS only after its markets were found by hand and checked to be that race and that election;
nothing is matched from titles. The page shows the prices apart from the record, labelled as what bettors are paying
(not a poll, a forecast or an official record), and opens a market only through a notice: that these are bets, the
age limits, that their legality is disputed in some states, and the national and state problem-gambling helplines.
No referral codes, ever.
"""

import datetime as dt
import json
import os

from ballot.common import CACHE
from states import net

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
    **{f"2026-{st}-H{int(d):02d}": {"kalshi": f"HOUSE{st}{d}-26", "checked": "2026-09-30"}      # "MN-02 House winner?" and the like
       for st, d in (("MN", 2), ("WI", 1), ("WI", 3), ("IA", 1), ("IA", 3), ("MI", 3), ("MI", 4), ("MI", 7), ("MI", 8), ("MI", 10),
                                  ("OH", 1), ("OH", 9), ("OH", 13), ("IN", 1), ("NE", 2), ("MT", 1), ("CO", 3), ("CO", 8),
                                  ("NC", 1), ("VA", 1), ("VA", 2), ("VA", 7), ("WA", 3), ("AZ", 1), ("AZ", 2), ("AZ", 6), ("OR", 5),
                                  ("NV", 1), ("NV", 3), ("NV", 4), ("NM", 2))},
}


def polymarket(slug):
    ev = json.loads(net.get(f"https://gamma-api.polymarket.com/events?slug={slug}", accept="application/json"))[0]
    rows = []
    for m in ev.get("markets") or []:
        prices = json.loads(m.get("outcomePrices") or "null")
        if not prices or m.get("closed"):
            continue
        rows.append([m.get("groupItemTitle") or m.get("question"), round(float(prices[0]), 3), round(float(m.get("volume") or 0))])
    return {"title": ev.get("title"), "url": f"https://polymarket.com/event/{slug}", "rows": rows, "volume": round(float(ev.get("volume") or 0))}


def kalshi(ticker):
    d = json.loads(net.get(f"https://api.elections.kalshi.com/trade-api/v2/events/{ticker}?with_nested_markets=true", accept="application/json"))
    ev = d.get("event", {})
    rows = sorted([[m.get("yes_sub_title") or m.get("title"), round(float(m.get("last_price_dollars") or 0), 3), round(float(m.get("volume_fp") or 0))]
                   for m in ev.get("markets") or d.get("markets") or [] if m.get("status") == "active"], key=lambda r: -r[1])
    return {"title": ev.get("title"), "url": f"https://kalshi.com/markets/{ev.get('series_ticker', ticker.split('-')[0]).lower()}", "rows": rows,
            "volume": sum(r[2] for r in rows), "unit": "contracts"}


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
    return out
