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
