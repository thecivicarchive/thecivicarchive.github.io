# Changelog

Newest first. One entry per set of changes to the site.

Format: `## v4.0.001 — YYYY-MM-DD — short title`, then bullet lines. The site
reads this file at build time: the newest heading's version goes on the badge,
the footer and the page's meta tag, and the newest entries show in the corner
panel. Keep the bullets short and written for a reader, not for a developer.
Versions: the last three digits go up with every saved build, the middle number
when John signs off on a milestone. `Save this version.bat` commits and tags;
`Go back to a version.bat` restores any saved one.

## v4.0.036 — 2026-09-24 — Washington's campaign money

- Washington is the third state with its campaign money loaded, from the
  Public Disclosure Commission's open data on data.wa.gov (public domain):
  every gift to a House or Senate campaign since 2015 (479,008 rows), the
  Commission's register of legislative campaigns (1,373 campaigns by 1,305
  people, with a person number that ties one candidate's campaigns together)
  and independent expenditures and electioneering communications for or
  against candidates. All 147 sitting legislators are matched: $68.1 million
  from named organizations and $21.2 million of outside spending ($9.6
  million for sitting members, $11.6 million against), 2016 through 2026.
- Washington lets businesses, unions and other organizations give to a
  campaign directly, and the Commission's file carries the code each campaign
  reported a giver under. So the site's rule reaches three more kinds of
  organization, named as the campaign reported them: businesses, unions and
  other organizations, each with its own colour beside political committees,
  party and caucus committees. People stay totals. A gift filed as
  miscellaneous or anonymous is counted as other.
- Campaigns are matched by name and never guessed. The register writes a name
  three ways ("CAYLOR KENNETH E", "Clifford Mark Greene", "GREGORY CAROL J
  (CAROL GREGORY)"); each way is read, a match needs the family name, a
  compatible given name and a chamber the member has served in, must be the
  only fit, and the register's district settles a tie. Two representatives'
  Senate campaigns were accepted because exactly one sitting member carries
  the name; nothing was left ambiguous.
- A receipt a campaign dated in the future (one is dated 2031) is filed
  under the campaign's election year rather than inventing a segment for it.

## v4.0.035 — 2026-09-24 — Iowa's campaign money

- Iowa is the second state with its campaign money loaded, from the Iowa
  Ethics and Campaign Disclosure Board's own datasets on data.iowa.gov: every
  contribution received since 2003 (3.2 million rows, of which 513,564 went
  to House and Senate campaigns since 2015), the Board's register of
  committees, and independent spending for or against candidates. All 149
  sitting legislators are matched to their committees (160 of them, 952 on
  file): $62.1 million from named organizations, $2.2 million of outside
  spending, in the 2016 through 2026 cycles.
- The same rule as everywhere on the site. Organizations are named: political
  action committees, the state and county central committees of the parties,
  and other candidates' committees, each recognised by the number the Board
  assigned it. People are only ever totals. A giver the file names without a
  committee number (a bank paying interest, a business, an unitemized line)
  cannot be verified from the file, so it is counted as "other" and not
  named either. Outside spending is kept apart, its free-text descriptions
  never reach the page, and a member's own earlier committee (a council or
  county race before the legislature) is "moved in", not a donor.
- Committees are matched by name and never guessed: the Board's register
  names the candidate for a committee still open; a closed committee's name
  is read from its title ("Committee to Elect Zach Wahls", "Pellant for
  Iowa House", "Cheevers4House"). A match needs the family name, a compatible
  given name where one is written, and a chamber the member has served in,
  and must be the only fit; the register's district settles a tie; a
  sitting representative's registered committee for a Senate race is
  accepted when exactly one sitting member carries the name. The one title
  two members fit ("Johnson for State House") is left out and said so.
- Each state's money card now carries that state's own sentence about what
  its agency's file holds (Iowa lists gifts over $25; Minnesota over $200
  and no public subsidy), and Iowa's carries the Board's credit line and
  its Creative Commons Attribution-NonCommercial licence.

## v4.0.034 — 2026-09-24 — Who lives in each district

- The second districting lens is built, on every level at once: all 435
  congressional districts and every district of all 99 state chambers, 7,210
  districts in all. For each: the Census Bureau's 2020 count of residents
  (the number the lines were drawn on), how far its people per seat sit from
  the state's ideal, people per square mile, the urban share, and the
  Bureau's 2020-2024 American Community Survey estimates with their margins
  of error: median age, median household income, under 18, 65 and over,
  Hispanic or Latino and each race among those who are not, born outside the
  United States, below the poverty line, a bachelor's degree or higher,
  owner-occupied homes.
- The page is "People", beside "Shape" on the federal Districts page
  (`#people`, `#people/MN`, `#people=MN-5`) and on every state's own pages
  (`#people`, `#people=S-61`). The map shades by any figure; people per seat
  uses fixed steps either side of the ideal in a palette that is no party's.
  A district's panel gives every figure with its margin; the table sorts on
  any column; the whole table downloads with margins included.
- Everything comes from keyless files on census.gov, each fingerprinted:
  the Bureau's own population-by-district files for the 119th Congress and
  the 2024 legislative districts, and ten ACS tables. Derived margins use the
  Bureau's own formulas from its handbook; the program's self-test
  reproduces the handbook's worked examples before it reads anything, and
  refuses to run unless every column carries the label it expects.
- Four checks are written into the results and shown under "Sources and
  methods": the 2020 count by district equals the apportionment resident
  population in every state checked; the Bureau's three tabulations of the
  same blocks (Congress, Senate, House) agree in all 50 states; the survey's
  district populations add up to the Bureau's own state figure in all 50;
  and the under-18 share built from the age bands equals the Bureau's own
  table B09001 in every one of the 7,210 districts.
- Where districts elect different numbers of members (Maryland's House of
  Delegates, Vermont's Senate and House), people per seat divides by the
  seats the roster shows, and the page says so. New Hampshire's floterial
  House districts have no lines in the Bureau's file, so people per seat is
  not computed for that chamber, and the page says why. A state with one
  representative has no row in the congressional file; its district's
  figures are the state's own, from the legislative tabulation of the same
  blocks.
- What the figures cannot tell you is on every page: residents are not
  voters; the count is five years old and the survey a five-year average;
  every estimate has a margin; a spread inside the range courts accept is
  not a finding of fairness, nor outside it of wrongdoing; and states that
  drew on counts adjusted for where people in prison lived look less equal
  here than under the count they used. The widest congressional spreads in
  the Bureau's unadjusted count are in such states.

## v4.0.033 — 2026-09-23 — The last ring: all fifty states

- New York, New Jersey, Delaware, Maryland, Connecticut, Rhode Island,
  Massachusetts, Vermont, New Hampshire, Maine, South Carolina, Florida,
  California, Alaska and Hawaii are open, and with them every state. Fifty
  states, 7,336 legislators and 177 statewide officials, each with a page and
  a preview card, and every state with its Shapes page (6,775 legislative
  districts measured in 99 chambers). The District of Columbia, Puerto Rico
  and Guam are still to come; each needs a source of its own.
- Some states name their districts rather than number them. Massachusetts
  has "First Middlesex" and "Berkshire, Hampden, Franklin and Hampshire",
  Vermont "Chittenden Southeast" and "Addison-1", New Hampshire "Belknap 7".
  The Census Bureau's file codes them differently (D11, CHS, 007), so each
  roster name is matched to the Bureau's own name by spelling, a match has to
  be the only one, and the lines are filed under the names the state uses.
  Every one of Massachusetts's 200 and Vermont's 125 matched.
- Where districts elect different numbers of members, the pages read each
  district's count from the roster instead of assuming one number for the
  chamber: New Hampshire's House districts elect from one to ten
  representatives, Maryland's from one to three delegates, Vermont's Senate
  districts from one to three senators, its House one or two. "Who represents
  you" says so, and a vacancy is counted for the chamber as a whole rather
  than guessed for one district.
- New Hampshire's 39 floterial House districts, each laid over several of its
  neighbours, have no lines of their own in the Bureau's file. They are
  listed, not drawn: the map and the roster say so, their members have pages
  like everyone else's, and "who represents you" says you may have a
  representative it cannot find. Maine seats a representative of the
  Passamaquoddy Tribe and one of the Houlton Band of Maliseet Indians beside
  its 151 members; they are shown with the House and counted apart from its
  seats.
- A joint nomination is counted with the party named first and shown with the
  whole label, as the record writes it: New York's "Democratic/Working
  Families" and "Republican/Conservative/Independence", Vermont's
  "Democratic/Progressive".
- When a seat is next on the ballot, from the record: Florida's and
  California's even-numbered Senate districts vote in 2026 and their
  odd-numbered ones in 2028 (elected in 2022 and 2024); New Jersey's whole
  legislature in 2027, having voted in 2023 and 2025; South Carolina's Senate
  in 2028; New York, Maryland, Connecticut, Rhode Island, Massachusetts,
  Vermont, New Hampshire, Maine and Delaware's House in 2026. Delaware's,
  Alaska's and Hawaii's Senates follow no district-number rule, so nothing
  is claimed for those.
- Alaska's coastline, with its fjords and islands, is drawn at about 250
  metres rather than 80, or its district file would weigh 1.3 MB; every
  other state keeps the finer line.
- Portraits stay missing where a legislature's site has moved or refuses
  them: most of New Jersey's (the old picture addresses answer 404), some of
  Connecticut's House Republicans (the site answers with a web page), a
  third of Maine's. The page shows a party initial in their place.
- Vacant seats are shown as vacant, 27 across the fifteen states.

## v4.0.032 — 2026-09-23 — The fourth ring: fourteen more states

- Pennsylvania, West Virginia, Virginia, North Carolina, Georgia, Alabama,
  Mississippi, Louisiana, Texas, New Mexico, Arizona, Nevada, Oregon and
  Washington are open: every state that touches the twenty-one before them.
  Thirty-five states now, 4,902 legislators and 125 statewide officials,
  each with a page and a preview card, and every state with its Shapes page
  (4,717 legislative districts measured in 69 chambers).
- Each state is named its own way: West Virginia and Virginia have a House of
  Delegates and delegates, Nevada an Assembly. West Virginia elects two
  senators from each of its seventeen districts, and Arizona and Washington
  two representatives from each district, so "who represents you" there finds
  three legislators. An Oregon member nominated jointly as
  "Democratic/Working Families" is shown with that label, as the record has
  it, and counted with the Democrats.
- When a seat is next on the ballot, from the record: Pennsylvania's
  even-numbered Senate districts vote in 2026 (the roster shows the
  odd-numbered ones were elected in 2020 and 2024); Virginia, Mississippi and
  Louisiana vote in 2027, having elected both chambers in 2023 or 2025; New
  Mexico's Senate in 2028; Alabama, Georgia, North Carolina and Arizona in
  2026. Texas's Senate drew lots for its terms, West Virginia's paired seats
  alternate, and Oregon's, Washington's and Nevada's Senates follow no
  district-number rule, so nothing is claimed for those.
- Worked out from the lines: Arizona, Nevada, Oregon and Washington nest their
  lower-chamber districts inside their Senate districts; the other ten new
  states do not, and their pages say the districts overlap.
- The shoreline test kept finding only real water: Puget Sound (19 of
  Washington's 49 districts), Chesapeake Bay and the Atlantic in Virginia and
  North Carolina, the Gulf in Texas, Louisiana, Mississippi and Alabama, the
  Georgia and Oregon coasts, and Lake Erie in Pennsylvania. Inland chambers
  agree with the Census Bureau's own areas to within 1 percent in every
  district.
- Louisiana's roster points at picture addresses its legislature has since
  moved, so most Louisiana members show a party initial until the roster is
  updated.
- Vacant seats are shown as vacant, twelve across the fourteen states.

## v4.0.031 — 2026-09-23 — Every district's shape, state by state and in the legislatures

- The federal Districts page now compares Congress state by state: a "State
  by state" table with each state's median on all three measures and its
  lowest and highest district, alphabetical unless you sort it; and, when a
  state is picked, its districts listed side by side in number order, each
  with its member and its score, so a state's map can be read in one glance.
  Every state has an address of its own (for example #shapes/MN).
- The same lens on the legislatures: every one of the 21 open states has a
  Shapes page measuring all of its Senate and House districts (2,739 districts
  in 41 chambers) from the Census Bureau's files for those chambers, with the
  same map, table, download and "Sources and methods" as the federal page.
  The two levels point at each other: a state on the federal page links to
  its legislature, and a legislature's page links back to the state's
  congressional districts.
- The checks held at the state level without a hand on the scale: in every
  inland chamber our areas agree with the Bureau's own to within 1 percent in
  every district, and the only districts marked "shoreline" are the ones on
  the Great Lakes (Michigan, Ohio, Illinois, Indiana, Wisconsin, Minnesota).
- What the measures show, for the reader to weigh: state legislative
  districts are on the whole more compact than congressional ones (a median
  Polsby-Popper of 0.35 across all their districts against 0.25 for Congress), and
  the spread between chambers is wide, from about 0.22 in the Illinois,
  Tennessee and Kentucky Senates to 0.48 in the Kansas House.
- The words the two levels share (the three formulas, how area and perimeter
  are measured, the self-test, what a score cannot tell you) are written once
  and used on both, so they cannot drift apart.

## v4.0.030 — 2026-09-20 — The shape of every district

- A new federal page, "Districts": all 435 congressional districts measured
  the same way for how compact their shapes are, on three published measures
  (Polsby-Popper, Reock, convex hull), shown on a national map, state by
  state, and in a table you can sort and download. It is the first of four
  planned ways to look at the district maps; who lives in each district, how
  votes became seats, and which counties each map keeps whole come next, and
  rule-drawn what-if maps after those.
- The page measures and never concludes. A score describes a shape, not why
  it has that shape, and the page says so wherever a score appears. The table
  is in order of state and number, not ranked.
- Shoreline districts are marked, by an objective test, and can be set aside:
  a jagged coast lowers a score through no one's choice, and the least compact
  districts by the commonest measure turn out to be Louisiana's coast, the
  Outer Banks, Cape Cod and Michigan's Upper Peninsula. The six at-large
  districts are whole states, drawn by no one, and are left out of every
  comparison.
- "Sources and methods" opens beside it: the Census Bureau file and its
  fingerprint, each formula with its citation, how area and perimeter are
  measured without choosing a map projection, the self-test the program must
  pass first (shapes whose answers are known, to the fourth decimal), the
  control against the Bureau's own areas (308 of 435 within 1 percent; the
  rest are coastal, as expected), and what a score cannot tell you.
- The top bar's "How ratings work" is now "Ratings", as the phone tab bar
  already called it, so seven items fit on one line.

## v4.0.029 — 2026-09-20 — The third ring: ten more states

- Indiana, Ohio, Kentucky, Tennessee, Arkansas, Oklahoma, Kansas, Colorado,
  Utah and Idaho are open: twenty-one states now, 2,840 legislators, each with
  a page and a preview card, and each state with its statewide offices.
- Idaho elects two representatives from every district, by seat. The record
  files them as 1A and 1B, but both answer to the whole of district 1, so the
  pages show "District 1, Seat A" and find you three legislators, as in the
  Dakotas.
- Statewide offices are whatever the public roster carries for that state:
  Arkansas's list includes its Auditor and Treasurer, Tennessee's has two
  offices, Utah's three. The page says so rather than promising a fixed four.
- When a seat is next on the ballot, checked before being shown: Ohio's and
  Tennessee's odd-numbered Senate districts and Kentucky's and Oklahoma's
  even-numbered ones vote in 2026; all of Kansas's Senate votes in 2028; all
  of Idaho's legislature in 2026. Indiana's, Arkansas's, Colorado's and Utah's
  Senates rotate by a list of districts, so nothing is claimed for them.
- Worked out from the lines: Ohio and Idaho nest their House districts inside
  Senate districts; Indiana, Kentucky, Tennessee, Arkansas, Oklahoma, Kansas,
  Colorado and Utah do not, and their pages say the districts overlap.
- Parties are shown as the record has them, including Utah's one senator from
  the Forward Party.

## v4.0.028 — 2026-09-20 — The second ring: six more states

- Michigan, Illinois, Missouri, Nebraska, Wyoming and Montana are open, every
  state that touches the five before them. Eleven states now, 1,535
  legislators in all, each with a page and a preview card, and each state with
  its statewide offices.
- Nebraska has one chamber, elected without party labels. Its page says "The
  chamber", calls its districts legislative districts, lists every member as
  nonpartisan, and says why.
- Which House districts sit inside which Senate district is still worked out
  from the lines themselves. That showed that Michigan, Missouri and Wyoming
  draw their two chambers' districts separately, so their pages say the
  districts overlap rather than nest; Illinois and Montana do nest.
- When a seat is next on the ballot, checked before being shown: all of
  Michigan's Senate in 2026; Missouri's even-numbered and Nebraska's
  even-numbered districts in 2026; Wyoming's odd-numbered in 2026. Illinois's
  and Montana's Senates follow no odd-and-even rule, so nothing is claimed.
- Portraits: two legislatures' picture servers leave a link out of their
  security certificate's chain, which browsers quietly repair. The downloader
  now repairs it the same way, without loosening the check, and Illinois went
  from 3 portraits to 178. Where a roster address is dead or a site refuses
  automated requests, a party initial still stands in.
- Vacant seats are shown as vacant: one Senate and five House seats in
  Missouri, one Senate seat in Iowa, one House seat in Minnesota.

## v4.0.027 — 2026-09-20 — Four neighbours, and the statewide offices

- Wisconsin, North Dakota, South Dakota and Iowa are open, each with the same
  pages as Minnesota: who represents you, the district map for both chambers,
  every legislator's page, and a preview card for every link. 527 more
  legislators and 449 more districts in all. The front door's map shows five
  states open.
- Each state is named the way it names itself: Wisconsin's lower chamber is
  the Assembly, and North Dakota's Democrats are the Democratic-NPL.
- In the Dakotas most House districts elect two representatives, so "who
  represents you" there finds three legislators, not two. A district whose two
  members come from different parties is drawn half and half on the map.
- Which House districts sit inside which Senate district is worked out from
  the district lines themselves, state by state, rather than assumed.
- New on every state: the statewide offices the public roster carries, which
  are the Governor, Lieutenant Governor, Attorney General and Secretary of
  State. Each has a page with the office, the term, when it is next on the
  ballot, contact details and a preview card; search finds them too. Other
  statewide offices, such as an auditor or a treasurer, are not in the roster
  yet, and the page says so.
- When a seat is next on the ballot is shown only where it was checked: in
  Wisconsin, North Dakota and Iowa odd-numbered Senate districts vote in 2026
  and even-numbered in 2028.
- Campaign money for the four new states is marked as coming. Every state
  keeps its own records in its own form, so money is added one state at a time.
- On the federal side, a reader who picks any of the five states is offered a
  link through to that state's own legislature.

## v4.0.026 — 2026-09-20 — Minnesota, ready to share

- A link to a Minnesota legislator now shows a proper preview when it is
  pasted into a message or a post: their portrait, seat and committees, the
  campaign money on file, and where their district sits in the state (ringed
  when it is only a few blocks wide). A link to the Minnesota front page shows
  the state with its Senate districts colored by party.
- New share buttons: "Share, so friends can find theirs" under your two
  legislators, and "Share" on any district on the map.
- The Minnesota front page now draws the state beside the welcome, Senate
  districts colored by party; tap it to open the map.
- The district map shows each district's number once the district is large
  enough on screen to hold it, so the rural numbers show at once and the
  cities' appear as you zoom in.
- One space, not two: on the federal side, a reader who picks Minnesota under
  "How did your members vote?" gets a link through to Minnesota's own
  legislature; a legislator's page has a way back to the full list.
- Small fixes: link-buttons are no longer underlined (both sides), and the
  location circle on the big Minnesota map is drawn in gold as on the small one.

## v4.0.025 — 2026-09-20 — Minnesota opens

- Minnesota now has pages of its own, one step inside the front door under
  "mn", in the same look as the federal side. On the front door's map
  Minnesota is marked "Open, still filling in".
- Who represents you: tap "Use my location", or pick your Senate or House
  district, and your state senator and representative appear with a small map
  of your district. Your location is worked out on your device, kept only
  there rounded to about half a mile, and "Forget my location" clears it on
  the federal pages too.
- A map of all 67 Senate and 134 House districts, colored by the party of the
  member who holds each one. Switch chambers, zoom to the Twin Cities where
  districts are a few blocks wide, drag the map when zoomed in, tap a district
  for its member. The one vacant House seat (21A) is shown as vacant.
- Every one of the 200 legislators has a page: how long they have served, the
  committees they sit on, the organizations that fund their campaigns, and one
  fenced paragraph from Wikipedia. The Democratic-Farmer-Labor Party is called
  the DFL, as Minnesota calls it.
- Campaign money, from the Campaign Finance Board's public files, is grouped
  in two-year segments the way the Board files it, 2015-16 through 2025-26.
  Organizations are named and link to their page at the Board; people,
  lobbyists included, are only ever totals; outside spending is kept apart.
  Money a member moved from an earlier committee of their own (a House account
  passed to a Senate one) is shown as "moved in", not as a donor.
- Said plainly where the record is thin: the roster does not record when 43
  long-serving members began, so their pages say "before 2023" rather than
  guess a year. The Board's file lists only givers of more than $200 a year,
  so its totals are lower than everything a campaign took in, and the page
  says so.
- Still to come for Minnesota: bills and recorded votes, then a statewide
  Money page.

## v4.0.024 — 2026-09-20 — The front door opens

- Fixed: pressing a card on the front door did nothing. A press now opens the
  card in front, and a press on a card at the side brings it round first.
- The ring turns much more slowly and eases to a stop, and it waits twice as
  long before moving on by itself.
- When a card arrives at the front and stops, a sweep of light crosses it and
  a few stars twinkle at its corners; while it rests there, a slow gold shimmer
  runs round its edge. With Motion off, none of that plays.

## v4.0.023 — 2026-09-20 — One front door

- The Civic Archive now has a front door: a page that welcomes everyone and
  leads to each level of government. The cards ride a ring in 3D, forwards and
  backwards in a loop: Federal, State, and a place held for county and city.
  Drag them, use the arrow keys or the arrows, or tap one.
- Choosing a card turns the page like a book, three seconds, and opens that
  space. Click, or press any key, to skip the turn. With Motion off nothing
  spins and there is no page-turn.
- The State card opens a map of the country. States that are open are filled,
  states being built are hatched and say what is loaded so far (Minnesota: its
  200 legislators, 201 districts and campaign money), and your own state is
  outlined in gold if you have picked one.
- The federal side now lives one step inside, under "us", with an "All levels"
  link in its top bar that leads back to the front door.

## v4.0.022 — 2026-09-20 — Groundwork for the states: Minnesota

- Nothing new to see on the site yet. This build lays the ground for bringing
  the same record to every state legislature, beginning with Minnesota.
- Loaded for Minnesota so far: all 200 sitting legislators (67 senators, 133
  representatives and one vacant House seat) with their service, committees
  and portraits; the lines of all 67 Senate and 134 House districts; and
  campaign money from the state's Campaign Finance Board, 2016 through 2026,
  matched to every sitting member.
- The same rule as the federal pages: organizations that gave are named,
  people who gave are counted in totals and never named, and spending by
  outside groups is kept apart from donations.
- Still to come before Minnesota opens: its bills and recorded votes, then the
  Minnesota pages themselves, then a shared front door for the federal and
  state sides.

## v4.0.021 — 2026-09-20 — Follow the money

- A new page, "Money". Its first tab is one list of every organization among
  any member's top donors and the members it gave to, 2016 through 2026: the
  cycle, the election the money was given toward, the amount, the number of
  payments and the first and latest dates. Search it; narrow it by cycle,
  chamber, party, state, kind of organization or election; sort by any column
  and hold Shift to sort within a sort; "only" beside a name narrows the list
  to that one organization or member. "Download these rows" saves what you see.
- The second tab is "Four ways to see it":
  - Ten coins. If a campaign's money were ten coins, where did they come from?
    For all of Congress, a party, a chamber, or one member.
  - Top givers. The fifteen organizations that gave the most, each bar split
    between the parties. Click one to see everyone it gave to.
  - Large print. The main numbers in big type with nothing to hover over, and
    a button that prints it cleanly.
  - The donor map. Every member placed by the donors they share, with a second
    view of money beside the party line, a way to find a member, and a way to
    light up one organization's money across Congress. It says how it is made.
- New everywhere money appears: "passed along". A few committees (AIPAC's
  PAC, WinRed, Club for Growth's PAC and others) collect gifts that individual
  people earmark for a candidate and hand them on, which is how a PAC limited
  to $5,000 per election can show $300,000 to one candidate. The total still
  reads as the filing reads, and the part that was people's gifts is now shown
  beside it, on member cards, in the tables and their payments, and in Top
  givers, where a switch counts each committee's own money only. The rule:
  every line the filing marks as an earmark, plus anything over $5,000 that a
  committee other than a party or a candidate sent one candidate for one
  election.
- Still organizations only; people who gave are never named.
- Fixed, in the record itself: two war-powers resolutions (S.J.Res. 98 and
  S.J.Res. 124) were shown as "Passed Senate". They did not pass. The recorded
  vote was on a point of order against each of them, and the point of order
  carried; the site had read "agreed to in Senate" at the end of that line as
  passage. Votes on points of order and on budget waivers (seven in all) now
  carry their own labels, and the two resolutions show where they really stand.

## v4.0.020 — 2026-09-20 — Who funds the campaign

- Every member's "Get to know" now has "Who funds the campaign": the ten
  organizations that gave the most, with a bar showing how much of the
  campaign's money came from people, from organizations, from the party and
  from the candidate's own pocket. Pick a cycle, 2016 through 2026, and it
  says what office the money was raised for and what seat they held then.
- Every member's page now has "Money: who gave, and who spent": the top
  hundred organizations in a table you can sort by any column (hold Shift and
  click to sort within a sort), each row opening to every payment with its
  date and the election it was given toward.
- Above the table, a picture of the same money: blocks sized by what each
  organization gave, coloured by kind. Point at a block and the table lights
  up; click it and its payments open. A switch puts the picture above the
  table or beside it.
- Outside spending has its own section, apart from donations: what super PACs
  and other groups spent on their own to support or oppose the member. The
  campaign never received that money, and the page says so.
- Donors here are organizations only: PACs, party committees, other
  candidates' committees. People who gave are counted in the totals and never
  named. Everything comes from the Federal Election Commission's public files
  (a new "donors" stage downloads them, about 170 MB).

## v4.0.019 — 2026-09-20 — Your state, drawn, with you on it

- Under "How did your members vote?" your state now appears as a map of its
  congressional districts, coloured by how each member voted: solid for yes,
  striped for no, gray for not voting. Tap a district for its representative.
  On a Senate vote the state is split between its two senators.
- Pick any of the roll calls listed and the map recolours to that vote ("Show
  on the map"). On a wide screen the map stays beside the list as you scroll.
- If you use "Use my location", your district is outlined in gold and a pin
  marks where your device says you are, with a 3-mile circle (wider if your
  device could only place you roughly). The spot is worked out on your device
  and kept only there, rounded to about half a mile, so the pin is back on
  your next visit. "Forget my location" removes it; so does choosing another
  state.

## v4.0.018 — 2026-09-20 — Decided by a handful

- New on the front page: "Decided by a handful", the recorded votes of this
  Congress that came down to the fewest votes, ties included. Each one opens
  to show how every member voted, and links to the bill.
- New on the Members page: "With their party, and against it". Every sitting
  member, with how many party-split votes they cast, how often they sided with
  their party, how many times they broke with it, and how often they did not
  vote. Click any column to sort; hold Shift and click another to sort within
  it (on a phone, turn on "Sort by several columns").
- Breaks with the party are now a way in. Tap the count, on the table or on a
  member's card, and you land on that member's page already narrowed to those
  votes. Each vote opens to show how everyone else voted, and each now links
  to the bill itself.

## v4.0.017 — 2026-09-20 — Your own seats on the chamber floor

- On the chamber floor, the seats of your state's members are ringed in gold,
  and the line under the floor says how they voted. Pick your state under "How
  did your members vote?" and it carries over.
- If you used "Use my location", your own representative is picked out the
  moment the floor opens, with how they voted.
- The site now remembers your district on this device, next to your state, so
  your representative is marked again on your next visit. It stays on your
  device; nothing is sent anywhere. Choosing a different state clears it.
- The front page scrolls more smoothly: the scroll effect now touches only the
  two things that move.

## v4.0.016 — 2026-09-20 — The front page moves

- The headline is bigger and stacked, and its second line turns over a few
  times to name what is here (in plain words, bill by bill, vote by vote, seat
  by seat) before coming to rest.
- The Capitol behind the words now takes its colours from the page. On the dark
  page it is a lit dome under a night sky with stars; on the light page, the
  daytime print as before. On a wide screen it stands at the right edge where
  you can see it, clear of the words.
- The scene has depth: the sky, the clouds and the building move at different
  speeds as you scroll, and shift a little with the pointer. The featured
  bill's card leans a degree or two toward the pointer.
- New under the headline: a moving line of the latest recorded votes. Each one
  opens that vote on the map. Hover to pause it.
- With Motion off, all of this holds still and the line of votes becomes a row
  you scroll yourself.

## v4.0.015 — 2026-09-20 — The chamber floor, in 3D

- Any recorded vote can now be seen a second way: the chamber floor. Every
  member who took part has a seat, Democrats to the left and Republicans to
  the right, lit by how they voted: bright for yes, hollow for no, gray for
  not voting. Drag to look around, tap a seat for the member, and flip to
  the next vote to watch the floor light up again.
- The seating is a diagram, not a seating chart; the House has no assigned
  seats. With Motion off, the floor holds still.
- On a phone the whole chamber fits the screen, and a tap finds the seat
  nearest your finger.
- Fixed: on a phone the buttons at the top of the page ran a few pixels off the
  right edge, which let the page slide sideways. They fit now, down to the
  smallest screens.

## v4.0.014 — 2026-09-20 — A page for every member

- Every senator and representative now has a page of their own. It opens with
  "Get to know", then lists every recorded vote they took part in, newest
  first, which you can narrow to the votes where they broke with their party
  or did not vote. Each line opens that vote on the map.
- A member's page can be shared, and the link shows a proper preview: their
  name and portrait, their seat, and how often they side with their party
  when the parties split.
- You reach a member's page from "Full profile" on their card, from the Your
  members list, and from search.

## v4.0.013 — 2026-09-20 — Get to know your members

- Every member's card now opens with "Get to know": how long they have held
  the seat and what they did in Congress before it, their committees and
  titles, how often they side with their party when the parties split (with
  the most recent times they did not, each one a tap away), how many votes
  they missed, and the subjects of the bills they sponsor. Every number is
  counted from the record by a rule printed beside it. Nothing describes
  anyone's character or beliefs.
- Life before Congress comes from the opening of each member's Wikipedia
  article, boxed and labelled as not an official record, with a link.
- Website, phone, contact form, Congress.gov and official social accounts
  now sit at the top of the card, each with a symbol for what it is.
- "Use my location" and your own representative now carry a slow shimmer,
  and your representative comes first, a little larger. With Motion off the
  shimmer holds still.

## v4.0.012 — 2026-09-20 — The names people actually use

- Eleven bills now carry the name in common use, each with a link showing
  where that name is used. Most read "commonly called ..." beneath the
  official name: the Russia sanctions bill, the housing bill, the stablecoin
  law, the NDAA, the rescissions package. Two whose official titles run to a
  full sentence lead with the plain description instead, with the official
  title beneath: the funding bill that ended the 2025 government shutdown,
  and the bill that ended the 2026 Homeland Security shutdown.
- These names are kept by hand and approved one by one. They are never part
  of the official record, and each bill says so.

## v4.0.011 — 2026-09-20 — Bills that became something else

- Two bills were rewritten wholesale by the other chamber and no longer match
  their original names. S. 1383 began as the Veterans Accessibility Advisory
  Committee Act and now carries the SAVE America Act; S. 1318 began as the
  Fallen Servicemembers Religious Heritage Restoration Act and now carries the
  Foreign Intelligence Accountability Act. Both lead with what they became,
  say what they began as, and note that earlier votes were on the original
  bill. All of it comes from the Library of Congress record.

## v4.0.010 — 2026-09-20 — Bills lead with the name people know

- A bill now leads with the name the record itself gives it when that is the
  name people know. H.R. 1 reads "One Big Beautiful Bill Act", its popular
  title in the Library of Congress record, with the formal title one tap away;
  bills whose only title was a formal one lead with the short title they
  carried earlier. The same name shows on the Start here lists, the vote map,
  search, and the preview when a link is shared.
- Names in common use that are not in the record can now appear as "commonly
  called ...", each with a link showing the name in use. None appear until
  they have been approved one by one.

## v4.0.009 — 2026-09-20 — Each bill gets its own vote map

- Inside a bill, "Votes and path" now has a map of that bill's recorded votes
  only. Flip from the House vote to the Senate vote with the arrows or the
  list, tap a state for its members' names, and share any one of them.
- "See the map" beside a vote now shows it right there in the bill.
- "Open on the full map" opens the big map narrowed to the same bill, for
  district lines and member cards; one tap shows every vote again.

## v4.0.008 — 2026-09-20 — Where every bill stands

- Every bill now carries a moving track of its journey: introduced, committee,
  the chamber it started in, the other chamber, the President, law. The marker
  travels to where the bill stands and keeps a slow pulse while it is still
  alive. A bill that failed stops at a red marker that says why; one nothing
  has happened to for six months is shown dimmed.
- Inside a bill, "Votes and path" opens with the full track and the date each
  stop was reached, and lists the votes newest first.
- Constitutional amendments end at "To the states" rather than the President.

## v4.0.007 — 2026-09-20 — Five tabs on a phone

- On a phone, five tabs along the bottom now reach every page: Home, Bills,
  Votes, Members and Ratings. Before, two of those pages could not be reached
  from a phone at all.
- The top bar now fits on a tablet.
- "Use my location" says when its district guess sits near a line.

## v4.0.006 — 2026-09-20 — How did your members vote?

- A new panel on the opening screen: pick your state, or let the site find it,
  and see how your senators and representatives voted on the latest roll
  calls, member by member. Tap a member for their card on the map, or share
  the vote in one tap.
- "Use my location" asks the browser for your position, then works out your
  district on your own phone or computer, from the same district lines the
  map draws. Your location never leaves it.

## v4.0.005 — 2026-09-20 — Dark by default

- The site now opens in its dark look. The sun-and-moon button in the top bar
  still switches, and your choice is remembered.
- A bigger opening headline.

## v4.0.004 — 2026-09-20 — Add it to your home screen

- The site can be added to a phone's home screen like an app, and the pages
  you have already opened stay readable without a connection.
- Visits can be counted without cookies or personal data, once the counter's
  address is set up. Until then nothing is counted at all.

## v4.0.003 — 2026-09-20 — Share a bill, a vote, or how your member voted

- Every bill card, every roll call on the map and every member's card now has
  a Share button. On a phone it opens the usual share sheet; on a computer it
  offers a copied link, X, Bluesky, Threads, Facebook or email.
- A shared link now shows a proper preview: the bill's title and status, or
  the vote map coloured the way the site colours it, drawn in the site's own
  type.
- The address bar follows the vote you are looking at, so any vote can be
  linked to directly.

## v4.0.002 — 2026-09-20 — A site that opens fast

- The page you open is now under a fiftieth of its former size. The bill
  list, the roll calls, the district lines and the portraits arrive only when
  you open the page that needs them, so the site starts at once on a phone.
- Each bill's full record loads the moment you open it.
- The whole site is still available as one file, for reading without a
  connection: "Download the offline copy", in the footer.
- Picking a member of Congress now takes you to their bills.

## v4.0.001 — 2026-09-20 — Version numbers, and four fixes

- Every build now carries a version number, shown on the corner badge and in
  the footer. Each saved build can be brought back exactly as it was.
- "How to read this site" can be closed again; it had been stuck open.
- The opening screen no longer hides its own words behind a pale haze.
- Tapping a bill under "Start here", in the hero panel or in search now opens
  that bill. The address bar shows a link you can share, and Back returns you.
- The vote picker and the sort menu are readable again in dark mode.

## 2026-09-19 — The Civic Archive

- Renamed from Plain Congress to The Civic Archive.
- The site is now five pages rather than one long scroll. Home is a welcome
  screen; Bills, Vote map, How ratings work and Your members each have their
  own page.
- Where this Congress stands now reads as a single column down the left.
- "How to read this site" moved into a help button in the top bar; it opens
  over a blurred page so it is hard to miss.
- New opening picture: the Capitol drawn as a print, under the sky and the
  weather outside right now.

## 2026-09-19 — A welcome screen

- New opening screen explaining what this site is for and who it is for.
- "Start here": five bills moving right now, five already law, chosen by a
  stated rule rather than by popularity.
- A scoreboard of where every bill in this Congress currently stands.
- Every claim on the site is now labelled Fact, Analysis or Opinion, with a
  short guide to what each one means.
- This changelog, so changes between versions are easy to follow.

## 2026-09-18 — First public build

- Catalogued all 16,364 bills and joint resolutions of the 119th Congress.
- Loaded all 608 recorded floor votes, member by member.
- Added the state-by-state vote map and member portraits.
- Published the site.
