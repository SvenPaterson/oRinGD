from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtCore import Qt

class MouseExample(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mouse Example")
        self.setGeometry(100, 100, 400, 300)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            print(f"Left button pressed at {event.pos()}")
        elif event.button() == Qt.MouseButton.RightButton:
            print(f"Right button pressed at {event.pos()}")

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            print(f"Dragging with left button at {event.pos()}")
        elif event.buttons() == Qt.MouseButton.RightButton:
            print(f"Dragging with right button at {event.pos()}")

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            print(f"Left button released at {event.pos()}")
        elif event.button() == Qt.MouseButton.RightButton:
            print(f"Right button released at {event.pos()}")

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            print(f"Left button double-clicked at {event.pos()}")

if __name__ == "__main__":
    app = QApplication([])
    window = MouseExample()
    window.show()
    app.exec()


### DEBUG CODE ###
""" # Rating 5 Conditions
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
print() """
###