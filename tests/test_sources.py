import unittest

from buildlab import sources


class TestSources(unittest.TestCase):
    def test_manifest_lists_thirteen_files(self):
        manifest = sources.load()
        self.assertEqual(len(manifest["sources"][0]["files"]), 13)

    def test_commit_is_pinned(self):
        manifest = sources.load()
        self.assertEqual(
            manifest["sources"][0]["commit"], "957d0095182702e34f671e81ecb81efa9def9cb3"
        )

    def test_every_file_matches_its_hash(self):
        # verify() raises if any vendored file has drifted from the manifest
        sources.verify()

    def test_path_for_returns_existing_file(self):
        path = sources.path_for("tuning/progression_attributes.txt")
        self.assertTrue(path.exists())


class TestHardening(unittest.TestCase):
    def test_verify_collects_every_mismatch(self):
        # verify_all returns a list rather than raising on the first problem,
        # so a refresh that breaks several files reports all of them.
        problems = sources.verify_all()
        self.assertEqual(problems, [])

    def test_verify_all_reports_a_tampered_file(self):
        entry = sources.load()["sources"][0]
        rel = next(iter(entry["files"]))
        path = sources.ROOT / entry["files"][rel]["local"]
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"\n")
            problems = sources.verify_all()
            self.assertEqual(len(problems), 1)
            self.assertIn(rel, problems[0])
        finally:
            path.write_bytes(original)
        self.assertEqual(sources.verify_all(), [])

    def test_a_corrupt_manifest_raises_source_error(self):
        with self.assertRaises(sources.SourceError):
            sources.parse_manifest("{ not json")

    def test_the_manifest_parse_error_points_at_the_vendoring_tool(self):
        with self.assertRaises(sources.SourceError) as caught:
            sources.parse_manifest("{ not json")
        self.assertIn("tools/vendor.py", str(caught.exception))

    def test_commit_is_recorded_in_full(self):
        # A trust boundary should pin the whole hash, not an abbreviation.
        commit = sources.load()["sources"][0]["commit"]
        self.assertEqual(len(commit), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in commit))


if __name__ == "__main__":
    unittest.main()
