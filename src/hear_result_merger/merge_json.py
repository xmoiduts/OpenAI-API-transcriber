#!/usr/bin/env python3

import json
import sys
import os
from typing import List, Dict, Tuple
import difflib
from collections import OrderedDict
import re
import time
from merge_json_algo import *

class OrderedEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, OrderedDict):
            return {k: self.default(v) for k, v in obj.items()}
        return super().default(obj)

def load_json(file_path: str) -> Dict:
    """Load JSON file."""
    print(f"loading file {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file {file_path}.", file=sys.stderr)
        sys.exit(1)

def parse_filename(filename: str) -> tuple:
    """Parse filename to extract start time and duration."""
    match = re.search(r'_ss(\d+)-t(\d+)\.json$', filename)
    if match:
        return int(match.group(1)), int(match.group(2)) # start at, duration
    raise ValueError(f"Invalid filename format: {filename}")

def extract_sort_key(filename: str) -> int:
    """Extract the start time part from the filename."""
    start_time, _ = parse_filename(filename)
    return start_time

def round_timestamp(timestamp: float) -> float:
    """Round timestamp to 0.01 second precision."""
    return round(timestamp, 2)

def initialize_json_file_names_and_transcript_segments(folder_name: str) -> Tuple[
    List[str], List[Tuple[float, float]]]:
    """
    Initialize JSON file names and transcript segment times for a given title prefix.

    Args:
    folder_name (str): Title prefix to filter JSON files.

    Returns:
    Tuple[List[str], List[Tuple[float, float]]]: 
        - Sorted list of JSON file names.
        - List of transcript segment times (start, end).

    Note:
    Assumes 'extract_sort_key', 'load_json', and 'parse_filename' functions exist.
    JSON files are expected in '<project-root>/transcription_result/'.
    """
    base_path = f"./transcription_result/{folder_name}"
    json_files = [f for f in os.listdir(base_path) 
                  if f.startswith(folder_name) and f.endswith('.json')]
    json_files.sort(key=extract_sort_key)
    transcript_segments = [] # [(0, 35.00), (30.00, 65.00), ...]
    for file in json_files:
        data = load_json(os.path.join(base_path, file))
        segment_start_time, duration = parse_filename(file)
        transcript_segments.append((segment_start_time, segment_start_time+duration))
    return json_files, transcript_segments

def get_overlap_intervals(transcript_segments):
    """
    Pad a list of overlap intervals for transcript segments.

    Args:
    transcript_segments (List[Tuple[float, float]]): List of (start, end) times for each segment.

    Returns:
    List[Tuple[float, float]]: Overlap intervals, including start and end points.
        Format: [(0,0), (overlap1_start, overlap1_end), ..., (last_segment_end, last_segment_end)]

    Note:
    Assumes 'find_overlapping_intervals' function exists to identify overlaps between segments.
    """
    return [(0,0)] + find_overlapping_intervals(transcript_segments) + [(transcript_segments[-1][-1],)*2]

def get_segment_times(segments, idx):
    """
    get the starting and ending offset of one segment respective of the full audio,
    and get its duration.
    """
    start_time, end_time = segments[idx][0], segments[idx][1]
    return start_time, end_time, start_time - end_time

def calculate_midpoints(overlaps, idx):
    """
    Every segment overlaps with previous and next one(s), so there are 2
    overlappings and there should be 2 midpoints, named left and right.
    """
    left = (overlaps[idx][1] + overlaps[idx][0]) / 2
    right = (overlaps[idx+1][1] + overlaps[idx+1][0]) / 2
    print(f"{left}, {right}")
    return left, right

def test_and_remove_non_subsequential_words(data, file):
    probe_subsequence = is_subsequence(data["words"], data["text"])
    print_test_result(file, probe_subsequence)
    # preprocess clip segment
    if not probe_subsequence:
        print("  entering redundant word deletion procedure")
        remove_indices = locate_non_subsequence_elements(
            data["words"], data["text"])
        print("removed_unsebsequential_indices:", 
            [data["words"][iw] for iw in sorted(list(remove_indices))])
        data["words"] = [
            word for i, word in enumerate(data["words"])
            if i not in remove_indices]
        probe_subsequence_re = is_subsequence(data["words"], data["text"])
        print_test_result(file, probe_subsequence_re)
    return data

def merge_words(
    data: Dict[str, any], segment_start_time: float, midpoint_left: float,
    midpoint_right: float, merged_data: OrderedDict[str, any]) -> None:
    """
    Combines 2 tasks:
    - Selecting and merging words timed between midpoint_left and midpoint_right.
    - Preserving and inserting punctuation from the original text into the merged words.

    Returns:
    None: This function doesn't return a value, it modifies merged_data in place.

    Notes:
    - This function assumes each word in data['words'] has 'start' and 'word' keys.
    - Punctuation is treated as separate "words" with a special "punctuation" marker.
    - Timestamps are rounded to two decimal places.
    """
    punctuated_text = data["text"]
    idx_punc = 0  # points to offset in punctuated_text

    for idx_word, word in enumerate(data["words"], start=0):
        word_global_timestamp = word["start"] + segment_start_time
        
        if midpoint_left < word_global_timestamp < midpoint_right:
            merged_data["words"].append((round_timestamp(word_global_timestamp), word["word"]))
        
        try:
            stop_char = data["words"][idx_word+1]["word"][0]
            idx_punc += len(word["word"])
            
            while punctuated_text[idx_punc] != stop_char:
                punc_timestamp = round_timestamp(word_global_timestamp + 0.01)
                if midpoint_left < punc_timestamp < midpoint_right:
                    merged_data["words"].append((punc_timestamp,
                        punctuated_text[idx_punc], "punctuation"))
                idx_punc += 1
        except IndexError:
            pass

    return

def merge_jsons(full_title: str, method: str = "midpoint") -> Dict:
    """Merge JSON files for the given title."""
    json_files, transcript_segments = initialize_json_file_names_and_transcript_segments(full_title)
    # overlaps:[(0,0), (30,35), (60,65), ..., (90,90)]
    overlaps = get_overlap_intervals(transcript_segments)
    merged_data = OrderedDict([("duration", 0), ("text", ""), ("words", [])])

    for idx_file, file in enumerate(json_files, start=0):
        # load data
        data = load_json(os.path.join('./transcription_result', full_title, file))
        # process clip segment times
        segment_start_time, segment_end_time, duration = get_segment_times(
            transcript_segments, idx_file)
        midpoint_left, midpoint_right = calculate_midpoints(overlaps, idx_file)

        # preprocess: validate whisper token words add up to subsequence of
        # whisper text, then remove non subsequence chars from data["words"]
        data = test_and_remove_non_subsequential_words(data, file)

        # prepare punctuated text
        punctuated_text = data["text"]
        idx_punc = 0 # points to offset in punctuated_text

        # Merge words
        merge_words(data, segment_start_time, midpoint_left, midpoint_right, merged_data)
        print("\r\n\r\n")

        # Update duration
        merged_data["duration"] = round_timestamp(max(merged_data["duration"], segment_start_time + data["duration"]))

    merged_data["text"] = "".join([w[1] for w in merged_data["words"]])
    return merged_data

def save_json(data: Dict, file_path: str):
    """Save data as JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, cls=OrderedEncoder)

def get_full_title_from_transcript_cuts(prefix: str) -> str:
    """
    Get the full folder name based on an arbitrary prefix.

    Args:
    prefix (str): Arbitrary prefix to match against folder names.

    Returns:
    str: Full folder name if found, empty string otherwise.
    """
    base_path = "./transcription_result"
    for folder in os.listdir(base_path):
        if os.path.isdir(os.path.join(base_path, folder)) and folder.startswith(prefix):
            return folder
    raise FileNotFoundError

def main(title_prefix: str):
    """Main function to merge JSON files."""
    full_title = get_full_title_from_transcript_cuts(title_prefix)
    merged_data = merge_jsons(full_title)
    output_file = f"./transcription_result/{full_title}/merged_{full_title}.json"
    save_json(merged_data, output_file)
    print(f"Merged JSON saved to:")
    print(f"{output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 merge_json.py <title prefix>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])