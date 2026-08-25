# Phase 1b: Badges, Tokens and Cap Breakers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given a build, report exactly which badges it unlocks at which tier, what those badges cost in tokens, how many tokens the build earns, and how cap breakers change its ceilings.

**Architecture:** Pure lookup and predicate evaluation over data already vendored in phase 1. Three focused modules — `badges` (eligibility and tiers), `tokens` (earning and spending) and `capbreakers` (ceiling gains) — plus a `badges` CLI subcommand. No new data downloads: all five source files are already in the manifest and hash-verified.

**Tech Stack:** Python 3.14 standard library only. `unittest` for tests. No pip installs, no third-party packages.

---

## Context the implementer needs

Phase 1 is merged to `main` and provides a verified engine. Available modules:

- `buildlab.sources` — `path_for(rel)` -> `pathlib.Path`, manifest-gated. `verify()`. Raises `SourceError`.
- `buildlab.tuning` — `load()` -> flat `dict[str, str]`, 16,008 keys.
- `buildlab.reference` — `attributes()`, `attribute_names()` (21 snake_case, index order), `tuning_order()` (21 tuning identifiers, same order), `TUNING_NAME`, `legal_bodies()`.
- `buildlab.tables` — `height_buckets()`, `bucket_for_inches(inches)`, `weight_buckets()` (5-24), `player_types()`, `weights()`, `scale_for()`, `lerp_points()`, `lerp()`.
- `buildlab.body` — `is_legal(position, height, weight, wingspan)` -> bool, `ceilings(height, weight, wingspan)` -> `dict[str, int]` keyed by snake_case name.
- `buildlab.archetypes` — `names()`, `minimums()`, `raw_score()`, `scaled_score()`, `select()`, `select_baseline()`.
- `buildlab.ovr` — `overall(height_inches, values)` -> int, `detailed(...)` -> float, `archetype(...)` -> int.
- `buildlab.constraints` — `load()`, `rules_for(attr, bucket)`, `effective_ceiling(attr, bucket, values, hard_ceiling)`. Keyed by **tuning identifiers**, not snake_case.
- `buildlab.cli` — `main(argv)`, `parse_height(text)`, with an `eval` subcommand.

Established codebase idioms — follow them:

- Every table loader is a module-level function decorated `@functools.lru_cache(maxsize=1)`.
- All data is read through `sources.path_for(rel)`. Never hardcode a path.
- Vendored JSON is either a bare list or an object with `_meta` and `data`. `reference._rows` handles both; badge files all use the `{_meta, data}` shape.
- Errors that mean "you asked about something with no data" raise `KeyError` with a message naming the inputs and the valid range. See `tables.weights` and `body.ceilings` for the house style.
- Attribute vectors are always **21 ints in builder index order**.

### The data, surveyed

All five files are already vendored and hash-verified. Do not add anything to `tools/vendor.py`.

| File | Rows | Shape |
|---|---|---|
| `badges/definitions.json` | 53 | `{"badge": 17, "name": "float_game", "discipline": "finishing", "group": 2, "height_inches": [63, 91], "allowed": true}` |
| `badges/tier_requirements.json` | 212 | `{"badge": 17, "name": "float_game", "tier": "bronze", "requirements": [{"attribute": 0, "name": "close_shot", "minimum": 65, "operator_to_next": "OR"}, ...]}` |
| `badges/token_costs.json` | 5300 | `{"badge": 17, "name": "float_game", "tier": "bronze", "height_inches": 69, "cost": 3}` |
| `badges/token_contributions.json` | 31500 | `{"height_inches": 69, "attribute": 0, "name": "close_shot", "rating": 25, "tokens": [0,0,0,0,0,0], "slots": [0,0,0,0,0,0]}` |
| `cap_breakers/gains_by_rating.json` | 13280 | `{"scenario": "isolated", "attribute": 0, "name": "close_shot", "rating": 25, "application": 0, "gain": 7}` |

Measured facts, all verified — treat as given:

- **`height_inches` of `[63, 91]` in definitions means unrestricted.** 26 of the 53 badges carry a narrower range. Legal build heights are 69–88, so 63–91 can never bind.
- **`allowed` is `true` for all 53 badges.** Still read it rather than assuming.
- **Requirement lists are 1 or 2 entries** — 88 badges/tiers with one, 124 with two. Never more.
- **Operators across all 212 rows: 296 `AND`, 40 `OR`.** The `operator_to_next` on the *final* entry of a list is a terminator with nothing to join to; it must be ignored, not applied. Do not let a trailing `AND` turn a one-attribute requirement into something it isn't.
- **`tier_requirements` has 4 tiers** — bronze, silver, gold, hall_of_fame. **`token_costs` has 5** — those four plus `legend`.
- **Every one of the 1,060 legend rows has `cost` 0**, and legend has no attribute requirement anywhere. Legend is not purchasable at build creation and cannot be reached by raising attributes. Model it as unreachable rather than free.
- **`token_costs` covers heights 69–88**, matching the legal build range exactly.
- **`tokens` and `slots` are 6-element arrays in `discipline_order`**, which `reference/enums.json` defines as `0 finishing, 1 shooting, 2 playmaking, 3 defense, 4 rebounding, 5 physicals`.

### The one thing this plan must not overclaim

`badges/token_contributions.json` measures tokens earned from **a single attribute at a given rating with every other attribute at the 25 floor**. Its own `describes` field says so.

It therefore does **not** directly give the token total for a real build, where 21 attributes are all above the floor. Summing the 21 per-attribute contributions assumes the earning function is additive, and **there is no multi-attribute token answer key anywhere in the vendored data** to check that against.

So: expose the per-attribute contribution as the measured fact it is, and expose any build-level total as an explicitly labelled **estimate** with the assumption named. Task 5 covers this. Do not present a summed total as if it were verified — that is exactly the kind of quiet wrongness this project exists to avoid.

The upstream README also states the badge **slot allocator** formula is unresolved. The `slots` array is therefore data we can read but not reproduce. Read it; do not build logic on it.

---

## File structure

| File | Responsibility |
|---|---|
| `buildlab/badges.py` | Badge definitions, height eligibility, tier requirement evaluation |
| `buildlab/tokens.py` | Token costs to equip, per-attribute token contributions, build-level estimate |
| `buildlab/capbreakers.py` | Cap breaker gain lookups |
| `buildlab/cli.py` | Add a `badges` subcommand (modify) |
| `tests/test_badges.py` | Definitions, eligibility, predicate evaluation |
| `tests/test_tokens.py` | Costs, contributions, the estimate and its caveat |
| `tests/test_capbreakers.py` | Gain lookups |
| `tests/test_cli.py` | Add coverage for the new subcommand (modify) |

`badges.py` depends on `sources` and `reference`. `tokens.py` depends on `sources` and `badges`. `capbreakers.py` depends on `sources` only. Nothing here touches `ovr` or `archetypes`.

---

## Task 1: Badge definitions and height eligibility

**Files:**
- Create: `buildlab/badges.py`
- Create: `tests/test_badges.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_badges.py`:

```python
import unittest

from buildlab import badges


class TestDefinitions(unittest.TestCase):
    def test_fifty_three_badges(self):
        self.assertEqual(len(badges.definitions()), 53)

    def test_lookup_by_id_and_by_name(self):
        by_id = badges.by_id(17)
        self.assertEqual(by_id["name"], "float_game")
        self.assertEqual(badges.by_name("float_game")["badge"], 17)

    def test_unknown_badge_raises(self):
        with self.assertRaises(KeyError):
            badges.by_id(9999)

    def test_every_badge_is_allowed(self):
        # All 53 ship allowed=True. Pinned so a future refresh that disables
        # one is noticed rather than silently changing what builds can equip.
        self.assertTrue(all(b["allowed"] for b in badges.definitions()))

    def test_six_disciplines(self):
        self.assertEqual(
            badges.DISCIPLINE_ORDER,
            ("finishing", "shooting", "playmaking", "defense", "rebounding", "physicals"),
        )


class TestHeightEligibility(unittest.TestCase):
    def test_unrestricted_badge_is_eligible_at_every_legal_height(self):
        unrestricted = next(
            b for b in badges.definitions() if b["height_inches"] == [63, 91]
        )
        for height in range(69, 89):
            self.assertTrue(badges.height_eligible(unrestricted["badge"], height))

    def test_twenty_six_badges_are_height_restricted(self):
        restricted = [b for b in badges.definitions() if b["height_inches"] != [63, 91]]
        self.assertEqual(len(restricted), 26)

    def test_restricted_badge_is_excluded_outside_its_range(self):
        restricted = next(
            b for b in badges.definitions() if b["height_inches"] != [63, 91]
        )
        low, high = restricted["height_inches"]
        self.assertTrue(badges.height_eligible(restricted["badge"], low))
        self.assertTrue(badges.height_eligible(restricted["badge"], high))
        self.assertFalse(badges.height_eligible(restricted["badge"], low - 1))
        self.assertFalse(badges.height_eligible(restricted["badge"], high + 1))

    def test_eligible_at_height_returns_ids(self):
        at_69 = badges.eligible_at_height(69)
        at_88 = badges.eligible_at_height(88)
        self.assertTrue(set(at_69) <= {b["badge"] for b in badges.definitions()})
        self.assertNotEqual(at_69, at_88)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_badges -v`
Expected: FAIL with `ImportError: cannot import name 'badges'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/badges.py`:

```python
"""Badge definitions, height eligibility and tier requirements."""

import functools
import json

from buildlab import sources

# reference/enums.json defines discipline_order 0-5. The `tokens` and `slots`
# arrays in badges/token_contributions.json are indexed by this order.
DISCIPLINE_ORDER = (
    "finishing",
    "shooting",
    "playmaking",
    "defense",
    "rebounding",
    "physicals",
)

# definitions.json uses [63, 91] to mean "no height restriction". Legal build
# heights are 69-88, so that range can never exclude anything.
UNRESTRICTED = [63, 91]


def _rows(rel):
    payload = json.loads(sources.path_for(rel).read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


@functools.lru_cache(maxsize=1)
def definitions():
    return _rows("badges/definitions.json")


@functools.lru_cache(maxsize=1)
def _by_id():
    return {b["badge"]: b for b in definitions()}


@functools.lru_cache(maxsize=1)
def _by_name():
    return {b["name"]: b for b in definitions()}


def by_id(badge_id):
    index = _by_id()
    if badge_id not in index:
        raise KeyError(f"no badge with id {badge_id}")
    return index[badge_id]


def by_name(name):
    index = _by_name()
    if name not in index:
        raise KeyError(f"no badge named {name!r}")
    return index[name]


def height_eligible(badge_id, height_inches):
    low, high = by_id(badge_id)["height_inches"]
    return low <= height_inches <= high


def eligible_at_height(height_inches):
    """Badge ids usable at this height, ignoring attributes."""
    return tuple(
        b["badge"]
        for b in definitions()
        if b["allowed"] and height_eligible(b["badge"], height_inches)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_badges -v`
Expected: `OK`, 9 tests

- [ ] **Step 5: Commit**

```bash
git add buildlab/badges.py tests/test_badges.py && git commit -m "feat: badge definitions and height eligibility"
```

---

## Task 2: Tier requirement evaluation

The predicate logic. A requirement list has one or two entries; two entries are joined by the `operator_to_next` of the **first**. The operator on the last entry is a terminator and must be ignored.

**Files:**
- Modify: `buildlab/badges.py`
- Modify: `tests/test_badges.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_badges.py`, before the `if __name__` block:

```python
class TestTierRequirements(unittest.TestCase):
    def test_two_hundred_and_twelve_requirement_rows(self):
        self.assertEqual(len(badges.tier_requirements()), 212)

    def test_four_tiers_have_requirements(self):
        self.assertEqual(badges.TIERS, ("bronze", "silver", "gold", "hall_of_fame"))

    def test_requirement_lists_are_one_or_two_entries(self):
        for row in badges.tier_requirements():
            with self.subTest(badge=row["name"], tier=row["tier"]):
                self.assertIn(len(row["requirements"]), (1, 2))

    def test_float_game_bronze_is_an_or(self):
        # close_shot 65 OR driving_layup 65 — either alone qualifies.
        values = [0] * 21
        values[0] = 65
        self.assertTrue(badges.meets(17, "bronze", values))
        values = [0] * 21
        values[1] = 65
        self.assertTrue(badges.meets(17, "bronze", values))
        self.assertFalse(badges.meets(17, "bronze", [0] * 21))

    def test_trailing_operator_is_ignored(self):
        # A single-entry requirement must qualify on that entry alone,
        # regardless of the terminator its operator_to_next carries.
        singles = [r for r in badges.tier_requirements() if len(r["requirements"]) == 1]
        self.assertGreater(len(singles), 0)
        row = singles[0]
        req = row["requirements"][0]
        values = [0] * 21
        values[req["attribute"]] = req["minimum"]
        self.assertTrue(badges.meets(row["badge"], row["tier"], values))

    def test_and_requires_both_attributes(self):
        ands = [
            r
            for r in badges.tier_requirements()
            if len(r["requirements"]) == 2
            and r["requirements"][0]["operator_to_next"] == "AND"
        ]
        self.assertGreater(len(ands), 0)
        row = ands[0]
        first, second = row["requirements"]
        only_first = [0] * 21
        only_first[first["attribute"]] = first["minimum"]
        self.assertFalse(badges.meets(row["badge"], row["tier"], only_first))
        both = list(only_first)
        both[second["attribute"]] = second["minimum"]
        self.assertTrue(badges.meets(row["badge"], row["tier"], both))

    def test_legend_has_no_attribute_path(self):
        # Legend never appears in tier_requirements: it cannot be reached by
        # raising attributes, only through a Max Plus 2 fuse slot.
        self.assertNotIn("legend", {r["tier"] for r in badges.tier_requirements()})
        with self.assertRaises(KeyError):
            badges.meets(17, "legend", [99] * 21)

    def test_best_tier_returns_the_highest_qualifying_tier(self):
        self.assertIsNone(badges.best_tier(17, [0] * 21, height_inches=75))
        self.assertEqual(badges.best_tier(17, [99] * 21, height_inches=75), "hall_of_fame")

    def test_best_tier_respects_height_eligibility(self):
        restricted = next(
            b for b in badges.definitions() if b["height_inches"] != badges.UNRESTRICTED
        )
        outside = restricted["height_inches"][1] + 1
        self.assertIsNone(
            badges.best_tier(restricted["badge"], [99] * 21, height_inches=outside)
        )

    def test_unlocked_lists_every_qualifying_badge(self):
        maxed = badges.unlocked([99] * 21, height_inches=75)
        self.assertGreater(len(maxed), 0)
        for badge_id, tier in maxed.items():
            with self.subTest(badge=badge_id):
                self.assertIn(tier, badges.TIERS)
        self.assertEqual(badges.unlocked([0] * 21, height_inches=75), {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_badges -v`
Expected: FAIL with `AttributeError: module 'buildlab.badges' has no attribute 'tier_requirements'`

- [ ] **Step 3: Write minimal implementation**

Append to `buildlab/badges.py`:

```python
# Ordered worst to best. `legend` is deliberately absent: it has no attribute
# requirement anywhere in tier_requirements.json and every legend row in
# token_costs.json has cost 0, because it is not purchasable at build creation.
TIERS = ("bronze", "silver", "gold", "hall_of_fame")


@functools.lru_cache(maxsize=1)
def tier_requirements():
    return _rows("badges/tier_requirements.json")


@functools.lru_cache(maxsize=1)
def _requirements_index():
    return {(r["badge"], r["tier"]): r["requirements"] for r in tier_requirements()}


def requirements_for(badge_id, tier):
    index = _requirements_index()
    if (badge_id, tier) not in index:
        raise KeyError(
            f"no requirements for badge {badge_id} at tier {tier!r}; "
            f"tiers with requirements are {TIERS}"
        )
    return index[(badge_id, tier)]


def meets(badge_id, tier, values):
    """Whether a 21-value attribute vector satisfies this badge tier.

    Requirement lists hold one or two entries. Two entries are joined by the
    `operator_to_next` of the FIRST entry. The operator on the last entry is a
    terminator with nothing to join to and is ignored.
    """
    requirements = requirements_for(badge_id, tier)
    satisfied = [values[r["attribute"]] >= r["minimum"] for r in requirements]
    if len(satisfied) == 1:
        return satisfied[0]
    if requirements[0]["operator_to_next"] == "OR":
        return satisfied[0] or satisfied[1]
    return satisfied[0] and satisfied[1]


def best_tier(badge_id, values, height_inches):
    """Highest tier this build qualifies for, or None."""
    if not height_eligible(badge_id, height_inches):
        return None
    best = None
    for tier in TIERS:
        try:
            qualifies = meets(badge_id, tier, values)
        except KeyError:
            continue
        if qualifies:
            best = tier
    return best


def unlocked(values, height_inches):
    """Badge id -> best qualifying tier, for every badge this build unlocks."""
    out = {}
    for badge_id in eligible_at_height(height_inches):
        tier = best_tier(badge_id, values, height_inches)
        if tier is not None:
            out[badge_id] = tier
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_badges -v`
Expected: `OK`, 19 tests

If `test_float_game_bronze_is_an_or` fails, print the actual row with
`python -c "from buildlab import badges; print(badges.requirements_for(17, 'bronze'))"`
and report it. The OR reading is verified against the source data and against the project's own knowledge-base notes; a failure means the operator semantics are different from what the survey found, which is important news. Do not flip the logic to make the test pass.

- [ ] **Step 5: Commit**

```bash
git add buildlab/badges.py tests/test_badges.py && git commit -m "feat: evaluate badge tier requirements with AND/OR predicates"
```

---

## Task 3: Token costs to equip

**Files:**
- Create: `buildlab/tokens.py`
- Create: `tests/test_tokens.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tokens.py`:

```python
import unittest

from buildlab import badges, tokens


class TestTokenCosts(unittest.TestCase):
    def test_five_thousand_three_hundred_cost_rows(self):
        self.assertEqual(len(tokens.costs()), 5300)

    def test_costs_cover_legal_heights_only(self):
        heights = {r["height_inches"] for r in tokens.costs()}
        self.assertEqual(min(heights), 69)
        self.assertEqual(max(heights), 88)
        self.assertEqual(len(heights), 20)

    def test_five_tiers_including_legend(self):
        self.assertEqual(
            sorted({r["tier"] for r in tokens.costs()}),
            ["bronze", "gold", "hall_of_fame", "legend", "silver"],
        )

    def test_known_cost(self):
        self.assertEqual(tokens.cost_for(17, "bronze", 69), 3)

    def test_every_legend_row_costs_zero(self):
        legend = [r for r in tokens.costs() if r["tier"] == "legend"]
        self.assertEqual(len(legend), 1060)
        self.assertTrue(all(r["cost"] == 0 for r in legend))

    def test_legend_is_reported_as_unreachable_not_free(self):
        # A zero cost must not read as "free to equip". Legend cannot be
        # bought at build creation at all.
        self.assertTrue(tokens.is_unreachable_tier("legend"))
        self.assertFalse(tokens.is_unreachable_tier("gold"))

    def test_unknown_combination_raises(self):
        with self.assertRaises(KeyError):
            tokens.cost_for(17, "bronze", 60)

    def test_cost_of_loadout_sums_equipped_badges(self):
        loadout = {17: "bronze"}
        expected = tokens.cost_for(17, "bronze", 69)
        self.assertEqual(tokens.cost_of_loadout(loadout, 69), expected)

    def test_cost_of_loadout_rejects_legend(self):
        with self.assertRaises(ValueError):
            tokens.cost_of_loadout({17: "legend"}, 69)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_tokens -v`
Expected: FAIL with `ImportError: cannot import name 'tokens'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/tokens.py`:

```python
"""Badge token costs, per-attribute contributions, and build-level estimates."""

import functools
import json

from buildlab import badges, sources

# Every legend row in token_costs.json has cost 0, and legend appears nowhere
# in tier_requirements.json. That is not "free" — legend is unreachable at
# build creation and only comes from a Max Plus 2 fuse slot.
UNREACHABLE_TIERS = ("legend",)


def _rows(rel):
    payload = json.loads(sources.path_for(rel).read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


def is_unreachable_tier(tier):
    return tier in UNREACHABLE_TIERS


@functools.lru_cache(maxsize=1)
def costs():
    return _rows("badges/token_costs.json")


@functools.lru_cache(maxsize=1)
def _cost_index():
    return {(r["badge"], r["tier"], r["height_inches"]): r["cost"] for r in costs()}


def cost_for(badge_id, tier, height_inches):
    index = _cost_index()
    key = (badge_id, tier, height_inches)
    if key not in index:
        raise KeyError(
            f"no token cost for badge {badge_id} tier {tier!r} at height "
            f"{height_inches}; costs cover heights 69-88"
        )
    return index[key]


def cost_of_loadout(loadout, height_inches):
    """Total tokens to equip a {badge_id: tier} loadout at this height."""
    total = 0
    for badge_id, tier in loadout.items():
        if is_unreachable_tier(tier):
            raise ValueError(
                f"badge {badge_id} at tier {tier!r} cannot be equipped at build "
                "creation; legend comes only from a Max Plus 2 fuse slot"
            )
        total += cost_for(badge_id, tier, height_inches)
    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_tokens -v`
Expected: `OK`, 9 tests

- [ ] **Step 5: Commit**

```bash
git add buildlab/tokens.py tests/test_tokens.py && git commit -m "feat: badge token costs and loadout pricing"
```

---

## Task 4: Per-attribute token contributions

This task exposes the measured fact only. The build-level estimate is Task 5, deliberately separated so the verified and unverified parts cannot be confused.

**Files:**
- Modify: `buildlab/tokens.py`
- Modify: `tests/test_tokens.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tokens.py`, before the `if __name__` block:

```python
class TestContributions(unittest.TestCase):
    def test_thirty_one_thousand_five_hundred_rows(self):
        # 20 heights x 21 attributes x 75 ratings
        self.assertEqual(len(tokens.contributions()), 31500)

    def test_contribution_is_six_values_in_discipline_order(self):
        got = tokens.contribution(height_inches=69, attribute=0, rating=25)
        self.assertEqual(len(got), 6)
        self.assertEqual(len(badges.DISCIPLINE_ORDER), 6)

    def test_floor_rating_earns_nothing(self):
        self.assertEqual(
            tokens.contribution(height_inches=69, attribute=0, rating=25),
            (0, 0, 0, 0, 0, 0),
        )

    def test_a_high_rating_earns_something(self):
        got = tokens.contribution(height_inches=69, attribute=0, rating=99)
        self.assertGreater(sum(got), 0)

    def test_contributions_never_decrease_with_rating(self):
        # Monotonic in rating: raising an attribute must never reduce tokens.
        for attribute in range(21):
            with self.subTest(attribute=attribute):
                previous = (0,) * 6
                for rating in range(25, 100):
                    got = tokens.contribution(
                        height_inches=75, attribute=attribute, rating=rating
                    )
                    for before, after in zip(previous, got):
                        self.assertGreaterEqual(after, before)
                    previous = got

    def test_ratings_cover_25_to_99(self):
        ratings = {r["rating"] for r in tokens.contributions()}
        self.assertEqual(min(ratings), 25)
        self.assertEqual(max(ratings), 99)
        self.assertEqual(len(ratings), 75)

    def test_unknown_lookup_raises(self):
        with self.assertRaises(KeyError):
            tokens.contribution(height_inches=60, attribute=0, rating=25)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_tokens -v`
Expected: FAIL with `AttributeError: module 'buildlab.tokens' has no attribute 'contributions'`

- [ ] **Step 3: Write minimal implementation**

Append to `buildlab/tokens.py`:

```python
@functools.lru_cache(maxsize=1)
def contributions():
    return _rows("badges/token_contributions.json")


@functools.lru_cache(maxsize=1)
def _contribution_index():
    return {
        (r["height_inches"], r["attribute"], r["rating"]): tuple(r["tokens"])
        for r in contributions()
    }


def contribution(height_inches, attribute, rating):
    """Tokens earned per discipline from ONE attribute at this rating.

    Measured with every other attribute at the 25 floor. Six values in
    badges.DISCIPLINE_ORDER. This is a measured fact; see estimate_earned for
    the build-level extrapolation and its caveat.
    """
    index = _contribution_index()
    key = (height_inches, attribute, rating)
    if key not in index:
        raise KeyError(
            f"no token contribution for height {height_inches}, attribute "
            f"{attribute}, rating {rating}; heights 69-88, attributes 0-20, "
            "ratings 25-99"
        )
    return index[key]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_tokens -v`
Expected: `OK`, 16 tests

If `test_contributions_never_decrease_with_rating` fails, **stop and report the attribute, height and ratings where it decreases.** Monotonicity is an assumption, not a measured fact, and a violation would be a genuine discovery about how token earning works. Do not remove or weaken the test.

- [ ] **Step 5: Commit**

```bash
git add buildlab/tokens.py tests/test_tokens.py && git commit -m "feat: per-attribute badge token contributions"
```

---

## Task 5: Build-level token estimate, honestly labelled

**Files:**
- Modify: `buildlab/tokens.py`
- Modify: `tests/test_tokens.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tokens.py`, before the `if __name__` block:

```python
class TestEstimatedEarnings(unittest.TestCase):
    def test_estimate_returns_six_disciplines_and_a_flag(self):
        result = tokens.estimate_earned([50] * 21, height_inches=75)
        self.assertEqual(len(result["per_discipline"]), 6)
        self.assertEqual(result["verified"], False)
        self.assertIn("additive", result["assumption"].lower())

    def test_floor_build_earns_nothing(self):
        result = tokens.estimate_earned([25] * 21, height_inches=75)
        self.assertEqual(result["per_discipline"], (0, 0, 0, 0, 0, 0))
        self.assertEqual(result["total"], 0)

    def test_maxed_build_earns_more_than_a_floor_build(self):
        low = tokens.estimate_earned([25] * 21, height_inches=75)
        high = tokens.estimate_earned([99] * 21, height_inches=75)
        self.assertGreater(high["total"], low["total"])

    def test_estimate_is_the_sum_of_its_parts(self):
        values = [40] * 21
        expected = [0] * 6
        for attribute, rating in enumerate(values):
            got = tokens.contribution(
                height_inches=75, attribute=attribute, rating=rating
            )
            expected = [a + b for a, b in zip(expected, got)]
        result = tokens.estimate_earned(values, height_inches=75)
        self.assertEqual(result["per_discipline"], tuple(expected))

    def test_estimate_rejects_a_wrong_length_vector(self):
        with self.assertRaises(ValueError):
            tokens.estimate_earned([50] * 20, height_inches=75)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_tokens -v`
Expected: FAIL with `AttributeError: module 'buildlab.tokens' has no attribute 'estimate_earned'`

- [ ] **Step 3: Write minimal implementation**

Append to `buildlab/tokens.py`:

```python
ADDITIVITY_ASSUMPTION = (
    "Assumes token earning is additive across attributes. "
    "badges/token_contributions.json measures one attribute at a time with all "
    "others at the 25 floor, and no multi-attribute token answer key exists in "
    "the vendored data, so this total is UNVERIFIED."
)


def estimate_earned(values, height_inches):
    """Estimated tokens earned by a full build, per discipline.

    Returns a dict with `per_discipline` (6 ints in badges.DISCIPLINE_ORDER),
    `total`, `verified` (always False) and `assumption`.

    The per-attribute contributions this sums are measured facts. Their SUM is
    not: see ADDITIVITY_ASSUMPTION. Callers must surface `verified` rather than
    presenting the total as ground truth.
    """
    if len(values) != 21:
        raise ValueError(f"expected 21 attribute values, got {len(values)}")
    totals = [0] * 6
    for attribute, rating in enumerate(values):
        got = contribution(height_inches, attribute, rating)
        totals = [a + b for a, b in zip(totals, got)]
    return {
        "per_discipline": tuple(totals),
        "total": sum(totals),
        "verified": False,
        "assumption": ADDITIVITY_ASSUMPTION,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_tokens -v`
Expected: `OK`, 21 tests

- [ ] **Step 5: Commit**

```bash
git add buildlab/tokens.py tests/test_tokens.py && git commit -m "feat: estimate build token earnings with the additivity caveat"
```

---

## Task 6: Cap breakers

**The single most important fact about this table: it is body-specific, and sparse because of it.**

A full grid would be 2 scenarios × 21 attributes × 75 ratings × 5 applications = **15,750 rows. Only 13,280 exist.** The 2,470 missing combinations are not random. For each attribute, rows stop at exactly that attribute's ceiling on the dataset's reference body — PG, 75 in, 198 lb, 78 in wingspan:

```
close_shot       25-99      standing_dunk    25-51      block            25-63
driving_dunk     25-94      post_control     25-80      offensive_reb    25-66
speed_with_ball  25-92      interior_def     25-73      strength         25-74
```

This was verified programmatically: the highest rating with cap-breaker data matches `body.ceilings(height=75, weight=198, wingspan=78)` for **all 21 attributes, with zero mismatches.**

Two consequences the implementation must respect:

1. **The data is only strictly valid for that one body.** A 7-foot build has completely different ceilings, and nothing here says what a cap breaker does at a rating that body could reach but the reference body could not. Do not present cap-breaker results for other bodies as verified.
2. **A sequence of applications can run out of data mid-way.** Applying five breakers to `standing_dunk` from 45 walks past the reference ceiling of 51 and falls off the table. Silently stopping there — the obvious `try/except KeyError: break` — would quietly return a wrong answer, which is precisely the failure mode that produced a real bug in phase 1. Report how many applications actually landed.

The sequential reading itself is confirmed. Each application looks up the gain at the rating the previous one produced, not at the original: attribute 0 from 25 walks `25 → 32 → 40 → 46 → 51 → 55`, and every lookup exists.

**Files:**
- Create: `buildlab/capbreakers.py`
- Create: `tests/test_capbreakers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_capbreakers.py`:

```python
import unittest

from buildlab import capbreakers


class TestCapBreakers(unittest.TestCase):
    def test_thirteen_thousand_two_hundred_and_eighty_rows(self):
        self.assertEqual(len(capbreakers.gains()), 13280)

    def test_two_scenarios(self):
        self.assertEqual(capbreakers.SCENARIOS, ("isolated", "near_caps"))

    def test_five_applications(self):
        applications = {r["application"] for r in capbreakers.gains()}
        self.assertEqual(sorted(applications), [0, 1, 2, 3, 4])

    def test_known_gain(self):
        self.assertEqual(
            capbreakers.gain_for("isolated", attribute=0, rating=25, application=0), 7
        )

    def test_unknown_lookup_raises(self):
        with self.assertRaises(KeyError):
            capbreakers.gain_for("isolated", attribute=0, rating=25, application=99)

    def test_unknown_scenario_raises(self):
        with self.assertRaises(KeyError):
            capbreakers.gain_for("nonsense", attribute=0, rating=25, application=0)

    def test_table_is_sparse_by_exactly_2470_rows(self):
        # 2 scenarios x 21 attributes x 75 ratings x 5 applications = 15750.
        # Only 13280 ship. The gap is structural, not corruption: see below.
        self.assertEqual(2 * 21 * 75 * 5 - len(capbreakers.gains()), 2470)

    def test_coverage_stops_at_the_reference_body_ceiling(self):
        # THE key property. For every attribute, the highest rating with
        # cap-breaker data equals that attribute's ceiling on the dataset's
        # reference body. Verified: 21/21, zero mismatches. Pinned here so a
        # future data refresh probed at a different body fails loudly.
        from buildlab import body, reference

        caps = body.ceilings(**capbreakers.REFERENCE_BODY)
        names = reference.attribute_names()
        for attribute in range(21):
            with self.subTest(attribute=names[attribute]):
                self.assertEqual(
                    capbreakers.max_rating_for("isolated", attribute),
                    caps[names[attribute]],
                )

    def test_apply_all_walks_the_sequence(self):
        # Each application looks up its gain at the rating the previous one
        # produced. Attribute 0 from 25: 25 -> 32 -> 40 -> 46 -> 51 -> 55.
        result = capbreakers.apply_all("isolated", attribute=0, rating=25)
        self.assertEqual(result["rating"], 55)
        self.assertEqual(result["applied"], 5)
        self.assertTrue(result["complete"])

    def test_every_covered_start_completes_all_five(self):
        # A real invariant, swept and confirmed: for every attribute and every
        # rating the table covers, all five applications land. The gains taper
        # near the ceiling rather than falling off it. Sweeping both scenarios
        # is what proves apply_all never silently truncates within coverage.
        for scenario in capbreakers.SCENARIOS:
            for attribute in range(21):
                top = capbreakers.max_rating_for(scenario, attribute)
                for rating in range(25, top + 1):
                    with self.subTest(
                        scenario=scenario, attribute=attribute, rating=rating
                    ):
                        result = capbreakers.apply_all(scenario, attribute, rating)
                        self.assertTrue(result["complete"])
                        self.assertEqual(result["applied"], 5)

    def test_start_above_reference_coverage_is_reported_not_truncated(self):
        # standing_dunk (attribute 3) tops out at 51 on the reference body. A
        # taller build can exceed that, and the table says nothing about it.
        # That must surface, never be silently treated as "no gain".
        self.assertEqual(capbreakers.max_rating_for("isolated", 3), 51)
        result = capbreakers.apply_all("isolated", attribute=3, rating=60)
        self.assertFalse(result["complete"])
        self.assertEqual(result["applied"], 0)
        self.assertIn("reference body", result["note"].lower())

    def test_apply_all_never_reduces_a_rating(self):
        for attribute in range(21):
            with self.subTest(attribute=attribute):
                result = capbreakers.apply_all(
                    "isolated", attribute=attribute, rating=40
                )
                self.assertGreaterEqual(result["rating"], 40)

    def test_apply_all_never_exceeds_ninety_nine(self):
        for attribute in range(21):
            with self.subTest(attribute=attribute):
                result = capbreakers.apply_all(
                    "isolated", attribute=attribute, rating=40
                )
                self.assertLessEqual(result["rating"], 99)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_capbreakers -v`
Expected: FAIL with `ImportError: cannot import name 'capbreakers'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/capbreakers.py`:

```python
"""Cap breaker gains: how much each of the five applications raises an attribute."""

import functools
import json

from buildlab import sources

SCENARIOS = ("isolated", "near_caps")
APPLICATIONS = 5
MAX_RATING = 99

# The table was probed at exactly this body. Coverage for each attribute stops
# at that attribute's ceiling here — verified against body.ceilings for all 21
# attributes with zero mismatches. Results for any other body are therefore
# unverified, and a sequence can run out of data partway.
REFERENCE_BODY = {"height": 75, "weight": 198, "wingspan": 78}

OUT_OF_RANGE_NOTE = (
    "ran past the highest rating this table covers for the attribute; the data "
    "was probed at the reference body (PG, 6'3, 198 lb, 78 in wingspan) and "
    "stops at that body's ceiling"
)


def _rows(rel):
    payload = json.loads(sources.path_for(rel).read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


@functools.lru_cache(maxsize=1)
def gains():
    return _rows("cap_breakers/gains_by_rating.json")


@functools.lru_cache(maxsize=1)
def _gain_index():
    return {
        (r["scenario"], r["attribute"], r["rating"], r["application"]): r["gain"]
        for r in gains()
    }


def gain_for(scenario, attribute, rating, application):
    index = _gain_index()
    key = (scenario, attribute, rating, application)
    if key not in index:
        raise KeyError(
            f"no cap breaker gain for scenario {scenario!r}, attribute "
            f"{attribute}, rating {rating}, application {application}; "
            f"scenarios are {SCENARIOS}, applications 0-{APPLICATIONS - 1}"
        )
    return index[key]


@functools.lru_cache(maxsize=None)
def max_rating_for(scenario, attribute):
    """Highest rating this table covers for an attribute under a scenario."""
    ratings = [
        key[2] for key in _gain_index() if key[0] == scenario and key[1] == attribute
    ]
    if not ratings:
        raise KeyError(f"no cap breaker data for {scenario!r}, attribute {attribute}")
    return max(ratings)


def apply_all(scenario, attribute, rating):
    """Apply the five cap breakers in sequence, reporting how far it got.

    Each application looks up its gain at the rating the previous one produced,
    not at the original rating.

    Returns a dict with `rating` (the result), `applied` (how many of the five
    actually landed), `complete` (whether all five did) and `note` (empty
    unless the sequence ran out of data). A sequence that walks past the
    reference body's ceiling for this attribute stops early — that is reported,
    never silently truncated.
    """
    current = rating
    applied = 0
    note = ""
    for application in range(APPLICATIONS):
        try:
            current += gain_for(scenario, attribute, current, application)
        except KeyError:
            note = OUT_OF_RANGE_NOTE
            break
        current = min(current, MAX_RATING)
        applied += 1
    return {
        "rating": current,
        "applied": applied,
        "complete": applied == APPLICATIONS,
        "note": note,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_capbreakers -v`
Expected: `OK`, 12 tests. `test_every_covered_start_completes_all_five` runs several thousand subtests and will take a few seconds.

If `test_coverage_stops_at_the_reference_body_ceiling` fails, **stop and report which attributes differ.** That property was verified 21/21 against `body.ceilings`; a failure means either the cap-breaker data was re-probed at a different body or `body.ceilings` has regressed, and both are important news.

If `test_every_covered_start_completes_all_five` fails, report the scenario, attribute and rating where the sequence stops. It was swept across both scenarios and every covered rating with zero incomplete cases, so a failure is a real change in the data rather than a bug in `apply_all`.

- [ ] **Step 5: Commit**

```bash
git add buildlab/capbreakers.py tests/test_capbreakers.py && git commit -m "feat: cap breaker gain lookups"
```

---

## Task 7: `badges` CLI subcommand

**Files:**
- Modify: `buildlab/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`, before the `if __name__` block:

```python
class TestBadgesCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_badges_lists_unlocked_badges(self):
        values = ",".join(["99"] * 21)
        code, out = self.run_cli(["badges", "--height", "6-3", "--values", values])
        self.assertEqual(code, 0)
        self.assertIn("UNLOCKED", out)
        self.assertIn("hall_of_fame", out)

    def test_badges_reports_none_for_a_floor_build(self):
        values = ",".join(["25"] * 21)
        code, out = self.run_cli(["badges", "--height", "6-3", "--values", values])
        self.assertEqual(code, 0)
        self.assertIn("UNLOCKED  0", out)

    def test_badges_rejects_wrong_attribute_count(self):
        code, out = self.run_cli(["badges", "--height", "6-3", "--values", "70,70"])
        self.assertEqual(code, 2)
        self.assertIn("21", out)

    def test_badges_surfaces_the_token_estimate_caveat(self):
        values = ",".join(["80"] * 21)
        _, out = self.run_cli(["badges", "--height", "6-3", "--values", values])
        self.assertIn("UNVERIFIED", out.upper())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL — `argparse` exits with an error because `badges` is not a valid subcommand

- [ ] **Step 3: Write minimal implementation**

In `buildlab/cli.py`, change the import line to:

```python
from buildlab import badges as badges_mod, ovr, reference, tokens
```

Add this function after `_eval`:

```python
def _badges(args):
    values = [int(v) for v in args.values.split(",")]
    if len(values) != 21:
        print(f"error: expected 21 attribute values, got {len(values)}")
        return 2
    height = parse_height(args.height)
    unlocked = badges_mod.unlocked(values, height)
    print(f"HEIGHT     {args.height}  ({height} in)")
    print(f"OVERALL    {ovr.overall(height, values)}")
    print(f"UNLOCKED  {len(unlocked)} badges")
    print()
    by_tier = {tier: [] for tier in badges_mod.TIERS}
    for badge_id, tier in unlocked.items():
        by_tier[tier].append(badges_mod.by_id(badge_id)["name"])
    for tier in reversed(badges_mod.TIERS):
        names = sorted(by_tier[tier])
        if names:
            print(f"  {tier}:")
            for name in names:
                cost = tokens.cost_for(badges_mod.by_name(name)["badge"], tier, height)
                print(f"    {name:<28} {cost} tokens")
    print()
    estimate = tokens.estimate_earned(values, height)
    print(f"TOKENS EARNED (estimate)  {estimate['total']}")
    for discipline, amount in zip(badges_mod.DISCIPLINE_ORDER, estimate["per_discipline"]):
        print(f"    {discipline:<12} {amount}")
    print()
    print(f"  NOTE: this total is UNVERIFIED. {estimate['assumption']}")
    return 0
```

Then register the subcommand inside `main`, after the `eval` parser is set up:

```python
    bd = sub.add_parser("badges", help="show badges a build unlocks")
    bd.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    bd.add_argument("--values", required=True, help="21 comma-separated ratings")
    bd.set_defaults(func=_badges)
```

Note the exact spacing in `UNLOCKED  {len(unlocked)} badges` — two spaces, matching the `test_badges_reports_none_for_a_floor_build` assertion. Keep the existing `eval` subcommand and `parse_height` untouched.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli -v`
Expected: `OK`, 7 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 88 pre-existing plus the new tests, all passing.

- [ ] **Step 5: Run it for real**

Run:

```bash
python -m buildlab.cli badges --height 6-3 --values 99,99,99,99,99,99,99,99,99,99,99,99,99,99,99,99,99,99,99,99,99
```

Paste the output in your report. A maxed build at 6'3" should unlock a large number of badges at hall_of_fame.

- [ ] **Step 6: Commit**

```bash
git add buildlab/cli.py tests/test_cli.py && git commit -m "feat: add badges subcommand"
```

---

## Definition of done

- `python -m unittest discover -s tests` passes with no failures and no skips.
- `python -m buildlab.cli badges --height 6-3 --values <21 values>` lists unlocked badges by tier with token costs, and prints the token estimate together with its UNVERIFIED caveat.
- `buildlab.sources.verify()` still passes — no data file was touched.
- Legend is reported as unreachable at build creation, never as a free tier.
- No third-party imports anywhere in `buildlab/`, `tools/` or `tests/`.

## Explicitly not in this plan

Animation parsing and threshold ladders, the constraint solver, the transcript-critique flow, the data refresh command, the animation ratings layer, and the web UI. Those are later plans.

Also deliberately excluded: the **badge slot allocator**. Upstream states the combining formula is unresolved — the inputs are known but the rule is not. `token_contributions.json` carries a `slots` array we can read, but nothing here should compute or predict a slot count. Reading the recorded value is fine; inventing one is not.
