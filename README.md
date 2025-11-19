# oRinGD - O-Ring Gas Decompression Analyzer

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![ISO 23936-2](https://img.shields.io/badge/ISO-23936--2-green.svg)](https://www.iso.org/standard/41948.html)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

oRinGD (O-Ring Gas Decompression) is a specialized image analysis tool for evaluating O-ring seal damage according to ISO 23936-2 Annex B standards. The application allows users to trace and quantify cracks in O-ring cross-sections, automatically calculating damage ratings for rapid gas decompression (RGD) testing.

Built with the help of AI because I just don't have time to git gud and write this from scratch myself.

## Features

- **Interactive crack tracing** on O-ring cross-section images
- **Automatic crack classification**: Internal, External, or Split cracks
- **ISO 23936-2 compliant** rating system (0-5 scale)
- **Real-time damage assessment** with pass/fail determination
- **Detailed metrics tracking** for quality control
- **Session summary tracking** with per-image finalize workflow
- **Tabbed workspace** separating live analysis metrics from the session log
- **Excel report generation** with annotated images
- **Comprehensive debug tools** for rating verification

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

2. Create a virtual environment (recommended):
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Application

```bash
python main.py
```

### Workflow

1. **Load Image**: Click "Load / Next Image" to load an O-ring cross-section image
2. **Define Perimeter**: 
   - Left-click to add points around the O-ring perimeter
   - Middle-click to generate the perimeter spline
   - Right-click to remove points (before confirming)
   - Middle-click again to confirm the perimeter
3. **Trace Cracks**:
   - Left-click and drag to trace visible cracks
   - Cracks are automatically classified by type
   - Right-click near a crack to delete it
4. **View Results**:
   - Rating is calculated automatically per ISO 23936-2
   - Table shows individual crack metrics
   - Overall pass/fail determination displayed
5. **Review Metrics vs. Session Log**:
   - Use the bottom tabs to switch between **Current Analysis** (all rating metrics, no scrolling needed) and **Session Summary** (scrollable, compact table)
   - The session table keeps a running list of every O-ring analyzed in the current run (handy for 50+ sections)
6. **Finalize & Start Next**:
   - Click **Finalize Analysis** to lock in the current rating and add it to the session summary table
   - Use **Load / Next Image** to immediately begin the next analysis
7. **Manage Past Results**:
   - Highlight a row in the session table and click **Edit Selected** to reload that image and redo the measurements
   - Click **Delete Selected** to remove an entry that you no longer need in the session log
8. **Export Report**: Click **Save Report** before finalizing if you need a canvas + metrics snapshot for the active image

### Crack Classification

- **Internal Crack** (Blue): Both endpoints inside the perimeter
- **External Crack** (Yellow): One endpoint on the perimeter  
- **Split Crack** (Red): Both endpoints on the perimeter (crosses completely)

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

## Testing

Run the test suite to verify ISO 23936-2 compliance:

```bash
# Run all tests with verbose output
python -m unittest tests.test_iso23936_unittest -v

# Run tests from the GUI
# Click "Run Validation Tests" button in the application
```

## Project Structure

```
oRinGD/
├── main.py                 # Main application and GUI
├── rating.py               # ISO 23936-2 rating engine
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── tests/
    └── test_iso23936_unittest.py  # Unit tests for rating logic
```

## Architecture

The application follows a clean separation of concerns:

- **main.py**: PyQt6 GUI handling, image processing, and user interaction
- **rating.py**: Pure business logic for ISO 23936-2 compliance
- **tests/**: Comprehensive test coverage for rating algorithms

## Debug Tools

The application includes built-in debugging capabilities:

- **Debug Current Rating**: Detailed breakdown of why a specific rating was assigned
- **Console Output**: Real-time metric calculations during crack analysis
- **Test Validation**: Automated testing against known ISO 23936-2 scenarios

## Requirements

See `requirements.txt` for full dependencies. Key packages:

- **PyQt6**: GUI framework
- **NumPy/SciPy**: Numerical computations and spline interpolation
- **OpenPyXL**: Excel report generation
- **Pillow**: Image processing support

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

**Version**: 1.0.0  
**Last Updated**: January 2025  
**Author**: Stephen Garden