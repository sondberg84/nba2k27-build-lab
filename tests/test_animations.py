import unittest

from buildlab import animations, sources


class TestVendoredSource(unittest.TestCase):
    def test_the_markdown_is_in_the_manifest(self):
        path = sources.path_for("local/animation_requirements.md")
        self.assertTrue(path.exists())

    def test_manifest_hashes_still_verify(self):
        sources.verify()

    def test_source_has_the_four_sections(self):
        text = sources.path_for("local/animation_requirements.md").read_text(
            encoding="utf-8"
        )
        for heading in (
            "Dunks, layups and post moves",
            "Shooting animations",
            "Dribble and pass animations",
            "Motion styles",
        ):
            self.assertIn(heading, text)


class TestParser(unittest.TestCase):
    def test_row_count(self):
        self.assertEqual(len(animations.packages()), 1814)

    def test_family_and_section_counts(self):
        rows = animations.packages()
        self.assertEqual(len({r["family"] for r in rows}), 52)
        self.assertEqual(len({r["section"] for r in rows}), 4)

    def test_section_row_counts_match_their_headings(self):
        # The headings declare their own counts; the parse must agree.
        expected = {
            "Dunks, layups and post moves": 266,
            "Shooting animations": 420,
            "Dribble and pass animations": 775,
            "Motion styles": 353,
        }
        counts = {}
        for row in animations.packages():
            counts[row["section"]] = counts.get(row["section"], 0) + 1
        self.assertEqual(counts, expected)

    def test_every_row_has_a_name_and_height_range(self):
        for row in animations.packages():
            with self.subTest(name=row["name"], family=row["family"]):
                self.assertTrue(row["name"])
                self.assertLessEqual(row["min_height"], row["max_height"])
                self.assertGreaterEqual(row["min_height"], 69)

    def test_motion_styles_use_the_name_column(self):
        motion = [r for r in animations.packages() if r["section"] == "Motion styles"]
        self.assertEqual(len(motion), 353)
        self.assertTrue(all(r["name"] for r in motion))

    def test_requirements_use_builder_attribute_names(self):
        from buildlab import reference

        valid = set(reference.attribute_names())
        for row in animations.packages():
            for attribute in row["requirements"]:
                with self.subTest(name=row["name"], attribute=attribute):
                    self.assertIn(attribute, valid)

    def test_requirement_values_are_integers(self):
        for row in animations.packages():
            for attribute, minimum in row["requirements"].items():
                with self.subTest(name=row["name"]):
                    self.assertIsInstance(minimum, int)

    def test_known_row_kyrie_dribble_style(self):
        row = animations.by_name("Kyrie Irving", family="Dribble Style")
        self.assertEqual(row["requirements"], {"speed_with_ball": 94})
        self.assertEqual(row["min_height"], 69)
        self.assertEqual(row["max_height"], 76)

    def test_known_row_small_contact_dunks(self):
        row = animations.by_name(
            "Small Contact Dunks Off Two",
            family="Two Foot Moving Dunks - Contact Dunks",
        )
        self.assertEqual(row["requirements"], {"driving_dunk": 86, "vertical": 75})
        self.assertEqual(row["max_height"], 76)

    def test_unknown_package_raises(self):
        with self.assertRaises(KeyError):
            animations.by_name("Not A Real Package", family="Dribble Style")


if __name__ == "__main__":
    unittest.main()
