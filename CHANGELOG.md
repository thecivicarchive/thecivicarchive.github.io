# Changelog

Newest first. One entry per set of changes to the site.

Format: `## v4.0.001 — YYYY-MM-DD — short title`, then bullet lines. The site
reads this file at build time: the newest heading's version goes on the badge,
the footer and the page's meta tag, and the newest entries show in the corner
panel. Keep the bullets short and written for a reader, not for a developer.
Versions: the last three digits go up with every saved build, the middle number
when John signs off on a milestone. `Save this version.bat` commits and tags;
`Go back to a version.bat` restores any saved one.

## v4.0.109 — 2026-10-10 — Election Night: the feed, the forecasts page and forecasts for the other states

- The feed is a new Election Night page about news coverage of the races. Each headline names its outlet and links to the story. Posts appear only from newsrooms, election offices and candidates' official accounts, and only once the site has its own contact address; everyone else is counted, never shown. A leaderboard ranks the races by coverage per 100,000 residents, the attention gap (coverage against how close a race is), momentum (the last hour against the hour before) and source breadth (how many outlets). It fills in once the night's updater is running.
- The forecasts page gives each race's chances, a likely range of the vote, the trend across every run of the model, its inputs and three blind spots in plain words, with the track record and the method. Forecasts are not public yet: until they are, the page shows only how they are made and how the method did on past elections.
- On election night Minnesota's forecasts are run again as each county reports. The other states' Congress, governor and statewide forecasts cover 40 states so far, tested on the 2022 and 2024 elections; seats on lines redrawn for 2026 have no forecast, and each page says why.
- Results pages: Michigan is read in part (Oakland County's own figures, labelled as one county's); each state's own word for its places (parish, borough, locality, town, ward); primaries replayed for practice show as their own contests.

## v4.0.108 — 2026-10-10 — Election Night: every state's results readers, the US map, live updates and Minnesota's first forecasts

- Election Night can now read the official results of 26 states and the District of Columbia straight from each state's own results system, each tested by replaying a past election and checked against its certified totals. The other states link to their own results pages.
- A results page updates itself while it is open: new figures appear in place, a table never re-sorts under your hands, and the page says plainly when updates are paused.
- Minnesota's races have their first forecasts: a chance and a likely vote range for every contested race, labelled Analysis, tested against the 2022 and 2024 elections, with ballot position, roll-off and the order in which counties count built in.

## v4.0.107 — 2026-10-10 — Election Night: the door and the first pages

- A third space opens beside On The Ballot and Legislation & Legislatures: Election Night, for results only. Its door is on the home page and in the top bar ("Follow the count, race by race."), and on phones it is the "Results" tab.
- Its home page lists when the polls close in every state, in your own time zone, and sends you to your state's own polling-place lookup.
- Minnesota's results page is built, with every contest on the November ballot, from Congress down to school boards, on one map shaded by who is ahead, and your own ballot's results when you use your location. Until Election Day it shows a practice run of 2024's official figures, labelled as practice.
- The figures come only from official sources. Where a state's results site does not allow programs, the page links to the state's own results instead.

## v4.0.106 — 2026-10-10 — Search and filter a member's votes and bills

- A member's "Every recorded vote" sheet keeps its three quick choices (All, Broke with party, Did not vote) and gains a search box and four fold-out groups of checkboxes, each choice with a live count: how they voted (yes, no, not voting, present; with or against most of their party; votes both parties backed, party-line votes, close votes), what the vote was about (the Bills page's four groups and 22 topics, and whether the bill became law, is still moving or failed), the kind of vote and its outcome (final passage, amendments, procedural motions, cloture, settling the other chamber's changes; passed or failed), and when (the last 30 or 90 days, this year, or dates you choose).
- Choices in use show as chips you can remove one at a time or all at once. A line above the list counts what matches and how the votes split. Sort by newest, oldest, closest or widest margin, or topic, and download what you see as a spreadsheet, with the official roll-call address on every row.
- Every filtered view has its own address, so a list such as "every no vote on health bills" can be bookmarked or sent, and the Back button undoes one change at a time.
- "What NAME works on" now lists the member's own bills, sponsored and cosponsored, with the same search, topic and status filters, sorting, count and download.

## v4.0.105 — 2026-10-09 — A member's page as a filing rack

- Every member's page, in Congress and in all fifty statehouses, now opens on "Get to know" alone: the portrait, the seat, the links, and the In office card. Everything else waits in a rack of folders down the left side: Committees, How they vote, What they work on, Who funds the campaign, Every recorded vote, and From Wikipedia. Each folder shows only when there is something in it.
- Choosing a folder files the open sheet back into the rack and draws the next one out, over five seconds. A click, a tap or any key finishes it at once. "Sheet speed" on the rack sets Full (5 seconds), Quick (1 second) or Instant, and the same setting is on the Access page; with Motion off, or when your device asks for less motion, sheets change at once.
- Each folder carries a small object drawn in 3D on your own device, in brass, verdigris and parchment: a nameplate, a clipped sheaf of papers, a gauge, an inkwell and quill, a stack of coins, a ballot box and an open book. They turn a little toward your pointer. Where 3D is not available, plain icons stand in.
- The rack works with the keyboard (arrow keys, Home, End, Enter), with screen readers, and on phones, where it becomes a row of folders under the top bar. Every folder has its own address, so a link can open it directly, and the Back button steps back through the folders you opened.

## v4.0.104 — 2026-10-07 — Every shared card in the new look

- The cards a shared link shows for a single bill, a single recorded vote, a member of Congress, a state legislator, each state legislature and each race on the ballot are now drawn in the same look as the rest: parchment, the emblem beside the site's name, a brass rule at the head and a verdigris band at the foot. Vote bars and maps keep red and blue for the parties, in the colours the light pages use.

## v4.0.103 — 2026-10-07 — One emblem for the tab, the bookmark and every shared link

- The Civic Archive has an emblem: a civic hall whose columns are books standing on a plinth, under a brass pediment with a seal. The civic building that is also an archive. Its colours are the site's own: verdigris, the patina of civic bronze; brass, the plaque and the label on a spine; and parchment.
- It is now the icon in the browser tab and on the bookmark bar on every page, drawn for each size it is shown at, and the icon a phone shows when the site is added to the home screen.
- Every page now has a share image in the same look: the emblem on parchment beside the page's own words. The home, Method and Access pages, the ring of cards, the cabin, On The Ballot's door, the Congress ballot page, the states' chooser and each state's own ballot page each have theirs; Plain Congress's card is redrawn to match. A pasted link to any of them shows the card.

## v4.0.102 — 2026-10-05 — Browse bills by topic, by how the vote went, and by what is new

- Topic: four groups and 22 topics (Money & Work, People & Communities, Safety & the World, Land, Energy & Government), each built from the one subject the Library of Congress gives every bill. Pick a group, then a topic; each shows how many bills it holds. New bills the Library has not labelled yet have their own button. Every card now names its topic.
- Votes: slide to how much of a chamber voted yes on the final vote to pass the bill, from any share to 50, 60, 70, 80, 90 or 95 percent or more, or every vote (100 percent). Pick the House, the Senate or either. Or find votes where both parties' majorities voted yes, party-line votes (most Democrats one way, most Republicans the other), close votes (10 points or less), and bills passed by voice vote or unanimous consent, where no one's vote is recorded. Every card with a final vote now shows it: the yes and no totals, the share, and each party's count.
- What's new: bills newly introduced and sent to committee, newly approved by a committee, or new on the House or Senate floor, in the last 7, 30 or 90 days.
- Coming up: bills on the House's posted weekly floor schedule, Senate bills with a cloture motion filed (a vote follows within days), and bills placed on a House or Senate calendar, ready for a vote but not scheduled. Only what the chambers publish; nothing is predicted. Right now the House has posted no schedule since the week of September 14, and the Senate is meeting in brief formal sessions; the page says so.
- The record is refreshed through October 1: 16,815 measures and 613 recorded votes, member by member.
- The Tax, Work and pay and Disability rating lenses moved into the Topic panel. The companion's guide explains the new filters.

## v4.0.101 — 2026-10-04 — Your companion is now a guide, on every page

- Help now starts with "On this page": what the page you are on is, how to use it in a few short steps, and where to go next. It changes as you move: open a bill and it explains the bill's tabs, its path and its rating bars; open the vote map and it explains how to step through votes. Every companion gives the same help.
- The companion now comes along everywhere: Plain Congress, every state legislature, On The Ballot for Congress and for each state, the ring of cards and the ballot door. Click or tap it to open the guide. Each guide also lists the whole site and lets you choose your companion, still it or switch it off. With the companion off, a small Help button opens the same guide.
- On these pages the companion stands in the bottom corner, above the version label, so it covers none of the page's own buttons.
- County and city officials (who holds each county and city office) are now marked "coming soon" for every state, on the home page, in the menus and on the ring of cards. Minnesota's early county pages are no longer published. The county and local races on the November ballot are unchanged.

## v4.0.100 — 2026-10-04 — A new front door, and seven companions

- The Civic Archive has a home page. It says in a few lines what the site holds, counts what is on file today, and opens five ways in: Plain Congress, On The Ballot, Officials, Method and Access. The ring of cards is still there under "All levels", and the log cabin under "Take a break".
- A new top bar with two menus, Reading & access and Help, and on a phone a bar of the same five doors at the foot of the screen. The record and ballot pages keep their own bar for now; they move to the new one next.
- Reading & access: type, size, spacing, contrast, motion and chart colours, in eight ready-made presets or eleven settings of your own, set once and kept on this device only. The Access page lists plainly what is done for readers with disabilities and what is not done yet.
- A Method page: where each fact comes from, how bills are rated and checked, and what the site will not do.
- A companion in the corner, if you want one: an Adélie penguin, a black-capped chickadee, a golden retriever, a tabby cat, an eastern gray squirrel, an eastern chipmunk or a garden snail, each drawn in 3D on your own device and sculpted from studies of how the real animal is built and moves. Point at it, with motion on, and it does a short dance made of the animal's own moves. It only opens Help; it never speaks or makes a sound, screen readers skip it, and Off loads nothing. Choose one under Help.

## v4.0.099 — 2026-10-03 — Arkansas gets the same treatment

- Arkansas's ballot page now has the real map: 2,915 precincts from the Arkansas GIS Office, cut where district lines split them, with every district each sits in (county, justice of the peace district, township, city, ward, House, Senate, Congress, judicial district, school district), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot, down to your own justice of the peace and constable. The same rule now places any county board seat elected by district, in every state.
- Arkansas lets a candidate file a title as part of the name printed on the ballot ("State Senator ..."); names are shown as printed, and a card's initials skip the title.
- Arkansas's candidates for Governor, the other statewide offices, the Legislature, the courts and the Pulaski and Washington county and city races show what the record holds: 79 campaign websites of their own, 51 official government pages, offices held (90, most from government pages), issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- How each place voted, from the Secretary of State's official results: President 2024, Governor and Senator 2022, President and Senator 2020, for all 75 counties and 16 judicial districts and the legislative districts whose precincts are whole.
- No pollster that publishes its methods has polled an Arkansas state race. The Governor's race has prediction-market prices as a tab. No readable Arkansas party page uses the word "endorsed". Polling places stay off the map; the page points to the state's own finder.

## v4.0.098 — 2026-10-03 — Utah gets the same treatment

- Utah's ballot page now has the real map: 3,331 precincts from the state's own map agency and the Lieutenant Governor's office, with the districts each sits in (county, city or town, House, Senate, Congress on the 2026 map, judicial district, State Board of Education district, school district), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot, including only your own State Board of Education seat.
- Utah elects no governor this year: its statewide races are the State Board of Education districts and judges standing for retention, and nobody has polled them or listed a market on them. Utah's cities vote in odd years, and its county and school races, though on the November ballot, are certified county by county and not loaded yet; the page says so.
- Utah's candidates show what the record holds: 157 campaign websites of their own, 67 official government pages, offices held (126, most from government pages), issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- How each place voted: 2024 by precinct for every county, judicial district and House district and 14 Senate districts; 2022 and 2020 by county. Every figure equals the official canvass.
- Utah's and Montana's court districts now carry their own state's ids. All states share one list of places, and Utah's district-court races had pointed at Minnesota's judicial districts, while Montana's court and Public Service Commission races did not match their own place records. These ids decide where a court race sits on the map and on a located reader's ballot, so they are fixed at the source.
- Iowa's map credit no longer names the same agency twice.

## v4.0.097 — 2026-10-03 — Oklahoma gets the same treatment, with its official primary results

- Oklahoma's ballot page now has the real map: 1,984 precincts from the State Election Board's own mapping contractor at the University of Oklahoma, with the districts each sits in (county, county commissioner district, city or town, ward, House, Senate, Congress, judicial district, school district), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot.
- Oklahoma prints only contested races on its November ballot. A candidate with no opponent is shown as elected without a vote and not printed on the ballot, never as "on the ballot".
- Oklahoma's official primary (June 16) and runoff (August 25) results are now loaded, from the State Election Board's own results files: the votes in every primary for Congress, the state offices, the Legislature and the county offices, and the winner of every seat the primary or runoff settled (23 House seats, 99 county seats and four district attorneys), each with when it was won.
- Oklahoma's candidates show what the record holds: 110 campaign websites of their own, official government pages, offices held, issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site. No Oklahoma party page that could be read uses the word "endorsed".
- How each place voted, from the Board's precinct results: President 2024 and 2020, Governor 2022 and both Senate races of 2022 and 2020, for all 77 counties, and for the legislative and commissioner districts whose precincts the results can place (Oklahoma and Tulsa counties count early and absentee votes countywide, so districts touching them are left out rather than estimated). Every county equals the Board's own county totals.
- No pollster that publishes its methods has polled an Oklahoma state race. The Governor's and Attorney General's races have prediction-market prices as a tab. Polling places stay off the map; the page points to the state's own finder.
- Kentucky's November list for Louisville and Jefferson County is now read from the County Clerk's own printed ballots, which put the sitting mayor on the Metro Mayor's race, where the state's list had left him out, and corrected several Metro Council, school board and small-city contests.

## v4.0.096 — 2026-10-03 — Colorado's campaign photos

- Colorado's candidates now show a photo where one was plainly the candidate's own portrait on their own campaign site (16 of the 29 whose sites offered pictures); the others keep their initials. Each photo is credited and linked to the site it came from.

## v4.0.095 — 2026-10-02 — Colorado gets the same treatment

- Colorado's ballot page now has the real map: 5,027 precinct pieces with the districts they sit in (county, city or town, House, Senate, Congress, judicial district, school district, the RTD transit district, and the seats of the University of Colorado regents and the State Board of Education), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot, including only your own regent and board seat. The precinct lines are the Census Bureau's from 2020, cut by today's district and city lines; where a piece matches the Secretary of State's 2026 precinct numbers, the page says so.
- Colorado's candidates for Governor, the other statewide offices and boards and the Legislature show what the record holds: campaign websites of their own, official government pages, offices held and issue headings, each with where it comes from. Photos from campaign sites follow once they have been looked at.
- "The record, not a label": endorsements only from party pages that themselves say "endorsed" (a county party's "do not retain" list on judges is not shown), earlier runs under a party label, and the candidate's own words. All 124 judges stand for retention, a yes-or-no question.
- How each place voted, from the Secretary of State's precinct results: President 2024 and 2020, Senator 2022 and 2020, Governor 2022, for every county and judicial district, and for 2022 and 2024 every congressional, Senate and House district (two House districts are left out for 2022, where one precinct voted in both).
- No pollster that publishes its methods has polled a Colorado state race. The Governor's and Secretary of State's races have prediction-market prices as a tab. No county clerk's local list is loaded yet, and the page says so. Colorado sells its statewide polling-place list, so polling places stay off the map and the page points to the state's own finder.

## v4.0.094 — 2026-10-02 — "Use my location" works in Alaska and Hawaii; lighter ballot pages

- "Use my location" now works for readers in Alaska and Hawaii, on the state pages and the ballot pages alike. Until now a reader in Anchorage or Honolulu was told the spot was outside the state: the two states' district and county lines had been drawn in a different frame of the map from the one used to find a reader. They are now drawn in Alaska's and Hawaii's own corners of the map, as on the Congress pages, so the maps and the lookup agree.
- Every state ballot page is about 14 percent smaller to download: the notes we leave ourselves in the page's code are taken out when the page is written. Nothing a page shows or does changed.

## v4.0.093 — 2026-10-02 — Wyoming gets the same treatment

- Wyoming's ballot page now has the real map: 946 precinct pieces with the districts they sit in (county, city or town, House, Senate, judicial district, school district), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot. The precinct lines are the Census Bureau's from 2020; where a piece matches the Secretary of State's 2026 precinct list, the page gives the precinct as that list writes it. Wyoming publishes no statewide lines for its conservation, hospital, college and other special districts, so a reader placed by location is told those races cannot be placed from a location.
- Wyoming's candidates for Governor, the other statewide offices, the Legislature, the courts and the counties, cities and school boards loaded so far show what the record holds: 120 have an official government page, 71 a campaign website of their own, offices held (163, most from government pages), issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- "The record, not a label": earlier runs under a party label and the candidate's own words. No Wyoming party page uses the word "endorsed", so that part of the record is empty here.
- How each place voted, from the Secretary of State's precinct results: President and Senator in 2024 and 2020, Governor in 2022, for all 23 counties and 9 judicial districts, and for the 33 House and 17 Senate districts whose precincts are whole; the rest are left out rather than estimated, and there are no figures for cities.
- No pollster that publishes its methods has polled a Wyoming state race. The Governor's race has prediction-market prices as a tab. Wyoming elects no Lieutenant Governor, so its Governor's race is between single candidates. Polling places stay off the map; the page points to the state's own finder.

## v4.0.092 — 2026-10-02 — Montana gets the same treatment

- Montana's ballot page now has the real map, drawn on the Montana State Library's 2026 precinct splits (current lines; in Carbon and Powell counties, where the splits are incomplete, whole precincts fill the gaps and the page says so), with the districts each precinct sits in (county, city or town, ward, House, Senate, Congress, judicial district, Public Service Commission district, school districts), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot.
- Montana elects no governor this year: its statewide races are one Supreme Court seat and two Public Service Commission districts. The page says so, and a reader outside those two districts is told the commission is not on their ballot this year. No one has polled or listed a market on any of them.
- Montana's candidates for the Supreme Court, the Public Service Commission, the Legislature and the county offices loaded so far show what the record holds: 113 have a campaign website of their own, 48 an official government page, offices held (87), issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- "The record, not a label": party endorsements on offices printed without a party (an endorsement made before the June 2 primary says so), earlier runs under a party label, and the candidate's own words. How each place voted in 2020 and 2024, from the Secretary of State's precinct results: every county and judicial district, and for 2024 every House, Senate and Public Service Commission district. Every figure equals the official canvass.
- Only 9 of Montana's 56 counties have their local lists loaded; elsewhere the page says "not loaded yet". Polling places stay off the map; the page points to the state's own finder.

## v4.0.091 — 2026-10-02 — Nebraska gets the same treatment

- Nebraska's ballot page now has the real map: 1,805 precinct pieces with the districts they sit in (county, city or township, ward, legislative district, Congress, judicial district, school district), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot, down to your own seat on the boards Nebraska elects by district (the Public Service Commission, the Board of Regents, the State Board of Education, natural resources districts, educational service units, community colleges). The precinct lines are the Census Bureau's from 2020, and the map says so.
- Nebraska has one chamber, elected without party labels: its races read "Legislative District", and the page shows no party colour or word for a legislative candidate.
- Nebraska's candidates for Governor, the other statewide offices and boards, the Legislature, the courts and the counties, cities and school boards loaded so far show what the record holds: 128 have an official government page, 54 a campaign website of their own, offices held (162, most from government pages), issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- "The record, not a label": earlier runs under a party label and the candidate's own words. No Nebraska party page uses the word "endorsed"; the parties publish lists of their candidates, which are not counted as endorsements, so that part of the record is empty here and the page says nothing in its place.
- How each place voted, by county: President and Senator in 2024, Governor in 2022, President and Senator in 2020, from the Board of State Canvassers' canvass books, for all 93 counties. Nebraska publishes no precinct results a program can read, so there are no figures for cities.
- No pollster that publishes its methods has polled a Nebraska state race this year. The Governor's race has prediction-market prices as a tab. Only ten counties' local lists are loaded; elsewhere the page says "not loaded yet". Polling places stay off the map; the page points to the state's own finder.

## v4.0.090 — 2026-10-02 — Missouri gets the same treatment

- Missouri's ballot page now has the real map: 5,462 precinct pieces with the districts they sit in (county, city or township, ward, House, Senate, Congress, judicial circuit, court of appeals district, school district), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot. The precinct lines are the Census Bureau's from 2020, the only statewide set, and the map says so.
- Missouri's candidates for State Auditor, the Legislature, the courts and the county offices loaded so far show what the record holds: 111 have a campaign website of their own, 69 an official government page, offices held (154), issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- A judge standing for retention is now shown as what it is, in every state: one name and a yes-or-no question, with no "vs" and no controls.
- How each place voted, by county: President, Senator and Governor in 2024, Senator in 2022, President and Governor in 2020, from the Secretary of State's county results, for all 115 counties and St. Louis city. Missouri sells its precinct results and publishes none, so there are no figures for cities or townships, and the page says so.
- "In office now" on a card is filled in more often, in every finished state: 127 sitting officeholders whose own government page gives the office with a start and no end (Missouri's State Auditor, county commissioners, judges, school board members) now show it. Where a page leaves any doubt about which office is still held, the card stays blank.
- Missouri elects no governor this year; State Auditor is the only statewide office, and no pollster that publishes its methods has polled it. Only 13 of Missouri's 116 election authorities have local lists loaded; elsewhere the page says "not loaded yet". Polling places stay off the map; the page points to the state's own finder.

## v4.0.089 — 2026-10-02 — State and local races get the Congress cards

- Every state and local race page (Governor and the other statewide offices, the Legislature, judges, county, city, township and school races, in every state) now has the same cards as the Congress race pages: the same card with its slight tilt and "vs" when two people face each other, and the same controls on each card: move it earlier or later, hide it, or drag it, with "Put back the official order" beneath. The arrangement is yours alone and stays on your device; the list's own order never changes, and the page ranks no one.
- "Step into the arena: compare them side by side" opens the same kind of table the Congress pages have: one column a candidate (the columns move and hide with the cards), and sections that open on a click and start closed: On the ballot; Who they are; The record, not a label; In office. It replaces the "Who they are" boxes and carries everything they held, with the same source lines and links. State and local pages show no campaign money, so there is no money section.
- Where voters choose several people (a school board, two Supreme Court seats) there is no "vs" between the names. A race with one name has no move or hide controls. A township or small district race gets the comparison only when a candidate filed a campaign website.
- "Forget my location and choices" now also clears any card arrangement you made.
- The comparison's "On the ballot" section shows the note the list keeps about a candidate, such as "standing for retention as the sitting judge" or "unopposed: declared elected without a vote", as the Congress pages do.

## v4.0.088 — 2026-10-02 — Michigan gets the same treatment

- Michigan's ballot page now has the real map, drawn on the Bureau of Elections' own 2026 precinct lines, with the districts each precinct sits in (county, city or township and village, ward, county commission district, House, Senate, Congress, district and circuit court, school district), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot; a reader in a village gets the township's contests too.
- Michigan's candidates for Governor, the other statewide offices and boards, the Supreme Court, the Legislature, the courts, and the cities and school boards of the nine counties loaded so far show what the record holds: 303 have an official government page, 184 a campaign website of their own, offices held (421, most from government pages), issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- "The record, not a label": endorsements only from party pages that themselves say "endorsed"; earlier runs under a party label; the candidate's own words. Michigan's Supreme Court justices are nominated at party conventions and printed without a party, so a convention nomination is shown too, in its own words and apart from endorsements.
- How each place voted, from the Bureau of Elections' precinct results: 2024 for 81 of 83 counties, 1,466 cities and townships and 37 House districts; 2020 for 73 counties; 2022 for 15. A county is shown for an election only where its precincts add up exactly to the Bureau's own county total; where they do not, the county is left out for that election and listed with both figures. Nothing is adjusted to fit.
- The Governor's race has its polls (Marist, Emerson, SSRS, Michigan State University) and prediction-market prices as tabs; Attorney General and Secretary of State have market prices. A market row for someone who is not on the November ballot is not drawn, and the tab says so.
- Only nine counties' local lists are loaded (Wayne, Oakland, Macomb, Kent, Ottawa, Ingham, Kalamazoo, Saginaw, Muskegon); elsewhere the page says the list is not loaded. Michigan publishes no statewide polling-place file, so the map points to the state's own finder.
- A name on Ingham County's list that our reader had cut short at a letter outside the English alphabet is now read whole.

## v4.0.087 — 2026-10-02 — Ohio gets the same treatment

- Ohio's ballot page now has the real map: 9,104 precinct pieces with the districts they sit in (county, city or township, House, Senate, Congress on the 2026 lines, court of appeals district, school district, and council districts and wards where a county or city has them), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot. The precinct lines are the Census Bureau's from 2020, the only statewide set, and the map says so.
- Ohio's candidates for Governor, the other statewide offices, the Supreme Court, the Legislature, the courts and the county offices loaded so far show what the record holds: 97 have an official government page, 74 a campaign website of their own, offices held (240, most from government pages), issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- "The record, not a label": endorsements only from party pages that themselves say "endorsed" (a party's slate card or sample ballot is not counted as one), earlier runs under a party label, the candidate's own words, and how each county and 185 cities voted in 2020, 2022 and 2024, from the Secretary of State's official canvass. Ohio's judges are nominated in party primaries and printed without a party in November; the page labels no one.
- The Governor's race has its polls (Marist, Emerson twice) and prediction-market prices as tabs; Secretary of State and one Supreme Court seat have market prices too.
- Only 23 of Ohio's 88 counties have their county and court races loaded, and 38 legislative seats have no November list yet; the page says "list not loaded" there, never "no candidate". Ohio rotates the order of names from precinct to precinct, so no ballot order is shown. Polling places stay off the map until the Secretary of State's list is matched to every precinct.
- Statewide court seats in every finished state now get the same polls and markets tabs as the other statewide races, and South Dakota's map now says its precinct lines are from 2020.
- "Earlier, under a party label" now needs the label on the record itself: a party's primary or nomination, a ballot that printed the party, a seat in a body whose members sit by party, or an appointment by a party's committee. A news article describing someone as a Democrat or a Republican does not count; two such entries (one in Ohio, one in Minnesota) were taken out.

## v4.0.086 — 2026-10-02 — South Dakota gets the same treatment

- South Dakota's ballot page now has the real map: its 835 precincts with the districts they sit in (county, city or township, House, Senate, Congress, judicial circuit, conservation and school districts), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot.
- South Dakota's candidates for Governor, the other statewide offices, the Legislature and the county offices show what the record holds: 182 have an official government page, 100 a campaign website of their own, offices held (116, most from government pages), issue headings from their own sites, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- "The record, not a label": earlier runs under a party label, the candidate's own words, and how each county voted in 2020, 2022 and 2024 from the State Board of Canvassers' certified canvass. A legislative district's past votes are shown only where its precincts add up exactly to that canvass; where they cannot be added up they are left out, never estimated.
- No pollster that publishes its methods has polled a South Dakota state race this year, and the page says so. The Governor's race has prediction-market prices as a tab. Polling places stay off the map until the Secretary of State's list is matched to every precinct.
- A candidate's page on a political party's own website is no longer shown as their campaign website, and no photo is taken from one. Eight North Dakota candidates whose only page is on their party's site now show no website; the party's endorsement of them is still shown where the party published one.

## v4.0.085 — 2026-10-02 — North Dakota gets the same treatment

- North Dakota's ballot page now has the real map: its 358 precincts with the districts they sit in (county, city or township, ward, commissioner district, legislative district, judicial district, soil conservation, park and school districts), drag and pinch, zoom to a street, streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot.
- North Dakota's candidates for the statewide offices, the Legislature, the courts and every county office show what the record holds: 226 have an official government page, with offices held (168) taken mostly from those pages, campaign websites where there is one, and a photo where one was plainly the candidate's own portrait on their own campaign site.
- "The record, not a label": the Democratic-NPL's and one Republican district's published endorsements, earlier runs under a party label, and how each county and legislative district voted in 2020, 2022 and 2024, from the Secretary of State's precinct results. County offices are nonpartisan here, and the page labels no one.
- No pollster has published a poll on any North Dakota state race this year, and the page says so. Polling places stay off the map until the Secretary of State's list is matched to every precinct.

## v4.0.084 — 2026-10-02 — Take a break, and "Insights on my location"

- Every page now has a small "Take a break" in its header. It leads to the cabin: a quiet log room with a fire and the Rocky Mountains outside the window. When you are ready, a glowing "Back to where you were" sign, or the cabin's own door, takes you straight back to the exact page you left.
- Every ballot page has "Insights on my location" fixed at the top. One click asks your device for your location, works out your state on the device, and lands you on that state's ballot page with a pin on the map, every district you are in, and the contests on your own ballot. Your location is never sent anywhere. If you would rather not share it, the page says so plainly and offers the list of states.

## v4.0.083 — 2026-10-02 — Iowa gets the same treatment

- Iowa's ballot page now has the real map: all 1,660 precincts with the districts they sit in (county, township or city, supervisor district, House, Senate, Congress, judicial, soil and water, hospital and school districts), drag and pinch, zoom to a street, and streets from OpenStreetMap only if you switch them on. "Use my location" finds your precinct on your own device and shows your exact ballot, township races included.
- Iowa's candidates for Governor, the other statewide offices, the Legislature and the county offices loaded so far show their campaign websites (120), issue headings from their own sites, offices held, and photos where one was plainly the candidate's own portrait, each with where it comes from.
- "The record, not a label" for Iowa: earlier runs under a party label, the candidate's own words, and how each county, township and district voted in 2020, 2022 and 2024, from the Secretary of State's precinct results. Iowa's parties publish nominee lists rather than endorsements, so that part of the record is mostly empty here, and the page says nothing in its place.
- The Governor's race has its polls (Marist, Emerson) and prediction-market prices as tabs; the Secretary of State and Agriculture races have a poll each.
- Only eleven counties' local lists are loaded so far; cities and school boards voted in 2025. The state's polling-place layer is from 2024, so polling places stay off the map until a current list is confirmed.

## v4.0.082 — 2026-10-02 — Wisconsin gets the same treatment

- Wisconsin's ballot page now has the real map: every one of its 7,161 wards with the districts it sits in (county, municipality, aldermanic and county board districts, Assembly, Senate, Congress, the Court of Appeals districts, school districts), drag and pinch, zoom to a street, and streets from OpenStreetMap only if you switch them on. "Use my location" finds your ward on your own device and shows your exact ballot.
- Wisconsin's candidates for Governor, the other statewide offices and the Legislature now show their campaign websites (146), issue headings from their own sites, offices held, and photos from their own campaign sites where one was plainly the candidate's portrait, each with where it comes from.
- "The record, not a label" for Wisconsin too: a party's own published endorsement, an earlier run under a party label, the candidate's own words, and how each county, municipality and district voted in 2020, 2022 and 2024, from official ward results.
- The Governor's race has its polls (Marquette Law School) and prediction-market prices as tabs; where no market lists a race the page says why that is usual.
- On Wisconsin's November ballot the only county offices are sheriff, clerk of circuit court and a few coroners, and only ten counties' lists are loaded so far; cities, towns and school boards vote in April. Polling places wait on a file from the Elections Commission.

## v4.0.081 — 2026-10-02 — Minnesota, finished: your precinct, your ballot, and who is on it

- A real map for Minnesota's ballot. One map draws every kind of district (counties, cities and townships, wards, county commissioner districts, school districts, state House and Senate, Congress, judicial, soil and water, hospital and park districts), and you can drag it, pinch it on a phone, and zoom from the whole state down to a street. Tap any district to see its name and its races.
- "Use my location" drops a pin, finds your precinct on your own device, names every district you are in, and shows exactly the contests on your ballot. Streets appear only if you switch them on; they come from OpenStreetMap, whose servers then see which map squares are asked for. Nothing else leaves your device.
- State and local candidates now show more than a name. For statewide offices, the Legislature, judges, county offices, mayors, councils and school boards: the campaign's website, a photo from the candidate's own site (119 so far, each looked at first), offices held, a birth year where a citable source gives one, and the issue headings from their own site, each with where it comes from. Township and small district candidates show what they filed. Never an address, a phone number, a family member or a word about anyone's views.
- "The record, not a label." Most local offices are nonpartisan, and this site does not guess anyone's politics. A race page shows what is on the record: a party's own published endorsement (256 so far), an earlier run or office under a party label, the candidate's own words, and how the place itself voted in past elections, from official results.
- The statewide races have their polls and prediction-market prices as tabs, under the same rules as Congress. Where no market lists a statewide or county race, the page says why that is usual.
- Ads now fold under one heading in groups of five, and every "Where this comes from" folds by kind of source.
- Polling places are not on the map yet: Minnesota sells that list rather than posting it, and the page says so and links the Secretary of State's own finder.

## v4.0.080 — 2026-10-01 — More faces, and more candidates in their own words

- 143 more candidates for Congress now have a photograph on their card, each taken from the candidate's own campaign website, credited and linked. Every option was looked at first: a photo is used only when it is plainly the site's own portrait of its candidate, one adult alone. Where the options showed several people, an event, a logo, or anything unclear, the card keeps the candidate's initials. Nobody is ever identified by their face.
- "In their own words" now lists the issue headings from 394 campaigns' own websites, as headings only: nothing is summarized or judged.

## v4.0.079 — 2026-10-01 — Ballot pages you can fold, sort and make your own; a cabin that looks like one

- The Congress ballot pages open calmer. The map of every state sits right under the numbers; the Senate races and every other race are folded away state by state until you open them; on a race page the polls and the betting prices are two tabs above the candidates that pull down when you want them.
- "Your ballot" can use your location (worked out on your device, never sent anywhere) and then shows a plain preview of the federal part of your ballot: each office, "Vote for one", and every name as printed. Your county's sample ballot remains the authority.
- The candidates' cards can be moved into any order and hidden one by one, and so can their columns in the side-by-side comparison, whose sections now start closed. The order a reader chooses is theirs alone and stays on their device; one button puts back the official list's order.
- The arena where the cards stand no longer has a colour of its own: it is a few shades off the page and follows light and dark.
- More candidates' blanks are filled. Where no official record gives a birth year or earlier offices, the pages now show what a government page, the campaign's own site, Wikipedia or a named news organization states: 824 campaign websites, 191 public offices and 56 birth years, each labelled with where it comes from and linked, each checked twice. Never an address, a family member or a word about anyone's views.
- The cabin has been rebuilt to look like a real one: round log walls and rafters, a wall of glass on a photograph of Rocky Mountain National Park for the hour and the season, a stacked-stone fireplace with a fire, real furniture, sunlight across the floor. It is still at its own address, cabin.html, and its Credits button names every photograph, texture and model it uses.

## v4.0.078 — 2026-10-01 — A first cabin, and quieter pages

- A first draft of a new front door: a small log cabin you can walk around in, with a fire, two armchairs, a bookshelf and a wide window on the Rocky Mountains. The view follows your own clock and calendar (morning, afternoon, dusk or night; gold aspens in autumn, snow in winter), worked out on your device. Nothing is sent anywhere. It lives at its own address, cabin.html, while it is made to look real; the ring of cards is still the landing page.
- Two posters glow on the cabin's far wall, and they are the doors. "Meet everyone asking for your vote" opens On The Ballot; "See what they did with the last one" opens Legislation & Legislatures. The same two doors are glowing signs at the foot of the page. Walk with the arrow keys or W, A, S, D and drag to look around; on a phone, drag to look and tap the floor to walk.
- The pages no longer offer the whole site as one file to download, and no longer name the files and programs the site is put together with. The sources, the methods, the formulas and the download of every figure on the district pages stay.

## v4.0.077 — 2026-10-01 — Local judges and the first counties of seven more states

- Colorado, Utah, Illinois, Oregon, Arkansas, Connecticut and Nevada join the local level, each with the part of its local ballot that an official list carries today. County and local races now stand at 22,148 contests and 36,970 candidates in 34 states.
- Illinois: the regional superintendents of schools in every region, the circuit judges, and suburban Cook County's and Chicago's own contests. Nevada: Clark and Washoe counties, where about nine in ten Nevadans live. Arkansas: Pulaski and Washington counties.
- Colorado's RTD directors and 117 judges' retention votes, Utah's justice court retention votes, Oregon's district attorneys and circuit judges, and Connecticut's judges of probate and registrars of voters in the 19 towns whose ballots are posted so far (the rest are due by October 9).
- Every county still to be read says so on its page and names the county office that publishes its list.

## v4.0.076 — 2026-10-01 — Nine more states, county by county

- County and local races open for Florida, Nebraska, Wyoming, Michigan, Iowa, Missouri, Montana, Ohio and Wisconsin: 4,732 more contests and 6,328 more candidates. On The Ballot's local level now holds 21,870 contests and 36,490 candidates in 29 states.
- Florida comes from the Division of Elections' own file of local candidates (county commissions, school boards, and nearly two thousand special district seats), placed county by county with each supervisor of elections' notice. A candidate nobody opposed is elected without a vote and is shown that way.
- These states have no single list for most local offices, so they are read one county at a time, largest first, from each county election office's own list or sample ballot: nine Michigan counties, sixteen in Wyoming, eleven in Iowa, twelve in Missouri, ten in Nebraska (plus every district board statewide), twenty-three county boards in Ohio, ten in Wisconsin, nine in Montana. Every county not read yet says so on its page, with the reason.
- Michigan's circuit, district and probate judges, Missouri's and Nebraska's judges' retention votes, Ohio's appeals and common pleas judges and Florida's county judges are in, each under the counties they serve.
- Wisconsin elects only sheriffs, clerks of circuit court and a few coroners in November (cities, towns and school boards vote in April); Iowa's cities and schools voted in 2025. Each state's page says which local offices are elected when.

## v4.0.075 — 2026-10-01 — County and local races in twenty states

- On The Ballot's county and local level, Minnesota only until now, opens for nineteen more states: Kentucky, North Carolina, Virginia, South Dakota, North Dakota, Washington, Idaho, West Virginia, Oklahoma, Texas, Louisiana, South Carolina, Alabama, Vermont, Maryland, New Mexico, Maine, Delaware and Hawaii. Together with Minnesota that is 17,138 county and local contests and 30,162 candidates in 1,235 counties, every one from the state's own election office.
- Each of these states' ballot pages now has its counties, a page per county (county offices, cities and towns, school boards, special districts and the local courts that reach it) and "your ballot": pick your county, then your city or town and your school district.
- Every state's page says, in the state's own terms, which local offices are on the November 3 ballot and which are elected at another time, and lists plainly what is not here yet and why. Oklahoma prints only contested races; Louisiana's November 3 is an open primary, and two thirds of its local offices were filled when only one candidate qualified; Texas's cities and school districts publish their own lists and are still to come.
- As everywhere on these pages, a local candidate is shown by name, office, place and party (or "Nonpartisan office") only. Addresses and contact details in the official files are never read.
- The ballot door's "County and city" card now counts every state loaded and opens the list of them.

## v4.0.074 — 2026-09-30 — State races in 49 states

- Every state with state races on this November's ballot now has its page: New England, South Carolina, Delaware, Alaska and Hawaii, and California, Texas, Florida, New York, Pennsylvania and Illinois join the list, with their primaries and official votes where published. New Jersey has no state race this year (its Legislature is elected in odd years).
- Massachusetts's, Rhode Island's and New Hampshire's November lists, and most of Connecticut's (whose Secretary of the State has posted only some towns' sample ballots), wait on files we cannot fetch yet; their pages say so.

## v4.0.073 — 2026-09-30 — Twelve more states' state races

- North Carolina, Maryland, Washington, Alabama, Oregon, Mississippi and New Mexico have their statewide, legislative and court races on the ballot pages, with official primary votes; Georgia's primaries and runoffs are in while its November list waits on a file its Secretary of State puts behind a check.
- Virginia and Louisiana elect their legislatures in odd years, so their pages show only the few state contests on this November's ballot (Virginia's House District 20 special election). Arizona's and Nevada's wait on files their offices do not let us fetch. 33 states in all.

## v4.0.072 — 2026-09-30 — Nine more states' legislatures on the ballot

- Colorado, Kentucky, Utah, Oklahoma, Arkansas, Idaho and West Virginia now have their statewide, legislative and court races on the ballot pages, from each state's own lists, with their primaries and official votes where published: 21 states in all.
- Tennessee's, Kansas's and Indiana's pages list their races and who holds each seat; their November candidate lists wait on files their election offices do not let us fetch, and the pages say so.

## v4.0.071 — 2026-09-30 — State and local races on the ballot, and the ads themselves

- On The Ballot now has state and local races. Minnesota's page has every race on its November ballot, from the Secretary of State's own lists: governor and the statewide offices, all 201 legislative seats, judges, and county, city, township, school and hospital district offices, 7,981 candidacies. Pick your county, city, school district and House district (or let your device find them) to see your whole ballot.
- Wisconsin, Iowa, Michigan, the Dakotas, Ohio, Indiana, Missouri, Nebraska, Montana and Wyoming have their statewide, legislative and court races, with their primaries and official votes where published. Choose a state from the ballot door.
- For state and local candidates the pages show only what each filed under: name, office, place, party or nonpartisan office, and ballot order. A sitting legislator links to their record; nothing else is shown about anyone.
- The ads themselves: 19,227 ads from Google's public political ads library are linked from the Congress race pages, each opening where Google shows it. A campaign's own ad says so; an outside group's ad carries what that group swore to the FEC it spent for or against the candidates in the race. The pages never call an ad an attack or a positive ad.

## v4.0.070 — 2026-09-30 — The side-by-side table fills in ads and polls

- When you step into the arena to compare candidates, the rows that said "still to come" now show the real figures: each campaign's own ad spending by kind, what outside groups spent on ads for and against each candidate, links to the public ad libraries, and each candidate's latest poll from a Transparency Initiative member with our average.

## v4.0.069 — 2026-09-30 — A thousands separator on the ballot home page

- The ballot home page writes its candidate count with a comma (1,128).

## v4.0.068 — 2026-09-30 — California checked against its certified list

- California's November candidates, taken from the June 2 top-two results, are now checked against the Secretary of State's Official Certified List of Candidates (August 27, 2026): all 104 names and party preferences agree, in all 52 districts.

## v4.0.067 — 2026-09-30 — The ballot door counts what the pages count

- The On The Ballot door now counts the states whose November lists are loaded (41) and every candidate on a November ballot, Louisiana's open primary included, the same way the pages do.

## v4.0.066 — 2026-09-30 — Primaries for the big states, and polls for Texas and Florida

- Texas's March 3 primaries and May 26 runoffs, Illinois's March 17 primaries, Pennsylvania's May 19 primaries and New York's June 23 primaries are in, with the official vote counts; Florida's August 18 primaries now show their official votes too.
- Polls for the Senate races in Texas (seven, from Marist, Emerson and ReconMR) and Florida (five), from Transparency Initiative members only; Illinois's race has no published November poll by anyone. Every one of the 35 Senate races now says what polls exist and which are counted.

## v4.0.065 — 2026-09-30 — Alabama, Louisiana, Oregon, Mississippi and New Mexico

- Alabama, Oregon, Mississippi and New Mexico are loaded from each state's own official list, with their primaries and official votes; Alabama's includes the August 11 special primaries held after its 2023 map came back.
- Louisiana's House races show what is really on the November 3 ballot, following the Secretary of State's own notice: an open primary with every party on one ballot, and a December 12 runoff if nobody wins more than half. Louisiana's Senate race is an ordinary general election, after party primaries in May and June.
- Nevada's list sits behind a check we do not get past, so its races say the list is coming.
- What bettors are paying, as information only, for the Senate races in Texas, Illinois and Florida and twenty-seven more House races in California, Texas, Florida, New York, Pennsylvania and Illinois, with each state's own problem-gambling line where its official page names one.

## v4.0.064 — 2026-09-30 — New England, the Carolinas' neighbours, Alaska and Hawaii

- New Jersey, South Carolina, Connecticut, Maine, Delaware, Vermont, Alaska and Hawaii are loaded from each state's own official list, with their primaries and official vote counts: Maine's counted by ranked choice, Alaska's a top-four primary, South Carolina's with the special primary held after Senator Lindsey Graham's death.
- Massachusetts's and Rhode Island's primaries are in with official votes; their November lists, and New Hampshire's files, sit behind checks we do not get past, so those races say the list is coming.
- Polls for the Senate races in North Carolina (eleven), Georgia, New Hampshire, Massachusetts, Rhode Island and Maine, from Transparency Initiative members only, including the University of New Hampshire Survey Center's releases read from its own repository.
- Each state's own problem-gambling line in the betting-market notice for twenty more states; only the national line is promised day and night.
- A candidate is never matched to another candidate's FEC registration or congressional record: Alaska's Senate ballot has two Daniel Sullivans, and each now shows only his own.

## v4.0.063 — 2026-09-30 — North Carolina, Virginia, Washington and Maryland, and Georgia's primaries

- North Carolina, Virginia, Washington and Maryland are loaded from each state's own official list, with every primary and the official vote counts. Washington's primary is top-two, like California's, and the page now names the right state.
- Georgia's primaries and runoffs are in, with the official results; its November list sits behind a check we do not get past, so its races say the list is coming. Arizona's lists and results refuse our requests, so Arizona waits.
- What bettors are paying for the Senate races in Georgia, North Carolina, Virginia, Alabama, Louisiana, Oregon, Mississippi and New Mexico, and thirteen more House races.
- Names written with a suffix after a comma (Donald S. Beyer, Jr.) are now read correctly when candidates are matched to their records.

## v4.0.062 — 2026-09-30 — Seven more states: Colorado, Kentucky, Utah, Oklahoma, Arkansas, Idaho and West Virginia

- Colorado, Kentucky, Utah, Arkansas, Idaho and West Virginia are loaded from each state's own official list, with their primaries and the official vote counts (Colorado's checked against its certified abstract; Kentucky's from the Board of Elections' certification, where Thomas Massie lost his primary).
- Oklahoma's November ballot is loaded from the State Election Board's list, county by county; its primaries show who won, because the Board's results site refuses our requests.
- Kansas's primaries are in with the official vote totals; its November list waits behind a human-verification page we do not get past. Tennessee's lists and results wait too: the Secretary of State's sites refuse our requests.
- Polls for the Senate races in Tennessee, Colorado, Kentucky, Oklahoma, Arkansas, Kansas, Idaho and West Virginia, from Transparency Initiative members only. Where the release's margin of error covers a different group than the figure shown, the table says so in plain words.
- Tennessee's problem-gambling line (the REDLINE) is in the betting-market notice; the other states in this group point to the national line.

## v4.0.061 — 2026-09-30 — Six more states, and the primaries of Iowa and the Dakotas

- Nebraska, Montana, Wyoming and Missouri are loaded from each state's own official candidate list, with their primaries: Nebraska, Montana and Wyoming with the official vote counts, Missouri with who won (its official totals are not posted yet).
- Ohio's Senate special election and 13 of its 15 House races are loaded from its county boards' official lists (in
  Ohio the board of each district's largest county certifies its candidates), with every May 5 primary and the
  official vote counts from the Secretary of State's canvass. Districts 2 and 12 say plainly that their list is not
  loaded yet: the boards that certify them do not post it where we can read it.
- Former members of Congress running again (Sherrod Brown, Mike Rogers, Colin Allred and others) now show the offices
  they held, from the official congressional roster.
- Indiana's primaries are in, with the certified vote counts. Its November list waits: the Election Division's own link to it is broken, for browsers as well as for us, so Indiana's races say the list is coming.
- Iowa's and North Dakota's primaries now show the official vote counts; South Dakota's show who won, until its certified canvass is posted.
- Polls for the Senate races in Ohio, Nebraska, Montana and Wyoming, only from pollsters in AAPOR's Transparency Initiative and each checked against the pollster's own release. Where no such poll exists the page says so, and says how many polls by others were found and left out.
- What bettors are paying, as information only, for the Senate races in Ohio, Nebraska, Montana, Wyoming, Tennessee, Colorado, Kentucky, Oklahoma, Arkansas, Kansas, Idaho and West Virginia, and eight more House races.

## v4.0.060 — 2026-09-30 — South Dakota's polls, and the helplines of the Dakotas and the next states

- South Dakota's Senate race now says plainly that no pollster in AAPOR's Transparency Initiative has published a poll of it, and names the eight polls by others that were found and left out (Public Policy Polling, Impact Research, Public Opinion Strategies, Mason-Dixon).
- The notice before a betting market now gives each state's own problem-gambling helpline, from the state's own page, for North Dakota (GamblerND, 1-877-702-7848), South Dakota (1-888-781-HELP), Ohio, Indiana, Nebraska and Montana. Wyoming's Department of Health points to the national helpline, which is shown everywhere.

## v4.0.059 — 2026-09-30 — Minnesota's primaries, and the campaigns in their own words

- Each Minnesota race shows its August 11 primaries: every candidate who
  filed for each party, from the Secretary of State's candidate filings,
  and who won, from the November list (14 party primaries). Vote counts
  come when the official results are loaded.
- Campaign websites come from Minnesota's own candidate list, so the
  cards link to each campaign's site.
- Where a campaign has an issues page, the comparison lists its topics as
  the campaign's own headings (nothing summarized or judged), with a link
  to read them in their own words: seven Minnesota campaigns so far.
- Five more candidates have a photo from their campaign's own site, each
  looked at first and chosen only when it shows the candidate alone.

## v4.0.058 — 2026-09-30 — Minnesota's candidates

- Minnesota's official candidate list is loaded, from the Secretary of
  State's "Candidates in the General Election" file: the Senate race
  (Michele Tafoya, Peggy Flanagan, Marisa Simonetti, Rebecca Whiting)
  and all eight House seats, 21 candidates in all, in ballot order.
- Every Minnesota race now has its arena of cards, the money behind each
  campaign, the ads for and against, the map, and its share card; the
  Senate race also has its poll and the betting markets. Minnesota's
  primary vote counts come next.

## v4.0.057 — 2026-09-30 — Each state's own gambling helpline

- The notice before a betting market now gives Michigan's (1-800-270-7117)
  and Wisconsin's (800-GAMBLE-5) own helplines for their races, as it does
  for Minnesota and Iowa, beside the national one; each number is taken
  from the state's own page.

## v4.0.056 — 2026-09-30 — Share any race

- Every race with an official list has a "Share this race" button and a
  share page of its own: a pasted link shows a card with the race, its
  day, who holds the seat, the candidates in their party colours and
  the district picked out on its state, and opens the race.
- The notice before a betting market now shows Iowa's own helpline for
  Iowa's races, beside the national one.

## v4.0.055 — 2026-09-30 — Polls for Michigan's and Iowa's Senate races

- Michigan's Senate race now shows five polls by members of the
  Transparency Initiative (Marist, Emerson twice, SSRS for CNN and
  Michigan State University), each checked against the pollster's own
  release, and our average of them with the arithmetic shown.
- Iowa's Senate race shows three (Marist and Emerson twice).
- Polls by members that could not yet be checked against the pollster's
  own release (one behind a paywall, one only reported secondhand) are
  named but not counted until they are.

## v4.0.054 — 2026-09-30 — Ads, polls and the betting markets, Minnesota first

- Every race with an official list now shows its ads and the money behind
  them: what each campaign reported spending on TV, digital and
  streaming, print and mail, radio, texts and calls, and door-knocking;
  what others spent for and against each candidate on their own, since
  the primary and in it; and the committees that spent the most. From
  the Federal Election Commission's filings; each expense's kind is read
  from the purpose its spender wrote, and one reported twice counts once.
  Links go to Meta's and Google's public ad libraries to see the ads.
- Polls, only from pollsters in the Transparency Initiative of the
  American Association for Public Opinion Research, each checked against
  the pollster's own release: the latest from up to five of them, and our
  own average of the ten most recent with the arithmetic shown. For
  Minnesota's Senate race one poll qualifies so far (Emerson College,
  February); the page says which other polls were left out and why.
- What bettors are paying on Polymarket and Kalshi, as information only,
  folded away and labelled as neither a poll, a forecast nor a record.
  Going to a market first opens a notice: that these are bets, the age
  limit, that their legality is disputed in some states, and the
  national (1-800-MY-RESET) and Minnesota (1-800-333-HOPE) problem-
  gambling helplines. No referral links. Minnesota's, Michigan's, Iowa's
  and South Dakota's Senate races, and ten House races where Kalshi runs
  a market (Minnesota's 2nd among them).

## v4.0.053 — 2026-09-30 — The Upper Midwest on the ballot, and maps for every race

- On The Ballot now carries the official candidate lists of Michigan,
  Wisconsin, Iowa, North Dakota and South Dakota, read from each state's
  own election office: every House seat, and the Senate races in
  Michigan, Iowa and South Dakota. Minnesota's list is ready to load as
  soon as its files are saved.
- Wisconsin's party primaries show every candidate's votes, from the
  Elections Commission's official county-by-county report. Michigan's
  show who ran in each party's August primary and who won it.
- Each state's page has a map, drawn like the Vote map: every district
  in the colour of the party that holds it today, with its number on it,
  and striped where the member who holds it is not on the ballot for it.
  Point at a district, or tap it, to see who is running there; zoom in
  for the cities. A second view shows the Senate seat.
- Each race's page shows where it is: its district picked out on the
  state, or the whole state for a Senate race. Tap a neighbouring
  district to go to its race.
- The map of the country has a second view too: the Senate seats on the
  ballot, by who holds them today.
- Where a state drew new district lines for 2026 (California, Florida,
  Texas and six more), its districts are listed but not drawn yet, since
  the old lines would be the wrong districts.

## v4.0.052 — 2026-09-29 — The crossings, in 3D and in your own eyes

- Both crossings are now real rooms in 3D, seen as if you were standing
  in them, with light, shadows and depth.
- Into On The Ballot: a polling place, with voting booths, a flag and a
  "Polling Place" sign. You step up to the scanner on the ballot box.
  Your ballot comes up from where your hand would hold it, a little
  unsteady, and you feed it into the slot at the front, as on the real
  machines. The rollers take it, the screen reads it and says "Your
  ballot was counted", and you lean in to the screen.
- Back to Legislation & Legislatures: a study. You reach for a book, the
  one nearest your pointer, and pull it. Something behind the shelves
  gives, light shows at the edges, and the books tumble off toward you
  and land in a heap. The empty bookcase pushes back into the wall and
  swings aside, and the lit passage behind it draws you through.
- Moving the pointer moves your head a little, as it would in a real
  room. A click or tap skips the rest.
- The ballot is generic: no names, no parties.
- Where a device can't draw 3D, the flat scenes play instead; with Motion
  off, the page simply fades. The 3D is drawn with three.js (MIT
  licence), kept with the site and loaded only when you reach for the
  switch.

## v4.0.051 — 2026-09-29 — Crossings that fit what each side covers

- Going into On The Ballot, a hand carries a marked ballot up to a ballot
  scanner and feeds it in; the scanner reads it, its light turns green,
  the screen says "Ballot counted, thank you for voting", the count of
  ballots cast goes up by one, and the view moves into the screen.
- Going back to Legislation & Legislatures, the books tumble off a
  bookshelf, the shelf falls away, a door behind it swings open onto
  light, and the view goes through the doorway.
- The wormhole and the black hole are kept for later.

## v4.0.050 — 2026-09-29 — A black hole, to compare with the wormhole

- Going into On The Ballot from the front door now falls through a black
  hole: starlight bends into arcs around it, a disc of hot gas swirls, a
  thin bright ring marks its edge, and the black event horizon grows until
  it swallows the screen. You come out the other side through a white
  hole, a flash of light with the page opening out of the middle.
- The way back still takes the wormhole, so the two can be compared.

## v4.0.049 — 2026-09-29 — Pennsylvania and Illinois

- Pennsylvania's list for November 3: all 17 House seats, 34 candidates,
  from the Department of State's own election information, with each
  party's May 19 primary field and its winner.
- Illinois's list: all 17 House seats and the open Senate seat, 39
  candidates, from the State Board of Elections' candidate list; the three
  candidates the Board removed are left off.
- Six states' official lists are now in: 180 races and 409 candidates on
  the November ballot, 398 of them tied to their FEC filings.

## v4.0.048 — 2026-09-29 — New York joins On The Ballot

- New York's certified list for November 3: all 26 House seats, 59
  candidates, from the State Board of Elections' certification of
  September 17. New York lets several parties nominate the same person, so
  a candidate's card lists every party line they hold, in ballot order;
  36 of the 59 hold more than one.
- Four states' official lists are now in (California, Florida, Texas and
  New York): 144 races and 336 candidates on the November ballot.
- The way back is now the flag: the fireworks spell LEGISLATION &
  LEGISLATURES with a blue canton of white stars and thirteen red and
  white stripes, rippling as if it were flying. When the words are
  complete, on either door, they finish with a flash of light and a ring
  of red, white and blue sparks.

## v4.0.047 — 2026-09-29 — Texas, and faces, ages and years in office on every card

- Texas joins California and Florida: its certified list for November 3,
  all 38 House seats and the Senate race, 87 candidates in ballot order,
  read from the Secretary of State's 1,395-page certification.
- Every candidate's card now shows their age, the office they hold now and
  for how long, and their years in any office on record. These come from
  official records only: the Biographical Directory of the U.S. Congress
  and the state rosters. Where no record gives a birth date or an office,
  the card says so; nothing is estimated.
- Members of Congress and state legislators now appear with their official
  portraits. Other candidates keep their initials for now; photos from
  their own campaign websites come next, each one looked at before use.
- The comparison adds a "Who they are" section: age, every office on
  record with its years, and where the photo comes from.
- On the ballot side, the switch at the top now reads Legislation &
  Legislatures and takes you back. Rest on it for three seconds and the
  fireworks spell out the way back.
- The fireworks are now red, white and blue, with CLICK TO SEE in silver.

## v4.0.046 — 2026-09-29 — On The Ballot opens: who is running for Congress

- A new switch sits at the top of the front door: On The Ballot, with the
  days left until the November 3 election beneath it. Click it and the page
  is pulled through a wormhole into a new space. Rest the pointer on it for
  three seconds first and fireworks spell out ON THE BALLOT, CLICK TO SEE
  across a night sky; a click goes through, and otherwise the sky clears.
  With Motion off it is a plain fade.
- The new space has its own front door, a ring of cards like the first:
  Congress now, then governors and legislatures, then county and city.
- Congress: every House seat and the 35 Senate races on the November 3
  ballot, two of them special elections, with a page for each state and
  each race. Who is running comes only from each state's own official
  list, added one state at a time, largest first. California and Florida
  come first: 190 candidates on the November ballot, and 441 in the
  primaries that chose them.
- A race's general election is an arena: one card per candidate, every
  card the same size, in the order the state's list gives (or by surname
  where it gives none), never by money or polls. Step into the arena and
  the candidates line up side by side: the party as printed on the ballot,
  their record in Congress if they serve there today, and their 2026
  campaign money from the FEC, organizations named and people as a total,
  with outside spending kept apart.
- A race's primaries are fields, every candidate in a lane: California's
  June 2 top-two primary with the official vote counts, Florida's August
  18 party primaries with the winners marked (their vote counts come next).
- Where a state drew new congressional lines for 2026 (nine states did),
  the pages say so and name the source.
- Organization names keep their capital letter after a bracket, on the
  money pages too.

## v4.0.045 — 2026-09-27 — This week's record

- The federal record is up to date through September 25: 16,593 bills and
  joint resolutions, 113 of them law, and 609 roll calls, each checked
  member by member against the official count.
- Five bills became law since the last update. The Lindsey O. Graham
  Sanctioning Russia and Iran Act of 2026 (H.R. 5334) was signed on
  September 18. Four signed on September 11 had been waiting for the record
  to catch up: the Stop Secret Spending Act of 2025 (H.R. 2069), the
  National Emergency Medical Services Memorial Extension Act (H.R. 2196),
  the Doug LaMalfa Federal Disaster Tax Relief Certainty Act (H.R. 5366),
  and H.R. 1276, which lifts restrictions on a parcel of land in Paducah,
  Kentucky. Each one's path now ends with the President's signature.
- Behind the scenes, the weekly update now redraws every bill's path along
  with its status, so the two always come from the same day's record, and
  it waits out a home connection that drops an address lookup for a few
  seconds instead of stopping.

## v4.0.044 — 2026-09-27 — Light pages, name cards, the reasons behind every rating, and a bill's real path

- Every page now opens light, on the white background, wherever you enter:
  the front door, the federal pages, every state and the county pages. A
  reader who switches to dark keeps dark; the choice is remembered.
- Rest the pointer on a member's name, anywhere a name appears, and a short
  card opens: portrait, seat and party, how long they have served and when
  they are next on the ballot, what they sponsor, how often they voted and
  broke with their party, their committees, and the first sentence of their
  Wikipedia article, fenced off and labelled as not an official record. A
  link opens their own page. State pages do the same with the state's own
  records, including the campaign money on file.
- Rest on a rating, or tap it, and its whole reasoning opens beside it:
  where this bill sits and why, the evidence grade and what that grade
  means, the confidence, the sources, how much is at stake, what the scale
  means from end to end, and who made the rating, when, under which version
  of the rubric, and whether a person has reviewed it. For "Who backed it"
  the card shows the arithmetic itself: each party's yes votes on each
  passage vote, the yes-rates, and how they make the number. Nothing about
  a rating is hidden anywhere else.
- A bill's path is no longer six fixed stops. It is every step the record
  shows, in order, drawn in three lanes (House, Senate, President), so a
  bill that goes back and forth between the chambers is drawn going back
  and forth. H.R. 6644, for example, passed the House, was changed by the
  Senate, changed again by the House, changed once more by the Senate,
  accepted by the House, and became law without the President's signature;
  all six trips are there with their dates. Steps still ahead are drawn
  dashed. Every dot carries its date; rest on it, or tap it, for what
  happened, the vote count with each party's yes and no votes, the votes
  along the way such as cloture, and a link to the official roll call.
- The Votes and path tab lists every step in order, in plain words, each
  with its date, its chamber and the votes that decided it, with what each
  committee did, and ends with the steps still ahead. The steps come from a
  new `actions` stage that reads every action in the Bill Status files
  already on this computer (68,407 of them, downloading nothing).

## v4.0.043 — 2026-09-26 — The local level opens: Minnesota's counties

- The front door's third card, County and city, opens for the first time,
  onto Minnesota's 87 counties: one map of every county, drawn from the
  Census Bureau's boundary file and sitting exactly inside the state
  outline the site already uses, a card for each county, and a page for
  each county's offices. The page says plainly what is not loaded yet.
- Who holds each county office will come from one source only, the
  Secretary of State's official election results, read from the results
  files the Secretary publishes for each election: the winner of every
  county office on the ballot, with the votes, the election date and the
  term the office carries. The loader for those files is written and
  waiting; the Secretary's results site turns scripts away, so the files
  are downloaded by hand. Every county office in Minnesota is nonpartisan
  on the ballot, so the pages show no party and guess none.
- New pieces: `run_local.py` (counties, results, check, site),
  `states/load_counties.py`, `states/load_local_results.py`,
  `build_local_dev.py`. The state pages and the money loaders are unchanged.

## v4.0.042 — 2026-09-25 — New York's campaign money

- New York is the ninth state with its campaign money loaded, from the
  State Board of Elections' public reporting system: its bulk download of
  every itemized transaction filed since 1999, its register of every filer,
  and its own list of the candidates each authorized committee was formed
  for. The Board's site turns scripts away at the door, so the files were
  carried out of the browser by hand and the loader reads them from disk;
  a newer one-year file dropped beside them replaces what it repeats. All
  212 sitting legislators are matched: their own candidate filings, 275
  authorized committees, and 9 committees the Board lists for several
  candidates, which are divided equally among them as New Jersey's joint
  committees are. Since 2015 the campaigns took $85 million from named
  organizations, $54 million from people as totals, and $3 million in
  loans.
- The Board codes every giver, so political committees and PACs, party
  and campaign committees, other candidates' committees, unions, and the
  corporations, LLCs, partnerships and associations New York lets give
  directly are named as filed; the candidate's own money and the spouse's,
  which the Board files under one code, count as own money; a professional
  practice under a person's own name is counted with people. A transfer
  between two of a member's own committees is "moved in", not a donor. The
  leadership committees give most of all: the Democratic Assembly Campaign
  Committee and the Democratic Senate Campaign Committee gave sitting
  members more than $7 million between them, under a dozen spellings the
  loader folds into one.
- A member's register entry carries only their latest office, and New
  York seats often pass between relatives and predecessors of the same
  name (Weprin, Wright, Hevesi), so a candidacy is the member's by name
  first, and by the seat alone only when registered in the member's own
  time. A committee tied to a member's run for another office is left out
  and listed. No outside spending is shown for New York: the Board's file
  records independent spending by office and district, not by candidate.
- The member page's sentence about shared committees now serves any state
  whose agency lists a committee for several candidates.

## v4.0.041 — 2026-09-25 — New Jersey's campaign money

- New Jersey is the eighth state with its campaign money loaded, from the
  Election Law Enforcement Commission's own reports and data search system.
  The Commission publishes no bulk file any more; the loader asks its search
  pages' data calls the way the pages themselves do, once for the register
  of every Senate and Assembly candidacy and every joint candidates
  committee, and once per chamber and election year for the contributions
  (kept for a month). All 120 sitting legislators are matched: 877 of their
  own campaign accounts with money since 2015, plus 366 joint candidates
  committees that 78 of them raised through. $128 million came from named
  organizations, $36 million from people as totals, and $4 million in loans.
- New Jersey candidates raise much of their money together: a district's
  senator and two Assembly members of one party form a joint candidates
  committee, named for them ("Sarlo Schaer & Calabrese"), and the Commission
  files it as a committee of its own. The loader reads which candidates a
  joint committee was formed for from the names in its title, checked
  against the Commission's register of that district's candidates, and
  divides every gift equally among them. A member's page names every joint
  committee their share came through. A member's own committee paying into
  their joint committee, or the joint committee passing money on to the
  member's own account, is the member's money moving and shows as
  "moved in", not as a donor.
- The Commission codes every giver by kind, so political committees, party
  and legislative leadership committees, other candidates' committees, and
  the businesses and unions New Jersey lets give directly are named as
  filed. A giver filed with no kind is read from its name, and a business
  filed under a person's own name (a doctor's or accountant's practice) is
  counted with people, so that a person is never shown. New Jersey's
  legislative leadership committees fund campaigns most of all: the
  Democratic Assembly Campaign Committee, the Senate Democratic Majority
  and the Republican State Committee gave sitting members $8 million between
  them. No outside spending is shown for New Jersey: the Commission's
  expenditure records name payees and purposes, not the candidate a
  committee spent for or against.

## v4.0.040 — 2026-09-25 — Florida's campaign money

- Florida is the seventh state with its campaign money loaded, from the
  Division of Elections' campaign finance database. Florida publishes no
  bulk file, so the loader asks the Division's own public query form, one
  family name at a time (161 requests, a second and a half apart, kept for a
  month), and reads the tab-separated file it answers with. All 155 sitting
  legislators are matched to their campaign accounts, 195 in all, with
  226,859 contributions since 2015: $73 million from named organizations,
  $39 million from people as totals, $7 million in loans and $2 million of
  the candidates' own money.
- Florida campaigns itemize every contribution, so nothing is below a
  threshold here, but the Division's records carry no code for what kind of
  giver a row is. An organization is named when its name or its occupation
  column says it is one: a political committee, a party, or a company by its
  corporate words. A giver whose name shows neither is counted with people,
  so a business written without such a word may be hidden, and a person is
  never shown. Florida's parties fund legislative campaigns most of all: the
  House Republican Campaign Committee, the Republican Party of Florida and
  the Senate Republican campaign committee gave sitting members $13 million
  between them.
- Only the accounts a member opened for State House and Senate races count,
  found by the Division's own candidate record. Four members changed party
  while in office and keep both accounts; an account of another party that
  was over before the member's first term is a namesake and is left out. A
  political committee a legislator chairs is a separate filer and is not
  part of the campaign. No outside spending is shown for Florida: the
  Division's expenditure records name payees and purposes, not the candidate
  a committee spent for or against.

## v4.0.039 — 2026-09-25 — California's campaign money

- California is the sixth state with its campaign money loaded, from the
  Secretary of State's Cal-Access raw data export: every table of the
  Cal-Access database as plain text (1.6 GB, refreshed daily, no account).
  All 119 sitting legislators are matched to their committees, 453 in all,
  with 315,090 receipts since 2015: $394 million from named organizations
  and $82 million from people, as totals. Outside groups spent $123 million
  to support sitting members and $34 million to oppose them; that money is
  shown apart, because the campaigns never received it.
- A legislator's committees are found two ways that check each other: the
  cover page of every campaign statement names the candidate, office and
  district, and the Secretary's own candidate records tie every committee a
  person controls to one record, whatever the committee is called (and
  however the Secretary spelled the name). Only the committees for the
  Assembly or Senate seat count, and only their statements whose own cover
  page names that seat: candidate committees, officeholder accounts and
  legal defense funds. A legislator's ballot measure committee (75 found), a
  general purpose committee (1) and a committee for another office (57, from
  Insurance Commissioner to a city council, including a namesake's account
  the Secretary had filed under the same record) are left out, and the
  run lists every one so they can be read.
- California lets businesses, unions, tribes and associations give to
  candidates directly, within limits, and Cal-Access files them all under one
  code, so they are named as the campaign reported them and labelled other
  organizations: $114 million, led by the Pechanga Band of Indians, the Yocha
  Dehe Wintun Nation, the Barona Band of Mission Indians, Sempra Energy and
  Anheuser-Busch. The parties fund legislative campaigns here too: the
  California Democratic Party gave sitting members $39 million and the
  California Republican Party $14 million.
- Campaigns do not always use the file's codes as meant, so names are read
  too. A giver filed as a business or a committee whose name reads like a
  person's, a person doing business under a name, a professional with a
  credential, a family or living trust, an estate, a person "and affiliated
  entities" or a major donor registered under a person's name is counted with
  people and never named (605 rows, $0.75 million); a contact person's name
  written after a business's name is cut off before the name is kept (about
  1,200 such names). A business named after its owner may be hidden this way;
  a person is never shown. Outside spenders filing on their own as major
  donors are named only when their names show them to be organizations.
- Money is counted once. A transfer between committees, which Cal-Access
  attributes to the original givers, is recorded as coming from the committee
  the money left, so money a member moved between their own committees shows
  as "moved in" rather than as fresh gifts (14,971 transfers); a statement
  filed twice under two filing numbers counts once (124 found); a loan from
  the member's own committee is that committee's money, not a loan; a
  forgiven loan is not counted again as a gift; an amended statement replaces
  the original (222,975 rows on superseded statements were set aside).
- What the record leaves out, and says so: gifts under $100 arrive as one
  sum per statement (counted as other receipts), and late-contribution
  reports are skipped because the same gifts appear on the next statement.
- Also fixed: the state list carried a second, empty money setting after
  Colorado's, Texas's and Washington's, so the runner's money stage and
  report for those states said no loader existed even though their money
  was loaded; the check stage's warning about named givers now knows the
  business, union and organization kinds; a new kind, "Not named here",
  pools outside spenders a file cannot tell from people.

## v4.0.038 — 2026-09-24 — Texas's campaign money

- Texas is the fifth state with its campaign money loaded, from the Texas
  Ethics Commission's bulk download of every electronically filed report
  since 2000 (one 1 GB file, 35.6 million contribution rows, read in eight
  minutes). All 179 sitting legislators are matched to their accounts:
  $279 million from named organizations since 2015 and $166 million from
  people, as totals. Texas has no contribution limits, and the file shows
  it: one committee, Texans for Lawsuit Reform PAC, gave sitting members
  about $30 million.
- The Commission's own filer index does the identifying. An account is
  matched by family name, a compatible given name and the office it sought
  or held; where the Commission's formal name does not fit the roster's
  (Roberto D. Guerra for Bobby Guerra, Eugene Y. Wu for Gene Wu), the
  Commission's own record of the seat the account holds settles it, and the
  run lists all eighteen such cases. A giver's kind comes from the same
  index: a registered committee is what it is registered as, whatever a
  campaign called it. Texas bars corporate and union gifts, so the rest of
  the named organizations are partnerships, law firms and associations.
- No outside spending is shown for Texas: the Commission's bulk file lists
  a committee's spending for a candidate on the same schedule as the gifts
  it made, with no flag to tell them apart and none for support or
  opposition. The money card says so.
- Reports superseded by a later filing (117,079 rows) are skipped in favour
  of the later one. Six committees were treated as a member's own earlier
  committee, all city council or mayoral accounts passed on to the
  legislative one.

## v4.0.037 — 2026-09-24 — Colorado's campaign money

- Colorado is the fourth state with its campaign money loaded, from the
  Secretary of State's TRACER bulk downloads: one contributions file a year,
  2015 through 2026 (2.5 million rows, of which 907,055 went to statewide
  candidate committees). All 100 sitting legislators are matched to 156
  committees: $12.4 million from named organizations (the Colorado
  Democratic Party first, then the small donor committees of firefighters,
  doctors, realtors and teachers) and $12.9 million from people, as totals.
- Colorado's files name no office for a candidate, so a campaign is matched
  only when it is a statewide-jurisdiction candidate committee whose name
  carries no other office and whose candidate's full name fits exactly one
  sitting legislator. Where the state's spelling of a name does not fit
  (Julia for Julie, Merrick for Rick), the committee's own name is read: the
  name the member goes by before "for", or the seat it names ("Taggart for
  House District 55"), and still only one member may fit. Every such match
  is listed by the run. Superseded records are skipped in favour of their
  amendments; returned and bounced gifts are left out.
- Colorado's bulk expenditure files do not say which candidate an
  independent spender supported or opposed, so no outside spending is shown
  for Colorado, and the money card says so rather than showing zero.
- Seventeen committees were treated as a member's own earlier committee
  ("moved in", not a donor): House accounts passed to Senate ones, and
  balances rolled over after redistricting, each listed by name in the run.
- Oregon has no bulk dataset (its ORESTAR system offers only search
  exports), so it is set aside for now; Texas is next.

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
