# Election Night: news and social sources (scout report)

Checked 2026-10-09 (evening, Central time). Research only: nothing in the kit was changed. Every request used the kit's
honest User-Agent (`congress-catalog/1.0 (personal legislative research; thecivicarchive.github.io)`), one at a time,
1.2 to 1.6 seconds apart, at most three per site; no CAPTCHA, bot wall, login or paywall was touched; no Minnesota
Secretary of State host was requested. The machine-readable twin is `feeds.json` (every feed address, tested status,
item count, and the refusals).

John's rule, which shapes everything below: open sources only (GDELT, outlets' public RSS headlines with links,
Bluesky's open feed, Mastodon, YouTube). Posts are **shown** only from news organizations, election offices and
candidates' official accounts. Everyone else is **counted**, never shown or named. No paid X API.

## What works, in one paragraph

GDELT's raw 15-minute files (free, no key) give every article it sees with its headline, outlet, themes and places,
and are the backbone of the news side. 145 RSS feeds answered, at least one for every state and DC, plus 24 national
ones. Bluesky's Jetstream (a free, keyless live stream of every public post) worked with nothing but Python's own
library and is how social mentions are counted without storing who posted. Mastodon's public hashtag timelines answer
without a login on seven large instances. YouTube offers keyless RSS for any channel whose ID we know; its search needs
a key and allows only 100 searches a day, so it is not part of the plan.

## What does not work

- **GDELT's DOC 2.0 search API** refused this machine: seven of nine requests answered 429 ("limit requests to one
  every 5 seconds") even 45 seconds apart, and the two that answered returned an empty result. The raw files carry the
  same articles, so the plan does not need it.
- **AP and Reuters** publish no public RSS (403, 404). Their stories reach us through member outlets and GDELT.
- **Big newspaper chains**: every Gannett paper tried answered 403 (Des Moines Register, Detroit Free Press, Milwaukee
  Journal Sentinel, IndyStar, Tennessean and others); McClatchy papers hung (a bot wall); Hearst papers have no feed;
  Tribune and MediaNews papers (Denver Post, Baltimore Sun, Chicago Tribune, Pioneer Press) answer 403. The Star
  Tribune answered a single request with 429. MinnPost and Sahan Journal answered 403. These are walls, so they stay
  out; GDELT still sees their stories.
- **Bluesky post search** on its public host answers 403. Counting comes from Jetstream instead.
- **mstdn.social** and some other Mastodon instances require a login for tag timelines.

## GDELT

- **Raw files**: `http://data.gdeltproject.org/gdeltv2/lastupdate.txt` lists the newest three zips every 15 minutes.
  The GKG zip of 03:15 UTC on 10 October was 2.6 MB and held 571 articles from 155 sources; 73 carried the ELECTION
  theme and 40 of those a US place. Every row carried its headline (`<PAGE_TITLE>` in the Extras column). A whole
  election night (18:00 to 06:00) is about 48 files, 125 MB.
- **Placing an article**: column V2Locations gives type (2 = US state, 3 = US city), ADM1 (`USMN`), ADM2 (`NY067` =
  state + county FIPS) and, for US cities, a GNIS feature id that the Census place files carry. **Caution, seen in the
  test file**: an Enumclaw, Washington paper's story about Washington State voters was placed at the White House.
  GDELT's city places are medium confidence and are checked against the outlet's home state.
- **DOC API** (for reference; not answering here): `https://api.gdeltproject.org/api/v2/doc/doc`, modes `artlist`
  (up to 250 articles), `timelinevolraw` (counts per 15 minutes), operators `sourcecountry:US`, `domain:`,
  `theme:ELECTION`, `near:`. Tested-form example for a Minnesota governor search:
  `?query=%22Minnesota%22%20(governor%20OR%20gubernatorial)%20election%20sourcecountry:US&mode=artlist&maxrecords=250&format=json&timespan=24h&sort=datedesc`.
- **Terms**: free for any use; any use or redistribution must cite the GDELT Project and link to
  https://www.gdeltproject.org/ (its About page, Terms of Use). The page footer needs that credit.

## News RSS

Found from each outlet's own home page links, then from the publishing system's usual pattern: WordPress `/feed/`
(all States Newsroom capitol bureaus), NPR station sites on Grove `<section>.rss` (their `index.rss` answers with no
items: use `politics.rss` or `news.rss`), Arc `/arc/outboundfeeds/rss/?outputType=xml` (Boston Globe, Inquirer, Tampa
Bay Times, OPB, Anchorage Daily News, Salt Lake Tribune, KTTC, WCAX), BLOX `/search/?f=rss&t=article&l=50&s=start_time&sd=desc`
(St. Louis Post-Dispatch, Omaha, Richmond, Casper, NOLA, Charleston Gazette-Mail, Mankato, WDEL). The Texas Tribune's
site refuses scripts but its `feeds.texastribune.org` host answers.

**Reuse**: show the headline, the outlet, the time and a link. Never the summary or the article, even where the feed
carries the whole text (most WordPress feeds do; `feed_carries_full_text` marks them). States Newsroom licenses
republication (CC BY-ND 4.0), but we link rather than copy, the same as everyone else.

**Minnesota** (first, so more than one per kind): Minnesota Reformer, MPR News (`/feed/homepage`), KARE 11, WCCO
(CBS Minnesota), FOX 9, KSTP, Duluth News Tribune, KTTC (Rochester), Mankato Free Press, InForum (Fargo-Moorhead).
Missing: Star Tribune (429), MinnPost and Sahan Journal (403), Pioneer Press (403).

Thinnest states (one feed): CT, DC, GA, ID, IL, IN, MS, OK, RI. GDELT covers what their walled papers publish.


## Bluesky

- **Jetstream**: `wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post` (also
  jetstream1.us-east and the two us-west hosts). Tested for 30 seconds with Python's own library, no package
  installed: 891 new posts (about 30 a second), 0.03 MB a second; at that hour 3 posts said "election" and 5 "vote".
  `wantedDids=` narrows a second connection to the official accounts; `cursor=<time_us>` resumes after a drop.
  Jetstream v2 is replacing v1 at the same addresses with the same JSON (its GitHub docs, read 2026-10-09).
- **Counting without knowing who**: each post's text is matched in memory against each race's names and words; a
  per-race, per-minute counter goes up by one. For "distinct people" the account id is run through a keyed hash whose
  key is made at start and never written; the set lives for one hour, then only its size is kept. No account id,
  handle, text or post id of an ordinary user is ever written to disk or a log.
- **Duties** (Bluesky Developer Guidelines, now at bsky.network/docs/developer-guidelines, read 2026-10-09): honor
  deletions ("All services must have a method for deleting content a user has requested to be deleted"), so a shown
  official post is removed on its delete event and an account that goes inactive is hidden; offer a way to report
  content; keep a public contact address that someone reads; keep data secure. The site has no e-mail contact yet
  (an open question on the Access page), so John must choose one before shown posts go live.
- **Recognising official accounts**: the handle is the organization's own domain (mprnews.org, startribune.com,
  npr.org, apnews.com all are), or the organization's own website links to the profile and the profile names it.
  Bluesky's blue check is a supporting sign only: a search for "Secretary of State" turned up verified UK MPs and one
  US election office (Oregon), and no `.gov` handle; sos.mn.gov is not a Bluesky handle.
- Rate limits for the public read host are "generous" (bsky.network/docs/rate-limits); it is the host Bluesky asks
  public sites to use.

## Mastodon

`GET https://<instance>/api/v1/timelines/tag/<tag>?limit=40&since_id=<id>`, no login, on mastodon.social,
mastodon.online, mastodon.world, mas.to, universeodon.com, journa.host (journalists) and newsie.social. Each answers
with `x-ratelimit-limit: 300` per 5 minutes. Planned load: about 14 requests a minute across all seven. The same
post arrives on several instances: dedupe by its `uri`. Count only accounts that are `indexable` or `discoverable`,
not `bot`, and without #nobot in their profile; store none. mastodon.social's terms (effective 2026-08-31) say public
content may be read by "RSS aggregators and readers" and indexed. An official account is one whose profile field
linking the organization's own domain carries `verified_at` (Mastodon's two-way link check).

## YouTube

- Keyless: `https://www.youtube.com/feeds/videos.xml?channel_id=<UC...>` gives a channel's 15 newest uploads (tested:
  200, 15 entries). That covers official channels whose ID we hold: 317 sitting members' channels in
  `member_social` (congress-legislators roster), and channels linked from campaign and election office sites.
- The Data API's search answered 403 without a key. With John's free key it allows only 100 searches a day (plus
  10,000 units for cheap calls), too few for election night. If he ever wants it, the kit's pattern applies: a
  `Save YouTube key.bat` that takes the key in a hidden window and writes `youtube_key.txt` (ignored by git), never
  asked for in chat, never read by Claude. **The plan does not need it.**

## Official accounts: building the list without guessing

Sources already in the kit: 844 candidate websites in `ballot_2026.sqlite` (`websites`, plus `people.website`),
2,376 in `ballot_local_2026.sqlite` (`sl_websites`, 861 in Minnesota, 795 of them filed with the Secretary of State),
and 193 official election-office hosts in the `url` columns of `ballot_sources` and `sl_sources`. Fetch each site
once, politely, read only its links to Bluesky, Mastodon and YouTube profiles, and accept an account with two
anchors: the site links to it, and it points back (Bluesky handle is the site's domain or names it; Mastodon
`verified_at`; YouTube channel's own link). Store the account, the linking page and the date.

A sample of 24 campaign sites (12 Minnesota local, 12 federal): Facebook 20, Instagram 15, X 10, YouTube 4,
Bluesky 3, Mastodon 3, Threads 1. **Most candidates post where we will not read** (X, Facebook, Instagram), so the
shown stream will mostly be newsrooms and election offices. The page should say that plainly.

## The leaderboard measures

All over a rolling 60 minutes on election night (24 hours before), recomputed every 5 minutes. News items and social
mentions are separate numbers.

**Counting rules (against one viral item or one big outlet).** One story = one canonical address; wire copy counts once
per outlet; at most 3 items per outlet per race per window; social counts are distinct people, once per race per
hour, reposts not read.

1. **Coverage per 100,000 residents** (John's leveler).
   `raw = 100000 × N ÷ pop`; shown: `100000 × (N + R_level) ÷ (pop + 100000)`.
   N = capped news items; pop = residents of the race's area from ACS 2020-2024 table B01003, already cached in
   `states_cache/acs2024/` at every level we need (state 52 rows, congressional 440, state senate 1,964, state house
   4,879, county 3,222, county subdivision 36,421, place 32,330, school districts 13,380); a district spanning counties
   adds them. R_level = the average rate of races at the same level. The shrinkage (worth 100,000 residents) stops a
   5,000-person school board with two stories from scoring 40 and topping the board; the raw figure is shown beside
   it. Ranked only with 3 or more items from 2 or more outlets, and on a board per level (statewide, Congress,
   legislature, county, city and school), never all together.
2. **Attention gap** (coverage against closeness).
   `gap = rank%(closeness) − rank%(coverage per 100k)` within the level, from −100 to +100; closeness = 1 − |margin|.
   Margin is live (leader minus runner-up over their combined votes) once 20% of the expected vote is counted, before
   that the predictions section's median margin; neither, not ranked. Positive = closer than its coverage suggests.
   Zero-coverage close races are included, which is the point. Retention and unopposed races are left out; the margin's
   source is printed beside the figure.
3. **Momentum** (last hour against the hour before).
   `(c_last + 1) ÷ (c_prev + 1)`, c = news items + distinct social people. Ranked only with 10 or more in the two
   hours; called "rising" only when c_last is above the 95% Poisson upper bound of c_prev (3 to 6 is noise, 30 to 60
   is not).
4. **Source breadth** (distinct outlets).
   Distinct outlets (registered domain) in 24 hours, and the effective number `exp(−Σ p·ln p)` over each outlet's share
   of the items: 10 stories with 8 from one paper is 3 distinct but about 1.9 effective. Ranked with 3 or more items.

A national outlet counts like any other, and a Senate race is ranked only against other statewide races, so a big
market does not win by being big.

## Geotagging an item (with its confidence)

1. **High**: the headline names a candidate on a race's list (full name, or family name with the office or district
   words) and the outlet's home state or the headline's state matches the race: placed on the race's area.
2. **High, or not placed**: a place name in the headline matched to `sl_places` or Census names, with a state context
   (outlet home state or a state named in the headline). Common names (Washington, Springfield, Jackson County) are
   placed only when one match fits that state.
3. **Medium**: GDELT's most-mentioned US state or city that agrees with the outlet's home state; county through ADM2,
   place through the GNIS id. Low when it disagrees (the Enumclaw example).
4. **Low**: the outlet's home market (`market` in `feeds.json`), marked "placed by where the outlet is", shown only at
   state zoom.
5. Social posts are placed only through a race or place named in their text, never from anyone's location.

## Plan for the build

1. A registry `election/feeds_registry.json` from `feeds.json`, refreshed by a polite weekly check (drop feeds that
   stop answering; never retry a 403 with a different identity).
2. On John's computer on election night, one updater loop: GDELT every 15 minutes; RSS every 5 minutes (conditional
   GET with ETag and Last-Modified); Mastodon every 3 minutes; Jetstream as two live connections (counting, and
   official accounts); YouTube channel RSS every 10 minutes. Stored: per item the headline, outlet, time, link, matched
   races and places with confidence; per race per minute the counts. Nothing about ordinary users.
3. Before Nov 3: the official accounts list (two anchors each), the race keyword sets (candidate names from the
   ballot databases, office and district words, state hashtags), and a dry run on a quiet evening to set the
   thresholds above against real volume.
4. Footer credits: GDELT Project (required), each outlet named on its own headlines, Bluesky and Mastodon as the
   sources of counts.
5. For John to decide: a public contact address for reports (Bluesky's guideline asks for one before posts are shown).

## Per-state feed list

| State | Outlets with a working feed |
| --- | --- |
| US | 24: NPR Politics, NPR News, PBS News Hour Politics, CBS News Politics, ABC News Politics, NBC News Politics, CNN Politics, Fox News Politics, New York Times Politics, Washington Post Politics, Politico, The Hill (campaigns), Axios, Bloomberg Politics, UPI Top News, CNBC Politics, Newsweek, The Guardian US Politics, BBC US and Canada, Votebeat, Stateline, Ballotpedia News, The 19th, RealClearPolitics |
| AK | 3: Alaska Beacon, Alaska Public Media, Anchorage Daily News |
| AL | 2: Alabama Reflector, Alabama Public Radio |
| AR | 2: Arkansas Advocate, Arkansas Democrat-Gazette |
| AZ | 2: Arizona Mirror, KJZZ |
| CA | 2: KQED, Los Angeles Times |
| CO | 2: Colorado Newsline, Colorado Public Radio |
| CT | 1: Connecticut Public |
| DC | 1: WAMU |
| DE | 2: Delaware Public Media, WDEL |
| FL | 3: Florida Phoenix, WUSF, Tampa Bay Times |
| GA | 1: Georgia Recorder |
| HI | 2: Honolulu Star-Advertiser, Hawaii Public Radio |
| IA | 2: Iowa Capital Dispatch, Iowa Public Radio |
| ID | 1: Idaho Capital Sun |
| IL | 1: WBEZ |
| IN | 1: Indiana Capital Chronicle |
| KS | 2: Kansas Reflector, KCUR |
| KY | 2: Kentucky Lantern, Louisville Public Media |
| LA | 3: Louisiana Illuminator, WWNO, NOLA.com |
| MA | 2: WBUR, Boston Globe |
| MD | 3: Maryland Matters, Maryland Matters, WYPR |
| ME | 4: Maine Morning Star, Portland Press Herald, Portland Press Herald, Maine Public |
| MI | 2: Michigan Advance, Michigan Public |
| MN | 9: Minnesota Reformer, MPR News, KARE 11, WCCO (CBS Minnesota), FOX 9, KSTP, Duluth News Tribune, KTTC, Mankato Free Press |
| MO | 3: Missouri Independent, St. Louis Post-Dispatch, St. Louis Public Radio |
| MS | 1: Mississippi Today |
| MT | 4: Daily Montanan, Montana Free Press, Montana Free Press, Montana Public Radio |
| NC | 2: NC Newsline, WUNC |
| ND | 3: North Dakota Monitor, InForum, Prairie Public |
| NE | 2: Nebraska Examiner, Omaha World-Herald |
| NH | 2: New Hampshire Bulletin, NHPR |
| NJ | 2: New Jersey Monitor, WHYY |
| NM | 2: Source NM, KUNM |
| NV | 4: Nevada Current, Nevada Independent, Las Vegas Review-Journal, KNPR |
| NY | 3: Gothamist, New York Focus, City and State New York |
| OH | 3: Ohio Capital Journal, Statehouse News Bureau, Ideastream |
| OK | 1: Oklahoma Voice |
| OR | 3: Oregon Capital Chronicle, Oregon Capital Chronicle, OPB |
| PA | 2: Pennsylvania Capital-Star, Philadelphia Inquirer |
| RI | 1: Rhode Island Current |
| SC | 3: SC Daily Gazette, Post and Courier, South Carolina Public Radio |
| SD | 2: South Dakota Searchlight, SDPB |
| TN | 3: Tennessee Lookout, Tennessee Lookout, WPLN |
| TX | 3: KUT, Texas Tribune, Houston Public Media |
| UT | 4: Utah News Dispatch, Salt Lake Tribune, Deseret News, KUER |
| VA | 3: Virginia Mercury, VPM, Richmond Times-Dispatch |
| VT | 2: Vermont Public, WCAX |
| WA | 2: Washington State Standard, Seattle Times |
| WI | 2: Wisconsin Examiner, WPR |
| WV | 2: West Virginia Watch, Charleston Gazette-Mail |
| WY | 2: Casper Star-Tribune, Wyoming Public Media |
