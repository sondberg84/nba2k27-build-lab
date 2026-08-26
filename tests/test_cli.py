import io
import unittest
from contextlib import redirect_stdout

from buildlab import cli


class TestCli(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_eval_prints_overall_and_archetype(self):
        values = ",".join(["70"] * 21)
        code, out = self.run_cli(["eval", "--height", "6-3", "--values", values])
        self.assertEqual(code, 0)
        self.assertIn("OVERALL", out)
        self.assertIn("ARCHETYPE", out)

    def test_eval_rejects_wrong_attribute_count(self):
        code, out = self.run_cli(["eval", "--height", "6-3", "--values", "70,70"])
        self.assertEqual(code, 2)
        self.assertIn("21", out)

    def test_height_accepts_feet_dash_inches(self):
        self.assertEqual(cli.parse_height("6-3"), 75)
        self.assertEqual(cli.parse_height("7-4"), 88)


class TestBadgesCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_badges_lists_unlocked_badges(self):
        values = ",".join(["99"] * 21)
        code, out = self.run_cli(["badges", "--height", "6-3", "--values", values])
        self.assertEqual(code, 0)
        self.assertIn("UNLOCKED", out)
        self.assertIn("hall_of_fame", out)

    def test_badges_reports_none_for_a_floor_build(self):
        values = ",".join(["25"] * 21)
        code, out = self.run_cli(["badges", "--height", "6-3", "--values", values])
        self.assertEqual(code, 0)
        self.assertIn("UNLOCKED  0", out)

    def test_badges_rejects_wrong_attribute_count(self):
        code, out = self.run_cli(["badges", "--height", "6-3", "--values", "70,70"])
        self.assertEqual(code, 2)
        self.assertIn("21", out)

    def test_badges_shows_the_token_basis(self):
        values = ",".join(["80"] * 21)
        _, out = self.run_cli(["badges", "--height", "6-3", "--values", values])
        self.assertIn("TOKENS EARNED", out)
        self.assertIn("additive", out.lower())

    def test_badges_survives_a_tall_build_without_token_data(self):
        # Height 7-0 is 84 inches, inside the range where token data is not
        # trustworthy. Badges still work; tokens must degrade gracefully.
        values = ",".join(["90"] * 21)
        code, out = self.run_cli(["badges", "--height", "7-0", "--values", values])
        self.assertEqual(code, 0)
        self.assertIn("UNLOCKED", out)
        self.assertIn("unavailable", out.lower())
        self.assertNotIn("TOKENS EARNED  0", out)

    def test_badges_prints_costs_for_unlocked_badges(self):
        values = ",".join(["99"] * 21)
        _, out = self.run_cli(["badges", "--height", "6-3", "--values", values])
        self.assertIn("tokens", out.lower())


class TestAnimationsCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_animations_lists_available_packages(self):
        values = ",".join(["99"] * 21)
        code, out = self.run_cli(["animations", "--height", "6-3", "--values", values])
        self.assertEqual(code, 0)
        self.assertIn("AVAILABLE", out)

    def test_animations_filters_by_family(self):
        values = ",".join(["99"] * 21)
        code, out = self.run_cli(
            [
                "animations", "--height", "6-2", "--values", values,
                "--family", "Dribble Style",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("Dribble Style", out)

    def test_animations_rejects_wrong_attribute_count(self):
        code, out = self.run_cli(["animations", "--height", "6-3", "--values", "70,70"])
        self.assertEqual(code, 2)
        self.assertIn("21", out)

    def test_ladder_shows_thresholds(self):
        code, out = self.run_cli(
            ["ladder", "--height", "6-4", "--attribute", "ball_handle"]
        )
        self.assertEqual(code, 0)
        self.assertIn("LADDER", out)
        self.assertIn("ball_handle", out)

    def test_ladder_rejects_an_unknown_attribute(self):
        code, out = self.run_cli(
            ["ladder", "--height", "6-4", "--attribute", "nonsense"]
        )
        self.assertEqual(code, 2)


    def test_reachability_lists_narrowed_packages(self):
        code, out = self.run_cli(["reachability", "--family", "Dribble Style"])
        self.assertEqual(code, 0)
        self.assertIn("NARROWED", out)
        self.assertIn("Kyrie Irving", out)

    def test_reachability_rejects_an_unknown_family(self):
        code, out = self.run_cli(["reachability", "--family", "Not A Family"])
        self.assertEqual(code, 2)


class TestSolveCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_solve_with_an_attribute_goal(self):
        code, out = self.run_cli(["solve", "--attribute", "three_point=90"])
        self.assertEqual(code, 0)
        self.assertIn("FEASIBLE", out)
        self.assertIn("three_point", out)

    def test_solve_with_a_badge_goal(self):
        code, out = self.run_cli(["solve", "--badge", "float_game=gold"])
        self.assertEqual(code, 0)
        self.assertIn("FEASIBLE", out)

    def test_solve_with_an_animation_goal(self):
        code, out = self.run_cli(
            ["solve", "--animation", "Dribble Style:Kyrie Irving"]
        )
        self.assertEqual(code, 0)
        self.assertIn("6-2", out)

    def test_solve_reports_infeasibility(self):
        code, out = self.run_cli(
            [
                "solve",
                "--animation", "Dribble Style:Kyrie Irving",
                "--badge", "paint_patroller=gold",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("NOT FEASIBLE", out)

    def test_solve_rejects_a_malformed_goal(self):
        code, out = self.run_cli(["solve", "--attribute", "three_point"])
        self.assertEqual(code, 2)

    def test_solve_requires_at_least_one_goal(self):
        code, out = self.run_cli(["solve"])
        self.assertEqual(code, 2)

    def test_solve_accepts_a_fixed_height(self):
        code, out = self.run_cli(
            ["solve", "--attribute", "three_point=90", "--height", "6-3"]
        )
        self.assertEqual(code, 0)
        self.assertIn("6-3", out)


class TestCritiqueCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_critique_reports_overall_and_waste(self):
        values = ",".join(["70"] * 21)
        code, out = self.run_cli(["critique", "--height", "6-4", "--values", values])
        self.assertEqual(code, 0)
        self.assertIn("OVERALL", out)
        self.assertIn("WASTED", out)

    def test_critique_checks_a_claim(self):
        values = ",".join(["70"] * 21)
        code, out = self.run_cli(
            [
                "critique", "--height", "6-4", "--values", values,
                "--claim", "ankle_assassin=hall_of_fame",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("CLAIMS", out)
        self.assertIn("does not hold", out.lower())

    def test_critique_rejects_wrong_attribute_count(self):
        code, out = self.run_cli(["critique", "--height", "6-4", "--values", "70,70"])
        self.assertEqual(code, 2)

    def test_critique_flags_an_illegal_value(self):
        values = ["70"] * 21
        values[3] = "95"
        code, out = self.run_cli(
            ["critique", "--height", "6-4", "--values", ",".join(values)]
        )
        self.assertEqual(code, 0)
        self.assertIn("ABOVE THE CEILING", out.upper())


class TestRefreshCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_refresh_requires_a_mode(self):
        code, out = self.run_cli(["refresh"])
        self.assertEqual(code, 2)
        self.assertIn("--check", out)

    def test_refresh_rejects_adopt_without_preview(self):
        code, out = self.run_cli(["refresh", "--adopt"])
        self.assertEqual(code, 2)
        self.assertIn("--preview", out)


class TestRateCommand(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_rate_validates_the_file(self):
        code, out = self.run_cli(["rate", "--validate"])
        self.assertEqual(code, 0)
        self.assertIn("VALID", out.upper())

    def test_rate_lists_the_testing_shortlist(self):
        code, out = self.run_cli(["rate", "--shortlist"])
        self.assertEqual(code, 0)
        self.assertIn("Dribble Style", out)

    def test_rate_requires_a_mode(self):
        code, out = self.run_cli(["rate"])
        self.assertEqual(code, 2)


class TestServeCommand(unittest.TestCase):
    def test_serve_rejects_a_bad_port(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(["serve", "--port", "99999"])
        self.assertEqual(code, 2)
        self.assertIn("port", buffer.getvalue().lower())

    def test_serve_is_a_registered_command(self):
        # Argparse should know about it without starting a server.
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                cli.main(["--help"])
        self.assertIn("serve", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
