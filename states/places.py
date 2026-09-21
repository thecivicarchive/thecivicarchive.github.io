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
    # The second ring (2026-09-20): every state that touches the five above. Election years checked the same day:
    # Michigan and Missouri against the published 2026 election lists and the roster; Wyoming and Nebraska against the
    # roster's start dates (every Wyoming senator who began in January 2025 sits in an even-numbered district, every
    # Nebraska one in an odd-numbered district, so those seats are not up again until 2028).
    "mi": {
        "code": "MI", "name": "Michigan", "fips": "26",
        "legislature": "Michigan Legislature", "session": "103rd Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://www.legislature.mi.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 38, "term_years": 4, "next": 2026},      # all 38 seats, with the governor's race
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 110, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Detroit", "box": [-83.55, 42.10, -82.85, 42.75]}, {"name": "Grand Rapids", "box": [-85.85, 42.80, -85.45, 43.10]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "il": {
        "code": "IL", "name": "Illinois", "fips": "17",
        "legislature": "Illinois General Assembly", "session": "104th General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://www.ilga.gov/",
        # Illinois senators serve two four-year terms and one two-year term in each ten years, by groups of districts,
        # so no single rule says when a Senate seat is next up; it is left out.
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 59, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 118, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Chicago", "box": [-88.30, 41.55, -87.50, 42.20]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "mo": {
        "code": "MO", "name": "Missouri", "fips": "29",
        "legislature": "Missouri General Assembly", "session": "103rd General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://www.mo.gov/government/legislative-branch/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 34, "term_years": 4, "next": {"even": 2026, "odd": 2028}},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 163, "term_years": 2, "next": 2026},
        "zooms": [{"name": "St. Louis", "box": [-90.75, 38.45, -90.10, 38.90]}, {"name": "Kansas City", "box": [-94.80, 38.85, -94.30, 39.35]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ne": {
        "code": "NE", "name": "Nebraska", "fips": "31",
        "legislature": "Nebraska Legislature", "session": "109th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://nebraskalegislature.gov/",
        # one chamber, elected on a ballot without party labels; its members are called senators
        "note": "Nebraska elects its one-chamber Legislature on a ballot without party labels, so every member is listed as nonpartisan.",
        "upper": {"name": "Legislature", "title": "Senator", "short": "Sen.", "seats": 49, "term_years": 4, "district_name": "Legislative District",
                  "next": {"even": 2026, "odd": 2028}},
        "zooms": [{"name": "Omaha", "box": [-96.30, 41.10, -95.85, 41.40]}, {"name": "Lincoln", "box": [-96.85, 40.70, -96.55, 40.95]}],
        "executive": "Governor",
        "parties": {"Nonpartisan": ("I", "Nonpartisan"), "Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "wy": {
        "code": "WY", "name": "Wyoming", "fips": "56",
        "legislature": "Wyoming Legislature", "session": "68th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://www.wyoleg.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 31, "term_years": 4, "next": {"odd": 2026, "even": 2028}},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 62, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Cheyenne", "box": [-104.95, 41.05, -104.65, 41.25]}, {"name": "Casper", "box": [-106.50, 42.75, -106.15, 42.95]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "mt": {
        "code": "MT", "name": "Montana", "fips": "30",
        "legislature": "Montana Legislature", "session": "69th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://www.legmt.gov/",
        # half the Senate is elected every two years, by a list of districts rather than by odd and even; left out
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 50, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 100, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Billings", "box": [-108.75, 45.65, -108.35, 45.90]}, {"name": "Missoula", "box": [-114.20, 46.75, -113.85, 47.00]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    # The third ring (2026-09-20): every state that touches the eleven above. "next" is filled in only after the
    # check described above; Senates that rotate by a list of districts rather than by odd and even are left without
    # (Indiana, Arkansas, Colorado, Utah). Ohio and Kentucky: the published 2026 lists and the roster agree. Tennessee,
    # Oklahoma and Kansas: from the roster's start dates (Tennessee's odd and Oklahoma's even districts were last
    # elected in 2022; every Kansas senator's term runs from a presidential year).
    "in": {
        "code": "IN", "name": "Indiana", "fips": "18",
        "legislature": "Indiana General Assembly", "session": "124th General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://iga.in.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 50, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 100, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Indianapolis", "box": [-86.35, 39.60, -85.90, 39.95]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "oh": {
        "code": "OH", "name": "Ohio", "fips": "39",
        "legislature": "Ohio General Assembly", "session": "136th General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://www.legislature.ohio.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 33, "term_years": 4, "next": {"odd": 2026, "even": 2028}},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 99, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Columbus", "box": [-83.20, 39.85, -82.75, 40.15]}, {"name": "Cleveland", "box": [-81.90, 41.35, -81.45, 41.62]},
                  {"name": "Cincinnati", "box": [-84.70, 39.05, -84.30, 39.30]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ky": {
        "code": "KY", "name": "Kentucky", "fips": "21",
        "legislature": "Kentucky General Assembly", "session": "2025-2026 term", "since": "2025-01-01",
        "url": "https://legislature.ky.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 38, "term_years": 4, "next": {"even": 2026, "odd": 2028}},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 100, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Louisville", "box": [-85.95, 38.05, -85.45, 38.35]}, {"name": "Lexington", "box": [-84.65, 37.95, -84.35, 38.12]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "tn": {
        "code": "TN", "name": "Tennessee", "fips": "47",
        "legislature": "Tennessee General Assembly", "session": "114th General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://www.capitol.tn.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 33, "term_years": 4, "next": {"odd": 2026, "even": 2028}},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 99, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Nashville", "box": [-87.05, 35.98, -86.55, 36.32]}, {"name": "Memphis", "box": [-90.15, 35.00, -89.70, 35.28]},
                  {"name": "Knoxville", "box": [-84.15, 35.85, -83.75, 36.08]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ar": {
        "code": "AR", "name": "Arkansas", "fips": "05",
        "legislature": "Arkansas General Assembly", "session": "95th General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://www.arkleg.state.ar.us/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 35, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 100, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Little Rock", "box": [-92.50, 34.62, -92.10, 34.88]}, {"name": "Northwest Arkansas", "box": [-94.35, 36.00, -94.00, 36.45]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ok": {
        "code": "OK", "name": "Oklahoma", "fips": "40",
        "legislature": "Oklahoma Legislature", "session": "60th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://www.oklegislature.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 48, "term_years": 4, "next": {"even": 2026, "odd": 2028}},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 101, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Oklahoma City", "box": [-97.75, 35.30, -97.30, 35.65]}, {"name": "Tulsa", "box": [-96.15, 35.95, -95.75, 36.25]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ks": {
        "code": "KS", "name": "Kansas", "fips": "20",
        "legislature": "Kansas Legislature", "session": "2025-2026 Legislature", "since": "2025-01-01",
        "url": "https://www.kslegislature.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 40, "term_years": 4, "next": 2028},      # all forty seats, in presidential years
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 125, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Kansas City", "box": [-94.95, 38.85, -94.60, 39.20]}, {"name": "Wichita", "box": [-97.55, 37.58, -97.15, 37.80]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "co": {
        "code": "CO", "name": "Colorado", "fips": "08",
        "legislature": "Colorado General Assembly", "session": "75th General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://leg.colorado.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 35, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 65, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Denver", "box": [-105.20, 39.55, -104.70, 39.95]}, {"name": "Colorado Springs", "box": [-105.00, 38.70, -104.60, 39.00]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ut": {
        "code": "UT", "name": "Utah", "fips": "49",
        "legislature": "Utah State Legislature", "session": "66th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://le.utah.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 29, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 75, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Salt Lake City", "box": [-112.15, 40.50, -111.75, 40.85]}, {"name": "Provo", "box": [-111.85, 40.15, -111.55, 40.45]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "id": {
        "code": "ID", "name": "Idaho", "fips": "16",
        "legislature": "Idaho Legislature", "session": "68th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://legislature.idaho.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 35, "term_years": 2, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 70, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Boise", "box": [-116.45, 43.50, -116.05, 43.75]}],
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
