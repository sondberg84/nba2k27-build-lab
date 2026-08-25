import unittest

from buildlab import tuning


class TestTuning(unittest.TestCase):
    def setUp(self):
        self.table = tuning.load()

    def test_comments_and_header_excluded(self):
        for key in self.table:
            self.assertFalse(key.startswith("//"))
            self.assertNotEqual(key, "DataPath")

    def test_known_scalar_value(self):
        self.assertEqual(self.table["VCRequiredToBuyRangeOfAttributes[0]"], "40000")

    def test_known_weight_value(self):
        key = (
            "HeightBasedAttributeWeight[HEIGHT_05][PLAYERTYPE_00]"
            "[PLAYERDATA_ATTRIBUTE_AgilityAbility]"
        )
        self.assertEqual(self.table[key], "6.55")

    def test_height_bucket_count(self):
        buckets = [k for k in self.table if k.startswith("HeightInWholeInches")]
        self.assertEqual(len(buckets), 31)

    def test_weight_row_count(self):
        rows = [k for k in self.table if k.startswith("HeightBasedAttributeWeight")]
        self.assertEqual(len(rows), 6271)


if __name__ == "__main__":
    unittest.main()
