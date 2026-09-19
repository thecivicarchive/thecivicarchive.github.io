# Plain Congress build kit

**Live site: https://thecivicarchive.github.io/**

Pipeline and site generator for Plain Congress: every bill and joint resolution in the current Congress, every
recorded floor vote member by member, plain-language ratings, and a one-file website with a state-by-state vote map.

Current build: 16,364 measures of the 119th Congress, 108 of them law, and all 608 recorded floor votes loaded
member by member. Every member on every roll call reconciles against the official tally, except two Senate votes
decided by the Vice President's tie-breaker, who is not a senator and so is not counted among the 100.

    python run_all.py check      # environment and network
    python run_all.py smoke      # offline test (8 bundled bills)
    python run_all.py            # full build: roster, catalog, roll calls, portraits, district lines, ratings, site, verify
    python run_all.py refresh    # weekly update

Outputs: congress_119.sqlite (database), congress_119.xlsx (Excel copy), site/index.html (website),
verify_report.md (reconciliation and coverage), logs/ (one log per run).

See START_HERE.txt to get going (or double-click the Start Claude Code launcher for your system) and CLAUDE.md for the full instructions Claude Code follows. Data sources are
public-domain government records (GovInfo Bill Status, House Clerk and Senate roll calls) and the
congress-legislators roster (CC0).
