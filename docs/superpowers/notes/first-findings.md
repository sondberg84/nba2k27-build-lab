# First findings from the engine

Produced by pointing the finished phase 1 engine at real build questions. Every number
here is computed, not quoted, and is reproducible from the committed code.

## 1. Attributes constrain each other, and nobody documents it

`AssociatedAttributeConstraints` carries **1,545 rules across all 21 attributes, per
height**, capping each attribute relative to another. 420 `(attribute, bucket)` pairs,
covering buckets 5–24 — exactly the legal height range. No rule is self-referential.

The full delta distribution spans 26 distinct values from 0 to 65, with the bulk at
25 (213 rules), 20 (173), 45 (167), 30 (159) and 40 (158).

**There is exactly one hard lock in the game** — a `MaxDelta` of 0, meaning an attribute
may never exceed its partner by even a point:

```
SpeedWithBall <= Speed + 0        at all 20 heights
```

Speed With Ball also carries two tight relative caps:

```
SpeedWithBall <= BallControl + 5
SpeedWithBall <= Agility + 15
```

### What that costs

A build advertised as needing "94 Speed With Ball" requires four attributes **directly**:

| Attribute | Forced minimum | Why |
|---|---|---|
| Speed With Ball | 94 | the stated requirement |
| Speed | 94 | `SWB <= Speed + 0` |
| Ball Handle | 89 | `SWB <= BallControl + 5` |
| Agility | 79 | `SWB <= Agility + 15` |

**But the real total is larger, because the constraints chain.** Speed is itself capped
relative to other attributes, and so on. Following the chain to a fixed point and discarding
anything at or below the starting floor of 25, the true cost of 94 Speed With Ball is:

```
5'9"   11 attributes        6'4"   14 attributes
6'2"   12 attributes        7'0"   20 attributes
```

The four direct links are the same at every height; the tail grows with the build. So a
guide quoting only the Speed With Ball number is quoting **one twelfth** of the real price
on a 6'2" guard, not one quarter.

(Phase 1 recorded this as "four attributes". That was the direct links only and understated
the cost — corrected here after the chain was implemented.)

## 2. Animation height ranges are not the real limit

Kyrie Irving's dribble style requires **94 Speed With Ball**. The NBA2KLab animation table
lists its height range as **5'9" – 6'4"**.

That range is unreachable. The maximum Speed With Ball ceiling by height, scanned
exhaustively across every legal weight and wingspan at each height:

```
5'9   99      6'2   94   <- last height where 94 is reachable
5'10  99      6'3   93
5'11  99      6'4   91
6'0   98      6'5   89
6'1   97      6'6   86
```

**The real limit is 6'2", not 6'4".** At 6'3" the ceiling is 93 — one point short — and no
weight or wingspan combination closes it.

Worse, at 6'2" it is reachable only at the **minimum weight and minimum wingspan**
(165 lb, 74 in). Any heavier or longer-armed 6'2" build cannot reach 94 either. The forced
companions do fit on that body: Speed ceiling 99, Ball Handle 98, Agility 99.

The general lesson: **an animation's stated height range is a necessary condition, not a
sufficient one.** The attribute ceiling can foreclose an animation well inside its
advertised range. Any tool that checks only the height gate will tell players a build
works when it cannot.

## 3. Height moves overall rating on its own

Identical attributes, every value 75, evaluated at different heights:

```
5'9   84        6'8   94
6'0   86        7'0   91
6'3   88        7'4   92
```

Ten points of overall between 5'9" and 6'8" with no change to a single attribute, because
each height and archetype pair carries its own weight vector.

## 4. Free throw is exempt from the rating scale

`AttributeRatingWeightScale` ships all 25 rows (ratings 75–99) for `ShotFreeThrow`, and
every one is **1.0**. It is the only builder attribute for which that holds.

For contrast, `ShotThree` scales 1.01 at rating 75 to **3.75** at 99. Since the overall
rating is a weighted average whose weights are multiplied by this scale, a high three-point
rating pulls the average toward itself far harder than a high free throw does.

## 5. Bodies foreclose attributes outright

The reference body used throughout the dataset — PG, 6'3", 198 lb, 78 in wingspan — can
reach 99 close shot and 99 perimeter defence, but is hard capped at **51 standing dunk and
63 block**. No amount of grinding moves those.

At 5'9" – 6'0", standing dunk is not a usable attribute at all: it has no height multiplier
and carries no weight in the overall rating. Its ceiling is the floor value, 25.

## Caveats

- All of this is Community Day data, captured 2026-08-22, pinned at upstream commit
  `957d009`. 2K can change any of it before launch.
- The overall-rating formula is verified against 256 golden vectors at 6'3" only. The
  identity holds structurally at every height, but the display cap is unverified away from
  6'3".
- The standing-dunk floor of 25 at 5'9"–6'0" is a reasoned inference, not a measured value.
  No answer key covers those heights.

---

# Phase 1b findings — badges, tokens and cap breakers

Same rule as above: every number is computed from the committed code, not quoted.

## 6. Two independent datasets agree

This phase gave the first chance to check the engine's badge data against the
NBA2KLab-derived tables in `2k27-build-knowledge-base.md`. Badge height ranges, nine
spot-checks, all exact:

```
mini_marksman      5'9-6'4     ankle_assassin   5'9-6'10    handles_for_days  5'9-7'0
paint_prodigy      6'3-7'4     lightning_launch 5'9-6'11    strong_handle     5'9-6'11
arc_cadence        5'9-6'11    pace             5'9-6'10    layup_mixmaster   5'9-7'0
```

One source is 2K's own rules engine, the other is NBA2KLab's testing. Landing on
identical numbers is strong mutual validation.

It also decoded a notation. **Unpluckable at hall-of-fame** reads `— / 97` in the
NBA2KLab table and `post_control 100 OR ball_handle 97` in the engine. The dash is the
engine's unreachable 100: no attribute can exceed 99, so that branch is dead and
Unpluckable HOF is **ball-handle-only**. A solver chasing the post-control side would be
chasing something that cannot exist.

## 7. 6'8" is a badge-token price breakpoint

Bronze cost varies with height for 11 of 53 badges, and almost all of them change at
exactly the same place:

```
big-man badges get MORE expensive at 6'8"+
  rise_up 1->3, brick_wall 1->3, paint_prodigy 1->3 (again at 6'10"),
  post_lockdown 1->2, post_powerhouse 1->2, high_flying_denier 1->2, pogostick 1->2

guard badges get CHEAPER at 6'8"+
  slippery_offball 2->1
```

Silver is a flat 2 tokens everywhere. Gold and hall-of-fame are a flat 1 everywhere. So
**bronze is the only tier whose price moves at all**, and 6'8" is where it moves.

A big built at 6'7" pays meaningfully less per badge than the same build at 6'10". That
trade-off is not documented anywhere.

## 8. Free throw is doubly inert

Phase 1 found free throw is the only attribute exempt from the overall-rating scale — its
multiplier stays 1.0 at every rating while three-point climbs to 3.75.

This phase found the other half: **free throw earns zero badge tokens at every rating and
every height.** It is the only attribute that earns nothing.

So free throw neither raises your overall nor buys you badges. Whatever it is for, it is
not those two things.

## 9. The token economy only makes sense one way

A maxed build earns 121 tokens at 6'3" (125 at 6'9", the ceiling of trustworthy data).
Every build gets 20 badge slots, per the upstream README.

The shipped cost data cannot settle whether a tier's price is absolute or incremental, so
the engine supports both and defaults to the literal reading the field description implies.
But the arithmetic argues:

```
47 eligible badges at hall-of-fame, literal      47 tokens   (121 earned - trivial)
47 eligible badges at hall-of-fame, cumulative  287 tokens   (impossible)
20 slots filled at hall-of-fame, cumulative     ~108 tokens  (121 earned - tight)
```

Under the literal reading tokens are nearly free and the system is pointless. Under the
cumulative reading, filling your 20 slots at max tier costs about 108 against 121 earned —
a real budget where choices bite. **Cumulative is almost certainly the true reading.**

That is an inference from game design, not from evidence, so the default stays faithful to
the data. One recorded token balance for a known loadout would settle it permanently.

## 10. Cap breakers do not model breaking a cap

Despite the name, the shipped data describes gains that **taper to exactly zero at the
ceiling**:

```
close_shot at 89 (below cap)   gains 2, 2, 2, 1, 1  ->  reaches 95
close_shot at 99 (at cap)      gains 0, 0, 0, 0, 0  ->  stays 99
```

The table was probed at one body and stops at that body's ceiling for each attribute. So it
answers "how fast does an attribute climb toward its cap", not "can a cap breaker exceed
the cap". The latter is **unanswerable from this data**.

Also measured: the `near_caps` scenario gives strictly more than `isolated`, sometimes far
more — speed_with_ball from 25 gains 5 under `isolated` and 25 under `near_caps`. What
distinguishes the two scenarios is not documented upstream and is an open question.

The largest single cap-breaker gain anywhere in the table is **+15**, on standing dunk at
rating 25.

## 11. A data defect that would have produced catastrophic advice

**Every token value is zero for heights 82-88 (6'10" and up)**, while the `slots` field in
those same rows stays populated. Counting rows with any nonzero token value:

```
69-81   689, 690, 694, 695, 706, 719, 731, 732, 741, 747, 746, 746, 746
82-88   0, 0, 0, 0, 0, 0, 0
```

A smooth climb that falls to exactly zero between 6'9" and 6'10", with a sibling field in
the same rows unaffected, is the signature of a capture that stopped recording — not a game
rule. Taken at face value it would tell **every centre they earn no badge tokens at all**.

Upstream commit `957d009` is still their latest and the README does not mention it. The
engine therefore treats 82+ as **missing**, raising rather than returning zero, and the CLI
degrades gracefully and explains why. A test pins the defect so that a future data refresh
which fixes it fails loudly and tells us to widen the trusted range.

**This is the first thing worth re-capturing at launch**, and worth reporting upstream.

## Caveats carried forward

- All Community Day data, captured 2026-08-22, pinned at upstream commit `957d009`.
- Token additivity is verified upstream against 2,048 native vectors, but those vectors are
  not shipped, so it cannot be re-checked locally.
- The badge slot allocator formula is unresolved upstream. The `slots` array is read but
  nothing is computed from it.
- Cap breaker data is valid only for the reference body, PG 6'3" 198 lb 78 in wingspan.

---

# Phase 2 findings — animations and ladders

## 12. Animation availability is not monotonic in height

Every animation sits in one of three height bands, because `min_height` only ever takes the
values 5'9", 6'5" and 6'10", and `max_height` only 6'4", 6'9" and 7'4". There are therefore
exactly two cliffs. For a maxed build, package counts:

```
5'9" - 6'4"    1184     flat at every single inch
6'5" - 6'9"    1263     peak
6'10" - 7'4"    623     roughly half
```

**375 packages drop out at the single inch between 6'4" and 6'9"**, Motion styles losing the
most (71), then Dribble Pull-Up (50), Go-To Shot (26), Hop Jumper (26).

Going from 6'3" to 6'10" does not trade some animations for others. It costs about half of
everything the build can do. Most advice about bigs implies the opposite.

## 13. One animation in five is blocked by ceilings, not by its height range

**397 of 1,814 packages (21.9%)** are unreachable somewhere inside their own stated height
range, because no legal body at that height has a high enough attribute ceiling.

Kyrie Irving's dribble style is the clearest case: listed 5'9"-6'4", actually reachable only
to **6'2"**, blocked by `speed_with_ball`. Every published table says 6'4".

The largest narrowings:

```
Kevin Durant, Go-To Shot        stated 7'4"  real 6'6"   blocked by three_point
Taj Gibson, Motion styles       stated 7'4"  real 6'9"   agility
Franz Wagner, Breakdown Combo   stated 7'4"  real 6'9"   ball_handle
Elite Contact Dunks Off One     stated 7'4"  real 6'9"   driving_dunk
```

And one package is unreachable at **every** height in its stated range: Paolo Banchero's
Go-To Shot, needing 94 mid-range and 94 three-point on a 6'10"-7'4" body.

**An animation's height range is a necessary condition, not a sufficient one.** Any tool
that checks only the height gate will tell a player a build works when it cannot.

## 14. The ladder shows how much is routinely wasted

Ball handle at 6'4", showing only the gaps:

```
 25  52 packages
     14 points buying nothing
 40  22 packages
     19 points buying nothing        <- the largest dead zone in the attribute
 60  strong_handle bronze
      4 points buying nothing
 65  unpluckable bronze
```

**Nineteen consecutive points of ball handle, from 41 to 59, unlock nothing at all.** A build
sitting at 55 has thrown away fifteen points it could have spent elsewhere.

The same view for a centre's standing dunk at 7'0" shows the real breakpoints — 80 for Pro
Bigman Contact Dunks, 90 for Elite Bigman Contact Dunks and Wembanyama's package, 93 for
Aerial Wizard hall-of-fame, 99 for Rise Up hall-of-fame — with dead stretches between.

## Caveats carried forward

- The animation data is NBA2KLab's Community Day capture, now vendored under the same hash
  manifest as the engine data. Re-import with `python tools/vendor_local.py` if it changes.
- **Jumpshot bases and releases are absent entirely.** The file has no jumpshot entries.
  Shooting coverage is Dribble Pull-Up, Go-To Shot, Hop Jumper, Post Fade, Post Hop Shot and
  Spin Jumper only. This remains the single largest gap in the animation data.
- Reachability is computed against the best legal body at each height. A specific build with
  a heavier frame or shorter wingspan may fall short where the scan says the height works.
