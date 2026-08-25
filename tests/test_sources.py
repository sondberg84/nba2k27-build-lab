import unittest

from buildlab import sources


class TestSources(unittest.TestCase):
    def test_manifest_lists_thirteen_files(self):
        manifest = sources.load()
        self.assertEqual(len(manifest["sources"][0]["files"]), 13)

    def test_commit_is_pinned(self):
        manifest = sources.load()
        self.assertEqual(manifest["sources"][0]["commit"], "957d009")

    def test_every_file_matches_its_hash(self):
        # verify() raises if any vendored file has drifted from the manifest
        sources.verify()

    def test_path_for_returns_existing_file(self):
        path = sources.path_for("tuning/progression_attributes.txt")
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
