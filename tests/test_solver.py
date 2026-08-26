import unittest

from buildlab import goals, ladders, solver


class TestSolveAtHeight(unittest.TestCase):
    def test_a_single_attribute_goal_produces_that_floor(self):
        result = solver.solve_at([goals.AttributeGoal("three_point", 90)], 75)
        self.assertTrue(result["feasible"])
        self.assertGreaterEqual(result["build"]["three_point"], 90)

    def test_the_build_is_a_full_21_attribute_vector(self):
        result = solver.solve_at([goals.AttributeGoal("three_point", 90)], 75)
        self.assertEqual(len(result["build"]), 21)
        for value in result["build"].values():
            self.assertGreaterEqual(value, ladders.ATTRIBUTE_FLOOR)

    def test_linked_constraints_are_included_in_the_build(self):
        result = solver.solve_at([goals.AttributeGoal("speed_with_ball", 94)], 74)
        self.assertTrue(result["feasible"])
        self.assertGreaterEqual(result["build"]["speed"], 94)
        self.assertGreaterEqual(result["build"]["ball_handle"], 89)
        self.assertGreaterEqual(result["build"]["agility"], 79)

    def test_points_and_overall_are_reported(self):
        result = solver.solve_at([goals.AttributeGoal("three_point", 90)], 75)
        self.assertIn("points", result)
        self.assertIn("overall", result)
        self.assertGreater(result["points"], 0)
        self.assertGreaterEqual(result["overall"], 25)

    def test_an_impossible_attribute_is_infeasible(self):
        # standing_dunk is capped at 51 on the best 6'3" body.
        result = solver.solve_at([goals.AttributeGoal("standing_dunk", 90)], 75)
        self.assertFalse(result["feasible"])
        self.assertIn("standing_dunk", result["reason"])

    def test_infeasibility_names_the_ceiling(self):
        result = solver.solve_at([goals.AttributeGoal("standing_dunk", 90)], 75)
        self.assertIn("ceiling", result["reason"].lower())

    def test_an_out_of_range_goal_is_infeasible_with_its_name(self):
        result = solver.solve_at([goals.BadgeGoal("mini_marksman", "bronze")], 88)
        self.assertFalse(result["feasible"])
        self.assertIn("mini_marksman", result["reason"])

    def test_an_or_goal_picks_the_cheaper_branch(self):
        result = solver.solve_at([goals.BadgeGoal("float_game", "bronze")], 75)
        self.assertTrue(result["feasible"])
        build = result["build"]
        self.assertTrue(build["close_shot"] >= 65 or build["driving_layup"] >= 65)

    def test_two_goals_take_the_pointwise_maximum(self):
        result = solver.solve_at(
            [
                goals.AttributeGoal("three_point", 90),
                goals.AttributeGoal("three_point", 80),
            ],
            75,
        )
        self.assertGreaterEqual(result["build"]["three_point"], 90)

    def test_empty_goals_gives_a_floor_build(self):
        result = solver.solve_at([], 75)
        self.assertTrue(result["feasible"])
        self.assertEqual(result["points"], 0)
        self.assertEqual(set(result["build"].values()), {ladders.ATTRIBUTE_FLOOR})


class TestSolveAcrossHeights(unittest.TestCase):
    def test_kyrie_dribble_style_only_works_to_six_two(self):
        result = solver.solve([goals.AnimationGoal("Kyrie Irving", "Dribble Style")])
        self.assertTrue(result["feasible"])
        self.assertEqual(result["heights"][-1], 74)

    def test_the_cheapest_height_is_reported(self):
        result = solver.solve([goals.AttributeGoal("three_point", 90)])
        self.assertIn("best", result)
        self.assertIn(result["best"]["height_inches"], result["heights"])

    def test_impossible_everywhere_is_reported_not_crashed(self):
        result = solver.solve(
            [
                goals.AnimationGoal("Kyrie Irving", "Dribble Style"),
                goals.BadgeGoal("paint_patroller", "gold"),
            ]
        )
        self.assertFalse(result["feasible"])
        self.assertTrue(result["reason"])

    def test_conflicting_goals_name_both_sides(self):
        # Kyrie's dribble style is reachable only to 6'2"; paint_patroller
        # starts at 6'5". They share no legal height.
        result = solver.solve(
            [
                goals.AnimationGoal("Kyrie Irving", "Dribble Style"),
                goals.BadgeGoal("paint_patroller", "gold"),
            ]
        )
        self.assertIn("Kyrie Irving", result["reason"])
        self.assertIn("paint_patroller", result["reason"])


if __name__ == "__main__":
    unittest.main()
