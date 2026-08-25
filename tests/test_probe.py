"""Smoke tests for tools/probe.py.

The harness is the safety net for a future upstream data refresh, so it has to
keep working even while nobody is using it. These tests exercise every helper
it owns -- `_scales`, `_pg_pricing`, `_price_cap_multipliers` and the
`scale_floor` closure -- and assert the rates it reports, so a refactor of
tables.py or archetypes.py that breaks the harness fails here rather than
halfway through someone's investigation.
"""

import contextlib
import io
import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import probe  # noqa: E402

from buildlab import tables  # noqa: E402


def rates(kernel):
    """(archetype hits, detailed hits) for a kernel, with the printing muted."""
    with contextlib.redirect_stdout(io.StringIO()):
        return probe.report("", probe.argmax(kernel), kernel)


class TestHarnessLoads(unittest.TestCase):
    def test_golden_files_load(self):
        self.assertEqual(len(probe.golden()), 256)
        self.assertEqual(len(probe.uniform()), 75)

    def test_main_runs_end_to_end(self):
        # Catches an exception in any ladder helper, not just the shipped one.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            probe.main()
        out = buffer.getvalue()
        self.assertIn("rating-scaled, renormalised", out)
        self.assertIn("buildlab.ovr cross-checks", out)


class TestHarnessHelpers(unittest.TestCase):
    def test_scales_are_one_below_the_table_floor(self):
        self.assertEqual(probe._scales([74] * 21), [1.0] * 21)
        # At 99 every attribute is boosted except free throw, which ships 25
        # explicit rows that are all 1.0 -- see test_free_throw_is_exempt.
        boosted = [s for s in probe._scales([99] * 21) if s > 1.0]
        self.assertEqual(len(boosted), 20)

    def test_free_throw_is_exempt_from_the_rating_scale(self):
        # ShotFreeThrow is the only builder attribute whose scale rows are all
        # present and all 1.0, so a high free throw never pulls the weighted
        # average toward itself. Stamina is likewise flat but is not one of the
        # 21 builder attributes.
        for rating in range(75, 100):
            self.assertEqual(tables.scale_for("ShotFreeThrow", rating), 1.0)

    def test_pg_pricing_defaults_to_one(self):
        pricing = probe._pg_pricing()
        self.assertEqual(len(pricing), 21)
        # 8 attributes carry an explicit key, but two of those (ShotMidrange,
        # ShotThree) are set to 1.0, so only 6 actually differ.
        self.assertEqual(sum(1 for p in pricing if p != 1.0), 6)

    def test_price_cap_multipliers_cover_every_attribute(self):
        mult = probe._price_cap_multipliers([50] * 21)
        self.assertEqual(len(mult), 21)
        self.assertTrue(all(0.0 < m <= 1.0 for m in mult))

    def test_scale_floor_closure_reduces_to_the_winner_at_75(self):
        # The scale table has no entries below 75, so a floor of 75 and the
        # shipped kernel must agree exactly.
        kernel = probe.scale_floor(75)
        for row in probe.golden()[:20]:
            self.assertAlmostEqual(
                kernel(11, row["player_type"], row["values"]),
                probe.scaled_renorm(11, row["player_type"], row["values"]),
                places=12,
            )


class TestHarnessReportsTheShippedResult(unittest.TestCase):
    def test_shipped_kernel_is_exact(self):
        with contextlib.redirect_stdout(io.StringIO()):
            hits = probe.report("", probe.shipped_select, probe.shipped_score)
        self.assertEqual(hits, (256, 256))

    def test_uncapped_curve_is_exact_before_the_cap(self):
        self.assertEqual(rates(probe.scaled_renorm), (256, 255))

    def test_baseline_ladder_rungs_are_unchanged(self):
        # These are the recorded failures. If any moves, the notes are stale.
        self.assertEqual(rates(probe.plain), (207, 0))
        self.assertEqual(rates(probe.scaled_over_100), (201, 0))
        self.assertEqual(rates(probe.plain_renorm), (205, 0))
        self.assertEqual(rates(probe.pricing_no_scale), (192, 0))
        self.assertEqual(rates(probe.pricing_scaled), (215, 0))
        self.assertEqual(rates(probe.price_cap_scaled), (231, 0))
        self.assertEqual(rates(probe.scale_floor(80)), (256, 103))
        self.assertEqual(rates(probe.scale_floor(85)), (253, 35))


if __name__ == "__main__":
    unittest.main()
