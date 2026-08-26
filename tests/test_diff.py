import unittest

from buildlab import diff, reference


def vec(**overrides):
    names = reference.attribute_names()
    values = [70] * 21
    for name, value in overrides.items():
        values[names.index(name)] = value
    return values


class TestCompare(unittest.TestCase):
    def test_identical_builds_have_nothing_to_do(self):
        report = diff.compare(vec(), vec(), height_inches=76)
        self.assertEqual(report["short"], [])
        self.assertEqual(report["surplus"], [])
        self.assertEqual(report["points_remaining"], 0)

    def test_a_shortfall_is_reported_with_the_gap(self):
        report = diff.compare(vec(three_point=80), vec(three_point=90), 76)
        short = {s["attribute"]: s for s in report["short"]}
        self.assertIn("three_point", short)
        self.assertEqual(short["three_point"]["gap"], 10)
        self.assertEqual(short["three_point"]["current"], 80)
        self.assertEqual(short["three_point"]["target"], 90)

    def test_surplus_is_reported_separately(self):
        report = diff.compare(vec(three_point=95), vec(three_point=90), 76)
        self.assertEqual(report["short"], [])
        surplus = {s["attribute"]: s for s in report["surplus"]}
        self.assertEqual(surplus["three_point"]["over"], 5)

    def test_points_remaining_counts_only_shortfalls(self):
        report = diff.compare(
            vec(three_point=80, steal=95), vec(three_point=90, steal=90), 76
        )
        self.assertEqual(report["points_remaining"], 10)

    def test_short_is_ordered_by_largest_gap(self):
        report = diff.compare(
            vec(three_point=80, steal=60), vec(three_point=90, steal=90), 76
        )
        self.assertEqual(report["short"][0]["attribute"], "steal")

    def test_badges_the_target_has_and_the_current_does_not(self):
        report = diff.compare(vec(), [99] * 21, 76)
        self.assertGreater(len(report["badges_missing"]), 0)
        for entry in report["badges_missing"]:
            self.assertIn("tier", entry)
            self.assertIn("badge", entry)

    def test_a_value_above_the_ceiling_is_flagged(self):
        report = diff.compare(vec(standing_dunk=95), vec(), 76)
        self.assertTrue(report["illegal"])
        self.assertIn("standing_dunk", str(report["illegal"]))

    def test_an_unreachable_target_is_flagged(self):
        report = diff.compare(vec(), vec(standing_dunk=95), 76)
        self.assertTrue(report["target_illegal"])

    def test_both_vectors_must_be_21_long(self):
        with self.assertRaises(ValueError):
            diff.compare([70] * 20, vec(), 76)
        with self.assertRaises(ValueError):
            diff.compare(vec(), [70] * 20, 76)

    def test_counts_are_reported_for_both_sides(self):
        report = diff.compare(vec(), [99] * 21, 76)
        self.assertLess(report["badges_current"], report["badges_target"])
        self.assertLessEqual(report["animations_current"], report["animations_target"])


if __name__ == "__main__":
    unittest.main()
