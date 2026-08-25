import json
import math
import unittest

from buildlab import archetypes, ovr, sources, tables

REFERENCE_HEIGHT = 75
BUCKET = 11


def uncapped(values, player_type):
    """Post-lerp overall before the display cap, for one archetype."""
    return tables.lerp(BUCKET, archetypes.scaled_score(BUCKET, player_type, values))


def mixed_rows():
    payload = json.loads(
        sources.path_for("overall/mixed_vectors.json").read_text(encoding="utf-8")
    )
    return payload["data"]


def uniform_rows():
    payload = json.loads(
        sources.path_for("overall/uniform_ratings.json").read_text(encoding="utf-8")
    )
    return payload["data"]


class TestSelection(unittest.TestCase):
    def test_select_matches_every_golden_archetype(self):
        rows = mixed_rows()
        self.assertEqual(len(rows), 256)
        misses = [
            row["sample"]
            for row in rows
            if archetypes.select(BUCKET, row["values"]) != row["player_type"]
        ]
        self.assertEqual(misses, [])

    def test_select_also_matches_best_player_type(self):
        # player_type and best_player_type agree on all 256 rows, so one rule
        # covers both native routines.
        for row in mixed_rows():
            self.assertEqual(
                archetypes.select(BUCKET, row["values"]), row["best_player_type"]
            )

    def test_baseline_is_still_the_weaker_rule(self):
        # Regression guard: select_baseline must stay a plain weighted argmax.
        rows = mixed_rows()
        hits = sum(
            1
            for row in rows
            if archetypes.select_baseline(BUCKET, row["values"]) == row["player_type"]
        )
        self.assertEqual(hits, 207)

    def test_uniform_vector_ties_every_archetype(self):
        # With all attributes equal the renormalised average is that value for
        # every archetype. This is why the uniform goldens report an
        # arbitrary-looking winner, and it is the evidence for renormalising by
        # sum(w*s) rather than by 100.
        for rating in (25, 50, 83, 99):
            scores = {
                archetypes.scaled_score(BUCKET, pt, [rating] * 21) for pt in range(15)
            }
            for score in scores:
                self.assertAlmostEqual(score, rating, places=9)


class TestOverall(unittest.TestCase):
    def test_detailed_matches_every_mixed_vector(self):
        for row in mixed_rows():
            self.assertAlmostEqual(
                ovr.detailed(REFERENCE_HEIGHT, row["values"]),
                row["detailed"],
                delta=1e-4,
                msg=f"sample {row['sample']}",
            )

    def test_uncapped_matches_every_mixed_vector(self):
        # The pre-clamp curve on its own, so a regression in the display cap
        # cannot be mistaken for a regression in the formula.
        for row in mixed_rows():
            self.assertAlmostEqual(
                uncapped(row["values"], row["uncapped_player_type"]),
                row["uncapped"],
                delta=1e-4,
                msg=f"sample {row['sample']}",
            )

    def test_overall_matches_every_mixed_vector(self):
        for row in mixed_rows():
            self.assertEqual(
                ovr.overall(REFERENCE_HEIGHT, row["values"]),
                row["overall"],
                msg=f"sample {row['sample']}",
            )

    def test_archetype_matches_every_mixed_vector(self):
        for row in mixed_rows():
            self.assertEqual(
                ovr.archetype(REFERENCE_HEIGHT, row["values"]), row["player_type"]
            )

    def test_uniform_ratings_detailed_and_overall(self):
        rows = uniform_rows()
        self.assertEqual(len(rows), 75)
        for row in rows:
            values = [row["rating"]] * 21
            self.assertAlmostEqual(
                ovr.detailed(REFERENCE_HEIGHT, values),
                row["detailed"],
                delta=1e-4,
                msg=f"rating {row['rating']}",
            )
            self.assertEqual(
                ovr.overall(REFERENCE_HEIGHT, values),
                row["overall"],
                msg=f"rating {row['rating']}",
            )

    def test_overall_is_floor_of_detailed(self):
        for row in mixed_rows():
            self.assertEqual(math.floor(row["detailed"]), row["overall"])

    def test_display_cap_holds_a_sub_maximal_build_at_98(self):
        # Sample 25 is the one mixed vector the cap bites on: uncapped 99.0955,
        # displayed 98.
        row = next(r for r in mixed_rows() if r["sample"] == 25)
        self.assertGreater(uncapped(row["values"], row["player_type"]), 99.0)
        self.assertEqual(ovr.overall(REFERENCE_HEIGHT, row["values"]), 98)

    def test_a_fully_maxed_vector_reaches_99(self):
        self.assertEqual(ovr.overall(REFERENCE_HEIGHT, [99] * 21), 99)

    def test_height_is_taken_in_inches(self):
        # The public API converts internally; callers never see bucket indices.
        row = mixed_rows()[0]
        self.assertEqual(
            ovr.archetype(REFERENCE_HEIGHT, row["values"]),
            archetypes.select(BUCKET, row["values"]),
        )
        with self.assertRaises(KeyError):
            ovr.overall(11, row["values"])


if __name__ == "__main__":
    unittest.main()
