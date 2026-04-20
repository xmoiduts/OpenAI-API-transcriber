import sys
import tempfile
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sentence_aligner.alignment_loader import build_aligned_rows, parse_axis_file, stable_sort_records


class TestAlignmentLoader(unittest.TestCase):
    def test_parse_axis_file_preserves_malformed_rows(self):
        records = self._parse_text(
            side="orig",
            text=(
                "{1.00} {2.00} alpha\n"
                "{2.00} beta\n"
                "{147b broken\n"
                "{1475.31s} broken2\n"
            ),
        )

        self.assertEqual(len(records), 4)
        self.assertEqual(
            [record.parse_status for record in records],
            ["valid_range", "valid_start_only", "invalid_time", "invalid_time"],
        )
        self.assertEqual(records[2].text, "broken")
        self.assertEqual(records[3].text, "broken2")

    def test_stable_sort_keeps_duplicate_and_invalid_rows_in_order(self):
        records = self._parse_text(
            side="orig",
            text=(
                "{10.00} {11.00} first\n"
                "{10.00} {11.50} duplicate\n"
                "{broken invalid\n"
                "{20.00} {21.00} last\n"
            ),
        )

        sorted_records = stable_sort_records(records)
        self.assertEqual(
            [record.text for record in sorted_records],
            ["first", "duplicate", "invalid", "last"],
        )

    def test_build_aligned_rows_expands_full_join_for_missing_and_invalid_rows(self):
        orig_records = self._parse_text(
            side="orig",
            text=(
                "{1.00} {2.00} orig1\n"
                "{2.00} {3.00} orig2\n"
                "{4.00} {5.00} orig4\n"
                "{147b orig-bad\n"
            ),
        )
        trans_records = self._parse_text(
            side="trans",
            text=(
                "{1.00} {2.00} trans1\n"
                "{3.00} {4.00} trans3\n"
                "{1475.31s} trans-bad\n"
            ),
        )

        rows = build_aligned_rows(orig_records, trans_records)

        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0].orig_record.text, "orig1")
        self.assertEqual(rows[0].trans_record.text, "trans1")

        self.assertEqual(rows[1].orig_record.text, "orig2")
        self.assertIsNone(rows[1].trans_record)
        self.assertTrue(rows[1].previewable)

        self.assertIsNone(rows[2].orig_record)
        self.assertEqual(rows[2].trans_record.text, "trans3")
        self.assertTrue(rows[2].previewable)

        self.assertEqual(rows[3].orig_record.text, "orig4")
        self.assertIsNone(rows[3].trans_record)

        self.assertEqual(rows[4].orig_record.text, "orig-bad")
        self.assertEqual(rows[4].trans_record.text, "trans-bad")
        self.assertFalse(rows[4].previewable)

    def test_duplicate_translation_timestamp_becomes_extra_row(self):
        orig_records = self._parse_text(
            side="orig",
            text=(
                "{1.00} {2.00} orig1\n"
                "{2.00} {3.00} orig2\n"
            ),
        )
        trans_records = self._parse_text(
            side="trans",
            text=(
                "{1.00} {2.00} trans1\n"
                "{1.00} {2.50} trans1-dup\n"
            ),
        )

        rows = build_aligned_rows(orig_records, trans_records)

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].orig_record.text, "orig1")
        self.assertEqual(rows[0].trans_record.text, "trans1")
        self.assertIsNone(rows[1].orig_record)
        self.assertEqual(rows[1].trans_record.text, "trans1-dup")
        self.assertEqual(rows[2].orig_record.text, "orig2")
        self.assertIsNone(rows[2].trans_record)

    def _parse_text(self, side: str, text: str):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / f"{side}.txt"
            path.write_text(text, encoding="utf-8")
            return parse_axis_file(path, side=side)


if __name__ == "__main__":
    unittest.main()
