# Election Night: prediction data and method (model scout)

Written 2026-10-09 by the model scout. Research only: no file in the kit was changed, and this is the only file
written. Every address below was opened or queried on **2026-10-09** unless the line says "found by search" (seen only
in a web search result, not opened) or "kit cache" (read from a copy the kit downloaded earlier, with that date). No
Minnesota Secretary of State host was requested (they show this machine a CAPTCHA). No personal contact details were
printed or kept; candidate names were never printed.

## In plain words

- **Past results by precinct exist and most are already reachable.** The Secretary of State's own precinct tables,
  published on the Minnesota Geospatial Commons, cover every general election from 2012 to 2024 for federal,
  statewide and legislative offices, with registration, same-day registration, absentee and Election Day counts for
  every precinct. The kit reads 5 of their contests today.
- **Judges, county offices and soil and water supervisors** (2022 and 2024, by precinct) are in the MIT Election Data
  and Science Lab's public-domain copies of the Secretary's files. **Cities, school boards, hospital districts and
  townships are only in the Secretary's own files, which John has to save by hand**; the kit's folders for 2022, 2024
  and the August 11, 2026 primary are empty.
- **Census figures exist for every block group** (the 2020-2024 survey, published January 2026), including marital
  status, households with children, poverty, citizens of voting age and how long people have lived where they live.
  The kit already holds 7 of the needed tables at block-group level; 6 more need downloading (about 330 MB).
- **The three blind spots, in Minnesota's law and files:** absentee votes are folded into each precinct's count by law,
  so no file says how absentee voters voted; the one count-order effect the law allows is a late batch of absentee
  ballots (received after 3 p.m. on Election Day), whose size each county must post on its website. Roll-off is large
  and measurable: 18 to 52 percent of voters skip a county or judicial race. Minnesota rotates the order of names
  precinct by precinct for nonpartisan state, county, judicial and city offices and, since 2024, for partisan offices
  other than President (townships list names alphabetically), so the first-listed edge mostly cancels within a race
  but shows up precinct by precinct; measuring it needs each precinct's printed order.
- **The method:** a forecast for every race before Election Day from past results, Census figures, incumbency,
  endorsements on the record, polls and money where they exist; on election night, a model that compares each
  reported precinct with what was expected and projects the precincts not yet in, run 1,000 or more times with random
  error to give each candidate a chance of winning and a likely vote range. A full Minnesota run took **7.2 seconds**
  on John's computer in a timing test. Every run is kept as a version, so each race page can draw its trend.
- **What it can never be:** a result. Every figure is labelled Analysis; only the official count and canvass decide.

---

## 1. Minnesota: what data exists

### 1.1 Past official results

| What | Where | Format | Geography | Years | In the kit? |
| --- | --- | --- | --- | --- | --- |
| Secretary of State precinct tables, general elections: federal, statewide, legislative offices plus registration and ballot-type counts | Minnesota Geospatial Commons items 40bde6cc6dfc4623b665e6cdb0bda21c ("2012-2020") and 446a973217ce46da9cc96bf43120fbba ("2022-2030"); served at `https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_sos/bdry_electionresults_2012_2020/FeatureServer` and `.../bdry_electionresults_2022_2030/FeatureServer` | ArcGIS feature service, JSON, 2,000 rows a request; one layer per election (2024 = layer 0, 2022 = layer 1, 2020 = layer 0 of the older service) | precinct (VTDID), with county, city or township, every district | 2012, 2014, 2016, 2018, 2020, 2022, 2024 | Partly: `ballot/mn_place_votes.py` reads President, U.S. Senate 2020 and 2024 and Governor 2022 only |
| Judges, county offices, soil and water, county questions | MIT Election Data and Science Lab (MEDSL): `https://github.com/MEDSL/2024-elections-official` (`individual_states/mn24.zip`, 2.1 MB) and `https://github.com/MEDSL/2022-elections-official` (`individual_states/2022-mn-local-precinct-general.zip`, 2.5 MB) | zipped CSV, one row per candidate per precinct | precinct | 2022, 2024 (also 2016-2020 in MEDSL's older repositories) | No |
| Cities, school districts, hospital districts, townships (and every other office) | The Secretary's "Media Files" text files for each election (results host; never requested) | semicolon-separated text, one line per candidate per precinct (layout in `states/load_local_results.py`) | precinct | every election | No: `states_cache/mn_local/sos/20221108/`, `20241105/` and `20260811/` are empty |
| 2026 state primary (August 11) | the same Media Files | as above | precinct | 2026 | No (folder empty; MEDSL has no 2026 files) |
| Older generals | LCC-GIS: `https://gis.lcc.mn.gov/data/shape/elec2010.zip` (5.3 MB, checked with a HEAD request) and metadata pages such as `https://gis.lcc.mn.gov/metadata/elec10.htm` (opened); 2002 and 2006 are not at that file path | zipped shapefile | precinct | 2002-2012 (metadata pages found by search) | No |
| Secondary compilations | OpenElections `https://github.com/openelections/openelections-data-mn` (2012-2022 precinct CSVs, 2022 file 23 MB, no 2024); VEST via the University of Florida Election Lab, e.g. `https://election.lab.ufl.edu/dataset/mn-2016-precinct-level-election-results/` (2016-2024, found by search, licence not checked); Minnesota Historical Election Archive `https://mn.electionarchives.lib.umn.edu/` (district-level returns since 1857 incl. primaries, no precinct data or bulk download; found by search) | various | precinct / district | various | The kit uses the Archive's 2022 governor canvass as a control |
| Official totals for controls | Clerk of the House, Statistics of the Presidential and Congressional Election 2020 and 2024 | PDF | state, district | 2020, 2024 | Yes (`states_cache/mn_local/clerk_statistics*.pdf`) |

**What the Secretary's precinct tables hold** (column definitions from the Secretary's metadata, kit cache of
2026-10-01, and a live query of the 2024 layer today):

- Ids and districts: VTDID, precinct name and code, city or township (MCD), county, congressional, Senate, House,
  county commissioner, judicial, soil and water, ward, hospital and park districts.
- Statistics, certified by the county canvassing boards: `REG7AM` (registered at 7 a.m.), `EDR` (registered on
  Election Day), `SIGNATURES` (voted in person on Election Day), `AB_MB` (absentee, military and overseas, and mail
  ballots accepted; from 2014), `FEDONLYAB`, `PRESONLYAB` (federal-only and president-only ballots), `TOTVOTING`,
  `MAILBALLOT` (all-mail precinct) and `TABMODEL` (the tabulator that processed most ballots).
- Contests: 2012 President, U.S. Senate, U.S. House, Senate, House, 2 amendments; 2014 U.S. Senate, U.S. House, House,
  Governor, Secretary of State, Auditor, Attorney General; 2016 President, U.S. House, Senate, House, amendment; 2018 both
  U.S. Senate seats, U.S. House, Senate, House, the four constitutional offices; 2020 President, U.S. Senate, U.S. House,
  Senate, House; 2022 the four constitutional offices, U.S. House, Senate, House; 2024 President, U.S. Senate, U.S.
  House, House, Senate specials, amendment 1.
- Not in them: judges, county, city, school, hospital, soil and water, township offices, and primaries.

**Measured today from these tables** (two-party DFL share, precincts with 50 or more two-party votes, weighted by votes):

| Comparison | Precincts matched | Correlation | Average shift | Shift, standard deviation (within counties) |
| --- | --- | --- | --- | --- |
| President 2020 to President 2024 | 3,594 | 0.979 | -0.7 points | 3.9 (3.7) points |
| Governor 2022 to President 2024 | 3,741 | 0.990 | -1.6 points | 2.7 (2.4) points |
| President 2020 to Governor 2022 | 3,475 | 0.981 | +0.9 points | 3.7 (3.5) points |
| President 2024 vs U.S. Senate 2024, same ballot | 3,740 | 0.993 | +5.9 points to the Senate DFL candidate | 2.8 (1.9) points |

Precinct lean is very stable; most of the precinct-to-precinct movement happens within counties, not between them; a
single candidate can run 6 points ahead of the ticket statewide. Precinct continuity: 4,078 of the 4,105 precincts in
today's "Voting Districts, Minnesota" (current to 2026-06-26, kit cache of 2026-10-01) carry a VTDID found in the 2024
table and 4,068 one found in 2022; the other 27 need the block crosswalk in 1.3.

**MEDSL's Minnesota files** (downloaded into memory today, nothing kept in the kit): compiled from the Secretary's
Media Files (the 2024 README names the Secretary's media page as its source), licence CC0 1.0 (Harvard Dataverse
dataset doi:10.7910/DVN/XDJYKC, "U.S. President Precinct-Level Returns 2024", licence read through the Dataverse API).
A labelled secondary source, never the authority. All Minnesota rows are mode `TOTAL`. 2024: 290,393 rows, 56 offices
(President, U.S. Senate, U.S. House, House, Senate special, Supreme Court, Court of Appeals, district courts, county
commissioner, county park commissioner, county questions, soil and water, amendment). 2022: 333,277 rows, 126 offices
(adds the four constitutional offices, Senate, county attorney, sheriff, auditor, auditor-treasurer, treasurer,
recorder, surveyor, coroner, special elections). **No city, school, hospital or township offices in either year.**
Contested contests usable for testing, 2022 and 2024 together: House 247, Senate 60, U.S. House 16, statewide partisan
6 (four constitutional offices in 2022, President and U.S. Senate in 2024), county offices about 311, soil and water
about 35, judicial about 10 (most judges run unopposed).

### 1.2 Registration

- Past: `REG7AM` and `EDR` for every precinct, every general election 2012-2024 (tables above). 2024: 3,272,414 ballots;
  3,686,596 registered at 7 a.m.; 296,287 registered on Election Day (9.1 percent of ballots); ballots were 82.2 percent
  of everyone registered by the end of the day. 2022: 2,525,873 ballots, Election Day registration 5.6 percent; 2020:
  3,292,997 ballots, 7.9 percent.
- 2026: the Secretary's "Voter Registration Counts" page,
  `https://sos.mn.gov/election-administration-campaigns/data-maps/voter-registration-counts` (found by search, not
  opened): spreadsheets by county and by precinct dated the first of each month, and a "precinct-split" file dated
  May 1 (the very count the ballot-rotation rule uses, 2.3). **John's save:** the newest precinct file and the May 1,
  2026 precinct-split file.
- A news report says the state counts 1,136 mail-ballot precincts this year (KTTC, 2026-10-06,
  `https://www.kttc.com/2026/10/06/state-reports-1136-mail-ballot-precincts-this-election-mower-county-leads-southeast-minnesota-total/`,
  found by search, not opened); 2024 had 1,126 (`MAILBALLOT = YES`, measured today).

### 1.3 Census figures

- Source: ACS 2020-2024 5-year table-based summary file, `https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/`
  (1,198 table files dated 2026-01-29; each a national pipe-delimited `.dat`: `GEO_ID`, then an estimate and a margin
  per cell; geography in `documentation/Geos20245YR.txt`). Keyless static files; the keyed Census data API is not used.
- Already in the kit (`states_cache/acs2024/`, national files, used by `district_people.py`). With Minnesota's 4,706
  block groups: B01001 sex by age, B01002 median age, B01003 population, B03002 Hispanic origin by race, B15003
  education, B19013 median household income, B25003 owners and renters. Tract level only (1,505 Minnesota tracts):
  B05002 place of birth, B09001 under 18, B17001 poverty.
- Still needed, each checked today for block-group rows by reading a 6 KB slice from the middle of the file (size as the
  server lists it):

| Table | What | Size | Lowest level |
| --- | --- | --- | --- |
| B12001 | marital status by sex | 78 MB | block group |
| B11005 | households by presence of people under 18 | 75 MB | block group |
| C17002 | ratio of income to poverty level (poverty at block-group level) | 40 MB | block group |
| B25038 | tenure by year householder moved in (residential mobility) | 61 MB | block group |
| B29001 | citizen voting-age population by age | 21 MB | block group |
| B07003 | moved in the past year | 41 MB | tract (no block-group rows where checked) |
| CVAP special tabulation 2020-2024 | citizens of voting age by race and ethnicity | 56 MB zip, `https://www2.census.gov/programs-surveys/decennial/rdo/datasets/2024/2024-cvap/CVAP_2020-2024_ACS_csv_files.zip` (dated 2026-01-30) | block group |

- 2020 census blocks (for carrying figures down): `https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_27_tabblock20.zip`
  (253 MB; every block's shape, 2020 population, housing units and internal point) and
  `https://www2.census.gov/geo/docs/maps-data/data/baf2020/BlockAssign_ST27_MN.zip` (4.7 MB; block to 2020 voting
  district, place, school district). Voting-age population by block, if wanted: the PL 94-171 file under
  `https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/`.
- **Carrying block-group figures to precincts and to every district:**
  1. Put each 2020 block in today's precinct by its internal point, using the kit's full precinct shapes
     (`states_cache/mn_local/sos_votingdistricts_geometry_4326.json.gz`, 4,105 precincts; not the simplified map tiles).
     Precinct lines were drawn on 2020 block lines for 2022 (Minn. Stat. 204B.14 subd. 6 as it reads in versions through
     2014, found by search; current text not opened); a later annexation can cut a block, which then goes to one side.
  2. Share each block group's estimate among its blocks in proportion to 2020 population (people tables), housing units
     (household tables) or adults (adult tables).
  3. Add blocks into precincts, and precincts into any district made of whole precincts: county, city or township,
     ward, commissioner, Senate, House, congressional, judicial, soil and water, hospital, park. School districts split
     precincts, so add blocks straight into school districts with the kit's Education Department shapes.
  4. Margins: the ACS handbook's approximations already coded and self-tested in `district_people.py` (root sum of
     squares for sums, the proportion formula for shares); parts of one block group are treated as fully correlated.
  5. Controls: blocks add to the state's 2020 count; each precinct's figures against its 2024 registration, with the
     outliers listed.
  The figures describe places, never voters, and the page calls every derived figure Analysis.

### 1.4 Polls

- Rule as everywhere in the kit: members of AAPOR's Transparency Initiative only (`ballot/polls/aapor_ti_members.json`,
  92 members). Minnesota (read today from `ballot/polls/polls_mn_state_2026.json` and `polls_2026.json`): Governor, one
  poll (Emerson College Polling, February 6-8, 2026, 1,000, ±3.0); U.S. Senate, one (Emerson, February 2026); Attorney
  General, Secretary of State, Auditor and Hennepin County Attorney, none. Every other Minnesota race: none.
- Polls in other states still help Minnesota: the member polls in the 35 Senate races (16 with checked polls) measure
  the national midterm mood, each poll against its state's 2024 presidential result.

### 1.5 Money

- Congress: FEC 2026 totals for 2,806 candidates in `ballot_2026.sqlite` (`fec26_totals`: receipts by source, loans,
  spending, cash on hand, coverage date).
- Legislature: the Campaign Finance Board files the kit already reads (`state_mn.sqlite`), sitting members only today;
  challengers' committees are in the same Board files.
- County, city, school: none collected (filed with county auditors and city clerks).

### 1.6 Candidates, incumbents, endorsements

- `ballot_local_2026.sqlite`: 4,721 Minnesota races (205 partisan, 4,516 nonpartisan): city 1,761, township 1,579,
  county 454, school 347, Legislature 201, soil and water 197, courts 121, hospital 55, statewide 4, other 2. 2,961
  have one name, 1,042 two, 718 three or more.
- Incumbent flag set in only 160 races; holder fields exist for legislators and judges. For local seats the incumbent
  comes from the 2022 and 2024 winners, which needs the Media Files in 1.1.
- Party endorsements on the record: `ballot/lean/mn_endorsements.json`; how each place voted:
  `ballot/lean/mn_place_votes.json`.

### 1.7 What the model needs live on election night

- Results: John's saved Media Files (the results feed is another scout's subject).
- Late absentee ballots: each county must post on its own website how many remain to be counted (Minn. Stat.
  204C.19 subd. 3, below), so county sites can be read; the Secretary's own "unprocessed absentee ballot counts" page
  (2024's: `https://www.sos.mn.gov/elections-voting/election-results/2024/2024-general-election-results/2024-state-general-election-unprocessed-absentee-ballot-counts/`,
  found by search, not opened) is John's save.

---

## 2. The three blind spots

### 2.1 Count order

**The law** (read today on revisor.mn.gov):

- Minn. Stat. 203B.121 (`https://www.revisor.mn.gov/statutes/cite/203B.121`): accepted absentee envelopes may be
  opened after the close of business on the 19th day before the election, precinct by precinct (subd. 4). Subd. 5(b):
  "After the polls have closed on election day" the ballot board counts them; in state primaries and generals the count
  is by precinct and "These vote totals must be added to the vote totals on the summary statements of the returns for
  the appropriate precinct"; nothing may be made public before voting closes. Subd. 5(c): accepted ballots that arrive
  late are checked within 24 hours and added.
- Minn. Stat. 204C.19 subd. 3 (`https://www.revisor.mn.gov/statutes/cite/204C.19`, amended 2024): no precinct's
  results may be disclosed until all of that precinct's results are available; absentee ballots received by the county
  after 3:00 p.m. on Election Day may be added after the precinct's first report; the county must report the number
  still to be processed to the Secretary and on its website, and afterwards how many were accepted and rejected.
- Hennepin County (`https://www.hennepincounty.gov/services/elections/election-results`): absentee results are combined
  with polling-place results and posted to the State Election Reporting System; ballots received after 3 p.m. may be
  processed and reported later.
- A 2026 law lets each city choose between a 46-day in-person absentee window and an 18-day early-voting window in
  which voters feed their ballot straight into a tabulator (Senate summary of Laws 2026, chapter 116,
  `https://assets.senate.mn/summ/chapter/2026/0/Chapter%20116%20Summary.pdf`, found by search, not opened). Results
  still stay sealed until polls close.

**What Minnesota's files say:** nothing about how each kind of ballot voted. Each precinct carries only counts:
`AB_MB`, `SIGNATURES`, `EDR`, `TOTVOTING`, `MAILBALLOT`. Measured today:

- Absentee and mail ballots: 39.8 percent of ballots in 2024 (1,304,018), 26.6 percent in 2022 (671,493), 57.9 percent in
  2020 (1,906,383). 1,126 of 4,103 precincts voted entirely by mail in 2024.
- Per precinct (50 or more voters) the absentee share runs from 13 percent (10th percentile) through 35 percent
  (median) to 100 percent (90th, the mail precincts); by county from 16 percent (Swift) to 87 percent (Grant).
- Absentee share against the DFL share of the two-party presidential vote: correlation +0.19 across precincts, but
  -0.005 within counties. The files cannot say how absentee voters voted; this is a figure about places only.
- Tabulators: a precinct scanner (DS200) did most of the counting in 2,958 precincts; a central-count scanner (DS450 or
  DS850) is named for at least 475 (alone in 270).

**So in Minnesota, count order means two things:**

1. *Which precincts come in first.* Each precinct reports once and complete. Nothing on record shows the order on past
   nights without the Secretary's hosts. The order is learned on the night from the time stamps of John's saves; the
   model never assumes the precincts already in are typical (it projects the rest from their own features, 3.3).
   One possible record of past nights is the Internet Archive's captures of the Secretary's results pages (as was used
   for Ohio's workbooks): not checked, John's decision.
2. *The late absentee batch per county*, with its size posted by the county and added after the precinct counts. News
   reports say Hennepin County added such ballots at about 1:30 a.m. after the 2024 general (KSTP,
   `https://kstp.com/?p=3425475`, found by search, not opened, date not confirmed). The batch is modelled as its own
   block of outstanding votes: size from the county website, lean unknown in advance (a wide prior, 3.3), learned
   when the county adds it.

**Each ballot type's past lean** cannot be measured from Minnesota's files. States whose files split votes by type
give a prior: MEDSL's 2024 files keep Oklahoma's absentee, early and in-person counts and South Carolina's Election
Day, early, absentee, failsafe and provisional counts for every precinct (checked today); Georgia, Kentucky, Wisconsin
and Minnesota are totals only there.

### 2.2 Roll-off

The share of voters who skip a race (per seat in races electing several). Measured today:

- Against ballots cast, 2024 precinct table: President 0.6 percent, U.S. Senate 2.5, U.S. House 3.8, state House 5.5
  (unopposed seats included). U.S. House roll-off runs from 1.3 percent (10th percentile precinct) to 5.8 (90th).
- Against the top race on the ballot, MEDSL precinct files (statewide figure; middle 80 percent of precincts):

| 2024, against President | Roll-off | Precincts, 10th to 90th percentile |
| --- | --- | --- |
| County commissioner, contested | 25% | 7% to 34% |
| Supreme Court, contested / one name | 27% / 41% | 15-33% / 25-49% |
| Court of Appeals, contested / one name | 31% / 43% | 17-36% / 25-52% |
| District court, contested / one name | 34% / 47% | 22-42% / 28-55% |
| Soil and water, contested | 32% | 14% to 39% |
| Constitutional amendment | 6% | 3% to 9% |

| 2022, against Governor | Roll-off |
| --- | --- |
| County attorney 24%, sheriff 21%, commissioner 21%, recorder 21%, auditor-treasurer 18% | 3% to 33% across precincts (10th to 90th percentile) |
| Soil and water 27%; district court contested 33%, one name 52%; Court of Appeals one name 52% | |

Why it matters: roll-off varies by 25 points or more between precincts, so the people deciding a judicial or county
race are not the people deciding the governor's race; a candidate whose strength sits in high-roll-off precincts is
overestimated by any top-of-ticket baseline. The model uses it three ways: the expected votes in each race from the
ballots counted; a check that a precinct's count is complete; and the weight of each precinct inside a down-ballot
race. For state and local races the denominator is ballots minus federal-only and president-only ballots. Cities and
schools need the Media Files.

### 2.3 Ballot position

**The law** (all read today on revisor.mn.gov):

- Minn. Stat. 204D.13 subd. 2a (`https://www.revisor.mn.gov/statutes/cite/204D.13`, new in 2023, c 62 art 4 s 102):
  names for partisan offices on the general ballot "shall be rotated in the manner provided for rotation of names on
  state partisan primary ballots by section 204D.08, subdivision 3", except President, where major parties stand in
  reverse order of their average statewide vote (subd. 2). The older wording gave every partisan office that fixed
  party order ("the first name printed for each partisan office", found by search), and the Secretary's 2024
  example-ballot notes cite the rotation rule (found by search, not opened), so 2024 appears to be the first general
  with rotated partisan names. The effective date of the 2023 section was not confirmed.
- 204D.08 subd. 3 (`https://www.revisor.mn.gov/statutes/cite/204D.08`): each name "substantially an equal number of
  times at the top, at the bottom, and at each intermediate place"; with no more candidates than seats, no rotation and
  order by lot.
- 204D.14 subd. 1 (`https://www.revisor.mn.gov/statutes/cite/204D.14`): nonpartisan offices on the state general and
  judicial ballots rotate the same way; subd. 3: an unopposed judgeship is listed after that court's other offices.
- 205.17 subd. 1 (`https://www.revisor.mn.gov/statutes/cite/205.17`): city ballots are arranged "in the manner provided
  for the state elections"; **town ballots alphabetically by surname** unless the town meeting chose state-style
  rotation for at least two years running.
- 206.61 subd. 5 (`https://www.revisor.mn.gov/statutes/cite/206.61`): rotation by precinct, the same order on every
  machine in a precinct, based on registered voters at 8 a.m. on May 1.
- Minn. R. 8220.0825 (`https://www.revisor.mn.gov/rules/8220.0825/`): base order by lot (the Secretary for partisan
  primary offices, county auditors for all others, who may delegate to city and school clerks); precincts sorted by
  May 1 registration, largest first; one rotation per candidate; each next precinct joins the rotation with the lowest
  running total; item F: "Print a report by race showing rotation subtotals." The rule names 205.17 and 447.32
  (hospital districts) among its authorities.

**What follows:** inside a rotated race every candidate is listed first for about the same number of registered
voters, so the first-listed edge nearly cancels for the race as a whole. It matters (1) precinct by precinct, which is
where the live model looks; (2) in township races, where one surname is first everywhere; (3) for comparing 2024 with
earlier years.

**Measuring the edge:** compare each candidate's share where they were listed first with where they were not, with
the precinct's other contests as the control. Assignment follows precinct size, not politics, so it is close to a
natural experiment once size is accounted for. Data: 2024 rotated partisan races (U.S. Senate, U.S. House, House) and
the rotated nonpartisan races of 2022 and 2024. It needs each precinct's printed order, from one of:

- the county auditors' rotation reports (the rule's item F): a public-data request to 87 counties, John's step;
- precinct sample ballots: mostly behind the Secretary's "My Ballot" tool; a few cities post precinct ballots
  (Golden Valley's 2022 primary ballot P-8, found by search);
- rebuilding the order from the base order (read off any one precinct's ballot) and the May 1 precinct-split counts
  with the rule's algorithm (exact only if the counts match the auditor's);
- the "candidate order" column of the Media Files, if it turns out to be each precinct's printed position (check it on
  the first file John saves).

**Size to expect** (a prior until Minnesota's own estimate exists): larger in low-information nonpartisan races.
Meredith and Salant found that ballot order decided more than 5 percent of California's city council and school board
races (`https://siepr.stanford.edu/publications/working-paper/causes-and-consequences-ballot-order-effects`, found by
search); Ho and Imai found effects in California's statewide general elections only for minor-party candidates
(`https://imai.fas.harvard.edu/research/alphabet.html`, found by search). Prior: 0 to 1 point in partisan races, 1 to 4
in nonpartisan ones.

---

## 3. The method

### 3.1 The pieces

```
precinct tables + Media Files + Census (blocks -> precincts) + registration + candidates
        |
        v
  features per precinct (lean, turnout, roll-off by office, ballot mix, population figures)
        |
        +--> pre-election forecast, every race (daily until Nov 3, and on any new poll, filing or saved file)
        |
        +--> election-night model, every race (each new snapshot of results)
        |
        v
  run store (every run, its inputs' fingerprints, its outputs)  -->  page files per race (trend across runs)
```

Unit: today's precinct (4,105). Every race is a set of precincts (or, for school districts, of precinct parts by block).
Everything is computed for places; nothing is ever said about a voter.

### 3.2 Pre-election forecast

**Partisan races** (Governor, the other three constitutional offices, U.S. Senate, U.S. House, Senate, House):

- *Precinct lean*: a weighted average of the precinct's DFL two-party share in recent contests, each measured against
  that contest's statewide result (2024 President, U.S. Senate, U.S. House, House; 2022 Governor and the other offices,
  Senate, House; older years with less weight). Weights come from the backtest (3.5).
- *Statewide mood for 2026* by office: Minnesota's own midterm history (2014, 2018, 2022 against the presidential year
  before), the national midterm mood from AAPOR-member Senate polls in every state, and Minnesota's own member polls
  where any exist. Before polls, a spread of about 4 points.
- *Turnout* per precinct: 2026 registration times the precinct's midterm turnout rate (2014, 2018, 2022), adjusted by the
  Census figures that predicted midterm drop-off in the backtest (age, renting, moving, education).
- *Roll-off* per precinct and office class from 2022 and 2018.
- *Candidate terms*: incumbency (estimated from 2022 and 2024 legislative races, with past incumbents identified from
  the kit's member terms), money share (FEC; Campaign Finance Board), a race with no major-party opponent. Each term
  stays in the model only if the backtest shows it helps.
- *Ballot position*: about zero at race level (rotation, 2.3).
- *Error*: statewide mood (shared by every race of an office and partly across offices), regional shifts, a
  district-level error sized by the backtest (likely 3 to 5 points for legislative seats), and precinct noise (the
  2.5 to 4 point shifts in 1.1).

**Nonpartisan races** (judges, county, city, school, hospital, soil and water, township):

- What can separate candidates, on the record only: incumbency; the 2026 primary share where the race had a primary
  (needs John's August 11 files); the candidate's earlier vote share for this or a similar office; a party's published
  endorsement combined with how the place voted (`mn_endorsements.json`, place votes; never a guess at anyone's
  politics); alphabetical first place on township ballots; the number of names against the number of seats.
- Model: vote shares proportional to exp(β · features), fitted on 2022 and 2024 county, judicial and soil and water
  races (cities and schools once their files exist), with a race-level spread measured in the backtest.
- Where nothing on the record separates the candidates, the chances are equal and the page says so ("The record gives
  no reason to favour any candidate here"), rather than inventing precision.
- Several seats ("vote for 3"): each candidate's chance of finishing in the top three.
- One name per seat: shown as unopposed, no percentages. A race with no names: no forecast.
- Ranked-choice voting: if any 2026 race uses it, first choices only, said on the page.

**Population figures** (age, sex, marriage, children at home, education, income, poverty, owning or renting, moving,
citizens of voting age, race and ethnicity) enter as precinct features in three places: turnout, the expected pattern
of shifts (fitted on how 2014, 2018 and 2022 moved against the year before), and, on the night, the projection of
precincts not yet counted.

### 3.3 Election-night model

Run each time a new snapshot arrives (John's saved Minnesota files; other states' official feeds):

1. *Reported precincts* (complete in Minnesota, by 204C.19): for each, the turnout ratio (ballots against expected)
   and, per partisan office, the shift (log-odds of the DFL two-party share minus the forecast's).
2. *Explain the shifts* across reported precincts: shift = region term + population features + past swing + noise,
   weighted by votes and pulled toward the pre-election forecast while few precincts are in (a Bayesian update). This
   is the published approach of the Washington Post's live model: "comparing the current results to a historical
   baseline and regressing on the difference using demographic features", with quantile regression and conformal
   prediction for uncertainty (`https://github.com/washingtonpost/elex-live-model`, README read today; GitHub shows
   no licence, so the method is followed, no code copied).
3. *Project precincts not yet in*: turnout times (1 minus roll-off) for each race; shares from the forecast plus the
   predicted shift; plus, where each precinct's printed order is known, the first-listed edge for that precinct.
4. *Late absentee batch* per county: size from the county website; lean = the county's reported precincts plus an
   unknown offset (prior spread about 5 points), narrowed once the county adds the batch.
5. *Nonpartisan races*: the forecast is the starting point; each reported precinct moves it by how far the precinct
   departs from its expected share. Candidates' home bases make early precincts unrepresentative, so precincts are
   compared only with their own baselines (past runs, primary results) and intervals stay wide where there are none.
6. *Simulate* at least 1,000 times: shared statewide and regional errors, the unexplained precinct error (added
   analytically per race), turnout error and the late-batch offset. For states whose feeds report by ballot type
   (2.1), each type gets its own shift, because those states really do report in batches.

### 3.4 What a "% spread" means and how it is shown

For each candidate: the **chance of winning** (the share of simulated outcomes they win; for several seats, the
chance of a seat) and a **likely vote range** (the middle 80 percent of simulated vote shares; the middle 95 percent
on request), plus the likely margin between the top two. Example line: "62% chance; likely 50.5% to 54.0% of the vote."
Shown as whole percents, never 100 or 0 before the canvass ("over 99%"). With 1,000 runs a chance near 50 percent is
uncertain by about 1.6 points, so the page rounds and runs more draws when time allows.

### 3.5 Calibration and backtesting (2022 and 2024)

- *Pre-election*: rebuild the model as it would have stood before each election (2022 from 2012-2020 data; 2024 from
  2012-2022), forecast every contested race, and score: Brier score and log loss; calibration (of races given 70 to 80
  percent, how many did that candidate win); how often the 80 and 95 percent vote ranges held the result; average miss
  on vote share; all by race type. Compare with two plain rules ("the incumbent wins", "last time repeats") so the page
  can say what the model adds. Sample sizes are in 1.1; judicial and statewide races are few, so they are pooled.
- *Election night*: replay 2022 and 2024 with reporting orders, since the true orders are not on record: random;
  small and rural precincts first; whole counties at a time with the largest metro counties last; late absentee
  batches held back. At 10, 25, 50, 75 and 90 percent counted, score the same measures; widen the error terms until the
  80 percent ranges hold the result about 80 percent of the time in every order.
- *Untested races*: cities and schools until their files exist. Their pages say the forecast is untested.
- *After November 3*: the 2026 forecasts are scored against the canvass and kept for good as the track record.

### 3.6 Every run kept as a version

A new SQLite file (for example `election_model_2026.sqlite`), never the existing databases:

- `runs`: run id (time stamp in UTC and Central time plus a counter), kind (pre-election, live, backtest), method
  version (raised whenever a formula changes, as the lenses do), fingerprint of the model's code, random seed, draws,
  start and end times.
- `run_inputs`: for each input, its name, file or address, SHA-256 and "as of" time (each saved results file, the
  precinct tables, Census files, polls file, registration file, endorsements, candidate list).
- `race_runs`: run, race, status (before Election Day, counting, official), precincts in and total, ballots counted,
  expected total range.
- `candidate_runs`: run, race, candidate, chance of winning, median share, 80 and 95 percent ranges.

A race gets a new row only when its inputs or outputs changed. The seed comes from the run id, so any run can be
reproduced from its stored inputs. The site gets one small history file per race (`data/predict/<race>.json`: time,
method version, each candidate's chance and range, percent counted) for the trend line; a change of method version
starts a new marked segment. Size: one row per changed race per run; even every race on every 5-minute run through a
12-hour night (8,080 Minnesota candidacies, 144 runs) is about 1.2 million candidate rows, comfortable for SQLite.

### 3.7 How long a run takes on John's computer

Measured today with synthetic Minnesota-sized data in pure Python (the kit's environment has no numpy, pandas or
scipy, checked today): 4,103 precincts, 87 counties, 12 features, 4,721 races, 90,969 race-precinct pairs, 1,000 draws: regression 0.05 s, race sums 0.04 s,
simulation 7.1 s, **7.2 s in all** (Python 3.13, Intel 10th-generation processor, 20 threads, one thread used).
Reading a full set of saved files and writing page files should add seconds, so a run every 2 to 5 minutes leaves
ample room. The daily pre-election rebuild and the backtests take minutes (not yet measured). numpy would make it
faster but is not needed; adding it is John's decision.

### 3.8 What the page must say

- "Analysis, not a result." Every forecast figure carries that label; the official count and, later, the canvassed
  result sit apart and are the only results shown.
- What the numbers are: chances and ranges from a computer model built on past official results, Census estimates,
  polls by AAPOR Transparency Initiative members, campaign money on file and the votes counted so far.
- What it cannot know: how absentee voters voted until their county adds them, late events, write-ins, recounts.
- The inputs, the method version, the time of the run, the trend across runs, and the track record (3.5).
- On Election Day, wherever polls are open: "Polls are still open here. If you haven't voted, your vote still
  counts," with the polling-place link (John's choice, his veto).
- Never "projected winner", "called" or "will win"; no forecast for a race with one name per seat.
- No precinct-level comparison shown where a precinct has fewer than 20 votes in a race (the kit's `too_few` rule).

---

## 4. Other states, in brief

**For every state:**

- *Official results*: each state's election office; the kit's ballot loaders already read official 2026 primary votes
  for 42 states and know each office's results site (CLAUDE.md, "On The Ballot").
- *MEDSL precinct returns*, CC0: 2016, 2018, 2020, 2022 and 2024 repositories on GitHub (`MEDSL/2018-elections-official`,
  `2020-...`, `2022-...`, `2024-elections-official`; the 2024 one has a file for every state and DC, sizes below), plus
  `state-returns`, `county-returns`, `constituency-returns` and `primary-precinct-returns` (listed today, contents not
  checked). Vote types are kept where the state reports them (Oklahoma and South Carolina confirmed today).
- *VEST* precinct shapes joined to results, 2016-2024 (Harvard Dataverse and the University of Florida Election Lab;
  licence to check).
- *The kit's own place votes* (`ballot/lean/<code>_place_votes.json`): AR CO IA KY MI MN MO MT ND NE OH OK SD UT WI WY,
  2020-2024 top-of-ticket contests (Kentucky 2022-2024) summed to counties, cities and districts from official files.
- *Clerk of the House statistics* for 2020 and 2024 (in the kit); the FEC's "Federal Elections 2022" (2024 edition not
  yet published as of 2026-09-20, per CLAUDE.md).
- *Census*: the same national ACS files (already on disk for 10 tables), one block file per state, the national CVAP
  file.
- *Polls*: `polls_2026.json` (all 35 Senate races, 16 with member polls) and state-race poll files for 16 states.
- *Money*: FEC totals for every congressional candidate.

| State | 2026 federal races (November list loaded) | Official 2026 primary votes in kit | Kit place votes | MEDSL 2024 file |
| --- | --- | --- | --- | --- |
| AK | 2 (2) | yes | | 0.9 MB |
| AL | 8 (8) | yes | | 1.8 MB |
| AR | 5 (5) | yes | yes | 1.4 MB |
| AZ | 9 (0) | | | 9.5 MB |
| CA | 52 (52) | yes | | 14.0 MB |
| CO | 9 (9) | yes | yes | 1.9 MB |
| CT | 5 (5) | yes | | 1.2 MB |
| DE | 2 (2) | yes | | 0.3 MB |
| FL | 29 (29) | yes | | 3.4 MB |
| GA | 15 (0) | yes | | 0.7 MB (totals only) |
| HI | 2 (2) | yes | | 0.1 MB |
| IA | 5 (5) | yes | yes | 1.6 MB |
| ID | 3 (3) | yes | | 0.5 MB |
| IL | 18 (18) | yes | | 8.2 MB |
| IN | 9 (0) | yes | | 2.8 MB |
| KS | 5 (0) | yes | | 1.0 MB |
| KY | 7 (7) | yes | yes | 0.9 MB (totals only) |
| LA | 7 (1) | yes | | 0.4 MB |
| MA | 10 (0) | yes | | 0.6 MB |
| MD | 8 (8) | yes | | 3.9 MB |
| ME | 3 (3) | yes | | 0.5 MB |
| MI | 14 (14) | | yes | 2.5 MB |
| MN | 9 (9) | | yes | 2.1 MB (totals only) |
| MO | 8 (8) | | yes | 1.5 MB |
| MS | 5 (5) | yes | | 0.3 MB |
| MT | 3 (3) | yes | yes | 0.3 MB |
| NC | 15 (15) | yes | | 12.2 MB |
| ND | 1 (1) | yes | yes | 0.2 MB |
| NE | 4 (4) | yes | yes | 0.3 MB |
| NH | 3 (0) | | | 0.2 MB |
| NJ | 13 (13) | yes | | 4.2 MB |
| NM | 4 (4) | yes | | 1.0 MB |
| NV | 4 (0) | | | 0.6 MB |
| NY | 26 (26) | yes | | 6.3 MB |
| OH | 16 (14) | yes | yes | 16.5 MB |
| OK | 6 (6) | yes | yes | 2.2 MB (by vote type) |
| OR | 7 (7) | yes | | 0.9 MB |
| PA | 17 (17) | yes | | 1.7 MB |
| RI | 3 (0) | yes | | 0.7 MB |
| SC | 8 (8) | yes | | 2.3 MB (by vote type) |
| SD | 2 (2) | | yes | 0.2 MB |
| TN | 10 (0) | | | 0.3 MB |
| TX | 39 (39) | yes | | 3.9 MB |
| UT | 4 (4) | yes | yes | 2.9 MB |
| VA | 12 (12) | yes | | 0.6 MB |
| VT | 1 (1) | yes | | 0.4 MB |
| WA | 10 (10) | yes | | 2.7 MB |
| WI | 8 (8) | yes | yes | 1.0 MB (totals only) |
| WV | 3 (3) | yes | | 0.5 MB |
| WY | 2 (2) | yes | yes | 0.1 MB |

(Counts from `ballot_2026.sqlite`, read today. Statewide offices such as governor are in `ballot_local_2026.sqlite`,
level `statewide`.) The same method applies everywhere: precinct-level where precinct files exist, county-level where
a state's live feed reports by county; ballot-type batches modelled separately where a state reports them. Each
state's own rule on name order must be read before position is measured (Ohio rotates by precinct, R.C. 3505.03, per
CLAUDE.md).

---

## 5. Questions for John

1. May the model use MEDSL's public-domain copies of the Secretary's 2022 and 2024 precinct files for judges, county
   offices and soil and water, labelled as a secondary source? (Your own saves would replace them.)
2. Files only you can save from the Secretary's sites: the 2022 and 2024 general Media Files (cities, schools, hospital
   districts, townships, by precinct), the August 11, 2026 primary Media Files, the newest precinct registration
   counts and the May 1, 2026 precinct-split counts; on election night, the Media Files and the unprocessed-absentee
   counts.
3. Ballot order: write to the 87 county auditors for their rotation reports for 2024 and 2026, or rebuild the order
   from the May 1 counts and accept that it is an estimate?
4. Past election-night timing: may the Internet Archive's captures of the Secretary's results pages be checked, as
   with Ohio's workbooks?
5. About 330 MB of extra Census tables, the 56 MB CVAP file and the 253 MB Minnesota block file, downloaded once onto
   your computer: all right?
6. numpy in the kit's environment: not needed (7.2 s without it); yours to decide.

## 6. Requests made today

revisor.mn.gov 9 (statutes 203B.121 twice, 204D.13, 204D.14, 204D.08, 205.17, 206.61, 204C.19; rule 8220.0825);
www2.census.gov 13 (seven directory listings and six 6 KB range reads); enterprise.gisdata.mn.gov 10 (the 2024
precinct table in three pages and two statewide sums, made twice because the first run kept no copy);
gis.lcc.mn.gov 4 (one page, three HEAD checks); GitHub about 24 (directory listings, two READMEs, and small zip files
of 0.2 to 2.5 MB read in memory, Minnesota's twice per run); Harvard Dataverse 2; hennepincounty.gov 1. The
temporary copies made in the session scratchpad were deleted; nothing was saved in the kit. All with the kit's User-Agent, one at a time, two or more seconds apart. Nothing
requested from any Minnesota Secretary of State host.
