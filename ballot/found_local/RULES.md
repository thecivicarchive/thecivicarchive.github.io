# Rules for researching and verifying state and local candidates (binding on every agent)

Project: C:\Users\16516\plain-congress (The Civic Archive). Python: `.venv\Scripts\python.exe`, run from the project
folder. No git. Never pipe a build or load through PowerShell's `Select-Object -First`. Patch files with the Edit tool.
Fetch only with the kit's honest User-Agent (`states/net.py`; WebSearch and WebFetch for reading). Never solve or work
around a CAPTCHA, bot wall, login or paywall (the Minnesota Secretary of State's own sites show this machine a
CAPTCHA: never request them). Do not use the Browser pane. Never write the real databases.

## John's order (2026-10-01)

Finish Minnesota's state and local ballot pages before any other state. For statewide offices, the Legislature,
judges, county offices, mayors and city councils, and school boards the pages may now show a campaign website, a
photo, a birth year, public offices held and issue headings, each with its source. Township and small district boards
show only what they filed, plus a campaign website if they listed one.

**Still never, for anyone:** home or mailing addresses, phone numbers, e-mail, family, marital status, religion,
health, ethnicity, income, employers, schools, legal troubles, or any description of a person's views or character;
never social media profiles as a source, people-search sites, data brokers or voter files. No hacking, no social
engineering, no contacting anyone, no forms.

**Political lean is shown only as the record:** a party's own published endorsement, an earlier run or office under a
party label, the candidate's own words on their own campaign site, and how a place voted in past elections from
official results. Nobody's politics is ever guessed or labelled by us.

## What a finding is

Each finding carries the exact page that states it and a kind: `official` (a government's own page), `campaign` (the
candidate's own campaign site), `party` (a party's own page), `secondary` (Wikipedia with a citation, or a named news
organization).

- `website`: the campaign's OWN site for this 2026 race (the site names the candidate and the office or place). A
  candidate's page on a party's site, a directory, a news site or a social profile is NOT their campaign website: leave
  `website` out and, if the party's page endorses them, record that under `endorsed_by` instead. A verifier deletes a
  `website` that sits on a party's domain.
- `official_page`: for someone holding office today, the government's own page about them.
- `born`: the year only (a full date only from an official or campaign page).
- `offices`: public offices held (elected or appointed government posts), with years and body. Not jobs, not party posts.
- `endorsed_by`: a party's OWN published endorsement for this 2026 race: `{"party", "unit", "url"}`.
- `past_party`: an earlier run or office under a party label: `{"what", "year", "party", "source", "url", "kind"}`.
- `own_words`: an explicit party or endorsement statement on the candidate's own site, quoted in at most twelve words, with the url.
- `review`: something our record shows that an official source contradicts.

**The same person.** Names repeat. A finding counts only when the source ties the person to this race by two anchors
(the state, the office or place sought in 2026, an office our record shows). Unsure means left out. A blank is fine;
a wrong fact about a real person is not.

## The files

Scope: `ballot/found_local/mn_scope.json` (a sorted list of `{"race_id", "name", "level", "office", "jurisdiction"}`).
Part k of n is the entries whose position in that list (from 0), modulo n, equals k. The record so far is in
`ballot_local_2026.sqlite` (open it read-only: `sqlite3.connect("file:ballot_local_2026.sqlite?mode=ro", uri=True)`;
tables `sl_races`, `sl_candidates`). A sitting legislator has `state_member_id` and a record page already: for them
only a website, endorsements and review items matter.

A researcher writes ONE file, `ballot/found_local/MN-<k>.json`:

    {"part": k, "of": n, "researched": "<today>", "candidates": [
      {"race_id": "...", "name": "<exactly as in our list>",
       "website": {"url", "how"}, "official_page": {"url", "source"},
       "born": {"year", "date", "source", "url", "kind"},
       "offices": [{"office", "from", "to", "source", "url", "kind"}],
       "endorsed_by": [{"party", "unit", "url"}],
       "past_party": [{"what", "year", "party", "source", "url", "kind"}],
       "own_words": {"quote", "url"},
       "review": [{"shows", "problem", "url"}]}]}

with only the keys something was found for. About six web requests a candidate is plenty.

A verifier re-opens every url in that file and checks: the page states the fact as recorded; it is the same person
(two anchors); the kind is labelled truthfully (an endorsement counts only on the party's own page); a secondary date
is cut to the year; an `own_words` quote is on the candidate's own site and at most twelve words; nothing from the
never-collected list is in any field. The verifier rewrites the same file: `"verified": true` on each confirmed
finding, corrected wording where the page differs slightly, and DELETES what it cannot confirm after two tries or what
sits behind a wall; it adds top-level `"verified_on"` and `"removed"`.
