# Deriving the overall-rating and archetype-selection formula

Task 8. Target: reproduce `player_type`, `detailed` and `overall` for all 256
rows of `overall/mixed_vectors.json`, probed at PG / 75 in (bucket 11) /
198 lb / 78 in.

Harness: `tools/probe.py`. Run it to reproduce every number below.

## Result

```
pre[p] = sum_i( w[p][i] * s[i] * v[i] ) / sum_i( w[p][i] * s[i] )
raw[p] = HeightBasedOverallLerp[HEIGHT_b] applied to pre[p]

winner   = argmax_p raw[p]                       (over all 15 PLAYERTYPE slots)
detailed = min( raw[winner], DISPLAY_CAP )
overall  = floor( detailed )
```

with

- `w[p][i]` = `HeightBasedAttributeWeight[HEIGHT_b][PLAYERTYPE_p][PLAYERDATA_ATTRIBUTE_<attr>Ability]`
- `s[i]` = `AttributeRatingWeightScale[PLAYERDATA_ATTRIBUTE_<attr>Ability][v[i]]`,
  which is 1.0 for any rating below the table's floor of 75
- the lerp = `HeightBasedOverallLerp[HEIGHT_b].Value[0]` -> `.Value[1]`, i.e.
  `y0 + (x-x0)/(x1-x0)*(y1-y0)`; at bucket 11 that is `[25, 83.5] -> [25, 99]`
- `DISPLAY_CAP` = the float32 predecessor of 99, `98.99999237060547`. This is
  the one term with no tuning key behind it. See "The display cap" below.

Scores: archetype 256/256, `detailed` 256/256, `uncapped` 256/256, `overall`
256/256 on the mixed vectors; `detailed` 75/75 and `overall` 75/75 on
`overall/uniform_ratings.json`.

## The one insight

The engine reports a weighted **average**, not a weighted **sum**. The rating
scale multiplies the *weight*, and the denominator is the resulting scaled
weight sum -- not a nominal 100.

The plan's clue was that the correct pre-lerp value for sample 0 (~56.3753)
sits between the plain weighted sum (54.8881) and the fully rating-scaled sum
over 100 (59.176948). Renormalising by `sum(w*s)` is exactly the operation that
lands between them: raising `s` on a high-rated attribute pulls the average
toward that attribute instead of simply adding more to a fixed denominator.
`scaled_score(11, 14, sample0.values)` = 56.375223, matching the ~56.3753 the
plan predicted, and the lerp of that is 64.688317 against a recorded
64.688316.

## What made it findable: `overall/uniform_ratings.json`

This file was the decisive evidence and is worth reading before anything else.
It records the overall for every vector with all 21 attributes set to the same
rating, 25 through 99. Two things fall straight out.

**1. The recorded values are exactly linear in the rating, at exactly the lerp
slope.** `(98.367546 - 25.000002) / (83 - 25)` = 1.2649572, and the bucket-11
lerp slope `74/58.5` = 1.2649573. So the pre-lerp value for a uniform vector at
rating r is exactly r, across the whole range -- including r = 83, where the
rating scale is already 1.392.

That kills `sum(w*s*v)/100`: with all attributes at 83 the scales are large and
that form overshoots badly. It also kills `sum(w*v)/100`: the weights only sum
to 100 within +/- 0.06, so that form would drift by up to 0.05 at r = 83 and
the recorded line would not be straight. Only a form that renormalises by its
own denominator returns exactly r. Both `sum(w*v)/sum(w)` and
`sum(w*s*v)/sum(w*s)` do.

**2. The winning archetype wanders arbitrarily.** For uniform rows the recorded
`detailed_player_type` jumps around (0, 10, 0, 4, 0, ... 1, 5, 7, 2, 13) with no
pattern. That is what an exact 15-way tie broken by float noise looks like. Any
form that does *not* renormalise would give the 15 archetypes genuinely
different scores and a stable winner. This is independent confirmation of the
renormalisation, from the selection side.

`test_ovr.TestSelection.test_uniform_vector_ties_every_archetype` pins this.

## The ladder

Every row scored against the archetype the golden row itself declares, so
selection is held fixed while the value curve is fitted. Verbatim from
`python tools/probe.py`:

```
plain weighted sum / 100                 archetype 207/256   detailed   0/256   worst delta 14.577842 (sample 32)
rating-scaled / 100                      archetype 201/256   detailed   0/256   worst delta 53.649720 (sample 25)
plain, renormalised by sum(w)            archetype 205/256   detailed   0/256   worst delta 14.563331 (sample 32)
PG pricing mult, no rating scale         archetype 192/256   detailed   0/256   worst delta 12.594194 (sample 32)
PG pricing mult + scale, renorm          archetype 215/256   detailed   0/256   worst delta 4.108456 (sample 188)
price-cap mult + scale, renorm           archetype 231/256   detailed   0/256   worst delta 4.759825 (sample 250)
rating-scale floor 80, renorm            archetype 256/256   detailed 103/256   worst delta 0.231859 (sample 199)
rating-scale floor 85, renorm            archetype 253/256   detailed  35/256   worst delta 1.307784 (sample 171)

rating-scaled, renormalised              archetype 256/256   detailed 255/256   worst delta 0.095489 (sample 25)
  + display clamp (shipped)              archetype 256/256   detailed 256/256   worst delta 0.000025 (sample 61)
```

Hypothesis by hypothesis:

| # | Hypothesis | Archetype | `detailed` | Verdict |
|---|---|---|---|---|
| 0 | `sum(w*v)/100` (baseline) | 207/256 | 0/256 | Baseline, as documented. |
| a | `sum(w*s*v)/sum(w*s)` | **256/256** | **255/256** | **Correct.** The one miss is the clamped row. |
| b | `sum(w*s*v)/100` | 201/256 | 0/256 | Overshoots hard; worst delta 53.6. |
| b' | `sum(w*v)/sum(w)` | 205/256 | 0/256 | Renormalisation alone is not enough; the scale is real. |
| c | scale floor 70 instead of 75 | 256/256 | 255/256 | Identical to (a) -- the table has no entries below 75, so the floor is unobservable from below. Not evidence either way. |
| c | scale floor 80 | 256/256 | 103/256 | Worse. The 75-79 entries (1.01-1.05) are genuinely applied. |
| c | scale floor 85 | 253/256 | 35/256 | Much worse. Confirms the floor is the table's own, 75. |
| d | different lerp input range | not run as a sweep | -- | Not needed: the uniform file pins the lerp exactly. The recorded slope matches `74/58.5` to 7 digits and the intercept matches `(25, 25)` to 1 float32 ULP, so `[25, 83.5] -> [25, 99]` is confirmed, not assumed. |
| e | `PerPosition[POINT_GUARD].MultiplierToRelativeAttributeImportanceForPricing` folded into the weight | 215/256 (192/256 without the scale) | 0/256 | **Wrong.** Worth recording because the plan flagged it as a likely missed term. It is not part of the overall formula. The 8 multipliers it defines (StandingDunk 0.7, PassAccuracy 0.6, Speed 0.8, Agility/Strength/Vertical 0.6) are a VC-pricing knob, as the key name says; folding them in moves the archetype rate up but leaves the value curve nowhere near. |
| f | `AttributePriceCapOverMaxRatioToMultiplierLerp` as a rating-over-ceiling multiplier, using `body.ceilings(75, 198, 78)` | 231/256 | 0/256 | **Wrong**, and moot: no mixed vector has any attribute above its ceiling for the reference body (checked -- 0 of 256), so a ratio-to-ceiling term cannot be doing work here. The 231/256 is coincidence, not signal. |

### Selection needed no separate rule

Once the value curve was right, re-running argmax with it gave 256/256 with no
tiebreaker, no eligibility filter, and no use of `DataPerArchetype` minimums.
The engine picks the archetype maximising the same number it then reports.

This also sidesteps the archetype-naming dead end entirely. The
name-to-PLAYERTYPE-index mapping is still unknown and still unrecoverable from
the vendored data, but the overall formula never needs it: it works on the 15
weight slots directly. `archetypes.select` returns a PLAYERTYPE index, not a
name, and that is all the goldens record too.

`player_type` and `best_player_type` agree on all 256 rows and the same argmax
reproduces both.

## The display cap

`detailed` and `uncapped` differ on exactly one mixed row, sample 25:
`uncapped` 99.095497, `detailed` 98.999992, `overall` 98. The formula above
reproduces the 99.095497 to 1.6e-5, so the 99.0955 is genuine and something
clamps it.

`98.999992` is exactly the float32 predecessor of 99 (`98.99999237060547`).
Nothing subtler: the whole engine computation is float32, which is also why
uniform rating 25 records `25.000002` (25 plus one ULP) and the mixed rows sit
about 1e-5 off throughout.

The uniform file shows the cap's shape clearly:

| uniform rating | uncapped (this formula) | recorded `detailed` | recorded `best` | `overall` |
|---|---|---|---|---|
| 83 | 98.367521 | 98.367546 | 98.367546 | 98 |
| 84 | 99.632479 | 98.999992 | 99.0 | 98 |
| 85-98 | 100.90 - 117.34 | 98.999992 | 99.0 | 98 |
| 99 | 118.606838 | **99.0** | 99.0 | **99** |

So `best` is a plain clamp to 99.0 (as the file's own notes say), while
`detailed` is held one ULP lower -- which is precisely what makes
`floor(detailed)` display 98 rather than 99. This is the "98-to-99 completion
edge" the `official_ui_verified.json` file is named for: the builder refuses to
show 99 until the build is finished.

`overall == floor(detailed)` holds on all 256 mixed rows (not round -- rounding
mismatches 126 of them).

**What is not derived.** No tuning key carries `98.99999237`, and no ordering of
the bucket-11 lerp arithmetic produces it: `25 + (83.5-25)/58.5*74`,
`25 + 58.5*float32(74/58.5)`, and `25 + 74*float32(1/58.5)*58.5` all evaluate to
exactly 99.0 in float32. It is an engine constant, read off the goldens.

**The weakest link.** Uniform rating 99 is the *only* recorded row that reaches
a clean 99.0, so the predicate for lifting the cap rests on one observation.
`ovr._cap_for` uses `min(values) >= 99` -- every attribute at the absolute
maximum. The alternative reading, "every attribute at its body ceiling", fits
that row equally well and cannot be distinguished by any data in this dataset;
the two agree on all 331 recorded rows (checked: zero disagreements across the
256 mixed vectors and the 75 uniform rows). `min(values) >= 99` is the more
conservative choice: it is strictly harder to satisfy, so it errs toward
displaying 98, which is what the game does. If a future probe records a 99
overall for a build that is at its ceilings but below 99 raw, switch the
predicate to the ceilings test.

Note also that `official_ui_verified.json` shows a *third* routine,
"availability rounding": its two rows record 98.994194 and 99.0 while the UI
displays 98 for both. This formula reproduces the first (98.994178) and gives
98.995412 for the second, whose recorded 99.0 comes from that separate
rounding step. Out of scope for Task 8; `overall` is `floor(detailed)`, not
`floor(availability_rounded)`.

## Things checked and ruled out along the way

- No mixed vector has any attribute above its ceiling for the reference body
  (0 of 256), so ceilings play no role in these goldens.
- Per-attribute clamping (capping each `v[i]` at the lerp's upper `x1` of 83.5
  before averaging) is *wrong*, and cheaply so: sample 0 has attributes at 85
  and 87 but a recorded `detailed` of 64.688316 that matches the unclamped
  formula exactly. The clamp is on the final value only.
- The 22nd entry in `AttributeRatingWeightScale` is `Stamina`, which is not one
  of the 21 builder attributes. It is simply unused here.
- Missing weight entries are implicit 0.0 (`tables.weights` already handles
  this); none of the omissions fall in bucket 11.

## Confidence

High on the value curve and on selection: they are exact on 331 recorded rows
across two independently probed files, every term maps to a named tuning key,
and the uniform file corroborates the structure from two directions.

Lower on the cap-lift predicate, for the reason given above. It affects only
builds that would otherwise display 99, i.e. essentially finished ones.

Untested at other heights: every golden row is at bucket 11. The formula is
written against the general tables and should generalise, but nothing here
verifies bucket 5-24 behaviour beyond the fact that the tables exist.
