# 2K27 Build Lab — Design

**Date:** 2026-08-25
**Status:** Approved design, ready for implementation planning

## 1. Purpose

A local tool for creating, evaluating and optimizing NBA 2K27 MyPLAYER builds, using NBA 2K's own rules engine data rather than estimates.

It serves three jobs that came out of brainstorming:

1. **Build and optimize** — make a build, have the tool find waste and improve it.
2. **Critique** — paste a YouTube build transcript, get a verdict grounded in real numbers.
3. **Answer open questions** — "what would a fast center look like?", "how do I get a defensive slasher?" — answered by Claude driving the engine, not by guessing.

The definition of "optimal" is **not** hardcoded. It is supplied per-question as constraints, because the goal changes with every conversation.

## 2. Non-goals

- No hosting, no server, no account, no paid service. Runs entirely on the local machine.
- No scraping of YouTube, no OCR of screenshots. Build import is a pasted transcript.
- No attempt to model in-game feel, shot timing, or server-side gameplay tuning.
- Not a replacement for the in-game builder — it is a planning tool.

## 3. Data sources and provenance

Every number carries provenance. The tool never blends verified and unverified data silently.

| Layer | Source | Confidence |
|---|---|---|
| `data/engine/*.json` | Vendored copy of `github.com/lightmatmul/nba2k27-builder-dataset`, pinned to a commit | Engine-exact; captured from 2K's native rules engine |
| `data/animations.json` | Parsed from `2k27-animation-requirements.md` (NBA2KLab, 1,814 rows) | Community Day data; parse must be spot-checked |
| `data/ratings.json` | Authored by the user through launch-day testing | Subjective, starts empty |
| `data/gaps.json` | Diff of repo `animations/glossary.json` (2,914 entries) against parsed requirements | Known unknowns |

### Known data caveats (carried into the tool as warnings)

- The dataset is a pre-release capture: `api_version 202750199`, `live_tuning_version 993560759169487438`, captured 2026-08-22. Day-one patches can move it.
- `overall/single_attribute.json` is flagged by the dataset author as "unverified semantics" — do not build logic on it without independent verification.
- The badge slot-allocator combining rule is unresolved upstream (inputs known, formula not).
- Takeover attribute enum mapping is unresolved beyond the 0–20 builder namespace.
- **Jumpshot bases/releases have no requirement data at all.** Verified by search: the animation markdown contains no jumpshot base or release entries. Shooting coverage is Dribble Pull-Up, Go-To Shot, Hop Jumper, Post Fade, Post Hop Shot, Spin Jumper only. This is the single largest gap and must be surfaced, not silently omitted.

### Verified during brainstorming

Spot-checks of third-party threshold claims against the source markdown all matched exactly: contact dunk gates (86/75, 87/75, 89/78, 93/80, 96/89, 99/90), bigman contact gates (80 SD / 60 Vert, 90 SD / 70 Vert), the big-man layup ladder (Wemby 70, Embiid 73, Sengun 75, KAT 77, Sabonis 78, Jokic 79, Paolo 85), the Signature Size-Up ladder, and the Dribble Style ladder.

Two findings the tool must encode:

- **Small Contact Dunks Off Two costs 86 Driving Dunk but caps at 6'4 max height**, below Pro Off Two at 87. On a build 6'4 or under, 86 is the real breakpoint and 87 buys nothing.
- **Kyrie Irving dribble style requires 94 Speed With Ball**, the highest gate in the file.

## 4. Architecture

Two layers, deliberately separated:

- **Math layer** — exact, derived from the rules engine, never guesses.
- **Ratings layer** — subjective animation quality, starts empty, filled by the user.

The ratings layer is what makes the solver useful rather than a catalogue: it lets the tool reason "Wemby layup at 70 rates better than Jokic at 79 — save 9 points."

```
data/                 engine/                          interfaces
  engine/*.json         body.py       caps, legal bodies    cli.py  (Claude + user)
  animations.json       ovr.py        pricing tables        ui/     (browser, later)
  ratings.json          badges.py     tiers, tokens
  gaps.json             animations.py gating + ratings
                        build.py      build state, evaluate
                        solve.py      constraints -> builds
                        analyze.py    waste detection
```

One engine underneath every interface, so the number shown in the browser is the same number Claude gets in conversation.

**Implementation constraints:** Python 3 standard library only (Python 3.14.3 confirmed present). No pip installs, no external dependencies, no build step. The web UI is plain HTML/CSS/JS served by `http.server`, so it stays install-free too.

### Module responsibilities

Each module has one job, a clear interface, and can be tested alone.

- **`body.py`** — legal height/weight/wingspan combinations per position; attribute ceilings via the dataset's verified formula `ceiling = clamp(round(25 + 74 * height_mult * weight_mult * wingspan_mult), 25, 99)`. Input: body. Output: legality plus per-attribute ceilings.
- **`ovr.py`** — overall rating and attribute pricing from the tuning tables, including archetype selection. Input: attribute vector plus body. Output: OVR plus winning archetype.
- **`badges.py`** — badge tier requirements as attribute predicates (AND/OR), token costs by badge × tier × height, token contributions by attribute × level × height, and the resulting token budget. Input: build. Output: unlocked tiers, tokens earned, tokens spent.
- **`animations.py`** — animation gating by attribute and height range, joined to the ratings layer. Input: build. Output: available packages per family, ranked by rating where ratings exist.
- **`build.py`** — the build object: body, 21 attributes, optional cap breakers. Supports **partial builds** where attributes are unspecified. `evaluate()` returns the full report.
- **`solve.py`** — constraint solver. See section 6.
- **`analyze.py`** — waste detection and threshold ladders. See section 5.

## 5. Threshold ladders and waste analysis

The highest-value feature. For any attribute on a given body, show what each point buys — badge tiers and animations together:

```
Ball Handle @ 6'4  —  currently 84
  85  ->  Allen Iverson, Jason Williams size-ups
  86  ->  Ja Morant, Harden, Poole size-ups        <- 2 pts, biggest jump
  87  ->  nothing                                   <- dead point
  90  ->  Kyrie, Lillard size-ups | Ankle Assassin GOLD
```

Waste analysis runs the same data in reverse across a whole build:

- **Dead points** — a rating sits above one threshold but below the next, unlocking nothing.
- **Near misses** — a rating sits 1–3 points below a threshold that unlocks something.
- **Height-invalidated spend** — points spent on an attribute whose payoff is gated to a height range this build falls outside.

## 6. Solver

Constraints in, builds out. Supported constraint types, freely combined:

- **Badge tier** — `Limitless Range >= Gold`, `Ankle Assassin >= HOF`
- **Attribute floor/ceiling** — `Speed With Ball >= 80`, `Strength <= 60`
- **Animation unlock** — `Victor Wembanyama dribble style`, `Elite Bigman Contact Dunks`
- **Body** — a fixed height, or a range to search across
- **Objective** — maximize an attribute, or minimize total cost

Output is the cheapest build or builds satisfying every constraint. On failure it reports **which constraint pair is irreconcilable**, not just "no solution" — for example "Kyrie size-ups require ≤ 6'4, Elite Bigman Contacts require ≥ 6'10."

When ratings data exists, the solver prefers the cheapest animation meeting a quality bar over the highest-requirement one.

## 7. Critique flow

Input is a pasted YouTube transcript. Claude extracts the build into a build file; the engine does the rest. Designed around what transcripts actually contain:

**Partial specification.** Creators name roughly 8 of 21 attributes. The engine evaluates what is given, lists what is unspecified, and can solve for the remainder under the stated OVR and cap constraints, so the report reflects a complete legal build.

**Incorrect claims.** The engine checks creator assertions against the rules data and reports mismatches:

```
Creator: "you get HOF Ankle Assassin here"    -> 93 BH = Gold. HOF needs 96.
Creator: "87 driving dunk for contact dunks"  -> Pro Off Two OK. At 6'4, 86 gets Small
                                                 Contacts; 87 wastes a point.
Creator: "6'9 with 7'3 wingspan"              -> Legal. Perimeter D ceiling 99, 3PT 92.
```

**Verdict.** Waste report, gaps relative to the stated playstyle, and a counter-build when the solver can beat it under the same constraints.

## 8. Testing

The engine must be provably correct before it is trusted, because a silently wrong number produces a ruined build that takes weeks of grinding to discover.

- **Golden vectors** — the dataset ships 256 mixed vectors with known OVR, winning archetype, and detailed/best variants, plus a UI-verified set. The engine must reproduce all of them exactly. This is the gate on phase 1.
- **Cap formula** — must reproduce the measured ceilings in `bodies/attribute_caps_sample.json`.
- **Badge tokens** — token contributions are testable against the dataset's 2,048-vector sweep.
- **Animation parse** — row counts must match the file's stated totals per section (266 / 420 / 775 / 353, 1,814 total), plus hand spot-checks of known ladders.
- **Regression on data refresh** — if a patched dataset breaks the golden vectors, the tests fail loudly rather than the tool quietly returning bad builds.

Tests use `unittest` from the standard library.

## 9. Data refresh and update handling

Upstream data will keep changing, and the changes are not additive. The dataset repo was created 2026-08-24 and within one day carried three corrections — `3084060` correcting `single_attribute` claims, `da328b2` retracting the slot-allocator documentation as not reproducing ground truth, and `957d009` fixing a MaxDelta reading and an archetype name. These are retractions of claims, not new rows. The game has not shipped yet, so this will continue.

The risk is therefore not "the data is stale" but "a correction silently moves a threshold a build was planned around." The design treats refresh as a first-class feature, not maintenance.

### Pin everything, adopt nothing automatically

`data/SOURCES.json` records, for every source: URL, exact commit SHA, fetch date, and a SHA-256 for each file. The engine refuses to run against data not present in the manifest. No source changes without an explicit adopt step.

### `2k refresh` is a three-step operation

1. **`--check`** — queries GitHub for the upstream head, compares against the pin, reports how many commits behind along with their messages. Downloads nothing.
2. **`--preview`** — downloads into a staging directory, leaving live data untouched, and produces a **semantic diff rather than a text diff**: `Ankle Assassin Gold: 93 -> 91`, `token cost badge 17 tier 3 @ 6'6: 4 -> 5`, `2 new badges`.
3. **`--adopt`** — applies the staged data. Only reachable after a preview.

### Distinguishing a real rules change from a broken capture

The golden vectors ship inside the dataset, so tables and vectors version together. Running the new vectors against the new tables gives a three-way verdict:

| New tables vs. new vectors | Values changed | Verdict |
|---|---|---|
| Reproduce exactly | yes | Real change — game patched or capture improved. Adopt, then show impact. |
| Reproduce exactly | no | Cosmetic upstream change. Adopt quietly. |
| Do not reproduce | — | Upstream capture is broken. Refuse to adopt, keep the existing pin, report why. |

The third row is the safety property that matters most against a fast-moving upstream: a bad upstream commit is rejected before it can reach a build.

### Impact report on saved builds

After a real change, every saved build is re-evaluated under both old and new data and the difference reported in build terms, not data terms:

```
center build:  OVR 87 -> 86
               LOST  Gold Rebound Chaser  (req 80 -> 82)
               NEW   2 dead points at Ball Handle 86
```

### Snapshots and rollback

Superseded data is retained under `data/snapshots/<sha>/`. Because the project lives in a private git repo, an adopt is a single commit and a revert is a single command, and any current state can be diffed against the original Community Day capture.

### Locally authored sources

The animation markdown and knowledge-base files are hashed in the same manifest and re-parsed and diffed by the same command when they change.

`data/ratings.json` is never written by refresh — it is user-authored. Ratings key on animation name, so an upstream rename or removal is reported as a warning rather than silently discarding testing work.

### What refresh will not do

No background polling, no scheduled jobs, no network access unless a refresh subcommand is invoked.

## 10. Build order

1. **Data plus core engine plus tests** — vendor the dataset behind `data/SOURCES.json` with a pinned SHA and per-file hashes, implement `body`, `ovr`, `badges`. Gate: all 256 golden vectors reproduce exactly.
2. **Animation parse** — markdown to structured JSON, spot-checked. Threshold ladders work.
3. **CLI** — `eval`, `solve`, `ladder`, `critique`, `diff`, and `refresh` (section 9). **At this point the tool is fully usable in conversation.**
4. **Ratings layer** — schema, editing workflow, solver integration, and the launch-day testing shortlist, in priority order: jumpshot, dribble style, layup style, contact dunks, signature dunk packages, signature size-up, behind-the-back, crossover/escape, pull-up and hop jumper, big post moves. Note that jumpshot heads this list as a *testing* priority while having no requirement data (section 3); rating it is possible in-game, gating on it is not until a requirement source exists.
5. **Web UI** — local page with sliders and live readout over the proven engine.

Phases 1–3 are the tool. Phases 4–5 are what make it better than anyone else's.

## 11. Open items

- Jumpshot base and release requirements need a source. Until one exists the tool reports them as a known gap rather than omitting them.
- The badge slot-allocator formula is unresolved upstream. The tool shows token costs and slot inputs but must not fabricate a slot count.
- Takeover requirements are present but their attribute enum is unmapped. Surface as low confidence.
- Upstream may retract further claims. Section 9 handles the mechanics; what remains open is whether any upstream correction ever proves the engine wrong rather than the data changed, which would mean revisiting the golden-vector strategy itself.
