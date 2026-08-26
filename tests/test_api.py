import json
import unittest

from buildlab import api


class TestMeta(unittest.TestCase):
    def test_meta_lists_the_attributes_in_order(self):
        payload = api.meta()
        self.assertEqual(len(payload["attributes"]), 21)
        self.assertEqual(payload["attributes"][0], "close_shot")
        self.assertEqual(payload["attributes"][20], "vertical")

    def test_meta_gives_the_legal_height_range(self):
        payload = api.meta()
        self.assertEqual(payload["min_height"], 69)
        self.assertEqual(payload["max_height"], 88)

    def test_meta_reports_the_pinned_commit(self):
        payload = api.meta()
        self.assertEqual(len(payload["commit"]), 40)

    def test_meta_gives_the_attribute_floor(self):
        self.assertEqual(api.meta()["floor"], 25)

    def test_meta_is_json_serialisable(self):
        json.dumps(api.meta())


class TestEvaluate(unittest.TestCase):
    def setUp(self):
        self.values = [70] * 21

    def test_evaluate_returns_overall_and_archetype(self):
        payload = api.evaluate(self.values, 76)
        self.assertIn("overall", payload)
        self.assertIn("archetype", payload)

    def test_evaluate_matches_the_engine(self):
        from buildlab import ovr

        payload = api.evaluate(self.values, 76)
        self.assertEqual(payload["overall"], ovr.overall(76, self.values))

    def test_evaluate_counts_badges_and_animations(self):
        payload = api.evaluate(self.values, 76)
        self.assertGreaterEqual(payload["badge_count"], 0)
        self.assertGreater(payload["animation_count"], 0)

    def test_evaluate_reports_ceilings(self):
        payload = api.evaluate(self.values, 76)
        self.assertEqual(len(payload["ceilings"]), 21)

    def test_evaluate_flags_values_above_the_ceiling(self):
        values = [70] * 21
        values[3] = 95
        payload = api.evaluate(values, 76)
        self.assertTrue(payload["illegal"])

    def test_evaluate_reports_tokens_when_available(self):
        payload = api.evaluate(self.values, 76)
        self.assertTrue(payload["tokens"]["available"])
        self.assertIn("total", payload["tokens"])

    def test_evaluate_degrades_where_token_data_is_missing(self):
        # 84 inches is inside the range where every token value is zero in the
        # shipped data. It must report unavailable, never zero.
        payload = api.evaluate(self.values, 84)
        self.assertFalse(payload["tokens"]["available"])
        self.assertIn("reason", payload["tokens"])

    def test_evaluate_rejects_a_wrong_length_vector(self):
        with self.assertRaises(ValueError):
            api.evaluate([70] * 20, 76)

    def test_evaluate_rejects_an_illegal_height(self):
        with self.assertRaises(ValueError):
            api.evaluate(self.values, 60)

    def test_evaluate_is_json_serialisable(self):
        json.dumps(api.evaluate(self.values, 76))


class TestLadder(unittest.TestCase):
    def test_ladder_returns_steps(self):
        payload = api.ladder("ball_handle", 76)
        self.assertGreater(len(payload["steps"]), 0)
        self.assertIn("ceiling", payload)

    def test_ladder_steps_are_plain_lists(self):
        payload = api.ladder("ball_handle", 76)
        for step in payload["steps"]:
            self.assertIsInstance(step["badges"], list)
            self.assertIsInstance(step["animations"], list)

    def test_ladder_rejects_an_unknown_attribute(self):
        with self.assertRaises(KeyError):
            api.ladder("nonsense", 76)

    def test_ladder_is_json_serialisable(self):
        json.dumps(api.ladder("ball_handle", 76))


if __name__ == "__main__":
    unittest.main()
