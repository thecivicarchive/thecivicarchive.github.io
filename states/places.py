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
        # the sentence on every money card about what the agency's file does and does not hold (each state's rules differ)
        "money_rule": "Campaigns list a giver once that giver passes $200 in a year; smaller gifts are reported as one sum, and the public subsidy the state pays campaigns is reported elsewhere, so neither is in this file and the totals here are lower than everything a campaign took in.",
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
        "money": "co_tracer",                  # states/money_co.py: the Secretary of State's TRACER bulk downloads, one contributions file a year
        "money_agency": {"name": "the Colorado Secretary of State", "url": "https://tracer.sos.colorado.gov/"},
        "money_rule": "TRACER, the Secretary of State's campaign-finance system, lists every giver of $20 or more by name and smaller gifts as one sum. Its bulk files name no office for a candidate, so a campaign is matched only when its candidate's full name fits exactly one sitting legislator, and they do not say which candidate an independent spender supported or opposed, so no outside spending is shown for Colorado.",
        "legislature": "Colorado General Assembly", "session": "75th General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://leg.colorado.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 35, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 65, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Denver", "box": [-105.20, 39.55, -104.70, 39.95]}, {"name": "Colorado Springs", "box": [-105.00, 38.70, -104.60, 39.00]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
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
    # The fourth ring (2026-09-23): every state that touches the twenty-one above. "next" for a staggered Senate is
    # filled in only after the check against the roster's start dates and the published 2026 election lists; where a
    # Senate rotates by lot or by list (Texas, Nevada, West Virginia's paired seats) it is left out.
    "pa": {
        "code": "PA", "name": "Pennsylvania", "fips": "42",
        "legislature": "Pennsylvania General Assembly", "session": "2025-2026 Legislative Session", "since": "2025-01-01",
        "url": "https://www.legis.state.pa.us/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 50, "term_years": 4, "next": {"even": 2026, "odd": 2028}},      # from the roster: odd districts began Dec 2020 and Dec 2024, even ones Dec 2018 and Dec 2022
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 203, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Philadelphia", "box": [-75.40, 39.85, -74.95, 40.20]}, {"name": "Pittsburgh", "box": [-80.20, 40.28, -79.75, 40.58]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "wv": {
        "code": "WV", "name": "West Virginia", "fips": "54",
        "legislature": "West Virginia Legislature", "session": "87th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://www.wvlegislature.gov/",
        # each Senate district elects two senators, one at a time, so no district-number rule says when a seat is next up
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 34, "term_years": 4},
        "lower": {"name": "House of Delegates", "full": "House of Delegates", "title": "Delegate", "short": "Del.", "seats": 100, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Charleston", "box": [-81.80, 38.25, -81.45, 38.48]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "va": {
        "code": "VA", "name": "Virginia", "fips": "51",
        "legislature": "Virginia General Assembly", "session": "2026 Session", "since": "2025-01-01",
        "url": "https://virginiageneralassembly.gov/",
        # Virginia votes in odd years: the whole Senate was elected in 2023 and the whole House in 2025
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 40, "term_years": 4, "next": 2027},
        "lower": {"name": "House of Delegates", "full": "House of Delegates", "title": "Delegate", "short": "Del.", "seats": 100, "term_years": 2, "next": 2027},
        "zooms": [{"name": "Northern Virginia", "box": [-77.60, 38.60, -77.00, 39.05]}, {"name": "Richmond", "box": [-77.65, 37.35, -77.25, 37.68]}, {"name": "Hampton Roads", "box": [-76.60, 36.68, -75.95, 37.12]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "nc": {
        "code": "NC", "name": "North Carolina", "fips": "37",
        "legislature": "North Carolina General Assembly", "session": "2025-2026 Session", "since": "2025-01-01",
        "url": "https://www.ncleg.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 50, "term_years": 2, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 120, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Charlotte", "box": [-81.10, 35.02, -80.62, 35.42]}, {"name": "Raleigh and Durham", "box": [-79.10, 35.62, -78.40, 36.12]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ga": {
        "code": "GA", "name": "Georgia", "fips": "13",
        "legislature": "Georgia General Assembly", "session": "2025-2026 term", "since": "2025-01-01",
        "url": "https://www.legis.ga.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 56, "term_years": 2, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 180, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Atlanta", "box": [-84.75, 33.52, -84.05, 34.08]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "al": {
        "code": "AL", "name": "Alabama", "fips": "01",
        "legislature": "Alabama Legislature", "session": "2022-2026 quadrennium", "since": "2025-01-01",
        "url": "https://alison.legislature.state.al.us/",
        # both chambers serve four years and were elected together in 2022
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 35, "term_years": 4, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 105, "term_years": 4, "next": 2026},
        "zooms": [{"name": "Birmingham", "box": [-87.05, 33.32, -86.55, 33.72]}, {"name": "Huntsville", "box": [-86.85, 34.58, -86.40, 34.88]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ms": {
        "code": "MS", "name": "Mississippi", "fips": "28",
        "legislature": "Mississippi Legislature", "session": "2024-2028 term", "since": "2025-01-01",
        "url": "https://www.legislature.ms.gov/",
        # both chambers serve four years and were elected together in 2023
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 52, "term_years": 4, "next": 2027},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 122, "term_years": 4, "next": 2027},
        "zooms": [{"name": "Jackson", "box": [-90.40, 32.18, -89.95, 32.50]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "la": {
        "code": "LA", "name": "Louisiana", "fips": "22",
        "legislature": "Louisiana Legislature", "session": "2024-2028 term", "since": "2025-01-01",
        "url": "https://legis.la.gov/",
        # both chambers serve four years and were elected together in 2023
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 39, "term_years": 4, "next": 2027},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 105, "term_years": 4, "next": 2027},
        "zooms": [{"name": "New Orleans", "box": [-90.35, 29.82, -89.80, 30.12]}, {"name": "Baton Rouge", "box": [-91.30, 30.32, -90.90, 30.58]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent"), "No Party": ("I", "No party")},
        "money": None,
    },
    "tx": {
        "code": "TX", "name": "Texas", "fips": "48",
        "money": "tx_tec",                     # states/money_tx.py: the Texas Ethics Commission's bulk download of every electronically filed report
        "money_agency": {"name": "the Texas Ethics Commission", "url": "https://www.ethics.state.tx.us/search/cf/"},
        "money_rule": "Campaigns list every giver whose gifts in a reporting period pass the Commission's threshold by name, and smaller gifts as one sum. Texas lets political committees, party committees, other campaigns and the partnerships, law firms and associations it allows give directly, and those are named as the campaign reported them; a corporation or union may not give to a Texas candidate. The Commission's bulk file lists a committee's spending for a candidate beside the gifts it made, with no flag to tell the two apart, so no outside spending is shown for Texas.",
        "legislature": "Texas Legislature", "session": "89th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://capitol.texas.gov/",
        # after the 2022 election senators drew lots for two- or four-year terms, so no district-number rule says when a seat is next up
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 31, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 150, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Houston", "box": [-95.80, 29.45, -95.00, 30.10]}, {"name": "Dallas and Fort Worth", "box": [-97.55, 32.50, -96.50, 33.15]},
                  {"name": "San Antonio", "box": [-98.80, 29.20, -98.25, 29.70]}, {"name": "Austin", "box": [-98.00, 30.05, -97.50, 30.55]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
    },
    "nm": {
        "code": "NM", "name": "New Mexico", "fips": "35",
        "legislature": "New Mexico Legislature", "session": "57th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://www.nmlegis.gov/",
        # the whole Senate was elected in 2024 for four years
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 42, "term_years": 4, "next": 2028},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 70, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Albuquerque", "box": [-106.85, 34.92, -106.40, 35.28]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "az": {
        "code": "AZ", "name": "Arizona", "fips": "04",
        "legislature": "Arizona Legislature", "session": "57th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://www.azleg.gov/",
        # each of the thirty districts elects one senator and two representatives, all for two years
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 30, "term_years": 2, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 60, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Phoenix", "box": [-112.50, 33.22, -111.60, 33.78]}, {"name": "Tucson", "box": [-111.15, 32.02, -110.70, 32.38]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "nv": {
        "code": "NV", "name": "Nevada", "fips": "32",
        "legislature": "Nevada Legislature", "session": "83rd Session, 2025-2026", "since": "2025-01-01",
        "url": "https://www.leg.state.nv.us/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 21, "term_years": 4},
        "lower": {"name": "Assembly", "full": "Assembly", "title": "Assembly Member", "short": "Asm.", "seats": 42, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Las Vegas", "box": [-115.40, 35.92, -114.90, 36.38]}, {"name": "Reno", "box": [-120.00, 39.38, -119.62, 39.68]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "or": {
        "code": "OR", "name": "Oregon", "fips": "41",
        "legislature": "Oregon Legislative Assembly", "session": "83rd Legislative Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://www.oregonlegislature.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 30, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 60, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Portland", "box": [-122.90, 45.32, -122.40, 45.68]}],
        "executive": "Governor",
        # a joint nomination is shown as the record writes it, and counted with the party that nominated first
        "parties": {"Democratic": ("D", "Democratic"), "Democratic/Working Families": ("D", "Democratic/Working Families"),
                    "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "wa": {
        "code": "WA", "name": "Washington", "fips": "53",
        "money": "wa_pdc",                     # states/money_wa.py: the Public Disclosure Commission's open data on data.wa.gov
        "money_agency": {"name": "the Washington Public Disclosure Commission", "url": "https://www.pdc.wa.gov/"},
        "money_rule": "Campaigns report every gift, and Washington lets businesses, unions and other organizations give to a campaign directly, so those are named here as the campaign reported them, beside political committees, party and caucus committees; a gift the campaign filed as miscellaneous or anonymous is counted as other.",
        "money_credit": "The data is the Commission's, published on data.wa.gov in the public domain.",
        "legislature": "Washington State Legislature", "session": "69th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://leg.wa.gov/",
        # each of the forty-nine districts elects one senator and two representatives (position 1 and position 2)
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 49, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 98, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Seattle and Tacoma", "box": [-122.60, 47.15, -122.05, 47.85]}, {"name": "Spokane", "box": [-117.60, 47.52, -117.20, 47.78]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
    },
    # The fifth and last ring (2026-09-23): the fifteen states that touch none of the thirty-five above by land, and
    # the two that touch nothing at all. "next" for a staggered Senate is filled in only after the roster check.
    "ny": {
        "code": "NY", "name": "New York", "fips": "36",
        "legislature": "New York State Legislature", "session": "2025-2026 Legislative Session", "since": "2025-01-01",
        "url": "https://www.nysenate.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 63, "term_years": 2, "next": 2026},
        "lower": {"name": "Assembly", "full": "State Assembly", "title": "Assembly Member", "short": "Asm.", "seats": 150, "term_years": 2, "next": 2026},
        "zooms": [{"name": "New York City", "box": [-74.30, 40.48, -73.65, 40.95]}, {"name": "Long Island", "box": [-73.75, 40.55, -72.60, 41.15]}, {"name": "Buffalo", "box": [-79.00, 42.78, -78.65, 43.05]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Democratic/Working Families": ("D", "Democratic/Working Families"), "Republican": ("R", "Republican"),
                    "Republican/Conservative": ("R", "Republican/Conservative"), "Working Families": ("I", "Working Families"), "Independent": ("I", "Independent")},
        "money": "ny_boe",                     # states/money_ny.py: the State Board of Elections' bulk download, carried out of the Browser pane by hand (its site blocks scripts)
        "money_agency": {"name": "the New York State Board of Elections", "url": "https://publicreporting.elections.ny.gov/DownloadCampaignFinanceData/DownloadCampaignFinanceData"},
        "money_rule": "Campaigns list every giver of more than $99 by name and smaller gifts as one sum, counted here as people or other receipts. The Board codes every giver by kind, so political committees and PACs, party committees, other candidates' committees, unions, and the corporations, LLCs, partnerships and associations New York lets give directly are named here as the campaign reported them; a giver filed with no kind is read from its name. The candidate's own money and the candidate's spouse's, which the Board files under one code, count as own money. The committees counted are the ones the Board lists as authorized for the member's Senate or Assembly candidacy, plus the member's own filings as a candidate; a committee tied only to a run for another office is left out. The Board's bulk file records independent spending by office and district but not by candidate, so no outside spending is shown for New York.",
    },
    "nj": {
        "code": "NJ", "name": "New Jersey", "fips": "34",
        "legislature": "New Jersey Legislature", "session": "222nd Legislature, 2026-2027", "since": "2025-01-01",
        "url": "https://www.njleg.state.nj.us/",
        # New Jersey votes in odd years; the whole legislature was elected in November 2025. Each district elects one senator and two Assembly members
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 40, "term_years": 4, "next": 2027},
        "lower": {"name": "General Assembly", "full": "General Assembly", "title": "Assembly Member", "short": "Asm.", "seats": 80, "term_years": 2, "next": 2027},
        "zooms": [{"name": "North Jersey", "box": [-74.45, 40.55, -73.90, 40.98]}, {"name": "Camden and Trenton", "box": [-75.20, 39.85, -74.65, 40.30]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": "nj_elec",                    # states/money_nj.py: the Election Law Enforcement Commission's reports and data search system, asked the way its own pages ask
        "money_agency": {"name": "the New Jersey Election Law Enforcement Commission", "url": "https://www.njelecefilesearch.com/SearchContributionToEntity"},
        "money_rule": "The Commission codes every giver by kind, so political committees, party and legislative leadership committees, other candidates' committees, and the businesses and unions New Jersey lets give directly are named here as the campaign reported them; a giver filed with no kind is read from its name, and counted with people when the name looks like a person's. Campaigns itemize gifts above the Commission's threshold and report smaller ones as one sum, counted here as other receipts. New Jersey's legislative candidates raise much of their money through joint candidates committees, one committee for a district's running mates: a gift to a joint committee is divided here equally among the candidates the committee was formed for, and a member's page names the joint committees their share came through. The Commission's expenditure records do not say which candidate an independent spender supported or opposed, so no outside spending is shown for New Jersey.",
    },
    "de": {
        "code": "DE", "name": "Delaware", "fips": "10",
        "legislature": "Delaware General Assembly", "session": "153rd General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://legis.delaware.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 21, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 41, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Wilmington", "box": [-75.68, 39.62, -75.42, 39.88]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "md": {
        "code": "MD", "name": "Maryland", "fips": "24",
        "legislature": "Maryland General Assembly", "session": "2023-2026 term", "since": "2025-01-01",
        "url": "https://mgaleg.maryland.gov/",
        # both chambers serve four years and were elected together in 2022; House districts elect one, two or three delegates
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 47, "term_years": 4, "next": 2026},
        "lower": {"name": "House of Delegates", "full": "House of Delegates", "title": "Delegate", "short": "Del.", "seats": 141, "term_years": 4, "next": 2026},
        "zooms": [{"name": "Baltimore", "box": [-76.85, 39.12, -76.35, 39.48]}, {"name": "Washington suburbs", "box": [-77.30, 38.82, -76.70, 39.18]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ct": {
        "code": "CT", "name": "Connecticut", "fips": "09",
        "legislature": "Connecticut General Assembly", "session": "2025-2026 term", "since": "2025-01-01",
        "url": "https://www.cga.ct.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 36, "term_years": 2, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 151, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Hartford", "box": [-72.85, 41.65, -72.50, 41.88]}, {"name": "New Haven and Bridgeport", "box": [-73.30, 41.12, -72.80, 41.42]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ri": {
        "code": "RI", "name": "Rhode Island", "fips": "44",
        "legislature": "Rhode Island General Assembly", "session": "2025-2026 term", "since": "2025-01-01",
        "url": "https://www.rilegislature.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 38, "term_years": 2, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 75, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Providence", "box": [-71.55, 41.72, -71.28, 41.92]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ma": {
        "code": "MA", "name": "Massachusetts", "fips": "25",
        "legislature": "Massachusetts General Court", "session": "194th General Court, 2025-2026", "since": "2025-01-01",
        "url": "https://malegislature.gov/",
        # districts are named, not numbered: "First Middlesex", "1st Barnstable"
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 40, "term_years": 2, "next": 2026, "district_name": ""},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 160, "term_years": 2, "next": 2026, "district_name": ""},
        "zooms": [{"name": "Boston", "box": [-71.30, 42.22, -70.90, 42.48]}, {"name": "Worcester", "box": [-71.95, 42.20, -71.70, 42.35]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "vt": {
        "code": "VT", "name": "Vermont", "fips": "50",
        "legislature": "Vermont General Assembly", "session": "2025-2026 biennium", "since": "2025-01-01",
        "url": "https://legislature.vermont.gov/",
        # districts are named ("Chittenden-Central", "Windsor-1"); a Senate district elects one to three senators, a House district one or two
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 30, "term_years": 2, "next": 2026, "district_name": ""},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 150, "term_years": 2, "next": 2026, "district_name": ""},
        "zooms": [{"name": "Burlington", "box": [-73.32, 44.38, -73.08, 44.58]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Progressive": ("I", "Progressive"),
                    "Democratic/Progressive": ("D", "Democratic/Progressive"), "Progressive/Democratic": ("I", "Progressive/Democratic"),
                    "Republican/Democratic": ("R", "Republican/Democratic"), "Democratic/Republican": ("D", "Democratic/Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "nh": {
        "code": "NH", "name": "New Hampshire", "fips": "33",
        "legislature": "New Hampshire General Court", "session": "169th General Court, 2025-2026", "since": "2025-01-01",
        "url": "https://www.gencourt.state.nh.us/",
        # House districts are named by county and number ("Hillsborough 12") and elect from one to eleven representatives; some voters also sit in an overlapping "floterial" district
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 24, "term_years": 2, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 400, "term_years": 2, "next": 2026, "district_name": ""},
        "zooms": [{"name": "Manchester and Nashua", "box": [-71.65, 42.68, -71.32, 43.08]}],
        "executive": "Governor",
        "note": "New Hampshire's House districts are named by county and number and elect from one to eleven representatives each; its floterial districts, each laid over several neighbouring districts and electing representatives of their own, have no lines in the Census Bureau's file, so they are listed in the roster but not drawn on the map.",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "me": {
        "code": "ME", "name": "Maine", "fips": "23",
        "legislature": "Maine Legislature", "session": "132nd Legislature, 2024-2026", "since": "2025-01-01",
        "url": "https://legislature.maine.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 35, "term_years": 2, "next": 2026},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 151, "term_years": 2, "next": 2026,
                  "beyond": "tribal representatives"},       # members the roster lists beside the 151 seats, in a district with no lines
        "zooms": [{"name": "Portland", "box": [-70.45, 43.58, -70.15, 43.78]}],
        "executive": "Governor",
        "note": "Beside its 151 members, the House seats a representative of the Passamaquoddy Tribe and one of the Houlton Band of Maliseet Indians; they sit and speak in the House but do not vote on final passage, and the roster lists each with the tribe as the district.",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "sc": {
        "code": "SC", "name": "South Carolina", "fips": "45",
        "legislature": "South Carolina General Assembly", "session": "126th General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://www.scstatehouse.gov/",
        # the whole Senate was elected in 2024 for four years
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 46, "term_years": 4, "next": 2028},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 124, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Columbia", "box": [-81.20, 33.92, -80.82, 34.18]}, {"name": "Charleston", "box": [-80.15, 32.68, -79.80, 32.98]}, {"name": "Greenville", "box": [-82.55, 34.72, -82.20, 34.98]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "fl": {
        "code": "FL", "name": "Florida", "fips": "12",
        "legislature": "Florida Legislature", "session": "2025-2026 term", "since": "2025-01-01",
        "url": "https://www.flsenate.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 40, "term_years": 4, "next": {"even": 2026, "odd": 2028}},     # after the 2022 redistricting, even-numbered districts drew four-year terms (the roster: elected 2022) and odd-numbered ones two, then four (elected 2024)
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 120, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Miami and Fort Lauderdale", "box": [-80.50, 25.55, -80.05, 26.35]}, {"name": "Tampa Bay", "box": [-82.85, 27.60, -82.25, 28.15]},
                  {"name": "Orlando", "box": [-81.60, 28.35, -81.15, 28.70]}, {"name": "Jacksonville", "box": [-81.90, 30.12, -81.40, 30.48]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": "fl_dos",                     # states/money_fl.py: the Division of Elections' campaign finance database, asked one family name at a time
        "money_agency": {"name": "the Florida Division of Elections", "url": "https://dos.elections.myflorida.com/campaign-finance/contributions/"},
        "money_rule": "Florida campaigns itemize every contribution, so there is no threshold, but the Division's records carry no code for what kind of giver a row is. An organization is named here when its name or its occupation column says it is one: a political committee, a party, or a company by its corporate words; a giver whose name shows neither is counted with people, so a business written without such a word may be hidden, and a person is never shown. The accounts counted are the ones the member opened for State House and Senate races; a political committee a legislator chairs is a separate filer and is not part of the campaign. The Division's expenditure records name payees and purposes but not the candidate a committee spent for or against, so no outside spending is shown for Florida.",
    },
    "ca": {
        "code": "CA", "name": "California", "fips": "06",
        "legislature": "California State Legislature", "session": "2025-2026 Regular Session", "since": "2025-01-01",
        "url": "https://www.legislature.ca.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 40, "term_years": 4, "next": {"even": 2026, "odd": 2028}},     # after the 2022 redistricting, even-numbered districts drew four-year terms (the roster: elected 2022) and odd-numbered ones two, then four (elected 2024)
        "lower": {"name": "Assembly", "full": "State Assembly", "title": "Assembly Member", "short": "Asm.", "seats": 80, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Los Angeles", "box": [-118.70, 33.65, -117.80, 34.30]}, {"name": "San Francisco Bay", "box": [-122.60, 37.25, -121.75, 38.00]},
                  {"name": "San Diego", "box": [-117.35, 32.55, -116.85, 33.10]}, {"name": "Sacramento", "box": [-121.65, 38.40, -121.25, 38.75]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent"), "No Party Preference": ("I", "No party preference")},
        "money": "ca_calaccess",               # states/money_ca.py: the Secretary of State's Cal-Access raw data export, every table as text
        "money_agency": {"name": "the California Secretary of State", "url": "https://www.sos.ca.gov/campaign-lobbying/cal-access-resources/raw-data-campaign-finance-and-lobbying-activity"},
        "money_rule": "Campaigns list every giver of $100 or more in a year by name on their Form 460 statements and report smaller gifts as one sum, counted here as other receipts. California lets businesses, unions, tribes and associations give to candidates directly, within limits, and Cal-Access files them all under one code, so they are named as the campaign reported them and labelled other organizations. The committees counted are the ones for the Assembly or Senate seat (candidate committees, officeholder accounts and legal defense funds); a legislator's ballot measure committee and a committee for another office are left out. The record runs through the last semi-annual or pre-election statement on file. Outside spending is read from the schedules on which a spender names the candidate; a major donor filing on its own is named only when its name shows it to be an organization, because the file does not tell a business from a person.",
    },
    "ak": {
        "code": "AK", "name": "Alaska", "fips": "02",
        "legislature": "Alaska State Legislature", "session": "34th Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://akleg.gov/",
        # Senate districts are lettered A to T and elected on a rota, not by letter
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 20, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 40, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Anchorage", "box": [-150.10, 61.02, -149.60, 61.32]}, {"name": "Fairbanks", "box": [-147.95, 64.75, -147.55, 64.92]}],
        "tolerance": 0.02,                                        # its coastline is drawn at about 250 m rather than 80 m, a fifth of the points
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent"), "Nonpartisan": ("I", "Nonpartisan"), "Undeclared": ("I", "Undeclared")},
        "money": None,
    },
    "hi": {
        "code": "HI", "name": "Hawaii", "fips": "15",
        "legislature": "Hawaii State Legislature", "session": "33rd Legislature, 2025-2026", "since": "2025-01-01",
        "url": "https://www.capitol.hawaii.gov/",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 25, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 51, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Honolulu", "box": [-158.15, 21.22, -157.62, 21.48]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
        "money": None,
    },
    "ia": {
        "code": "IA", "name": "Iowa", "fips": "19",
        "legislature": "Iowa General Assembly", "session": "91st General Assembly, 2025-2026", "since": "2025-01-01",
        "url": "https://www.legis.iowa.gov/",
        "money": "ia_iecdb",                   # states/money_ia.py: the Iowa Ethics and Campaign Disclosure Board's datasets on data.iowa.gov
        "money_agency": {"name": "the Iowa Ethics and Campaign Disclosure Board", "url": "https://ethics.iowa.gov/"},
        "money_rule": "Campaigns list every giver whose gifts pass $25 in a year and report smaller gifts as one sum. Iowa's file names registered committees by number; a giver it names without a number (a bank paying interest, a business, an unitemized line) is counted in the totals as other receipts and not named here.",
        "money_credit": "The data is the Board's, published on data.iowa.gov under a Creative Commons Attribution-NonCommercial licence; this site is not commercial.",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 50, "term_years": 4, "next": {"odd": 2026, "even": 2028}},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 100, "term_years": 2, "next": 2026},
        "zooms": [{"name": "Des Moines", "box": [-93.92, 41.45, -93.40, 41.78]}],
        "executive": "Governor",
        "parties": {"Democratic": ("D", "Democratic"), "Republican": ("R", "Republican"), "Independent": ("I", "Independent")},
    },
}


def place(code):
    try:
        return PLACES[code.lower()]
    except KeyError:
        raise SystemExit(f"'{code}' is not set up yet. Places so far: {', '.join(sorted(PLACES))}")


def party_code(p, name):
    """(code for colour and counting, the label to show) for a party name as the roster writes it.

    A joint nomination ("Democratic/Working Families", "Republican/Conservative/Independence") is counted with the
    party named first, which is the member's own, and shown with the whole label as the record writes it."""
    name = name or ""
    if name in p["parties"]:
        return p["parties"][name]
    if "/" in name and name.split("/")[0].strip() in p["parties"]:
        return p["parties"][name.split("/")[0].strip()][0], name
    return "I", name or "Independent"
