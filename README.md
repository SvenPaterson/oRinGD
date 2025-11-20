# oRinGD - O-Ring Gas Decompression Analyzer

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![ISO 23936-2](https://img.shields.io/badge/ISO-23936--2-green.svg)](https://www.iso.org/standard/41948.html)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

oRinGD (O-Ring Gas Decompression) is a specialized image analysis tool for evaluating O-ring seal damage according to ISO 23936-2 Annex B standards. The application allows users to trace and quantify cracks in O-ring cross-sections, automatically calculating damage ratings for rapid gas decompression (RGD) testing.

## Key Features (User-Facing)

- **Interactive crack tracing** on O-ring cross-section images
- **Automatic crack classification** (color-coded):
   - Split (red)
   - External (yellow)
   - Internal (green)
- **Perimeter workflow** with preview: tentative (green) loop auto-updates after 5+ points, then locks blue on middle-click
- **ISO 23936-2 compliant** rating system (0–5 scale) with pass/fail result
- **Live metrics table** and rating thresholds side-by-side
- **Session summary tracking** with per-image finalize workflow
- **Canvas snapshots** stored in the session and exported into Excel reports
- **Excel report generation** with standardized-size annotated images (anchored at the top-left) and analysis tables on the right
- **Session persistence** via `.orngd` files with RDMS/project metadata and compatibility gating
- **Tabbed workspace** separating live analysis metrics from the session log
- **Resizable workspace** with splitter drag bars; optional layout debug mode saves preferences to `layout_prefs.json`
- **Debug Current Rating** view for step-by-step rating rationale

## Installation

### Prerequisites

- Python 3.8 or higher
- Windows, macOS, or Linux

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/oRinGD.git
cd oRinGD
```

2. Create a virtual environment (recommended) and install dependencies (Windows PowerShell example):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Using the App

### Running the Application

```powershell
.\.venv\Scripts\Activate.ps1
python main.py

# Optional: enable layout debugging to persist splitter/window sizes
python main.py --debug-layout
```

### Typical Workflow

1. **Start Session**
   - On launch, choose **Load Existing Session** (open an `.orngd`) or **Start New Session**.
   - New sessions require RDMS project number (≥4 digits), project name, and technician name; a project code like `RT-4567_Project-Name_YYYYMMDD` is generated.
2. **Load Image**
   - Click **Load Image** to select an O-ring cross-section image.
3. **Define Perimeter**
   - Left-click to drop perimeter points around the O-ring.
   - After 5+ points, a tentative green perimeter auto-appears and updates as you add/remove points.
   - Right-click a point to delete it; right-click with a confirmed loop clears the perimeter.
   - Middle-click once to confirm the drawn perimeter (turns blue) and switch to crack tracing.
4. **Trace Cracks**
   - Left-click and drag to trace visible cracks; release to finalize each crack.
   - Start a crack outside the perimeter and draw inwards to draw an external crack.
   - Start a crack outside the perimeter and finish outside the perimeter to draw a split
   - Cracks are automatically classified and drawn using the color key in the top-left:
     - Split (red), External (yellow), Internal (green).
   - Right-click near a crack to delete it; hold right-drag to pan.
5. **Finalize & Continue**
   - Middle-click in crack mode to finalize the analysis; a dialog lets you load another image, generate a report, or keep drawing.
   - Finalizing stores a canvas snapshot, appends a row in the **Session Summary** tab, and automatically saves the updated session back to the active `.orngd` file.
6. **Review Results**
   - The **Current Analysis** tab shows the live metrics and rating thresholds.
   - The overall rating (0–5) and pass/fail status are updated as you add/remove cracks.
7. **Manage Past Results**
   - In **Session Summary**, select a row and use **View Snapshot** to view the stored canvas image for that analysis.
   - Use **Delete Selected** to remove an entire past analysis (including its snapshot and metrics) from the session; changes are autosaved to the `.orngd` file.
8. **Export Excel Report**
   - Click **Save Report** to generate an `.xlsx` file for the current session.
   - Each analysis sheet contains the standardized-size snapshot anchored at cell `A1`, metadata at `O2`, rating table from `O9`, and crack table beneath it.

### Crack Classification Colors

- **Internal Crack** (Green): Both endpoints inside the perimeter.
- **External Crack** (Yellow): One endpoint on the perimeter.
- **Split Crack** (Red): Both endpoints on the perimeter (crosses completely).

### Rating System (ISO 23936-2)

| Rating | Result | Criteria |
|--------|--------|----------|
| 0 | PASS | No cracks present |
| 1 | PASS | Total ≤100% CSD, all cracks <25%, external <10% |
| 2 | PASS | Total ≤200% CSD, all cracks <50%, external <25% |
| 3 | PASS | Total ≤300% CSD, ≤2 internals 50-80%, external <50% |
| 4 | FAIL | Total >300% OR internal >80% OR ≥3 internals >50% OR external >50% |
| 5 | FAIL | Any split crack present |

*CSD = Cross-Sectional Diameter*

## Session Files (.orngd)

- Each session is stored as a zipped archive containing a `session.json` payload and embedded crack snapshots.
- Session metadata captures the RDMS number, project name, technician, and generated project code (`RT-XXXX_Project_YYYYMMDD`).
- A schema and app version are written into every file; newer files cannot be opened by older builds to avoid compatibility issues.
- Reload a saved session by choosing **Load Existing Session** at startup and pointing to the `.orngd` file.

## Testing (Developers)

Run tests from the project virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests
```

You can also target individual modules during development:

```powershell
python -m unittest tests.test_session_store -v
python -m unittest tests.test_iso23936_unittest -v
```

## Project Structure

```
oRinGD/
├── main.py                 # Main application and GUI
├── session_store.py        # Session metadata + persistence helpers
├── rating.py               # ISO 23936-2 rating engine
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── tests/
   ├── test_iso23936_unittest.py  # Unit tests for rating logic
   └── test_session_store.py      # Session persistence tests
```

## Architecture (Developers)

The application follows a separation of concerns:

- `main.py`: PyQt6 GUI, image/session workflow, Excel report generation.
- `canvas_gv.py`: Canvas scene/view, perimeter and crack drawing, snap/simplify logic.
- `rating.py`: Pure ISO 23936-2 rating logic.
- `session_store.py`: Session metadata, `.orngd` persistence, and compatibility checks.
- `tests/`: Unit tests for rating rules and session format.

## Debug Tools

- **Debug Current Rating** button opens a detailed text breakdown of all rating conditions and which ones triggered.
- Layout debug mode (`--debug-layout`) persists splitter/window sizes to `layout_prefs.json` for easy tuning.

## Requirements

See `requirements.txt` for full dependencies. Key packages:

- **PyQt6**: GUI framework
- **NumPy/SciPy**: Numerical computations and spline interpolation
- **OpenPyXL**: Excel report generation
- **Pillow**: Image processing support

## Release Notes / Feature History

- **v1.2.0**
   - Added automatic perimeter preview once 5+ points are placed, with live updates as points are added or removed.
   - Kept middle-mouse confirmation to lock perimeter (blue) before crack tracing.
   - Introduced crack-type color coding and legend overlay: Split (red), External (yellow), Internal (green).
   - Standardized exported canvas snapshot size and anchored snapshots at cell `A1` in per-analysis Excel sheets.
   - Moved per-analysis metadata, rating, and crack tables to start at column `O` to give the image more space.
- **v1.1.x**
   - Added session persistence via `.orngd` files with schema/app version gating.
   - Implemented Excel report generation with one sheet per analysis and a session summary.
   - Introduced layout debugging and persisted splitter/window sizes to `layout_prefs.json` when enabled.
- **v1.0.0**
   - Initial public version with manual perimeter definition, crack tracing, and ISO 23936-2 rating engine.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Run tests to ensure compliance (`python -m unittest tests.test_iso23936_unittest -v`)
4. Commit changes (`git commit -am 'Add new feature'`)
5. Push to branch (`git push origin feature/improvement`)
6. Create a Pull Request

## Standards Compliance

This software implements the damage rating system specified in:
- **ISO 23936-2:2011** - Petroleum, petrochemical and natural gas industries — Non-metallic materials in contact with media related to oil and gas production
- **Annex B** - Assessment of seal damage from rapid gas decompression

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Contact: stephen.garden@yourcompany.com

## Acknowledgments

- ISO TC 67 for standardization of RGD testing procedures
- Contributors to the NumPy and SciPy scientific computing libraries
- PyQt6 development team for the robust GUI framework

---

**Last Updated**: November 2025  
**Author**: Stephen Garden