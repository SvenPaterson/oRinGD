"""
ISO 23936-2 O-Ring Crack Rating Test Suite
==========================================
This module provides comprehensive testing for the crack rating system
according to ISO 23936-2 Annex B, Table B.4.

Key Issues Found in Original Code:
1. Rating logic doesn't follow the ISO standard's hierarchical evaluation
2. Missing proper handling of "no splits permitted" in ratings 1-4
3. Incorrect threshold comparisons for internal crack counts
4. Rating evaluation should be sequential, not independent
"""

import unittest
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum


class CrackType(Enum):
    INTERNAL = "Internal"  # Both ends inside perimeter
    EXTERNAL = "External"  # One end on perimeter
    SPLIT = "Split"        # Both ends on perimeter (crossing completely)


@dataclass
class Crack:
    type: CrackType
    length_percent_csd: float  # Length as percentage of CSD
    
    
@dataclass
class RatingCriteria:
    """Represents the criteria for a specific rating level"""
    rating: int
    total_crack_length_max: Optional[float]  # Max total length as % of CSD
    external_cracks_max_percent: Optional[float]  # Max % for each external crack
    internal_cracks_50_80_max_count: Optional[int]  # Max count of internal cracks 50-80%
    internal_cracks_above_80_min_count: Optional[int]  # Min count for failure
    internal_cracks_above_50_min_count: Optional[int]  # Min count for failure
    splits_allowed: bool
    
    
class ISO23936_2_RatingSystem:
    """
    Correct implementation of ISO 23936-2 Table B.4 rating system.
    
    CRITICAL FIXES from original code:
    1. Splits (Rating 5) are evaluated FIRST - any split = automatic failure
    2. Rating evaluation is hierarchical, not independent
    3. "No splits permitted" is enforced for ratings 0-4
    4. External crack thresholds are properly evaluated
    """
    
    @staticmethod
    def calculate_rating(cracks: List[Crack]) -> Tuple[int, str]:
        """
        Calculate the damage rating according to ISO 23936-2 Table B.4
        
        Returns:
            Tuple of (rating: int, pass_fail: str)
            rating: 0-5 where 0-3 = PASS, 4-5 = FAIL
            pass_fail: "PASS" or "FAIL"
        """
        
        # Rating 0: No cracks at all
        if not cracks:
            return 0, "PASS"
        
        # Rating 5: Any split present (must check first!)
        has_split = any(c.type == CrackType.SPLIT for c in cracks)
        if has_split:
            return 5, "FAIL"
        
        # Calculate metrics
        total_length = sum(c.length_percent_csd for c in cracks)
        external_cracks = [c for c in cracks if c.type == CrackType.EXTERNAL]
        internal_cracks = [c for c in cracks if c.type == CrackType.INTERNAL]
        
        # Count internal cracks in different ranges
        internal_50_80_count = sum(1 for c in internal_cracks 
                                  if 50 <= c.length_percent_csd <= 80)
        internal_above_80_count = sum(1 for c in internal_cracks 
                                     if c.length_percent_csd > 80)
        internal_above_50_count = sum(1 for c in internal_cracks 
                                     if c.length_percent_csd > 50)
        
        # Check Rating 1 conditions
        if (total_length <= 100 and 
            all(c.length_percent_csd < 25 for c in cracks) and
            all(c.length_percent_csd < 10 for c in external_cracks)):
            return 1, "PASS"
        
        # Check Rating 4 conditions (before ratings 2 and 3)
        # This is crucial: Rating 4 triggers if ANY of these conditions are met
        if (total_length > 300 or
            internal_above_80_count >= 1 or
            internal_above_50_count >= 3 or
            any(c.length_percent_csd > 50 for c in external_cracks)):
            return 4, "FAIL"
        
        # Check Rating 2 conditions
        if (total_length <= 200 and
            all(c.length_percent_csd < 50 for c in cracks) and
            all(c.length_percent_csd < 25 for c in external_cracks)):
            return 2, "PASS"
        
        # Check Rating 3 conditions
        if (total_length <= 300 and
            internal_50_80_count <= 2 and
            all(c.length_percent_csd < 50 for c in external_cracks)):
            return 3, "PASS"
        
        # Default to Rating 4 if no other conditions met
        return 4, "FAIL"


class TestISO23936_2_Rating(unittest.TestCase):
    """Comprehensive test cases for ISO 23936-2 rating system"""
    
    def setUp(self):
        self.rating_system = ISO23936_2_RatingSystem()
    
    # ============= Rating 0 Tests =============
    def test_rating_0_no_cracks(self):
        """No cracks should give Rating 0"""
        rating, result = self.rating_system.calculate_rating([])
        self.assertEqual(rating, 0)
        self.assertEqual(result, "PASS")
    
    # ============= Rating 1 Tests =============
    def test_rating_1_single_small_internal(self):
        """Single small internal crack < 25% CSD"""
        cracks = [Crack(CrackType.INTERNAL, 20)]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 1)
        self.assertEqual(result, "PASS")
    
    def test_rating_1_multiple_small_cracks(self):
        """Multiple cracks totaling < 100% CSD, all < 25%"""
        cracks = [
            Crack(CrackType.INTERNAL, 24),
            Crack(CrackType.INTERNAL, 20),
            Crack(CrackType.EXTERNAL, 9)  # External must be < 10%
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 1)
        self.assertEqual(result, "PASS")
    
    def test_rating_1_fail_external_above_10(self):
        """Should not be Rating 1 if external crack >= 10%"""
        cracks = [
            Crack(CrackType.INTERNAL, 20),
            Crack(CrackType.EXTERNAL, 10)  # Exactly 10% fails Rating 1
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertNotEqual(rating, 1)
    
    # ============= Rating 2 Tests =============
    def test_rating_2_valid(self):
        """Valid Rating 2: total <= 200%, all < 50%, external < 25%"""
        cracks = [
            Crack(CrackType.INTERNAL, 45),
            Crack(CrackType.INTERNAL, 40),
            Crack(CrackType.EXTERNAL, 24)
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 2)
        self.assertEqual(result, "PASS")
    
    def test_rating_2_fail_total_above_200(self):
        """Should not be Rating 2 if total > 200%"""
        cracks = [
            Crack(CrackType.INTERNAL, 49),
            Crack(CrackType.INTERNAL, 49),
            Crack(CrackType.INTERNAL, 49),
            Crack(CrackType.INTERNAL, 49),
            Crack(CrackType.EXTERNAL, 24)
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertNotEqual(rating, 2)
    
    # ============= Rating 3 Tests =============
    def test_rating_3_valid_with_large_internals(self):
        """Rating 3: Can have 2 internal cracks 50-80%"""
        cracks = [
            Crack(CrackType.INTERNAL, 75),  # 50-80% range
            Crack(CrackType.INTERNAL, 60),  # 50-80% range
            Crack(CrackType.EXTERNAL, 45)   # External < 50%
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 3)
        self.assertEqual(result, "PASS")
    
    def test_rating_3_fail_three_internals_50_80(self):
        """Should fail Rating 3 with 3 internal cracks 50-80%"""
        cracks = [
            Crack(CrackType.INTERNAL, 75),
            Crack(CrackType.INTERNAL, 60),
            Crack(CrackType.INTERNAL, 55),  # Third one in 50-80% range
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 4)  # Should be Rating 4
        self.assertEqual(result, "FAIL")
    
    # ============= Rating 4 Tests =============
    def test_rating_4_total_above_300(self):
        """Rating 4: Total crack length > 300%"""
        cracks = [
            Crack(CrackType.INTERNAL, 150),
            Crack(CrackType.INTERNAL, 151)
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 4)
        self.assertEqual(result, "FAIL")
    
    def test_rating_4_one_internal_above_80(self):
        """Rating 4: At least 1 internal crack > 80%"""
        cracks = [
            Crack(CrackType.INTERNAL, 81),
            Crack(CrackType.INTERNAL, 20)
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 4)
        self.assertEqual(result, "FAIL")
    
    def test_rating_4_three_internals_above_50(self):
        """Rating 4: 3 or more internal cracks > 50%"""
        cracks = [
            Crack(CrackType.INTERNAL, 51),
            Crack(CrackType.INTERNAL, 52),
            Crack(CrackType.INTERNAL, 53)
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 4)
        self.assertEqual(result, "FAIL")
    
    def test_rating_4_external_above_50(self):
        """Rating 4: Any external crack > 50%"""
        cracks = [
            Crack(CrackType.INTERNAL, 30),
            Crack(CrackType.EXTERNAL, 51)
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 4)
        self.assertEqual(result, "FAIL")
    
    # ============= Rating 5 Tests =============
    def test_rating_5_single_split(self):
        """Rating 5: Any split present"""
        cracks = [Crack(CrackType.SPLIT, 10)]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 5)
        self.assertEqual(result, "FAIL")
    
    def test_rating_5_split_overrides_all(self):
        """Split should give Rating 5 regardless of other conditions"""
        cracks = [
            Crack(CrackType.INTERNAL, 5),  # Would qualify for Rating 1
            Crack(CrackType.SPLIT, 5)      # But split forces Rating 5
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 5)
        self.assertEqual(result, "FAIL")
    
    # ============= Edge Cases =============
    def test_edge_case_exactly_100_percent(self):
        """Edge case: Total exactly 100% should be Rating 1 if conditions met"""
        cracks = [
            Crack(CrackType.INTERNAL, 24),
            Crack(CrackType.INTERNAL, 24),
            Crack(CrackType.INTERNAL, 24),
            Crack(CrackType.INTERNAL, 24),
            Crack(CrackType.EXTERNAL, 4)
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 1)
        self.assertEqual(result, "PASS")
    
    def test_edge_case_internal_exactly_80(self):
        """Edge case: Internal crack exactly 80% is in 50-80 range"""
        cracks = [
            Crack(CrackType.INTERNAL, 80),
            Crack(CrackType.INTERNAL, 80)
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        self.assertEqual(rating, 3)  # 2 internals at 80%, total 160%
        self.assertEqual(result, "PASS")
    
    def test_edge_case_internal_exactly_50(self):
        """Edge case: Internal crack exactly 50% counts for both ranges"""
        cracks = [
            Crack(CrackType.INTERNAL, 50),
            Crack(CrackType.INTERNAL, 50),
            Crack(CrackType.INTERNAL, 50)
        ]
        rating, result = self.rating_system.calculate_rating(cracks)
        # 3 internals > 50% triggers Rating 4
        self.assertEqual(rating, 4)
        self.assertEqual(result, "FAIL")


def generate_test_report():
    """Generate a detailed test report showing all test results"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestISO23936_2_Rating)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("ISO 23936-2 RATING SYSTEM TEST SUMMARY")
    print("="*60)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success Rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILED TESTS:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    return result


if __name__ == "__main__":
    # Run the comprehensive test suite
    generate_test_report()