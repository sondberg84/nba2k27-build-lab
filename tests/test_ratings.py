import unittest

from buildlab import ratings


class TestRatingsFile(unittest.TestCase):
    def test_loads_and_starts_empty(self):
        self.assertEqual(ratings.all_ratings(), {})

    def test_the_scale_is_documented(self):
        self.assertIn("1 to 10", ratings.meta()["scale"])

    def test_the_file_is_not_manifested(self):
        # Ratings are hand-authored, so they must not be hash-pinned like
        # vendored data — a hash would make editing them look like corruption.
        # (A plain substring check on "ratings" false-positives against the
        # legitimately-vendored overall/uniform_ratings.json, so this checks
        # the actual local path of data/ratings.json instead.)
        from buildlab import sources

        for source in sources.load()["sources"]:
            for entry in source["files"].values():
                self.assertNotEqual(entry["local"], "data/ratings.json")


class TestLookup(unittest.TestCase):
    def test_an_unrated_package_returns_none(self):
        self.assertIsNone(ratings.rating_for("Kyrie Irving", "Dribble Style"))

    def test_rating_for_rejects_an_unknown_package(self):
        with self.assertRaises(KeyError):
            ratings.rating_for("Not A Package", "Dribble Style")

    def test_key_round_trips(self):
        key = ratings.key_for("Kyrie Irving", "Dribble Style")
        self.assertIn("Kyrie Irving", key)
        self.assertIn("Dribble Style", key)


class TestValidation(unittest.TestCase):
    def test_a_well_formed_entry_validates(self):
        problems = ratings.validate(
            {"Dribble Style::Kyrie Irving": {"speed": 8, "tier": "S"}}
        )
        self.assertEqual(problems, [])

    def test_an_unknown_package_is_reported(self):
        problems = ratings.validate({"Dribble Style::Nobody": {"speed": 8}})
        self.assertEqual(len(problems), 1)
        self.assertIn("Nobody", problems[0])

    def test_a_score_outside_one_to_ten_is_reported(self):
        problems = ratings.validate(
            {"Dribble Style::Kyrie Irving": {"speed": 44}}
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("speed", problems[0])

    def test_an_unknown_tier_is_reported(self):
        problems = ratings.validate(
            {"Dribble Style::Kyrie Irving": {"tier": "Z"}}
        )
        self.assertEqual(len(problems), 1)

    def test_the_shipped_empty_file_validates(self):
        self.assertEqual(ratings.validate(ratings.all_ratings()), [])


class TestRanking(unittest.TestCase):
    def test_unrated_packages_rank_after_rated_ones(self):
        scored = ratings.rank(
            [
                {"name": "Kyrie Irving", "family": "Dribble Style"},
                {"name": "Pro", "family": "Dribble Style"},
            ],
            table={"Dribble Style::Pro": {"tier": "S"}},
        )
        self.assertEqual(scored[0]["name"], "Pro")

    def test_ranking_is_stable_when_nothing_is_rated(self):
        rows = [
            {"name": "Kyrie Irving", "family": "Dribble Style"},
            {"name": "Pro", "family": "Dribble Style"},
        ]
        self.assertEqual([r["name"] for r in ratings.rank(rows, table={})],
                         [r["name"] for r in rows])


if __name__ == "__main__":
    unittest.main()
