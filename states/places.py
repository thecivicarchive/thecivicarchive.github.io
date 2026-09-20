"""What is particular to each place: what its legislature and chambers are called, how its parties map onto the
site's colours, its Census number. A state is added here first; everything else reads from this.

Party codes are only for colour and arithmetic (D, R, I). The name a state uses for a party is always kept and
shown as the state writes it: Minnesota's Democrats are the Democratic-Farmer-Labor Party, the DFL."""

PLACES = {
    "mn": {
        "code": "MN", "name": "Minnesota", "fips": "27",
        "legislature": "Minnesota Legislature", "session": "94th Legislature, 2025-2026", "since": "2025-01-01",
        "upper": {"name": "Senate", "title": "Senator", "short": "Sen.", "seats": 67, "term_years": 4},
        "lower": {"name": "House", "full": "House of Representatives", "title": "Representative", "short": "Rep.", "seats": 134, "term_years": 2},
        "executive": "Governor",
        "parties": {"Democratic-Farmer-Labor": ("D", "DFL"), "Democratic": ("D", "DFL"), "Republican": ("R", "Republican"),
                    "Independent": ("I", "Independent")},
        "bill_prefixes": {"HF": "House File", "SF": "Senate File"},
        "money": "mn_cfb",                     # which campaign-finance loader this state uses; None until one is written
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
