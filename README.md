# 2K27 Build Lab

A local tool for planning NBA 2K27 MyPLAYER builds, built on the game's own rules data
rather than estimates.

Everything runs on your machine. No install, no dependencies, no account, no cost. If you
have Python, you can run it.

---

## Where the data comes from

**This project computes; it did not gather.** Two other people's work makes it possible, and
neither is mine:

**[lightmatmul/nba2k27-builder-dataset](https://github.com/lightmatmul/nba2k27-builder-dataset)**
— the game's own rules data, captured by calling NBA 2K HQ's native builder functions
directly rather than estimating. Attribute weights, body multipliers, badge requirements,
token tables, cap breakers, and the 256 golden vectors this engine is verified against. A
copy is vendored in `data/engine/`, pinned to commit `957d0095`.

**NBA2KLab** — the 1,814 animation requirement rows in `data/local/`, gathered by testing
rather than extraction. These **are** included in this repository, because there is nowhere
else to obtain them: someone sat down and recorded them, and there is no machine-readable
upstream to point you at. Everything the `animations`, `ladder` and `reachability` commands do rests on
that work.

If you find this useful, the credit belongs upstream. All this repository adds is the
arithmetic on top — reconstructing the rating formula from the tuning tables, and joining
the two datasets so they can answer questions neither can alone.

The data is **pre-release Community Day capture, dated 2026-08-22**, and 2K can change any
of it.

---

## Setup, once

The upstream dataset is **not redistributed here** — you fetch it from its source:

```bash
python tools/vendor.py
```

That downloads the 13 data files from lightmatmul's repository at the exact pinned commit
and hash-verifies them. It takes a few seconds and you never need to run it again unless
the data changes.

The animation requirements in `data/local/` **are** included, because there is nowhere else
to get them — they were gathered by hand and have no machine-readable upstream.

## Quick start

Then run:

```bash
python -m buildlab.cli serve
```

That opens the build lab in your browser: a height picker, twenty-one sliders, and the
overall, archetype, badges, animations and threshold ladder updating as you drag.

Everything it shows is also available from the command line, which is often faster for a
specific question:

```bash
python -m buildlab.cli eval --height 6-3 --values 47,30,47,26,79,54,87,77,36,55,45,31,73,53,27,40,43,34,85,50,51
```

The 21 numbers are your attributes, in the order the in-game builder lists them.

---

## The commands

### `serve` — the browser page

```bash
python -m buildlab.cli serve
python -m buildlab.cli serve --port 9000 --no-browser
```

Opens a local page with a height picker and twenty-one sliders. Overall, archetype, badge
count, animation count, upgrade points and badge tokens all update live. Click any attribute
name to see its threshold ladder alongside. An attribute pushed above its ceiling turns red.

It binds to `127.0.0.1` only — nothing on your network can reach it. The data is loaded once
when the server starts, so if you re-import data, restart it.

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

The ceiling it reports is the best any legal body can reach at that height. A heavier
build, or one with a shorter wingspan, may fall short of it — so treat the top of the
ladder as the best case for that height, not a promise for your specific body.

### `solve` — what's the cheapest build that does X?

```bash
python -m buildlab.cli solve --attribute three_point=95 --attribute perimeter_defense=90
python -m buildlab.cli solve --animation "Dribble Style:Kyrie Irving" --badge ankle_assassin=gold
python -m buildlab.cli solve --badge float_game=hall_of_fame --height 6-6
```

You state goals — attribute floors, badges at a tier, specific animations — and it finds
the cheapest build meeting all of them, tells you every height where it works, and prints
the attributes you actually need.

When it can't be done it says so and names why. Ask for a guard animation and a big-man
badge together and it will tell you they share no legal height, rather than shrugging.

Goals are repeatable and mixable. `--height` pins it to one height instead of searching.

### `critique` — is this build any good?

```bash
python -m buildlab.cli critique --height 6-4 --values <21 numbers>
python -m buildlab.cli critique --height 6-4 --values <21 numbers> --claim ankle_assassin=hall_of_fame
```

Point it at a build somebody proposed — off a video, off a forum — and it reports the
overall, the badges, how many points are buying nothing, and any attribute that is above
its ceiling and therefore impossible.

`--claim` checks stated badge claims against reality. If a video says a build gets
hall-of-fame Ankle Assassin and it actually reaches silver, this is where you find out.

### `refresh` — is there newer game data?

```bash
python -m buildlab.cli refresh --check
python -m buildlab.cli refresh --preview
```

`--check` compares your pinned data against upstream without downloading anything.
`--preview` fetches to a staging folder — your live data is never touched — diffs it, and
then runs the game's own 256 test vectors against the staged tables.

That last step is the point. If the staged tables still reproduce the vectors, the change
is safe. If they don't, either the rules genuinely changed or somebody's capture broke,
and the tool refuses to adopt rather than guessing which.

### `rate` — your own animation quality notes

```bash
python -m buildlab.cli rate --shortlist
python -m buildlab.cli rate --validate
```

The animation *requirements* come from data. The animation *quality* can't be known until
you play the game. `data/ratings.json` is where your judgement goes — it's yours, no tool
writes it, and it is deliberately not hash-pinned so editing it doesn't look like corruption.

`--shortlist` shows the ten families worth testing first and how many you've rated.
`--validate` checks your file for typos and out-of-range scores.

### `diff` — how far off the plan am I?

```bash
python -m buildlab.cli diff --height 6-10 --values <current 21> --target <target 21>
```

The mid-build command. Screenshot your builder, hand me the numbers, and this says what
is still needed, what is already past target, which badges you have not reached yet, and
whether either build is impossible at that height.

### `reachability` — which animations lie about their height range

```bash
python -m buildlab.cli reachability
python -m buildlab.cli reachability --family "Dribble Style"
```

Lists every animation that cannot actually be reached somewhere inside its own published
height range, because no legal body at that height has a high enough attribute ceiling.
There are **397 of them**, including 21 of the 39 dribble styles. For each it shows the
stated range, the real one, and which attribute is doing the blocking.

---

## Height format

Heights are written `feet-inches`: `5-9`, `6-3`, `6-11`, `7-4`.

---

## Things the tool knows that build guides do not

**Attributes constrain each other.** Speed With Ball can never exceed Speed by even a point,
and is also capped at Ball Handle + 5 and Agility + 15. So a build advertised as needing
"94 Speed With Ball" also needs Speed 94, Ball Handle 89 and Agility 79. And those are only
the *direct* links — the constraints chain onward, so the real cost is **twelve attributes
at 6'2" and twenty at 7'0"**. Run `solve --attribute speed_with_ball=94` to see the whole bill.

**A fast centre does not exist above 6'9".** Agility is capped at 68 at 7'0". Fast bigs live
at 6'7"–6'9", which is also the last height before roughly half the animation packages
disappear.

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

Two different sources, updated two different ways.

The **upstream game data** is pinned to an exact commit and hash-verified, so it never
changes underneath you. Re-pulling it is a deliberate act, not something that happens by
accident.

The **animation requirements** come from your own `2k27-animation-requirements.md` in the
folder above this one. If you edit that file, re-import it:

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
  goals       goal types and the floors they imply
  solver      cheapest build meeting a set of goals
  critique    evaluate a build somebody proposed
  diff        compare a build in progress against a target
  refresh     check, stage and judge new upstream data
  ratings     your own animation quality scores
  cli         the commands above

data/         the pinned game data, hash-verified
docs/         plans, derivation notes, findings
tests/        the test suite
tools/        data import scripts
```
