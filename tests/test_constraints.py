import unittest

from buildlab import constraints, reference


class TestConstraints(unittest.TestCase):
    def test_every_attribute_has_constraints(self):
        table = constraints.load()
        covered = {attr for attr, _ in table}
        for name in reference.tuning_order():
            self.assertIn(name, covered)

    def test_agility_is_linked_to_speed_at_bucket_5(self):
        rules = constraints.rules_for("Agility", 5)
        linked = {rule["associated"]: rule["max_delta"] for rule in rules}
        self.assertEqual(linked["Speed"], 10)
        self.assertEqual(linked["ReboundDefense"], 50)

    def test_zero_max_delta_is_preserved_not_dropped(self):
        # Upstream commit 957d009 fixed a bug reading MaxDelta 0. A zero delta
        # is a hard lock, not a missing value, and must survive parsing.
        zeros = [
            (attr, bucket, rule)
            for (attr, bucket), rules in constraints.load().items()
            for rule in rules
            if rule["max_delta"] == 0
        ]
        self.assertGreater(len(zeros), 0)

    def test_effective_ceiling_respects_a_linked_attribute(self):
        values = {name: 40 for name in reference.tuning_order()}
        values["Speed"] = 60
        capped = constraints.effective_ceiling("Agility", 5, values, hard_ceiling=99)
        self.assertEqual(capped, 70)  # Speed 60 + MaxDelta 10

    def test_effective_ceiling_never_exceeds_the_hard_ceiling(self):
        values = {name: 99 for name in reference.tuning_order()}
        capped = constraints.effective_ceiling("Agility", 5, values, hard_ceiling=85)
        self.assertEqual(capped, 85)


if __name__ == "__main__":
    unittest.main()
