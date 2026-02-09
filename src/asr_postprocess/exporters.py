"""
Export/transcode utilities for ASR postprocessing.

This module contains file-export related helpers that were previously placed in
`src.asr_postprocess.core`. Keeping export logic here makes `core.py` smaller
and lets scripts/GUI reuse a single formatting definition.
"""

from __future__ import annotations

import json
import os
import unicodedata

from .utils import find_cut_result_json_files


def _format_offset_word_field(word: str) -> str:
    """
    Format word field for offset (start/end) exports.

    Requirement:
    - Do NOT quote normal words (even if they contain spaces).
    - ONLY quote whitespace-only words (e.g. a single space " ") so that the
      content remains visible and is not lost when trimming/splitting.
    """
    if word.strip() == "":
        word_escaped = word.replace('"', '""')
        return f'"{word_escaped}"'
    return word


def _is_invisible_only_token(word: str) -> bool:
    """
    True if `word` consists ONLY of "invisible" Unicode format characters (category Cf),
    optionally surrounded by normal whitespace.

    Why:
    - Some Whisper outputs contain tokens like ZWSP (U+200B) / BOM (U+FEFF) as standalone
      "words". These are not meaningful and should be removed.
    - BUT whitespace-only tokens (e.g. a single space) are meaningful in this project and
      must be preserved (they are quoted as `" "` by `_format_offset_word_field`).
    """
    if word == "":
        # Keep empty tokens as-is to avoid surprising behavior changes; callers may still
        # quote them if needed.
        return False

    saw_non_space = False
    for ch in word:
        if ch.isspace():
            continue
        saw_non_space = True
        if unicodedata.category(ch) != "Cf":
            return False
    return saw_non_space


def convert_raw_json_to_csv(target_directory: str, output_filename: str = "word_timestamps.csv") -> str:
    """
    Convert word-level timestamps from all _cut_result.json files to a single CSV-like text file.

    Output format (offset mode): each line
      {start_seconds_2dp} {end_seconds_2dp} {word}

    Note:
    - Words are not quoted by default.
    - Whitespace-only words (e.g. " ") are wrapped in quotes to remain visible.
    """
    json_files = find_cut_result_json_files(target_directory)

    all_rows: list[str] = []
    for file_path in json_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "words" in data and isinstance(data["words"], list):
                for word_entry in data["words"]:
                    start = float(word_entry.get("start", 0.0))
                    end = float(word_entry.get("end", 0.0))
                    word = str(word_entry.get("word", ""))

                    start_str = f"{start:.2f}"
                    end_str = f"{end:.2f}"
                    word_field = _format_offset_word_field(word)

                    all_rows.append(f"{start_str} {end_str} {word_field}")

    if not all_rows:
        raise ValueError("No word-level timestamps found in the JSON files.")

    output_file_path = os.path.join(target_directory, output_filename)
    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_rows))

    return output_file_path


def convert_merged_json_to_csv(target_directory: str, output_filename: str = "merged_word_timestamps.csv") -> str:
    """
    Convert the merged JSON file to word timestamp CSV-like text file.

    The merged JSON has words as tuples: (start, end, word, [optional "punctuation"])

    Output format (offset mode): each line
      {start_seconds_2dp} {end_seconds_2dp} {word}

    Note:
    - Words are not quoted by default.
    - Whitespace-only words (e.g. " ") are wrapped in quotes to remain visible.
    """
    dir_name = os.path.basename(target_directory)
    merged_json_path = os.path.join(target_directory, f"merged_{dir_name}.json")

    if not os.path.exists(merged_json_path):
        raise FileNotFoundError(
            f"Merged JSON file not found: {merged_json_path}\n"
            "Please run 'Merge Whisper JSON' first."
        )

    with open(merged_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "words" not in data or not isinstance(data["words"], list):
        raise ValueError("No words found in merged JSON file.")

    # Step 1: build normalized (start_str, end_str, word) rows and drop invisible-only tokens.
    rows: list[tuple[str, str, str]] = []
    for word_entry in data["words"]:
        if isinstance(word_entry, (list, tuple)) and len(word_entry) >= 3:
            start_time = float(word_entry[0])
            end_time = float(word_entry[1])
            word = str(word_entry[2])

            start_str = f"{start_time:.2f}"
            end_str = f"{end_time:.2f}"

            if _is_invisible_only_token(word):
                continue

            rows.append((start_str, end_str, word))

    if not rows:
        raise ValueError("No word timestamps found in merged JSON.")

    # Step 2: merge adjacent rows with identical (start,end) by appending later token to former.
    # Per requirement: only handle the common 2-line case; do NOT attempt to fold 3+ rows.
    merged_rows: list[tuple[str, str, str]] = []
    i = 0
    while i < len(rows):
        start_str, end_str, word = rows[i]
        if i + 1 < len(rows) and rows[i + 1][0] == start_str and rows[i + 1][1] == end_str:
            word = word + rows[i + 1][2]
            merged_rows.append((start_str, end_str, word))
            i += 2
            continue
        merged_rows.append((start_str, end_str, word))
        i += 1

    all_rows: list[str] = []
    for start_str, end_str, word in merged_rows:
        word_field = _format_offset_word_field(word)
        all_rows.append(f"{start_str} {end_str} {word_field}")

    output_file_path = os.path.join(target_directory, output_filename)
    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_rows))

    return output_file_path


def convert_merged_json_to_delta_csv(
    target_directory: str, output_filename: str = "merged_words_centi_delta.csv"
) -> str:
    """
    Convert merged JSON to delta format CSV with centisecond timestamps.

    Output format (Mode 3: word-timestamp, delta)
    Each line: {start_centiseconds} +{duration_centiseconds} {word}
    """
    dir_name = os.path.basename(target_directory)
    merged_json_path = os.path.join(target_directory, f"merged_{dir_name}.json")

    if not os.path.exists(merged_json_path):
        raise FileNotFoundError(
            f"Merged JSON file not found: {merged_json_path}\n"
            "Please run 'Merge Whisper JSON' first."
        )

    with open(merged_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "words" not in data or not isinstance(data["words"], list):
        raise ValueError("No words found in merged JSON file.")

    all_rows: list[str] = []
    for word_entry in data["words"]:
        if isinstance(word_entry, (list, tuple)) and len(word_entry) >= 3:
            start_time = float(word_entry[0])  # in seconds (float)
            end_time = float(word_entry[1])  # in seconds (float)
            word = str(word_entry[2])

            start_cs = round(start_time * 100)
            end_cs = round(end_time * 100)
            duration_cs = end_cs - start_cs

            # Keep existing robust quoting rules for delta mode
            if word.strip() == "" or " " in word:
                word_escaped = word.replace('"', '""')
                word_field = f'"{word_escaped}"'
            else:
                word_field = word

            all_rows.append(f"{start_cs} +{duration_cs} {word_field}")

    if not all_rows:
        raise ValueError("No word timestamps found in merged JSON.")

    output_file_path = os.path.join(target_directory, output_filename)
    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_rows))

    return output_file_path

