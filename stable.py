import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem, QPushButton
from PyQt6.QtGui import QPainter, QMouseEvent, QPen, QPixmap
from PyQt6.QtCore import Qt, QPointF
from scipy.interpolate import splprep, splev
import numpy as np
import math

class Canvas(QWidget):
    def __init__(self, background_image=None, table_widget=None, rating_table_widget=None):
        super().__init__()
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

        if self.rating_table_widget:
            self.initialize_rating_table()  # Initialize rating table during setup

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
            pen = QPen(Qt.GlobalColor.white, 5)  # White for temporary undefined cracks
            painter.setPen(pen)
            for i in range(len(self.current_crack) - 1):
                painter.drawLine(self.current_crack[i], self.current_crack[i + 1])

    def mousePressEvent(self, event: QMouseEvent):
        if self.drawing_perimeter and event.button() == Qt.MouseButton.LeftButton:
            # Append the new point to perimeter points
            self.perimeter_points.append(QPointF(event.pos()))
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
                self.delete_closest_point(QPointF(event.pos()))
            else:
                # Delete the generated loop (before confirmation)
                self.perimeter_spline = []
                self.drawing_perimeter = True
                self.update()

        elif self.drawing_cracks and event.button() == Qt.MouseButton.LeftButton:
            # Snap the first point to the perimeter if needed
            snapped_point = self.snap_to_perimeter(QPointF(event.pos()))
            self.current_crack = [snapped_point]  # Start a new crack with the snapped starting point if applicable

        elif self.drawing_cracks and event.button() == Qt.MouseButton.RightButton:
            # Delete a crack if right mouse button is clicked near it
            self.delete_crack(QPointF(event.pos()))

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drawing_cracks and event.buttons() == Qt.MouseButton.LeftButton:
            current_point = QPointF(event.pos())
            # Prevent adding points outside the perimeter
            if not self.is_within_perimeter(current_point):
                return

            self.current_crack.append(current_point)  # Add points to the crack
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.drawing_cracks and event.button() == Qt.MouseButton.LeftButton:
            # Snap the endpoint to the perimeter if it's close enough
            snapped_point = self.snap_to_perimeter(QPointF(event.pos()))
            self.current_crack.append(snapped_point)  # Add the endpoint
            # Classify and color the crack
            crack_color = self.classify_crack(self.current_crack)
            self.cracks.append((self.current_crack, crack_color))  # Store the completed crack with color
            self.update_table(self.current_crack, crack_color)
            self.update_rating_table()  # Update rating evaluation table
            self.current_crack = []  # Reset for the next crack
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
        spline_x, spline_y = splev(np.linspace(0, 1, 200), tck)  # Increase the resolution to 200 points

        # Convert spline points back to QPointF
        self.perimeter_spline = [QPointF(px, py) for px, py in zip(spline_x, spline_y)]

        self.update()

    def confirm_perimeter_prompt(self):
        """Ask the user to confirm the generated perimeter."""
        response = QMessageBox.question(self, "Confirm Perimeter?", "Do you want to confirm the perimeter?", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if response == QMessageBox.StandardButton.Ok:
            self.confirm_perimeter()
        else:
            # Cancel deletes the generated loop and allows the user to edit points again
            self.perimeter_spline = []
            self.drawing_perimeter = True
            self.update()

    def confirm_perimeter(self):
        """Confirm the perimeter and switch to crack defining mode."""
        self.drawing_perimeter = False
        self.drawing_cracks = True
        self.update()
        self.update_rating_table()

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

        # Return the closest perimeter point if within threshold, otherwise return the original point
        return closest_point if min_distance <= threshold else point

    def is_within_perimeter(self, point):
        """Check if a point is inside the perimeter defined by the spline."""
        if len(self.perimeter_spline) < 3:
            return True  # If no perimeter is defined, allow drawing everywhere

        # Implement a simple point-in-polygon algorithm (ray-casting algorithm)
        num_points = len(self.perimeter_spline)
        odd_nodes = False
        j = num_points - 1

        for i in range(num_points):
            if (self.perimeter_spline[i].y() < point.y() and self.perimeter_spline[j].y() >= point.y()) or (
                self.perimeter_spline[j].y() < point.y() and self.perimeter_spline[i].y() >= point.y()):
                if (self.perimeter_spline[i].x() + (point.y() - self.perimeter_spline[i].y()) /
                    (self.perimeter_spline[j].y() - self.perimeter_spline[i].y()) *
                    (self.perimeter_spline[j].x() - self.perimeter_spline[i].x())) < point.x():
                    odd_nodes = not odd_nodes
            j = i

        return odd_nodes

    def delete_closest_point(self, point):
        """Delete the closest perimeter point to the given point."""
        if not self.perimeter_points:
            return

        closest_point = min(self.perimeter_points, key=lambda p: math.hypot(p.x() - point.x(), p.y() - point.y()))
        distance = math.hypot(closest_point.x() - point.x(), closest_point.y() - point.y())
        if distance < 10:
            self.perimeter_points.remove(closest_point)
            self.update()

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
                        self.update_crack_details_table()

                    # Update the rating evaluation table
                    if self.rating_table_widget:
                        self.update_rating_table()

                    return

    def classify_crack(self, crack):
        """Determine the type of crack based on if endpoints are snapped to the perimeter."""
        snap_count = sum(1 for point in [crack[0], crack[-1]] if point in self.perimeter_spline)

        if snap_count == 0:
            return Qt.GlobalColor.blue  # Internal crack
        elif snap_count == 1:
            return Qt.GlobalColor.yellow  # External crack (crossing perimeter once)
        elif snap_count == 2:
            return Qt.GlobalColor.red  # Split crack (crossing perimeter twice)
        else:
            return Qt.GlobalColor.white  # Fail-safe color for undefined classification

    def update_table(self, crack, color):
        """Update the table with the crack details."""
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
            self.table_widget.setItem(row_position, 0, QTableWidgetItem(str(row_position + 1)))
            self.table_widget.setItem(row_position, 1, QTableWidgetItem(crack_type))
            self.table_widget.setItem(row_position, 2, QTableWidgetItem(f"{combined_length_all_cracks:.2f}%"))

    def update_crack_details_table(self):
        """Update the crack details table with the current cracks information."""
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
            "Total Crack Length (% of CSD)",  # Rating 1, Metric 1
            "# Cracks < 25% CSD",  # Rating 1, Metric 2
            "All external cracks < 10% CSD",  # Rating 1, Metric 3
            "# Cracks < 50% CSD",  # Rating 2, Metric 4
            # Metric 5 and 8 are accounted for by Metric 1
            "All external cracks < 25% CSD",  # Rating 2, Metric 6
            "Two or less Internal Cracks 50-80% CSD",  # Rating 3, Metric 7
            "All external cracks < 50% CSD",  # Rating 4, Metric 9
            "At least one Internal Crack > 80% CSD",  # Rating 4, Metric 10
            "Three or more Internal Cracks > 50% CSD",  # Rating 4, Metric 11
            "Presence of Splits",  # Rating 5, Metric 12
            "Overall Evaluation"  # Final result
        ]

        # Define thresholds for each metric across all ratings
        thresholds = {
            "Threshold (1)": [
                "≤ 100% CSD",  # Metric 1
                "Any number",  # Metric 2
                "All < 10%",  # Metric 3
                "-",  # Metric 4
                "-",  # Metric 6
                "-",  # Metric 7
                "-",  # Metric 9
                "-",  # Metric 10
                "-",  # Metric 11
                "-",  # Metric 12
                "Pass"  # Overall Evaluation
            ],
            "Threshold (2)": [
                "≤ 200% CSD",  # Metric 1
                "-",  # Metric 2
                "-",  # Metric 3
                "Any number",  # Metric 4
                "All < 25%",  # Metric 6
                "-",  # Metric 7
                "-",  # Metric 9
                "-",  # Metric 10
                "-",  # Metric 11
                "-",  # Metric 12
                "Pass"  # Overall Evaluation
            ],
            "Threshold (3)": [
                "≤ 300% CSD",  # Metric 1
                "-",  # Metric 2
                "-",  # Metric 3
                "-",  # Metric 4
                "-",  # Metric 6
                "≤ 2 cracks",  # Metric 7
                "All < 50%",  # Metric 9
                "-",  # Metric 10
                "-",  # Metric 11
                "-",  # Metric 12
                "Pass"  # Overall Evaluation
            ],
            "Threshold (4)": [
                "> 300% CSD",  # Metric 1
                "-",  # Metric 2
                "-",  # Metric 3
                "-",  # Metric 4
                "-",  # Metric 6
                "-",  # Metric 7
                "Any > 50%",  # Metric 9
                "≥ 1 crack > 80%",  # Metric 10
                "≥ 3 cracks > 50%",  # Metric 11
                "-",  # Metric 12
                "Fail"  # Overall Evaluation
            ],
            "Threshold (5)": [
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
        self.rating_table_widget.setHorizontalHeaderLabels(["Metric", "Measured Value"] + list(thresholds.keys()))

        # Populate the metrics and thresholds in the table
        for row, metric in enumerate(metrics):
            self.rating_table_widget.setItem(row, 0, QTableWidgetItem(metric))  # Metric name
            self.rating_table_widget.setRowHeight(row, 1)
            for col, threshold_key in enumerate(thresholds.keys(), start=2):
                self.rating_table_widget.setItem(row, col, QTableWidgetItem(thresholds[threshold_key][row]))



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
        self.rating_table_widget.setItem(0, 1, QTableWidgetItem(f"{combined_length_all_cracks:.2f}%"))

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
        self.rating_table_widget.setItem(1, 1, QTableWidgetItem(str(cracks_below_25_percent)))

        # if are_all_cracks_below_25_percent:

        # Metric 3: All external cracks should be < 10% CSD
        are_all_external_cracks_below_10_percent = all((length / csd) * 100 < 10 for length, color in crack_lengths if color == Qt.GlobalColor.yellow)
        self.rating_table_widget.setItem(2, 1, QTableWidgetItem("Yes" if are_all_external_cracks_below_10_percent else "No"))

        ## Rating 2 conditions
        # Metric 4: # Cracks < 50% CSD
        num_cracks_below_50_percent = sum(1 for length, _ in crack_lengths if (length / csd) * 100 < 50)
        are_all_cracks_below_50_percent = all((length / csd) * 100 < 50 for length, _ in crack_lengths)
        self.rating_table_widget.setItem(3, 1, QTableWidgetItem(str(num_cracks_below_50_percent)))

        # Metric 5: Total Crack Length (% of CSD) below 2 x CSD
        all_cracks_combined_below_2xCSD = combined_length_all_cracks <= 200
        
        # Metric 6: All external cracks < 25% CSD
        are_all_external_cracks_below_25_percent = all((length / csd) * 100 < 25 for length, color in crack_lengths if color == Qt.GlobalColor.yellow)
        self.rating_table_widget.setItem(4, 1, QTableWidgetItem("Yes" if are_all_external_cracks_below_25_percent else "No"))

        ## Rating 3 conditions
        # Metric 7: Two or less Internal Cracks 50-80% CSD
        num_internal_cracks_50_80_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and 50 <= (length / csd) * 100 <= 80)
        are_there_two_or_less_internal_cracks_each_between_50_80 = num_internal_cracks_50_80_percent <= 2
        self.rating_table_widget.setItem(5, 1, QTableWidgetItem(str(are_there_two_or_less_internal_cracks_each_between_50_80)))

        # Metric 8: Total Crack Length (% of CSD) below 3 x csd
        are_all_cracks_combined_below_3xCSD = combined_length_all_cracks <= 300
        
        ## Rating 4 conditions
        # Metric 9: All external cracks < 50% CSD
        are_all_external_cracks_below_50_percent = all((length / csd) * 100 < 50 for length, color in crack_lengths if color == Qt.GlobalColor.yellow)
        self.rating_table_widget.setItem(6, 1, QTableWidgetItem("Yes" if are_all_external_cracks_below_50_percent else "No"))

        # Metric 10: At least one internal crack > 80% CSD
        num_internal_cracks_above_80_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and (length / csd) * 100 > 80)
        are_there_one_or_more_internal_cracks_each_above_80_percent = num_internal_cracks_above_80_percent >= 1
        self.rating_table_widget.setItem(7, 1, QTableWidgetItem("Yes" if are_there_one_or_more_internal_cracks_each_above_80_percent else "No"))

        # Metric 12: Three or more internal cracks, each > 50% CSD
        num_internal_cracks_above_50_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and (length / csd) * 100 > 50)
        are_there_three_or_more_internal_cracks_each_above_50_percent = num_internal_cracks_above_50_percent >= 3
        self.rating_table_widget.setItem(8, 1, QTableWidgetItem("Yes" if are_there_three_or_more_internal_cracks_each_above_50_percent else "No"))

        # Rating 5 conditions
        # Metric 13: Presence of Splits (color = red)
        are_any_splits_present = any(color == Qt.GlobalColor.red for _, color in crack_lengths)
        self.rating_table_widget.setItem(9, 1, QTableWidgetItem("Yes" if are_any_splits_present else "No"))

        ## Final Evaluation
        are_any_cracks_present = bool(crack_lengths)

        ### DEBUG CODE ###
        # Rating 5 Conditions
        print("Rating 5 Conditions:")
        print(f"are_any_splits_present: {are_any_splits_present}")

        # Rating 0 Conditions
        print("\nRating 0 Conditions:")
        print(f"are_any_cracks_present: {are_any_cracks_present}")

        # Rating 1 Conditions
        print("\nRating 1 Conditions:")
        print(f"are_all_cracks_below_25_percent: {are_all_cracks_below_25_percent}")
        print(f"all_cracks_combined_below_CSD: {all_cracks_combined_below_CSD}")
        print(f"are_all_external_cracks_below_10_percent: {are_all_external_cracks_below_10_percent}")

        # Rating 2 Conditions
        print("\nRating 2 Conditions:")
        print(f"are_all_cracks_below_50_percent: {are_all_cracks_below_50_percent}")
        print(f"all_cracks_combined_below_2xCSD: {all_cracks_combined_below_2xCSD}")
        print(f"are_all_external_cracks_below_25_percent: {are_all_external_cracks_below_25_percent}")

        # Rating 3 Conditions
        print("\nRating 3 Conditions:")
        print(f"are_there_two_or_less_internal_cracks_each_between_50_80: {are_there_two_or_less_internal_cracks_each_between_50_80}")
        print(f"are_all_cracks_combined_below_3xCSD: {are_all_cracks_combined_below_3xCSD}")
        print(f"are_all_external_cracks_below_50_percent: {are_all_external_cracks_below_50_percent}")

        # Rating 4 Conditions
        print("\nRating 4 Conditions:")
        print(f"not_are_all_cracks_combined_below_3xCSD: {not are_all_cracks_combined_below_3xCSD}")
        print(f"are_there_one_or_more_internal_cracks_each_above_80_percent: {are_there_one_or_more_internal_cracks_each_above_80_percent}")
        print(f"are_there_three_or_more_internal_cracks_each_above_50_percent: {are_there_three_or_more_internal_cracks_each_above_50_percent}")
        print(f"not_are_all_external_cracks_below_50_percent: {not are_all_external_cracks_below_50_percent}")
        print()
        print()
        ###

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
                                    if self.rating_table_widget.item(row, 0) and self.rating_table_widget.item(row, 0).text() == "Overall Evaluation"), None)
        overall_evaluation = "Pass" if assigned_rating <= 3 else "Fail"

        if overall_evaluation_row is not None:
            overall_evaluation_text = f"Rating: {assigned_rating} - {overall_evaluation}"
            self.rating_table_widget.setItem(overall_evaluation_row, 1, QTableWidgetItem(overall_evaluation_text))
            evaluation_item = self.rating_table_widget.item(overall_evaluation_row, 1)
            if evaluation_item:
                evaluation_item.setBackground(Qt.GlobalColor.green if overall_evaluation == "Pass" else Qt.GlobalColor.red)

        # Refresh the table
        self.rating_table_widget.viewport().update()

    def count_cracks_below_threshold(self, threshold_percent):
        """Count the number of cracks below a given length threshold percentage of CSD."""
        if not self.perimeter_spline:
            return 0

        perimeter_length = sum(
            math.hypot(self.perimeter_spline[i + 1].x() - self.perimeter_spline[i].x(),
                       self.perimeter_spline[i + 1].y() - self.perimeter_spline[i].y())
            for i in range(len(self.perimeter_spline) - 1)
        )
        perimeter_length += math.hypot(
            self.perimeter_spline[-1].x() - self.perimeter_spline[0].x(),
            self.perimeter_spline[-1].y() - self.perimeter_spline[0].y()
        )
        csd = perimeter_length / math.pi

        count = 0
        for crack, color in self.cracks:
            crack_length = sum(math.hypot(crack[i + 1].x() - crack[i].x(), crack[i + 1].y() - crack[i].y()) for i in range(len(crack) - 1))
            combined_length_all_cracks = (crack_length / csd) * 100 if csd > 0 else 0
            if combined_length_all_cracks < threshold_percent:
                count += 1

        return count


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 O-Ring Analyzer")
        self.resize(1200, 800)  # Set initial size to ensure better fit for canvas and tables

        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)

        # Create the main layout
        main_layout = QVBoxLayout(centralWidget)

        # Top layout: Canvas and Crack Table Side by Side
        top_layout = QHBoxLayout()

        # Add the canvas on the left
        self.canvas = Canvas(background_image="C:\\Users\\Stephen.Garden\\oRinGD\\test_2.jpg")
        self.canvas.setMinimumSize(600, 400)  # Set minimum size to ensure it's visible
        top_layout.addWidget(self.canvas, stretch = 5)

        # Crack details table widget (right of the canvas)
        self.crack_table_widget = QTableWidget()
        self.crack_table_widget.setColumnCount(3)
        self.crack_table_widget.setHorizontalHeaderLabels(["Crack #", "Type", "Length, % of CSD"])
        self.crack_table_widget.verticalHeader().setVisible(False)  # Hide row numbers for cleanliness
        self.crack_table_widget.resizeColumnsToContents()
        self.crack_table_widget.setColumnWidth(1, 60)
        top_layout.addWidget(self.crack_table_widget, stretch=1)

        # Add the top layout to the main layout
        main_layout.addLayout(top_layout, stretch=32)

        # Bottom layout: Rating Evaluation Table
        self.rating_table_widget = QTableWidget()
        self.rating_table_widget.setColumnCount(7)
        self.rating_table_widget.setHorizontalHeaderLabels(
            ["Metric", "Measured Value", "Threshold (0)", "Threshold (1)", "Threshold (2)", "Threshold (3)", "Threshold (4)"]
        )
        self.rating_table_widget.verticalHeader().setVisible(False)  # Hide row labels for cleanliness

        # Alternatively, set specific widths for cells
        self.rating_table_widget.setColumnWidth(0, 250)  # Set width for "Metric" column
        self.rating_table_widget.setColumnWidth(1, 120)  # Set width for "Measured Value" column

        main_layout.addWidget(self.rating_table_widget, stretch=13)

        # Bottom layout for buttons
        button_layout = QHBoxLayout()

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
        self.showFullScreen()

        # Show instructions for perimeter drawing
        self.show_perimeter_prompt()

    def show_perimeter_prompt(self):
        QMessageBox.information(
            self,
            "Set Perimeter",
            "Please click to add points around the perimeter of the o-ring.\n"
            "When finished, click the middle mouse button to generate the loop and review the line fit.\n"
            "Once happy, click the middle mouse button again to confirm.\n"
            "You can also use the right mouse button to delete any points before confirming.\n"
            "After confirming, if you right-click, the perimeter will disappear and you can edit points again."
        )

app = QApplication(sys.argv)
window = MainWindow()
sys.exit(app.exec())