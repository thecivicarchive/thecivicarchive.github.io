"""What is particular to each place: what its legislature and chambers are called, how its parties map onto the
site's colours, its Census number. A state is added here first; everything else reads from this.

Party codes are only for colour and arithmetic (D, R, I). The name a state uses for a party is always kept and
shown as the state writes it: Minnesota's Democrats are the Democratic-Farmer-Labor Party, the DFL."""

PLACES = {
    "mn": {
        "code": "MN", "name": "Minnesota", "fips": "27",
        "legislature": "Minnesota Legislature", "session": "94th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://www.leg.mn.gov/",
        # "next" is the year every seat in the chamber is next on the ballot (senators elected in 2022 serve four years)
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 67, "term_years": 4, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 134, "term_years": 2, "next": 2026},
        "nested": True,                        # each Senate district is made of the House districts that share its number (45 holds 45A and 45B)
        "zooms": [{"name": "Twin Cities", "box": [-93.75, 44.65, -92.80, 45.30]}],      # where districts are too small to tap: west, south, east, north
        "executive": "Governor",
        "parties": {"Democratic-Farmer-Labor": ("D", "DFL"), "Democratic": ("D", "DFL"), "Republican": ("R", "Republican"),
                    "Independent": ("I", "Independent")},
        "bill_prefixes": {"HF": "House File", "SF": "Senate File"},
        "money": "mn_cfb",                     # which campaign-finance loader this state uses; None until one is written
        "money_agency": {"name": "the Minnesota Campaign Finance and Public Disclosure Board", "url": "https://cfb.mn.gov/"},
        # the Board's own page for a committee, by kind of committee ({id} is its registration number)
        "money_links": {"pcf": "https://cfb.mn.gov/reports-and-data/viewers/campaign-finance/political-committee-fund/{id}/",
                        "party": "https://cfb.mn.gov/reports-and-data/viewers/campaign-finance/party-unit/{id}/",
                        "cand": "https://cfb.mn.gov/reports-and-data/viewers/campaign-finance/candidates/{id}/"},
    },
    # Minnesota's neighbours (2026-09-20). Members and district lines come from the same two sources for every state;
    # campaign money is each state's own agency and is added one state at a time ("money": None until then).
    # "next" is left out wherever the year a seat is next on the ballot has not been checked against the record.
    # Where a chamber's terms are staggered it is given by district number: odd-numbered districts one year, even the
    # other (checked 2026-09-20 against the roster's own start dates and the published 2026 election lists).
    "wi": {
        "code": "WI", "name": "Wisconsin", "fips": "55",
        "legislature": "Wisconsin Legislature", "session": "107th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://legis.wisconsin.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 33, "term_years": 4, "next": {"odd": 2026, "even": 2028}},
        "lower": {"name": "Assembly", "full": "State Assembly", "title": "Representative", "short": "Rep.", "seats": 99, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Milwaukee", "box": [-88.15, 42.88, -87.80, 43.22]}, {"name": "Madison", "box": [-89.62, 42.95, -89.18, 43.22]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "nd": {
        "code": "ND", "name": "North Dakota", "fips": "38",
        "legislature": "North Dakota Legislative Assembly", "session": "69th Legislative Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://ndlegis.gov/",
        # a district elects its senator and its two representatives in the same year, all for four years
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 47, "term_years": 4, "next": {"odd": 2026, "even": 2028}},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 94, "term_years": 4, "next": {"odd": 2026, "even": 2028}},
        "zooms": [{"name": "Fargo", "box": [-96.98, 46.74, -96.68, 46.98]}, {"name": "Bismarck", "box": [-100.98, 46.72, -100.62, 46.92]}],
        "executive": "Governor",
        # North Dakota's Democrats are the Democratic-Nonpartisan League Party, the Democratic-NPL
        "parties": {"Democratic-Nonpartisan League": ("D", "Democratic-NPL"), "Democratic-NPL": ("D", "Democratic-NPL"), "Democratic": ("D", "Democratic-NPL"),
                    "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "sd": {
        "code": "SD", "name": "South Dakota", "fips": "46",
        "legislature": "South Dakota Legislature", "session": "2025-2026 term", "since": "2025-01-01",
        "url": "https://sdlegislature.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 35, "term_years": 2, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 70, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Sioux Falls", "box": [-96.92, 43.44, -96.58, 43.66]}, {"name": "Rapid City", "box": [-103.38, 43.98, -103.08, 44.16]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ia": {
        "code": "IA", "name": "Iowa", "fips": "19",
        "legislature": "Iowa General Assembly", "session": "91st General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://www.legis.iowa.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 50, "term_years": 4, "next": {"odd": 2026, "even": 2028}},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 100, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Des Moines", "box": [-93.92, 41.45, -93.40, 41.78]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
}


def place(code):
    try:
        return PLACES[code.lower()]
    except KeyError:
        raise SystemExit(f"'{code}' is not set up yet. Places so far: {', '.join(sorted(PLACES))}")


def party_code(p, name):
    """(code for colour and counting, the label to show) for a party name as the roster writes it."""
    code, label = p["parties"].get(name or "", ("I", name or "Independent"))
    return code, label
