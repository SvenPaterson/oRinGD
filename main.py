import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
from PyQt6.QtGui import QPainter, QMouseEvent, QPen, QPixmap
from PyQt6.QtCore import Qt, QPointF
from scipy.interpolate import splprep, splev
import numpy as np
import math


class Canvas(QWidget):
    def __init__(self, background_image=None):
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
            painter.drawLine(point.x() - 5, point.y(), point.x() + 5, point.y())  # Horizontal line of the cross
            painter.drawLine(point.x(), point.y() - 5, point.x(), point.y() + 5)  # Vertical line of the cross

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
            self.perimeter_points.append(event.pos())
            self.update()

        elif self.drawing_cracks and event.button() == Qt.MouseButton.LeftButton:
            self.current_crack = [event.pos()]  # Start a new crack

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drawing_cracks and event.buttons() == Qt.MouseButton.LeftButton:
            self.current_crack.append(event.pos())  # Add points to the crack
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.drawing_cracks and event.button() == Qt.MouseButton.LeftButton:
            # After releasing the mouse, classify and color the crack
            crack_color = self.classify_crack(self.current_crack)
            self.cracks.append((self.current_crack, crack_color))  # Store the completed crack with color
            self.current_crack = []  # Reset for the next crack
            self.update()

    def clearCanvas(self):
        """Clear everything: perimeter and cracks."""
        self.perimeter_points = []
        self.perimeter_spline = []
        self.cracks = []
        self.current_crack = []
        self.update()

    def confirmPerimeter(self):
        """Generate the spline for the perimeter and switch to crack defining mode."""
        if len(self.perimeter_points) < 3:
            QMessageBox.warning(self, "Not Enough Points", "Please add more points to define the perimeter.")
            return

        # Generate a spline curve from the perimeter points
        x = [point.x() for point in self.perimeter_points]
        y = [point.y() for point in self.perimeter_points]
        tck, _ = splprep([x, y], s=0, per=True)  # Create a periodic spline
        spline_x, spline_y = splev(np.linspace(0, 1, 200), tck)  # Increase the resolution to 200 points

        # Convert spline points back to QPointF
        self.perimeter_spline = [QPointF(px, py) for px, py in zip(spline_x, spline_y)]

        # Switch to crack defining mode
        self.drawing_perimeter = False
        self.drawing_cracks = True
        self.update()

    def undoLastPerimeterPoint(self):
        """Undo the last perimeter point added."""
        if self.perimeter_points:
            self.perimeter_points.pop()  # Remove the last perimeter point
            self.update()

    def undoLastCrack(self):
        """Remove the last crack line drawn."""
        if self.cracks:
            self.cracks.pop()  # Remove the last crack segment
            self.update()

    def classify_crack(self, crack):
        """Determine the type of crack based on its endpoints and proximity to the perimeter."""
        if len(self.perimeter_spline) < 3:
            return Qt.GlobalColor.white  # Default color if perimeter is incomplete or undefined

        # Count the number of times a crack crosses the perimeter
        proximity_threshold = 5
        crosses = 0

        # Iterate through each segment of the crack
        for i in range(len(crack) - 1):
            start_point = crack[i]
            end_point = crack[i + 1]

            # Iterate through each segment of the perimeter
            for j in range(len(self.perimeter_spline) - 1):
                perimeter_start = self.perimeter_spline[j]
                perimeter_end = self.perimeter_spline[j + 1]

                # Check proximity for start and end points of crack segment
                if self.segment_proximity(start_point, end_point, perimeter_start, perimeter_end, proximity_threshold):
                    crosses += 1
                    if crosses > 2:
                        return Qt.GlobalColor.white  # Undefined crack if more than 2 crossings

        # Assign colors based on the number of crossings
        if crosses == 0:
            return Qt.GlobalColor.blue  # Internal crack
        elif crosses == 1:
            return Qt.GlobalColor.yellow  # External crack (crossing perimeter once)
        elif crosses == 2:
            return Qt.GlobalColor.red  # Split crack (crossing perimeter twice)
        else:
            return Qt.GlobalColor.white  # Fail-safe color for undefined classification

    def segment_proximity(self, p1, p2, p3, p4, threshold):
        """Check if the crack segment (p1, p2) is within the threshold distance of the perimeter segment (p3, p4)."""
        if self.is_within_proximity(p1, p3, threshold) or self.is_within_proximity(p2, p4, threshold):
            return True
        return False

    def is_within_proximity(self, point1, point2, threshold):
        """Check if point1 is within the given threshold distance from point2."""
        distance = math.hypot(point1.x() - point2.x(), point1.y() - point2.y())
        return distance <= threshold


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 O-Ring Analyzer")
        self.showFullScreen()

        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)

        layout = QVBoxLayout(centralWidget)

        # Add the canvas
        self.canvas = Canvas(background_image="C:\\Users\\Stephen.Garden\\oRinGD\\test_2.jpg")
        layout.addWidget(self.canvas)

        # Add buttons below the canvas
        buttonLayout = QHBoxLayout()

        # Confirm Perimeter Button
        self.confirmPerimeterButton = QPushButton("Confirm Perimeter")
        self.confirmPerimeterButton.clicked.connect(self.confirmPerimeter)
        buttonLayout.addWidget(self.confirmPerimeterButton)

        # Undo Last Point Button (for perimeter)
        self.undoLastPointButton = QPushButton("Undo Last Point")
        self.undoLastPointButton.clicked.connect(self.canvas.undoLastPerimeterPoint)
        buttonLayout.addWidget(self.undoLastPointButton)

        # Crack Defining Buttons (initially hidden)
        self.undoButton = QPushButton("Undo Last Crack")
        self.undoButton.clicked.connect(self.canvas.undoLastCrack)
        self.undoButton.setVisible(False)
        buttonLayout.addWidget(self.undoButton)

        self.clearButton = QPushButton("Clear All")
        self.clearButton.clicked.connect(self.canvas.clearCanvas)
        self.clearButton.setVisible(False)
        buttonLayout.addWidget(self.clearButton)

        closeButton = QPushButton("Close")
        closeButton.clicked.connect(self.close)
        buttonLayout.addWidget(closeButton)

        # Add button layout to main layout
        layout.addLayout(buttonLayout)

        # Show instructions for perimeter drawing
        self.show_perimeter_prompt()

    def show_perimeter_prompt(self):
        QMessageBox.information(self, "Set Perimeter", "Please click to add points around the perimeter of the o-ring. When finished, click 'Confirm Perimeter'. If needed, use 'Undo Last Point' to adjust points.")

    def show_crack_prompt(self):
        QMessageBox.information(self, "Define Cracks", "Please define cracks. External cracks should cross the perimeter boundary. External cracks will be colored yellow, internal cracks will be blue, and splits will be red.")

    def confirmPerimeter(self):
        """Confirm the perimeter and proceed to crack definition."""
        self.canvas.confirmPerimeter()  # Confirm the perimeter on the canvas

        # Hide perimeter confirmation and undo buttons
        self.confirmPerimeterButton.setVisible(False)
        self.undoLastPointButton.setVisible(False)

        # Show crack-related buttons
        self.undoButton.setVisible(True)
        self.clearButton.setVisible(True)

        # Show instructions for defining cracks
        self.show_crack_prompt()


app = QApplication(sys.argv)
window = MainWindow()
window.showFullScreen()  # Fullscreen mode
sys.exit(app.exec())
