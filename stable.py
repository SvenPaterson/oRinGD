import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView
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
                if distance < 10:
                    self.cracks.remove((crack, color))
                    self.update()
                    if self.table_widget:
                        self.update_table_widget()
                    self.update_rating_table()  # Ensure table updates after deletion
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
            length_percent = (crack_length / csd) * 100 if csd > 0 else 0

            # Fill in table values
            self.table_widget.setItem(row_position, 0, QTableWidgetItem(str(row_position + 1)))
            self.table_widget.setItem(row_position, 1, QTableWidgetItem(crack_type))
            self.table_widget.setItem(row_position, 2, QTableWidgetItem(f"{length_percent:.2f}%"))

    def initialize_rating_table(self):
        """Initialize the rating evaluation table with metrics and thresholds for ratings."""
        if not self.rating_table_widget:
            return

        metrics = [
            "Total Crack Length (% of CSD)",
            "# Cracks < 25% CSD",
            "# Cracks < 50% CSD",
            "# Internal Cracks",
            "Internal Cracks 50-80% CSD",
            "Max Internal Crack Length",
            "Max External Crack Length",
            "Presence of Splits",
            "Overall Evaluation"  # New row to show the pass/fail status
        ]

        # Define thresholds for each metric including the new "Threshold (5)"
        thresholds = {
            "Threshold (0)": ["0%", "0", "-", "0", "-", "-", "0", "None", "Pass"],
            "Threshold (1)": ["≤ 100%", "Any number", "-", "Any number", "-", "< 25% CSD", "< 10% CSD", "None", "Pass"],
            "Threshold (2)": ["≤ 200%", "-", "Any number", "Any number", "≤ 2", "< 50% CSD", "< 25% CSD", "None", "Pass"],
            "Threshold (3)": ["≤ 300%", "-", "-", "Any number", "≤ 2", "≤ 80% CSD", "< 50% CSD", "None", "Pass"],
            "Threshold (4)": ["> 300%", "-", "-", "≥ 3 > 50% CSD", "-", "> 80% CSD", "> 50% CSD", "None", "Fail"],
            "Threshold (5)": ["-", "-", "-", "-", "-", "-", "-", "Any split", "Fail"]  # New Threshold (5) including split condition
        }

        # Update column count to accommodate the new "Threshold (5)" column
        self.rating_table_widget.setColumnCount(len(thresholds) + 2)

        # Update header labels
        self.rating_table_widget.setHorizontalHeaderLabels(
            ["Metric", "Measured Value"] + list(thresholds.keys())
        )

        # Set the row count for the metrics
        self.rating_table_widget.setRowCount(len(metrics))

        # Fill in the metrics and thresholds
        for row, metric in enumerate(metrics):
            # Set metric name
            self.rating_table_widget.setItem(row, 0, QTableWidgetItem(metric))

            # Set thresholds for each rating level
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

        for crack, color in self.cracks:
            crack_length = sum(math.hypot(crack[i + 1].x() - crack[i].x(), crack[i + 1].y() - crack[i].y()) for i in range(len(crack) - 1))
            total_crack_length += crack_length
            crack_lengths.append((crack_length, color))

        length_percent = (total_crack_length / csd) * 100 if csd > 0 else 0

        # Metric 1: Total Crack Length (% of CSD)
        self.rating_table_widget.setItem(0, 1, QTableWidgetItem(f"{length_percent:.2f}%"))

        # Metric 2: # Cracks < 25% CSD
        cracks_below_25_percent = sum(1 for length, _ in crack_lengths if (length / csd) * 100 < 25)
        self.rating_table_widget.setItem(1, 1, QTableWidgetItem(str(cracks_below_25_percent)))

        # Metric 3: # Cracks < 50% CSD
        cracks_below_50_percent = sum(1 for length, _ in crack_lengths if (length / csd) * 100 < 50)
        self.rating_table_widget.setItem(2, 1, QTableWidgetItem(str(cracks_below_50_percent)))

        # Metric 4: # Internal Cracks (color = blue)
        internal_cracks_count = sum(1 for _, color in crack_lengths if color == Qt.GlobalColor.blue)
        self.rating_table_widget.setItem(3, 1, QTableWidgetItem(str(internal_cracks_count)))

        # Metric 5: Internal Cracks 50-80% CSD
        internal_cracks_50_80 = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and 50 <= (length / csd) * 100 <= 80)
        self.rating_table_widget.setItem(4, 1, QTableWidgetItem(str(internal_cracks_50_80)))

        # Metric 6: Max Internal Crack Length (color = blue)
        max_internal_crack_length = max((length for length, color in crack_lengths if color == Qt.GlobalColor.blue), default=0)
        self.rating_table_widget.setItem(5, 1, QTableWidgetItem(f"{(max_internal_crack_length / csd) * 100:.2f}%"))

        # Metric 7: Max External Crack Length (color = yellow)
        max_external_crack_length = max((length for length, color in crack_lengths if color == Qt.GlobalColor.yellow), default=0)
        self.rating_table_widget.setItem(6, 1, QTableWidgetItem(f"{(max_external_crack_length / csd) * 100:.2f}%"))

        # Metric 8: Presence of Splits (color = red)
        presence_of_splits = "Yes" if any(color == Qt.GlobalColor.red for _, color in crack_lengths) else "No"
        self.rating_table_widget.setItem(7, 1, QTableWidgetItem(presence_of_splits))

        # Determine Overall Evaluation
        overall_evaluation = "Pass"
        assigned_rating = 5  # Start with the highest rating, and reduce as needed

        # Step 1: Check for Rating 5 (Any split)
        if presence_of_splits == "Yes":
            assigned_rating = 5
            overall_evaluation = "Fail"

        # Step 2: Check if no cracks (Rating 0)
        elif len(crack_lengths) == 0:
            assigned_rating = 0
            overall_evaluation = "Pass"

        else:
            # Step 3: Evaluate external cracks
            for crack_length, color in crack_lengths:
                if color == Qt.GlobalColor.yellow:  # External crack
                    crack_length_percent = (crack_length / csd) * 100

                    if crack_length_percent > 50:
                        assigned_rating = 4
                        overall_evaluation = "Fail"
                        break
                    elif 25 < crack_length_percent <= 50:
                        assigned_rating = min(assigned_rating, 3)
                    elif 10 < crack_length_percent <= 25:
                        assigned_rating = min(assigned_rating, 2)
                    elif crack_length_percent <= 10:
                        assigned_rating = min(assigned_rating, 1)

            # Step 4: Further evaluation based on assigned rating
            if assigned_rating >= 1:
                if assigned_rating == 1:
                    if all((length / csd) * 100 < 25 for length, _ in crack_lengths) and length_percent < 100:
                        assigned_rating = 1
                elif assigned_rating == 2:
                    if all(25 <= (length / csd) * 100 < 50 for length, _ in crack_lengths) and 100 <= length_percent < 200:
                        assigned_rating = 2
                elif assigned_rating == 3:
                    if internal_cracks_50_80 <= 2 and 200 <= length_percent < 300:
                        assigned_rating = 3
                        overall_evaluation = "Fail"
                elif assigned_rating == 4:
                    if length_percent >= 300 or any((length / csd) * 100 > 80 for length, color in crack_lengths if color == Qt.GlobalColor.blue) or \
                            sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and (length / csd) * 100 > 50) >= 3:
                        assigned_rating = 4
                        overall_evaluation = "Fail"

        # Update Overall Evaluation in the Rating Table
        overall_evaluation_text = f"Rating: {assigned_rating} - {overall_evaluation}"
        self.rating_table_widget.setItem(8, 1, QTableWidgetItem(overall_evaluation_text))

        # Visual Cue: Change the background color based on the evaluation
        if overall_evaluation == "Fail":
            self.rating_table_widget.item(8, 1).setBackground(Qt.GlobalColor.red)
        else:
            self.rating_table_widget.item(8, 1).setBackground(Qt.GlobalColor.green)

        # Refresh the UI for the table to reflect changes
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
            length_percent = (crack_length / csd) * 100 if csd > 0 else 0
            if length_percent < threshold_percent:
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
        top_layout.addWidget(self.canvas, stretch = 1)

        # Crack details table widget (right of the canvas)
        self.crack_table_widget = QTableWidget()
        self.crack_table_widget.setColumnCount(3)
        self.crack_table_widget.setHorizontalHeaderLabels(["Crack #", "Type", "Length, % of CSD"])
        self.crack_table_widget.verticalHeader().setVisible(False)  # Hide row numbers for cleanliness
        top_layout.addWidget(self.crack_table_widget, stretch=1)

        # Add the top layout to the main layout
        main_layout.addLayout(top_layout, stretch=9)

        # Bottom layout: Rating Evaluation Table
        self.rating_table_widget = QTableWidget()
        self.rating_table_widget.setColumnCount(7)
        self.rating_table_widget.setHorizontalHeaderLabels(
            ["Metric", "Measured Value", "Threshold (0)", "Threshold (1)", "Threshold (2)", "Threshold (3)", "Threshold (4)"]
        )
        self.rating_table_widget.verticalHeader().setVisible(False)  # Hide row labels for cleanliness

        # Alternatively, set specific widths for individual columns
        self.rating_table_widget.setColumnWidth(0, 250)  # Set width for "Metric" column
        self.rating_table_widget.setColumnWidth(1, 120)  # Set width for "Measured Value" column

        main_layout.addWidget(self.rating_table_widget, stretch=4)

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
window.show()
window.showFullScreen()
sys.exit(app.exec())
