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


if __name__ == "__main__":
    unittest.main()
