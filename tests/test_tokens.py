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

    def test_cost_table_prices_heights_where_a_badge_is_ineligible(self):
        # rise_up is eligible 77-91 but the cost table still carries rows at 69.
        # Pinned because it is the trap cost_of_loadout guards against.
        self.assertFalse(badges.height_eligible(19, 69))
        self.assertIsInstance(tokens.cost_for(19, "bronze", 69), int)

    def test_cost_of_loadout_rejects_a_height_ineligible_badge(self):
        with self.assertRaises(ValueError):
            tokens.cost_of_loadout({19: "bronze"}, 69)

    def test_cumulative_costs_more_than_literal(self):
        loadout = {17: "hall_of_fame"}
        literal = tokens.cost_of_loadout(loadout, 75)
        cumulative = tokens.cost_of_loadout(loadout, 75, cumulative=True)
        self.assertEqual(literal, tokens.cost_for(17, "hall_of_fame", 75))
        self.assertEqual(
            cumulative,
            sum(tokens.cost_for(17, t, 75) for t in badges.TIERS),
        )
        self.assertGreater(cumulative, literal)

    def test_cumulative_stops_at_the_requested_tier(self):
        loadout = {17: "silver"}
        self.assertEqual(
            tokens.cost_of_loadout(loadout, 75, cumulative=True),
            tokens.cost_for(17, "bronze", 75) + tokens.cost_for(17, "silver", 75),
        )

    def test_cumulative_still_rejects_legend(self):
        with self.assertRaises(ValueError):
            tokens.cost_of_loadout({17: "legend"}, 75, cumulative=True)


class TestContributions(unittest.TestCase):
    def test_thirty_one_thousand_five_hundred_rows(self):
        # 20 heights x 21 attributes x 75 ratings
        self.assertEqual(len(tokens.contributions()), 31500)

    def test_contribution_is_six_values_in_discipline_order(self):
        got = tokens.contribution(height_inches=69, attribute=0, rating=25)
        self.assertEqual(len(got), 6)
        self.assertEqual(len(badges.DISCIPLINE_ORDER), 6)

    def test_floor_rating_earns_nothing(self):
        self.assertEqual(
            tokens.contribution(height_inches=69, attribute=0, rating=25),
            (0, 0, 0, 0, 0, 0),
        )

    def test_a_high_rating_earns_something(self):
        got = tokens.contribution(height_inches=69, attribute=0, rating=99)
        self.assertGreater(sum(got), 0)

    def test_contributions_never_decrease_with_rating(self):
        # Monotonic in rating: raising an attribute must never reduce tokens.
        for attribute in range(21):
            with self.subTest(attribute=attribute):
                previous = (0,) * 6
                for rating in range(25, 100):
                    got = tokens.contribution(
                        height_inches=75, attribute=attribute, rating=rating
                    )
                    for before, after in zip(previous, got):
                        self.assertGreaterEqual(after, before)
                    previous = got

    def test_ratings_cover_25_to_99(self):
        ratings = {r["rating"] for r in tokens.contributions()}
        self.assertEqual(min(ratings), 25)
        self.assertEqual(max(ratings), 99)
        self.assertEqual(len(ratings), 75)

    def test_unknown_lookup_raises(self):
        with self.assertRaises(KeyError):
            tokens.contribution(height_inches=60, attribute=0, rating=25)


if __name__ == "__main__":
    unittest.main()
