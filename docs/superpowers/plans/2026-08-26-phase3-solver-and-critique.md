# Phase 3: Constraint Solver and Build Critique Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given a set of goals — badge tiers, animations, attribute floors — find the cheapest legal build that meets them, say which heights it works at, and explain precisely why when it cannot be done. Then use the same machinery to critique a build somebody else proposed.

**Architecture:** Every badge and animation requirement in the data is a **lower bound**, so the cheapest build meeting a set of goals is the pointwise maximum of the implied floors, closed under the linked-attribute constraints. No search over attribute space is needed and the answer is exact. The only branching is the 40 badge tiers joined by `OR`, enumerated only for badges actually requested. Infeasibility is reported by naming the specific pair of goals that cannot coexist.

**Tech Stack:** Python 3.14 standard library only. `unittest` for tests. No pip installs, no third-party packages.

---

## Context the implementer needs

Phases 1a, 1b and 2 are merged. 212 tests pass. Available modules:

- `buildlab.sources` — `path_for(rel)`, `rows_for(rel)`, `verify()`. Raises `SourceError`.
- `buildlab.reference` — `attribute_names()` (21 snake_case, builder index order), `tuning_order()`, `TUNING_NAME` (snake_case -> tuning identifier), `legal_bodies()`.
- `buildlab.tables` — `bucket_for_inches(inches)`, `weight_buckets()`, `height_buckets()`.
- `buildlab.body` — `is_legal(position, height, weight, wingspan)`, `ceilings(height, weight, wingspan)` -> dict keyed by snake_case.
- `buildlab.ovr` — `overall(height_inches, values)`, `detailed(...)`, `archetype(...)`.
- `buildlab.constraints` — `rules_for(tuning_attribute, bucket)` -> list of `{"associated", "max_delta"}`, `effective_ceiling(...)`.
- `buildlab.badges` — `TIERS` (`bronze, silver, gold, hall_of_fame`), `DISCIPLINE_ORDER`, `definitions()`, `by_id`, `by_name`, `height_eligible`, `eligible_at_height`, `requirements_for(badge_id, tier)`, `meets`, `best_tier`, `unlocked`.
- `buildlab.tokens` — `cost_for`, `cost_of_loadout(loadout, height, cumulative=False)`, `TOKEN_DATA_HEIGHTS` (69-81), `has_token_data`, `contribution`, `earned`.
- `buildlab.capbreakers` — `SCENARIOS`, `REFERENCE_BODY`, `gain_for`, `max_rating_for`, `apply_all`.
- `buildlab.animations` — `packages()`, `by_name(name, family)`, `families()`, `available(values, height_inches, family=None)`, `requirements_of(name, family)`, `max_ceiling_at(height_inches, attribute)`, `reachable_at`, `reachable_range`.
- `buildlab.ladders` — `ATTRIBUTE_FLOOR` (25), `max_ceiling(attribute, height_inches)`, `ladder(attribute, height_inches)`, `dead_points(...)`, `full_cost_of(targets, height_inches)`.
- `buildlab.cli` — `main(argv)`, `parse_height(text)`, `_ft(inches)`, subcommands `eval`, `badges`, `animations`, `ladder`, `reachability`.

Codebase idioms — follow them:

- Table loaders are module-level functions decorated `@functools.lru_cache(maxsize=1)`.
- `KeyError` messages name the inputs and the valid range.
- **Refuse rather than guess** where data is untrustworthy or a promise cannot be kept. See `docs/superpowers/notes/error-conventions.md` for the four established cases.

### The insight that makes this tractable

Verified against the real data:

- **Every badge tier requirement is a `minimum`.** All 212 rows, no exceptions.
- **Every animation requirement is a `minimum`.** All 1,814 rows.
- Badge requirement lists hold 1 or 2 entries. **40 of 212 join two entries with `OR`**; the remaining 296 operators are `AND`.
- Animation requirements are always conjunctive — 826 packages gate on two attributes, none on three, and there is never a choice to make.

Because every constraint is a lower bound, **the minimum-cost build satisfying a set of goals is the pointwise maximum of the implied floors**, then closed under linked attribute constraints via `ladders.full_cost_of`. There is nothing to search. An `OR` badge tier is the one place a choice exists, and only for badges the caller actually asks for.

### What "cost" means here, and what it does not

The tuning file contains `VCRequiredToBuyRangeOfAttributes` and `AttributePriceCapOverMaxRatioToMultiplierLerp`, but **no verified model of VC pricing exists in this project** and phase 1's derivation explicitly rejected the price-cap curve as part of the overall-rating formula.

So this plan uses two honest, computable costs and reports both:

- **`points`** — the sum of `(value - 25)` across all 21 attributes. Every attribute starts at 25, so this is literally how many upgrades the build needs. It is exact.
- **`overall`** — the displayed rating from `ovr.overall`. Also exact.

Neither is VC. Do not invent a VC figure, and do not present `points` as if it were the in-game currency.

### Facts the solver must respect

1. **Linked attribute constraints chain.** `speed_with_ball <= speed + 0` is a hard lock, plus `<= ball_handle + 5` and `<= agility + 15`. Following the chain, 94 speed with ball forces 12 attributes above the floor at 6'2" and 20 at 7'0". `ladders.full_cost_of` already does this closure.
2. **A stated animation height range is not the real one.** 397 of 1,722 packages with attribute requirements are unreachable somewhere inside their published range. Use `animations.reachable_at`, never the raw `min_height`/`max_height`.
3. **Badge legend tier is unreachable at build creation** and has no attribute requirements at all. `badges.requirements_for(badge_id, "legend")` raises. The solver must reject a legend goal with a clear message rather than crashing.
4. **Token data is missing above 6'9".** `tokens.earned` raises for heights 82-88. A solver result at those heights must report tokens as unavailable, not zero.

---

## File structure

| File | Responsibility |
|---|---|
| `buildlab/goals.py` | Goal types and their conversion to attribute floors |
| `buildlab/solver.py` | Feasibility, the minimal build, height search, infeasibility diagnosis |
| `buildlab/critique.py` | Evaluate a proposed build; check claims; find waste |
| `buildlab/cli.py` | Add `solve` and `critique` subcommands (modify) |
| `tests/test_goals.py` | Goal parsing and floor derivation |
| `tests/test_solver.py` | Solving, infeasibility, height search |
| `tests/test_critique.py` | Critique output |
| `tests/test_cli.py` | Coverage for the two new subcommands (modify) |

`goals.py` depends on `badges`, `animations` and `reference`. `solver.py` depends on `goals`, `ladders`, `body`, `ovr` and `animations`. `critique.py` depends on `solver`, `ladders`, `badges` and `ovr`.

---

## Task 1: Goals and their attribute floors

A goal is one of three things. Each converts to a set of attribute floors, or to a set of alternative floor-sets when the goal has an `OR`.

**Files:**
- Create: `buildlab/goals.py`
- Create: `tests/test_goals.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_goals.py`:

```python
import unittest

from buildlab import goals


class TestGoalTypes(unittest.TestCase):
    def test_attribute_goal_is_its_own_floor(self):
        goal = goals.AttributeGoal("three_point", 90)
        self.assertEqual(goal.floor_options(height_inches=75), [{"three_point": 90}])

    def test_attribute_goal_rejects_an_unknown_name(self):
        with self.assertRaises(KeyError):
            goals.AttributeGoal("nonsense", 90).floor_options(height_inches=75)

    def test_animation_goal_uses_the_package_requirements(self):
        goal = goals.AnimationGoal("Kyrie Irving", "Dribble Style")
        self.assertEqual(
            goal.floor_options(height_inches=74), [{"speed_with_ball": 94}]
        )

    def test_animation_goal_rejects_an_unknown_package(self):
        with self.assertRaises(KeyError):
            goals.AnimationGoal("Not Real", "Dribble Style").floor_options(
                height_inches=75
            )

    def test_and_badge_goal_yields_one_option_with_both_floors(self):
        # posterizer bronze joins two attributes with AND, verified.
        goal = goals.BadgeGoal("posterizer", "bronze")
        options = goal.floor_options(height_inches=75)
        self.assertEqual(len(options), 1)
        self.assertEqual(len(options[0]), 2)

    def test_or_badge_goal_yields_two_options(self):
        goal = goals.BadgeGoal("float_game", "bronze")
        options = goal.floor_options(height_inches=75)
        self.assertEqual(len(options), 2)
        self.assertIn({"close_shot": 65}, options)
        self.assertIn({"driving_layup": 65}, options)

    def test_badge_goal_rejects_legend(self):
        with self.assertRaises(ValueError):
            goals.BadgeGoal("float_game", "legend").floor_options(height_inches=75)

    def test_badge_goal_rejects_an_unknown_tier(self):
        with self.assertRaises(ValueError):
            goals.BadgeGoal("float_game", "platinum").floor_options(height_inches=75)

    def test_badge_goal_out_of_height_range_yields_nothing(self):
        # mini_marksman is guard-only; at 7'4" it cannot be had at any cost.
        goal = goals.BadgeGoal("mini_marksman", "bronze")
        self.assertEqual(goal.floor_options(height_inches=88), [])

    def test_animation_goal_out_of_height_range_yields_nothing(self):
        goal = goals.AnimationGoal("Kyrie Irving", "Dribble Style")
        self.assertEqual(goal.floor_options(height_inches=80), [])

    def test_animation_goal_respects_reachability_not_just_the_stated_range(self):
        # Stated range runs to 6'4" but the ceiling blocks it above 6'2".
        goal = goals.AnimationGoal("Kyrie Irving", "Dribble Style")
        self.assertEqual(goal.floor_options(height_inches=74), [{"speed_with_ball": 94}])
        self.assertEqual(goal.floor_options(height_inches=75), [])

    def test_describe_is_human_readable(self):
        self.assertIn("three_point", goals.AttributeGoal("three_point", 90).describe())
        self.assertIn("float_game", goals.BadgeGoal("float_game", "gold").describe())
        self.assertIn(
            "Kyrie Irving",
            goals.AnimationGoal("Kyrie Irving", "Dribble Style").describe(),
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_goals -v`
Expected: FAIL with `ImportError: cannot import name 'goals'`

- [ ] **Step 3: Write the implementation**

Create `buildlab/goals.py`:

```python
"""Build goals and the attribute floors they imply.

Every badge and animation requirement in the data is a lower bound, so a goal
converts to a set of attribute floors. A goal whose requirement uses OR
converts to several alternative floor sets, and the solver picks the cheapest.
"""

from buildlab import animations, badges, reference


class Goal:
    """Base class. Subclasses return a list of alternative floor dicts.

    An empty list means the goal is impossible at that height — not that it is
    free. Callers must distinguish those.
    """

    def floor_options(self, height_inches):
        raise NotImplementedError

    def describe(self):
        raise NotImplementedError


class AttributeGoal(Goal):
    """A bare attribute floor, e.g. three_point at least 90."""

    def __init__(self, attribute, minimum):
        self.attribute = attribute
        self.minimum = minimum

    def floor_options(self, height_inches):
        names = reference.attribute_names()
        if self.attribute not in names:
            raise KeyError(
                f"no builder attribute named {self.attribute!r}; "
                f"valid names are {names}"
            )
        return [{self.attribute: self.minimum}]

    def describe(self):
        return f"{self.attribute} >= {self.minimum}"


class BadgeGoal(Goal):
    """A badge at a tier."""

    def __init__(self, badge_name, tier):
        self.badge_name = badge_name
        self.tier = tier

    def floor_options(self, height_inches):
        if self.tier not in badges.TIERS:
            raise ValueError(
                f"{self.tier!r} is not a tier that attributes can reach; "
                f"valid tiers are {badges.TIERS}. Legend is not purchasable at "
                "build creation and has no attribute requirements."
            )
        badge = badges.by_name(self.badge_name)
        if not badges.height_eligible(badge["badge"], height_inches):
            return []
        requirements = badges.requirements_for(badge["badge"], self.tier)
        if len(requirements) == 1:
            entry = requirements[0]
            return [{entry["name"]: entry["minimum"]}]
        first, second = requirements
        if first["operator_to_next"] == "OR":
            return [
                {first["name"]: first["minimum"]},
                {second["name"]: second["minimum"]},
            ]
        return [
            {
                first["name"]: first["minimum"],
                second["name"]: second["minimum"],
            }
        ]

    def describe(self):
        return f"{self.badge_name} {self.tier}"


class AnimationGoal(Goal):
    """An animation package, gated by reachability rather than the stated range."""

    def __init__(self, name, family):
        self.name = name
        self.family = family

    def floor_options(self, height_inches):
        row = animations.by_name(self.name, self.family)
        if not animations.reachable_at(self.name, self.family, height_inches):
            return []
        return [dict(row["requirements"])]

    def describe(self):
        return f"{self.family}: {self.name}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_goals -v`
Expected: `OK`, 12 tests

If `test_and_badge_goal_yields_one_option_with_both_floors` fails because `posterizer` bronze is not an AND badge, find one with
`python -c "from buildlab import badges; print([(r['name'], r['tier']) for r in badges.tier_requirements() if len(r['requirements'])==2 and r['requirements'][0]['operator_to_next']=='AND'][:5])"`
and use a real one. Report which you used.

- [ ] **Step 5: Commit**

```bash
git add buildlab/goals.py tests/test_goals.py && git commit -m "feat: build goals and the attribute floors they imply"
```

---

## Task 2: The solver core

**Files:**
- Create: `buildlab/solver.py`
- Create: `tests/test_solver.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_solver.py`:

```python
import unittest

from buildlab import goals, ladders, solver


class TestSolveAtHeight(unittest.TestCase):
    def test_a_single_attribute_goal_produces_that_floor(self):
        result = solver.solve_at([goals.AttributeGoal("three_point", 90)], 75)
        self.assertTrue(result["feasible"])
        self.assertGreaterEqual(result["build"]["three_point"], 90)

    def test_the_build_is_a_full_21_attribute_vector(self):
        result = solver.solve_at([goals.AttributeGoal("three_point", 90)], 75)
        self.assertEqual(len(result["build"]), 21)
        for value in result["build"].values():
            self.assertGreaterEqual(value, ladders.ATTRIBUTE_FLOOR)

    def test_linked_constraints_are_included_in_the_build(self):
        result = solver.solve_at(
            [goals.AttributeGoal("speed_with_ball", 94)], 74
        )
        self.assertTrue(result["feasible"])
        self.assertGreaterEqual(result["build"]["speed"], 94)
        self.assertGreaterEqual(result["build"]["ball_handle"], 89)
        self.assertGreaterEqual(result["build"]["agility"], 79)

    def test_points_and_overall_are_reported(self):
        result = solver.solve_at([goals.AttributeGoal("three_point", 90)], 75)
        self.assertIn("points", result)
        self.assertIn("overall", result)
        self.assertGreater(result["points"], 0)
        self.assertGreaterEqual(result["overall"], 25)

    def test_an_impossible_attribute_is_infeasible(self):
        # standing_dunk is capped at 51 on the best 6'3" body.
        result = solver.solve_at([goals.AttributeGoal("standing_dunk", 90)], 75)
        self.assertFalse(result["feasible"])
        self.assertIn("standing_dunk", result["reason"])

    def test_infeasibility_names_the_ceiling(self):
        result = solver.solve_at([goals.AttributeGoal("standing_dunk", 90)], 75)
        self.assertIn("ceiling", result["reason"].lower())

    def test_an_out_of_range_goal_is_infeasible_with_its_name(self):
        result = solver.solve_at([goals.BadgeGoal("mini_marksman", "bronze")], 88)
        self.assertFalse(result["feasible"])
        self.assertIn("mini_marksman", result["reason"])

    def test_an_or_goal_picks_the_cheaper_branch(self):
        # float_game bronze is close_shot 65 OR driving_layup 65. Both are
        # reachable, so the solver must choose one and not demand both.
        result = solver.solve_at([goals.BadgeGoal("float_game", "bronze")], 75)
        self.assertTrue(result["feasible"])
        build = result["build"]
        self.assertTrue(build["close_shot"] >= 65 or build["driving_layup"] >= 65)

    def test_two_goals_take_the_pointwise_maximum(self):
        result = solver.solve_at(
            [
                goals.AttributeGoal("three_point", 90),
                goals.AttributeGoal("three_point", 80),
            ],
            75,
        )
        self.assertGreaterEqual(result["build"]["three_point"], 90)

    def test_empty_goals_gives_a_floor_build(self):
        result = solver.solve_at([], 75)
        self.assertTrue(result["feasible"])
        self.assertEqual(result["points"], 0)
        self.assertEqual(
            set(result["build"].values()), {ladders.ATTRIBUTE_FLOOR}
        )


class TestSolveAcrossHeights(unittest.TestCase):
    def test_kyrie_dribble_style_only_works_to_six_two(self):
        result = solver.solve([goals.AnimationGoal("Kyrie Irving", "Dribble Style")])
        self.assertTrue(result["feasible"])
        self.assertEqual(result["heights"][-1], 74)

    def test_the_cheapest_height_is_reported(self):
        result = solver.solve([goals.AttributeGoal("three_point", 90)])
        self.assertIn("best", result)
        self.assertIn(result["best"]["height_inches"], result["heights"])

    def test_impossible_everywhere_is_reported_not_crashed(self):
        result = solver.solve(
            [
                goals.AnimationGoal("Kyrie Irving", "Dribble Style"),
                goals.BadgeGoal("paint_patroller", "gold"),
            ]
        )
        self.assertFalse(result["feasible"])
        self.assertTrue(result["reason"])

    def test_conflicting_goals_name_both_sides(self):
        # A guard-only animation and a big-only badge cannot coexist.
        result = solver.solve(
            [
                goals.AnimationGoal("Kyrie Irving", "Dribble Style"),
                goals.BadgeGoal("paint_patroller", "gold"),
            ]
        )
        self.assertIn("Kyrie Irving", result["reason"])
        self.assertIn("paint_patroller", result["reason"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_solver -v`
Expected: FAIL with `ImportError: cannot import name 'solver'`

- [ ] **Step 3: Write the implementation**

Create `buildlab/solver.py`:

```python
"""Find the cheapest legal build meeting a set of goals.

Every requirement in the data is a lower bound, so the cheapest build is the
pointwise maximum of the implied floors, closed under linked attribute
constraints. Nothing is searched over attribute space. The only branching is a
badge tier whose requirement uses OR, and only for badges actually requested.
"""

import itertools

from buildlab import animations, ladders, ovr, reference

# Heights any legal build can have. Matches the union of the five positions'
# ranges from reference.legal_bodies().
MIN_HEIGHT = 69
MAX_HEIGHT = 88


def _best_ceilings(height_inches):
    """Best reachable ceiling per attribute at a height, across legal bodies."""
    return {
        name: animations.max_ceiling_at(height_inches, name)
        for name in reference.attribute_names()
    }


def _merge(options):
    """Pointwise maximum of several floor dicts."""
    merged = {}
    for option in options:
        for attribute, minimum in option.items():
            if minimum > merged.get(attribute, 0):
                merged[attribute] = minimum
    return merged


def solve_at(goal_list, height_inches):
    """Cheapest build meeting every goal at one height.

    Returns a dict with `feasible`, and on success `build` (all 21 attributes),
    `points` (upgrades above the 25 floor), `overall`, and `height_inches`. On
    failure, `reason` explains which goal cannot be met and why.
    """
    per_goal = []
    for goal in goal_list:
        options = goal.floor_options(height_inches)
        if not options:
            return {
                "feasible": False,
                "height_inches": height_inches,
                "reason": (
                    f"{goal.describe()} is not attainable at "
                    f"{height_inches // 12}'{height_inches % 12}"
                ),
            }
        per_goal.append(options)

    ceilings = _best_ceilings(height_inches)
    best = None
    for combination in itertools.product(*per_goal) if per_goal else [()]:
        floors = _merge(combination)
        closed = ladders.full_cost_of(floors, height_inches)
        over = [
            (attribute, minimum)
            for attribute, minimum in closed.items()
            if minimum > ceilings.get(attribute, 0)
        ]
        if over:
            continue
        build = {
            name: max(closed.get(name, 0), ladders.ATTRIBUTE_FLOOR)
            for name in reference.attribute_names()
        }
        points = sum(v - ladders.ATTRIBUTE_FLOOR for v in build.values())
        candidate = {
            "feasible": True,
            "height_inches": height_inches,
            "build": build,
            "points": points,
            "overall": ovr.overall(
                height_inches, [build[n] for n in reference.attribute_names()]
            ),
        }
        if best is None or candidate["points"] < best["points"]:
            best = candidate

    if best is not None:
        return best

    # Nothing worked. Report the attribute that exceeded its ceiling by most,
    # using the first combination, which is representative enough to explain.
    floors = _merge(list(itertools.product(*per_goal))[0]) if per_goal else {}
    closed = ladders.full_cost_of(floors, height_inches)
    worst = None
    for attribute, minimum in closed.items():
        excess = minimum - ceilings.get(attribute, 0)
        if worst is None or excess > worst[1]:
            worst = (attribute, excess, minimum, ceilings.get(attribute, 0))
    reason = (
        f"needs {worst[0]} {worst[2]} but the ceiling at "
        f"{height_inches // 12}'{height_inches % 12} is {worst[3]}"
    )
    return {"feasible": False, "height_inches": height_inches, "reason": reason}


def solve(goal_list, heights=None):
    """Cheapest build meeting every goal, searched across heights.

    Returns `feasible`, `heights` (every height that works, ascending), `best`
    (the cheapest solve_at result by points, ties broken by lower height), and
    `per_height`. On total failure, `reason` names the goals that conflict.
    """
    candidates = heights or range(MIN_HEIGHT, MAX_HEIGHT + 1)
    per_height = {}
    working = []
    for height in candidates:
        outcome = solve_at(goal_list, height)
        per_height[height] = outcome
        if outcome["feasible"]:
            working.append(height)

    if working:
        best = min(
            (per_height[h] for h in working),
            key=lambda r: (r["points"], r["height_inches"]),
        )
        return {
            "feasible": True,
            "heights": working,
            "best": best,
            "per_height": per_height,
        }

    return {
        "feasible": False,
        "heights": [],
        "per_height": per_height,
        "reason": _diagnose(goal_list, candidates),
    }


def _diagnose(goal_list, candidates):
    """Explain why no height works, naming a conflicting pair when there is one."""
    reachable = {}
    for goal in goal_list:
        reachable[goal.describe()] = {
            h for h in candidates if goal.floor_options(h)
        }

    empty = [name for name, heights in reachable.items() if not heights]
    if empty:
        return f"{empty[0]} is not attainable at any legal height"

    names = list(reachable)
    for first, second in itertools.combinations(names, 2):
        if not reachable[first] & reachable[second]:
            return (
                f"{first} and {second} cannot coexist: "
                f"they share no legal height"
            )

    return (
        "no single height satisfies every goal; each is individually "
        "attainable but the attribute ceilings do not allow them together"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_solver -v`
Expected: `OK`, 14 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 238 tests, OK.

**If `test_kyrie_dribble_style_only_works_to_six_two` fails**, print the reachable range with
`python -c "from buildlab import animations; print(animations.reachable_range('Kyrie Irving','Dribble Style'))"`
and report rather than adjusting. The value 74 was measured directly.

**If `test_conflicting_goals_name_both_sides` fails because `paint_patroller` is reachable at 6'2"**, find a genuinely big-only badge with
`python -c "from buildlab import badges; print([(b['name'], b['height_inches']) for b in badges.definitions() if b['height_inches'][0] >= 77])"`
and use one whose minimum height exceeds 74. Report which you used.

- [ ] **Step 5: Commit**

```bash
git add buildlab/solver.py tests/test_solver.py && git commit -m "feat: constraint solver over attribute floors"
```

---

## Task 3: The `solve` CLI command

**Files:**
- Modify: `buildlab/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`, before the `if __name__` block:

```python
class TestSolveCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_solve_with_an_attribute_goal(self):
        code, out = self.run_cli(["solve", "--attribute", "three_point=90"])
        self.assertEqual(code, 0)
        self.assertIn("FEASIBLE", out)
        self.assertIn("three_point", out)

    def test_solve_with_a_badge_goal(self):
        code, out = self.run_cli(["solve", "--badge", "float_game=gold"])
        self.assertEqual(code, 0)
        self.assertIn("FEASIBLE", out)

    def test_solve_with_an_animation_goal(self):
        code, out = self.run_cli(
            ["solve", "--animation", "Dribble Style:Kyrie Irving"]
        )
        self.assertEqual(code, 0)
        self.assertIn("6-2", out)

    def test_solve_reports_infeasibility(self):
        code, out = self.run_cli(
            [
                "solve",
                "--animation",
                "Dribble Style:Kyrie Irving",
                "--badge",
                "paint_patroller=gold",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("NOT FEASIBLE", out)

    def test_solve_rejects_a_malformed_goal(self):
        code, out = self.run_cli(["solve", "--attribute", "three_point"])
        self.assertEqual(code, 2)

    def test_solve_accepts_a_fixed_height(self):
        code, out = self.run_cli(
            ["solve", "--attribute", "three_point=90", "--height", "6-3"]
        )
        self.assertEqual(code, 0)
        self.assertIn("6-3", out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL — `argparse` rejects `solve` as an invalid choice

- [ ] **Step 3: Write the implementation**

Add `solver` and `goals` to the import list at the top of `buildlab/cli.py`, so it reads:

```python
from buildlab import (
    animations as animations_mod,
    badges as badges_mod,
    goals as goals_mod,
    ladders,
    ovr,
    reference,
    solver,
    tokens,
)
```

Add after `_reachability`:

```python
def _parse_goals(args):
    """Turn --attribute/--badge/--animation strings into Goal objects."""
    built = []
    for spec in args.attribute or []:
        name, sep, minimum = spec.partition("=")
        if not sep or not minimum.isdigit():
            raise ValueError(f"--attribute wants name=value, got {spec!r}")
        built.append(goals_mod.AttributeGoal(name.strip(), int(minimum)))
    for spec in args.badge or []:
        name, sep, tier = spec.partition("=")
        if not sep:
            raise ValueError(f"--badge wants name=tier, got {spec!r}")
        built.append(goals_mod.BadgeGoal(name.strip(), tier.strip()))
    for spec in args.animation or []:
        family, sep, name = spec.partition(":")
        if not sep:
            raise ValueError(f"--animation wants Family:Name, got {spec!r}")
        built.append(goals_mod.AnimationGoal(name.strip(), family.strip()))
    return built


def _solve(args):
    try:
        goal_list = _parse_goals(args)
    except ValueError as error:
        print(f"error: {error}")
        return 2
    if not goal_list:
        print("error: give at least one --attribute, --badge or --animation goal")
        return 2

    heights = None
    if args.height is not None:
        heights = [parse_height(args.height)]

    try:
        result = solver.solve(goal_list, heights=heights)
    except (KeyError, ValueError) as error:
        print(f"error: {error}")
        return 2

    print("GOALS")
    for goal in goal_list:
        print(f"  {goal.describe()}")
    print()

    if not result["feasible"]:
        print("NOT FEASIBLE")
        print(f"  {result['reason']}")
        return 0

    best = result["best"]
    low, high = result["heights"][0], result["heights"][-1]
    print(f"FEASIBLE   {_ft(low)} to {_ft(high)}")
    print(
        f"CHEAPEST   {_ft(best['height_inches'])}   "
        f"{best['points']} upgrade points   overall {best['overall']}"
    )
    print()
    for name in reference.attribute_names():
        value = best["build"][name]
        if value > ladders.ATTRIBUTE_FLOOR:
            print(f"  {name:<20} {value}")
    return 0
```

Register it in `main`, before `args = parser.parse_args(argv)`:

```python
    sv = sub.add_parser("solve", help="find the cheapest build meeting goals")
    sv.add_argument(
        "--attribute", action="append", help="name=value, repeatable"
    )
    sv.add_argument("--badge", action="append", help="name=tier, repeatable")
    sv.add_argument(
        "--animation", action="append", help="Family:Name, repeatable"
    )
    sv.add_argument("--height", default=None, help="fix the height, e.g. 6-3")
    sv.set_defaults(func=_solve)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli -v`
Expected: `OK`, 22 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 244 tests, OK.

- [ ] **Step 5: Run it for real**

```bash
python -m buildlab.cli solve --animation "Dribble Style:Kyrie Irving" --badge "ankle_assassin=gold"
```

```bash
python -m buildlab.cli solve --attribute three_point=95 --attribute perimeter_defense=90 --height 6-6
```

Paste both outputs in your report.

- [ ] **Step 6: Commit**

```bash
git add buildlab/cli.py tests/test_cli.py && git commit -m "feat: add the solve subcommand"
```

---

## Task 4: Build critique

Evaluate a build somebody else proposed: what it unlocks, what it wastes, and whether stated claims about it hold.

**Files:**
- Create: `buildlab/critique.py`
- Create: `tests/test_critique.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_critique.py`:

```python
import unittest

from buildlab import critique


class TestCritique(unittest.TestCase):
    def setUp(self):
        self.values = [70] * 21
        self.values[6] = 90  # three_point
        self.values[9] = 88  # ball_handle: 87 is an unlock, 88 wastes one

    def test_report_has_the_expected_sections(self):
        report = critique.critique(self.values, height_inches=76)
        for key in ("overall", "archetype", "badges", "waste", "unspecified"):
            self.assertIn(key, report)

    def test_overall_matches_the_engine(self):
        from buildlab import ovr

        report = critique.critique(self.values, height_inches=76)
        self.assertEqual(report["overall"], ovr.overall(76, self.values))

    def test_waste_finds_dead_points(self):
        report = critique.critique(self.values, height_inches=76)
        wasted = {w["attribute"]: w for w in report["waste"]}
        self.assertIn("ball_handle", wasted)
        self.assertGreater(wasted["ball_handle"]["wasted"], 0)

    def test_waste_reports_the_next_unlock(self):
        report = critique.critique(self.values, height_inches=76)
        for entry in report["waste"]:
            with self.subTest(attribute=entry["attribute"]):
                self.assertIn("next_unlock_at", entry)

    def test_a_value_above_the_ceiling_is_flagged(self):
        values = [70] * 21
        values[3] = 95  # standing_dunk, ceiling is far below this at 6'4"
        report = critique.critique(values, height_inches=76)
        self.assertTrue(report["illegal"])
        self.assertIn("standing_dunk", str(report["illegal"]))

    def test_a_legal_build_has_no_illegal_entries(self):
        report = critique.critique([30] * 21, height_inches=76)
        self.assertEqual(report["illegal"], [])

    def test_rejects_a_wrong_length_vector(self):
        with self.assertRaises(ValueError):
            critique.critique([70] * 20, height_inches=76)


class TestClaims(unittest.TestCase):
    def test_a_true_badge_claim_is_confirmed(self):
        values = [99] * 21
        checked = critique.check_claims(
            values, height_inches=76, claims=[("ankle_assassin", "hall_of_fame")]
        )
        self.assertTrue(checked[0]["holds"])

    def test_a_false_badge_claim_is_refuted_with_the_real_tier(self):
        values = [70] * 21
        checked = critique.check_claims(
            values, height_inches=76, claims=[("ankle_assassin", "hall_of_fame")]
        )
        self.assertFalse(checked[0]["holds"])
        self.assertIn("actual", checked[0])

    def test_an_unreachable_claim_is_refuted(self):
        values = [99] * 21
        checked = critique.check_claims(
            values, height_inches=88, claims=[("mini_marksman", "bronze")]
        )
        self.assertFalse(checked[0]["holds"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_critique -v`
Expected: FAIL with `ImportError: cannot import name 'critique'`

- [ ] **Step 3: Write the implementation**

Create `buildlab/critique.py`:

```python
"""Evaluate a build somebody else proposed."""

from buildlab import animations, badges, ladders, ovr, reference


def critique(values, height_inches):
    """Full report on a proposed build.

    Returns `overall`, `archetype`, `badges` (id -> tier), `waste` (attributes
    with points buying nothing), `illegal` (attributes above their ceiling) and
    `unspecified` (attributes still at the floor, which a transcript probably
    just did not mention).
    """
    if len(values) != 21:
        raise ValueError(f"expected 21 attribute values, got {len(values)}")

    names = reference.attribute_names()
    illegal = []
    waste = []
    unspecified = []
    for index, name in enumerate(names):
        value = values[index]
        ceiling = animations.max_ceiling_at(height_inches, name)
        if value > ceiling:
            illegal.append(
                {"attribute": name, "value": value, "ceiling": ceiling}
            )
            continue
        if value <= ladders.ATTRIBUTE_FLOOR:
            unspecified.append(name)
            continue
        dead = ladders.dead_points(name, height_inches, value)
        if dead["wasted"] > 0:
            waste.append(
                {
                    "attribute": name,
                    "value": value,
                    "wasted": dead["wasted"],
                    "last_unlock_at": dead["last_unlock_at"],
                    "next_unlock_at": dead["next_unlock_at"],
                }
            )

    return {
        "height_inches": height_inches,
        "overall": ovr.overall(height_inches, values),
        "archetype": ovr.archetype(height_inches, values),
        "badges": badges.unlocked(values, height_inches),
        "waste": sorted(waste, key=lambda w: -w["wasted"]),
        "illegal": illegal,
        "unspecified": unspecified,
    }


def check_claims(values, height_inches, claims):
    """Check stated badge claims against what the build actually reaches.

    `claims` is a list of (badge_name, tier). Each result carries `badge`,
    `claimed`, `holds` and, when it does not hold, `actual` — the tier the
    build really reaches, or None.
    """
    checked = []
    for badge_name, tier in claims:
        badge = badges.by_name(badge_name)
        actual = badges.best_tier(badge["badge"], values, height_inches)
        holds = actual == tier
        entry = {"badge": badge_name, "claimed": tier, "holds": holds}
        if not holds:
            entry["actual"] = actual
        checked.append(entry)
    return checked
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_critique -v`
Expected: `OK`, 10 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 254 tests, OK.

**If `test_waste_finds_dead_points` fails**, print the ladder around 87 with
`python -c "from buildlab import ladders; print([s['rating'] for s in ladders.ladder('ball_handle', 76)])"`
and pick a value that genuinely sits in a gap. Report which you used and why.

- [ ] **Step 5: Commit**

```bash
git add buildlab/critique.py tests/test_critique.py && git commit -m "feat: critique a proposed build"
```

---

## Task 5: The `critique` CLI command

**Files:**
- Modify: `buildlab/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`, before the `if __name__` block:

```python
class TestCritiqueCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_critique_reports_overall_and_waste(self):
        values = ",".join(["70"] * 21)
        code, out = self.run_cli(
            ["critique", "--height", "6-4", "--values", values]
        )
        self.assertEqual(code, 0)
        self.assertIn("OVERALL", out)
        self.assertIn("WASTED", out)

    def test_critique_checks_a_claim(self):
        values = ",".join(["70"] * 21)
        code, out = self.run_cli(
            [
                "critique", "--height", "6-4", "--values", values,
                "--claim", "ankle_assassin=hall_of_fame",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("CLAIMS", out)
        self.assertIn("does not hold", out.lower())

    def test_critique_rejects_wrong_attribute_count(self):
        code, out = self.run_cli(
            ["critique", "--height", "6-4", "--values", "70,70"]
        )
        self.assertEqual(code, 2)

    def test_critique_flags_an_illegal_value(self):
        values = ["70"] * 21
        values[3] = "95"
        code, out = self.run_cli(
            ["critique", "--height", "6-4", "--values", ",".join(values)]
        )
        self.assertEqual(code, 0)
        self.assertIn("ABOVE THE CEILING", out.upper())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL — `argparse` rejects `critique`

- [ ] **Step 3: Write the implementation**

Add `critique as critique_mod` to the import list in `buildlab/cli.py`.

Add after `_solve`:

```python
def _critique(args):
    values = [int(v) for v in args.values.split(",")]
    if len(values) != 21:
        print(f"error: expected 21 attribute values, got {len(values)}")
        return 2
    height = parse_height(args.height)
    report = critique_mod.critique(values, height)

    print(f"HEIGHT     {args.height}  ({height} in)")
    print(f"OVERALL    {report['overall']}   archetype {report['archetype']}")
    print(f"BADGES     {len(report['badges'])} unlocked")
    print()

    if report["illegal"]:
        print("ABOVE THE CEILING — this build cannot be made:")
        for entry in report["illegal"]:
            print(
                f"  {entry['attribute']:<20} {entry['value']} "
                f"but the ceiling here is {entry['ceiling']}"
            )
        print()

    total_wasted = sum(entry["wasted"] for entry in report["waste"])
    print(f"WASTED     {total_wasted} points buying nothing")
    for entry in report["waste"]:
        nxt = entry["next_unlock_at"]
        tail = f", next unlock at {nxt}" if nxt is not None else ", nothing further"
        print(
            f"  {entry['attribute']:<20} {entry['value']} "
            f"({entry['wasted']} wasted{tail})"
        )
    print()

    if report["unspecified"]:
        print(f"AT THE FLOOR  {len(report['unspecified'])} attributes")
        print(f"  {', '.join(report['unspecified'])}")
        print()

    if args.claim:
        claims = []
        for spec in args.claim:
            name, sep, tier = spec.partition("=")
            if not sep:
                print(f"error: --claim wants name=tier, got {spec!r}")
                return 2
            claims.append((name.strip(), tier.strip()))
        print("CLAIMS")
        for checked in critique_mod.check_claims(values, height, claims):
            if checked["holds"]:
                print(f"  {checked['badge']} {checked['claimed']}  holds")
            else:
                actual = checked.get("actual") or "nothing"
                print(
                    f"  {checked['badge']} {checked['claimed']}  "
                    f"does not hold — actually reaches {actual}"
                )
    return 0
```

Register it in `main`, before `args = parser.parse_args(argv)`:

```python
    cr = sub.add_parser("critique", help="evaluate a build somebody proposed")
    cr.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    cr.add_argument("--values", required=True, help="21 comma-separated ratings")
    cr.add_argument(
        "--claim", action="append", help="name=tier to check, repeatable"
    )
    cr.set_defaults(func=_critique)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli -v`
Expected: `OK`, 26 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 258 tests, OK.

- [ ] **Step 5: Run it for real**

```bash
python -m buildlab.cli critique --height 6-4 --values 70,70,70,70,70,80,90,70,70,87,80,70,80,70,70,70,70,80,80,70,70 --claim "ankle_assassin=hall_of_fame"
```

Paste the output in your report.

- [ ] **Step 6: Commit**

```bash
git add buildlab/cli.py tests/test_cli.py && git commit -m "feat: add the critique subcommand"
```

---

## Definition of done

- `python -m unittest discover -s tests` passes with no failures and no skips.
- `python -m buildlab.cli solve --animation "Dribble Style:Kyrie Irving"` reports feasible only up to 6'2".
- `python -m buildlab.cli solve` with a guard animation and a big-only badge reports NOT FEASIBLE and names both.
- `python -m buildlab.cli critique` reports overall, wasted points and claim checks.
- `buildlab.sources.verify()` still passes.
- No third-party imports anywhere in `buildlab/`, `tools/` or `tests/`.

## Explicitly not in this plan

The data refresh command, the animation quality ratings layer, and the web UI — those are plans 4 and 5.

Also excluded: **any VC cost model.** The tuning file has VC keys but no verified pricing formula exists in this project, and phase 1's derivation explicitly rejected the price-cap curve as part of the overall-rating maths. `points` and `overall` are the two honest costs. Do not invent a third.
