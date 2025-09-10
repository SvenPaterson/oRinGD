"""
Validation and Debugging Tools for ISO 23936-2 O-Ring Analysis
==============================================================
This module provides tools to validate your implementation against
the ISO standard and debug rating assignments.
"""

import json
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass, asdict
import math


@dataclass
class TestScenario:
    """Represents a test scenario with expected outcome"""
    name: str
    description: str
    cracks: List[Dict[str, Any]]  # List of {'type': 'Internal/External/Split', 'length_percent': float}
    expected_rating: int
    expected_result: str  # 'PASS' or 'FAIL'
    rationale: str


class ISO23936_2_Validator:
    """
    Validation tool for testing the O-ring crack rating implementation
    """
    
    @staticmethod
    def generate_test_scenarios() -> List[TestScenario]:
        """Generate comprehensive test scenarios based on ISO 23936-2 Table B.4"""
        
        scenarios = [
            # Rating 0 scenarios
            TestScenario(
                name="R0_No_Cracks",
                description="No cracks present",
                cracks=[],
                expected_rating=0,
                expected_result="PASS",
                rationale="No cracks = Rating 0 (intact seal)"
            ),
            
            # Rating 1 scenarios
            TestScenario(
                name="R1_Small_Internal",
                description="Single small internal crack",
                cracks=[{'type': 'Internal', 'length_percent': 20}],
                expected_rating=1,
                expected_result="PASS",
                rationale="Total 20% < 100%, all cracks < 25%, no external cracks"
            ),
            TestScenario(
                name="R1_Multiple_Small",
                description="Multiple small cracks with small external",
                cracks=[
                    {'type': 'Internal', 'length_percent': 24},
                    {'type': 'Internal', 'length_percent': 24},
                    {'type': 'External', 'length_percent': 9}
                ],
                expected_rating=1,
                expected_result="PASS",
                rationale="Total 57% < 100%, all < 25%, external < 10%"
            ),
            TestScenario(
                name="R1_Edge_100_Percent",
                description="Total exactly 100% CSD",
                cracks=[
                    {'type': 'Internal', 'length_percent': 24},
                    {'type': 'Internal', 'length_percent': 24},
                    {'type': 'Internal', 'length_percent': 24},
                    {'type': 'Internal', 'length_percent': 24},
                    {'type': 'External', 'length_percent': 4}
                ],
                expected_rating=1,
                expected_result="PASS",
                rationale="Total exactly 100%, all < 25%, external < 10%"
            ),
            
            # Rating 2 scenarios
            TestScenario(
                name="R2_Medium_Cracks",
                description="Medium cracks under 50%",
                cracks=[
                    {'type': 'Internal', 'length_percent': 45},
                    {'type': 'Internal', 'length_percent': 40},
                    {'type': 'External', 'length_percent': 24}
                ],
                expected_rating=2,
                expected_result="PASS",
                rationale="Total 109% < 200%, all < 50%, external < 25%"
            ),
            TestScenario(
                name="R2_Near_Limit",
                description="Near 200% limit",
                cracks=[
                    {'type': 'Internal', 'length_percent': 49},
                    {'type': 'Internal', 'length_percent': 49},
                    {'type': 'Internal', 'length_percent': 49},
                    {'type': 'Internal', 'length_percent': 49}
                ],
                expected_rating=2,
                expected_result="PASS",
                rationale="Total 196% < 200%, all < 50%"
            ),
            
            # Rating 3 scenarios
            TestScenario(
                name="R3_Two_Large_Internals",
                description="Two internal cracks 50-80%",
                cracks=[
                    {'type': 'Internal', 'length_percent': 75},
                    {'type': 'Internal', 'length_percent': 60},
                    {'type': 'External', 'length_percent': 45}
                ],
                expected_rating=3,
                expected_result="PASS",
                rationale="Total 180% < 300%, 2 internals 50-80%, external < 50%"
            ),
            TestScenario(
                name="R3_Edge_80_Percent",
                description="Internal cracks at exactly 80%",
                cracks=[
                    {'type': 'Internal', 'length_percent': 80},
                    {'type': 'Internal', 'length_percent': 80}
                ],
                expected_rating=3,
                expected_result="PASS",
                rationale="Total 160% < 300%, 2 internals at 80% (within 50-80%)"
            ),
            TestScenario(
                name="R3_Mixed_Sizes",
                description="Mixed crack sizes within Rating 3 limits",
                cracks=[
                    {'type': 'Internal', 'length_percent': 70},
                    {'type': 'Internal', 'length_percent': 30},
                    {'type': 'Internal', 'length_percent': 20},
                    {'type': 'External', 'length_percent': 40}
                ],
                expected_rating=3,
                expected_result="PASS",
                rationale="Total 160% < 300%, only 1 internal 50-80%, external < 50%"
            ),
            
            # Rating 4 scenarios
            TestScenario(
                name="R4_Total_Above_300",
                description="Total crack length > 300%",
                cracks=[
                    {'type': 'Internal', 'length_percent': 151},
                    {'type': 'Internal', 'length_percent': 150}
                ],
                expected_rating=4,
                expected_result="FAIL",
                rationale="Total 301% > 300% triggers Rating 4"
            ),
            TestScenario(
                name="R4_One_Above_80",
                description="One internal crack > 80%",
                cracks=[
                    {'type': 'Internal', 'length_percent': 81},
                    {'type': 'Internal', 'length_percent': 20}
                ],
                expected_rating=4,
                expected_result="FAIL",
                rationale="At least 1 internal > 80% triggers Rating 4"
            ),
            TestScenario(
                name="R4_Three_Above_50",
                description="Three internal cracks > 50%",
                cracks=[
                    {'type': 'Internal', 'length_percent': 51},
                    {'type': 'Internal', 'length_percent': 52},
                    {'type': 'Internal', 'length_percent': 53}
                ],
                expected_rating=4,
                expected_result="FAIL",
                rationale="3 or more internals > 50% triggers Rating 4"
            ),
            TestScenario(
                name="R4_External_Above_50",
                description="External crack > 50%",
                cracks=[
                    {'type': 'Internal', 'length_percent': 30},
                    {'type': 'External', 'length_percent': 51}
                ],
                expected_rating=4,
                expected_result="FAIL",
                rationale="Any external > 50% triggers Rating 4"
            ),
            TestScenario(
                name="R4_Three_Internals_50_80",
                description="Three internal cracks in 50-80% range",
                cracks=[
                    {'type': 'Internal', 'length_percent': 75},
                    {'type': 'Internal', 'length_percent': 60},
                    {'type': 'Internal', 'length_percent': 55}
                ],
                expected_rating=4,
                expected_result="FAIL",
                rationale="More than 2 internals 50-80% AND all 3 are > 50%"
            ),
            
            # Rating 5 scenarios
            TestScenario(
                name="R5_Single_Split",
                description="Single split crack",
                cracks=[{'type': 'Split', 'length_percent': 10}],
                expected_rating=5,
                expected_result="FAIL",
                rationale="Any split = automatic Rating 5"
            ),
            TestScenario(
                name="R5_Split_Override",
                description="Split overrides other good conditions",
                cracks=[
                    {'type': 'Internal', 'length_percent': 5},
                    {'type': 'Split', 'length_percent': 5}
                ],
                expected_rating=5,
                expected_result="FAIL",
                rationale="Split present overrides all other conditions"
            ),
            
            # Edge cases
            TestScenario(
                name="Edge_External_10_Percent",
                description="External at exactly 10% (fails Rating 1)",
                cracks=[
                    {'type': 'Internal', 'length_percent': 20},
                    {'type': 'External', 'length_percent': 10}
                ],
                expected_rating=2,  # Should be Rating 2, not 1
                expected_result="PASS",
                rationale="External = 10% fails Rating 1 condition (must be < 10%)"
            ),
            TestScenario(
                name="Edge_Internal_50_Percent",
                description="Exactly at 50% threshold",
                cracks=[
                    {'type': 'Internal', 'length_percent': 50},
                    {'type': 'Internal', 'length_percent': 50},
                    {'type': 'Internal', 'length_percent': 50}
                ],
                expected_rating=4,
                expected_result="FAIL",
                rationale="3 internals at exactly 50% triggers Rating 4 (≥3 > 50%)"
            ),
        ]
        
        return scenarios
    
    @staticmethod
    def create_manual_test_file(filename: str = "iso_23936_2_test_cases.json"):
        """
        Create a JSON file with test cases for manual validation
        """
        scenarios = ISO23936_2_Validator.generate_test_scenarios()
        
        # Convert to JSON-serializable format
        test_data = {
            "test_suite": "ISO 23936-2 Annex B Rating System",
            "version": "1.0",
            "test_cases": [
                {
                    "id": i + 1,
                    "name": s.name,
                    "description": s.description,
                    "cracks": s.cracks,
                    "expected_rating": s.expected_rating,
                    "expected_result": s.expected_result,
                    "rationale": s.rationale
                }
                for i, s in enumerate(scenarios)
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        print(f"Test file created: {filename}")
        print(f"Total test cases: {len(scenarios)}")
        return filename
    
    @staticmethod
    def validate_single_case(cracks: List[Tuple[str, float]], 
                           expected_rating: int,
                           actual_rating: int) -> Dict[str, Any]:
        """
        Validate a single test case
        
        Args:
            cracks: List of (type, length_percent) tuples
            expected_rating: Expected rating from ISO standard
            actual_rating: Rating produced by implementation
        
        Returns:
            Dictionary with validation results
        """
        passed = expected_rating == actual_rating
        
        result = {
            "passed": passed,
            "expected_rating": expected_rating,
            "actual_rating": actual_rating,
            "cracks": cracks,
        }
        
        if not passed:
            # Provide diagnostic information
            total_length = sum(length for _, length in cracks)
            has_split = any(crack_type == 'Split' for crack_type, _ in cracks)
            internal_cracks = [l for t, l in cracks if t == 'Internal']
            external_cracks = [l for t, l in cracks if t == 'External']
            
            result["diagnostics"] = {
                "total_length_percent": total_length,
                "has_split": has_split,
                "internal_count": len(internal_cracks),
                "external_count": len(external_cracks),
                "internal_above_80": sum(1 for l in internal_cracks if l > 80),
                "internal_above_50": sum(1 for l in internal_cracks if l > 50),
                "internal_50_80": sum(1 for l in internal_cracks if 50 <= l <= 80),
                "external_above_50": any(l > 50 for l in external_cracks),
                "external_above_25": any(l >= 25 for l in external_cracks),
                "external_above_10": any(l >= 10 for l in external_cracks),
            }
        
        return result


class MockCanvasForTesting:
    """
    Mock Canvas class for testing the rating logic without PyQt dependencies
    """
    
    def __init__(self):
        self.perimeter_length = 100 * math.pi  # Standard CSD = 100
        self.cracks = []  # Will be populated with test data
    
    def add_crack(self, crack_type: str, length_percent: float):
        """Add a crack for testing"""
        # Map crack types to Qt colors (simulating your actual implementation)
        color_map = {
            'Internal': 'blue',
            'External': 'yellow', 
            'Split': 'red'
        }
        
        # Convert percentage to actual length
        csd = self.perimeter_length / math.pi
        actual_length = (length_percent / 100) * csd
        
        # Create mock crack points (simplified - just two points)
        crack_points = [(0, 0), (actual_length, 0)]
        
        self.cracks.append((crack_points, color_map[crack_type]))
    
    def calculate_rating(self) -> Tuple[int, str]:
        """
        Calculate rating using the corrected logic
        This should match your corrected update_rating_table logic
        """
        if not self.cracks:
            return 0, "PASS"
        
        csd = self.perimeter_length / math.pi
        
        # Process cracks
        total_length_percent = 0
        internal_lengths = []
        external_lengths = []
        has_split = False
        
        for crack_points, color in self.cracks:
            # Calculate crack length (simplified for mock)
            length = abs(crack_points[1][0] - crack_points[0][0])
            length_percent = (length / csd) * 100
            total_length_percent += length_percent
            
            if color == 'red':
                has_split = True
            elif color == 'blue':
                internal_lengths.append(length_percent)
            elif color == 'yellow':
                external_lengths.append(length_percent)
        
        # Apply corrected rating logic
        if has_split:
            return 5, "FAIL"
        
        # Check Rating 1
        if (total_length_percent <= 100 and
            all(l < 25 for l in internal_lengths + external_lengths) and
            all(l < 10 for l in external_lengths)):
            return 1, "PASS"
        
        # Check Rating 4 (before 2 and 3!)
        internal_above_80 = sum(1 for l in internal_lengths if l > 80)
        internal_above_50 = sum(1 for l in internal_lengths if l > 50)
        any_external_above_50 = any(l > 50 for l in external_lengths) if external_lengths else False
        
        if (total_length_percent > 300 or
            internal_above_80 >= 1 or
            internal_above_50 >= 3 or
            any_external_above_50):
            return 4, "FAIL"
        
        # Check Rating 2
        if (total_length_percent <= 200 and
            all(l < 50 for l in internal_lengths + external_lengths) and
            all(l < 25 for l in external_lengths)):
            return 2, "PASS"
        
        # Check Rating 3
        internal_50_80 = sum(1 for l in internal_lengths if 50 <= l <= 80)
        if (total_length_percent <= 300 and
            internal_50_80 <= 2 and
            all(l < 50 for l in external_lengths)):
            return 3, "PASS"
        
        return 4, "FAIL"


def run_validation_suite():
    """
    Run the complete validation suite
    """
    print("ISO 23936-2 VALIDATION SUITE")
    print("=" * 60)
    
    validator = ISO23936_2_Validator()
    scenarios = validator.generate_test_scenarios()
    
    passed = 0
    failed = 0
    failures = []
    
    for scenario in scenarios:
        # Create mock canvas
        canvas = MockCanvasForTesting()
        
        # Add cracks from scenario
        for crack in scenario.cracks:
            canvas.add_crack(crack['type'], crack['length_percent'])
        
        # Calculate rating
        actual_rating, actual_result = canvas.calculate_rating()
        
        # Validate
        if actual_rating == scenario.expected_rating and actual_result == scenario.expected_result:
            passed += 1
            print(f"✓ {scenario.name}: PASSED")
        else:
            failed += 1
            print(f"✗ {scenario.name}: FAILED")
            print(f"  Expected: Rating {scenario.expected_rating} ({scenario.expected_result})")
            print(f"  Got: Rating {actual_rating} ({actual_result})")
            print(f"  Rationale: {scenario.rationale}")
            failures.append(scenario.name)
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(scenarios)} tests")
    
    if failures:
        print("\nFailed tests:")
        for name in failures:
            print(f"  - {name}")
    
    # Create test file for manual validation
    validator.create_manual_test_file()
    
    return passed, failed


if __name__ == "__main__":
    run_validation_suite()