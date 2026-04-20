# Sentence Aligner Axis Loader

## Scope

This document records the data contract introduced for `Sentence Aligner`
after it stopped reading `subtitles-bilang.srt` and started loading
`句轴原文.txt` and `句轴译文.txt` directly.

The UI itself is still experimental, but the parsing, row-building, and
preview-safety behavior are now explicit enough that they should be treated as
shared behavior rather than accidental implementation detail.

Primary code paths:

- `src/sentence_aligner/alignment_loader.py`
- `src/gui/sentence_aligner_tab.py`

## Source Resolution

`SentenceAlignerTab` resolves the active transcription result directory in this
order:

1. Prefer `MainWindow.asr_postprocess_tab.target_directory`
2. Fallback to the existing `file_path -> sanitize(stem) -> result_dir/<stem>`
   derivation

The tab only loads data when both files exist in the chosen directory:

- `句轴原文.txt`
- `句轴译文.txt`

If either file is missing, the table is cleared and waveform preview is also
cleared.

## Input Parsing Contract

Each non-empty input line is parsed into an `AxisRecord`.

Current fields:

- `side`: `orig` or `trans`
- `line_index`: original line order within that file
- `raw_line`: full source line
- `text`: remaining text payload after leading timestamp tokens
- `raw_time_text`: joined raw timestamp tokens for display/debugging
- `raw_start_token`
- `raw_end_token`
- `start_sec`
- `end_sec`
- `parse_status`
- `sort_anchor_sec`
- `sort_bucket`

### Accepted shapes

The parser is intentionally tolerant and does not require a fully valid pair of
timestamps.

Examples:

```text
{26.04} {28.92} 次回予告
{32.08} 世界で一番可愛いよ
{147b 破损时间戳
{1475.31s} malformed
```

### Parse statuses

- `valid_range`: both start and end parse as numeric seconds, and preview can
  use the full range
- `valid_start_only`: start parses but end is missing or broken
- `invalid_time`: no usable start timestamp could be parsed

Important: malformed rows are preserved. They are not dropped during loading.

## Stable Ordering Rules

Original and translation records are each sorted independently before joining.

The sort is intentionally stable:

- primary anchor: parsed `start_sec` when available
- malformed rows inherit the previous valid anchor so they stay near their
  original neighborhood
- original in-file order is preserved through `line_index`

This is meant to avoid reshuffling near-sorted source files when there are:

- duplicate start timestamps
- non-decreasing but stalled timestamps
- broken timestamp tokens

## Row-Building Contract

The join output is `AlignedRow`.

Current fields:

- `row_key`
- `orig_record`
- `trans_record`
- `display_time_text`
- `preview_start_sec`
- `preview_end_sec`
- `preview_text`
- `previewable`

### Join behavior

The join is "full-outer-like", not a normalization pass.

- If original and translation start times match within tolerance
  (`MATCH_TOLERANCE_SEC = 0.1`), they share one row
- If only one side is available at the current cursor, that side still becomes
  a row and the other side is left empty
- If both sides have malformed timestamps, they may still pair by ordered
  progression rather than being discarded

The goal is not to reconstruct a perfect subtitle file. The goal is to expose a
stable bilingual comparison view for manual inspection.

## Preview Safety Contract

Waveform preview must never rely on implicit table shape assumptions.

`SentenceAlignerTab` consumes `AlignedRow` as the source of truth:

- table row index maps to `aligned_rows[row]`
- preview only starts when `previewable` is true and both
  `preview_start_sec` / `preview_end_sec` are present
- if the selected row has no safe preview window, the waveform area is cleared
  instead of reusing the previous preview

This avoids two failure modes:

1. rows with only one-sided or malformed data crashing due to missing keys
2. reordered rows previewing the wrong timeline segment

## Preview Window Selection

`AlignedRow` preview metadata is chosen conservatively:

1. Prefer the first side that has a valid `[start, end]` range
2. Otherwise try to combine a valid start from one side with a valid end from
   the other side
3. If no safe range can be formed, mark the row as non-previewable

`preview_text` currently prefers original text, then falls back to translation
text.

## Current Table Mapping

The current table columns are:

`Time (Original) | Original | Time (Translation) | Translation`

Time-cell behavior:

- default cell text strips outer braces and keeps second-based values, for
  example `1152.92 -> 1153.44`
- hover tooltip shows formatted clock time
- when duration is below one hour, tooltip format is `MM:SS.xx`
- when duration reaches one hour or more, tooltip format is `H:MM:SS.xx`

This presentation logic lives in `src/gui/sentence_aligner_tab.py` and should be
treated as UI formatting, not as canonical parsing.

## Non-Goals

This loader does not:

- repair broken timestamps upstream
- rewrite sentence-axis files
- guarantee linguistically correct alignment
- replace the bilingual SRT generator

Its responsibility is limited to tolerant loading, stable row construction, and
safe preview metadata for the experimental aligner UI.
