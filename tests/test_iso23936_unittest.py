# tests_iso23936_unittest.py
import unittest
from rating import assign_iso23936_rating

class TestISO23936(unittest.TestCase):
    def test_canonical_cases(self):
        cases = [
            ("R0_No_Cracks", [], 0),
            ("R1_Small_Internal", [("Internal", 20.0)], 1),
            ("R1_Multiple_Small",
             [("Internal", 24.0), ("Internal", 24.0), ("External", 9.0)], 1),
            ("R2_Medium_Cracks",
             [("Internal", 45.0), ("Internal", 40.0), ("External", 24.0)], 2),
            ("R3_Two_Large_Internals",
             [("Internal", 75.0), ("Internal", 60.0), ("External", 45.0)], 3),
            ("R4_Total_Above_300", [("Internal", 151.0), ("Internal", 150.0)], 4),
            ("R4_Three_Above_50",
             [("Internal", 51.0), ("Internal", 52.0), ("Internal", 53.0)], 4),
            ("R5_Single_Split", [("Split", 10.0)], 5),
            ("R5_Split_Override", [("Internal", 5.0), ("Split", 5.0)], 5),
        ]
        for name, cracks, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(assign_iso23936_rating(cracks), expected)

    def test_boundaries(self):
        # Rating 1 boundary: total == 100% AND every crack <25% AND externals <10%
        self.assertEqual(
            assign_iso23936_rating([("Internal", 20.0)] * 5),  # 5 × 20% = 100%, all <25%
            1
        )

        # Rating 2 boundary: total == 200% AND every crack <50% AND externals <25%
        self.assertEqual(
            assign_iso23936_rating([("Internal", 40.0)] * 5),  # 5 × 40% = 200%, all <50%
            2
        )

        # Rating 3 boundary: total == 300%, ≤2 internal cracks in 50–80%, all externals <50%
        # Two internals in 50–80 (80, 70), plus others <50, externals <50
        self.assertEqual(
            assign_iso23936_rating([
                ("Internal", 80.0), ("Internal", 70.0),  # 2 internals in 50–80 bucket
                ("Internal", 49.0), ("Internal", 3.0),
                ("External", 49.0), ("External", 49.0)   # externals <50
            ]), 3
        )

        # Rating 4 triggers (confirm they fire at boundaries)
        self.assertEqual(assign_iso23936_rating([("Internal", 80.01)]), 4)   # internal >80%
        self.assertEqual(assign_iso23936_rating([("External", 50.01)]), 4)   # external >50%
        self.assertEqual(assign_iso23936_rating([("Internal", 151.0), ("Internal", 150.0)]), 4)  # total >300
        self.assertEqual(assign_iso23936_rating([("Internal", 51.0), ("Internal", 52.0), ("Internal", 53.0)]), 4)  # ≥3 internals >50%


if __name__ == "__main__":
    unittest.main(verbosity=2)
