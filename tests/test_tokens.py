import unittest

from buildlab import badges, tokens


class TestTokenCosts(unittest.TestCase):
    def test_five_thousand_three_hundred_cost_rows(self):
        self.assertEqual(len(tokens.costs()), 5300)

    def test_costs_cover_legal_heights_only(self):
        heights = {r["height_inches"] for r in tokens.costs()}
        self.assertEqual(min(heights), 69)
        self.assertEqual(max(heights), 88)
        self.assertEqual(len(heights), 20)

    def test_five_tiers_including_legend(self):
        self.assertEqual(
            sorted({r["tier"] for r in tokens.costs()}),
            ["bronze", "gold", "hall_of_fame", "legend", "silver"],
        )

    def test_known_cost(self):
        self.assertEqual(tokens.cost_for(17, "bronze", 69), 3)

    def test_every_legend_row_costs_zero(self):
        legend = [r for r in tokens.costs() if r["tier"] == "legend"]
        self.assertEqual(len(legend), 1060)
        self.assertTrue(all(r["cost"] == 0 for r in legend))

    def test_legend_is_reported_as_unreachable_not_free(self):
        # A zero cost must not read as "free to equip". Legend cannot be
        # bought at build creation at all.
        self.assertTrue(tokens.is_unreachable_tier("legend"))
        self.assertFalse(tokens.is_unreachable_tier("gold"))

    def test_unknown_combination_raises(self):
        with self.assertRaises(KeyError):
            tokens.cost_for(17, "bronze", 60)

    def test_cost_of_loadout_sums_equipped_badges(self):
        loadout = {17: "bronze"}
        expected = tokens.cost_for(17, "bronze", 69)
        self.assertEqual(tokens.cost_of_loadout(loadout, 69), expected)

    def test_cost_of_loadout_rejects_legend(self):
        with self.assertRaises(ValueError):
            tokens.cost_of_loadout({17: "legend"}, 69)


if __name__ == "__main__":
    unittest.main()
