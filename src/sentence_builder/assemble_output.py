"""
Pure helpers for Assemble Sentence post-processing and merge.

Rules:
- Trailing punctuation: strip a run of ，。、,.．!?！？… from each line end
- Merge: ordered by 1-based task index; mergeable parts write body text;
  non-mergeable parts write a searchable full-width placeholder
- Join: strip leading/trailing blank lines per part, join with a single
  newline, keep one trailing newline on the final file text
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

TRAILING_PUNCT_CHARS = "，。、,.．!?！？…"
_TRAILING_PUNCT_RE = re.compile(rf"[{re.escape(TRAILING_PUNCT_CHARS)}]+$")

AXIS_ORIGINAL_FILENAME = "句轴原文.txt"


def strip_trailing_punctuation(text: str) -> str:
    """Remove a trailing run of common CJK/Latin sentence punctuation per line."""
    if not text:
        return text
    lines = text.split("\n")
    return "\n".join(_TRAILING_PUNCT_RE.sub("", line) for line in lines)


def placeholder_for_task(task_index: int, line_range: Tuple[int, int]) -> str:
    """Build the searchable placeholder for a non-mergeable sub-task."""
    start, end = line_range
    return f"【sub-task {task_index} for lines {start}-{end}】"


def _trim_outer_blank_lines(text: str) -> str:
    """Strip leading/trailing blank lines while preserving internal blanks."""
    if not text:
        return ""
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


@dataclass(frozen=True)
class AssemblePart:
    """One assemble sub-task contribution for merge."""

    task_index: int  # 1-based
    line_range: Tuple[int, int]
    text: str
    mergeable: bool


def build_merged_text(parts: Sequence[AssemblePart]) -> str:
    """Concatenate ordered parts into the final 句轴原文 body."""
    ordered = sorted(parts, key=lambda p: p.task_index)
    chunks: List[str] = []
    for part in ordered:
        if part.mergeable:
            chunk = _trim_outer_blank_lines(part.text or "")
        else:
            chunk = placeholder_for_task(part.task_index, part.line_range)
        if chunk:
            chunks.append(chunk)
    if not chunks:
        return "\n"
    return "\n".join(chunks) + "\n"


def write_axis_original_atomic(result_dir: Path, content: str) -> Path:
    """Atomically write content to ``{result_dir}/句轴原文.txt``."""
    result_dir = Path(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    target = result_dir / AXIS_ORIGINAL_FILENAME

    fd, tmp_name = tempfile.mkstemp(
        prefix=".句轴原文_",
        suffix=".tmp",
        dir=str(result_dir),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target
