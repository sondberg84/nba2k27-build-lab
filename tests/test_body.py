import json
import unittest

from buildlab import body, sources

# The one body bodies/attribute_caps_sample.json was probed at.
REFERENCE = {"height": 75, "weight": 198, "wingspan": 78}


class TestBody(unittest.TestCase):
    def test_reference_body_is_legal(self):
        self.assertTrue(body.is_legal("PG", **REFERENCE))

    def test_height_outside_position_range_is_illegal(self):
        self.assertFalse(body.is_legal("PG", height=84, weight=250, wingspan=88))

    def test_wingspan_is_height_to_height_plus_six(self):
        self.assertTrue(body.is_legal("PG", height=75, weight=198, wingspan=81))
        self.assertFalse(body.is_legal("PG", height=75, weight=198, wingspan=82))

    def test_weight_outside_the_row_bounds_is_illegal(self):
        self.assertFalse(body.is_legal("PG", height=75, weight=120, wingspan=78))

    def test_ceilings_match_the_measured_sample(self):
        payload = json.loads(
            sources.path_for("bodies/attribute_caps_sample.json").read_text(
                encoding="utf-8"
            )
        )
        rows = payload["data"]
        self.assertEqual(len(rows), 21)
        got = body.ceilings(**REFERENCE)
        for row in rows:
            with self.subTest(attribute=row["name"]):
                self.assertEqual(got[row["name"]], row["cap"])


if __name__ == "__main__":
    unittest.main()
