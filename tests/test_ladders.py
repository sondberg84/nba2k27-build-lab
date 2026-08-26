import unittest

from buildlab import ladders


class TestLadder(unittest.TestCase):
    def test_ladder_returns_steps_in_ascending_rating_order(self):
        steps = ladders.ladder("ball_handle", height_inches=76)
        self.assertGreater(len(steps), 0)
        ratings = [s["rating"] for s in steps]
        self.assertEqual(ratings, sorted(ratings))

    def test_every_step_unlocks_something(self):
        for step in ladders.ladder("ball_handle", height_inches=76):
            with self.subTest(rating=step["rating"]):
                self.assertTrue(step["animations"] or step["badges"])

    def test_steps_stay_within_the_reachable_ceiling(self):
        steps = ladders.ladder("ball_handle", height_inches=76)
        ceiling = ladders.max_ceiling("ball_handle", height_inches=76)
        for step in steps:
            with self.subTest(rating=step["rating"]):
                self.assertLessEqual(step["rating"], ceiling)

    def test_badge_tiers_appear_as_steps(self):
        steps = ladders.ladder("ball_handle", height_inches=76)
        self.assertGreater(len([s for s in steps if s["badges"]]), 0)

    def test_animation_unlocks_appear_as_steps(self):
        steps = ladders.ladder("speed_with_ball", height_inches=74)
        self.assertGreater(len([s for s in steps if s["animations"]]), 0)

    def test_dead_points_are_identified(self):
        dead = ladders.dead_points("ball_handle", height_inches=76, rating=87)
        self.assertIn("wasted", dead)
        self.assertIn("next_unlock_at", dead)
        self.assertIn("last_unlock_at", dead)

    def test_unknown_attribute_raises(self):
        with self.assertRaises(KeyError):
            ladders.ladder("not_an_attribute", height_inches=76)


class TestFullCost(unittest.TestCase):
    def test_speed_with_ball_drags_in_its_linked_attributes(self):
        # SpeedWithBall <= Speed + 0, <= BallControl + 5, <= Agility + 15.
        cost = ladders.full_cost_of({"speed_with_ball": 94}, height_inches=74)
        self.assertEqual(cost["speed_with_ball"], 94)
        self.assertEqual(cost["speed"], 94)
        self.assertEqual(cost["ball_handle"], 89)
        self.assertEqual(cost["agility"], 79)

    def test_an_unlinked_request_costs_only_itself(self):
        # Every one of the 21 attributes carries at least one associated-
        # attribute rule at every legal build height (verified by scanning
        # buckets 5-24, i.e. 69-88 inches) - there is no attribute that is
        # ever truly rule-free. What "unlinked" means in practice is a target
        # low enough that none of its rules' max_delta cushions are exceeded:
        # free_throw's rules here are <= mid_range + 25 and <= three_point +
        # 20, so a target of 20 needs neither partner to move (20 - 25 and
        # 20 - 20 are both <= 0) and the request costs only itself.
        cost = ladders.full_cost_of({"free_throw": 20}, height_inches=75)
        self.assertEqual(cost, {"free_throw": 20})

    def test_full_cost_respects_an_existing_higher_value(self):
        cost = ladders.full_cost_of(
            {"speed_with_ball": 94, "speed": 99}, height_inches=74
        )
        self.assertEqual(cost["speed"], 99)


if __name__ == "__main__":
    unittest.main()
