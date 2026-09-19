# Bill rating rubric — version 1.1

`method_version: v1.1` · Applies to every rating written to the `ratings` table.
Changes in v1.1: added the `blocks_agency_rule` rights flag (Congressional Review Act disapprovals were
otherwise invisible on the rights axis); no scale or threshold changed, so v1.0 ratings need no re-score beyond that flag.
Change the version number whenever any scale, threshold or definition below changes; never
re-score under an old version.

## 1. Ground rules

1. **Facts and judgments never mix.** Everything in `bills`, `floor_votes`, `sponsorships` and
   the other fact tables comes from the official record. Everything here is a judgment and lives
   only in `ratings`, tagged with its version, rater and evidence.
2. **Every rating has four parts:** a position on the axis, a magnitude (how much money or how
   many people are at stake), an evidence grade, and a justification of two to four sentences
   that cites the section, summary passage or analysis it rests on.
3. **Mixed bills get a range, not an average.** If a bill helps one group and hurts another on
   the same axis, report `position_low` and `position_high` and explain the split. Never let
   offsetting effects wash out to "neutral".
4. **"Not assessable" is a legitimate answer** (`evidence_grade: N`, position null). Use it for
   naming resolutions, commemorations, purely procedural measures, and anything where the input
   gives no basis for the axis. Do not guess.
5. **Score the enacted or latest text.** Use the most recent CRS summary version supplied. If
   the summary describes an earlier version than the current status, say so in the justification.
6. **Blind to politics.** The rater never sees sponsor names, party labels, cosponsor counts by
   party, vote tallies, or the President's name, and must not use outside knowledge of who
   backed the bill. Party backing is measured separately from the vote record (section 4).
7. **Plain words.** Justifications and plain-language fields target an 8th-grade reading level.
   No "leverage", "framework", "stakeholders", "reconciliation" (say "budget bill"), "CRA"
   (say "repeal of a rule"), "means-tested" (say "for people below an income limit").

## 2. Evidence grades

| Grade | Meaning | Typical sources |
|---|---|---|
| **A** | Official distributional or cost analysis of this bill exists and the rating follows it | JCT distribution tables, CBO cost estimate or distributional letter, CBO private-sector mandate statement |
| **B** | Independent quantitative models of this bill exist; rating reflects their range | Penn Wharton Budget Model, Tax Policy Center, Tax Foundation, Yale Budget Lab, CBPP, AEI; use models from more than one part of the spectrum and report where they disagree |
| **C** | Rating rests on a reading of the bill text or its CRS summary using the text rules below | CRS summary, enrolled text |
| **N** | Not assessable on this axis | — |

Only grades A and B may carry `confidence` above 0.7. Grade C caps at 0.6.

## 3. Axis 1 — Who gains, by income (`axis = income`)

**Scale:** −100 = benefits go overwhelmingly to lower-income households; 0 = broad-based or
proportional; +100 = benefits go overwhelmingly to high-income households. Costs are the
mirror image: a bill that cuts a program used mainly by lower-income households scores
positive (the burden falls at the bottom).

**Primary measure (grades A/B):** percent change in after-tax-and-transfer income by income
group (quintiles or deciles), the standard used by CBO and JCT. The position is the slope of
that curve:

| Pattern of percent change in income | Position |
|---|---|
| Bottom groups gain ≥ 3× the top group's percentage | −80 to −100 |
| Bottom gains clearly more than top | −40 to −79 |
| Roughly even percentage gains across groups | −15 to +15 |
| Top gains clearly more than bottom | +40 to +79 |
| Top gains ≥ 3× the bottom's percentage, or bottom loses while top gains | +80 to +100 |

**Secondary measure (report in `magnitude_note`):** share of total dollars going to the top
20%. A flat percentage cut is neutral on the primary measure but can send most dollars to the
top; say both.

**Text rules (grade C) — start at 0 and move:**

| Feature in the bill | Move |
|---|---|
| Refundable credit, EITC/CTC expansion, SSI/SNAP/Medicaid/housing benefit expansion, minimum-wage increase, overtime protection | −20 to −40 each |
| Consumer-protection rule that limits fees or interest charged mainly to lower-balance customers | −15 to −30 |
| Cut or new condition on SNAP, Medicaid, SSI, housing aid, student aid | +20 to +40 each |
| Non-refundable credit or deduction with no phase-out; SALT or mortgage-interest expansion | +15 to +30 |
| Capital-gains, dividend, estate, pass-through or corporate rate cut | +30 to +50 |
| Phase-out at high income, income cap, or refundability | pull toward 0 by 10–20 |
| Universal benefit (Social Security COLA, broad rebate) | toward 0 |

**Magnitude labels** (10-year federal budget effect, or people directly affected):
`none` < $1B · `small` $1–10B · `moderate` $10–100B · `large` $100B–1T · `major` > $1T.
Give the number you used in `magnitude_note`.

## 4. Axis 2 — Party (`axis = backing`, computed; plus a geography sub-rating)

Party benefit is not scored by the model. Two measurable things replace it.

**4a. Who backed it (`backing`, computed by `score_bills.py`, evidence grade A):**
For the final passage vote in each chamber that had a recorded vote, compute each party's
yes-rate: `r = R yeas / (R yeas + R nays)`, `d = D yeas / (D yeas + D nays)`. Independents
count with the caucus they sit with. `position = 100 × (r − d)`, averaged across chambers.
−100 = Democrats only, 0 = bipartisan, +100 = Republicans only.
Labels come from the smaller of the two yes-rates: ≥ 50% → "bipartisan"; 15–49% →
"one party plus crossover"; < 15% → "party-line". (Position says which way it leans; the
label says how much of the other party came along.)
If the vote record has tallies but no party split loaded yet, a recorded passage vote with at
least 85% in favor is scored 0 ("bipartisan", grade C): in a closely divided chamber that margin
needs most of both parties. If no recorded passage vote exists (voice vote, unanimous consent),
use cosponsors: `position = 100 × (R − D) / (R + D)` and set `magnitude_note = "cosponsor-based"`.

**4b. Where the benefits land (`flags_json.geography`, optional):** only when a source
allocates the bill's benefits by state (JCT/CBO rarely do; independent models sometimes do).
Compare the benefit share of states won by each party in the last presidential election.
Report as text, never as a score. Leave empty when no source exists.

**4c. Election-rules flag:** any bill that changes voting procedures, districting, campaign
finance or election administration gets `flags_json.election_rules = true` with a one-sentence
factual description. No prediction of who gains.

## 5. Axis 3 — Households vs. businesses (`axis = households_business`)

Two independent scores; a bill can help both.

* `position` (households): −100 = imposes costs or removes protections from households; 0 =
  no direct effect; +100 = large direct benefit to households.
* `position2` (businesses): same scale for businesses.
* `flags_json.business_tag`: `small firms` / `large corporations` / `both` / `n/a`. Small firm
  = provisions keyed to revenue, employee-count or pass-through status.

**Rules:**
* Corporate income-tax changes: assign 25% of the value to households (as workers) and 75%
  to owners of capital, the CBO/JCT convention, and say so.
* A CBO cost estimate's private-sector mandate section (UMRA) counts as a direct business cost
  at grade A.
* Regulation repeal: the regulated industry gains; households lose whatever the rule gave
  them. Score both sides.
* Lobbying disclosures (lobbying records that name the bill) show attention, not position.
  Report the top filer categories in `magnitude_note`; never treat them as endorsement.

## 6. Timing (`axis = timing`, no position)

`plain_json`:
```
{"effective": "2027-01-01 | on enactment | after agency rules",
 "phase_changes": [{"date": "2029-01-01", "what": "credit shrinks from 100% to 50%"}],
 "sunset": "2030-12-31 | none | permanent",
 "delayed_cost": "yes/no — a temporary benefit paired with a permanent cost, or the reverse",
 "plain": "One sentence: when people will actually feel this."}
```
Always fill `sunset`. A benefit that expires while a cost continues is the single most common
way a bill's real effect differs from its headline; say so in `plain`.

## 7. Your rights and who decides (`axis = rights`, no position)

`flags_json.flags` is a list drawn from this fixed vocabulary; each entry has a `flag` and a
one-sentence `plain` explanation:

| flag | Use when the bill… |
|---|---|
| `preempts_state_law` | overrides or blocks state or local laws |
| `limits_lawsuits` | caps damages, adds notice periods, shortens filing windows, or removes a right to sue |
| `expands_lawsuits` | creates a new right to sue, or lets governments sue |
| `requires_arbitration` | forces disputes into arbitration or blocks class actions |
| `delegates_to_agency` | leaves the operative rules to an agency's later regulations |
| `blocks_agency_rule` | nullifies a regulation and bars the agency from issuing a substantially similar one (Congressional Review Act), or repeals the law a rule rests on |
| `expands_detention_or_penalties` | mandatory detention, mandatory minimums, new criminal penalties |
| `expands_enforcement_power` | new inspection, surveillance, or data-collection authority |
| `shifts_costs_to_states` | moves program costs or administration to states |
| `changes_benefit_eligibility` | adds or removes conditions for a public benefit |
| `retroactive` | applies to past tax years or past conduct |
| `emergency_or_waiver_power` | gives the executive new waiver or emergency authority |

Empty list is valid. Through an employment and disability lens, watch especially for notice
requirements before accessibility suits, arbitration mandates, worker-classification rules,
and benefit work requirements.

## 8. Plain-language layer (`axis = plain_language`, no position)

`plain_json`:
```
{"one_sentence": "≤ 30 words, no jargon, what the bill does for a normal reader",
 "status_plain": "Became law | Passed the House, waiting on the Senate | Still just a proposal — most bills never get a vote | Vetoed",
 "if_you_are": {"worker": "...", "parent": "...", "retiree": "...", "small_business_owner": "...",
                "disability": "..."},
 "what_it_does_not_do": "one sentence on the most common misreading, if any"}
```
Each `if_you_are` entry is one sentence, or the words "No direct effect." Never leave one out.
About one in four U.S. adults has a disability; the `disability` entry covers the person
and their caregiver.

## 9. Output contract

The rater returns one JSON object per bill, no prose outside it:
```
{"income": {"position": -100..100 | null, "position_low": .., "position_high": ..,
            "magnitude_label": "none|small|moderate|large|major", "magnitude_note": "...",
            "evidence_grade": "A|B|C|N", "confidence": 0..1, "justification": "...",
            "sources": [{"type": "CRS summary|CBO|JCT|model|bill text", "ref": "..."}]},
 "households_business": {"position": .., "position2": .., "business_tag": "...",
            "magnitude_label": "...", "magnitude_note": "...", "evidence_grade": "...",
            "confidence": .., "justification": "...", "sources": [...]},
 "timing": {"evidence_grade": "A|C|N", "plain_json": {...}, "justification": "..."},
 "rights": {"evidence_grade": "A|C|N", "flags": [{"flag": "...", "plain": "..."}],
            "election_rules": false, "justification": "..."},
 "plain_language": {"plain_json": {...}},
 "not_assessable_reason": "only when an axis is N"}
```

## 10. Validation protocol

1. **Calibration set.** Before scoring the catalog, score the first 25 enacted laws of the
   Congress. A human reviews every axis, records agree/disagree and a corrected value, and the
   disagreement rate per axis is published with the ratings.
2. **Blinding check.** For 30 bills, score three variants: blinded (normal), blinded plus the
   line "Sponsor's party: Democratic", and blinded plus "Sponsor's party: Republican". Report the
   mean absolute shift on `income` and `households_business`. A shift above 10 points fails the
   version; fix the prompt and re-run.
3. **Known limitation.** For widely covered bills the model may recognize the bill and its
   politics from the text alone. Blinding removes the labels, not the memory. The blinding
   check measures how much that matters; the human review catches the rest.
4. **Ongoing review.** Every enacted law and every bill with a recorded floor vote gets a human
   review within 30 days of the rating. Pending bills with no floor action are model-only and
   labeled "automated rating, not yet reviewed" on the site.
5. **Re-scoring.** A bill is re-scored when its latest CRS summary version changes, when an
   official analysis (JCT/CBO) is published, or when the rubric version changes. Old ratings
   are kept with `is_current = 0` and `superseded_by` set.
