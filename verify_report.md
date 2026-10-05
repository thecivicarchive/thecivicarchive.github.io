# Verify report, 2026-10-05 08:24

Database: `congress_119.sqlite`

| Check | Result |
| --- | --- |
| Measures | 16,815 (hr 10,714, s 5,663, sjres 220, hjres 218) |
| Became law | 120 |
| Latest action in the data | 2026-10-01 |
| Roll calls linked to these measures | 613 |
| ...with member-level votes loaded | 609 (99.3%) |
| Member votes add up to the official tally | 607 of 609 votes match |
| Members on roll calls matched to the roster | all |
| Party backing computed from roll calls | 330 measures (of 979 with a recorded passage vote) |
| Measures with full ratings | 10 |
| Campaign money (FEC bulk files), 2016 to 2026 | 1,683,658 committee payments; 537 of 539 current members have FEC records |
| ...what committees say they gave vs. what campaigns say they received, 2024 | $420M vs. $448M (94%) |
| Current members with a portrait | 524 of 539 |
| District lines | 429 districts, 119th Congress lines (Census Bureau cb_2024_us_cd119_500k.zip) |
| Site file | site/index.html, 10.6 MB (fits a claude.ai artifact) |

## Result

CHECK:

- 4 roll call(s) still lack member votes: re-run `python run_all.py rollcalls`.
- 2 vote(s) where member counts differ from the official tally (listed below).

## Votes that do not reconcile

- hr1-119|S|2025-07-01|372: members 50-50 vs official 51-50 https://www.senate.gov/legislative/LIS/roll_call_votes/vote1191/vote_119_1_00372.htm
- hr4-119|S|2025-07-15|392: members 50-50 vs official 51-50 https://www.senate.gov/legislative/LIS/roll_call_votes/vote1191/vote_119_1_00392.htm
