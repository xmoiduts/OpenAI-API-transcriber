"""Unit tests for sentence_builder.assemble_output helpers."""

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sentence_builder.assemble_output import (
    AssemblePart,
    AXIS_ORIGINAL_FILENAME,
    build_merged_text,
    placeholder_for_task,
    strip_trailing_punctuation,
    write_axis_original_atomic,
)


class TestStripTrailingPunctuation(unittest.TestCase):
    def test_strips_broad_run(self):
        text = "{1.0} {2.0} 你好！！！\n{3.0} {4.0} world...\n{5.0} {6.0} 完了。、，"
        out = strip_trailing_punctuation(text)
        self.assertEqual(
            out,
            "{1.0} {2.0} 你好\n{3.0} {4.0} world\n{5.0} {6.0} 完了",
        )

    def test_preserves_internal_punct(self):
        text = "{1.0} {2.0} 你好，世界"
        self.assertEqual(strip_trailing_punctuation(text), text)

    def test_empty(self):
        self.assertEqual(strip_trailing_punctuation(""), "")


class TestBuildMergedText(unittest.TestCase):
    def test_orders_by_task_index_and_placeholders(self):
        parts = [
            AssemblePart(2, (101, 200), "{2.0} {3.0} second\n", True),
            AssemblePart(1, (1, 100), "{0.0} {1.0} first\n", True),
            AssemblePart(3, (201, 300), "partial fail", False),
        ]
        merged = build_merged_text(parts)
        self.assertEqual(
            merged,
            "{0.0} {1.0} first\n"
            "{2.0} {3.0} second\n"
            "【sub-task 3 for lines 201-300】\n",
        )

    def test_manual_mergeable_partial_output(self):
        parts = [
            AssemblePart(1, (1, 10), "kept partial。", True),
            AssemblePart(2, (11, 20), "", False),
        ]
        merged = build_merged_text(parts)
        self.assertEqual(
            merged,
            "kept partial。\n"
            "【sub-task 2 for lines 11-20】\n",
        )

    def test_trims_outer_blank_lines_single_join(self):
        parts = [
            AssemblePart(1, (1, 1), "\n\nalpha\n\n", True),
            AssemblePart(2, (2, 2), "\nbeta\n", True),
        ]
        merged = build_merged_text(parts)
        self.assertEqual(merged, "alpha\nbeta\n")

    def test_empty_parts_still_trailing_newline(self):
        self.assertEqual(build_merged_text([]), "\n")

    def test_placeholder_format(self):
        self.assertEqual(
            placeholder_for_task(4, (50, 99)),
            "【sub-task 4 for lines 50-99】",
        )


class TestAtomicWrite(unittest.TestCase):
    def test_atomic_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = write_axis_original_atomic(root, "one\n")
            self.assertEqual(first.name, AXIS_ORIGINAL_FILENAME)
            self.assertEqual(first.read_text(encoding="utf-8"), "one\n")

            write_axis_original_atomic(root, "two\n")
            self.assertEqual(first.read_text(encoding="utf-8"), "two\n")
            leftovers = [
                p for p in root.iterdir() if p.name != AXIS_ORIGINAL_FILENAME
            ]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
