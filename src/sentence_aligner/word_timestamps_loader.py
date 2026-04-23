"""
Word timestamps loader for the Sentence Aligner tab.

Reads a `merged_word_timestamps.csv`-style file (see
`doc/multi-mode-word-timestamp-csv.md`) and produces a `WordTimeline` that
supports fast viewport queries via `np.searchsorted`.

Design notes:
- Input may be sorted, nearly-sorted, or contain format-broken lines.
- We parse tolerantly (malformed rows are skipped and counted), then stably
  sort by start time so later query logic can rely on monotonic `starts`.
- `query(view_start, view_end)` runs in O(log N + k), where k is the number
  of entries overlapping the viewport. This keeps per-paint cost constant
  for large sessions (100k+ merged-project scale).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from src.scripts.rangetime import parse_line


@dataclass(frozen=True)
class WordTimeline:
    starts: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    ends: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    texts: tuple[str, ...] = ()
    max_duration: float = 0.0
    bad_line_count: int = 0

    def __len__(self) -> int:
        return int(self.starts.size)

    def is_empty(self) -> bool:
        return self.starts.size == 0

    def query(self, view_start: float, view_end: float) -> np.ndarray:
        """Return sorted indices whose [start, end] intersects [view_start, view_end]."""
        if self.starts.size == 0 or view_end <= view_start:
            return np.empty(0, dtype=np.int64)

        lookback = max(self.max_duration, 0.0)
        lo = int(np.searchsorted(self.starts, view_start - lookback, side="left"))
        hi = int(np.searchsorted(self.starts, view_end, side="right"))
        if hi <= lo:
            return np.empty(0, dtype=np.int64)

        window_ends = self.ends[lo:hi]
        mask = window_ends > view_start
        hits = np.nonzero(mask)[0]
        if hits.size == 0:
            return np.empty(0, dtype=np.int64)
        return (hits + lo).astype(np.int64)


def load_word_timeline(path: Path) -> WordTimeline:
    """Parse a word-timestamp CSV and produce a sorted WordTimeline.

    Malformed rows are skipped; their count is recorded in `bad_line_count`.
    Missing files yield an empty timeline (not an error).
    """
    if not path.exists():
        return WordTimeline()

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return WordTimeline()

    entries: list[tuple[float, float, str]] = []
    bad_line_count = 0

    for raw_line in raw_text.splitlines():
        if not raw_line.strip():
            continue

        parsed = parse_line(raw_line)
        if parsed is None:
            bad_line_count += 1
            continue

        start, end, text = parsed
        if end < start:
            bad_line_count += 1
            continue
        if start == 0.0 and end == 0.0:
            bad_line_count += 1
            continue

        entries.append((start, end, text))

    if not entries:
        return WordTimeline(bad_line_count=bad_line_count)

    entries.sort(key=lambda item: item[0])

    starts = np.fromiter((e[0] for e in entries), dtype=np.float64, count=len(entries))
    ends = np.fromiter((e[1] for e in entries), dtype=np.float64, count=len(entries))
    texts = tuple(e[2] for e in entries)

    durations = ends - starts
    max_duration = float(durations.max()) if durations.size else 0.0
    max_duration = max(max_duration, 0.0)

    return WordTimeline(
        starts=starts,
        ends=ends,
        texts=texts,
        max_duration=max_duration,
        bad_line_count=bad_line_count,
    )
