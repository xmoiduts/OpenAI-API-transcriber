from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


MATCH_TOLERANCE_SEC = 0.1
_FLOAT_PATTERN = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class AxisRecord:
    side: str
    line_index: int
    raw_line: str
    text: str
    raw_time_text: str
    raw_start_token: str
    raw_end_token: str
    start_sec: float | None
    end_sec: float | None
    parse_status: str
    sort_anchor_sec: float
    sort_bucket: int

    @property
    def has_valid_start(self) -> bool:
        return self.start_sec is not None

    @property
    def has_valid_range(self) -> bool:
        return (
            self.start_sec is not None
            and self.end_sec is not None
            and self.end_sec >= self.start_sec
        )


@dataclass(frozen=True)
class AlignedRow:
    row_key: str
    orig_record: AxisRecord | None
    trans_record: AxisRecord | None
    display_time_text: str
    preview_start_sec: float | None
    preview_end_sec: float | None
    preview_text: str
    previewable: bool


def load_aligned_rows(orig_path: Path, trans_path: Path) -> list[AlignedRow]:
    orig_records = parse_axis_file(orig_path, side="orig")
    trans_records = parse_axis_file(trans_path, side="trans")
    return build_aligned_rows(orig_records, trans_records)


def parse_axis_file(path: Path, side: str) -> list[AxisRecord]:
    records: list[AxisRecord] = []
    previous_valid_start: float | None = None

    for raw_index, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not raw_line.strip():
            continue

        raw_start_token, raw_end_token, text = _split_axis_line(raw_line)
        start_sec = _parse_time_token(raw_start_token)
        end_sec = _parse_time_token(raw_end_token)
        parse_status = _classify_parse_status(raw_start_token, raw_end_token, start_sec, end_sec)

        if start_sec is not None:
            sort_anchor_sec = start_sec
            previous_valid_start = start_sec
            sort_bucket = 0
        else:
            sort_anchor_sec = previous_valid_start if previous_valid_start is not None else -1.0
            sort_bucket = 1

        records.append(
            AxisRecord(
                side=side,
                line_index=raw_index,
                raw_line=raw_line,
                text=text,
                raw_time_text=" ".join(
                    token for token in (raw_start_token, raw_end_token) if token
                ).strip(),
                raw_start_token=raw_start_token,
                raw_end_token=raw_end_token,
                start_sec=start_sec,
                end_sec=end_sec,
                parse_status=parse_status,
                sort_anchor_sec=sort_anchor_sec,
                sort_bucket=sort_bucket,
            )
        )

    return records


def build_aligned_rows(
    orig_records: list[AxisRecord],
    trans_records: list[AxisRecord],
    tolerance_sec: float = MATCH_TOLERANCE_SEC,
) -> list[AlignedRow]:
    orig_sorted = stable_sort_records(orig_records)
    trans_sorted = stable_sort_records(trans_records)

    rows: list[AlignedRow] = []
    orig_idx = 0
    trans_idx = 0

    while orig_idx < len(orig_sorted) or trans_idx < len(trans_sorted):
        orig = orig_sorted[orig_idx] if orig_idx < len(orig_sorted) else None
        trans = trans_sorted[trans_idx] if trans_idx < len(trans_sorted) else None

        if orig is None:
            rows.append(_build_row(None, trans))
            trans_idx += 1
            continue

        if trans is None:
            rows.append(_build_row(orig, None))
            orig_idx += 1
            continue

        if _records_match(orig, trans, tolerance_sec):
            rows.append(_build_row(orig, trans))
            orig_idx += 1
            trans_idx += 1
            continue

        if _comes_before(orig, trans):
            rows.append(_build_row(orig, None))
            orig_idx += 1
        else:
            rows.append(_build_row(None, trans))
            trans_idx += 1

    return rows


def stable_sort_records(records: list[AxisRecord]) -> list[AxisRecord]:
    return sorted(records, key=_record_sort_key)


def _split_axis_line(line: str) -> tuple[str, str, str]:
    remaining = line.lstrip()
    tokens: list[str] = []

    for _ in range(2):
        token, remaining = _consume_leading_token(remaining)
        if not token:
            break
        tokens.append(token)
        remaining = remaining.lstrip()

    text = remaining.strip()
    if not text and tokens:
        text = line.strip()

    raw_start = tokens[0] if len(tokens) > 0 else ""
    raw_end = tokens[1] if len(tokens) > 1 else ""
    return raw_start, raw_end, text


def _consume_leading_token(text: str) -> tuple[str, str]:
    if not text.startswith("{"):
        return "", text

    closing_brace = text.find("}")
    if closing_brace != -1:
        token = text[: closing_brace + 1]
        remaining = text[closing_brace + 1 :]
        return token, remaining

    parts = text.split(maxsplit=1)
    token = parts[0]
    remaining = parts[1] if len(parts) > 1 else ""
    return token, remaining


def _parse_time_token(raw_token: str) -> float | None:
    if not raw_token:
        return None

    token = raw_token.strip()
    if token.startswith("{"):
        token = token[1:]
    if token.endswith("}"):
        token = token[:-1]
    token = token.strip()

    if not _FLOAT_PATTERN.fullmatch(token):
        return None
    return float(token)


def _classify_parse_status(
    raw_start_token: str,
    raw_end_token: str,
    start_sec: float | None,
    end_sec: float | None,
) -> str:
    if start_sec is None:
        return "invalid_time"
    if not raw_end_token or end_sec is None:
        return "valid_start_only"
    return "valid_range"


def _records_match(orig: AxisRecord, trans: AxisRecord, tolerance_sec: float) -> bool:
    if orig.start_sec is not None and trans.start_sec is not None:
        return abs(orig.start_sec - trans.start_sec) <= tolerance_sec

    return orig.start_sec is None and trans.start_sec is None


def _comes_before(left: AxisRecord, right: AxisRecord) -> bool:
    if left.has_valid_start != right.has_valid_start:
        return left.has_valid_start
    return _record_sort_key(left) <= _record_sort_key(right)


def _record_sort_key(record: AxisRecord) -> tuple[float, int, int]:
    return (record.sort_anchor_sec, record.sort_bucket, record.line_index)


def _build_row(orig: AxisRecord | None, trans: AxisRecord | None) -> AlignedRow:
    preview_start_sec, preview_end_sec, previewable = _choose_preview_window(orig, trans)
    preview_text = _pick_preview_text(orig, trans)

    row_key_parts = []
    if orig is not None:
        row_key_parts.append(f"orig-{orig.line_index}")
    if trans is not None:
        row_key_parts.append(f"trans-{trans.line_index}")

    return AlignedRow(
        row_key="+".join(row_key_parts) if row_key_parts else "empty",
        orig_record=orig,
        trans_record=trans,
        display_time_text=_pick_display_time_text(orig, trans),
        preview_start_sec=preview_start_sec,
        preview_end_sec=preview_end_sec,
        preview_text=preview_text,
        previewable=previewable,
    )


def _choose_preview_window(
    orig: AxisRecord | None,
    trans: AxisRecord | None,
) -> tuple[float | None, float | None, bool]:
    for record in (orig, trans):
        if record is not None and record.has_valid_range:
            return record.start_sec, record.end_sec, True

    start_sec = None
    for record in (orig, trans):
        if record is not None and record.start_sec is not None:
            start_sec = record.start_sec
            break

    if start_sec is None:
        return None, None, False

    for record in (orig, trans):
        if (
            record is not None
            and record.end_sec is not None
            and record.end_sec >= start_sec
        ):
            return start_sec, record.end_sec, True

    return start_sec, None, False


def _pick_preview_text(orig: AxisRecord | None, trans: AxisRecord | None) -> str:
    if orig is not None and orig.text:
        return orig.text
    if trans is not None and trans.text:
        return trans.text
    return ""


def _pick_display_time_text(orig: AxisRecord | None, trans: AxisRecord | None) -> str:
    labels = []
    if orig is not None and orig.raw_time_text:
        labels.append(orig.raw_time_text)
    if trans is not None and trans.raw_time_text and trans.raw_time_text not in labels:
        labels.append(trans.raw_time_text)
    return " | ".join(labels)
