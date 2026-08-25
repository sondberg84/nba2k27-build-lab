import json
import math
import unittest

from buildlab import archetypes, ovr, reference, sources, tables

REFERENCE_HEIGHT = 75
BUCKET = 11
SWEEP_RATINGS = (25, 40, 60, 75, 80, 83, 90, 95, 99)


def uncapped(values, player_type):
    """Post-lerp overall before the display cap, for one archetype."""
    return ovr._raw(BUCKET, player_type, values)


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


class TestGeneralisesAcrossHeights(unittest.TestCase):
    """Every golden row is at bucket 11. These tests cover buckets 5-24.

    The uniform-vector identity is algebraic, not empirical: sum(w*s*r)/sum(w*s)
    reduces to r for any weight vector whatsoever, so it holds at every height
    without needing golden data there. That makes it the one property able to
    catch an indexing or bucket-mismatch bug that bucket-11-only goldens
    structurally cannot.
    """

    def test_uniform_vector_gives_back_the_rating_at_every_bucket(self):
        # Asserted to within one ULP of the rating, which is the strongest
        # bound IEEE-754 admits here -- see test_the_one_ulp_bound_is_rounding
        # below for why exact equality is unreachable for ANY implementation.
        for bucket in tables.weight_buckets():
            for rating in SWEEP_RATINGS:
                for player_type in tables.player_types():
                    score = archetypes.scaled_score(bucket, player_type, [rating] * 21)
                    self.assertLessEqual(
                        abs(score - rating),
                        math.ulp(float(rating)),
                        msg=f"bucket {bucket}, rating {rating}, type {player_type}",
                    )

    def test_the_one_ulp_bound_is_rounding_not_a_formula_defect(self):
        # Each product fl(fl(w*s)*r) is rounded independently, so the summed
        # numerator is not bit-identical to r times the summed denominator even
        # under exact (fsum) accumulation. Pinning that here documents that the
        # residual is representation, not modelling: if a future change makes
        # this deviation exceed one ULP, the formula really has drifted.
        worst = 0.0
        for bucket in tables.weight_buckets():
            for rating in SWEEP_RATINGS:
                for player_type in tables.player_types():
                    weights = tables.weights(bucket, player_type)
                    scales = [
                        tables.scale_for(attr, rating)
                        for attr in reference.tuning_order()
                    ]
                    exact = math.fsum(
                        w * s * rating for w, s in zip(weights, scales)
                    ) / math.fsum(w * s for w, s in zip(weights, scales))
                    worst = max(worst, abs(exact - rating) / math.ulp(float(rating)))
        self.assertLessEqual(worst, 1.0)

    def test_public_api_is_sane_at_every_bucket(self):
        heights = tables.height_buckets()
        for bucket in tables.weight_buckets():
            height = heights[bucket]
            for rating in SWEEP_RATINGS:
                values = [rating] * 21
                where = f"height {height} (bucket {bucket}), rating {rating}"

                detail = ovr.detailed(height, values)
                self.assertIsInstance(detail, float, msg=where)
                self.assertGreaterEqual(detail, 25.0, msg=where)
                self.assertLessEqual(detail, 99.0, msg=where)

                displayed = ovr.overall(height, values)
                self.assertIsInstance(displayed, int, msg=where)
                self.assertGreaterEqual(displayed, 25, msg=where)
                self.assertLessEqual(displayed, 99, msg=where)
                self.assertEqual(displayed, math.floor(detail), msg=where)

                winner = ovr.archetype(height, values)
                self.assertIn(winner, tables.player_types(), msg=where)

    def test_overall_is_monotonic_in_the_uniform_rating(self):
        # A bucket-mismatch bug would most likely show up as a non-monotonic
        # or flat curve at some height.
        heights = tables.height_buckets()
        for bucket in tables.weight_buckets():
            height = heights[bucket]
            series = [ovr.detailed(height, [r] * 21) for r in SWEEP_RATINGS]
            for lower, higher in zip(series, series[1:]):
                self.assertLessEqual(lower, higher, msg=f"bucket {bucket}")


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
