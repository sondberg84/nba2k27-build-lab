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


if __name__ == "__main__":
    unittest.main()
