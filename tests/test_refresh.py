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
