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

    def test_families_is_sortable_and_complete(self):
        # Motion styles has no sub-headings, so its rows take the section name
        # as their family. Without that, families() raises on sorting None.
        names = animations.families()
        self.assertEqual(len(names), 52)
        self.assertIn("Motion styles", names)
        self.assertNotIn(None, names)

    def test_motion_styles_rows_are_addressable(self):
        row = animations.by_name("Base", family="Motion styles")
        self.assertEqual(row["section"], "Motion styles")
        self.assertEqual(row["min_height"], 69)
        self.assertEqual(row["max_height"], 88)


class TestAvailability(unittest.TestCase):
    def test_a_floor_build_gets_only_unrestricted_packages(self):
        available = animations.available([25] * 21, height_inches=75)
        self.assertGreater(len(available), 0)
        for row in available:
            with self.subTest(name=row["name"]):
                self.assertTrue(
                    all(minimum <= 25 for minimum in row["requirements"].values())
                )

    def test_a_maxed_build_gets_more_than_a_floor_build(self):
        low = animations.available([25] * 21, height_inches=75)
        high = animations.available([99] * 21, height_inches=75)
        self.assertGreater(len(high), len(low))

    def test_height_gates_are_enforced(self):
        # "Kyrie Irving" names packages in 34 families, so the assertion must
        # be scoped to one of them. The Dribble Style row caps at 6'4"; its
        # Pass Style row runs to 7'4" and would mask the gate if we matched on
        # name alone.
        values = [99] * 21

        def has_dribble_style(height_inches):
            return any(
                row["name"] == "Kyrie Irving" and row["family"] == "Dribble Style"
                for row in animations.available(values, height_inches=height_inches)
            )

        self.assertTrue(has_dribble_style(76))
        self.assertFalse(has_dribble_style(77))

    def test_available_in_family_filters(self):
        rows = animations.available(
            [99] * 21, height_inches=75, family="Dribble Style"
        )
        self.assertGreater(len(rows), 0)
        for row in rows:
            with self.subTest(name=row["name"]):
                self.assertEqual(row["family"], "Dribble Style")

    def test_missing_requirement_blocks_a_package(self):
        # Same scoping requirement: lowering speed_with_ball blocks the Dribble
        # Style row but leaves the Post Go-To Shot and Pass Style rows of the
        # same name untouched.
        from buildlab import reference

        index = reference.attribute_names().index("speed_with_ball")

        def has_dribble_style(speed_with_ball):
            values = [99] * 21
            values[index] = speed_with_ball
            return any(
                row["name"] == "Kyrie Irving" and row["family"] == "Dribble Style"
                for row in animations.available(values, height_inches=75)
            )

        self.assertFalse(has_dribble_style(93))
        self.assertTrue(has_dribble_style(94))

    def test_requirements_of_reports_every_gate(self):
        gates = animations.requirements_of("Kyrie Irving", family="Dribble Style")
        self.assertEqual(gates["requirements"], {"speed_with_ball": 94})
        self.assertEqual(gates["min_height"], 69)
        self.assertEqual(gates["max_height"], 76)

    def test_available_rejects_a_wrong_length_vector(self):
        with self.assertRaises(ValueError):
            animations.available([50] * 20, height_inches=75)

    def test_height_gates_collapse_into_three_bands(self):
        # min_height takes only 3 values and max_height only 3, so every
        # package sits in one of three height bands. The boundaries at 6'4"/6'5"
        # and 6'9"/6'10" are where availability changes sharply, and 375
        # packages drop out at the first one alone.
        rows = animations.packages()
        self.assertEqual(sorted({r["min_height"] for r in rows}), [69, 77, 82])
        self.assertEqual(sorted({r["max_height"] for r in rows}), [76, 81, 88])

        maxed = [99] * 21
        counts = {
            h: len(animations.available(maxed, height_inches=h))
            for h in (76, 77, 81, 82)
        }
        self.assertGreater(counts[77], counts[76])
        self.assertGreater(counts[81], counts[82])


class TestReachability(unittest.TestCase):
    def test_kyrie_dribble_style_is_unreachable_above_six_two(self):
        # Stated range is 5'9"-6'4", but it needs 94 speed_with_ball and the
        # ceiling is 93 at 6'3" and 91 at 6'4" on every legal body.
        self.assertTrue(
            animations.reachable_at("Kyrie Irving", "Dribble Style", height_inches=74)
        )
        self.assertFalse(
            animations.reachable_at("Kyrie Irving", "Dribble Style", height_inches=75)
        )
        self.assertFalse(
            animations.reachable_at("Kyrie Irving", "Dribble Style", height_inches=76)
        )

    def test_reachable_range_narrows_the_stated_range(self):
        stated = animations.requirements_of("Kyrie Irving", family="Dribble Style")
        real = animations.reachable_range("Kyrie Irving", "Dribble Style")
        self.assertEqual(stated["max_height"], 76)
        self.assertEqual(real["max_height"], 74)
        self.assertTrue(real["narrower_than_stated"])

    def test_reachable_range_reports_the_binding_attribute(self):
        real = animations.reachable_range("Kyrie Irving", "Dribble Style")
        self.assertEqual(real["blocked_by"], "speed_with_ball")

    def test_an_unrestricted_package_is_reachable_across_its_whole_range(self):
        row = next(r for r in animations.packages() if not r["requirements"])
        real = animations.reachable_range(row["name"], row["family"])
        self.assertEqual(real["min_height"], row["min_height"])
        self.assertEqual(real["max_height"], row["max_height"])
        self.assertFalse(real["narrower_than_stated"])

    def test_max_ceiling_at_matches_body_ceilings(self):
        # The scan must agree with body.ceilings for a known body.
        from buildlab import body

        caps = body.ceilings(height=75, weight=198, wingspan=78)
        self.assertGreaterEqual(
            animations.max_ceiling_at(75, "speed_with_ball"), caps["speed_with_ball"]
        )


if __name__ == "__main__":
    unittest.main()
