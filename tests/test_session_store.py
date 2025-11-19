import datetime
import json
import os
import tempfile
import unittest
import zipfile

from session_store import (
    APP_VERSION,
    SESSION_SCHEMA_VERSION,
    SessionAnalysis,
    SessionVersionError,
    create_session_metadata,
    generate_project_code,
    load_session_file,
    save_session_file,
)


def _write_session_archive(directory: str, *, schema_version: int, app_version: str) -> str:
    """Create a synthetic `.orngd` file for compatibility tests."""
    payload = {
        "schema_version": schema_version,
        "app_version": app_version,
        "metadata": {
            "rdms_project_number": "55555",
            "project_name": "Legacy Session",
            "technician_name": "Test Tech",
            "project_code": "RT-55555_Legacy_20250201",
            "created_at": "2025-02-01T10:00:00",
            "updated_at": "2025-02-01T10:05:00",
            "schema_version": schema_version,
            "app_version": app_version,
        },
        "analyses": [
            {
                "index": 1,
                "image_name": "legacy.png",
                "image_path": "C:/data/legacy.png",
                "completed_at": "2025-02-01T10:04:00",
                "crack_count": 1,
                "total_pct": 45.0,
                "rating": 2,
                "result": "Pass",
                "cracks": [["Internal", 45.0]],
                "snapshot_png": None,
            }
        ],
    }

    archive_path = os.path.join(directory, f"schema_{schema_version}_app_{app_version}.orngd")
    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("session.json", json.dumps(payload, indent=2).encode("utf-8"))
    return archive_path


def _bump_version(version: str, part: str) -> str:
    parts = [int(piece) for piece in version.split(".")]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts[:3]
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


class SessionStoreTests(unittest.TestCase):
    def test_generate_project_code_format(self):
        fake_date = datetime.datetime(2025, 1, 15)
        code = generate_project_code("98765", "Project Alpha", fake_date)
        self.assertTrue(code.startswith("RT-98765_Project-Alpha_20250115"))

    def test_round_trip_save_and_load(self):
        metadata = create_session_metadata("12345", "Hydrogen Analysis", "Dr. Ada")
        record = SessionAnalysis(
            index=1,
            image_name="sample.png",
            image_path="/tmp/sample.png",
            completed_at=datetime.datetime(2025, 1, 1, 12, 0, 0),
            crack_count=2,
            total_pct=150.0,
            rating=3,
            result="Pass",
            cracks=[("Internal", 75.0), ("External", 25.0)],
            snapshot_png=b"demo-bytes",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "round-trip.orngd")
            save_session_file(file_path, metadata, [record])
            state = load_session_file(file_path)

        self.assertEqual(state.metadata.rdms_project_number, "12345")
        self.assertEqual(len(state.records), 1)
        loaded_record = state.records[0]
        self.assertEqual(loaded_record.image_name, "sample.png")
        self.assertEqual(len(loaded_record.cracks), 2)
        self.assertEqual(loaded_record.cracks[0][0], "Internal")
        self.assertEqual(loaded_record.cracks[0][1], 75.0)
        self.assertEqual(loaded_record.snapshot_png, b"demo-bytes")

    def test_loads_legacy_session_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_file = _write_session_archive(
                tmpdir,
                schema_version=SESSION_SCHEMA_VERSION,
                app_version="1.0.0",
            )
            state = load_session_file(legacy_file)

        self.assertEqual(state.metadata.project_name, "Legacy Session")
        self.assertEqual(len(state.records), 1)
        self.assertEqual(state.records[0].crack_count, 1)

    def test_newer_minor_version_is_permitted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            compat_file = _write_session_archive(
                tmpdir,
                schema_version=SESSION_SCHEMA_VERSION,
                app_version=_bump_version(APP_VERSION, "minor"),
            )

            state = load_session_file(compat_file)

        self.assertEqual(state.metadata.project_name, "Legacy Session")

    def test_newer_major_version_raises_version_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            future_file = _write_session_archive(
                tmpdir,
                schema_version=SESSION_SCHEMA_VERSION,
                app_version=_bump_version(APP_VERSION, "major"),
            )

            with self.assertRaises(SessionVersionError):
                load_session_file(future_file)

    def test_newer_schema_version_raises_version_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            newer_schema_file = _write_session_archive(
                tmpdir,
                schema_version=SESSION_SCHEMA_VERSION + 1,
                app_version=APP_VERSION,
            )

            with self.assertRaises(SessionVersionError):
                load_session_file(newer_schema_file)


if __name__ == "__main__":
    unittest.main()
