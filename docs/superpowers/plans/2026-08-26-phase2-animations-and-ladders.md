# Phase 2: Animation Parser and Threshold Ladders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the 1,814 NBA2KLab animation requirement rows into structured data the engine can gate on, and build the threshold ladder — for any attribute, what each additional point actually buys in badges and animations.

**Architecture:** A parser converts the markdown tables into a normalised list of packages, each with a height range and a dict of attribute minimums. Query functions answer "what can this build use" and "what does this package cost". The ladder module joins animation gates and badge tiers into a single per-attribute view, and cross-checks reachability against body ceilings so it never promises something a body cannot reach.

**Tech Stack:** Python 3.14 standard library only. `unittest` for tests. No pip installs, no third-party packages.

---

## Context the implementer needs

Phases 1a and 1b are merged. Available modules:

- `buildlab.sources` — `path_for(rel)` for **vendored** data, manifest-gated. Raises `SourceError`.
- `buildlab.reference` — `attribute_names()` (21 snake_case, builder index order), `tuning_order()`, `TUNING_NAME`, `legal_bodies()`.
- `buildlab.tables` — `bucket_for_inches(inches)`, `weight_buckets()`, `height_buckets()`.
- `buildlab.body` — `is_legal(position, height, weight, wingspan)`, `ceilings(height, weight, wingspan)` -> dict keyed by snake_case.
- `buildlab.constraints` — `rules_for(attr, bucket)`, `effective_ceiling(attr, bucket, values, hard_ceiling)`. **Keyed by tuning identifiers**, not snake_case.
- `buildlab.ovr` — `overall(height_inches, values)`, `detailed`, `archetype`.
- `buildlab.badges` — `TIERS`, `DISCIPLINE_ORDER`, `by_id`, `by_name`, `definitions()`, `height_eligible`, `eligible_at_height`, `tier_requirements()`, `requirements_for(badge_id, tier)`, `meets`, `best_tier`, `unlocked`.
- `buildlab.tokens` — `cost_for`, `cost_of_loadout(loadout, height, cumulative=False)`, `TOKEN_DATA_HEIGHTS` (69-81), `has_token_data`, `contribution`, `earned`.
- `buildlab.capbreakers` — `SCENARIOS`, `REFERENCE_BODY`, `gain_for`, `max_rating_for`, `apply_all`.
- `buildlab.cli` — `main(argv)`, `parse_height(text)`, subcommands `eval` and `badges`.

Codebase idioms — follow them:

- Table loaders are module-level functions decorated `@functools.lru_cache(maxsize=1)`.
- "You asked about something with no data" raises `KeyError` naming the inputs and the valid range.
- Where data is untrustworthy, **refuse to answer rather than guess**. Phase 1b established this: `tokens.contribution` raises for heights 82+ rather than returning the shipped zeros.

### The source file is NOT vendored data

`2k27-animation-requirements.md` lives at `C:\Users\jns\OneDrive\Documents\2k\2k27\2k27-animation-requirements.md` — one directory above the repository root. It is the user's own file, derived from NBA2KLab, and is **not** in `data/SOURCES.json`.

Task 1 vendors it: copy it into `data/local/` and add it to the manifest with a SHA-256, so the same integrity guarantee covers it. Do not read it from outside the repo at runtime.

### The markdown structure, surveyed

Verified by parsing the real file. Treat as given:

- **1,814 data rows across 52 families in 4 sections.** Section headings are `## `, family headings are `### `. The counts in the section headings are `Dunks, layups and post moves (266)`, `Shooting animations (420)`, `Dribble and pass animations (775)`, `Motion styles (353)`.
- Tables are GitHub-flavoured markdown pipe tables. The row after the header is a `---` separator and must be skipped.
- **Every row has `Min Height` and `Max Height`**, formatted `5'9`, `6'11`, `7'4`.
- The package name column is **`Package` on 1,461 rows and `Name` on 353 rows**. The 353 are exactly the Motion styles section. Handle both.
- **A `—` (em dash) means no requirement** for that column.
- Twelve distinct attribute columns appear. The mapping to builder attribute names is:

| Column header | Builder attribute |
|---|---|
| `Ball Handle` | ball_handle |
| `Speed` | speed |
| `Agility` | agility |
| `Mid` | mid_range |
| `3Pt` | three_point |
| `Vertical` | vertical |
| `Dr. Dunk` | driving_dunk |
| `Dr. Layup` | driving_layup |
| `Std Dunk` | standing_dunk |
| `Passing Accuracy` | pass_accuracy |
| `Speed w/ Ball` | speed_with_ball |
| `Post Control` | post_control |

Column frequencies, for the parser's sanity checks: Ball Handle 676, Speed 353, Agility 353, Mid 341, 3Pt 341, Vertical 143, Dr. Dunk 141, Dr. Layup 80, Std Dunk 76, Passing Accuracy 60, Speed w/ Ball 39, Post Control 26.

### Two findings this phase must encode

Both were established by driving the phase 1 engine at real questions.

1. **An animation's height range is a necessary condition, not a sufficient one.** Kyrie Irving's dribble style requires 94 Speed With Ball and lists a range of 5'9"-6'4". But the maximum Speed With Ball ceiling is 93 at 6'3" and 91 at 6'4" — so it is unreachable above 6'2", and at 6'2" only at minimum weight and minimum wingspan. Any tool that checks only the height gate will tell a player a build works when it cannot. `reachable_at` in Task 4 exists for exactly this.
2. **Attributes constrain each other.** `SpeedWithBall <= Speed + 0` is a hard lock, plus `<= BallControl + 5` and `<= Agility + 15`. So an animation requiring 94 Speed With Ball really requires Speed 94, Ball Handle 89 and Agility 79 as well. `full_cost_of` in Task 5 surfaces that.

---

## File structure

| File | Responsibility |
|---|---|
| `tools/vendor_local.py` | Copy the user's markdown into `data/local/` and add it to the manifest |
| `buildlab/animations.py` | Parse the markdown; expose packages, requirements, availability |
| `buildlab/ladders.py` | Threshold ladders joining animations and badges, reachability-aware |
| `buildlab/cli.py` | Add `animations` and `ladder` subcommands (modify) |
| `tests/test_animations.py` | Parser and query tests |
| `tests/test_ladders.py` | Ladder tests |
| `tests/test_cli.py` | Coverage for the two new subcommands (modify) |

`animations.py` depends on `sources` and `reference`. `ladders.py` depends on `animations`, `badges`, `body` and `constraints`.

---

## Task 1: Vendor the animation source

**Files:**
- Create: `tools/vendor_local.py`
- Modify: `data/SOURCES.json` (generated)
- Create: `tests/test_animations.py`

- [ ] **Step 1: Write the vendoring tool**

Create `tools/vendor_local.py`:

```python
"""Copy the user's own source documents into data/local and record hashes.

These are not downloaded from an upstream repository — they are files the user
maintains. They get the same manifest and hash treatment as vendored data so
the engine can detect when one changes underneath it.
"""

import hashlib
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT.parent
DEST = ROOT / "data" / "local"

FILES = {
    "local/animation_requirements.md": "2k27-animation-requirements.md",
}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "data" / "SOURCES.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    entries = {}
    for rel, filename in FILES.items():
        origin = SOURCE_DIR / filename
        if not origin.exists():
            raise SystemExit(f"missing source file {origin}")
        payload = origin.read_bytes()
        out = DEST / pathlib.PurePosixPath(rel).name
        out.write_bytes(payload)
        entries[rel] = {
            "local": f"data/local/{out.name}",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        print(f"{rel}  {len(payload)} bytes")

    manifest["sources"] = [
        s for s in manifest["sources"] if s.get("name") != "user-local-documents"
    ]
    manifest["sources"].append(
        {
            "name": "user-local-documents",
            "url": "local",
            "commit": "n/a",
            "files": entries,
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"recorded {len(entries)} local files in the manifest")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python tools/vendor_local.py`
Expected: `local/animation_requirements.md  <N> bytes` then `recorded 1 local files in the manifest`. N should be roughly 73,000.

- [ ] **Step 3: Write the failing test**

Create `tests/test_animations.py`:

```python
import unittest

from buildlab import animations, sources


class TestVendoredSource(unittest.TestCase):
    def test_the_markdown_is_in_the_manifest(self):
        path = sources.path_for("local/animation_requirements.md")
        self.assertTrue(path.exists())

    def test_manifest_hashes_still_verify(self):
        sources.verify()

    def test_source_has_the_four_sections(self):
        text = sources.path_for("local/animation_requirements.md").read_text(
            encoding="utf-8"
        )
        for heading in (
            "Dunks, layups and post moves",
            "Shooting animations",
            "Dribble and pass animations",
            "Motion styles",
        ):
            self.assertIn(heading, text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m unittest tests.test_animations -v`
Expected: FAIL with `ImportError: cannot import name 'animations'`

Create an empty placeholder so the import resolves, then re-run to see the real assertions:

```bash
printf '"""Animation requirements."""\n' > buildlab/animations.py
python -m unittest tests.test_animations -v
```

Expected: `OK`, 3 tests. If `test_manifest_hashes_still_verify` fails, the vendoring tool corrupted an existing entry — stop and report.

- [ ] **Step 5: Commit**

```bash
git add tools/vendor_local.py buildlab/animations.py tests/test_animations.py data && git commit -m "feat: vendor the animation requirements markdown under the manifest"
```

---

## Task 2: Parse the markdown

**Files:**
- Modify: `buildlab/animations.py`
- Modify: `tests/test_animations.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_animations.py`, before the `if __name__` block:

```python
class TestParser(unittest.TestCase):
    def test_row_count(self):
        self.assertEqual(len(animations.packages()), 1814)

    def test_family_and_section_counts(self):
        rows = animations.packages()
        self.assertEqual(len({r["family"] for r in rows}), 52)
        self.assertEqual(len({r["section"] for r in rows}), 4)

    def test_section_row_counts_match_their_headings(self):
        # The headings declare their own counts; the parse must agree.
        expected = {
            "Dunks, layups and post moves": 266,
            "Shooting animations": 420,
            "Dribble and pass animations": 775,
            "Motion styles": 353,
        }
        counts = {}
        for row in animations.packages():
            counts[row["section"]] = counts.get(row["section"], 0) + 1
        self.assertEqual(counts, expected)

    def test_every_row_has_a_name_and_height_range(self):
        for row in animations.packages():
            with self.subTest(name=row["name"], family=row["family"]):
                self.assertTrue(row["name"])
                self.assertLessEqual(row["min_height"], row["max_height"])
                self.assertGreaterEqual(row["min_height"], 69)

    def test_motion_styles_use_the_name_column(self):
        motion = [r for r in animations.packages() if r["section"] == "Motion styles"]
        self.assertEqual(len(motion), 353)
        self.assertTrue(all(r["name"] for r in motion))

    def test_requirements_use_builder_attribute_names(self):
        from buildlab import reference

        valid = set(reference.attribute_names())
        for row in animations.packages():
            for attribute in row["requirements"]:
                with self.subTest(name=row["name"], attribute=attribute):
                    self.assertIn(attribute, valid)

    def test_em_dash_means_no_requirement(self):
        for row in animations.packages():
            for attribute, minimum in row["requirements"].items():
                with self.subTest(name=row["name"]):
                    self.assertIsInstance(minimum, int)

    def test_known_row_kyrie_dribble_style(self):
        row = animations.by_name("Kyrie Irving", family="Dribble Style")
        self.assertEqual(row["requirements"], {"speed_with_ball": 94})
        self.assertEqual(row["min_height"], 69)
        self.assertEqual(row["max_height"], 76)

    def test_known_row_small_contact_dunks(self):
        row = animations.by_name(
            "Small Contact Dunks Off Two", family="Two Foot Moving Dunks - Contact Dunks"
        )
        self.assertEqual(
            row["requirements"], {"driving_dunk": 86, "vertical": 75}
        )
        self.assertEqual(row["max_height"], 76)

    def test_unknown_package_raises(self):
        with self.assertRaises(KeyError):
            animations.by_name("Not A Real Package", family="Dribble Style")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_animations -v`
Expected: FAIL with `AttributeError: module 'buildlab.animations' has no attribute 'packages'`

- [ ] **Step 3: Write the implementation**

Replace `buildlab/animations.py` with:

```python
"""Animation packages: requirements parsed from the NBA2KLab markdown tables."""

import functools
import re

from buildlab import sources

REL = "local/animation_requirements.md"

# The markdown column headers, mapped to builder attribute names. Twelve
# distinct attribute columns appear across the 52 families.
COLUMN_ATTRIBUTE = {
    "Ball Handle": "ball_handle",
    "Speed": "speed",
    "Agility": "agility",
    "Mid": "mid_range",
    "3Pt": "three_point",
    "Vertical": "vertical",
    "Dr. Dunk": "driving_dunk",
    "Dr. Layup": "driving_layup",
    "Std Dunk": "standing_dunk",
    "Passing Accuracy": "pass_accuracy",
    "Speed w/ Ball": "speed_with_ball",
    "Post Control": "post_control",
}

# The package name lives under `Package` in most families and `Name` in the
# Motion styles section.
NAME_COLUMNS = ("Package", "Name")

# An em dash means the column carries no requirement for that row.
NO_REQUIREMENT = "—"

HEIGHT_RE = re.compile(r"^(\d+)'(\d+)$")


def _height(text):
    match = HEIGHT_RE.match(text.strip())
    if not match:
        raise ValueError(f"unparseable height {text!r}")
    return int(match.group(1)) * 12 + int(match.group(2))


def _is_separator(cells):
    return set("".join(cells)) <= set("-: ")


@functools.lru_cache(maxsize=1)
def packages():
    """Every animation package as a dict.

    Keys: `name`, `family`, `section`, `min_height`, `max_height` (both in
    whole inches) and `requirements`, a dict of builder attribute name to
    minimum rating. A package with no attribute requirement has an empty
    requirements dict.
    """
    rows = []
    section = family = header = None
    text = sources.path_for(REL).read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("## "):
            section = re.sub(r"\s*\(\d+\)\s*$", "", line[3:].strip())
            family = header = None
            continue
        if line.startswith("### "):
            family = re.sub(r"\s*\(\d+\)\s*$", "", line[4:].strip())
            header = None
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if _is_separator(cells):
            continue
        if header is None:
            header = cells
            continue
        row = dict(zip(header, cells))
        name = ""
        for column in NAME_COLUMNS:
            if row.get(column):
                name = row[column]
                break
        requirements = {}
        for column, attribute in COLUMN_ATTRIBUTE.items():
            value = row.get(column, NO_REQUIREMENT)
            if value and value != NO_REQUIREMENT:
                requirements[attribute] = int(value)
        rows.append(
            {
                "name": name,
                "family": family,
                "section": section,
                "min_height": _height(row["Min Height"]),
                "max_height": _height(row["Max Height"]),
                "requirements": requirements,
            }
        )
    return rows


@functools.lru_cache(maxsize=1)
def _by_key():
    return {(r["family"], r["name"]): r for r in packages()}


def by_name(name, family):
    index = _by_key()
    if (family, name) not in index:
        raise KeyError(f"no package {name!r} in family {family!r}")
    return index[(family, name)]


@functools.lru_cache(maxsize=1)
def families():
    return tuple(sorted({r["family"] for r in packages()}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_animations -v`
Expected: `OK`, 13 tests

If `test_section_row_counts_match_their_headings` fails, the parser is dropping or duplicating rows. **Report the actual counts and stop** — do not adjust the expectation. The headings declare their own totals and the parse must agree with them.

If `test_every_row_has_a_name_and_height_range` fails on `min_height >= 69`, report the offending rows. Legal build heights start at 69, and a lower value means either a parse error or a row describing something outside the builder.

- [ ] **Step 5: Commit**

```bash
git add buildlab/animations.py tests/test_animations.py && git commit -m "feat: parse animation requirements into structured packages"
```

---

## Task 3: Availability queries

**Files:**
- Modify: `buildlab/animations.py`
- Modify: `tests/test_animations.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_animations.py`, before the `if __name__` block:

```python
class TestAvailability(unittest.TestCase):
    def test_a_floor_build_gets_only_unrestricted_packages(self):
        available = animations.available([25] * 21, height_inches=75)
        self.assertGreater(len(available), 0)
        for row in available:
            with self.subTest(name=row["name"]):
                self.assertTrue(
                    all(minimum <= 25 for minimum in row["requirements"].values())
                )

    def test_a_maxed_build_gets_more_than_a_floor_build(self):
        low = animations.available([25] * 21, height_inches=75)
        high = animations.available([99] * 21, height_inches=75)
        self.assertGreater(len(high), len(low))

    def test_height_gates_are_enforced(self):
        values = [99] * 21
        at_76 = {r["name"] for r in animations.available(values, height_inches=76)}
        at_77 = {r["name"] for r in animations.available(values, height_inches=77)}
        self.assertIn("Kyrie Irving", at_76)
        self.assertNotIn("Kyrie Irving", at_77)

    def test_available_in_family_filters(self):
        rows = animations.available(
            [99] * 21, height_inches=75, family="Dribble Style"
        )
        self.assertGreater(len(rows), 0)
        for row in rows:
            with self.subTest(name=row["name"]):
                self.assertEqual(row["family"], "Dribble Style")

    def test_missing_requirement_blocks_a_package(self):
        # Kyrie's dribble style needs 94 speed_with_ball. At 93 it is out.
        from buildlab import reference

        values = [99] * 21
        index = reference.attribute_names().index("speed_with_ball")
        values[index] = 93
        names = {r["name"] for r in animations.available(values, height_inches=75)}
        self.assertNotIn("Kyrie Irving", names)
        values[index] = 94
        names = {r["name"] for r in animations.available(values, height_inches=75)}
        self.assertIn("Kyrie Irving", names)

    def test_requirements_of_reports_every_gate(self):
        gates = animations.requirements_of("Kyrie Irving", family="Dribble Style")
        self.assertEqual(gates["requirements"], {"speed_with_ball": 94})
        self.assertEqual(gates["min_height"], 69)
        self.assertEqual(gates["max_height"], 76)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_animations -v`
Expected: FAIL with `AttributeError: module 'buildlab.animations' has no attribute 'available'`

- [ ] **Step 3: Write the implementation**

Append to `buildlab/animations.py`:

```python
def _qualifies(row, values, height_inches, name_index):
    if not row["min_height"] <= height_inches <= row["max_height"]:
        return False
    for attribute, minimum in row["requirements"].items():
        if values[name_index[attribute]] < minimum:
            return False
    return True


def available(values, height_inches, family=None):
    """Packages this build can use, optionally filtered to one family."""
    from buildlab import reference

    if len(values) != 21:
        raise ValueError(f"expected 21 attribute values, got {len(values)}")
    name_index = {n: i for i, n in enumerate(reference.attribute_names())}
    return [
        row
        for row in packages()
        if (family is None or row["family"] == family)
        and _qualifies(row, values, height_inches, name_index)
    ]


def requirements_of(name, family):
    """Every gate on a package: attribute minimums and the height range."""
    row = by_name(name, family)
    return {
        "requirements": dict(row["requirements"]),
        "min_height": row["min_height"],
        "max_height": row["max_height"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_animations -v`
Expected: `OK`, 19 tests

- [ ] **Step 5: Commit**

```bash
git add buildlab/animations.py tests/test_animations.py && git commit -m "feat: query which animations a build can use"
```

---

## Task 4: Reachability — the height range is not the real limit

This is the task that stops the tool lying. An animation's stated height range is a necessary condition; the attribute ceiling on an actual body is the binding one.

**Files:**
- Modify: `buildlab/animations.py`
- Modify: `tests/test_animations.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_animations.py`, before the `if __name__` block:

```python
class TestReachability(unittest.TestCase):
    def test_kyrie_dribble_style_is_unreachable_above_six_two(self):
        # Its stated range is 5'9"-6'4", but it needs 94 speed_with_ball and
        # the ceiling is 93 at 6'3" and 91 at 6'4" on every legal body.
        self.assertTrue(
            animations.reachable_at("Kyrie Irving", "Dribble Style", height_inches=74)
        )
        self.assertFalse(
            animations.reachable_at("Kyrie Irving", "Dribble Style", height_inches=75)
        )
        self.assertFalse(
            animations.reachable_at("Kyrie Irving", "Dribble Style", height_inches=76)
        )

    def test_reachable_range_narrows_the_stated_range(self):
        stated = animations.requirements_of("Kyrie Irving", family="Dribble Style")
        real = animations.reachable_range("Kyrie Irving", "Dribble Style")
        self.assertEqual(stated["max_height"], 76)
        self.assertEqual(real["max_height"], 74)
        self.assertTrue(real["narrower_than_stated"])

    def test_an_unrestricted_package_is_reachable_across_its_whole_range(self):
        # A package with no attribute requirement can never be ceiling-blocked.
        row = next(r for r in animations.packages() if not r["requirements"])
        real = animations.reachable_range(row["name"], row["family"])
        self.assertEqual(real["min_height"], row["min_height"])
        self.assertEqual(real["max_height"], row["max_height"])
        self.assertFalse(real["narrower_than_stated"])

    def test_reachable_range_reports_the_binding_attribute(self):
        real = animations.reachable_range("Kyrie Irving", "Dribble Style")
        self.assertEqual(real["blocked_by"], "speed_with_ball")

    def test_unreachable_everywhere_is_reported_not_crashed(self):
        # If some package were unreachable at every legal height, that must
        # come back as an empty range rather than an exception.
        real = animations.reachable_range("Kyrie Irving", "Dribble Style")
        self.assertIsNotNone(real["min_height"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_animations -v`
Expected: FAIL with `AttributeError: module 'buildlab.animations' has no attribute 'reachable_at'`

- [ ] **Step 3: Write the implementation**

Append to `buildlab/animations.py`:

```python
@functools.lru_cache(maxsize=None)
def max_ceiling_at(height_inches, attribute):
    """Highest ceiling for an attribute across every legal body at a height.

    Scans all legal weight and wingspan combinations at that height. Returns 0
    if no position permits the height at all.
    """
    from buildlab import body, reference

    best = 0
    for position in reference.legal_bodies():
        for entry in position["bodies"]:
            if entry["height_inches"] != height_inches:
                continue
            weights = entry["weight_lb"]
            spans = entry["wingspan_inches"]
            for weight in range(weights[0], weights[1] + 1):
                for wingspan in range(spans[0], spans[1] + 1):
                    caps = body.ceilings(
                        height=height_inches, weight=weight, wingspan=wingspan
                    )
                    if caps[attribute] > best:
                        best = caps[attribute]
    return best


def reachable_at(name, family, height_inches):
    """Whether a package's requirements are physically reachable at a height.

    The stated height range is a necessary condition. This checks the
    sufficient one: that some legal body at this height has a ceiling high
    enough for every attribute the package requires.
    """
    row = by_name(name, family)
    if not row["min_height"] <= height_inches <= row["max_height"]:
        return False
    for attribute, minimum in row["requirements"].items():
        if max_ceiling_at(height_inches, attribute) < minimum:
            return False
    return True


def reachable_range(name, family):
    """The heights where a package is actually attainable.

    Returns `min_height`, `max_height`, `narrower_than_stated`, and
    `blocked_by` — the attribute whose ceiling binds, or None. Both heights are
    None if the package is unreachable at every legal height.
    """
    row = by_name(name, family)
    heights = [
        h
        for h in range(row["min_height"], row["max_height"] + 1)
        if reachable_at(name, family, h)
    ]
    blocked_by = None
    if len(heights) < (row["max_height"] - row["min_height"] + 1):
        worst = None
        for attribute, minimum in row["requirements"].items():
            shortfall = minimum - max_ceiling_at(row["max_height"], attribute)
            if worst is None or shortfall > worst[1]:
                worst = (attribute, shortfall)
        if worst and worst[1] > 0:
            blocked_by = worst[0]
    return {
        "min_height": heights[0] if heights else None,
        "max_height": heights[-1] if heights else None,
        "narrower_than_stated": len(heights)
        < (row["max_height"] - row["min_height"] + 1),
        "blocked_by": blocked_by,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_animations -v`
Expected: `OK`, 24 tests. `max_ceiling_at` scans every legal weight and wingspan, so the first call at each height is slow; the cache makes the rest fast.

If `test_kyrie_dribble_style_is_unreachable_above_six_two` fails, print the actual ceilings with
`python -c "from buildlab import animations; print([(h, animations.max_ceiling_at(h, 'speed_with_ball')) for h in range(69, 78)])"`
and **report rather than adjusting the test**. The values 93 at 75 and 91 at 76 were measured directly; a change means either `body.ceilings` regressed or the data moved.

- [ ] **Step 5: Commit**

```bash
git add buildlab/animations.py tests/test_animations.py && git commit -m "feat: report where an animation is actually reachable, not just permitted"
```

---

## Task 5: Threshold ladders

For any attribute on a given body, what each additional point buys — in animations and badge tiers together, including the knock-on cost from linked attribute constraints.

**Files:**
- Create: `buildlab/ladders.py`
- Create: `tests/test_ladders.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ladders.py`:

```python
import unittest

from buildlab import ladders


class TestLadder(unittest.TestCase):
    def test_ladder_returns_steps_in_ascending_rating_order(self):
        steps = ladders.ladder("ball_handle", height_inches=76)
        self.assertGreater(len(steps), 0)
        ratings = [s["rating"] for s in steps]
        self.assertEqual(ratings, sorted(ratings))

    def test_every_step_unlocks_something(self):
        for step in ladders.ladder("ball_handle", height_inches=76):
            with self.subTest(rating=step["rating"]):
                self.assertTrue(step["animations"] or step["badges"])

    def test_steps_stay_within_the_reachable_ceiling(self):
        steps = ladders.ladder("ball_handle", height_inches=76)
        ceiling = ladders.max_ceiling("ball_handle", height_inches=76)
        for step in steps:
            with self.subTest(rating=step["rating"]):
                self.assertLessEqual(step["rating"], ceiling)

    def test_badge_tiers_appear_as_steps(self):
        steps = ladders.ladder("ball_handle", height_inches=76)
        badge_steps = [s for s in steps if s["badges"]]
        self.assertGreater(len(badge_steps), 0)

    def test_animation_unlocks_appear_as_steps(self):
        steps = ladders.ladder("speed_with_ball", height_inches=74)
        animation_steps = [s for s in steps if s["animations"]]
        self.assertGreater(len(animation_steps), 0)

    def test_dead_points_are_identified(self):
        dead = ladders.dead_points("ball_handle", height_inches=76, rating=87)
        self.assertIsInstance(dead, dict)
        self.assertIn("wasted", dead)
        self.assertIn("next_unlock_at", dead)

    def test_unknown_attribute_raises(self):
        with self.assertRaises(KeyError):
            ladders.ladder("not_an_attribute", height_inches=76)


class TestFullCost(unittest.TestCase):
    def test_speed_with_ball_drags_in_its_linked_attributes(self):
        # SpeedWithBall <= Speed + 0, <= BallControl + 5, <= Agility + 15.
        cost = ladders.full_cost_of({"speed_with_ball": 94}, height_inches=74)
        self.assertEqual(cost["speed_with_ball"], 94)
        self.assertEqual(cost["speed"], 94)
        self.assertEqual(cost["ball_handle"], 89)
        self.assertEqual(cost["agility"], 79)

    def test_an_unlinked_request_costs_only_itself(self):
        cost = ladders.full_cost_of({"free_throw": 80}, height_inches=75)
        self.assertEqual(cost, {"free_throw": 80})

    def test_full_cost_respects_an_existing_higher_value(self):
        cost = ladders.full_cost_of(
            {"speed_with_ball": 94, "speed": 99}, height_inches=74
        )
        self.assertEqual(cost["speed"], 99)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ladders -v`
Expected: FAIL with `ImportError: cannot import name 'ladders'`

- [ ] **Step 3: Write the implementation**

Create `buildlab/ladders.py`:

```python
"""Threshold ladders: what each additional point in an attribute buys."""

import functools

from buildlab import animations, badges, constraints, reference, tables


def _attribute_index(attribute):
    names = reference.attribute_names()
    if attribute not in names:
        raise KeyError(
            f"no builder attribute named {attribute!r}; valid names are {names}"
        )
    return names.index(attribute)


@functools.lru_cache(maxsize=None)
def max_ceiling(attribute, height_inches):
    """Highest reachable value for an attribute at a height, any legal body."""
    _attribute_index(attribute)
    return animations.max_ceiling_at(height_inches, attribute)


@functools.lru_cache(maxsize=None)
def ladder(attribute, height_inches):
    """Every rating at which this attribute unlocks something, ascending.

    Each step is a dict with `rating`, `animations` (list of "family: name")
    and `badges` (list of "badge tier"). Only ratings reachable at this height
    are included: promising an unlock a body cannot reach is worse than
    silence.
    """
    index = _attribute_index(attribute)
    ceiling = max_ceiling(attribute, height_inches)

    steps = {}
    for row in animations.packages():
        if attribute not in row["requirements"]:
            continue
        if not row["min_height"] <= height_inches <= row["max_height"]:
            continue
        minimum = row["requirements"][attribute]
        if minimum > ceiling:
            continue
        steps.setdefault(minimum, {"animations": [], "badges": []})
        steps[minimum]["animations"].append(f"{row['family']}: {row['name']}")

    for badge in badges.definitions():
        if not badges.height_eligible(badge["badge"], height_inches):
            continue
        for tier in badges.TIERS:
            for requirement in badges.requirements_for(badge["badge"], tier):
                if requirement["attribute"] != index:
                    continue
                minimum = requirement["minimum"]
                if minimum > ceiling:
                    continue
                steps.setdefault(minimum, {"animations": [], "badges": []})
                steps[minimum]["badges"].append(f"{badge['name']} {tier}")

    return tuple(
        {
            "rating": rating,
            "animations": sorted(steps[rating]["animations"]),
            "badges": sorted(steps[rating]["badges"]),
        }
        for rating in sorted(steps)
    )


def dead_points(attribute, height_inches, rating):
    """How many points at this rating are buying nothing.

    `wasted` counts points above the last unlock reached. `next_unlock_at` is
    the next rating that buys something, or None if there is nothing further.
    """
    steps = ladder(attribute, height_inches)
    reached = [s["rating"] for s in steps if s["rating"] <= rating]
    upcoming = [s["rating"] for s in steps if s["rating"] > rating]
    last = max(reached) if reached else None
    return {
        "wasted": rating - last if last is not None else 0,
        "last_unlock_at": last,
        "next_unlock_at": min(upcoming) if upcoming else None,
    }


def full_cost_of(targets, height_inches):
    """Expand attribute targets to include everything they force.

    Linked attribute constraints mean an attribute cannot be raised alone: at
    every height `speed_with_ball` is capped at `speed + 0`, `ball_handle + 5`
    and `agility + 15`, so asking for 94 speed with ball really costs four
    attributes. Returns the full set of minimums implied.
    """
    bucket = tables.bucket_for_inches(height_inches)
    to_tuning = reference.TUNING_NAME
    from_tuning = {v: k for k, v in to_tuning.items()}

    resolved = dict(targets)
    changed = True
    while changed:
        changed = False
        for attribute, minimum in list(resolved.items()):
            rules = constraints.rules_for(to_tuning[attribute], bucket)
            for rule in rules:
                partner = from_tuning.get(rule["associated"])
                if partner is None:
                    continue
                needed = minimum - rule["max_delta"]
                if needed > resolved.get(partner, 0):
                    resolved[partner] = needed
                    changed = True
    return {k: v for k, v in resolved.items() if v > 0}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ladders -v`
Expected: `OK`, 10 tests

If `test_speed_with_ball_drags_in_its_linked_attributes` fails, print the rules with
`python -c "from buildlab import constraints, tables; print(constraints.rules_for('SpeedWithBall', tables.bucket_for_inches(74)))"`
and **report rather than adjusting**. The three rules were measured directly.

- [ ] **Step 5: Commit**

```bash
git add buildlab/ladders.py tests/test_ladders.py && git commit -m "feat: threshold ladders and linked-attribute cost expansion"
```

---

## Task 6: `animations` and `ladder` CLI subcommands

**Files:**
- Modify: `buildlab/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`, before the `if __name__` block:

```python
class TestAnimationsCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_animations_lists_available_packages(self):
        values = ",".join(["99"] * 21)
        code, out = self.run_cli(
            ["animations", "--height", "6-3", "--values", values]
        )
        self.assertEqual(code, 0)
        self.assertIn("AVAILABLE", out)

    def test_animations_filters_by_family(self):
        values = ",".join(["99"] * 21)
        code, out = self.run_cli(
            [
                "animations",
                "--height",
                "6-2",
                "--values",
                values,
                "--family",
                "Dribble Style",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("Dribble Style", out)

    def test_animations_rejects_wrong_attribute_count(self):
        code, out = self.run_cli(
            ["animations", "--height", "6-3", "--values", "70,70"]
        )
        self.assertEqual(code, 2)
        self.assertIn("21", out)

    def test_ladder_shows_thresholds(self):
        code, out = self.run_cli(["ladder", "--height", "6-4", "--attribute", "ball_handle"])
        self.assertEqual(code, 0)
        self.assertIn("LADDER", out)
        self.assertIn("ball_handle", out)

    def test_ladder_rejects_an_unknown_attribute(self):
        code, out = self.run_cli(
            ["ladder", "--height", "6-4", "--attribute", "nonsense"]
        )
        self.assertEqual(code, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL — `argparse` rejects `animations` as an invalid choice

- [ ] **Step 3: Write the implementation**

Change the import in `buildlab/cli.py` to:

```python
from buildlab import (
    animations as animations_mod,
    badges as badges_mod,
    ladders,
    ovr,
    reference,
    tokens,
)
```

Add these two functions after `_badges`:

```python
def _animations(args):
    values = [int(v) for v in args.values.split(",")]
    if len(values) != 21:
        print(f"error: expected 21 attribute values, got {len(values)}")
        return 2
    height = parse_height(args.height)
    rows = animations_mod.available(values, height, family=args.family)
    print(f"HEIGHT     {args.height}  ({height} in)")
    print(f"AVAILABLE  {len(rows)} packages")
    print()
    by_family = {}
    for row in rows:
        by_family.setdefault(row["family"], []).append(row["name"])
    for family in sorted(by_family):
        print(f"  {family}:")
        for name in sorted(by_family[family]):
            print(f"    {name}")
    return 0


def _ladder(args):
    height = parse_height(args.height)
    try:
        steps = ladders.ladder(args.attribute, height)
    except KeyError as error:
        print(f"error: {error}")
        return 2
    ceiling = ladders.max_ceiling(args.attribute, height)
    print(f"LADDER  {args.attribute} at {args.height}  (ceiling {ceiling})")
    print()
    for step in steps:
        unlocks = step["badges"] + step["animations"]
        print(f"  {step['rating']:>3}  {unlocks[0]}")
        for extra in unlocks[1:]:
            print(f"       {extra}")
    return 0
```

Register both inside `main`, before `args = parser.parse_args(argv)`:

```python
    an = sub.add_parser("animations", help="show animations a build can use")
    an.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    an.add_argument("--values", required=True, help="21 comma-separated ratings")
    an.add_argument("--family", default=None, help="restrict to one family")
    an.set_defaults(func=_animations)

    la = sub.add_parser("ladder", help="show what each point in an attribute buys")
    la.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    la.add_argument("--attribute", required=True, help="builder attribute name")
    la.set_defaults(func=_ladder)
```

Leave `_eval`, `_badges`, `parse_height` and the existing subcommands untouched.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli -v`
Expected: `OK`, 14 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: every prior test plus the new ones, all passing.

- [ ] **Step 5: Run it for real**

```bash
python -m buildlab.cli ladder --height 6-4 --attribute ball_handle
```

```bash
python -m buildlab.cli animations --height 6-2 --values 70,70,70,70,70,80,80,70,70,90,94,70,70,70,70,70,70,94,80,70,70 --family "Dribble Style"
```

Paste both outputs in your report.

- [ ] **Step 6: Commit**

```bash
git add buildlab/cli.py tests/test_cli.py && git commit -m "feat: add animations and ladder subcommands"
```

---

## Definition of done

- `python -m unittest discover -s tests` passes with no failures and no skips.
- `python -m buildlab.cli ladder --height 6-4 --attribute ball_handle` prints a ladder whose steps stay at or below the reachable ceiling.
- `buildlab.sources.verify()` passes, now covering the animation markdown as well.
- `animations.reachable_range("Kyrie Irving", "Dribble Style")` reports a max height of 74, narrower than the stated 76.
- `ladders.full_cost_of({"speed_with_ball": 94}, 74)` returns all four linked attributes.
- No third-party imports anywhere in `buildlab/`, `tools/` or `tests/`.

## Explicitly not in this plan

The constraint solver, the transcript-critique flow, the data refresh command, the animation quality ratings layer, and the web UI.

Also excluded: **jumpshot bases and releases.** The markdown contains no jumpshot entries at all — verified by search. The shooting section covers Dribble Pull-Up, Go-To Shot, Hop Jumper, Post Fade, Post Hop Shot and Spin Jumper only. That is the single largest gap in the animation data and needs a source before anything can gate on it.
