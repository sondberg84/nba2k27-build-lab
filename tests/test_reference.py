import unittest

from buildlab import reference


class TestReference(unittest.TestCase):
    def test_twenty_one_attributes_in_index_order(self):
        attrs = reference.attributes()
        self.assertEqual(len(attrs), 21)
        self.assertEqual([a["index"] for a in attrs], list(range(21)))

    def test_first_and_last_attribute_names(self):
        names = reference.attribute_names()
        self.assertEqual(names[0], "close_shot")
        self.assertEqual(names[20], "vertical")

    def test_ball_handle_maps_to_ball_control(self):
        self.assertEqual(reference.TUNING_NAME["ball_handle"], "BallControl")

    def test_mapping_covers_every_attribute(self):
        for name in reference.attribute_names():
            self.assertIn(name, reference.TUNING_NAME)

    def test_tuning_order_matches_attribute_order(self):
        order = reference.tuning_order()
        self.assertEqual(len(order), 21)
        self.assertEqual(order[0], "ShotClose")
        self.assertEqual(order[9], "BallControl")

    def test_five_positions_with_expected_height_ranges(self):
        bodies = reference.legal_bodies()
        ranges = {b["position"]: tuple(b["height_inches"]) for b in bodies}
        self.assertEqual(ranges["PG"], (69, 79))
        self.assertEqual(ranges["SG"], (72, 80))
        self.assertEqual(ranges["C"], (79, 88))


if __name__ == "__main__":
    unittest.main()
