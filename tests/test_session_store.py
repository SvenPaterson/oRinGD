import datetime
import os
import tempfile
import unittest

from session_store import (
    SessionAnalysis,
    create_session_metadata,
    generate_project_code,
    load_session_file,
    save_session_file,
)


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


if __name__ == "__main__":
    unittest.main()
