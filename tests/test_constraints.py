import unittest

from buildlab import body, constraints, reference, tables


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

    # -- Task A: sweep the constraints table --------------------------------

    def test_table_covers_exactly_every_attribute_and_bucket(self):
        table = constraints.load()
        valid_buckets = set(tables.weight_buckets())
        valid_attrs = set(reference.tuning_order())
        for attr, bucket in table:
            self.assertIn(bucket, valid_buckets, f"unexpected bucket {bucket}")
            self.assertIn(attr, valid_attrs, f"unexpected attribute {attr}")
        # 21 attributes x 20 buckets: a future data refresh that drops or
        # adds coverage should be noticed here, not discovered later.
        self.assertEqual(len(table), 21 * 20)

    def test_every_associated_name_is_a_tracked_attribute(self):
        # effective_ceiling silently no-ops (values.get(...) is None: continue)
        # for any associated name it doesn't recognise, so an unrecognised
        # name would quietly stop constraining anything -- the same silent
        # gap shape as the 5'9" body.ceilings bug. This must never happen.
        valid_attrs = set(reference.tuning_order())
        unrecognised = [
            (attr, bucket, rule["associated"])
            for (attr, bucket), rules in constraints.load().items()
            for rule in rules
            if rule["associated"] not in valid_attrs
        ]
        self.assertEqual(unrecognised, [])

    def test_no_rule_links_an_attribute_to_itself(self):
        self_refs = [
            (attr, bucket, rule)
            for (attr, bucket), rules in constraints.load().items()
            for rule in rules
            if rule["associated"] == attr
        ]
        self.assertEqual(self_refs, [])

    def test_every_rule_has_both_keys_and_a_valid_max_delta(self):
        for (attr, bucket), rules in constraints.load().items():
            for rule in rules:
                self.assertIn("associated", rule, f"{attr}/{bucket}: {rule}")
                self.assertIn("max_delta", rule, f"{attr}/{bucket}: {rule}")
                self.assertIsInstance(rule["max_delta"], int, f"{attr}/{bucket}: {rule}")
                self.assertGreaterEqual(rule["max_delta"], 0, f"{attr}/{bucket}: {rule}")

    def test_table_has_exactly_1545_rules(self):
        total = sum(len(rules) for rules in constraints.load().values())
        self.assertEqual(total, 1545)

    def test_rules_for_never_raises_across_every_combination(self):
        for attr in reference.tuning_order():
            for bucket in tables.weight_buckets():
                rules = constraints.rules_for(attr, bucket)
                self.assertIsInstance(rules, list)

    # -- Task B: prove the constraints/body integration ----------------------

    def test_effective_ceiling_stays_within_bounds_for_a_real_body(self):
        height, weight, wingspan = 74, 165, 74
        self.assertTrue(body.is_legal("PG", height, weight, wingspan))
        bucket = tables.bucket_for_inches(height)
        ceilings = body.ceilings(height, weight, wingspan)
        # Bridge snake_case builder names to tuning identifiers.
        values = {
            reference.TUNING_NAME[name]: ceiling
            for name, ceiling in ceilings.items()
        }
        for attr in reference.tuning_order():
            hard_ceiling = values[attr]
            result = constraints.effective_ceiling(attr, bucket, values, hard_ceiling)
            self.assertIsInstance(result, int)
            self.assertGreaterEqual(result, 25)
            self.assertLessEqual(result, 99)
            self.assertLessEqual(result, hard_ceiling)

    def test_speed_with_ball_is_hard_locked_to_speed_at_6ft2(self):
        # The single most consequential constraint in the game:
        # SpeedWithBall <= Speed + 0. At a 6'2" body (min weight, min
        # wingspan) body.ceilings gives speed_with_ball a raw ceiling of 94,
        # but if Speed is only 80 the effective ceiling must come down to 80.
        height, weight, wingspan = 74, 165, 74
        self.assertTrue(body.is_legal("PG", height, weight, wingspan))
        ceilings = body.ceilings(height, weight, wingspan)
        self.assertEqual(ceilings["speed_with_ball"], 94)

        bucket = tables.bucket_for_inches(height)
        values = {
            reference.TUNING_NAME[name]: ceiling
            for name, ceiling in ceilings.items()
        }
        values["Speed"] = 80
        result = constraints.effective_ceiling(
            "SpeedWithBall", bucket, values, hard_ceiling=94
        )
        self.assertEqual(result, 80)


if __name__ == "__main__":
    unittest.main()
