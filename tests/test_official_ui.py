import json
import unittest

from buildlab import ovr, sources

REFERENCE_HEIGHT = 75
STANDING_DUNK_INDEX = 3  # values[3] == StandingDunk, per reference.tuning_order()


def official_ui_rows():
    payload = json.loads(
        sources.path_for("overall/official_ui_verified.json").read_text(
            encoding="utf-8"
        )
    )
    return payload["data"]


class TestOfficialUiVerified(unittest.TestCase):
    """Pins the two rows in this dataset that were checked against something
    outside the engine: the real, signed-in official builder UI, screenshotted
    at the 98-to-99 completion edge. Every other golden file was produced by
    probing the game's native library -- the same engine this project
    reimplements -- so those files can confirm internal consistency but not
    that the formula matches what a player actually sees. These two rows are
    the one place that outside check exists, which is worth guarding even
    though it is only two rows.

    NOTE on `availability_rounded`: this field is the output of a THIRD,
    separate routine -- upgrade-availability rounding -- that this project
    does not model and is not in scope for the pricing engine. Do not assert
    against it, and do not be tempted to "fix" ovr.detailed()/ovr.overall() to
    make them match it. Row 2 makes the distinction concrete:
    availability_rounded is 99.0, but the official UI's own displayed overall
    was still 98, and our ovr.detailed() gives 98.995412 -- neither integer
    99 nor 98.995412 is "wrong" here; they are three different, legitimate
    routines. floor(ovr.detailed(...)) == 98 is what actually reproduces the
    number the UI showed, which is the only claim this test makes.
    """

    def test_dataset_has_exactly_two_rows(self):
        # A future data refresh that adds more UI-verified rows should be
        # noticed (and covered) rather than silently under-tested.
        self.assertEqual(len(official_ui_rows()), 2)

    def test_rows_differ_only_at_standing_dunk(self):
        rows = official_ui_rows()
        row_a, row_b = rows[0], rows[1]

        self.assertEqual(row_a["values"][STANDING_DUNK_INDEX], row_a["standing_dunk"])
        self.assertEqual(row_b["values"][STANDING_DUNK_INDEX], row_b["standing_dunk"])

        diff_indexes = [
            i
            for i, (a, b) in enumerate(zip(row_a["values"], row_b["values"]))
            if a != b
        ]
        self.assertEqual(diff_indexes, [STANDING_DUNK_INDEX])

    def test_overall_and_archetype_match_the_official_ui(self):
        for row in official_ui_rows():
            with self.subTest(standing_dunk=row["standing_dunk"]):
                self.assertEqual(
                    ovr.overall(REFERENCE_HEIGHT, row["values"]), row["overall"]
                )
                self.assertEqual(
                    ovr.archetype(REFERENCE_HEIGHT, row["values"]), row["player_type"]
                )


if __name__ == "__main__":
    unittest.main()
