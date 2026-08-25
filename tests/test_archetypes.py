import json
import unittest

from buildlab import archetypes, sources, tables


def golden_rows():
    payload = json.loads(
        sources.path_for("overall/mixed_vectors.json").read_text(encoding="utf-8")
    )
    return payload["data"]


class TestArchetypes(unittest.TestCase):
    def test_twelve_named_archetypes(self):
        # DataPerArchetype names 12 archetypes: 504 MinMax rows = 12 x 21 x 2.
        self.assertEqual(len(archetypes.names()), 12)

    def test_minimums_cover_every_named_archetype(self):
        mins = archetypes.minimums()
        self.assertEqual(len(mins), 12)
        for vector in mins.values():
            self.assertEqual(len(vector), 21)

    def test_weight_slots_outnumber_named_archetypes(self):
        # 15 PLAYERTYPE weight vectors but only 12 named archetypes, and no key
        # family other than HeightBasedAttributeWeight mentions PLAYERTYPE, so
        # three weight slots have no reachable minimums table. Pinned here so a
        # future data refresh that closes the gap fails loudly instead of
        # quietly changing what Task 8 is allowed to assume.
        self.assertEqual(len(tables.player_types()), 15)
        self.assertEqual(len(archetypes.names()), 12)

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
