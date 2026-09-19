-- Congress catalog + ratings schema for Postgres (Supabase, Neon, RDS, or a local Postgres).
-- Mirrors the SQLite schema that congress_catalog.py --db writes.
--
-- Fastest way to fill it: build the SQLite file locally, then copy it over with pgloader
--   pgloader ./congress_119.sqlite postgresql://USER:PASSWORD@HOST:5432/DBNAME
-- (pgloader creates the tables itself; run this file afterwards for the views, indexes and
--  constraints, or run it first and add `WITH data only` to the pgloader command.)
--
-- Facts tables are rebuilt from the official Bill Status feed on every run.
-- ratings and rating_runs are never rebuilt: they are the judgment layer and keep their history.

BEGIN;

CREATE TABLE IF NOT EXISTS bills (
  bill_key            text PRIMARY KEY,          -- e.g. hr1-119
  congress            integer NOT NULL,
  bill_type           text NOT NULL,             -- hr, s, hjres, sjres, hconres, sconres, hres, sres
  number              integer NOT NULL,
  display_id          text NOT NULL,             -- H.R. 1
  kind                text,                      -- Bill / Joint resolution / ...
  title               text,
  short_title         text,
  introduced_date     date,
  origin_chamber      text,
  sponsor_bioguide    text,
  policy_area         text,
  committees_referred text,
  committee_path      text,
  committee_votes     text,
  house_floor_summary text,
  senate_floor_summary text,
  passed_house        boolean DEFAULT false,
  passed_senate       boolean DEFAULT false,
  status              text,
  outcome             text,
  law_kind            text,                      -- Public / Private
  law_number          text,                      -- 119-21
  latest_action_date  date,
  latest_action       text,
  lens_flags          text,
  related_enacted     text,
  identical_bills     text,
  cosponsors_active   integer,
  original_cosponsors integer,
  cosponsors_by_party text,
  bipartisan          boolean,
  congress_url        text,
  text_url            text,
  latest_text_version text,
  latest_text_pdf     text,
  actions_url         text,
  cosponsors_url      text,
  committees_url      text,
  source_update       timestamptz,               -- updateDate in the source XML
  loaded_at           timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS members (
  bioguide_id text PRIMARY KEY,
  full_name   text, first_name text, last_name text,
  party       text, state text, district text, chamber text,
  updated_at  timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sponsorships (
  bill_key      text REFERENCES bills(bill_key) ON DELETE CASCADE,
  bioguide_id   text REFERENCES members(bioguide_id),
  role          text NOT NULL,                   -- sponsor / cosponsor
  date_joined   date,
  is_original   boolean,
  withdrawn_date date,
  PRIMARY KEY (bill_key, bioguide_id, role)
);

CREATE TABLE IF NOT EXISTS committee_actions (
  id          bigserial PRIMARY KEY,
  bill_key    text REFERENCES bills(bill_key) ON DELETE CASCADE,
  chamber     text, committee text, action_date date, activity text,
  vote_method text, yeas integer, nays integer, action_text text
);

CREATE TABLE IF NOT EXISTS floor_votes (
  vote_id      text PRIMARY KEY,                 -- bill_key|H|date|roll
  bill_key     text REFERENCES bills(bill_key) ON DELETE CASCADE,
  chamber      text, vote_date date, category text, key_vote boolean,
  result       text, method text, yeas integer, nays integer, present integer, roll_number integer,
  action_text  text, roll_call_url text, roll_call_xml text, party_split text
);

CREATE TABLE IF NOT EXISTS member_votes (
  vote_id     text REFERENCES floor_votes(vote_id) ON DELETE CASCADE,
  member_key  text NOT NULL,                     -- Bioguide ID (House) or LIS member id (Senate)
  member_name text, party text, state text, position text,   -- Yea / Nay / Present / Not Voting
  PRIMARY KEY (vote_id, member_key)
);

CREATE TABLE IF NOT EXISTS related_bills (
  bill_key        text REFERENCES bills(bill_key) ON DELETE CASCADE,
  related_display text, relationship text, related_law text,
  PRIMARY KEY (bill_key, related_display, relationship)
);

CREATE TABLE IF NOT EXISTS subjects (
  bill_key text REFERENCES bills(bill_key) ON DELETE CASCADE,
  subject  text,
  PRIMARY KEY (bill_key, subject)
);

CREATE TABLE IF NOT EXISTS summaries (                  -- CRS plain-language summaries, every version
  bill_key     text REFERENCES bills(bill_key) ON DELETE CASCADE,
  version_code text, action_date date, action_desc text,
  text_html    text, text_plain text,
  PRIMARY KEY (bill_key, version_code, action_date)
);

CREATE TABLE IF NOT EXISTS text_versions (
  bill_key text REFERENCES bills(bill_key) ON DELETE CASCADE,
  version_date date, version_type text, url text,
  PRIMARY KEY (bill_key, version_type, version_date)
);

CREATE TABLE IF NOT EXISTS cbo_estimates (
  bill_key text REFERENCES bills(bill_key) ON DELETE CASCADE,
  pub_date date, title text, url text, description text,
  PRIMARY KEY (bill_key, url)
);

CREATE TABLE IF NOT EXISTS committee_reports (
  bill_key text REFERENCES bills(bill_key) ON DELETE CASCADE,
  citation text,
  PRIMARY KEY (bill_key, citation)
);


CREATE TABLE IF NOT EXISTS legislators (                -- from load_legislators.py (official roster)
  bioguide_id      text PRIMARY KEY,
  lis_id           text,                               -- Senate roll-call member id
  govtrack_id      integer,
  first_name       text, last_name text, official_full text,
  birthday         date, gender text,
  party            text, party_name text, state text, district integer, chamber text, senate_class integer,
  is_current       boolean, term_start date, term_end date, first_term_start date, terms_count integer,
  url              text, contact_form text, phone text, office text, wikipedia text,
  updated_at       timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_legislators_lis   ON legislators (lis_id);
CREATE INDEX IF NOT EXISTS ix_legislators_state ON legislators (state, chamber);

-- What the vote map reads: every member's vote on a roll call, with the roster joined in.
CREATE OR REPLACE VIEW vote_map AS
SELECT fv.vote_id, fv.bill_key, fv.chamber, fv.vote_date, fv.category, fv.result, fv.yeas, fv.nays,
       mv.member_key AS bioguide_id, COALESCE(mv.party, l.party) AS party, COALESCE(NULLIF(mv.state, ''), l.state) AS state,
       l.district, l.official_full, mv.position, l.birthday, l.first_term_start, l.url, l.phone
FROM member_votes mv
JOIN floor_votes fv ON fv.vote_id = mv.vote_id
LEFT JOIN legislators l ON l.bioguide_id = mv.member_key;

-- ------------------------------------------------------------------ judgment layer
CREATE TABLE IF NOT EXISTS rating_runs (
  run_id         text PRIMARY KEY,
  method_version text NOT NULL,                 -- rubric version, e.g. v1.0
  model          text,                          -- claude-sonnet-5, human, ...
  rater          text,
  started_at     timestamptz, finished_at timestamptz,
  scope          text, notes text
);

CREATE TABLE IF NOT EXISTS ratings (
  rating_id       bigserial PRIMARY KEY,
  bill_key        text NOT NULL REFERENCES bills(bill_key),
  axis            text NOT NULL,                -- income | backing | households_business | timing | rights | plain_language
  method_version  text NOT NULL,
  run_id          text REFERENCES rating_runs(run_id),
  rater           text,
  rated_at        timestamptz DEFAULT now(),
  position        double precision,             -- -100..100 (see rubric for each axis)
  position_low    double precision,             -- range for mixed bills
  position_high   double precision,
  position2       double precision,             -- second dimension (business side of the quadrant)
  position2_low   double precision,
  position2_high  double precision,
  magnitude_label text,                         -- none | small | moderate | large | major
  magnitude_note  text,                         -- "$4.5T over 10 years", "~70M SNAP/Medicaid enrollees"
  evidence_grade  text,                         -- A | B | C | N
  confidence      double precision,             -- 0..1
  justification   text,
  sources_json    jsonb,
  flags_json      jsonb,
  plain_json      jsonb,
  input_hash      text,                         -- sha256 of the blinded input the rater saw
  superseded_by   bigint,
  is_current      boolean NOT NULL DEFAULT true,
  CONSTRAINT ratings_axis_chk CHECK (axis IN ('income','backing','households_business','timing','rights','plain_language')),
  CONSTRAINT ratings_grade_chk CHECK (evidence_grade IN ('A','B','C','N') OR evidence_grade IS NULL)
);

CREATE INDEX IF NOT EXISTS ix_ratings_bill      ON ratings (bill_key, axis) WHERE is_current;
CREATE INDEX IF NOT EXISTS ix_bills_outcome     ON bills (outcome);
CREATE INDEX IF NOT EXISTS ix_bills_policy      ON bills (policy_area);
CREATE INDEX IF NOT EXISTS ix_bills_introduced  ON bills (introduced_date);
CREATE INDEX IF NOT EXISTS ix_sponsorships_mem  ON sponsorships (bioguide_id);
CREATE INDEX IF NOT EXISTS ix_member_votes_mem  ON member_votes (member_key);
CREATE INDEX IF NOT EXISTS ix_summaries_fts     ON summaries USING gin (to_tsvector('english', coalesce(text_plain, '')));
CREATE INDEX IF NOT EXISTS ix_bills_title_fts   ON bills USING gin (to_tsvector('english', coalesce(title, '')));

-- One row per bill with the current rating on every axis: what a bill page reads.
CREATE OR REPLACE VIEW bill_cards AS
SELECT b.bill_key, b.display_id, b.title, b.outcome, b.status, b.law_number, b.policy_area,
       b.introduced_date, b.latest_action_date, b.congress_url, b.text_url,
       MAX(r.position)        FILTER (WHERE r.axis = 'income')              AS income_position,
       MAX(r.position_low)    FILTER (WHERE r.axis = 'income')              AS income_low,
       MAX(r.position_high)   FILTER (WHERE r.axis = 'income')              AS income_high,
       MAX(r.evidence_grade)  FILTER (WHERE r.axis = 'income')              AS income_grade,
       MAX(r.magnitude_label) FILTER (WHERE r.axis = 'income')              AS income_magnitude,
       MAX(r.position)        FILTER (WHERE r.axis = 'backing')             AS backing_position,
       MAX(r.position)        FILTER (WHERE r.axis = 'households_business') AS households_position,
       MAX(r.position2)       FILTER (WHERE r.axis = 'households_business') AS business_position,
       MAX(r.evidence_grade)  FILTER (WHERE r.axis = 'households_business') AS hb_grade,
       MAX(r.plain_json::text)FILTER (WHERE r.axis = 'plain_language')      AS plain_json,
       MAX(r.plain_json::text)FILTER (WHERE r.axis = 'timing')              AS timing_json,
       MAX(r.flags_json::text)FILTER (WHERE r.axis = 'rights')              AS rights_flags
FROM bills b
LEFT JOIN ratings r ON r.bill_key = b.bill_key AND r.is_current
GROUP BY b.bill_key;

-- "How did my representative vote": every key vote by member, with the bill attached.
CREATE OR REPLACE VIEW member_key_votes AS
SELECT mv.member_key, mv.member_name, mv.party, mv.state, fv.chamber, fv.vote_date, fv.category,
       fv.result, mv.position, b.bill_key, b.display_id, b.title, b.outcome
FROM member_votes mv
JOIN floor_votes fv ON fv.vote_id = mv.vote_id AND fv.key_vote
JOIN bills b ON b.bill_key = fv.bill_key;

-- Public read access pattern for Supabase: enable RLS and allow SELECT to anon on the fact tables
-- and on ratings; keep INSERT/UPDATE on ratings for the service role only.
-- ALTER TABLE bills ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY public_read ON bills FOR SELECT USING (true);
-- (repeat for the other tables)

COMMIT;
