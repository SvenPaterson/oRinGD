import os
import sys
import datetime
import tempfile
from typing import Optional

from PyQt6.QtCore import Qt
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
    QTextEdit,
    QDialog,
)

from openpyxl import Workbook
from openpyxl.drawing.image import Image

from rating import compute_metrics, table_values, assign_iso23936_rating

from canvas_gv import CanvasScene, CanvasView


class MainWindow(QMainWindow):
    def __init__(self):
        window_size = [850, 900]
        super().__init__()
        self.setWindowTitle("oRinGD - ISO23936-2 Annex B Analyzer")
        self.resize(window_size[0], window_size[1])
        self.setFixedSize(window_size[0], window_size[1])

        self.current_image_path: Optional[str] = None
        self._has_shown_crack_prompt = False

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        content_layout = QHBoxLayout()
        root_layout.addLayout(content_layout, stretch=32)

        self.scene = CanvasScene()
        self.view = CanvasView(self.scene)
        self.view.setMinimumSize(600, 400)
        content_layout.addWidget(self.view, stretch=32)

        self.crack_table_widget = QTableWidget()
        self.crack_table_widget.setColumnCount(3)
        self.crack_table_widget.setHorizontalHeaderLabels(["Crack #", "Type", "Length, % of CSD"])
        self.crack_table_widget.verticalHeader().setVisible(False)
        self.crack_table_widget.setColumnWidth(0, 50)
        self.crack_table_widget.setColumnWidth(1, 75)
        crack_header = self.crack_table_widget.horizontalHeader()
        crack_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        content_layout.addWidget(self.crack_table_widget, stretch=17)

        self.rating_table_widget = QTableWidget()
        self.rating_table_widget.setColumnCount(7)
        self.rating_table_widget.setHorizontalHeaderLabels(
            ["Metric", "Value", "Rating 1", "Rating 2", "Rating 3", "Rating 4", "Rating 5"]
        )
        self.rating_table_widget.verticalHeader().setVisible(False)
        root_layout.addWidget(self.rating_table_widget, stretch=17)

        button_layout = QHBoxLayout()

        image_button = QPushButton("Select Image")
        image_button.clicked.connect(self.select_image)
        button_layout.addWidget(image_button)

        perim_mode_button = QPushButton("Perimeter Mode")
        perim_mode_button.clicked.connect(lambda: self.view.set_mode('draw_perimeter'))
        button_layout.addWidget(perim_mode_button)

        crack_mode_button = QPushButton("Crack Mode")
        crack_mode_button.clicked.connect(lambda: self.view.set_mode('draw_crack'))
        button_layout.addWidget(crack_mode_button)

        clear_button = QPushButton("Clear Session")
        clear_button.clicked.connect(self.clear_session)
        button_layout.addWidget(clear_button)

        save_report_button = QPushButton("Save Report")
        save_report_button.clicked.connect(self.saveAsExcel)
        button_layout.addWidget(save_report_button)

        debug_button = QPushButton("Debug Current Rating")
        debug_button.clicked.connect(self.debug_current_rating)
        button_layout.addWidget(debug_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)

        root_layout.addLayout(button_layout)

        self.initialize_rating_table()
        self.refresh_tables()

        self.view.perimeterUpdated.connect(self.refresh_tables)
        self.view.cracksUpdated.connect(self.refresh_tables)
        self.view.modeChanged.connect(self.on_mode_changed)

        self.show()
        self.show_perimeter_prompt()

    def on_mode_changed(self, mode: str):
        if mode == 'draw_perimeter':
            self._has_shown_crack_prompt = False
        if mode == 'draw_crack' and not self._has_shown_crack_prompt:
            self.show_crack_prompt()
            self._has_shown_crack_prompt = True

    def refresh_tables(self):
        self.update_crack_table()
        self.update_rating_table()

    def update_crack_table(self):
        _, cracks = self.view.engine_inputs()
        self.crack_table_widget.setRowCount(len(cracks))
        for row, (crack_type, percent_length) in enumerate(cracks):
            number_item = QTableWidgetItem(str(row + 1))
            number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_item = QTableWidgetItem(crack_type)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            length_item = QTableWidgetItem(f"{percent_length:.2f}%")
            length_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.crack_table_widget.setItem(row, 0, number_item)
            self.crack_table_widget.setItem(row, 1, type_item)
            self.crack_table_widget.setItem(row, 2, length_item)

    def initialize_rating_table(self):
        metrics = [
            "Total crack length (% of CSD)",
            "# cracks that are <25% CSD",
            "All ext. cracks that are <10% CSD",
            "# cracks that are <50% CSD",
            "All ext. cracks that are <25% CSD",
            "Are there 2 or fewer cracks between 50-80% CSD",
            "All ext. cracks are <50% CSD",
            "One or more int. cracks that are >80% CSD",
            "Three or more int. cracks that are >50% CSD",
            "Any splits present",
            "OVERALL RATING",
        ]

        thresholds = {
            "Rating 1": [
                "≤100% CSD",
                "Any number",
                "All <10%",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "Pass",
            ],
            "Rating 2": [
                "≤200% CSD",
                "-",
                "-",
                "Any number",
                "All <25%",
                "-",
                "-",
                "-",
                "-",
                "-",
                "Pass",
            ],
            "Rating 3": [
                "≤300% CSD",
                "-",
                "-",
                "-",
                "-",
                "≤2 cracks",
                "All <50%",
                "-",
                "-",
                "-",
                "Pass",
            ],
            "Rating 4": [
                "> 300% CSD",
                "-",
                "-",
                "-",
                "-",
                "-",
                "Any >50%",
                "≥1 crack >80%",
                "≥3 cracks >50%",
                "-",
                "Fail",
            ],
            "Rating 5": [
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "Yes",
                "Fail",
            ],
        }

        self.rating_table_widget.setRowCount(len(metrics))
        self.rating_table_widget.setColumnCount(len(thresholds) + 2)
        self.rating_table_widget.setHorizontalHeaderLabels(["Metric", "Value"] + list(thresholds.keys()))

        vertical_header = self.rating_table_widget.verticalHeader()
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rating_table_widget.resizeColumnsToContents()
        header = self.rating_table_widget.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.rating_table_widget.setColumnWidth(0, 275)

        for row, metric in enumerate(metrics):
            self.rating_table_widget.setItem(row, 0, QTableWidgetItem(metric))
            for col, threshold_key in enumerate(thresholds.keys(), start=2):
                self.rating_table_widget.setColumnWidth(col, 90)
                threshold_item = QTableWidgetItem(thresholds[threshold_key][row])
                threshold_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.rating_table_widget.setItem(row, col, threshold_item)

    def update_rating_table(self) -> None:
        if self.rating_table_widget.rowCount() == 0:
            self.initialize_rating_table()

        _, cracks = self.view.engine_inputs()
        metrics = compute_metrics(cracks)
        assigned_rating = assign_iso23936_rating(cracks)
        values = table_values(metrics)

        for row, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.rating_table_widget.setItem(row, 1, item)

        for col in range(2, 7):
            for row in range(10):
                cell = self.rating_table_widget.item(row, col)
                if not cell:
                    continue
                if col == assigned_rating + 1:
                    cell.setBackground(Qt.GlobalColor.yellow)
                    cell.setForeground(Qt.GlobalColor.black)
                else:
                    cell.setData(Qt.ItemDataRole.BackgroundRole, None)
                    cell.setData(Qt.ItemDataRole.ForegroundRole, None)

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

    def select_image(self):
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not fname:
            return
        if not self.view.load_image(fname):
            QMessageBox.warning(self, "Load Failed", "Failed to load the selected image.")
            return
        self.current_image_path = fname
        self.view.set_mode('draw_perimeter')
        self._has_shown_crack_prompt = False
        self.show_perimeter_prompt()

    def clear_session(self):
        response = QMessageBox.question(
            self,
            "Clear Session?",
            "Are you sure you want to clear the session? All data will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            self.view.clear_overlays()
            self.view.set_mode('draw_perimeter')
            self._has_shown_crack_prompt = False
            self.refresh_tables()

    def saveCanvas(self, file_path: Optional[str] = None, suppress_conf: bool = False):
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Image",
                "",
                "PNG Files (*.png);;All Files (*)",
            )
        if file_path:
            pixmap = self.view.grab()
            pixmap.save(file_path)
            if not suppress_conf:
                QMessageBox.information(self, "Success", f"Image saved to {file_path}")

    def saveAsExcel(self):
        if not self.current_image_path:
            QMessageBox.warning(self, "No Image!", "No image has been loaded. Please load an image first.")
            return

        image_name = os.path.basename(self.current_image_path)
        base_name = os.path.splitext(image_name)[0]
        current_date = datetime.datetime.now().strftime("%m%d%Y")
        default_report_name = f"{base_name} - report - {current_date}.xlsx"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report",
            default_report_name,
            "Excel Files (*.xlsx);;All Files (*)",
        )

        if not file_path:
            return

        workbook = Workbook()
        image_sheet = workbook.active
        image_sheet.title = f"{base_name} Analysis"

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_image_path = temp_file.name
        self.saveCanvas(temp_image_path, suppress_conf=True)

        excel_image = Image(temp_image_path)
        image_sheet.add_image(excel_image, "B2")

        header_row = 2
        for col in range(self.rating_table_widget.columnCount()):
            header_item = self.rating_table_widget.horizontalHeaderItem(col)
            header_value = header_item.text() if header_item else ""
            header_cell = image_sheet.cell(row=header_row, column=12 + col)
            header_cell.value = header_value

        start_row = header_row + 1
        for row in range(self.rating_table_widget.rowCount()):
            for col in range(self.rating_table_widget.columnCount()):
                item = self.rating_table_widget.item(row, col)
                value = item.text() if item else ""
                cell = image_sheet.cell(row=start_row + row, column=12 + col)
                cell.value = value

        image_sheet.column_dimensions["L"].width = 50
        for col_letter in ["M", "N", "O", "P", "Q", "R"]:
            image_sheet.column_dimensions[col_letter].width = 20

        crack_sheet = workbook.create_sheet("Crack List")
        crack_sheet.append(["Crack #", "Type", "Length (% of CSD)"])
        for row in range(self.crack_table_widget.rowCount()):
            crack_sheet.append([
                self.crack_table_widget.item(row, 0).text() if self.crack_table_widget.item(row, 0) else "",
                self.crack_table_widget.item(row, 1).text() if self.crack_table_widget.item(row, 1) else "",
                self.crack_table_widget.item(row, 2).text() if self.crack_table_widget.item(row, 2) else "",
            ])

        workbook.save(file_path)
        QMessageBox.information(self, "Success", f"Report saved to {file_path}")
        os.remove(temp_image_path)

    def debug_current_rating(self):
        perimeter = self.view.get_perimeter_data()
        if len(perimeter.spline_points) < 3:
            QMessageBox.warning(self, "No Perimeter", "Please define a perimeter first.")
            return

        debug_info = self.get_rating_debug_info()

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

    def get_rating_debug_info(self) -> str:
        per = self.view.get_perimeter_data()
        if len(per.spline_points) < 3:
            return "No perimeter defined"

        csd_px, cracks = self.view.engine_inputs()

        info = ["CURRENT RATING DEBUG INFORMATION", "=" * 40]
        info.append(f"CSD: {csd_px:.2f} pixels")
        info.append(f"Number of cracks: {len(cracks)}")
        info.append("")

        total_length_percent = sum(length for _, length in cracks)
        internal_lengths = [length for ctype, length in cracks if ctype == "Internal"]
        external_lengths = [length for ctype, length in cracks if ctype == "External"]
        has_split = any(ctype == "Split" for ctype, _ in cracks)

        for idx, (ctype, length) in enumerate(cracks, start=1):
            info.append(f"Crack {idx}: {ctype}, {length:.2f}% CSD")

        info.append("")
        info.append("DETAILED METRICS FOR RATING DETERMINATION:")
        info.append("-" * 40)

        all_crack_lengths = internal_lengths + external_lengths

        info.append("Rating 1 Requirements:")
        all_below_25 = all(length < 25 for length in all_crack_lengths) if all_crack_lengths else True
        all_ext_below_10 = all(length < 10 for length in external_lengths) if external_lengths else True
        num_at_or_above_25 = sum(1 for length in all_crack_lengths if length >= 25)
        info.append(f"  Total length ≤100%: {total_length_percent:.2f}% ({'✓' if total_length_percent <= 100 else '✗'})")
        info.append(f"  All cracks <25%: {'✓' if all_below_25 else '✗'}")
        if not all_below_25:
            info.append(f"    → {num_at_or_above_25} crack(s) ≥25% CSD")
        info.append(f"  All external <10%: {'✓' if all_ext_below_10 else '✗'}")

        info.append("\nRating 2 Requirements:")
        all_below_50 = all(length < 50 for length in all_crack_lengths) if all_crack_lengths else True
        all_ext_below_25 = all(length < 25 for length in external_lengths) if external_lengths else True
        num_at_or_above_50 = sum(1 for length in all_crack_lengths if length >= 50)
        info.append(f"  Total length ≤200%: {total_length_percent:.2f}% ({'✓' if total_length_percent <= 200 else '✗'})")
        info.append(f"  All cracks <50%: {'✓' if all_below_50 else '✗'}")
        if not all_below_50:
            info.append(f"    → {num_at_or_above_50} crack(s) ≥50% CSD")
        info.append(f"  All external <25%: {'✓' if all_ext_below_25 else '✗'}")

        info.append("\nRating 3 Requirements:")
        internal_50_80_count = sum(1 for length in internal_lengths if 50 <= length <= 80)
        all_ext_below_50 = all(length < 50 for length in external_lengths) if external_lengths else True
        info.append(f"  Total length ≤300%: {total_length_percent:.2f}% ({'✓' if total_length_percent <= 300 else '✗'})")
        info.append(f"  ≤2 internal cracks 50-80%: {internal_50_80_count} ({'✓' if internal_50_80_count <= 2 else '✗'})")
        info.append(f"  All external <50%: {'✓' if all_ext_below_50 else '✗'}")

        info.append("\nRating 4 Triggers (any one triggers failure):")
        internal_above_80_count = sum(1 for length in internal_lengths if length > 80)
        internal_above_50_count = sum(1 for length in internal_lengths if length > 50)
        any_ext_above_50 = any(length > 50 for length in external_lengths) if external_lengths else False
        info.append(f"  Total >300%: {'✗' if total_length_percent > 300 else '✓'}")
        info.append(f"  ≥1 internal >80%: {internal_above_80_count} ({'✗' if internal_above_80_count >= 1 else '✓'})")
        info.append(f"  ≥3 internals >50%: {internal_above_50_count} ({'✗' if internal_above_50_count >= 3 else '✓'})")
        info.append(f"  Any external >50%: {'✗' if any_ext_above_50 else '✓'}")

        info.append("\nRating 5 Trigger:")
        info.append(f"  Any split present: {'✗' if has_split else '✓'}")

        info.append("\n" + "=" * 40)
        info.append("RATING DECISION TREE:")

        if not cracks:
            assigned_rating = 0
            info.append("No cracks → Rating 0")
        elif has_split:
            assigned_rating = 5
            info.append("Has split → Rating 5 (FAIL)")
        else:
            if total_length_percent <= 100 and all_below_25 and all_ext_below_10:
                assigned_rating = 1
                info.append("Meets Rating 1 conditions")
            elif (
                total_length_percent > 300
                or internal_above_80_count >= 1
                or internal_above_50_count >= 3
                or any_ext_above_50
            ):
                assigned_rating = 4
                info.append("Triggers Rating 4 conditions (FAIL)")
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
            elif total_length_percent <= 200 and all_below_50 and all_ext_below_25:
                assigned_rating = 2
                info.append("Meets Rating 2 conditions")
            elif total_length_percent <= 300 and internal_50_80_count <= 2 and all_ext_below_50:
                assigned_rating = 3
                info.append("Meets Rating 3 conditions")
            else:
                assigned_rating = 4
                info.append("Default to Rating 4 (no other conditions met)")

        info.append(f"\nFINAL RATING: {assigned_rating} - {'PASS' if assigned_rating <= 3 else 'FAIL'}")
        return "\n".join(info)

    def show_perimeter_prompt(self):
        QMessageBox.information(
            self,
            "Set Perimeter",
            "Use the left-mouse button to add points around the perimeter of the o-ring.\n\n"
            "When finished, click the middle mouse button to generate the loop and review the line fit.\n\n"
            "You may use the right-mouse button to delete any points or the fitted perimeter line before confirming.\n\n"
            "Once happy, click the middle mouse button again to confirm.\n",
        )

    def show_crack_prompt(self):
        QMessageBox.information(
            self,
            "Trace cracks",
            "Click and drag the left-mouse button to trace the visible cracks on the o-ring.\n\n"
            "Release the left-mouse button to confirm a crack and add it to the analysis.\n\n"
            "You may use the right-mouse button to delete any number of drawn cracks from the analysis.\n\n"
            "You can click the 'Clear Session' button to re-start the analysis.\n",
        )


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
