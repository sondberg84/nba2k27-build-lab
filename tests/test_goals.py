import unittest

from buildlab import goals


class TestGoalTypes(unittest.TestCase):
    def test_attribute_goal_is_its_own_floor(self):
        goal = goals.AttributeGoal("three_point", 90)
        self.assertEqual(goal.floor_options(height_inches=75), [{"three_point": 90}])

    def test_attribute_goal_rejects_an_unknown_name(self):
        with self.assertRaises(KeyError):
            goals.AttributeGoal("nonsense", 90).floor_options(height_inches=75)

    def test_animation_goal_uses_the_package_requirements(self):
        goal = goals.AnimationGoal("Kyrie Irving", "Dribble Style")
        self.assertEqual(
            goal.floor_options(height_inches=74), [{"speed_with_ball": 94}]
        )

    def test_animation_goal_rejects_an_unknown_package(self):
        with self.assertRaises(KeyError):
            goals.AnimationGoal("Not Real", "Dribble Style").floor_options(
                height_inches=75
            )

    def test_and_badge_goal_yields_one_option_with_both_floors(self):
        # posterizer bronze joins two attributes with AND, verified.
        goal = goals.BadgeGoal("posterizer", "bronze")
        options = goal.floor_options(height_inches=75)
        self.assertEqual(len(options), 1)
        self.assertEqual(len(options[0]), 2)

    def test_or_badge_goal_yields_two_options(self):
        goal = goals.BadgeGoal("float_game", "bronze")
        options = goal.floor_options(height_inches=75)
        self.assertEqual(len(options), 2)
        self.assertIn({"close_shot": 65}, options)
        self.assertIn({"driving_layup": 65}, options)

    def test_badge_goal_rejects_legend(self):
        with self.assertRaises(ValueError):
            goals.BadgeGoal("float_game", "legend").floor_options(height_inches=75)

    def test_badge_goal_rejects_an_unknown_tier(self):
        with self.assertRaises(ValueError):
            goals.BadgeGoal("float_game", "platinum").floor_options(height_inches=75)

    def test_badge_goal_out_of_height_range_yields_nothing(self):
        # mini_marksman is guard-only (63-76); at 7'4" it cannot be had at all.
        goal = goals.BadgeGoal("mini_marksman", "bronze")
        self.assertEqual(goal.floor_options(height_inches=88), [])

    def test_animation_goal_out_of_height_range_yields_nothing(self):
        goal = goals.AnimationGoal("Kyrie Irving", "Dribble Style")
        self.assertEqual(goal.floor_options(height_inches=80), [])

    def test_animation_goal_respects_reachability_not_just_the_stated_range(self):
        # Stated range runs to 6'4" but the ceiling blocks it above 6'2".
        goal = goals.AnimationGoal("Kyrie Irving", "Dribble Style")
        self.assertEqual(goal.floor_options(height_inches=74), [{"speed_with_ball": 94}])
        self.assertEqual(goal.floor_options(height_inches=75), [])

    def test_describe_is_human_readable(self):
        self.assertIn("three_point", goals.AttributeGoal("three_point", 90).describe())
        self.assertIn("float_game", goals.BadgeGoal("float_game", "gold").describe())
        self.assertIn(
            "Kyrie Irving",
            goals.AnimationGoal("Kyrie Irving", "Dribble Style").describe(),
        )


if __name__ == "__main__":
    unittest.main()
