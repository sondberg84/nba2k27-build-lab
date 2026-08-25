import unittest

import buildlab


class TestPackage(unittest.TestCase):
    def test_version_present(self):
        self.assertEqual(buildlab.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
