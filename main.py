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
        """Update the rating evaluation table with the measured values for each metric."""
        if not self.rating_table_widget:
            return

        # Calculate the perimeter length (CSD)
        perimeter_length = sum(
            math.hypot(self.perimeter_spline[i + 1].x() - self.perimeter_spline[i].x(),
                    self.perimeter_spline[i + 1].y() - self.perimeter_spline[i].y())
            for i in range(len(self.perimeter_spline) - 1)
        )
        perimeter_length += math.hypot(
            self.perimeter_spline[-1].x() - self.perimeter_spline[0].x(),
            self.perimeter_spline[-1].y() - self.perimeter_spline[0].y()
        )
        csd = perimeter_length / math.pi if perimeter_length > 0 else 1  # Prevent division by zero

        # Calculate total crack length and length percentages
        total_crack_length = 0
        crack_lengths = []
        external_crack_lengths = []

        for crack, color in self.cracks:
            crack_length = sum(math.hypot(crack[i + 1].x() - crack[i].x(), crack[i + 1].y() - crack[i].y()) for i in range(len(crack) - 1))
            total_crack_length += crack_length
            crack_lengths.append((crack_length, color))
            if color == Qt.GlobalColor.yellow:  # External cracks
                external_crack_lengths.append(crack_length)

        ### Metrics Calculation and Table Update
        ## Rating 1 conditions
        # Metric 1: Total Crack Length (% of CSD)
        combined_length_all_cracks = (total_crack_length / csd) * 100 if csd > 0 else 0
        all_cracks_combined_below_CSD = combined_length_all_cracks <= 100
        value_item = QTableWidgetItem(f"{combined_length_all_cracks:.2f}%")
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(0, 1, value_item)

        # Highlight the current threshold for Metric 1
        if combined_length_all_cracks <= 100:
            col = 2
        elif combined_length_all_cracks <= 200:
            col = 3
        elif combined_length_all_cracks < 300:
            col = 4
        else:
            col = 5
        
        for c in range(6):
            highlight_cell = self.rating_table_widget.item(0, c)
            if c == col:
                highlight_cell.setBackground(Qt.GlobalColor.yellow)
            else: highlight_cell.setBackground(Qt.GlobalColor.white)
            
        
        # Metric 2: # Cracks < 25% CSD
        cracks_below_25_percent = sum(1 for length, _ in crack_lengths if (length / csd) * 100 < 25)
        are_all_cracks_below_25_percent = all((length / csd) * 100 < 25 for length, _ in crack_lengths)
        value_item = QTableWidgetItem(str(cracks_below_25_percent))
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(1, 1, value_item)

        # Metric 3: All external cracks should be < 10% CSD
        are_all_external_cracks_below_10_percent = all((length / csd) * 100 < 10 for length, color in crack_lengths if color == Qt.GlobalColor.yellow)
        value_item = QTableWidgetItem("Yes" if are_all_external_cracks_below_10_percent else "No")
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(2, 1, value_item)

        ## Rating 2 conditions
        # Metric 4: # Cracks < 50% CSD
        num_cracks_below_50_percent = sum(1 for length, _ in crack_lengths if (length / csd) * 100 < 50)
        are_all_cracks_below_50_percent = all((length / csd) * 100 < 50 for length, _ in crack_lengths)
        value_item = QTableWidgetItem(str(num_cracks_below_50_percent))
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(3, 1, value_item)

        # Metric 5: Total Crack Length (% of CSD) below 2 x CSD
        all_cracks_combined_below_2xCSD = combined_length_all_cracks <= 200
        
        # Metric 6: All external cracks < 25% CSD
        are_all_external_cracks_below_25_percent = all((length / csd) * 100 < 25 for length, color in crack_lengths if color == Qt.GlobalColor.yellow)
        value_item = QTableWidgetItem("Yes" if are_all_external_cracks_below_25_percent else "No")
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(4, 1, value_item)

        ## Rating 3 conditions
        # Metric 7: Two or less Internal Cracks 50-80% CSD
        num_internal_cracks_50_80_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and 50 <= (length / csd) * 100 <= 80)
        are_there_two_or_less_internal_cracks_each_between_50_80 = num_internal_cracks_50_80_percent <= 2
        value_item = QTableWidgetItem(str(are_there_two_or_less_internal_cracks_each_between_50_80))
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(5, 1, value_item)

        # Metric 8: Total Crack Length (% of CSD) below 3 x csd
        are_all_cracks_combined_below_3xCSD = combined_length_all_cracks <= 300
        
        ## Rating 4 conditions
        # Metric 9: All external cracks < 50% CSD
        are_all_external_cracks_below_50_percent = all((length / csd) * 100 < 50 for length, color in crack_lengths if color == Qt.GlobalColor.yellow)
        value_item = QTableWidgetItem("Yes" if are_all_external_cracks_below_50_percent else "No")
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(6, 1, value_item)

        # Metric 10: At least one internal crack > 80% CSD
        num_internal_cracks_above_80_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and (length / csd) * 100 > 80)
        are_there_one_or_more_internal_cracks_each_above_80_percent = num_internal_cracks_above_80_percent >= 1
        value_item = QTableWidgetItem("Yes" if are_there_one_or_more_internal_cracks_each_above_80_percent else "No")
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(7, 1, value_item)

        # Metric 12: Three or more internal cracks, each > 50% CSD
        num_internal_cracks_above_50_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and (length / csd) * 100 > 50)
        are_there_three_or_more_internal_cracks_each_above_50_percent = num_internal_cracks_above_50_percent >= 3
        value_item = QTableWidgetItem("Yes" if are_there_three_or_more_internal_cracks_each_above_50_percent else "No")
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(8, 1, value_item)

        # Rating 5 conditions
        # Metric 13: Presence of Splits (color = red)
        are_any_splits_present = any(color == Qt.GlobalColor.red for _, color in crack_lengths)
        value_item = QTableWidgetItem("Yes" if are_any_splits_present else "No")
        value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating_table_widget.setItem(9, 1, value_item)

        ## Final Evaluation
        are_any_cracks_present = bool(crack_lengths)

        # Step 1: Evaluate Rating 5 (Any split at all)
        if are_any_splits_present:
            assigned_rating = 5

        # Step 2: Evaluate Rating 0 (No cracks at all)
        elif not are_any_cracks_present:
            assigned_rating = 0

        # Step 3: Evaluate sequentially for Ratings 1 through 4
        else:
        
            if are_all_cracks_below_25_percent and all_cracks_combined_below_CSD and are_all_external_cracks_below_10_percent:
                assigned_rating = 1

            elif not are_all_cracks_combined_below_3xCSD or are_there_one_or_more_internal_cracks_each_above_80_percent \
                 or are_there_three_or_more_internal_cracks_each_above_50_percent or not are_all_external_cracks_below_50_percent:
                assigned_rating = 4
            
            elif are_all_cracks_below_50_percent and all_cracks_combined_below_2xCSD and are_all_external_cracks_below_25_percent:
                assigned_rating = 2

            elif are_there_two_or_less_internal_cracks_each_between_50_80 and are_all_cracks_combined_below_3xCSD and are_all_external_cracks_below_50_percent:
                assigned_rating = 3

        # Update Overall Evaluation
        overall_evaluation_row = next((row for row in range(self.rating_table_widget.rowCount())
                                    if self.rating_table_widget.item(row, 0) and self.rating_table_widget.item(row, 0).text() == "OVERALL RATING"), None)
        overall_evaluation = "Pass" if assigned_rating <= 3 else "Fail"

        if overall_evaluation_row is not None:
            overall_evaluation_text = f"Rating: {assigned_rating} - {overall_evaluation}"
            self.rating_table_widget.setItem(overall_evaluation_row, 1, QTableWidgetItem(overall_evaluation_text))
            evaluation_item = self.rating_table_widget.item(overall_evaluation_row, 1)
            evaluation_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if evaluation_item:
                evaluation_item.setBackground(Qt.GlobalColor.green if overall_evaluation == "Pass" else Qt.GlobalColor.red)

        # Refresh the table
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
    

app = QApplication(sys.argv)
window = MainWindow()
sys.exit(app.exec())