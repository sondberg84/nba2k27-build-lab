import unittest

from buildlab import badges


class TestDefinitions(unittest.TestCase):
    def test_fifty_three_badges(self):
        self.assertEqual(len(badges.definitions()), 53)

    def test_lookup_by_id_and_by_name(self):
        by_id = badges.by_id(17)
        self.assertEqual(by_id["name"], "float_game")
        self.assertEqual(badges.by_name("float_game")["badge"], 17)

    def test_unknown_badge_raises(self):
        with self.assertRaises(KeyError):
            badges.by_id(9999)

    def test_every_badge_is_allowed(self):
        # All 53 ship allowed=True. Pinned so a future refresh that disables
        # one is noticed rather than silently changing what builds can equip.
        self.assertTrue(all(b["allowed"] for b in badges.definitions()))

    def test_six_disciplines(self):
        self.assertEqual(
            badges.DISCIPLINE_ORDER,
            ("finishing", "shooting", "playmaking", "defense", "rebounding", "physicals"),
        )


class TestHeightEligibility(unittest.TestCase):
    def test_unrestricted_badge_is_eligible_at_every_legal_height(self):
        unrestricted = next(
            b for b in badges.definitions() if b["height_inches"] == [63, 91]
        )
        for height in range(69, 89):
            self.assertTrue(badges.height_eligible(unrestricted["badge"], height))

    def test_twenty_six_badges_are_height_restricted(self):
        restricted = [b for b in badges.definitions() if b["height_inches"] != [63, 91]]
        self.assertEqual(len(restricted), 26)

    def test_restricted_badge_is_excluded_outside_its_range(self):
        restricted = next(
            b for b in badges.definitions() if b["height_inches"] != [63, 91]
        )
        low, high = restricted["height_inches"]
        self.assertTrue(badges.height_eligible(restricted["badge"], low))
        self.assertTrue(badges.height_eligible(restricted["badge"], high))
        self.assertFalse(badges.height_eligible(restricted["badge"], low - 1))
        self.assertFalse(badges.height_eligible(restricted["badge"], high + 1))

    def test_eligible_at_height_returns_ids(self):
        at_69 = badges.eligible_at_height(69)
        at_88 = badges.eligible_at_height(88)
        self.assertTrue(set(at_69) <= {b["badge"] for b in badges.definitions()})
        self.assertNotEqual(at_69, at_88)


class TestTierRequirements(unittest.TestCase):
    def test_two_hundred_and_twelve_requirement_rows(self):
        self.assertEqual(len(badges.tier_requirements()), 212)

    def test_four_tiers_have_requirements(self):
        self.assertEqual(badges.TIERS, ("bronze", "silver", "gold", "hall_of_fame"))

    def test_requirement_lists_are_one_or_two_entries(self):
        for row in badges.tier_requirements():
            with self.subTest(badge=row["name"], tier=row["tier"]):
                self.assertIn(len(row["requirements"]), (1, 2))

    def test_float_game_bronze_is_an_or(self):
        # close_shot 65 OR driving_layup 65 — either alone qualifies.
        values = [0] * 21
        values[0] = 65
        self.assertTrue(badges.meets(17, "bronze", values))
        values = [0] * 21
        values[1] = 65
        self.assertTrue(badges.meets(17, "bronze", values))
        self.assertFalse(badges.meets(17, "bronze", [0] * 21))

    def test_trailing_operator_is_ignored(self):
        # A single-entry requirement must qualify on that entry alone,
        # regardless of the terminator its operator_to_next carries.
        singles = [r for r in badges.tier_requirements() if len(r["requirements"]) == 1]
        self.assertGreater(len(singles), 0)
        row = singles[0]
        req = row["requirements"][0]
        values = [0] * 21
        values[req["attribute"]] = req["minimum"]
        self.assertTrue(badges.meets(row["badge"], row["tier"], values))

    def test_and_requires_both_attributes(self):
        ands = [
            r
            for r in badges.tier_requirements()
            if len(r["requirements"]) == 2
            and r["requirements"][0]["operator_to_next"] == "AND"
        ]
        self.assertGreater(len(ands), 0)
        row = ands[0]
        first, second = row["requirements"]
        only_first = [0] * 21
        only_first[first["attribute"]] = first["minimum"]
        self.assertFalse(badges.meets(row["badge"], row["tier"], only_first))
        both = list(only_first)
        both[second["attribute"]] = second["minimum"]
        self.assertTrue(badges.meets(row["badge"], row["tier"], both))

    def test_legend_has_no_attribute_path(self):
        # Legend never appears in tier_requirements: it cannot be reached by
        # raising attributes, only through a Max Plus 2 fuse slot.
        self.assertNotIn("legend", {r["tier"] for r in badges.tier_requirements()})
        with self.assertRaises(KeyError):
            badges.meets(17, "legend", [99] * 21)

    def test_best_tier_returns_the_highest_qualifying_tier(self):
        self.assertIsNone(badges.best_tier(17, [0] * 21, height_inches=75))
        self.assertEqual(badges.best_tier(17, [99] * 21, height_inches=75), "hall_of_fame")

    def test_best_tier_respects_height_eligibility(self):
        restricted = next(
            b for b in badges.definitions() if b["height_inches"] != badges.UNRESTRICTED
        )
        outside = restricted["height_inches"][1] + 1
        self.assertIsNone(
            badges.best_tier(restricted["badge"], [99] * 21, height_inches=outside)
        )

    def test_unlocked_lists_every_qualifying_badge(self):
        maxed = badges.unlocked([99] * 21, height_inches=75)
        self.assertGreater(len(maxed), 0)
        for badge_id, tier in maxed.items():
            with self.subTest(badge=badge_id):
                self.assertIn(tier, badges.TIERS)
        self.assertEqual(badges.unlocked([0] * 21, height_inches=75), {})

    def test_every_badge_has_all_four_tiers(self):
        # The 212 row count alone would not catch an uneven distribution, and
        # best_tier now relies on every tier being present rather than
        # silently skipping a missing one.
        by_badge = {}
        for row in badges.tier_requirements():
            by_badge.setdefault(row["badge"], set()).add(row["tier"])
        self.assertEqual(len(by_badge), 53)
        for badge_id, tiers in by_badge.items():
            with self.subTest(badge=badge_id):
                self.assertEqual(tiers, set(badges.TIERS))

    def test_meets_rejects_an_unexpected_requirement_count(self):
        # Guards the satisfied[0]/satisfied[1] indexing in meets(). Injects a
        # third entry into the cached index and restores it afterwards.
        index = badges._requirements_index()
        key = (17, "bronze")
        original = index[key]
        index[key] = list(original) + [dict(original[0])]
        try:
            with self.assertRaises(ValueError):
                badges.meets(17, "bronze", [99] * 21)
        finally:
            index[key] = original


if __name__ == "__main__":
    unittest.main()
