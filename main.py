import sys
import math
import tempfile
import datetime
import os

import numpy as np
from scipy.interpolate import splprep, splev

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QMouseEvent, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QFileDialog,
)

from openpyxl import Workbook
from openpyxl.drawing.image import Image

import sys
import json
from typing import List, Dict, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QTextEdit, QDialog, QVBoxLayout, QPushButton

from rating import compute_metrics, table_values, assign_iso23936_rating

class ValidationHarness:
    """
    Add this class to your existing application file.
    It wraps your Canvas class to enable testing.
    """
    
    def __init__(self, canvas_instance):
        """Initialize with your existing canvas instance"""
        self.canvas = canvas_instance
        self.test_results = []
        
    def run_single_test(self, test_case: Dict) -> Dict:
        """
        Run a single test case on your canvas implementation
        
        Args:
            test_case: Dictionary with 'cracks' list and expected results
        
        Returns:
            Dictionary with test results
        """
        # Clear existing cracks
        original_cracks = self.canvas.cracks.copy()
        self.canvas.cracks = []
        
        # Add test cracks to canvas
        for crack_def in test_case['cracks']:
            crack_type = crack_def['type']
            length_percent = crack_def['length_percent']
            
            # Map type to Qt color (matching your implementation)
            color_map = {
                'Internal': Qt.GlobalColor.blue,
                'External': Qt.GlobalColor.yellow,
                'Split': Qt.GlobalColor.red
            }
            
            # Create mock crack with appropriate length
            # Assuming perimeter_spline exists and has been initialized
            if self.canvas.perimeter_spline:
                csd = self._calculate_csd()
                crack_length_pixels = (length_percent / 100) * csd
                
                # Create a simple two-point crack for testing
                mock_crack = [
                    QPointF(100, 100),  # Start point
                    QPointF(100 + crack_length_pixels, 100)  # End point
                ]
                
                self.canvas.cracks.append((mock_crack, color_map[crack_type]))
        
        # Run your rating calculation
        self.canvas.update_rating_table()
        
        # Extract the assigned rating from your table
        actual_rating = self._extract_rating_from_table()
        
        # Compare with expected
        result = {
            'test_name': test_case.get('name', 'Unknown'),
            'expected_rating': test_case['expected_rating'],
            'actual_rating': actual_rating,
            'passed': actual_rating == test_case['expected_rating'],
            'cracks': test_case['cracks']
        }
        
        # Restore original cracks
        self.canvas.cracks = original_cracks
        self.canvas.update_rating_table()
        
        return result
    
    def _calculate_csd(self) -> float:
        """Calculate CSD from perimeter spline"""
        if not self.canvas.perimeter_spline:
            return 100  # Default value for testing
            
        perimeter_length = sum(
            math.hypot(
                self.canvas.perimeter_spline[i + 1].x() - self.canvas.perimeter_spline[i].x(),
                self.canvas.perimeter_spline[i + 1].y() - self.canvas.perimeter_spline[i].y()
            )
            for i in range(len(self.canvas.perimeter_spline) - 1)
        )
        perimeter_length += math.hypot(
            self.canvas.perimeter_spline[-1].x() - self.canvas.perimeter_spline[0].x(),
            self.canvas.perimeter_spline[-1].y() - self.canvas.perimeter_spline[0].y()
        )
        return perimeter_length / math.pi
    
    def _extract_rating_from_table(self) -> int:
        """Extract the current rating from your rating table"""
        if not self.canvas.rating_table_widget:
            return -1
            
        # Find the overall rating row
        overall_row = 10  # Based on your implementation
        rating_cell = self.canvas.rating_table_widget.item(overall_row, 1)
        
        if rating_cell:
            text = rating_cell.text()
            # Parse "Rating: X - Pass/Fail" format
            if "Rating:" in text:
                rating_str = text.split("Rating:")[1].split("-")[0].strip()
                try:
                    return int(rating_str)
                except ValueError:
                    return -1
        return -1
    
    def run_all_tests(self) -> List[Dict]:
        """Run all ISO 23936-2 test cases"""
        # Load test cases
        test_cases = self.load_test_cases()
        results = []
        
        for test_case in test_cases:
            result = self.run_single_test(test_case)
            results.append(result)
            
        self.test_results = results
        return results
    
    def load_test_cases(self) -> List[Dict]:
        """Load the standard ISO 23936-2 test cases"""
        return [
            {
                'name': 'R0_No_Cracks',
                'cracks': [],
                'expected_rating': 0,
                'expected_result': 'PASS'
            },
            {
                'name': 'R1_Small_Internal',
                'cracks': [{'type': 'Internal', 'length_percent': 20}],
                'expected_rating': 1,
                'expected_result': 'PASS'
            },
            {
                'name': 'R1_Multiple_Small',
                'cracks': [
                    {'type': 'Internal', 'length_percent': 24},
                    {'type': 'Internal', 'length_percent': 24},
                    {'type': 'External', 'length_percent': 9}
                ],
                'expected_rating': 1,
                'expected_result': 'PASS'
            },
            {
                'name': 'R2_Medium_Cracks',
                'cracks': [
                    {'type': 'Internal', 'length_percent': 45},
                    {'type': 'Internal', 'length_percent': 40},
                    {'type': 'External', 'length_percent': 24}
                ],
                'expected_rating': 2,
                'expected_result': 'PASS'
            },
            {
                'name': 'R3_Two_Large_Internals',
                'cracks': [
                    {'type': 'Internal', 'length_percent': 75},
                    {'type': 'Internal', 'length_percent': 60},
                    {'type': 'External', 'length_percent': 45}
                ],
                'expected_rating': 3,
                'expected_result': 'PASS'
            },
            {
                'name': 'R4_Total_Above_300',
                'cracks': [
                    {'type': 'Internal', 'length_percent': 151},
                    {'type': 'Internal', 'length_percent': 150}
                ],
                'expected_rating': 4,
                'expected_result': 'FAIL'
            },
            {
                'name': 'R4_Three_Above_50',
                'cracks': [
                    {'type': 'Internal', 'length_percent': 51},
                    {'type': 'Internal', 'length_percent': 52},
                    {'type': 'Internal', 'length_percent': 53}
                ],
                'expected_rating': 4,
                'expected_result': 'FAIL'
            },
            {
                'name': 'R5_Single_Split',
                'cracks': [{'type': 'Split', 'length_percent': 10}],
                'expected_rating': 5,
                'expected_result': 'FAIL'
            },
            {
                'name': 'R5_Split_Override',
                'cracks': [
                    {'type': 'Internal', 'length_percent': 5},
                    {'type': 'Split', 'length_percent': 5}
                ],
                'expected_rating': 5,
                'expected_result': 'FAIL'
            }
        ]
    
    def generate_report(self) -> str:
        """Generate a detailed test report"""
        if not self.test_results:
            return "No test results available. Run tests first."
        
        report = []
        report.append("=" * 60)
        report.append("ISO 23936-2 VALIDATION REPORT")
        report.append("=" * 60)
        report.append("")
        
        passed = sum(1 for r in self.test_results if r['passed'])
        failed = len(self.test_results) - passed
        
        report.append(f"Total Tests: {len(self.test_results)}")
        report.append(f"Passed: {passed}")
        report.append(f"Failed: {failed}")
        report.append(f"Success Rate: {(passed/len(self.test_results)*100):.1f}%")
        report.append("")
        
        if failed > 0:
            report.append("FAILED TESTS:")
            report.append("-" * 40)
            for result in self.test_results:
                if not result['passed']:
                    report.append(f"\nTest: {result['test_name']}")
                    report.append(f"  Expected Rating: {result['expected_rating']}")
                    report.append(f"  Your Rating: {result['actual_rating']}")
                    report.append(f"  Cracks: {result['cracks']}")
        
        return "\n".join(report)

class Canvas(QWidget):
    def __init__(self, background_image=None, table_widget=None, rating_table_widget=None):
        super().__init__()
        self.background_img = background_image
        self.background = QPixmap(background_image) if background_image else None
        if self.background and not self.background.isNull():
            print("Image loaded successfully.")
        else:
            print("Failed to load image. Check the path.")
            self.background = None
        self.scaled_background = None
        self.perimeter_points = []  # Points for perimeter
        self.perimeter_spline = []  # Smoothed spline points for perimeter
        self.cracks = []  # Store multiple crack lines as (points, color)
        self.current_crack = []  # Store the currently drawn crack

        self.drawing_perimeter = True  # Start with perimeter drawing mode
        self.drawing_cracks = False  # Initially disable crack drawing

        self.table_widget = table_widget  # Reference to the crack details table widget
        self.rating_table_widget = rating_table_widget  # Reference to the rating table widget

    def resizeEvent(self, event):
        """Rescale the background image when the canvas is resized."""
        if self.background:
            self.scaled_background = self.background.scaled(
                self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio
            )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw the background image
        if self.scaled_background:
            painter.drawPixmap(0, 0, self.scaled_background)
        elif self.background:
            # Set the initial scaled image if not already set
            self.scaled_background = self.background.scaled(
                self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio
            )
            painter.drawPixmap(0, 0, self.scaled_background)
        else:
            print("No image available for painting.")

        # Draw the perimeter points as red crosses
        pen = QPen(Qt.GlobalColor.red, 2)  # Pen for drawing perimeter points
        painter.setPen(pen)
        for point in self.perimeter_points:
            painter.drawLine(QPointF(point.x() - 5, point.y()), QPointF(point.x() + 5, point.y()))  # Horizontal line of the cross
            painter.drawLine(QPointF(point.x(), point.y() - 5), QPointF(point.x(), point.y() + 5))  # Vertical line of the cross

        # Draw the perimeter spline
        if self.perimeter_spline:
            pen = QPen(Qt.GlobalColor.green, 4)  # Green for perimeter with thicker line
            painter.setPen(pen)
            for i in range(len(self.perimeter_spline) - 1):
                painter.drawLine(self.perimeter_spline[i], self.perimeter_spline[i + 1])
            painter.drawLine(self.perimeter_spline[-1], self.perimeter_spline[0])  # Close the spline loop

        # Draw completed crack lines
        for crack, color in self.cracks:
            pen = QPen(color, 5)  # Thicker pen for better visibility
            painter.setPen(pen)
            for i in range(len(crack) - 1):
                painter.drawLine(crack[i], crack[i + 1])

        # Draw the current crack being defined
        if self.current_crack:
            pen = QPen(Qt.GlobalColor.black, 5)  # White for cracks under construction
            painter.setPen(pen)
            for i in range(len(self.current_crack) - 1):
                painter.drawLine(self.current_crack[i], self.current_crack[i + 1])

    def is_within_perimeter(self, point):
        """Check if a point is inside the perimeter defined by the spline."""
        if len(self.perimeter_spline) < 3:
            return True  # Allow drawing anywhere if no perimeter is defined

        # Implement a simple point-in-polygon algorithm (ray-casting algorithm)
        num_points = len(self.perimeter_spline)
        odd_nodes = False
        j = num_points - 1

        for i in range(num_points):
            if (self.perimeter_spline[i].y() < point.y() and self.perimeter_spline[j].y() >= point.y()) or \
            (self.perimeter_spline[j].y() < point.y() and self.perimeter_spline[i].y() >= point.y()):
                if (self.perimeter_spline[i].x() + (point.y() - self.perimeter_spline[i].y()) /
                    (self.perimeter_spline[j].y() - self.perimeter_spline[i].y()) *
                    (self.perimeter_spline[j].x() - self.perimeter_spline[i].x())) < point.x():
                    odd_nodes = not odd_nodes
            j = i

        return odd_nodes
    
    def mousePressEvent(self, event: QMouseEvent):
        point = QPointF(event.pos())
        
        if self.drawing_perimeter and event.button() == Qt.MouseButton.LeftButton:
            # Append the new point to perimeter points
            self.perimeter_points.append(point)
            self.update()

        elif self.drawing_perimeter and event.button() == Qt.MouseButton.MiddleButton:
            # Confirm or generate the perimeter if middle mouse button is pressed
            if not self.perimeter_spline:
                self.generate_loop()
            else:
                self.confirm_perimeter_prompt()

        elif self.drawing_perimeter and event.button() == Qt.MouseButton.RightButton:
            if not self.perimeter_spline:
                # Delete the closest point if right mouse button is pressed before loop generation
                self.delete_closest_point(point)
            else:
                # Delete the generated loop (before confirmation)
                self.perimeter_spline = []
                self.drawing_perimeter = True
                self.update()

        elif self.drawing_cracks and event.button() == Qt.MouseButton.LeftButton:
                # If the starting point is outside the perimeter, wait for the user to cross inwards
                if not self.is_within_perimeter(point):
                    self.current_crack = []  # Don't start the crack yet
                else:
                    # Snap the starting point to the perimeter if applicable
                    snapped_point = self.snap_to_perimeter(point)
                    self.current_crack = [snapped_point]  # Start the crack immediately


        elif self.drawing_cracks and event.button() == Qt.MouseButton.RightButton:
            # Delete a crack if right mouse button is clicked near it
            self.delete_crack(point)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drawing_cracks and event.buttons() == Qt.MouseButton.LeftButton:
            current_point = QPointF(event.pos())
            # Prevent adding points outside the perimeter
            if not self.is_within_perimeter(current_point):
                return
            
            if len(self.current_crack) >= 1: 
                self.current_crack.append(current_point)
            else:
                self.current_crack.append(self.snap_to_perimeter(current_point))  # Add points to the crack
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.drawing_cracks and event.button() == Qt.MouseButton.LeftButton:
            point = QPointF(event.pos())

            # Finalize the crack at the last valid point if it extends outside
            if not self.is_within_perimeter(point):
                if not self.current_crack:
                    # If no valid starting point exists inside the perimeter, ignore
                    return
                point = self.current_crack[-1]  # Use the last valid point inside the perimeter
                point = self.snap_to_perimeter(point)

            self.current_crack.append(self.snap_to_perimeter(point))

            # Validation: Ignore single-point cracks or cracks with no points inside the perimeter
            if len(self.current_crack) < 3:
                self.current_crack = []  # Reset the crack
                return

            # Classify the crack and add it to the list
            crack_color = self.classify_crack(self.current_crack)
            self.cracks.append((self.current_crack, crack_color))  # Store the completed crack with color
            self.add_to_crack_table(self.current_crack, crack_color)
            self.update_rating_table()
            self.current_crack = []  # Reset for the next crack
            self.update()
    
    def loadImage(self, file_path):
        """Load a new image into the canvas."""
        self.clearCanvas()
        self.background_image = file_path
        self.background = QPixmap(file_path)
        self.scaled_background = None  # Force rescaling
        self.update()
    
    def clearCanvas(self):
        """Clear everything: perimeter and cracks."""
        self.perimeter_points = []
        self.perimeter_spline = []
        self.cracks = []
        self.current_crack = []
        self.update()
        if self.table_widget:
            self.table_widget.clearContents()
            self.table_widget.setRowCount(0)
        if self.rating_table_widget:
            self.rating_table_widget.clearContents()
            self.initialize_rating_table()

    def generate_loop(self):
        """Generate the spline for the perimeter in a clockwise order."""
        if len(self.perimeter_points) < 3:
            QMessageBox.warning(self, "Not Enough Points", "Please add more points to define the perimeter.")
            return

        # Calculate the centroid of the points
        centroid_x = sum(point.x() for point in self.perimeter_points) / len(self.perimeter_points)
        centroid_y = sum(point.y() for point in self.perimeter_points) / len(self.perimeter_points)
        centroid = QPointF(centroid_x, centroid_y)

        # Sort the points in clockwise order relative to the centroid
        def angle_from_centroid(point):
            return math.atan2(point.y() - centroid.y(), point.x() - centroid.x())

        self.perimeter_points.sort(key=angle_from_centroid)

        # Generate a spline curve from the sorted perimeter points
        x = [point.x() for point in self.perimeter_points]
        y = [point.y() for point in self.perimeter_points]
        tck, _ = splprep([x, y], s=0, per=True)  # Create a periodic spline
        spline_x, spline_y = splev(np.linspace(0, 1, 1000), tck)  # Increase the resolution to 1000 points

        # Convert spline points back to QPointF
        self.perimeter_spline = [QPointF(px, py) for px, py in zip(spline_x, spline_y)]

        self.update()

    def confirm_perimeter_prompt(self):
        """Ask the user to confirm the generated perimeter."""
        response = QMessageBox.question(self, "Confirm Perimeter?", "Do you want to confirm the perimeter?", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if response == QMessageBox.StandardButton.Ok:
            self.drawing_perimeter = False
            self.perimeter_points = [] # clear the points from the screen
            self.drawing_cracks = True
            self.update_rating_table()
            self.show_crack_prompt()
        else:
            # Cancel deletes the generated loop and allows the user to edit points again
            self.perimeter_spline = []
            self.drawing_perimeter = True
        self.update()     

    def snap_to_perimeter(self, point, threshold=5):
        """Snap the point to the nearest perimeter point if within threshold."""
        if len(self.perimeter_spline) < 3:
            return point  # No snapping if the perimeter is not defined

        closest_point = point
        min_distance = threshold + 1  # Initialize with a value greater than the threshold

        for perimeter_point in self.perimeter_spline:
            distance = math.hypot(point.x() - perimeter_point.x(), point.y() - perimeter_point.y())
            if distance < min_distance:
                closest_point = perimeter_point
                min_distance = distance

        if min_distance <= threshold:
            return closest_point
        else: return point

    def delete_closest_point(self, point):
        """Delete the closest perimeter point to the given point."""
        if not self.perimeter_points:
            return

        closest_point = min(self.perimeter_points, key=lambda p: math.hypot(p.x() - point.x(), p.y() - point.y()))
        distance = math.hypot(closest_point.x() - point.x(), closest_point.y() - point.y())
        if distance < 10:
            self.perimeter_points.remove(closest_point)
            self.update()

    def classify_crack(self, crack):
        """Determine the type of crack based on if endpoints are snapped to the perimeter."""
        snap_count = sum(1 for point in [crack[0], crack[-1]] if point in self.perimeter_spline)

        if snap_count == 0:
            return Qt.GlobalColor.blue  # Internal crack
        elif snap_count == 1:
            return Qt.GlobalColor.yellow  # External crack (crossing perimeter once)
        elif snap_count >= 2:
            return Qt.GlobalColor.red  # Split crack (crossing perimeter twice)
        else:
            return Qt.GlobalColor.white  # Fail-safe color for undefined classification

    def add_to_crack_table(self, crack, color):
        """Adds new crack to crack details table"""
        if self.table_widget:
            row_position = self.table_widget.rowCount()
            self.table_widget.insertRow(row_position)

            # Determine crack type
            color_name = {
                Qt.GlobalColor.blue: "Internal",
                Qt.GlobalColor.yellow: "External",
                Qt.GlobalColor.red: "Split",
                Qt.GlobalColor.white: "Undefined"
            }
            crack_type = color_name.get(color, "Unknown")

            # Calculate crack length
            crack_length = sum(math.hypot(crack[i + 1].x() - crack[i].x(), crack[i + 1].y() - crack[i].y()) for i in range(len(crack) - 1))

            # Calculate the CSD and percentage length
            perimeter_length = sum(math.hypot(self.perimeter_spline[i + 1].x() - self.perimeter_spline[i].x(),
                                              self.perimeter_spline[i + 1].y() - self.perimeter_spline[i].y())
                                   for i in range(len(self.perimeter_spline) - 1))
            perimeter_length += math.hypot(self.perimeter_spline[-1].x() - self.perimeter_spline[0].x(),
                                           self.perimeter_spline[-1].y() - self.perimeter_spline[0].y())
            csd = perimeter_length / math.pi
            combined_length_all_cracks = (crack_length / csd) * 100 if csd > 0 else 0

            # Fill in table values
            item_crack_number = QTableWidgetItem(str(row_position + 1))
            item_crack_number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # Center-align
            self.table_widget.setItem(row_position, 0, item_crack_number)

            item_crack_type = QTableWidgetItem(crack_type)
            item_crack_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # Center-align
            self.table_widget.setItem(row_position, 1, item_crack_type)

            item_crack_length = QTableWidgetItem(f"{combined_length_all_cracks:.2f}%")
            item_crack_length.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # Center-align
            self.table_widget.setItem(row_position, 2, item_crack_length)

    def delete_crack(self, point):
        """Delete the crack if the right mouse button is clicked near it."""
        for crack, color in self.cracks:
            for crack_point in crack:
                distance = math.hypot(crack_point.x() - point.x(), crack_point.y() - point.y())
                if distance < 10:  # If the clicked point is close to any point in a crack
                    self.cracks.remove((crack, color))
                    self.update()

                    # Update the crack details table
                    if self.table_widget:
                        self.update_crack_table()

                    # Update the rating evaluation table
                    if self.rating_table_widget:
                        self.update_rating_table()

                    return
                
    def update_crack_table(self):
        """Update the crack details table, used when a crack is deleted."""
        if not self.table_widget:
            return

        self.table_widget.setRowCount(0)  # Clear the table and reset rows

        for row_position, (crack, color) in enumerate(self.cracks):
            # Determine crack type
            color_name = {
                Qt.GlobalColor.blue: "Internal",
                Qt.GlobalColor.yellow: "External",
                Qt.GlobalColor.red: "Split",
                Qt.GlobalColor.white: "Undefined"
            }
            crack_type = color_name.get(color, "Unknown")

            # Calculate crack length
            crack_length = sum(math.hypot(crack[i + 1].x() - crack[i].x(), crack[i + 1].y() - crack[i].y()) for i in range(len(crack) - 1))

            # Calculate the CSD and percentage length
            perimeter_length = sum(math.hypot(self.perimeter_spline[i + 1].x() - self.perimeter_spline[i].x(),
                                            self.perimeter_spline[i + 1].y() - self.perimeter_spline[i].y())
                                for i in range(len(self.perimeter_spline) - 1))
            perimeter_length += math.hypot(self.perimeter_spline[-1].x() - self.perimeter_spline[0].x(),
                                        self.perimeter_spline[-1].y() - self.perimeter_spline[0].y())
            csd = perimeter_length / math.pi if perimeter_length > 0 else 1
            combined_length_all_cracks = (crack_length / csd) * 100 if csd > 0 else 0

            # Insert updated crack information into the table
            self.table_widget.insertRow(row_position)
            self.table_widget.setItem(row_position, 0, QTableWidgetItem(str(row_position + 1)))
            self.table_widget.setItem(row_position, 1, QTableWidgetItem(crack_type))
            self.table_widget.setItem(row_position, 2, QTableWidgetItem(f"{combined_length_all_cracks:.2f}%"))

    def initialize_rating_table(self):
        """Initialize the rating evaluation table with metrics and thresholds for ratings."""
        if not self.rating_table_widget:
            return

        # Define the metrics and their descriptions
        metrics = [
            "Total crack length (% of CSD)",  # Rating 1, Metric 1
            "# cracks that are <25% CSD",  # Rating 1, Metric 2
            "All ext. cracks that are <10% CSD",  # Rating 1, Metric 3
            "# cracks that are <50% CSD",  # Rating 2, Metric 4
            # Metric 5 and 8 are accounted for by Metric 1
            "All ext. cracks that are <25% CSD",  # Rating 2, Metric 6
            "Are there 2 or fewer cracks between 50-80% CSD",  # Rating 3, Metric 7
            "All ext. cracks are <50% CSD",  # Rating 4, Metric 9
            "One or more int. cracks that are >80% CSD",  # Rating 4, Metric 10
            "Three or more int. cracks that are >50% CSD",  # Rating 4, Metric 11
            "Any splits present",  # Rating 5, Metric 12
            "OVERALL RATING"  # Final result
        ]

        # Define thresholds for each metric across all ratings
        thresholds = {
            "Rating 1": [
                "≤100% CSD",  # Metric 1
                "Any number",  # Metric 2
                "All <10%",  # Metric 3
                "-",  # Metric 4
                "-",  # Metric 6
                "-",  # Metric 7
                "-",  # Metric 9
                "-",  # Metric 10
                "-",  # Metric 11
                "-",  # Metric 12
                "Pass"  # Overall Evaluation
            ],
            "Rating 2": [
                "≤200% CSD",  # Metric 1
                "-",  # Metric 2
                "-",  # Metric 3
                "Any number",  # Metric 4
                "All <25%",  # Metric 6
                "-",  # Metric 7
                "-",  # Metric 9
                "-",  # Metric 10
                "-",  # Metric 11
                "-",  # Metric 12
                "Pass"  # Overall Evaluation
            ],
            "Rating 3": [
                "≤300% CSD",  # Metric 1
                "-",  # Metric 2
                "-",  # Metric 3
                "-",  # Metric 4
                "-",  # Metric 6
                "≤2 cracks",  # Metric 7
                "All <50%",  # Metric 9
                "-",  # Metric 10
                "-",  # Metric 11
                "-",  # Metric 12
                "Pass"  # Overall Evaluation
            ],
            "Rating 4": [
                "> 300% CSD",  # Metric 1
                "-",  # Metric 2
                "-",  # Metric 3
                "-",  # Metric 4
                "-",  # Metric 6
                "-",  # Metric 7
                "Any >50%",  # Metric 9
                "≥1 crack >80%",  # Metric 10
                "≥3 cracks >50%",  # Metric 11
                "-",  # Metric 12
                "Fail"  # Overall Evaluation
            ],
            "Rating 5": [
                "-",  # Metric 1
                "-",  # Metric 2
                "-",  # Metric 3
                "-",  # Metric 4
                "-",  # Metric 6
                "-",  # Metric 7
                "-",  # Metric 9
                "-",  # Metric 10
                "-",  # Metric 11
                "Yes",  # Metric 12
                "Fail"  # Overall Evaluation
            ],
        }

        # Set the row and column counts for the table
        self.rating_table_widget.setRowCount(len(metrics))
        self.rating_table_widget.setColumnCount(len(thresholds) + 2)  # Metric, Measured Value, Thresholds

        # Set the header labels
        self.rating_table_widget.setHorizontalHeaderLabels(["Metric", "Value"] + list(thresholds.keys()))

        # Make the rows stretch to fill the vertical space
        vertical_header = self.rating_table_widget.verticalHeader()
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Organize horizontal spacing
        self.rating_table_widget.resizeColumnsToContents()
        header = self.rating_table_widget.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.rating_table_widget.setColumnWidth(0, 275)  # Set width for "Metric" column

        # Populate the metrics and thresholds in the table
        for row, metric in enumerate(metrics):
            self.rating_table_widget.setItem(row, 0, QTableWidgetItem(metric))  # Metric name
            for col, threshold_key in enumerate(thresholds.keys(), start=2):
                self.rating_table_widget.setColumnWidth(col, 90)
                threshold_item = QTableWidgetItem(thresholds[threshold_key][row])
                threshold_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # Center-align threshold content
                self.rating_table_widget.setItem(row, col, threshold_item)
    
    def update_rating_table(self):
        if not self.rating_table_widget:
            return

        # ---- CSD ----
        perimeter_length = sum(
            math.hypot(self.perimeter_spline[i + 1].x() - self.perimeter_spline[i].x(),
                    self.perimeter_spline[i + 1].y() - self.perimeter_spline[i].y())
            for i in range(len(self.perimeter_spline) - 1)
        ) if self.perimeter_spline else 0.0

        if self.perimeter_spline:
            perimeter_length += math.hypot(
                self.perimeter_spline[-1].x() - self.perimeter_spline[0].x(),
                self.perimeter_spline[-1].y() - self.perimeter_spline[0].y()
            )
        csd = perimeter_length / math.pi if perimeter_length > 0 else 1.0

        # ---- Build engine inputs (percent of CSD per crack) ----
        engine_cracks = []  # [("Internal"/"External"/"Split", percent)]


        for crack, color in self.cracks:
            crack_len_px = sum(
                math.hypot(crack[i + 1].x() - crack[i].x(), crack[i + 1].y() - crack[i].y())
                for i in range(len(crack) - 1)
            )
            pct = (crack_len_px / csd) * 100.0 if csd > 0 else 0.0

            if color == Qt.GlobalColor.blue:
                engine_cracks.append(("Internal", pct))
            elif color == Qt.GlobalColor.yellow:
                engine_cracks.append(("External", pct))
            elif color == Qt.GlobalColor.red:
                engine_cracks.append(("Split", pct))
            # ignore other colors

        # ---- Delegate ALL metrics & rating to rating.py ----
        m = compute_metrics(engine_cracks, debug = True)
        assigned_rating = assign_iso23936_rating(engine_cracks)
        values = table_values(m)  # list of 10 strings in your row order

        # ---- Populate the Value column using engine-provided values ----
        for row, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.rating_table_widget.setItem(row, 1, item)

        # ---- Highlight the corresponding rating column (keep your mapping/look) ----
        # columns: 0=Metric, 1=Value, 2=R1, 3=R2, 4=R3, 5=R4, 6=R5
        for col in range(2, 8):
            for row in range(10):  # first 10 rows are metrics
                cell = self.rating_table_widget.item(row, col)
                if cell:
                    if col == assigned_rating + 1:  # 1->2, 2->3, ... ; rating 0 highlights none
                        cell.setBackground(Qt.GlobalColor.yellow)
                        cell.setForeground(Qt.GlobalColor.black)
                    else:
                        cell.setData(Qt.ItemDataRole.BackgroundRole, None)
                        cell.setData(Qt.ItemDataRole.ForegroundRole, None)

        # ---- Overall row (unchanged visuals) ----
        overall_row = 10
        overall_eval = "Pass" if assigned_rating <= 3 else "Fail"
        overall_text = f"Rating: {assigned_rating} - {overall_eval}"
        overall_item = QTableWidgetItem(overall_text)
        overall_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(overall_row, 1, overall_item)

        if overall_eval == "Pass":
            overall_item.setBackground(Qt.GlobalColor.green)
            overall_item.setForeground(Qt.GlobalColor.black)
        else:
            overall_item.setBackground(Qt.GlobalColor.red)
            overall_item.setForeground(Qt.GlobalColor.white)

        self.rating_table_widget.viewport().update()
   
    def show_crack_prompt(self):
        QMessageBox.information(
            self,
            "Trace cracks",
            "Click and drag the left-mouse button to trace the visible cracks on the o-ring.\n\n"
            "Release the left-mouse button to confirm a crack and add it to the analysis.\n\n"
            "You may use the right-mouse button to delete any number of drawn cracks from the analysis.\n\n"
            "You can click the 'Clear Session' button to re-start the analysis.\n"
        )
    
class MainWindow(QMainWindow):
    def __init__(self):
        window_size = [850, 900]
        super().__init__()
        self.setWindowTitle("oRinGD - ISO23939-2 Annex B Analyzer")
        self.resize(window_size[0], window_size[1])  # Set initial size to ensure better fit for canvas and tables
        self.setFixedSize(window_size[0], window_size[1])

        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)

        # Create the main layout
        main_layout = QVBoxLayout(centralWidget)

        # Top layout: Canvas and Crack Table Side by Side
        top_layout = QHBoxLayout()

        # Add the canvas on the left
        self.canvas = Canvas() # background_image="C:\\Users\\Stephen.Garden\\oRinGD\\test_2.jpg"
        self.canvas.setMinimumSize(600, 400)  # Set minimum size to ensure it's visible
        top_layout.addWidget(self.canvas)

        # Crack details table widget (right of the canvas)
        self.crack_table_widget = QTableWidget()
        self.crack_table_widget.setColumnCount(3)
        self.crack_table_widget.setHorizontalHeaderLabels(["Crack #", "Type", "Length, % of CSD"])
        self.crack_table_widget.verticalHeader().setVisible(False)  # Hide row numbers for cleanliness

        # Set specific column widths for the first two columns
        self.crack_table_widget.setColumnWidth(0, 50)  # Fixed width for column 0
        self.crack_table_widget.setColumnWidth(1, 75)   # Fixed width for column 1

        # Set the third column to stretch and fill the remaining space
        header = self.crack_table_widget.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        top_layout.addWidget(self.crack_table_widget)

        # Add the top layout to the main layout
        main_layout.addLayout(top_layout, stretch=32)

        # Bottom layout: Rating Evaluation Table
        self.rating_table_widget = QTableWidget()
        self.rating_table_widget.setColumnCount(7)
        self.rating_table_widget.setHorizontalHeaderLabels(
            ["Metric", "Value", "Rating 0", "Rating 1", "Rating 2", "Rating 3", "Rating 4", "Rating 5"]
        )
        self.rating_table_widget.verticalHeader().setVisible(False)  # Hide row labels for cleanliness

        main_layout.addWidget(self.rating_table_widget, stretch=17)

        # Bottom layout for buttons
        button_layout = QHBoxLayout()

        # Image Selection Button
        imageButton = QPushButton("Select Image")
        imageButton.clicked.connect(self.select_image)
        button_layout.addWidget(imageButton)

        # Restart / Clear Button
        clearButton = QPushButton("Clear Session")
        clearButton.clicked.connect(self.clear_session)
        button_layout.addWidget(clearButton)

        # Save Analysis Button
        saveReportButton = QPushButton("Save Report")
        saveReportButton.clicked.connect(self.saveAsExcel)
        button_layout.addWidget(saveReportButton)

        # Close button
        closeButton = QPushButton("Close")
        closeButton.clicked.connect(self.close)
        button_layout.addWidget(closeButton)

        # Add debug evaluation buttons
        debugButton = QPushButton("Debug Current Rating")
        debugButton.clicked.connect(self.debug_current_rating)
        button_layout.addWidget(debugButton)

        # Add button layout to the main vertical layout
        main_layout.addLayout(button_layout)

        # Assign crack details and rating evaluation table to canvas for updates
        self.canvas.table_widget = self.crack_table_widget
        self.canvas.rating_table_widget = self.rating_table_widget

        # Initialize rating table properly
        self.canvas.initialize_rating_table()
        
        self.show()
        # self.showFullScreen()

        # Show instructions for perimeter drawing
        self.show_perimeter_prompt()

    def clear_session(self):
        """Clear the canvas and reset the session."""
        response = QMessageBox.question(
            self,
            "Clear Session?",
            "Are you sure you want to clear the session? All data will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if response == QMessageBox.StandardButton.Yes:
            self.canvas.clearCanvas()  # Reset the canvas

    def show_perimeter_prompt(self):
        QMessageBox.information(
            self,
            "Set Perimeter",
            "Use the left-mouse button to add points around the perimeter of the o-ring.\n\n"
            "When finished, click the middle mouse button to generate the loop and review the line fit.\n\n"
            "You may use the right-mouse button to delete any points or the fitted perimeter line before confirming.\n\n"
            "Once happy, click the middle mouse button again to confirm.\n"
        )

    def select_image(self):
        """Open a file dialog to select an image and load it into the canvas."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select O-Ring Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.canvas.loadImage(file_path)

    def saveCanvas(self, file_path=0, suppress_conf=False):
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(self,
                                                   "Save Image",
                                                   "",
                                                   "PNG Files (*.png);;All Files (*)")
        if file_path:
            pixmap = self.canvas.grab()
            pixmap.save(file_path)
            if not suppress_conf:
                QMessageBox.information(self, "Success", f"Image saved to {file_path}")

    def saveAsExcel(self):
        # Ensure an image is loaded first
        if not self.canvas.background_image:
            QMessageBox.warning(self, "No Image!", "No image has been loaded. Please load an image first.")
            return
        
        # Extract the file name from the loaded image path
        image_path = self.canvas.background_image
        image_name = os.path.basename(image_path) # e.g. "sample1.png"
        base_name = os.path.splitext(image_name)[0] # e.g. "sample1"
        
        # Suggest a default report name
        current_date = datetime.datetime.now().strftime("%m%d%Y")
        default_report_name = f"{base_name} - report - {current_date}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, 
                                                   "Save Report", 
                                                   default_report_name, 
                                                   "Excel Files (*.xlsx);;All Files (*)")
        
        if file_path:
            # Create an Excel workbook
            workbook = Workbook()

            # 1. Save the annotated image
            image_sheet = workbook.active
            image_sheet.title = f"{base_name} Analysis"

            # Use saveCanvas to create a temporary PNG file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_image_path = temp_file.name
            self.saveCanvas(temp_image_path, suppress_conf=True)

            # Add the temporary image to the Excel workbook
            excel_image = Image(temp_image_path)
            image_sheet.add_image(excel_image, "B2")

            # Save the headers for the results table
            header_row = 2  # Adjust as necessary
            for col in range(self.rating_table_widget.columnCount()):
                header_item = self.rating_table_widget.horizontalHeaderItem(col)
                header_value = header_item.text() if header_item else ""
                header_cell = image_sheet.cell(row=header_row, column=12 + col)  # Headers start at row 2, column L
                header_cell.value = header_value

            # Save the results table rows below the headers
            start_row = header_row + 1  # Data starts just below the headers
            for row in range(self.rating_table_widget.rowCount()):
                for col in range(self.rating_table_widget.columnCount()):
                    item = self.rating_table_widget.item(row, col)
                    value = item.text() if item else ""
                    cell = image_sheet.cell(row=start_row + row, column=12 + col)
                    cell.value = value

            # Manually set column widths
            image_sheet.column_dimensions["L"].width = 50  # Set width for column L
            for col_letter in ["M", "N", "O", "P", "Q", "R"]:
                image_sheet.column_dimensions[col_letter].width = 20  # Set width for columns M through R


                
            # 2. Save the crack list
            crack_sheet = workbook.create_sheet("Crack List")
            crack_sheet.append(["Crack #", "Type", "Length (% of CSD)"])
            for row in range(self.crack_table_widget.rowCount()):
                crack_sheet.append([
                    self.crack_table_widget.item(row, 0).text(),
                    self.crack_table_widget.item(row, 1).text(),
                    self.crack_table_widget.item(row, 2).text()
                ])
            
            # Save the workbook
            workbook.save(file_path)
            QMessageBox.information(self, "Success", f"Report saved to {file_path}")

            # Clean up the temporary image file
            os.remove(temp_image_path)
    
    def add_validation_menu(self):
        """
        Add this method to your MainWindow __init__ to create a validation menu
        Call this after creating the canvas
        """
        # Add to your button layout
        validationButton = QPushButton("Run Validation Tests")
        validationButton.clicked.connect(self.run_validation_tests)
        # Add to your button_layout
        
        debugButton = QPushButton("Debug Current Rating")
        debugButton.clicked.connect(self.debug_current_rating)
        # Add to your button_layout

    def debug_current_rating(self):
        """Debug the current rating assignment"""
        if not self.canvas.perimeter_spline:
            QMessageBox.warning(self, "No Perimeter", "Please define a perimeter first.")
            return
        
        # Calculate current metrics
        debug_info = self.get_rating_debug_info()
        
        # Show debug information
        dialog = QDialog(self)
        dialog.setWindowTitle("Rating Debug Information")
        dialog.setMinimumSize(500, 800)
        
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setPlainText(debug_info)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        dialog.setLayout(layout)
        dialog.exec()

    def get_rating_debug_info(self):
        """
        Enhanced debug information about current rating with ALL relevant conditions
        """
        info = []
        info.append("CURRENT RATING DEBUG INFORMATION")
        info.append("=" * 40)
        
        if not self.canvas.perimeter_spline:
            return "No perimeter defined"
        
        # Calculate CSD
        perimeter_length = sum(
            math.hypot(
                self.canvas.perimeter_spline[i + 1].x() - self.canvas.perimeter_spline[i].x(),
                self.canvas.perimeter_spline[i + 1].y() - self.canvas.perimeter_spline[i].y()
            )
            for i in range(len(self.canvas.perimeter_spline) - 1)
        )
        perimeter_length += math.hypot(
            self.canvas.perimeter_spline[-1].x() - self.canvas.perimeter_spline[0].x(),
            self.canvas.perimeter_spline[-1].y() - self.canvas.perimeter_spline[0].y()
        )
        csd = perimeter_length / math.pi
        
        info.append(f"CSD: {csd:.2f} pixels")
        info.append(f"Number of cracks: {len(self.canvas.cracks)}")
        info.append("")
        
        # Analyze each crack
        total_length_percent = 0
        internal_lengths = []
        external_lengths = []
        has_split = False
        
        for i, (crack, color) in enumerate(self.canvas.cracks):
            crack_length = sum(
                math.hypot(crack[j + 1].x() - crack[j].x(), 
                        crack[j + 1].y() - crack[j].y()) 
                for j in range(len(crack) - 1)
            )
            length_percent = (crack_length / csd) * 100
            total_length_percent += length_percent
            
            crack_type = "Unknown"
            if color == Qt.GlobalColor.blue:
                crack_type = "Internal"
                internal_lengths.append(length_percent)
            elif color == Qt.GlobalColor.yellow:
                crack_type = "External"
                external_lengths.append(length_percent)
            elif color == Qt.GlobalColor.red:
                crack_type = "Split"
                has_split = True
            
            info.append(f"Crack {i+1}: {crack_type}, {length_percent:.2f}% CSD")
        
        info.append("")
        info.append("DETAILED METRICS FOR RATING DETERMINATION:")
        info.append("-" * 40)
        
        # Calculate ALL relevant metrics
        all_crack_lengths = internal_lengths + external_lengths
        
        # Rating 1 metrics
        info.append("Rating 1 Requirements:")
        info.append(f"  Total length ≤100%: {total_length_percent:.2f}% ({'✓' if total_length_percent <= 100 else '✗'})")
        all_below_25 = all(l < 25 for l in all_crack_lengths)
        info.append(f"  All cracks <25%: {'✓' if all_below_25 else '✗'}")
        num_at_or_above_25 = sum(1 for l in all_crack_lengths if l >= 25)
        if not all_below_25:
            info.append(f"    → {num_at_or_above_25} crack(s) ≥25% CSD")
        all_ext_below_10 = all(l < 10 for l in external_lengths) if external_lengths else True
        info.append(f"  All external <10%: {'✓' if all_ext_below_10 else '✗'}")
        
        # Rating 2 metrics
        info.append("\nRating 2 Requirements:")
        info.append(f"  Total length ≤200%: {total_length_percent:.2f}% ({'✓' if total_length_percent <= 200 else '✗'})")
        all_below_50 = all(l < 50 for l in all_crack_lengths)
        info.append(f"  All cracks <50%: {'✓' if all_below_50 else '✗'}")
        num_at_or_above_50 = sum(1 for l in all_crack_lengths if l >= 50)
        if not all_below_50:
            info.append(f"    → {num_at_or_above_50} crack(s) ≥50% CSD")
        all_ext_below_25 = all(l < 25 for l in external_lengths) if external_lengths else True
        info.append(f"  All external <25%: {'✓' if all_ext_below_25 else '✗'}")
        
        # Rating 3 metrics
        info.append("\nRating 3 Requirements:")
        info.append(f"  Total length ≤300%: {total_length_percent:.2f}% ({'✓' if total_length_percent <= 300 else '✗'})")
        internal_50_80_count = sum(1 for l in internal_lengths if 50 <= l <= 80)
        info.append(f"  ≤2 internal cracks 50-80%: {internal_50_80_count} ({'✓' if internal_50_80_count <= 2 else '✗'})")
        all_ext_below_50 = all(l < 50 for l in external_lengths) if external_lengths else True
        info.append(f"  All external <50%: {'✓' if all_ext_below_50 else '✗'}")

        # Rating 4 triggers (any one triggers failure)
        info.append("\nRating 4 Triggers (any one triggers failure):")
        info.append(f"  Total >300%: {'✗' if total_length_percent > 300 else '✓'}")
        internal_above_80_count = sum(1 for l in internal_lengths if l > 80)
        info.append(f"  ≥1 internal >80%: {internal_above_80_count} ({'✗' if internal_above_80_count >= 1 else '✓'})")
        internal_above_50_count = sum(1 for l in internal_lengths if l > 50)
        info.append(f"  ≥3 internals >50%: {internal_above_50_count} ({'✗' if internal_above_50_count >= 3 else '✓'})")
        any_ext_above_50 = any(l > 50 for l in external_lengths) if external_lengths else False
        info.append(f"  Any external >50%: {'✗' if any_ext_above_50 else '✓'}")

        # Rating 5 trigger
        info.append("\nRating 5 Trigger:")
        info.append(f"  Any split present: {'✗' if has_split else '✓'}")

        
        info.append("\n" + "=" * 40)
        info.append("RATING DECISION TREE:")
        
        # Determine rating using same logic as update_rating_table
        if not self.canvas.cracks:
            assigned_rating = 0
            info.append("No cracks → Rating 0")
        elif has_split:
            assigned_rating = 5
            info.append("Has split → Rating 5 (FAIL)")
        else:
            # Check Rating 1
            if total_length_percent <= 100 and all_below_25 and all_ext_below_10:
                assigned_rating = 1
                info.append("Meets Rating 1 conditions")
            # Check Rating 4 (before 2 and 3)
            elif (total_length_percent > 300 or 
                internal_above_80_count >= 1 or 
                internal_above_50_count >= 3 or 
                any_ext_above_50):
                assigned_rating = 4
                info.append("Triggers Rating 4 conditions (FAIL)")
                # Explain which condition triggered it
                triggers = []
                if total_length_percent > 300:
                    triggers.append(f"Total {total_length_percent:.1f}% > 300%")
                if internal_above_80_count >= 1:
                    triggers.append(f"{internal_above_80_count} internal(s) > 80%")
                if internal_above_50_count >= 3:
                    triggers.append(f"{internal_above_50_count} internals > 50%")
                if any_ext_above_50:
                    triggers.append("External crack > 50%")
                info.append(f"   Triggered by: {', '.join(triggers)}")
            # Check Rating 2
            elif total_length_percent <= 200 and all_below_50 and all_ext_below_25:
                assigned_rating = 2
                info.append("Meets Rating 2 conditions")
            # Check Rating 3
            elif total_length_percent <= 300 and internal_50_80_count <= 2 and all_ext_below_50:
                assigned_rating = 3
                info.append("Meets Rating 3 conditions")
            else:
                assigned_rating = 4
                info.append("Default to Rating 4 (no other conditions met)")
        
        info.append(f"\nFINAL RATING: {assigned_rating} - {'PASS' if assigned_rating <= 3 else 'FAIL'}")
        
        return "\n".join(info)

app = QApplication(sys.argv)
window = MainWindow()
sys.exit(app.exec())