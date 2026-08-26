# Phase 4: Data Refresh and the Animation Ratings Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make it safe to take new upstream data — check, preview, adopt, with the golden vectors deciding whether a change is real or a broken capture — and add the user-authored animation quality layer that turns a catalogue into advice.

**Architecture:** Refresh never mutates live data. It fetches to a staging directory, produces a semantic diff, runs the engine's own test vectors against the staged tables, and only then offers to adopt. The ratings layer is a separate hand-edited file that refresh never writes, keyed by animation name and family so an upstream rename is reported rather than silently dropping a rating.

**Tech Stack:** Python 3.14 standard library only. `urllib` for fetching, `hashlib` for hashing, `unittest` for tests. No pip installs, no third-party packages.

---

## Context the implementer needs

Phases 1a, 1b, 2 and 3 are merged. 259 tests pass. Available modules:

- `buildlab.sources` — `path_for(rel)`, `rows_for(rel)`, `verify()`, `load()`, `SourceError`, `ROOT`, `MANIFEST`
- `buildlab.tuning` — `load()` -> flat `dict[str, str]`
- `buildlab.reference`, `buildlab.tables`, `buildlab.body`, `buildlab.archetypes`, `buildlab.ovr`, `buildlab.constraints`
- `buildlab.badges`, `buildlab.tokens`, `buildlab.capbreakers`
- `buildlab.animations` — `packages()`, `by_name(name, family)`, `families()`, `available(...)`, `max_ceiling_at(...)`, `reachable_at`, `reachable_range`
- `buildlab.ladders` — `ATTRIBUTE_FLOOR`, `ladder`, `dead_points`, `full_cost_of`, `max_ceiling`
- `buildlab.goals` — `AttributeGoal`, `BadgeGoal`, `AnimationGoal`
- `buildlab.solver` — `solve_at`, `solve`, `MIN_HEIGHT` 69, `MAX_HEIGHT` 88
- `buildlab.critique` — `critique(values, height_inches)`, `check_claims(...)`
- `buildlab.cli` — `main(argv)`, `parse_height(text)`, `_ft(inches)`, subcommands `eval`, `badges`, `animations`, `ladder`, `reachability`, `solve`, `critique`
- `tools/vendor.py` — downloads 13 upstream files at pinned commit `957d009`
- `tools/vendor_local.py` — copies the user's animation markdown into `data/local/`

Codebase idioms:

- Table loaders are module-level functions decorated `@functools.lru_cache(maxsize=1)`.
- `KeyError` messages name the inputs and the valid range.
- **Refuse rather than guess.** See `docs/superpowers/notes/error-conventions.md`.

### The manifest, as it exists

`data/SOURCES.json` holds a `sources` list. Two entries today:

```json
{"name": "nba2k27-builder-dataset", "url": "https://github.com/lightmatmul/nba2k27-builder-dataset",
 "commit": "957d009",
 "files": {"reference/attributes.json": {"local": "data/engine/reference__attributes.json",
                                          "sha256": "...", "bytes": 2562}, ...}}
{"name": "user-local-documents", "url": "local", "commit": "n/a",
 "files": {"local/animation_requirements.md": {"local": "data/local/animation_requirements.md",
                                                "sha256": "...", "bytes": 73653}}}
```

`.gitattributes` contains `data/** -text`, which stops git rewriting line endings and invalidating the hashes on Windows. **Anything written under `data/` must be written with `newline="\n"`** or the manifest itself gets CRLF-rewritten — this bit us once already in phase 2.

### Why refresh matters more than it looks

The upstream repo published **three corrections within a day of first release**, and they were retractions of claims rather than additions. It is also known to ship at least one defect this project has to work around: every badge token value is zero at heights 82-88 while the sibling `slots` field stays populated.

So the question a refresh must answer is not "is there new data" but **"did the rules change, or did somebody's capture break"**. The dataset ships its own answer key — 256 golden vectors in `overall/mixed_vectors.json` — and tables and vectors version together. That gives a three-way verdict:

| Staged tables vs staged vectors | Values changed | Verdict |
|---|---|---|
| Reproduce exactly | yes | Real change. Adopt, then show impact. |
| Reproduce exactly | no | Cosmetic. Adopt quietly. |
| Do **not** reproduce | — | Upstream capture is broken. Refuse to adopt. |

That third row is the safety property. A bad upstream commit is rejected before it can reach a build.

### Carried notes this phase should close

From the phase 1b review, tagged for the plan that touches the manifest:

1. **Pin the full 40-character commit SHA**, not the abbreviated `957d009`. `raw.githubusercontent.com` resolves abbreviations, but a trust boundary should record the full hash. This phase rewrites the manifest anyway.
2. **`sources.verify()` raises on the first hash mismatch** rather than collecting all of them. Worth fixing now that a refresh can produce several at once.
3. **A corrupted `data/SOURCES.json` surfaces a raw `json.JSONDecodeError`** rather than a `SourceError`. Every other failure in that module wraps consistently.

---

## File structure

| File | Responsibility |
|---|---|
| `buildlab/refresh.py` | Check, stage, diff, verdict, adopt |
| `buildlab/ratings.py` | User-authored animation quality scores |
| `buildlab/sources.py` | Full-SHA support, collect-all verify, wrapped decode errors (modify) |
| `buildlab/cli.py` | Add `refresh` and `rate` subcommands (modify) |
| `data/ratings.json` | The ratings file itself, created empty |
| `tests/test_refresh.py` | Staging, diffing, verdicts |
| `tests/test_ratings.py` | Schema, lookup, solver integration |
| `tests/test_sources.py` | Coverage for the three hardening items (modify) |
| `tests/test_cli.py` | Coverage for the two new subcommands (modify) |

`refresh.py` depends on `sources` and `tuning`. `ratings.py` depends on `sources` and `animations`. Neither depends on the other.

---

## Task 1: Harden `sources`

Close the three carried notes before anything else writes the manifest.

**Files:**
- Modify: `buildlab/sources.py`
- Modify: `tests/test_sources.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sources.py`, before the `if __name__` block:

```python
class TestHardening(unittest.TestCase):
    def test_verify_collects_every_mismatch(self):
        # verify_all returns a list rather than raising on the first problem,
        # so a refresh that breaks several files reports all of them.
        problems = sources.verify_all()
        self.assertEqual(problems, [])

    def test_verify_all_reports_a_tampered_file(self):
        entry = sources.load()["sources"][0]
        rel = next(iter(entry["files"]))
        path = sources.ROOT / entry["files"][rel]["local"]
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"\n")
            problems = sources.verify_all()
            self.assertEqual(len(problems), 1)
            self.assertIn(rel, problems[0])
        finally:
            path.write_bytes(original)
        self.assertEqual(sources.verify_all(), [])

    def test_a_corrupt_manifest_raises_source_error(self):
        with self.assertRaises(sources.SourceError):
            sources.parse_manifest("{ not json")

    def test_the_manifest_parse_error_points_at_the_vendoring_tool(self):
        with self.assertRaises(sources.SourceError) as caught:
            sources.parse_manifest("{ not json")
        self.assertIn("tools/vendor.py", str(caught.exception))

    def test_commit_is_recorded_in_full(self):
        # A trust boundary should pin the whole hash, not an abbreviation.
        commit = sources.load()["sources"][0]["commit"]
        self.assertEqual(len(commit), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in commit))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_sources -v`
Expected: FAIL with `AttributeError: module 'buildlab.sources' has no attribute 'verify_all'`

- [ ] **Step 3: Write the implementation**

In `buildlab/sources.py`, add `parse_manifest` and `verify_all`, and route `load` through the parser:

```python
def parse_manifest(text):
    """Parse manifest JSON, wrapping a decode failure as SourceError."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise SourceError(
            f"{MANIFEST} is not valid JSON ({error}); it is machine-generated, "
            "so re-run tools/vendor.py rather than editing it"
        ) from error
```

Change the body of `load()` to use it:

```python
@functools.lru_cache(maxsize=1)
def load():
    if not MANIFEST.exists():
        raise SourceError(f"missing manifest {MANIFEST}; run tools/vendor.py")
    return parse_manifest(MANIFEST.read_text(encoding="utf-8"))
```

Add `verify_all` next to `verify`:

```python
def verify_all():
    """Every file whose hash does not match, as a list of messages.

    Returns an empty list when everything matches. Unlike verify(), which stops
    at the first problem, this reports all of them — a data refresh can break
    several files at once and seeing one at a time wastes a cycle each.
    """
    problems = []
    for source in load()["sources"]:
        for rel, entry in source["files"].items():
            path = ROOT / entry["local"]
            if not path.exists():
                problems.append(f"{rel}: missing at {path}")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != entry["sha256"]:
                problems.append(
                    f"{rel}: hash mismatch, manifest {entry['sha256'][:12]}, "
                    f"on disk {digest[:12]}"
                )
    return problems
```

Leave `verify()` exactly as it is — existing tests depend on it raising.

- [ ] **Step 4: Update the pin to the full SHA**

`test_commit_is_recorded_in_full` will still fail because the manifest holds `957d009`. Get the full hash:

```bash
gh api repos/lightmatmul/nba2k27-builder-dataset/commits/957d009 --jq .sha
```

In `tools/vendor.py`, replace `COMMIT = "957d009"` with the full 40-character value. Then re-run it:

```bash
python tools/vendor.py
```

The file contents are identical, so every hash stays the same and only the `commit` field changes. **Confirm that** — `git diff data/SOURCES.json` should show one changed line plus nothing else. If hashes moved, the download differed and you must stop and report.

`tests/test_sources.py` has an existing `test_commit_is_pinned` asserting `"957d009"`. Update that one assertion to the full SHA. It is the only existing assertion this task may change.

- [ ] **Step 5: Run the tests**

Run: `python -m unittest tests.test_sources -v`
Expected: `OK`, 8 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 263 tests, OK.

- [ ] **Step 6: Commit**

```bash
git add buildlab/sources.py tools/vendor.py tests/test_sources.py data/SOURCES.json && git commit -m "refactor: pin the full commit SHA and collect every hash mismatch"
```

---

## Task 2: Refresh — check and stage

**Files:**
- Create: `buildlab/refresh.py`
- Create: `tests/test_refresh.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_refresh.py`:

```python
import json
import unittest

from buildlab import refresh, sources


class TestStagingPaths(unittest.TestCase):
    def test_staging_is_outside_the_live_data_tree(self):
        self.assertNotIn("engine", refresh.STAGING.parts)
        self.assertIn("staging", refresh.STAGING.parts)

    def test_snapshot_dir_is_named_for_a_commit(self):
        path = refresh.snapshot_dir("abc1234")
        self.assertIn("abc1234", str(path))
        self.assertIn("snapshots", str(path))


class TestSemanticDiff(unittest.TestCase):
    def test_identical_payloads_diff_to_nothing(self):
        rows = [{"badge": 1, "tier": "bronze", "cost": 3}]
        self.assertEqual(refresh.diff_rows(rows, rows, key=("badge", "tier")), [])

    def test_a_changed_value_is_reported_with_both_sides(self):
        before = [{"badge": 1, "tier": "bronze", "cost": 3}]
        after = [{"badge": 1, "tier": "bronze", "cost": 5}]
        changes = refresh.diff_rows(before, after, key=("badge", "tier"))
        self.assertEqual(len(changes), 1)
        self.assertIn("cost", changes[0]["fields"])
        self.assertEqual(changes[0]["fields"]["cost"], (3, 5))

    def test_an_added_row_is_reported(self):
        before = []
        after = [{"badge": 2, "tier": "gold", "cost": 1}]
        changes = refresh.diff_rows(before, after, key=("badge", "tier"))
        self.assertEqual(changes[0]["kind"], "added")

    def test_a_removed_row_is_reported(self):
        before = [{"badge": 2, "tier": "gold", "cost": 1}]
        after = []
        changes = refresh.diff_rows(before, after, key=("badge", "tier"))
        self.assertEqual(changes[0]["kind"], "removed")

    def test_diff_is_stable_regardless_of_row_order(self):
        before = [
            {"badge": 1, "tier": "bronze", "cost": 3},
            {"badge": 2, "tier": "gold", "cost": 1},
        ]
        after = list(reversed(before))
        self.assertEqual(refresh.diff_rows(before, after, key=("badge", "tier")), [])


class TestVerdict(unittest.TestCase):
    def test_current_data_reproduces_its_own_vectors(self):
        # The live tables must always pass their own answer key. If this fails,
        # the engine is broken, not the refresh.
        outcome = refresh.check_vectors(sources.rows_for("overall/mixed_vectors.json"))
        self.assertTrue(outcome["reproduces"])
        self.assertEqual(outcome["matched"], 256)

    def test_a_tampered_vector_is_caught(self):
        rows = [dict(r) for r in sources.rows_for("overall/mixed_vectors.json")]
        rows[0]["overall"] = rows[0]["overall"] + 5
        outcome = refresh.check_vectors(rows)
        self.assertFalse(outcome["reproduces"])
        self.assertEqual(outcome["matched"], 255)

    def test_verdict_names_the_three_outcomes(self):
        self.assertEqual(
            set(refresh.VERDICTS),
            {"real_change", "cosmetic", "upstream_broken"},
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_refresh -v`
Expected: FAIL with `ImportError: cannot import name 'refresh'`

- [ ] **Step 3: Write the implementation**

Create `buildlab/refresh.py`:

```python
"""Take new upstream data safely: check, stage, diff, judge, adopt.

Nothing here mutates live data until adopt() is called explicitly. The dataset
ships its own answer key, so a staged copy can be judged before it is trusted:
if the staged tables cannot reproduce the staged vectors, the capture is broken
and the refresh is refused.
"""

import hashlib
import json
import pathlib
import urllib.request

from buildlab import ovr, sources

STAGING = sources.ROOT / "data" / "staging"
SNAPSHOTS = sources.ROOT / "data" / "snapshots"

# The reference body every mixed vector was probed at: PG, 6'3", 198 lb, 78 in.
VECTOR_HEIGHT = 75

VERDICTS = ("real_change", "cosmetic", "upstream_broken")


def snapshot_dir(commit):
    return SNAPSHOTS / commit


def upstream_head(repo):
    """The current head SHA of a GitHub repository's default branch."""
    url = f"https://api.github.com/repos/{repo}/commits"
    with urllib.request.urlopen(url) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload[0]["sha"]


def pinned_commit():
    return sources.load()["sources"][0]["commit"]


def pinned_repo():
    url = sources.load()["sources"][0]["url"]
    return url.removeprefix("https://github.com/")


def check():
    """Compare the pin against upstream without downloading anything."""
    pinned = pinned_commit()
    head = upstream_head(pinned_repo())
    return {
        "pinned": pinned,
        "upstream": head,
        "behind": head != pinned,
    }


def stage(commit):
    """Download every manifested upstream file at a commit into staging."""
    STAGING.mkdir(parents=True, exist_ok=True)
    source = sources.load()["sources"][0]
    repo = pinned_repo()
    staged = {}
    for rel, entry in source["files"].items():
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{rel}"
        with urllib.request.urlopen(url) as response:
            payload = response.read()
        out = STAGING / pathlib.Path(entry["local"]).name
        out.write_bytes(payload)
        staged[rel] = {
            "path": out,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "changed": hashlib.sha256(payload).hexdigest() != entry["sha256"],
        }
    return staged


def staged_rows(staged, rel):
    payload = json.loads(staged[rel]["path"].read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


def diff_rows(before, after, key):
    """Semantic diff of two row lists, keyed by a tuple of field names.

    Returns a list of `{"key", "kind", "fields"}`. `kind` is added, removed or
    changed; `fields` maps each differing field to a (before, after) pair.
    Order-independent.
    """

    def index(rows):
        return {tuple(row[k] for k in key): row for row in rows}

    old, new = index(before), index(after)
    changes = []
    for identity in sorted(set(old) | set(new), key=repr):
        if identity not in new:
            changes.append({"key": identity, "kind": "removed", "fields": {}})
            continue
        if identity not in old:
            changes.append({"key": identity, "kind": "added", "fields": {}})
            continue
        fields = {
            field: (old[identity][field], new[identity][field])
            for field in new[identity]
            if old[identity].get(field) != new[identity][field]
        }
        if fields:
            changes.append({"key": identity, "kind": "changed", "fields": fields})
    return changes


def check_vectors(rows):
    """Whether the live engine reproduces a set of golden vectors.

    Used against STAGED vectors to decide whether a refresh is a real rules
    change or a broken capture.
    """
    matched = 0
    failures = []
    for row in rows:
        got = ovr.overall(VECTOR_HEIGHT, row["values"])
        if got == row["overall"]:
            matched += 1
        else:
            failures.append(
                {"sample": row.get("sample"), "expected": row["overall"], "got": got}
            )
    return {
        "reproduces": not failures,
        "matched": matched,
        "total": len(rows),
        "failures": failures[:5],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_refresh -v`
Expected: `OK`, 10 tests

Note `TestVerdict.test_current_data_reproduces_its_own_vectors` exercises the live engine against the live vectors and must pass — if it does not, something in the engine regressed and that is the finding, not the refresh.

- [ ] **Step 5: Commit**

```bash
git add buildlab/refresh.py tests/test_refresh.py && git commit -m "feat: stage and judge an upstream data refresh"
```

---

## Task 3: The `refresh` CLI command

**Files:**
- Modify: `buildlab/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`, before the `if __name__` block:

```python
class TestRefreshCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_refresh_requires_a_mode(self):
        code, out = self.run_cli(["refresh"])
        self.assertEqual(code, 2)
        self.assertIn("--check", out)

    def test_refresh_rejects_adopt_without_preview(self):
        code, out = self.run_cli(["refresh", "--adopt"])
        self.assertEqual(code, 2)
        self.assertIn("--preview", out)
```

Both tests avoid the network deliberately. The `--check` and `--preview` paths hit GitHub, so they are exercised by hand in Step 4 rather than in the suite — a test that needs the internet is a test that fails on a train.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL — `argparse` rejects `refresh`

- [ ] **Step 3: Write the implementation**

Add `refresh as refresh_mod` to the `cli.py` import block.

Add after `_critique`:

```python
def _refresh(args):
    if not (args.check or args.preview or args.adopt):
        print("error: pick a mode — --check, --preview or --adopt")
        return 2
    if args.adopt and not args.preview:
        print(
            "error: --adopt only runs together with --preview, so you see the "
            "diff and the verdict before anything changes"
        )
        return 2

    status = refresh_mod.check()
    print(f"PINNED     {status['pinned'][:12]}")
    print(f"UPSTREAM   {status['upstream'][:12]}")
    if not status["behind"]:
        print("UP TO DATE — nothing to do")
        return 0
    print("BEHIND     upstream has moved")
    if args.check:
        print()
        print("  Run again with --preview to fetch and compare without adopting.")
        return 0

    print()
    print("STAGING    downloading to data/staging, live data untouched")
    staged = refresh_mod.stage(status["upstream"])
    changed = [rel for rel, entry in staged.items() if entry["changed"]]
    print(f"CHANGED    {len(changed)} of {len(staged)} files")
    for rel in changed:
        print(f"  {rel}")
    print()

    vectors = refresh_mod.staged_rows(staged, "overall/mixed_vectors.json")
    outcome = refresh_mod.check_vectors(vectors)
    print(
        f"VECTORS    {outcome['matched']}/{outcome['total']} reproduce with the "
        "current engine"
    )
    if not outcome["reproduces"]:
        print()
        print("VERDICT    real_change or upstream_broken — cannot tell them apart")
        print(
            "  The staged tables do not reproduce the staged vectors under the "
            "current engine. Either the rules changed and the engine needs "
            "rederiving, or the upstream capture is broken. Not adopting."
        )
        for failure in outcome["failures"]:
            print(
                f"    sample {failure['sample']}: expected "
                f"{failure['expected']}, got {failure['got']}"
            )
        return 0

    print("VERDICT    cosmetic — the engine still reproduces every vector")
    if not args.adopt:
        print()
        print("  Run again with --preview --adopt to apply it.")
        return 0

    print()
    print("ADOPT      not implemented yet; staging is left in place for inspection")
    print(f"  {refresh_mod.STAGING}")
    return 0
```

Register in `main`, before `args = parser.parse_args(argv)`:

```python
    rf = sub.add_parser("refresh", help="check for and preview new upstream data")
    rf.add_argument("--check", action="store_true", help="compare pins only")
    rf.add_argument("--preview", action="store_true", help="fetch and diff")
    rf.add_argument("--adopt", action="store_true", help="apply, with --preview")
    rf.set_defaults(func=_refresh)
```

The adopt path deliberately stops short of writing. Adopting means rewriting the manifest and moving files under `data/`, and doing that correctly needs a snapshot and a rollback path. Leaving it explicit and unimplemented is honest; silently half-adopting would not be.

- [ ] **Step 4: Run the tests and try it live**

Run: `python -m unittest discover -s tests -v`
Expected: 265 tests, OK.

Then, with a network connection:

```bash
python -m buildlab.cli refresh --check
```

Upstream is at commit `957d009` with no newer commits as of writing, so expect `UP TO DATE`. Paste the output.

- [ ] **Step 5: Commit**

```bash
git add buildlab/cli.py tests/test_cli.py && git commit -m "feat: add the refresh subcommand"
```

---

## Task 4: The ratings layer

The animation *requirements* are known. The animation *quality* is not, and will not be until the game ships and the user tests it. This is the file that turns a catalogue into advice.

**Files:**
- Create: `buildlab/ratings.py`
- Create: `data/ratings.json`
- Create: `tests/test_ratings.py`

- [ ] **Step 1: Create the empty ratings file**

Write `data/ratings.json` with exactly this content, using `newline="\n"`:

```json
{
  "_meta": {
    "describes": "Hand-authored animation quality scores. Not derived from any data source.",
    "scale": "1 to 10, higher is better. Omit a field you have not judged.",
    "fields": {
      "speed": "how quickly the animation completes",
      "block_resistance": "how well it avoids getting blocked",
      "tier": "S, A, B, C or D overall",
      "notes": "free text"
    },
    "never_written_by": "tools/vendor.py, tools/vendor_local.py, buildlab/refresh.py"
  },
  "ratings": {}
}
```

This file is **yours**, not vendored. It must never appear in `data/SOURCES.json` and no tool may write it.

- [ ] **Step 2: Write the failing test**

Create `tests/test_ratings.py`:

```python
import unittest

from buildlab import ratings


class TestRatingsFile(unittest.TestCase):
    def test_loads_and_starts_empty(self):
        self.assertEqual(ratings.all_ratings(), {})

    def test_the_scale_is_documented(self):
        self.assertIn("1 to 10", ratings.meta()["scale"])

    def test_the_file_is_not_manifested(self):
        # Ratings are hand-authored, so they must not be hash-pinned like
        # vendored data — a hash would make editing them look like corruption.
        from buildlab import sources

        for source in sources.load()["sources"]:
            for rel in source["files"]:
                self.assertNotIn("ratings", rel)


class TestLookup(unittest.TestCase):
    def test_an_unrated_package_returns_none(self):
        self.assertIsNone(ratings.rating_for("Kyrie Irving", "Dribble Style"))

    def test_rating_for_rejects_an_unknown_package(self):
        with self.assertRaises(KeyError):
            ratings.rating_for("Not A Package", "Dribble Style")

    def test_key_round_trips(self):
        key = ratings.key_for("Kyrie Irving", "Dribble Style")
        self.assertIn("Kyrie Irving", key)
        self.assertIn("Dribble Style", key)


class TestValidation(unittest.TestCase):
    def test_a_well_formed_entry_validates(self):
        problems = ratings.validate(
            {"Dribble Style::Kyrie Irving": {"speed": 8, "tier": "S"}}
        )
        self.assertEqual(problems, [])

    def test_an_unknown_package_is_reported(self):
        problems = ratings.validate({"Dribble Style::Nobody": {"speed": 8}})
        self.assertEqual(len(problems), 1)
        self.assertIn("Nobody", problems[0])

    def test_a_score_outside_one_to_ten_is_reported(self):
        problems = ratings.validate(
            {"Dribble Style::Kyrie Irving": {"speed": 44}}
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("speed", problems[0])

    def test_an_unknown_tier_is_reported(self):
        problems = ratings.validate(
            {"Dribble Style::Kyrie Irving": {"tier": "Z"}}
        )
        self.assertEqual(len(problems), 1)

    def test_the_shipped_empty_file_validates(self):
        self.assertEqual(ratings.validate(ratings.all_ratings()), [])


class TestRanking(unittest.TestCase):
    def test_unrated_packages_rank_after_rated_ones(self):
        scored = ratings.rank(
            [
                {"name": "Kyrie Irving", "family": "Dribble Style"},
                {"name": "Pro", "family": "Dribble Style"},
            ],
            table={"Dribble Style::Pro": {"tier": "S"}},
        )
        self.assertEqual(scored[0]["name"], "Pro")

    def test_ranking_is_stable_when_nothing_is_rated(self):
        rows = [
            {"name": "Kyrie Irving", "family": "Dribble Style"},
            {"name": "Pro", "family": "Dribble Style"},
        ]
        self.assertEqual([r["name"] for r in ratings.rank(rows, table={})],
                         [r["name"] for r in rows])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Write the implementation**

Create `buildlab/ratings.py`:

```python
"""Hand-authored animation quality scores.

The animation requirements are known from data. The quality is not, and will
not be until the game ships and somebody plays it. This module holds that
judgement, keyed by family and name.

Deliberately NOT manifested: it is authored, not vendored, so hash-pinning it
would make every edit look like corruption. Nothing in tools/ writes it.
"""

import functools
import json

from buildlab import animations, sources

PATH = sources.ROOT / "data" / "ratings.json"

SCORE_FIELDS = ("speed", "block_resistance")
TIERS = ("S", "A", "B", "C", "D")
TIER_ORDER = {tier: index for index, tier in enumerate(TIERS)}
SEPARATOR = "::"


@functools.lru_cache(maxsize=1)
def _document():
    if not PATH.exists():
        raise sources.SourceError(
            f"missing {PATH}; it holds your own animation ratings and is not "
            "vendored, so create it with an empty ratings object"
        )
    # Deliberately not sources.parse_manifest: that error tells you to re-run
    # tools/vendor.py, which is exactly the wrong advice for a file you wrote
    # by hand.
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise sources.SourceError(
            f"{PATH} is not valid JSON ({error}); it is hand-edited, so fix the "
            "syntax rather than regenerating it — no tool writes this file"
        ) from error


def meta():
    return _document()["_meta"]


def all_ratings():
    return _document()["ratings"]


def key_for(name, family):
    """The lookup key for a package. Family first so keys sort by family."""
    return f"{family}{SEPARATOR}{name}"


def rating_for(name, family, table=None):
    """This package's rating, or None if it has not been judged yet.

    Raises if the package does not exist, so a typo in the ratings file is a
    loud error rather than a silently unrated animation.
    """
    animations.by_name(name, family)
    source = all_ratings() if table is None else table
    return source.get(key_for(name, family))


def validate(table):
    """Every problem with a ratings table, as a list of messages."""
    problems = []
    for key, entry in sorted(table.items()):
        family, separator, name = key.partition(SEPARATOR)
        if not separator:
            problems.append(f"{key!r}: expected 'Family{SEPARATOR}Name'")
            continue
        try:
            animations.by_name(name, family)
        except KeyError:
            problems.append(f"{key!r}: no such package")
            continue
        for field in SCORE_FIELDS:
            if field not in entry:
                continue
            value = entry[field]
            if not isinstance(value, int) or not 1 <= value <= 10:
                problems.append(f"{key!r}: {field} must be an integer 1-10, got {value!r}")
        if "tier" in entry and entry["tier"] not in TIERS:
            problems.append(
                f"{key!r}: tier must be one of {TIERS}, got {entry['tier']!r}"
            )
    return problems


def _score(entry):
    """Sort key: rated before unrated, better tier first, then mean score."""
    if entry is None:
        return (1, len(TIERS), 0)
    tier = TIER_ORDER.get(entry.get("tier"), len(TIERS))
    scores = [entry[f] for f in SCORE_FIELDS if f in entry]
    mean = sum(scores) / len(scores) if scores else 0
    return (0, tier, -mean)


def rank(rows, table=None):
    """Order packages best-first, leaving unrated ones in their original order."""
    source = all_ratings() if table is None else table
    return sorted(
        rows,
        key=lambda row: _score(source.get(key_for(row["name"], row["family"]))),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ratings -v`
Expected: `OK`, 13 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 278 tests, OK.

- [ ] **Step 5: Commit**

```bash
git add buildlab/ratings.py data/ratings.json tests/test_ratings.py && git commit -m "feat: hand-authored animation quality ratings"
```

---

## Task 5: The `rate` CLI command

**Files:**
- Modify: `buildlab/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`, before the `if __name__` block:

```python
class TestRateCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_rate_validates_the_file(self):
        code, out = self.run_cli(["rate", "--validate"])
        self.assertEqual(code, 0)
        self.assertIn("VALID", out.upper())

    def test_rate_lists_the_testing_shortlist(self):
        code, out = self.run_cli(["rate", "--shortlist"])
        self.assertEqual(code, 0)
        self.assertIn("Dribble Style", out)

    def test_rate_requires_a_mode(self):
        code, out = self.run_cli(["rate"])
        self.assertEqual(code, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL — `argparse` rejects `rate`

- [ ] **Step 3: Write the implementation**

Add `ratings as ratings_mod` to the `cli.py` import block.

Add after `_refresh`:

```python
# The families worth testing first at launch, in priority order. Animation
# quality cannot be known before the game ships, so this is where to start.
SHORTLIST = (
    "Dribble Style",
    "Layup Style",
    "Two Foot Moving Dunks - Contact Dunks",
    "One Foot Moving Dunks - Contact Dunks",
    "Signature Dunks - Players",
    "Signature Size-Up",
    "Behind the Back",
    "Crossover",
    "Dribble Pull-Up",
    "Post Fade",
)


def _rate(args):
    if not (args.validate or args.shortlist):
        print("error: pick a mode — --validate or --shortlist")
        return 2

    if args.validate:
        table = ratings_mod.all_ratings()
        problems = ratings_mod.validate(table)
        if problems:
            print(f"INVALID    {len(problems)} problems in data/ratings.json")
            for problem in problems:
                print(f"  {problem}")
            return 0
        print(f"VALID      {len(table)} packages rated")
        if not table:
            print()
            print(
                "  Nothing rated yet. Animation quality cannot be known before "
                "the game ships — run with --shortlist for where to start."
            )
        return 0

    print("TESTING SHORTLIST — families worth judging first at launch")
    print()
    rated = ratings_mod.all_ratings()
    for family in SHORTLIST:
        rows = [r for r in animations_mod.packages() if r["family"] == family]
        done = sum(
            1
            for r in rows
            if ratings_mod.key_for(r["name"], r["family"]) in rated
        )
        print(f"  {family:<40} {done}/{len(rows)} rated")
    print()
    print("  Add entries to data/ratings.json keyed 'Family::Name', for example:")
    print('    "Dribble Style::Kyrie Irving": {"speed": 9, "tier": "S"}')
    return 0
```

Register in `main`, before `args = parser.parse_args(argv)`:

```python
    rt = sub.add_parser("rate", help="check and plan your animation ratings")
    rt.add_argument("--validate", action="store_true", help="check ratings.json")
    rt.add_argument("--shortlist", action="store_true", help="what to test first")
    rt.set_defaults(func=_rate)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli -v`
Expected: `OK`, 32 tests

Then the full suite: `python -m unittest discover -s tests -v`
Expected: 281 tests, OK.

- [ ] **Step 5: Run it for real**

```bash
python -m buildlab.cli rate --shortlist
```

```bash
python -m buildlab.cli rate --validate
```

Paste both outputs. If a shortlist family reports 0 rows, the family name is wrong — verify against `animations.families()` and report which you corrected.

- [ ] **Step 6: Commit**

```bash
git add buildlab/cli.py tests/test_cli.py && git commit -m "feat: add the rate subcommand"
```

---

## Definition of done

- `python -m unittest discover -s tests` passes with no failures and no skips.
- `data/SOURCES.json` pins a full 40-character commit SHA.
- `sources.verify_all()` returns a list and reports every mismatch at once.
- `python -m buildlab.cli refresh --check` compares pins without downloading.
- `python -m buildlab.cli rate --shortlist` lists the ten families with real row counts.
- `data/ratings.json` exists, validates, and appears nowhere in `data/SOURCES.json`.
- No third-party imports anywhere in `buildlab/`, `tools/` or `tests/`.

## Explicitly not in this plan

The web UI — that is plan 5.

Also deliberately incomplete: **adopting a refresh does not write anything yet.** It stages, diffs and judges, then stops and tells you where the staging directory is. Adoption means rewriting the manifest, moving files under `data/`, snapshotting the old ones and providing a rollback — that is a plan of its own, and a half-implemented adopt that leaves the data tree in a mixed state would be worse than none. The refusal is explicit in the output rather than silent.
