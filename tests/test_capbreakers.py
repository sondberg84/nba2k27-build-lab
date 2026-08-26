import unittest

from buildlab import body, capbreakers, reference


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
        # Only 13280 ship. The gap is structural, not corruption.
        self.assertEqual(2 * 21 * 75 * 5 - len(capbreakers.gains()), 2470)

    def test_coverage_stops_at_the_reference_body_ceiling(self):
        # THE key property. For every attribute, the highest rating with
        # cap-breaker data equals that attribute's ceiling on the dataset's
        # reference body. Verified 21/21. Pinned here so a future data refresh
        # probed at a different body fails loudly.
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
        # near the ceiling rather than falling off it.
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
