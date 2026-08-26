import unittest

from buildlab import critique


class TestCritique(unittest.TestCase):
    def setUp(self):
        self.values = [70] * 21
        self.values[6] = 90  # three_point
        self.values[9] = 88  # ball_handle: 87 is an unlock, 88 wastes one

    def test_report_has_the_expected_sections(self):
        report = critique.critique(self.values, height_inches=76)
        for key in ("overall", "archetype", "badges", "waste", "unspecified"):
            self.assertIn(key, report)

    def test_overall_matches_the_engine(self):
        from buildlab import ovr

        report = critique.critique(self.values, height_inches=76)
        self.assertEqual(report["overall"], ovr.overall(76, self.values))

    def test_waste_finds_dead_points(self):
        report = critique.critique(self.values, height_inches=76)
        wasted = {w["attribute"]: w for w in report["waste"]}
        self.assertIn("ball_handle", wasted)
        self.assertGreater(wasted["ball_handle"]["wasted"], 0)

    def test_waste_reports_the_next_unlock(self):
        report = critique.critique(self.values, height_inches=76)
        for entry in report["waste"]:
            with self.subTest(attribute=entry["attribute"]):
                self.assertIn("next_unlock_at", entry)

    def test_a_value_above_the_ceiling_is_flagged(self):
        values = [70] * 21
        values[3] = 95  # standing_dunk, ceiling is 65 at 6'4"
        report = critique.critique(values, height_inches=76)
        self.assertTrue(report["illegal"])
        self.assertIn("standing_dunk", str(report["illegal"]))

    def test_a_legal_build_has_no_illegal_entries(self):
        report = critique.critique([30] * 21, height_inches=76)
        self.assertEqual(report["illegal"], [])

    def test_rejects_a_wrong_length_vector(self):
        with self.assertRaises(ValueError):
            critique.critique([70] * 20, height_inches=76)


class TestClaims(unittest.TestCase):
    def test_a_true_badge_claim_is_confirmed(self):
        values = [99] * 21
        checked = critique.check_claims(
            values, height_inches=76, claims=[("ankle_assassin", "hall_of_fame")]
        )
        self.assertTrue(checked[0]["holds"])

    def test_a_false_badge_claim_is_refuted_with_the_real_tier(self):
        values = [70] * 21
        checked = critique.check_claims(
            values, height_inches=76, claims=[("ankle_assassin", "hall_of_fame")]
        )
        self.assertFalse(checked[0]["holds"])
        self.assertIn("actual", checked[0])

    def test_an_unreachable_claim_is_refuted(self):
        values = [99] * 21
        checked = critique.check_claims(
            values, height_inches=88, claims=[("mini_marksman", "bronze")]
        )
        self.assertFalse(checked[0]["holds"])


if __name__ == "__main__":
    unittest.main()
