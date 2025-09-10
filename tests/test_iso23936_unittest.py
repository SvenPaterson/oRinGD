"""
tests/test_iso23936_unittest.py
======================
Consolidated test suite for oRinGD project (ISO 23936-2)
"""

import sys
from pathlib import Path
import unittest

# Ensure project root (where rating.py lives) is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rating import compute_metrics, assign_iso23936_rating, table_values


class TestISO23936Rating(unittest.TestCase):
    """Core rating logic tests"""

    def test_canonical_cases(self):
        """Standard ISO 23936-2 scenarios (R0–R5)"""
        cases = [
            ("R0_No_Cracks", [], 0),

            ("R1_Small_Internal", [("Internal", 20.0)], 1),
            ("R1_Multiple_Small",
             [("Internal", 24.0), ("Internal", 24.0), ("External", 9.0)], 1),
            ("R1_Edge_100_Percent",
             [("Internal", 24.0), ("Internal", 24.0), ("Internal", 24.0),
              ("Internal", 24.0), ("External", 4.0)], 1),

            ("R2_Medium_Cracks",
             [("Internal", 45.0), ("Internal", 40.0), ("External", 24.0)], 2),
            ("R2_Near_Limit",
             [("Internal", 49.0), ("Internal", 49.0),
              ("Internal", 49.0), ("Internal", 49.0)], 2),

            ("R3_Two_Large_Internals",
             [("Internal", 75.0), ("Internal", 60.0), ("External", 45.0)], 3),
            ("R3_Edge_80_Percent",
             [("Internal", 80.0), ("Internal", 80.0)], 3),

            ("R4_Total_Above_300",
             [("Internal", 151.0), ("Internal", 150.0)], 4),
            ("R4_One_Above_80",
             [("Internal", 81.0), ("Internal", 20.0)], 4),
            ("R4_Three_Above_50",
             [("Internal", 51.0), ("Internal", 52.0), ("Internal", 53.0)], 4),
            ("R4_External_Above_50",
             [("Internal", 30.0), ("External", 51.0)], 4),

            ("R5_Single_Split", [("Split", 10.0)], 5),
            ("R5_Split_Override", [("Internal", 5.0), ("Split", 5.0)], 5),
        ]
        for name, cracks, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(
                    assign_iso23936_rating(cracks), expected,
                    f"{name}: expected {expected}"
                )

    def test_boundary_conditions(self):
        """Boundaries at 10/25/50/300 with correct strict/≤ logic"""

        # Exactly 25%: fails Rating 1 (<25), becomes Rating 2 if total≤200 and externals<25
        self.assertEqual(
            assign_iso23936_rating([("Internal", 25.0)]),
            2,
            "Internal at 25% should be Rating 2 (not Rating 1)"
        )

        # Exactly 50% internal: fails Rating 2 (<50); Rating 3 passes other checks => Rating 3
        self.assertEqual(
            assign_iso23936_rating([("Internal", 50.0)]),
            3,
            "Internal at 50% should be Rating 3 (fails R2, meets R3)"
        )

        # External 10%: fails Rating 1 (<10); should meet Rating 2
        self.assertEqual(
            assign_iso23936_rating([("Internal", 20.0), ("External", 10.0)]),
            2,
            "External at 10% should fail R1 and pass R2"
        )

        # Three internals at exactly 50%: not a 4-trigger (needs >50), but fails R2 & R3 → default 4
        self.assertEqual(
            assign_iso23936_rating([("Internal", 50.0)] * 3),
            4,
            "Three internals at 50% default to Rating 4 (no pass conditions met)"
        )

    def test_metrics_calculation(self):
        """Metrics integrity"""
        cracks = [("Internal", 75.0), ("External", 25.0), ("Internal", 30.0)]
        m = compute_metrics(cracks)

        self.assertEqual(m.num_cracks, 3)
        self.assertAlmostEqual(m.total_pct, 130.0)
        self.assertEqual(len(m.internal_pct), 2)
        self.assertEqual(len(m.external_pct), 1)
        self.assertFalse(m.has_split)
        self.assertEqual(m.internal_50_80_count, 1)   # 75 only
        self.assertEqual(m.internal_above_80, 0)
        self.assertEqual(m.internal_above_50, 1)      # 75 only
        self.assertFalse(m.has_three_internal_above_50)

    def test_table_values_output(self):
        """table_values formatting and ordering"""
        cracks = [("Internal", 54.26)]
        m = compute_metrics(cracks)
        values = table_values(m)

        self.assertEqual(len(values), 10)
        self.assertEqual(values[0], "54.26%")  # total
        self.assertEqual(values[1], "0")       # # <25
        self.assertEqual(values[2], "Yes")     # externals <10 (no externals)
        self.assertEqual(values[3], "0")       # # <50
        self.assertEqual(values[4], "Yes")     # externals <25 (no externals)
        self.assertEqual(values[5], "1")       # internal 50–80 count
        self.assertEqual(values[6], "Yes")     # externals <50 (no externals)
        self.assertEqual(values[7], "No")      # internal >80
        self.assertEqual(values[8], "No")      # ≥3 internals >50
        self.assertEqual(values[9], "No")      # splits

    def test_additional_edges(self):
        """Extra edges and realistic mixes"""

        # True Rating 3 at exactly 300%:
        # two internals in 50–80, others <50, no externals ≥50
        self.assertEqual(
            assign_iso23936_rating([
                ("Internal", 80.0), ("Internal", 70.0),   # 2 in 50–80
                ("Internal", 40.0), ("Internal", 40.0),
                ("Internal", 40.0), ("Internal", 30.0)    # totals 300%
            ]),
            3,
            "Valid Rating 3 at total=300% with ≤2 internals in 50–80"
        )

        # External exactly 25% → fails R2 (<25) but can be R3
        self.assertEqual(
            assign_iso23936_rating([("External", 25.0), ("Internal", 40.0)]),
            3,
            "External at 25% should fail R2 and pass R3"
        )

        # External exactly 50% → fails R1/R2/R3; not a 4-trigger (>50) → defaults to 4
        self.assertEqual(
            assign_iso23936_rating([("External", 50.0)]),
            4,
            "External at 50% ends up Rating 4 (no pass conditions met)"
        )

        # High total just over 300 → 4-trigger
        self.assertEqual(
            assign_iso23936_rating([("Internal", 100.01), ("Internal", 100.0), ("Internal", 100.0)]),
            4,
            "Total >300% should trigger Rating 4"
        )

        # Zero-length cracks: total 0, all <25, externals <10 → Rating 1
        self.assertEqual(
            assign_iso23936_rating([("Internal", 0.0), ("External", 0.0)]),
            1,
            "Zero-length cracks should be treated as Rating 1"
        )

        # Split always overrides → Rating 5
        self.assertEqual(
            assign_iso23936_rating([("Split", 1.0), ("Internal", 99.0)]),
            5,
            "Split overrides all other conditions"
        )


def run_all_tests(verbose=True):
    """Run all tests and return the unittest result object."""
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestISO23936Rating)
    runner = unittest.TextTestRunner(verbosity=(2 if verbose else 1))
    return runner.run(suite)


if __name__ == "__main__":
    result = run_all_tests()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed - see details above")
        sys.exit(1)