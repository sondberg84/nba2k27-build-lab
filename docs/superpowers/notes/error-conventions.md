# How this codebase handles bad, missing and ambiguous data

Several of the vendored tables are defective or ambiguous in ways that would
produce confident wrong answers. The handling is not uniform, and that is
deliberate: it is calibrated to **how confidently wrong a naive answer would
be**. Four cases, four responses.

## 1. Data is unusable — raise

The naive answer would be silently, catastrophically wrong.

`tokens.contribution` and `tokens.earned` raise for heights 82 and above. Every
token value there is zero while the sibling `slots` field stays populated, which
reads as a capture that stopped recording rather than a game rule. Returning the
shipped zeros would tell every centre they earn no badge tokens.

**Rule:** if a plausible-looking value would mislead badly, refuse. Name the real
reason in the message.

## 2. Data is usable but the question is wrong — raise on the aggregate path only

The low-level lookup is legitimate; the build-level question is not.

`badges/token_costs.json` prices badges at heights where they are not eligible —
`rise_up` has a price at 5'9" despite being eligible only from 6'5". `cost_for`
stays a raw lookup and returns it, because composability matters and the caller
may have a reason. `cost_of_loadout` raises, because pricing a loadout that
cannot be built is never what anyone wants.

**Rule:** keep raw accessors raw. Guard at the level where the question acquires
meaning.

## 3. Two readings both fit — offer a flag, document both

The data cannot arbitrate and neither reading is a defect.

Token costs decrease with tier (bronze 3, silver 2, gold 1). That only makes
sense if each row prices a tier *step*, but the field description says the cost
is for "tier being equipped". `cost_of_loadout` takes `cumulative` and documents
both readings in its docstring.

**Rule:** do not pick silently. Make the fork visible in the signature.

## 4. Partial success is real information — return a structured result

Failing outright would discard something useful.

`capbreakers.apply_all` returns `rating`, `applied`, `complete` and `note`. Two
of five applications landing is a genuine answer, not an error — but silently
returning the truncated rating as if all five had landed would be wrong.

**Rule:** when partial work has value, report how far it got rather than raising
or pretending.

## The through-line

Every one of these exists because a plausible number would have been worse than
no number. Phase 1a shipped a real bug of exactly that shape — `body.ceilings`
crashed at 5'9" because a table was sparser than assumed, and it survived a green
88-test suite and two code reviews before being caught by pointing the finished
engine at a real question.

So: when a table turns out to be sparse, defective or ambiguous, the first
question is not "what should we return" but "would returning anything here
mislead someone building a character they will grind for weeks".
