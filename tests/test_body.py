import json
import unittest

from buildlab import body, reference, sources

# The one body bodies/attribute_caps_sample.json was probed at.
REFERENCE = {"height": 75, "weight": 198, "wingspan": 78}


def _pg_body(height):
    """A legal PG body row at this height, for building ceilings() inputs."""
    for record in reference.legal_bodies():
        if record["position"] == "PG":
            for row in record["bodies"]:
                if row["height_inches"] == height:
                    return row
    raise AssertionError(f"no PG body at height {height}")


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

    def test_ceilings_rejects_a_height_with_no_engine_data(self):
        with self.assertRaises(KeyError):
            body.ceilings(height=64, weight=180, wingspan=66)

    def test_ceilings_works_for_a_legal_five_nine_body(self):
        # 69 inches (5'9") is a legal PG height, but HeightMultiplier omits
        # StandingDunk for it. ceilings() must not raise and must still
        # return all 21 attributes.
        row = _pg_body(69)
        got = body.ceilings(
            height=69,
            weight=row["default_weight_lb"],
            wingspan=row["default_wingspan_inches"],
        )
        self.assertEqual(len(got), 21)

    def test_standing_dunk_floors_at_the_height_multiplier_gap(self):
        # HeightMultiplier has no StandingDunk entry at buckets 5-8
        # (69-72 in) - the same four buckets HeightBasedAttributeWeight
        # omits it at. Missing height multiplier means the attribute is not
        # usable at that height, so its ceiling floors at 25 regardless of
        # weight or wingspan.
        for height in (69, 70, 71, 72):
            with self.subTest(height=height):
                row = _pg_body(height)
                got = body.ceilings(
                    height=height,
                    weight=row["default_weight_lb"],
                    wingspan=row["default_wingspan_inches"],
                )
                self.assertEqual(got["standing_dunk"], 25)

    def test_standing_dunk_recovers_past_the_gap(self):
        # 73 inches is the first height above the gap; HeightMultiplier
        # covers StandingDunk there, so its ceiling should clear the floor.
        row = _pg_body(73)
        got = body.ceilings(
            height=73,
            weight=row["default_weight_lb"],
            wingspan=row["default_wingspan_inches"],
        )
        self.assertGreater(got["standing_dunk"], 25)

    def test_ceilings_are_valid_for_every_legal_body(self):
        # The sweep that would have caught the height-69 crash: every legal
        # body, at the corners of its legal weight/wingspan range, must
        # produce all 21 attributes within the formula's own clamp bounds.
        checked = 0
        for record in reference.legal_bodies():
            position = record["position"]
            for row in record["bodies"]:
                height = row["height_inches"]
                weight_lo, weight_hi = row["weight_lb"]
                wingspan_lo, wingspan_hi = row["wingspan_inches"]
                for weight in (weight_lo, weight_hi):
                    for wingspan in (wingspan_lo, wingspan_hi):
                        with self.subTest(
                            position=position,
                            height=height,
                            weight=weight,
                            wingspan=wingspan,
                        ):
                            got = body.ceilings(
                                height=height, weight=weight, wingspan=wingspan
                            )
                            self.assertEqual(len(got), 21)
                            for name, cap in got.items():
                                self.assertGreaterEqual(cap, 25, name)
                                self.assertLessEqual(cap, 99, name)
                checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
