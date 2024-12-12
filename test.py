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
