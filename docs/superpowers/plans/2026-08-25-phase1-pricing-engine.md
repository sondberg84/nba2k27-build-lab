# Phase 1: Data Layer and Pricing Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a verified, dependency-free Python engine that reproduces NBA 2K27's overall-rating and archetype-selection math exactly, gated on reproducing all 256 golden vectors from the upstream dataset.

**Architecture:** Vendored upstream data pinned by commit SHA and per-file hash, parsed by a thin tuning-file reader into typed lookup tables. Pure functions over those tables compute attribute ceilings, archetype eligibility and selection, and overall rating. Correctness is established by test-driven reconstruction against the dataset's own answer key — the formula is not known in advance and is derived through a measured hypothesis ladder.

**Tech Stack:** Python 3.14 standard library only. `unittest` for tests, `urllib` for vendoring, `hashlib` for manifest verification. No pip installs, no third-party packages, no build step.

---

## Context the implementer needs

**This is a reverse-engineering task, not a transcription task.** The upstream dataset ships the tuning tables and an answer key, but not the engine code. The formula must be derived. A preliminary probe established these facts — treat them as given, they are verified:

- `HeightBasedAttributeWeight[HEIGHT_nn][PLAYERTYPE_nn][PLAYERDATA_ATTRIBUTE_XxxAbility]` covers **15 archetypes × 31 heights × 21 attributes**. For any fixed height and archetype, the 21 weights **sum to 100.0** (spot-checked: height bucket 11, archetype 14 → 99.98; archetype 0 → 100.0). It is a percentage model.
- Selecting an archetype by plain weighted-sum argmax reproduces the golden `player_type` on **207 of 256** vectors. It is close but wrong; the remaining 49 need eligibility gates and/or the tiebreaker table.
- `HeightBasedOverallLerp[HEIGHT_11]` gives `Value[0] = [25, 83.5]` and `Value[1] = [25, 99]`, which reads as an input range mapped onto the displayed 25–99 range.
- Naive `lerp(weighted_sum)` does **not** reproduce `detailed`. For golden row 0 the target is `64.688316`; plain weighted sum gives `54.8881` and rating-scaled gives `59.176948`. Working backwards, the correct pre-lerp value is approximately `56.3753`. The rating-weight scale is involved but not in the way first tried.
- `AttributeRatingWeightScale[PLAYERDATA_ATTRIBUTE_XxxAbility][rating]` has exactly **25 entries per attribute, covering ratings 75–99**. Ratings below 75 have no entry.
- `DataPerArchetype[NAME].MinMaxValuePerAttribute[Attr][0]` supplies **504 rows** of per-archetype attribute minimums. `StrengthsAndWeaknessesTieBreakerRank` supplies **106 rows**.

**Upstream pin:** `lightmatmul/nba2k27-builder-dataset` at commit `957d009`. That repo made three corrections within a day of creation; the pin is not optional.

**Attribute name mapping.** The builder's `reference/attributes.json` uses snake_case names in index order 0–20. The tuning tables use different identifiers. This mapping is required in several tasks and is verified correct:

| index | attributes.json | tuning identifier |
|---|---|---|
| 0 | close_shot | ShotClose |
| 1 | driving_layup | DrivingLayup |
| 2 | driving_dunk | DrivingDunk |
| 3 | standing_dunk | StandingDunk |
| 4 | post_control | PostControl |
| 5 | mid_range | ShotMidrange |
| 6 | three_point | ShotThree |
| 7 | free_throw | ShotFreeThrow |
| 8 | pass_accuracy | PassAccuracy |
| 9 | ball_handle | BallControl |
| 10 | speed_with_ball | SpeedWithBall |
| 11 | interior_defense | InteriorDefense |
| 12 | perimeter_defense | PerimeterDefense |
| 13 | steal | Steal |
| 14 | block | Block |
| 15 | offensive_rebound | ReboundOffense |
| 16 | defensive_rebound | ReboundDefense |
| 17 | speed | Speed |
| 18 | agility | Agility |
| 19 | strength | Strength |
| 20 | vertical | Vertical |

Note `ball_handle` maps to `BallControl`, not `BallHandle`. Note the tuning file also contains `StaminaAbility`, which is **not** a builder attribute and must be excluded.

**Project root:** `C:\Users\jns\OneDrive\Documents\2k\2k27\claude code`. All paths below are relative to it. Git remote `origin` is `sondberg84/nba2k27-build-lab` (private).

---

## File structure

| File | Responsibility |
|---|---|
| `buildlab/__init__.py` | Package marker, version constant |
| `buildlab/sources.py` | Load and verify `data/SOURCES.json`; refuse unhashed data |
| `buildlab/tuning.py` | Parse `progression_attributes.txt` into a flat `dict[str, str]` |
| `buildlab/reference.py` | Load `attributes.json` and `legal_bodies.json`; the name mapping |
| `buildlab/tables.py` | Typed lookups built from tuning: weights, rating scale, lerp, height buckets |
| `buildlab/body.py` | Body legality and attribute ceilings |
| `buildlab/archetypes.py` | Archetype minimums, eligibility, selection |
| `buildlab/ovr.py` | Overall rating computation |
| `buildlab/cli.py` | `eval` subcommand |
| `tools/vendor.py` | Download upstream at a pinned SHA, write the manifest |
| `tools/probe.py` | Formula-discovery harness (Task 8), reports match rates |
| `tests/test_*.py` | One test module per source module |
| `tests/test_golden.py` | The 256/256 gate |

Each module is a single responsibility and is importable alone. `ovr.py` depends on `tables.py` and `archetypes.py` and nothing else.

---

## Task 1: Project scaffold

**Files:**
- Create: `buildlab/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_smoke.py`:

```python
import unittest

import buildlab


class TestPackage(unittest.TestCase):
    def test_version_present(self):
        self.assertEqual(buildlab.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_smoke -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'buildlab'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/__init__.py`:

```python
"""NBA 2K27 build engine."""

__version__ = "0.1.0"
```

Create an empty `tests/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_smoke -v`
Expected: `OK`, 1 test

- [ ] **Step 5: Commit**

```bash
git add buildlab/__init__.py tests/__init__.py tests/test_smoke.py && git commit -m "chore: scaffold buildlab package and test runner"
```

---

## Task 2: Vendor upstream data with a pinned manifest

**Files:**
- Create: `tools/vendor.py`
- Create: `buildlab/sources.py`
- Create: `tests/test_sources.py`
- Generated: `data/SOURCES.json`, `data/engine/*.json`, `data/engine/progression_attributes.txt`

- [ ] **Step 1: Write the vendoring tool**

Create `tools/vendor.py`:

```python
"""Download upstream dataset files at a pinned commit and write the manifest."""

import hashlib
import json
import pathlib
import urllib.request

REPO = "lightmatmul/nba2k27-builder-dataset"
COMMIT = "957d009"
FILES = [
    "reference/attributes.json",
    "reference/enums.json",
    "bodies/legal_bodies.json",
    "bodies/attribute_caps_sample.json",
    "overall/mixed_vectors.json",
    "overall/uniform_ratings.json",
    "overall/official_ui_verified.json",
    "badges/definitions.json",
    "badges/tier_requirements.json",
    "badges/token_costs.json",
    "badges/token_contributions.json",
    "cap_breakers/gains_by_rating.json",
    "tuning/progression_attributes.txt",
]

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "engine"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    entries = {}
    for rel in FILES:
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{rel}"
        with urllib.request.urlopen(url) as response:
            payload = response.read()
        out = DEST / rel.replace("/", "__")
        out.write_bytes(payload)
        entries[rel] = {
            "local": f"data/engine/{out.name}",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        print(f"{rel}  {len(payload)} bytes")

    manifest = {
        "sources": [
            {
                "name": "nba2k27-builder-dataset",
                "url": f"https://github.com/{REPO}",
                "commit": COMMIT,
                "files": entries,
            }
        ]
    }
    (ROOT / "data" / "SOURCES.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote manifest with {len(entries)} files")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the vendoring tool**

Run: `python tools/vendor.py`
Expected: 13 lines of `path  N bytes`, then `wrote manifest with 13 files`. `progression_attributes.txt` should report roughly 1,336,000 bytes.

- [ ] **Step 3: Write the failing test**

Create `tests/test_sources.py`:

```python
import unittest

from buildlab import sources


class TestSources(unittest.TestCase):
    def test_manifest_lists_thirteen_files(self):
        manifest = sources.load()
        self.assertEqual(len(manifest["sources"][0]["files"]), 13)

    def test_commit_is_pinned(self):
        manifest = sources.load()
        self.assertEqual(manifest["sources"][0]["commit"], "957d009")

    def test_every_file_matches_its_hash(self):
        # verify() raises if any vendored file has drifted from the manifest
        sources.verify()

    def test_path_for_returns_existing_file(self):
        path = sources.path_for("tuning/progression_attributes.txt")
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m unittest tests.test_sources -v`
Expected: FAIL with `ImportError: cannot import name 'sources'`

- [ ] **Step 5: Write minimal implementation**

Create `buildlab/sources.py`:

```python
"""Manifest-gated access to vendored upstream data."""

import functools
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "SOURCES.json"


class SourceError(RuntimeError):
    """Raised when vendored data is missing or does not match the manifest."""


@functools.lru_cache(maxsize=1)
def load():
    if not MANIFEST.exists():
        raise SourceError(f"missing manifest {MANIFEST}; run tools/vendor.py")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _entry(rel):
    for source in load()["sources"]:
        if rel in source["files"]:
            return source["files"][rel]
    raise SourceError(f"{rel} is not in the manifest")


def path_for(rel):
    path = ROOT / _entry(rel)["local"]
    if not path.exists():
        raise SourceError(f"missing vendored file {path}; run tools/vendor.py")
    return path


def verify():
    """Raise SourceError if any vendored file differs from its recorded hash."""
    for source in load()["sources"]:
        for rel, entry in source["files"].items():
            path = ROOT / entry["local"]
            if not path.exists():
                raise SourceError(f"missing vendored file {path}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != entry["sha256"]:
                raise SourceError(
                    f"{rel} hash mismatch: manifest {entry['sha256'][:12]}, "
                    f"on disk {digest[:12]}"
                )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m unittest tests.test_sources -v`
Expected: `OK`, 4 tests

- [ ] **Step 7: Commit**

```bash
git add tools/vendor.py buildlab/sources.py tests/test_sources.py data && git commit -m "feat: vendor upstream dataset at pinned commit with hash manifest"
```

---

## Task 3: Tuning file parser

**Files:**
- Create: `buildlab/tuning.py`
- Create: `tests/test_tuning.py`

The file format is `key,value` per line. `//` marks comments. A leading `DataPath|...` line is an export header, not data. Values may themselves contain no commas (verified: `partition(",")` on the first comma is correct).

- [ ] **Step 1: Write the failing test**

Create `tests/test_tuning.py`:

```python
import unittest

from buildlab import tuning


class TestTuning(unittest.TestCase):
    def setUp(self):
        self.table = tuning.load()

    def test_comments_and_header_excluded(self):
        for key in self.table:
            self.assertFalse(key.startswith("//"))
            self.assertNotEqual(key, "DataPath")

    def test_known_scalar_value(self):
        self.assertEqual(self.table["VCRequiredToBuyRangeOfAttributes[0]"], "40000")

    def test_known_weight_value(self):
        key = (
            "HeightBasedAttributeWeight[HEIGHT_05][PLAYERTYPE_00]"
            "[PLAYERDATA_ATTRIBUTE_AgilityAbility]"
        )
        self.assertEqual(self.table[key], "6.55")

    def test_height_bucket_count(self):
        buckets = [k for k in self.table if k.startswith("HeightInWholeInches")]
        self.assertEqual(len(buckets), 31)

    def test_weight_row_count(self):
        rows = [k for k in self.table if k.startswith("HeightBasedAttributeWeight")]
        self.assertEqual(len(rows), 6271)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_tuning -v`
Expected: FAIL with `ImportError: cannot import name 'tuning'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/tuning.py`:

```python
"""Reader for the named key/value tuning export."""

import functools

from buildlab import sources

REL = "tuning/progression_attributes.txt"


@functools.lru_cache(maxsize=1)
def load():
    """Return the tuning export as a flat dict of key -> raw string value."""
    table = {}
    path = sources.path_for(REL)
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("DataPath"):
                continue
            key, sep, value = line.partition(",")
            if not sep:
                continue
            table[key.strip()] = value.strip()
    return table
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_tuning -v`
Expected: `OK`, 5 tests

- [ ] **Step 5: Commit**

```bash
git add buildlab/tuning.py tests/test_tuning.py && git commit -m "feat: parse the named tuning export into a flat table"
```

---

## Task 4: Reference data and the attribute name mapping

**Files:**
- Create: `buildlab/reference.py`
- Create: `tests/test_reference.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_reference.py`:

```python
import unittest

from buildlab import reference


class TestReference(unittest.TestCase):
    def test_twenty_one_attributes_in_index_order(self):
        attrs = reference.attributes()
        self.assertEqual(len(attrs), 21)
        self.assertEqual([a["index"] for a in attrs], list(range(21)))

    def test_first_and_last_attribute_names(self):
        names = reference.attribute_names()
        self.assertEqual(names[0], "close_shot")
        self.assertEqual(names[20], "vertical")

    def test_ball_handle_maps_to_ball_control(self):
        self.assertEqual(reference.TUNING_NAME["ball_handle"], "BallControl")

    def test_mapping_covers_every_attribute(self):
        for name in reference.attribute_names():
            self.assertIn(name, reference.TUNING_NAME)

    def test_tuning_order_matches_attribute_order(self):
        order = reference.tuning_order()
        self.assertEqual(len(order), 21)
        self.assertEqual(order[0], "ShotClose")
        self.assertEqual(order[9], "BallControl")

    def test_five_positions_with_expected_height_ranges(self):
        bodies = reference.legal_bodies()
        ranges = {b["position"]: tuple(b["height_inches"]) for b in bodies}
        self.assertEqual(ranges["PG"], (69, 79))
        self.assertEqual(ranges["SG"], (72, 80))
        self.assertEqual(ranges["C"], (79, 88))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_reference -v`
Expected: FAIL with `ImportError: cannot import name 'reference'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/reference.py`:

```python
"""Builder reference data and the attribute name mapping."""

import functools
import json

from buildlab import sources

TUNING_NAME = {
    "close_shot": "ShotClose",
    "driving_layup": "DrivingLayup",
    "driving_dunk": "DrivingDunk",
    "standing_dunk": "StandingDunk",
    "post_control": "PostControl",
    "mid_range": "ShotMidrange",
    "three_point": "ShotThree",
    "free_throw": "ShotFreeThrow",
    "pass_accuracy": "PassAccuracy",
    "ball_handle": "BallControl",
    "speed_with_ball": "SpeedWithBall",
    "interior_defense": "InteriorDefense",
    "perimeter_defense": "PerimeterDefense",
    "steal": "Steal",
    "block": "Block",
    "offensive_rebound": "ReboundOffense",
    "defensive_rebound": "ReboundDefense",
    "speed": "Speed",
    "agility": "Agility",
    "strength": "Strength",
    "vertical": "Vertical",
}


def _rows(rel):
    payload = json.loads(sources.path_for(rel).read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


@functools.lru_cache(maxsize=1)
def attributes():
    return sorted(_rows("reference/attributes.json"), key=lambda a: a["index"])


@functools.lru_cache(maxsize=1)
def attribute_names():
    return tuple(a["name"] for a in attributes())


@functools.lru_cache(maxsize=1)
def tuning_order():
    """Tuning identifiers in builder attribute-index order."""
    return tuple(TUNING_NAME[name] for name in attribute_names())


@functools.lru_cache(maxsize=1)
def legal_bodies():
    return _rows("bodies/legal_bodies.json")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_reference -v`
Expected: `OK`, 6 tests

If `test_five_positions_with_expected_height_ranges` fails on the C range, print the actual value with `python -c "from buildlab import reference; print([(b['position'], b['height_inches']) for b in reference.legal_bodies()])"` and correct the assertion to the real data. PG `(69, 79)` and SG `(72, 80)` are verified; the C range is asserted from the same source and should hold.

- [ ] **Step 5: Commit**

```bash
git add buildlab/reference.py tests/test_reference.py && git commit -m "feat: load builder reference data and attribute name mapping"
```

---

## Task 5: Typed lookup tables

**Files:**
- Create: `buildlab/tables.py`
- Create: `tests/test_tables.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tables.py`:

```python
import unittest

from buildlab import reference, tables


class TestTables(unittest.TestCase):
    def test_height_buckets_cover_64_to_94_inches(self):
        buckets = tables.height_buckets()
        self.assertEqual(len(buckets), 31)
        self.assertEqual(buckets[0], 64)
        self.assertEqual(buckets[30], 94)

    def test_bucket_for_inches_round_trips(self):
        self.assertEqual(tables.bucket_for_inches(75), 11)
        self.assertEqual(tables.bucket_for_inches(64), 0)

    def test_fifteen_archetype_slots(self):
        self.assertEqual(len(tables.player_types()), 15)

    def test_weight_buckets_match_the_legal_height_range(self):
        # The weight table covers buckets 5-24 only, which is exactly 69-88
        # inches — the union of every position's legal height range. Heights
        # outside it have no weight data because no build can reach them.
        self.assertEqual(tables.weight_buckets(), tuple(range(5, 25)))

    def test_weights_sum_to_one_hundred(self):
        # A percentage model: every (height, archetype) row sums to 100 within
        # rounding slack, because the shipped values are 2-decimal rounded.
        for bucket in tables.weight_buckets():
            for player_type in tables.player_types():
                total = sum(tables.weights(bucket, player_type))
                self.assertAlmostEqual(total, 100.0, delta=0.15)

    def test_missing_attribute_weight_reads_as_zero(self):
        # 29 of the 300 (bucket, archetype) rows omit StandingDunk entirely,
        # all at buckets 5-8 (69-72 in). Those rows already sum to ~100 without
        # it, so an omitted entry is an implicit 0.0, not an error.
        index = reference.tuning_order().index("StandingDunk")
        self.assertEqual(tables.weights(5, 0)[index], 0.0)

    def test_weights_rejects_a_bucket_with_no_data(self):
        with self.assertRaises(KeyError):
            tables.weights(0, 0)

    def test_weight_vector_is_attribute_ordered(self):
        vector = tables.weights(5, 0)
        self.assertEqual(len(vector), 21)

    def test_rating_scale_covers_75_to_99_only(self):
        scale = tables.rating_scale()
        ratings = sorted({rating for _, rating in scale})
        self.assertEqual(ratings[0], 75)
        self.assertEqual(ratings[-1], 99)

    def test_scale_defaults_to_one_below_75(self):
        self.assertEqual(tables.scale_for("BallControl", 74), 1.0)
        self.assertEqual(tables.scale_for("BallControl", 75), 1.01)

    def test_lerp_endpoints_for_bucket_11(self):
        self.assertEqual(tables.lerp_points(11), ((25.0, 83.5), (25.0, 99.0)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_tables -v`
Expected: FAIL with `ImportError: cannot import name 'tables'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/tables.py`:

```python
"""Typed lookup tables derived from the tuning export."""

import functools
import re

from buildlab import reference, tuning

WEIGHT_RE = re.compile(
    r"^HeightBasedAttributeWeight\[HEIGHT_(\d+)\]\[PLAYERTYPE_(\d+)\]"
    r"\[PLAYERDATA_ATTRIBUTE_(\w+)Ability\]$"
)
SCALE_RE = re.compile(
    r"^AttributeRatingWeightScale\[PLAYERDATA_ATTRIBUTE_(\w+)Ability\]\[(\d+)\]$"
)
LERP_RE = re.compile(r"^HeightBasedOverallLerp\[HEIGHT_(\d+)\]\.Value\[(\d)\]\[(\d)\]$")
BUCKET_RE = re.compile(r"^HeightInWholeInches\[HEIGHT_(\d+)\]$")


@functools.lru_cache(maxsize=1)
def height_buckets():
    """Bucket index -> whole inches."""
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = BUCKET_RE.match(key)
        if match:
            out[int(match.group(1))] = int(value)
    return out


def bucket_for_inches(inches):
    for bucket, value in height_buckets().items():
        if value == inches:
            return bucket
    raise KeyError(f"no height bucket for {inches} inches")


@functools.lru_cache(maxsize=1)
def _weight_index():
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = WEIGHT_RE.match(key)
        if match:
            bucket, player_type, attr = match.groups()
            out[(int(bucket), int(player_type), attr)] = float(value)
    return out


@functools.lru_cache(maxsize=1)
def player_types():
    return tuple(sorted({pt for _, pt, _ in _weight_index()}))


@functools.lru_cache(maxsize=1)
def weight_buckets():
    """Height buckets the weight table covers: 5-24, i.e. 69-88 inches.

    This is exactly the union of every position's legal height range. Heights
    outside it carry no weight data because no build can reach them.
    """
    return tuple(sorted({bucket for bucket, _, _ in _weight_index()}))


@functools.lru_cache(maxsize=None)
def weights(bucket, player_type):
    """21 weights in builder attribute-index order.

    An attribute absent from a row is an implicit 0.0, not an error: 29 of the
    300 rows omit StandingDunk at buckets 5-8, and those rows already sum to
    ~100 without it. A bucket with no data at all is an error, because it means
    the caller asked about a height no build can have.
    """
    covered = weight_buckets()
    if bucket not in covered:
        raise KeyError(
            f"no weight data for height bucket {bucket}; "
            f"covered buckets are {covered[0]}-{covered[-1]}"
        )
    index = _weight_index()
    return tuple(
        index.get((bucket, player_type, attr), 0.0)
        for attr in reference.tuning_order()
    )


@functools.lru_cache(maxsize=1)
def rating_scale():
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = SCALE_RE.match(key)
        if match:
            out[(match.group(1), int(match.group(2)))] = float(value)
    return out


def scale_for(attr, rating):
    """Rating weight scale, defaulting to 1.0 below the table's floor of 75."""
    return rating_scale().get((attr, rating), 1.0)


@functools.lru_cache(maxsize=1)
def _lerp_index():
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = LERP_RE.match(key)
        if match:
            bucket, i, j = (int(g) for g in match.groups())
            out[(bucket, i, j)] = float(value)
    return out


def lerp_points(bucket):
    """((x0, x1), (y0, y1)) for the overall display curve at this height."""
    index = _lerp_index()
    return (
        (index[(bucket, 0, 0)], index[(bucket, 0, 1)]),
        (index[(bucket, 1, 0)], index[(bucket, 1, 1)]),
    )


def lerp(bucket, value):
    (x0, x1), (y0, y1) = lerp_points(bucket)
    return y0 + (value - x0) / (x1 - x0) * (y1 - y0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_tables -v`
Expected: `OK`, 8 tests

If `test_weights_sum_to_one_hundred` fails for a specific bucket or archetype, do not widen the delta past 0.15. Print the offending row and stop — a row that does not sum to 100 means the weight table has a structure the parser is missing, and that must be understood before Task 8.

- [ ] **Step 5: Commit**

```bash
git add buildlab/tables.py tests/test_tables.py && git commit -m "feat: build typed weight, scale and lerp lookups from tuning"
```

---

## Task 6: Body legality and attribute ceilings

**Files:**
- Create: `buildlab/body.py`
- Create: `tests/test_body.py`

The upstream README states the ceiling formula as
`ceiling = clamp(round(25 + 74 * height_mult * weight_mult * wingspan_mult), 25, 99)`
and reports it reproduces all 21 measured ceilings. The multiplier tables must be located in the tuning export first.

The three multiplier tables have been located. Their exact key shapes are:

```
PlayerRestrictions[NBA].HeightMultiplier[HEIGHT_05][Agility]            0.98
PlayerRestrictions[NBA].WeightMultiplier[0].HeightInInches              69
PlayerRestrictions[NBA].WeightMultiplier[0].Weight                      <lb>
PlayerRestrictions[NBA].WeightMultiplier[0].Multiplier[BallControl]     1
PlayerRestrictions[NBA].WingspanMultiplier[0].HeightInInches            69
PlayerRestrictions[NBA].WingspanMultiplier[0].WingspanInInches          <in>
PlayerRestrictions[NBA].WingspanMultiplier[0].Multiplier[Block]         0.88
```

Height multipliers are indexed by height bucket and tuning attribute name. Weight and wingspan multipliers use a **flat row index** (84 rows each); each row carries its own `HeightInInches` plus the `Weight` or `WingspanInInches` it applies at, and then one `Multiplier[Attr]` per attribute. So the lookup is: find the row matching this height and this weight (or wingspan), then read that row's multiplier for the attribute.

The multiplier row structure has also been confirmed. Weight and wingspan multipliers ship as **paired rows per height, giving the endpoints of a range**:

```
WeightMultiplier   46 rows:  row 0 height 69 Weight 145   row 1 height 69 Weight 185
                             row 2 height 70 Weight 150   row 3 height 70 Weight 190
WingspanMultiplier 42 rows:  row 0 height 69 Wingspan 69  row 1 height 69 Wingspan 75
                             row 2 height 70 Wingspan 70  row 3 height 70 Wingspan 76
```

Each height carries a low row and a high row, and those endpoints match the legal weight and wingspan bounds for that height in `bodies/legal_bodies.json`. So the multiplier for an actual weight or wingspan is a **linear interpolation between the two rows at that height**, per attribute. Height multipliers are a direct lookup, `HeightMultiplier[HEIGHT_nn][Attr]`, with no interpolation.

Note the row counts differ (46 vs 42) and neither is 2 × 31, so do not assume every height bucket appears. Build the index from what is actually present and key it by the `HeightInInches` value each row declares.

**The answer key.** `bodies/attribute_caps_sample.json` describes exactly one reference body — PG, 75 in, 198 lb, 78 in wingspan — with 21 rows shaped `{"attribute": 0, "name": "close_shot", "cap": 99}`. It is a single body, not a table of bodies.

- [ ] **Step 1: Write the failing test**

Create `tests/test_body.py`:

```python
import json
import unittest

from buildlab import body, sources

# The one body bodies/attribute_caps_sample.json was probed at.
REFERENCE = {"height": 75, "weight": 198, "wingspan": 78}


class TestBody(unittest.TestCase):
    def test_reference_body_is_legal(self):
        self.assertTrue(body.is_legal("PG", **REFERENCE))

    def test_height_outside_position_range_is_illegal(self):
        self.assertFalse(body.is_legal("PG", height=84, weight=250, wingspan=88))

    def test_wingspan_is_height_to_height_plus_six(self):
        self.assertTrue(body.is_legal("PG", height=75, weight=198, wingspan=81))
        self.assertFalse(body.is_legal("PG", height=75, weight=198, wingspan=82))

    def test_weight_outside_the_row_bounds_is_illegal(self):
        self.assertFalse(body.is_legal("PG", height=75, weight=120, wingspan=78))

    def test_ceilings_match_the_measured_sample(self):
        payload = json.loads(
            sources.path_for("bodies/attribute_caps_sample.json").read_text(
                encoding="utf-8"
            )
        )
        rows = payload["data"]
        self.assertEqual(len(rows), 21)
        got = body.ceilings(**REFERENCE)
        for row in rows:
            with self.subTest(attribute=row["name"]):
                self.assertEqual(got[row["name"]], row["cap"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m unittest tests.test_body -v`
Expected: FAIL with `ImportError: cannot import name 'body'`

- [ ] **Step 5: Write the implementation**

Create `buildlab/body.py` implementing:

- `is_legal(position, height, weight, wingspan)` — looks up the position's body rows from `reference.legal_bodies()`, finds the row for `height`, and checks `weight` is within `weight_lb` and `wingspan` is within `wingspan_inches`. Return `False` for an unknown position or a height with no row.
- `ceilings(height, weight, wingspan)` — returns a dict of attribute name to integer ceiling, using the multiplier tables located in Step 1 and the formula `max(25, min(99, round(25 + 74 * h_mult * w_mult * ws_mult)))`.

Use Python's `round`. If the test shows systematic off-by-one on `.5` values, switch to `math.floor(x + 0.5)` — the engine is C++ and rounds half away from zero, while Python rounds half to even.

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m unittest tests.test_body -v`
Expected: `OK`, 4 tests, with every ceiling subtest passing

- [ ] **Step 7: Commit**

```bash
git add buildlab/body.py tests/test_body.py && git commit -m "feat: body legality checks and attribute ceiling formula"
```

---

## Task 7: Archetype tables and the baseline selector

This task establishes the measured baseline. It deliberately does **not** try to reach 256/256 — that is Task 8. Locking the baseline in a test makes progress in Task 8 measurable rather than anecdotal.

**Files:**
- Create: `buildlab/archetypes.py`
- Create: `tests/test_archetypes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_archetypes.py`:

```python
import json
import unittest

from buildlab import archetypes, sources


def golden_rows():
    payload = json.loads(
        sources.path_for("overall/mixed_vectors.json").read_text(encoding="utf-8")
    )
    return payload["data"]


class TestArchetypes(unittest.TestCase):
    def test_fifteen_archetypes_named(self):
        self.assertEqual(len(archetypes.names()), 15)

    def test_minimums_cover_every_archetype(self):
        mins = archetypes.minimums()
        self.assertEqual(len(mins), 15)
        for vector in mins.values():
            self.assertEqual(len(vector), 21)

    def test_golden_reference_body_is_six_three(self):
        payload = json.loads(
            sources.path_for("overall/mixed_vectors.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["_meta"]["reference_body"]["height_inches"], 75)

    def test_baseline_argmax_matches_207_of_256(self):
        # Documented baseline, not the target. Task 8 raises this to 256.
        rows = golden_rows()
        hits = sum(
            1
            for row in rows
            if archetypes.select_baseline(11, row["values"]) == row["player_type"]
        )
        self.assertEqual(len(rows), 256)
        self.assertEqual(hits, 207)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_archetypes -v`
Expected: FAIL with `ImportError: cannot import name 'archetypes'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/archetypes.py`:

```python
"""Archetype definitions, eligibility minimums and selection."""

import functools
import re

from buildlab import reference, tables, tuning

MIN_RE = re.compile(
    r"^DataPerArchetype\[(\w+)\]\.MinMaxValuePerAttribute\[(\w+)\]\[(\d)\]$"
)


@functools.lru_cache(maxsize=1)
def _minmax_index():
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = MIN_RE.match(key)
        if match:
            name, attr, slot = match.groups()
            out[(name, attr, int(slot))] = int(value)
    return out


@functools.lru_cache(maxsize=1)
def names():
    return tuple(sorted({name for name, _, _ in _minmax_index()}))


@functools.lru_cache(maxsize=1)
def minimums():
    """Archetype name -> 21 minimum attribute values in builder index order."""
    index = _minmax_index()
    out = {}
    for name in names():
        out[name] = tuple(
            index.get((name, attr, 0), 0) for attr in reference.tuning_order()
        )
    return out


def raw_score(bucket, player_type, values):
    """Plain weighted sum over the 21 attributes, scaled to a 0-99 range."""
    weights = tables.weights(bucket, player_type)
    return sum(w * v for w, v in zip(weights, values)) / 100.0


def select_baseline(bucket, values):
    """Archetype index by plain weighted argmax. Correct on 207/256 goldens."""
    return max(tables.player_types(), key=lambda pt: raw_score(bucket, pt, values))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_archetypes -v`
Expected: `OK`, 4 tests

If `test_fifteen_archetypes_named` reports a count other than 15, print `archetypes.names()` and reconcile against `tables.player_types()`. The `PLAYERTYPE_nn` indices and the `DataPerArchetype[NAME]` keys are two namings of the same 15 archetypes, and establishing that correspondence is required input for Task 8. Record it as a module-level dict `INDEX_BY_NAME` once known.

- [ ] **Step 5: Commit**

```bash
git add buildlab/archetypes.py tests/test_archetypes.py && git commit -m "feat: archetype minimums and baseline weighted-argmax selector"
```

---

## Task 8: Derive the exact formula

This is the research task and the only open-ended one in this plan. It has a hard success criterion and a fixed method: change one thing, measure, keep or discard.

**Files:**
- Create: `tools/probe.py`
- Modify: `buildlab/archetypes.py`
- Modify: `buildlab/ovr.py` (created here)
- Create: `docs/superpowers/notes/ovr-derivation.md`

- [ ] **Step 1: Write the measurement harness**

Create `tools/probe.py`:

```python
"""Formula-discovery harness. Reports match rates against the golden vectors."""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from buildlab import sources, tables  # noqa: E402

BUCKET = 11  # golden vectors use the 6'3 reference body


def golden():
    payload = json.loads(
        sources.path_for("overall/mixed_vectors.json").read_text(encoding="utf-8")
    )
    return payload["data"]


def report(label, select, score):
    rows = golden()
    arch_hits = sum(1 for r in rows if select(BUCKET, r["values"]) == r["player_type"])
    val_hits = 0
    worst = (0.0, None)
    for row in rows:
        got = score(BUCKET, row["player_type"], row["values"])
        delta = abs(got - row["detailed"])
        if delta < 1e-4:
            val_hits += 1
        if delta > worst[0]:
            worst = (delta, row["sample"])
    print(
        f"{label:<34} archetype {arch_hits:>3}/256   detailed {val_hits:>3}/256"
        f"   worst delta {worst[0]:.4f} (sample {worst[1]})"
    )
    return arch_hits, val_hits


if __name__ == "__main__":
    from buildlab import archetypes

    def baseline_score(bucket, pt, values):
        return tables.lerp(bucket, archetypes.raw_score(bucket, pt, values))

    report("baseline: raw argmax + lerp", archetypes.select_baseline, baseline_score)
```

- [ ] **Step 2: Run the harness to confirm the baseline**

Run: `python tools/probe.py`
Expected: a line reading `archetype 207/256` and `detailed 0/256`. This confirms the starting point.

- [ ] **Step 3: Work the hypothesis ladder**

Add one hypothesis at a time to `tools/probe.py` as an additional `report(...)` call. After each, run `python tools/probe.py` and record the numbers in `docs/superpowers/notes/ovr-derivation.md`. Keep a change only if it raises a match rate; revert it otherwise.

Test in this order — earlier items are cheaper and more likely:

1. **Archetype eligibility.** Restrict the argmax to archetypes whose `minimums()` vector is satisfied by the build (every attribute at or above its minimum). If nothing is eligible, fall back to unrestricted argmax. Target: archetype match above 207.
2. **Partial eligibility.** If strict eligibility overshoots and drops the rate, try counting satisfied minimums and ranking by that first, weighted score second.
3. **Tiebreaker.** Inspect `StrengthsAndWeaknessesTieBreakerRank` with
   `python -c "from buildlab import tuning; t=tuning.load(); [print(k,'=',v) for k,v in t.items() if k.startswith('StrengthsAndWeaknesses')]"`.
   Apply it to resolve archetypes within a small epsilon of the top score.
4. **The value curve.** Once archetype selection is 256/256, fit `detailed`. The known target for sample 0 is a pre-lerp value of about `56.3753` where plain weighted sum gives `54.8881` and fully rating-scaled gives `59.176948`. Test, in order:
   a. Scale applied and renormalised: `sum(w*v*s) / sum(w*s)`.
   b. Scale applied to the weight only, not the product: `sum(w*s*v) / 100`.
   c. Scale applied only to attributes at or above the archetype's minimum.
   d. Scale applied, then the lerp taken over the scaled input range rather than `[25, 83.5]`.
5. **Clamping.** `mixed_vectors.json` carries `uncapped` alongside `detailed`. If `detailed` resists, fit `uncapped` first — it is the same number before the 99 display clamp and removes one variable.

Record every hypothesis and its measured result in the notes file, including the failures. A future data refresh may need this reasoning.

- [ ] **Step 4: Promote the winning formula**

Once `python tools/probe.py` reports `archetype 256/256` and `detailed 256/256`:

- Replace `archetypes.select_baseline` with `archetypes.select`, implementing the winning selection rule. Keep `select_baseline` and its 207/256 test as a regression guard.
- Create `buildlab/ovr.py` exposing:
  - `overall(height_inches, values)` -> `int`, the displayed rating
  - `detailed(height_inches, values)` -> `float`, the pre-rounding value
  - `archetype(height_inches, values)` -> `int`, the winning archetype index

Every function takes height in inches and converts via `tables.bucket_for_inches`, so callers never handle bucket indices.

- [ ] **Step 5: Commit**

```bash
git add tools/probe.py buildlab/archetypes.py buildlab/ovr.py docs/superpowers/notes/ovr-derivation.md && git commit -m "feat: derive exact archetype selection and overall rating from tuning tables"
```

---

## Task 9: The 256/256 gate

**Files:**
- Create: `tests/test_golden.py`

This is the gate the whole phase exists to pass. It must not be softened. If it fails, the engine is wrong.

- [ ] **Step 1: Write the failing test**

Create `tests/test_golden.py`:

```python
import json
import unittest

from buildlab import ovr, sources

REFERENCE_HEIGHT = 75  # 6'3, the body the mixed vectors were probed at


def load(rel):
    payload = json.loads(sources.path_for(rel).read_text(encoding="utf-8"))
    return payload["data"], payload.get("_meta", {})


class TestGoldenVectors(unittest.TestCase):
    def test_all_256_archetypes_reproduce(self):
        rows, _ = load("overall/mixed_vectors.json")
        self.assertEqual(len(rows), 256)
        for row in rows:
            with self.subTest(sample=row["sample"]):
                self.assertEqual(
                    ovr.archetype(REFERENCE_HEIGHT, row["values"]), row["player_type"]
                )

    def test_all_256_detailed_values_reproduce(self):
        rows, _ = load("overall/mixed_vectors.json")
        for row in rows:
            with self.subTest(sample=row["sample"]):
                self.assertAlmostEqual(
                    ovr.detailed(REFERENCE_HEIGHT, row["values"]),
                    row["detailed"],
                    places=4,
                )

    def test_all_256_displayed_overalls_reproduce(self):
        rows, _ = load("overall/mixed_vectors.json")
        for row in rows:
            with self.subTest(sample=row["sample"]):
                self.assertEqual(
                    ovr.overall(REFERENCE_HEIGHT, row["values"]), row["overall"]
                )

    def test_uniform_ratings_reproduce(self):
        rows, _ = load("overall/uniform_ratings.json")
        self.assertGreater(len(rows), 0)
        for row in rows:
            with self.subTest(row=row):
                height = row.get("height_inches", REFERENCE_HEIGHT)
                self.assertEqual(ovr.overall(height, row["values"]), row["overall"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the gate**

Run: `python -m unittest tests.test_golden -v`
Expected: `OK`, 4 tests, 0 failures

`test_uniform_ratings_reproduce` may need its field names adjusted to match the real file. Inspect it with
`python -c "import json; from buildlab import sources; d=json.loads(sources.path_for('overall/uniform_ratings.json').read_text(encoding='utf-8')); print(json.dumps(d['data'][0], indent=1)); print(json.dumps(d['_meta'], indent=1)[:600])"`
and use the actual shape. Do not delete the test to make it pass.

- [ ] **Step 3: Run the whole suite**

Run: `python -m unittest discover -s tests -v`
Expected: `OK`, every module passing, no skips

- [ ] **Step 4: Commit**

```bash
git add tests/test_golden.py && git commit -m "test: gate the engine on all 256 golden vectors"
```

---

## Task 10: `eval` command

**Files:**
- Create: `buildlab/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
import io
import unittest
from contextlib import redirect_stdout

from buildlab import cli


class TestCli(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_eval_prints_overall_and_archetype(self):
        values = ",".join(["70"] * 21)
        code, out = self.run_cli(["eval", "--height", "6-3", "--values", values])
        self.assertEqual(code, 0)
        self.assertIn("OVERALL", out)
        self.assertIn("ARCHETYPE", out)

    def test_eval_rejects_wrong_attribute_count(self):
        code, out = self.run_cli(["eval", "--height", "6-3", "--values", "70,70"])
        self.assertEqual(code, 2)
        self.assertIn("21", out)

    def test_height_accepts_feet_dash_inches(self):
        self.assertEqual(cli.parse_height("6-3"), 75)
        self.assertEqual(cli.parse_height("7-4"), 88)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL with `ImportError: cannot import name 'cli'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/cli.py`:

```python
"""Command line entry point."""

import argparse

from buildlab import ovr, reference


def parse_height(text):
    feet, _, inches = text.partition("-")
    return int(feet) * 12 + int(inches)


def _eval(args):
    values = [int(v) for v in args.values.split(",")]
    if len(values) != 21:
        print(f"error: expected 21 attribute values, got {len(values)}")
        return 2
    height = parse_height(args.height)
    print(f"HEIGHT     {args.height}  ({height} in)")
    print(f"OVERALL    {ovr.overall(height, values)}")
    print(f"ARCHETYPE  {ovr.archetype(height, values)}")
    print(f"DETAILED   {ovr.detailed(height, values):.6f}")
    print()
    for name, value in zip(reference.attribute_names(), values):
        print(f"  {name:<20} {value}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="buildlab")
    sub = parser.add_subparsers(dest="command", required=True)
    ev = sub.add_parser("eval", help="evaluate a full attribute vector")
    ev.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    ev.add_argument("--values", required=True, help="21 comma-separated ratings")
    ev.set_defaults(func=_eval)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli -v`
Expected: `OK`, 3 tests

- [ ] **Step 5: Run it for real**

Run: `python -m buildlab.cli eval --height 6-3 --values 47,30,47,26,79,54,87,77,36,55,45,31,73,53,27,40,43,34,85,50,51`
Expected: `OVERALL 64`, `ARCHETYPE 14`, `DETAILED 64.688316` — this is golden sample 0.

- [ ] **Step 6: Commit and push**

```bash
git add buildlab/cli.py tests/test_cli.py && git commit -m "feat: add eval command" && git push origin main
```

---

## Task 11: Linked attribute constraints

The tuning export carries a builder rule the design spec did not account for: attributes are **capped relative to each other**, per height. `AssociatedAttributeConstraints[Agility][HEIGHT_05][0]` names `Speed` with `MaxDelta 10`, meaning at that height Agility may not exceed Speed by more than 10. There are **1,545 such pairs across all 21 attributes**, with deltas of 0, 5, 10, 15, 18, 20, 25, 30, 32, 35 and higher. A `MaxDelta` of 0 is a hard lock to the associated attribute.

This matters beyond ceilings: it means attributes cannot be raised independently, which changes what the solver in a later plan is allowed to propose. Upstream commit `957d009` was specifically "Fix MaxDelta 0 reading", so treat the zero case as a known trap and test it explicitly.

**Files:**
- Create: `buildlab/constraints.py`
- Create: `tests/test_constraints.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_constraints.py`:

```python
import unittest

from buildlab import constraints, reference


class TestConstraints(unittest.TestCase):
    def test_every_attribute_has_constraints(self):
        table = constraints.load()
        covered = {attr for attr, _ in table}
        for name in reference.tuning_order():
            self.assertIn(name, covered)

    def test_agility_is_linked_to_speed_at_bucket_5(self):
        rules = constraints.rules_for("Agility", 5)
        linked = {rule["associated"]: rule["max_delta"] for rule in rules}
        self.assertEqual(linked["Speed"], 10)
        self.assertEqual(linked["ReboundDefense"], 50)

    def test_zero_max_delta_is_preserved_not_dropped(self):
        # Upstream commit 957d009 fixed a bug reading MaxDelta 0. A zero delta
        # is a hard lock, not a missing value, and must survive parsing.
        zeros = [
            (attr, bucket, rule)
            for (attr, bucket), rules in constraints.load().items()
            for rule in rules
            if rule["max_delta"] == 0
        ]
        self.assertGreater(len(zeros), 0)

    def test_effective_ceiling_respects_a_linked_attribute(self):
        values = {name: 40 for name in reference.tuning_order()}
        values["Speed"] = 60
        capped = constraints.effective_ceiling("Agility", 5, values, hard_ceiling=99)
        self.assertEqual(capped, 70)  # Speed 60 + MaxDelta 10

    def test_effective_ceiling_never_exceeds_the_hard_ceiling(self):
        values = {name: 99 for name in reference.tuning_order()}
        capped = constraints.effective_ceiling("Agility", 5, values, hard_ceiling=85)
        self.assertEqual(capped, 85)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_constraints -v`
Expected: FAIL with `ImportError: cannot import name 'constraints'`

- [ ] **Step 3: Write minimal implementation**

Create `buildlab/constraints.py`:

```python
"""Linked attribute constraints: per-height caps relative to other attributes."""

import functools
import re

from buildlab import tuning

RULE_RE = re.compile(
    r"^AssociatedAttributeConstraints\[(\w+)\]\[HEIGHT_(\d+)\]\[(\d+)\]\.(\w+)$"
)


@functools.lru_cache(maxsize=1)
def load():
    """(attribute, height_bucket) -> list of {associated, max_delta}."""
    table = tuning.load()
    staged = {}
    for key, value in table.items():
        match = RULE_RE.match(key)
        if not match:
            continue
        attr, bucket, slot, field = match.groups()
        entry = staged.setdefault((attr, int(bucket)), {}).setdefault(int(slot), {})
        if field == "AssociatedAttribute":
            entry["associated"] = value
        elif field == "MaxDelta":
            # int() so that a shipped "0" survives as a hard lock rather than
            # being treated as absent.
            entry["max_delta"] = int(value)

    out = {}
    for pair, slots in staged.items():
        out[pair] = [slots[slot] for slot in sorted(slots) if "associated" in slots[slot]]
    return out


def rules_for(attr, bucket):
    return load().get((attr, bucket), [])


def effective_ceiling(attr, bucket, values, hard_ceiling):
    """Lowest of the body ceiling and every linked-attribute cap."""
    ceiling = hard_ceiling
    for rule in rules_for(attr, bucket):
        associated = values.get(rule["associated"])
        if associated is None:
            continue
        ceiling = min(ceiling, associated + rule["max_delta"])
    return ceiling
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_constraints -v`
Expected: `OK`, 5 tests

If `test_agility_is_linked_to_speed_at_bucket_5` fails on the `ReboundDefense` delta, print the real rules with
`python -c "from buildlab import constraints; print(constraints.rules_for('Agility', 5))"`
and correct the assertion to the shipped values. The `Speed` / `10` pair is verified and must hold.

- [ ] **Step 5: Commit and push**

```bash
git add buildlab/constraints.py tests/test_constraints.py && git commit -m "feat: parse linked attribute constraints including MaxDelta 0 locks" && git push origin main
```

---

## Definition of done

- `python -m unittest discover -s tests` passes with no failures and no skips.
- `tests/test_golden.py` reproduces all 256 mixed vectors on archetype, detailed value and displayed overall.
- `python -m buildlab.cli eval --height 6-3 --values <golden sample 0>` prints `OVERALL 64`, `ARCHETYPE 14`.
- `data/SOURCES.json` pins commit `957d009` and `buildlab.sources.verify()` passes.
- `docs/superpowers/notes/ovr-derivation.md` records the hypotheses tried in Task 8, including the ones that failed.
- Linked attribute constraints parse with `MaxDelta 0` preserved.
- No third-party imports anywhere in `buildlab/`, `tools/` or `tests/`.

## Explicitly not in this plan

**Badges are deliberately deferred.** The design spec grouped badges into phase 1, but this plan splits them out: badge tier evaluation, token costs, token contributions and the token budget become **plan 1b**, executed straight after this one. The split is because Task 8 is open-ended reverse-engineering and bundling a second subsystem behind it would leave both unfinished for longer. Badges depend on nothing in this plan except `sources.py` and `reference.py`, so they can even proceed in parallel.

Also out of scope: cap breakers, takeovers, animation parsing, threshold ladders, the solver, the critique flow, the refresh command, and the web UI. Those are plans 2 through 5. This plan ends when the pricing engine is proven correct, because nothing downstream can be trusted until it is.

---

## Carried review notes

Raised by the Task 2 code quality review. None blocked that task; each is recorded here so the plan that first stresses the assumption can act on it.

1. **Pin the full 40-character commit SHA, not the abbreviated `957d009`.** `raw.githubusercontent.com` resolves abbreviations today and collision risk is negligible at this repo's size, but a trust boundary whose purpose is supply-chain pinning should record the full SHA. Changing it touches `tools/vendor.py`, the generated `data/SOURCES.json`, and the `test_commit_is_pinned` assertion. Fold into the refresh command (plan 3), which rewrites the manifest anyway.
2. **`verify()` raises on the first hash mismatch rather than collecting all of them.** Harmless while the only remedy is re-running `tools/vendor.py`, which re-downloads everything regardless. Revisit if files ever become hand-editable — `data/ratings.json` in plan 4 is the first case.
3. **`lru_cache(maxsize=1)` on `sources.load()` is a staleness hazard in a long-running process.** Fine for short-lived CLI runs and tests. The web UI in plan 5 is the first resident process against this module; it must either invalidate the cache or re-read the manifest per request.
4. **A corrupted `data/SOURCES.json` surfaces a raw `json.JSONDecodeError`** instead of a `SourceError` with the module's usual "run tools/vendor.py" guidance. Every other failure mode is wrapped consistently. Low probability — the file is machine-generated and committed — but worth aligning when the module is next touched.

Also confirmed during review, worth keeping: `data/** -text` prevents CRLF corruption **without** costing the line-level `git diff` visibility that vendoring exists to provide. The attribute governs end-of-line normalisation only, not git's text/binary diff heuristic.
