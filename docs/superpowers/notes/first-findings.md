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

A build advertised as needing "94 Speed With Ball" actually requires four attributes:

| Attribute | Forced minimum | Why |
|---|---|---|
| Speed With Ball | 94 | the stated requirement |
| Speed | 94 | `SWB <= Speed + 0` |
| Ball Handle | 89 | `SWB <= BallControl + 5` |
| Agility | 79 | `SWB <= Agility + 15` |

Any build guide quoting only the Speed With Ball number is quoting roughly a quarter of
the real price.

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
