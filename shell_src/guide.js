/* The Civic Archive: the page guide (John, 2026-10-04: "can the content they are able to provide change based on
   whatever page a person is on? ... a guide/helper ... how to use the total site + the pages they are working within.
   Each companion would provide the same content.")
   One guide for the whole site. Help shows the part for the page the reader is on, worked out from the address alone
   (the folder and the part after #), and changes when that part changes. Every companion opens the same guide; with the
   companion off, Help still opens it. Nothing here is sent anywhere.
   Each entry: t (where you are), a (what the page is, one sentence), s (how to use it, a few short steps), n (where
   to go next: [label, address from the site's root]). Words are plain and short: no hype, no exclamation marks, and
   only what the page really has. Button and section names are written as the page writes them. */

const E = {
  home: {t: "The home page", a: "What the archive holds today, and the ways in.",
    s: ["Pick one of the five doors: Plain Congress, On The Ballot, Officials, Method or Access.",
        "On a phone, the same five sit in the bar at the bottom of the screen.",
        "Under Officials, choose your state and press Go to meet your legislators.",
        "Reading & access, at the top, changes text size, type, spacing, contrast and motion. It is kept on this device."],
    n: [["Plain Congress", "us/"], ["On The Ballot", "ballot/"], ["How pages are made", "method/"]]},
  method: {t: "How every page is made", a: "Where each fact comes from, how bills are rated, and what this site will not do.",
    s: ["Read where each kind of fact comes from. Every page links back to the office that keeps the record.",
        "Facts and judgments are kept apart. A rating is a judgment, and it is labelled as one.",
        "Bills are rated. People are not: no member or candidate gets a score."],
    n: [["How the ratings work", "us/#how"], ["Reading and access", "access/"]]},
  access: {t: "Reading and access", a: "Set the pages up the way you read best. Your choices stay on this device.",
    s: ["Try a preset, such as Dyslexia or Low vision. You can turn on more than one.",
        "Or change one setting at a time: text size, typeface, spacing, contrast, motion, chart colours.",
        "Put everything back returns every setting to its start.",
        "The companion can be On, Still or Off, here or in Help."],
    n: [["Home", ""]]},
  rooms: {t: "All levels: the ring of cards", a: "One card for each level of government. The card in front opens its level.",
    s: ["Turn the ring with the arrows or the dots under it.",
        "Step inside opens Congress. Choose a state opens a map of the country.",
        "County and city officials are coming soon, for every state."],
    n: [["Home", ""], ["On The Ballot", "ballot/"]]},
  rooms_states: {t: "Choose a state", a: "Every state legislature, on one map.",
    s: ["Choose a state on the map to open its legislature: its districts, its members and their committees.",
        "A state marked as still filling in is open, with more of its record on the way."],
    n: [["All levels", "rooms.html"], ["Home", ""]]},

  /* Plain Congress */
  us_home: {t: "Plain Congress", a: "Every bill and recorded vote of the 119th Congress, in plain words.",
    s: ["Start here lists bills moving right now and bills already law.",
        "How did your members vote? Choose your state, or Use my location. Your location is worked out on this device.",
        "Search, at the top, finds a bill or a member. Ctrl K opens it too (Command K on a Mac).",
        "Point at a name, or tap it, for a short card about that member."],
    n: [["Every bill", "us/#bills"], ["The vote map", "us/#map"], ["Your members", "us/#members"]]},
  us_bills: {t: "Every bill", a: "All bills and joint resolutions of this Congress, newest action first.",
    s: ["Type in Search bills to find a bill by its name, number or topic.",
        "Topic: pick one of four groups, then a topic such as Health or Taxes. Each bill's subject comes from the Library of Congress.",
        "Votes: slide to how much of a chamber voted yes on the final vote, from any share to every vote. Or pick Both parties for it, Party-line, Close, or No tally.",
        "What's new shows bills newly introduced, newly approved by a committee, or new on the floor. Coming up shows what is scheduled or ready for a vote.",
        "Filters combine. Clear these filters starts over. Open a bill to read it in plain words."],
    n: [["How the ratings work", "us/#how"], ["The vote map", "us/#map"]]},
  us_bill: {t: "One bill", a: "What this bill does, where it has been, and how each member voted on it.",
    s: ["The tabs: For you, When it hits, Your rights, Votes and path, Why this rating, Facts and links.",
        "The steps show where the bill has been. Point at a step, or tap it, for what happened that day and the vote.",
        "A rating bar is a judgment, not a fact. Point at it, or tap it, for the reasons and how sure the rating is.",
        "Share copies a link to this bill. Close returns to the list."],
    n: [["Every bill", "us/#bills"], ["How the ratings work", "us/#how"]]},
  us_map: {t: "Who voted how, state by state", a: "One recorded vote at a time, member by member, on the map.",
    s: ["Choose a recorded vote, or step through them with Newer vote and Older vote.",
        "Each state shows how its members voted. Choose a state to see each member.",
        "State map and Chamber floor, in 3D, are two views of the same vote."],
    n: [["Every bill", "us/#bills"], ["Your members", "us/#members"]]},
  us_shapes: {t: "The shape of every district", a: "Three measures of the shape of every House district. They measure; they do not judge.",
    s: ["Look at one state's districts with the State menu, or see every district.",
        "Set shoreline districts aside: a coastline makes any shape look ragged.",
        "Sources and methods shows each formula and where the lines come from.",
        "A shape alone cannot tell you why a line was drawn where it is."],
    n: [["Who lives in each district", "us/#people"], ["How pages are made", "method/"]]},
  us_people: {t: "Who lives in each district", a: "The Census Bureau's counts and estimates for every House district.",
    s: ["Shade by picks the figure that colours the map.",
        "An estimate comes with its margin of error. A small difference can be inside it.",
        "Look at one state's districts with the State menu.",
        "Sources and methods explains every figure."],
    n: [["The shape of every district", "us/#shapes"]]},
  us_how: {t: "How the ratings work", a: "How a bill is rated: who gains, who pays, and who backed it.",
    s: ["Bills are rated. People are not.",
        "Each rating shows an evidence grade, its reasons, how sure it is, and the version of the rules it was made under.",
        "Who backed it is counted from the recorded votes, party by party."],
    n: [["Every bill", "us/#bills"], ["How pages are made", "method/"]]},
  us_members: {t: "Your members", a: "Every senator and representative, with how often they vote with their party.",
    s: ["Search members, or filter by name or state.",
        "Show both chambers, the House or the Senate, and one party or all.",
        "Open a member for their service, committees, votes and money."],
    n: [["Follow the money", "us/#money"], ["The vote map", "us/#map"]]},
  us_member: {t: "One member", a: "This member's record: service, committees, votes, bills and money.",
    s: ["Get to know shows terms and office, from the record. The site does not describe anyone's views.",
        "The rest is on tabs beside the page (in a row under the links on a phone): Committees, How they vote, What they work on, Who funds the campaign, Every recorded vote and From Wikipedia. Choose one and its sheet comes out.",
        "Sheet speed, under the tabs and on the Access page, makes the change full, quick or instant. Any click, tap or key skips it. Motion off makes it instant.",
        "Votes: all of them, the times they broke with their party, and the ones they missed. Search, or open Filters to narrow by how they voted, topic, kind of vote and dates; sort, or download what you see. The address keeps your filters, so you can share them.",
        "Money shows organizations that gave, by election. Spending by outside groups is kept apart: the campaign never received it.",
        "The paragraph from Wikipedia is marked as not an official record. Share this profile copies a link."],
    n: [["Your members", "us/#members"], ["Follow the money", "us/#money"]]},
  us_money: {t: "Follow the money", a: "The organizations behind each campaign, from the Federal Election Commission.",
    s: ["See the list, or Four ways to see it.",
        "Organizations are named. People who gave appear only as totals.",
        "Outside spending is shown apart from donations: the campaign never received it."],
    n: [["Your members", "us/#members"]]},

  /* a state's legislature */
  st_home: {t: "This state's legislature", a: "Who represents you in the statehouse, and the record they keep.",
    s: ["Who represents you? Use my location, worked out on this device, or choose your Senate and House districts.",
        "Statewide offices and the two chambers are listed further down.",
        "Search, at the top, finds a legislator. Ctrl K opens it too."],
    n: [["The district map", "#map"], ["Your legislators", "#members"]]},
  st_map: {t: "Every district, and who holds it", a: "The state's districts, coloured by the party that holds each seat.",
    s: ["Jump to a district, or choose one on the map.",
        "Each district opens the legislators who hold it."],
    n: [["Your legislators", "#members"]]},
  st_shapes: {t: "The shape of every district", a: "Three measures of the shape of this state's districts. They measure; they do not judge.",
    s: ["Set shoreline districts aside: a coastline makes any shape look ragged.",
        "Sources and methods shows each formula and where the lines come from."],
    n: [["Who lives in each district", "#people"]]},
  st_people: {t: "Who lives in each district", a: "The Census Bureau's counts and estimates for this state's districts.",
    s: ["Shade by picks the figure that colours the map.",
        "An estimate comes with its margin of error. A small difference can be inside it."],
    n: [["The shape of every district", "#shapes"]]},
  st_members: {t: "Your legislators", a: "Every member of this legislature, and the statewide offices.",
    s: ["Filter by name or district.",
        "Open a legislator for their service and committees, and money where the state's records are loaded."],
    n: [["The district map", "#map"]]},
  st_member: {t: "One legislator", a: "This legislator's record: service, committees, and money where it is loaded.",
    s: ["Service and committees come from the state's roster. A year the record does not give is not filled in.",
        "Get to know is the front sheet. Committees, Who funds the campaign (where loaded) and From Wikipedia are tabs beside the page (in a row under the links on a phone); choose one and its sheet comes out.",
        "Sheet speed, under the tabs and on the Access page, makes the change full, quick or instant. Any click, tap or key skips it. Motion off makes it instant.",
        "Money names organizations only. People who gave appear only as totals.",
        "The paragraph from Wikipedia is marked as not an official record."],
    n: [["Your legislators", "#members"]]},
  st_sources: {t: "Where this comes from", a: "Every source behind this state's pages.", s: ["Each source has its address and the date it was read."],
    n: [["This state's legislature", "#home"]]},

  /* On The Ballot */
  b_door: {t: "On The Ballot", a: "Who is on the November 3 ballot, race by race, from each state's official lists.",
    s: ["Pick a card: Congress, the states' own races, or county and city races.",
        "Turn the ring with the arrows or the dots under it.",
        "The switch at the top takes you back to the record: bills, votes and legislatures."],
    n: [["Congress", "ballot/us/"], ["The states", "ballot/states/"]]},
  bu_home: {t: "Who's running for Congress", a: "Every race for the House and Senate on the November ballot.",
    s: ["Your ballot: Use my location for a preview of the Congress part of your ballot. It is worked out on this device.",
        "Every state: choose a state on the map.",
        "The Senate races, and Every race, state by state, open into lists.",
        "Forget my choices clears what this page kept on your device."],
    n: [["The states' own races", "ballot/states/"]]},
  bu_state: {t: "One state's races for Congress", a: "This state's House and Senate races, on a map and in a list.",
    s: ["Switch the map between the House districts and the Senate seat.",
        "Choose a race to open it.",
        "Where this comes from lists every source."],
    n: [["Who's running for Congress", "ballot/us/"]]},
  bu_race: {t: "One race", a: "Everyone on the official list for this seat, side by side.",
    s: ["The cards follow the official list. You can move or hide cards to compare; Put back the official order restores it.",
        "Step into the arena compares the candidates side by side.",
        "Polls and What bettors are paying are tabs, closed until you open them. Bets are not polls.",
        "Ads and the money behind them shows spending reported to the Federal Election Commission. Share this race copies a link."],
    n: [["Who's running for Congress", "ballot/us/"]]},
  bu_senate: {t: "The Senate races", a: "Every Senate seat on the November ballot.", s: ["Open a state to see its candidates, then choose the race."],
    n: [["Who's running for Congress", "ballot/us/"]]},
  bu_sources: {t: "Where this comes from", a: "Every source behind these pages.", s: ["Sources are grouped by kind. Open a group to see each one."],
    n: [["Who's running for Congress", "ballot/us/"]]},
  bs_home: {t: "Choose a state", a: "The states whose own races are loaded: governors, legislatures, courts and more.",
    s: ["Open now lists the states whose ballots are loaded.",
        "County and local races lists the states whose county and city races are loaded."],
    n: [["Congress", "ballot/us/"], ["On The Ballot", "ballot/"]]},
  bx_home: {t: "This state's ballot", a: "Every race on this state's November ballot, from the official lists.",
    s: ["Your ballot: Use my location finds your precinct on this device and shows only the races you vote in. The spot is not kept.",
        "The buttons over the map show each kind of line: counties, cities, school districts, districts and more.",
        "Show streets adds a street map from OpenStreetMap. It stays off until you ask.",
        "Level by level, and County by county, list every race."],
    n: [["Statewide offices", "#statewide"], ["The Legislature", "#legislature"]]},
  bx_list: {t: "A list of races", a: "Every race of this kind on the November ballot.",
    s: ["Choose a race to open it.",
        "A judge's retention vote is a yes-or-no question about one name."],
    n: [["This state's ballot", "#"]]},
  bx_counties: {t: "County by county", a: "The races in each county, from the county's own lists where the state has none.",
    s: ["Choose a county to see its races.",
        "Where a county's list could not be read, the page says so and why."],
    n: [["This state's ballot", "#"]]},
  bx_race: {t: "One race", a: "Everyone on the official list for this office, side by side.",
    s: ["Step into the arena compares the candidates side by side. Its sections start closed.",
        "The record, not a label: endorsements a party published, earlier runs under a party label, and how this place voted before. Nobody's politics is guessed.",
        "Polls and What bettors are paying are tabs, closed until you open them. Bets are not polls.",
        "Every fact names its source: an official page, the campaign's own site, or a news report."],
    n: [["This state's ballot", "#"]]},
  bx_sources: {t: "Sources and methods", a: "Every source behind this state's ballot page.", s: ["Sources are grouped by kind. Open a group to see each one."],
    n: [["This state's ballot", "#"]]},
  other: {t: "The Civic Archive", a: "The public record, for everyone.", s: ["The links below lead to every part of the site."], n: [["Home", ""]]}
};

/* the whole site, in the same order as the top bar */
export const AROUND = [["Home", "", "What the archive holds"], ["Plain Congress", "us/", "Every bill and recorded vote"],
  ["On The Ballot", "ballot/", "Who is on your November ballot"], ["State legislatures", "rooms.html#states", "Choose a state"],
  ["Method", "method/", "How each page is made"], ["Access", "access/", "Reading and access settings"]];

/* where the reader is: the page's folder below the site's root, and the part of the address after # */
export function where(rel, hash) {
  const h = (hash || "").replace(/^#/, ""), k = h.split("=")[0];
  rel = (rel || "").replace(/index\.html$/, "");
  if (rel === "") return "home";
  if (rel === "method/") return "method";
  if (rel === "access/") return "access";
  if (rel === "rooms.html") return k === "states" ? "rooms_states" : "rooms";
  if (rel === "us/") return ({bills: "us_bills", bill: "us_bill", map: "us_map", vote: "us_map", shapes: "us_shapes", shape: "us_shapes",
    people: "us_people", how: "us_how", members: "us_members", member: "us_member", money: "us_money"})[k] || "us_home";
  if (rel === "ballot/") return "b_door";
  if (rel === "ballot/us/") return ({state: "bu_state", race: "bu_race", senate: "bu_senate", sources: "bu_sources"})[k] || "bu_home";
  if (rel === "ballot/states/") return "bs_home";
  if (/^ballot\/[a-z]{2}\/$/.test(rel)) return ({statewide: "bx_list", legislature: "bx_list", courts: "bx_list", counties: "bx_counties",
    county: "bx_counties", race: "bx_race", sources: "bx_sources"})[k] || "bx_home";
  if (/^[a-z]{2}\/$/.test(rel)) return ({map: "st_map", shapes: "st_shapes", shape: "st_shapes", people: "st_people", members: "st_members",
    member: "st_member", sources: "st_sources"})[k] || "st_home";
  return "other";
}

export function guideFor(rel, hash) { return E[where(rel, hash)]; }

const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);

/* the guide as HTML. `root` is the way from the page to the site's root; an address that starts with # stays on the page */
export function guideHTML(g, root) {
  const href = u => u.startsWith("#") ? u : root + u;
  return `<p class="tca-g-t"><b>${esc(g.t)}</b><br>${esc(g.a)}</p>` +
    `<ol class="tca-g-s">${g.s.map(x => `<li>${esc(x)}</li>`).join("")}</ol>` +
    (g.n && g.n.length ? `<p class="tca-g-n">Next: ${g.n.map(([l, u]) => `<a href="${esc(href(u))}">${esc(l)}</a>`).join(" &middot; ")}</p>` : "");
}
