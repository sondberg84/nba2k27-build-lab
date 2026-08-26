# 2K27 Build Lab

A local tool for planning NBA 2K27 MyPLAYER builds, built on the game's own rules data
rather than estimates.

Everything runs on your machine. No install, no dependencies, no account, no cost. If you
have Python, you can run it.

---

## Quick start

Open a terminal in this folder and try:

```bash
python -m buildlab.cli eval --height 6-3 --values 47,30,47,26,79,54,87,77,36,55,45,31,73,53,27,40,43,34,85,50,51
```

That prints the overall rating and archetype for a build. The 21 numbers are your
attributes, in the order the in-game builder lists them.

---

## The four commands

### `eval` — what is this build?

```bash
python -m buildlab.cli eval --height 6-3 --values <21 numbers>
```

Prints the overall rating, the winning archetype, and the attributes you gave it.

### `badges` — what badges does it unlock?

```bash
python -m buildlab.cli badges --height 6-3 --values <21 numbers>
```

Lists every badge the build unlocks, grouped by tier, with the token cost of each. Then
shows how many badge tokens the build earns, split by discipline.

### `animations` — what can it actually do?

```bash
python -m buildlab.cli animations --height 6-3 --values <21 numbers>
python -m buildlab.cli animations --height 6-3 --values <21 numbers> --family "Dribble Style"
```

Lists the animation packages the build qualifies for. Add `--family` to narrow it to one
kind — dribble styles, layup styles, contact dunks and so on.

### `ladder` — what does the next point buy?

```bash
python -m buildlab.cli ladder --height 6-4 --attribute ball_handle
```

The most useful one. For a single attribute at a given height, it shows every rating that
unlocks something and what that something is — badge tiers and animations together. Ratings
that unlock nothing simply do not appear, so the gaps between rows are the wasted points.

Attribute names are the snake_case ones: `ball_handle`, `speed_with_ball`, `three_point`,
`driving_dunk`, `perimeter_defense`, and so on.

---

## Height format

Heights are written `feet-inches`: `5-9`, `6-3`, `6-11`, `7-4`.

---

## Things the tool knows that build guides do not

**Attributes constrain each other.** Speed With Ball can never exceed Speed by even a point,
and is also capped at Ball Handle + 5 and Agility + 15. So a build advertised as needing
"94 Speed With Ball" actually needs Speed 94, Ball Handle 89 and Agility 79 as well. Four
attributes, not one.

**An animation's height range is not the real limit.** Kyrie Irving's dribble style is
listed as 5'9"–6'4", but it needs 94 Speed With Ball and no body above 6'2" can reach that.
The published range says yes; the attribute ceiling says no.

**Bodies foreclose attributes outright.** A 6'3" 198 lb build with a 78" wingspan can reach
99 close shot and 99 perimeter defence but is hard capped at 51 standing dunk and 63 block.
No grinding moves those.

**Height changes your overall on its own.** The same 21 attributes score 84 at 5'9" and 94
at 6'8".

**6'8" is a badge token price breakpoint.** Big-man badges get more expensive above it,
guard badges get cheaper.

**Free throw is inert.** It is the only attribute exempt from the overall-rating scale and
the only one that earns no badge tokens. It raises neither your rating nor your badges.

More in [docs/superpowers/notes/first-findings.md](docs/superpowers/notes/first-findings.md).

---

## What it refuses to tell you, and why

Some of the source data is defective or ambiguous. Where a confident answer would mislead,
the tool declines instead of guessing.

The clearest case: **badge token data is missing for builds 6'10" and taller.** The source
records zero tokens for every attribute at those heights while the badge slot data in the
same rows keeps working — the signature of a capture that stopped recording, not a game
rule. Taken at face value it would tell every centre they earn no badge tokens at all. So
the `badges` command still lists your badges at those heights but reports token earnings as
unavailable and says why.

The full reasoning behind each refusal is in
[docs/superpowers/notes/error-conventions.md](docs/superpowers/notes/error-conventions.md).

---

## How much to trust the numbers

The overall-rating engine is **exact**. It reproduces all 256 of the game's own test vectors
on archetype, precise float and displayed integer, plus 75 uniform-rating rows and the two
builds corroborated against screenshots of the real in-game builder. Attribute ceilings
reproduce the game's own measured caps, 21 out of 21.

Badge requirements and heights cross-check against NBA2KLab's independently gathered tables,
nine for nine on the ones tested.

Three values are reasoned inferences rather than measurements, each flagged in the code
where a maintainer would find it: the display cap constant, the rule for when a build shows
a clean 99, and the standing-dunk ceiling at 5'9"–6'0".

**Everything is pre-release Community Day data, captured 2026-08-22.** 2K can change any of
it before launch, and a day-one patch will move some of it.

---

## Running the tests

```bash
python -m unittest discover -s tests
```

Everything should pass. If something fails after a data update, that is the point — the
tests pin the data's known shape so a change is loud rather than silent.

To re-check that the data files have not been altered:

```bash
python -c "from buildlab import sources; sources.verify()"
```

---

## Updating the data

The upstream dataset is pinned to a specific commit, so it never changes underneath you.

If you edit `2k27-animation-requirements.md` in the folder above this one, re-import it:

```bash
python tools/vendor_local.py
```

Then run the tests. If the row counts moved, they will tell you.

---

## Layout

```
buildlab/     the engine
  sources     manifest-gated access to the data files
  tuning      reads the game's tuning export
  reference   the 21 attributes, legal bodies
  tables      weights, rating scales, the display curve
  body        legality and attribute ceilings
  archetypes  archetype scoring and selection
  ovr         overall rating
  constraints linked attribute caps
  badges      definitions, tiers, requirements
  tokens      badge token costs and earnings
  capbreakers cap breaker gains
  animations  animation package requirements
  ladders     what each point buys
  cli         the commands above

data/         the pinned game data, hash-verified
docs/         plans, derivation notes, findings
tests/        the test suite
tools/        data import scripts
```
