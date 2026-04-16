#!/usr/bin/env python3

import json
import sys
import os
from typing import List, Dict, Tuple, Optional
import difflib
from collections import OrderedDict
import re
import time
from pathlib import Path

# Try relative import first (when used as module), fall back to direct import
try:
    from .merge_json_algo import *
except ImportError:
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
    # Updated to match new format: {file_stem}_ss{start}-t{duration}_cut_result.json
    match = re.search(r'_ss(\d+)-t(\d+)_cut_result\.json$', filename)
    if match:
        return int(match.group(1)), int(match.group(2)) # start at, duration
    
    # Fallback to old format for backwards compatibility
    match_old = re.search(r'_ss(\d+)-t(\d+)\.json$', filename)
    if match_old:
        return int(match_old.group(1)), int(match_old.group(2))
    
    raise ValueError(f"Invalid filename format: {filename}. Expected format: *_ss<start>-t<duration>_cut_result.json")

def extract_sort_key(filename: str) -> int:
    """Extract the start time part from the filename."""
    start_time, _ = parse_filename(filename)
    return start_time

def round_timestamp(timestamp: float) -> float:
    """Round timestamp to 0.01 second precision."""
    return round(timestamp, 2)

def initialize_json_file_names_and_transcript_segments(target_directory: str) -> Tuple[
    List[str], List[Tuple[float, float]]]:
    """
    Initialize JSON file names and transcript segment times from target directory.

    Args:
    target_directory (str): Directory containing JSON files.

    Returns:
    Tuple[List[str], List[Tuple[float, float]]]: 
        - Sorted list of JSON file names.
        - List of transcript segment times (start, end).
    """
    # Find all _cut_result.json files
    pattern = re.compile(r".*_ss\d+-t\d+_cut_result\.json$")
    json_files = [f for f in os.listdir(target_directory) if pattern.match(f)]
    json_files.sort(key=extract_sort_key)
    
    transcript_segments = [] # [(0, 35.00), (30.00, 65.00), ...]
    for file in json_files:
        data = load_json(os.path.join(target_directory, file))
        segment_start_time, duration = parse_filename(file)
        transcript_segments.append((segment_start_time, segment_start_time+duration))
    
    # Debug: Print return result
    print("Debug: JSON files:", json_files)
    print("Debug: Transcript segments:", transcript_segments)
    return json_files, transcript_segments

def get_overlap_intervals(transcript_segments):
    """
    Pad a list of boundary intervals for transcript segments.

    Args:
    transcript_segments (List[Tuple[float, float]]): List of (start, end) times for each segment.

    Returns:
    List[Tuple[float, float]]: Boundary intervals, including start and end points.
        Format: [(0,0), (boundary1_left, boundary1_right), ..., (last_segment_end, last_segment_end)]

    Note:
    Adjacent segments may overlap, touch, or have gaps.
    We return one interval per boundary so midpoint calculation works for all three cases.
    """
    if not transcript_segments:
        return []

    boundary_intervals = []
    for current_segment, next_segment in zip(transcript_segments, transcript_segments[1:]):
        current_end = current_segment[1]
        next_start = next_segment[0]
        boundary_intervals.append((
            min(current_end, next_start),
            max(current_end, next_start),
        ))

    return [(0,0)] + boundary_intervals + [(transcript_segments[-1][-1],)*2]

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
    if idx + 1 >= len(overlaps):
        raise ValueError(
            f"Insufficient boundary intervals for segment index {idx}: {overlaps}"
        )
    print(f"Debug: overlaps={overlaps}, idx={idx}")
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
    midpoint_right: float, merged_data: OrderedDict[str, any], 
    dedup_method: str = "none") -> None:
    """
    Combines 2 tasks:
    - Selecting and merging words timed between midpoint_left and midpoint_right.
    - Preserving and inserting punctuation from the original text into the merged words.

    Args:
    dedup_method: "none" (no filtering), "midpoint" (filter by midpoints), or "LLM" (future implementation)

    Returns:
    None: This function doesn't return a value, it modifies merged_data in place.

    Notes:
    - This function assumes each word in data['words'] has 'start', 'end', and 'word' keys.
    - Words are stored as tuples: (start, end, word)
    - Punctuation is treated as separate entries with a "punctuation" marker: (start, end, char, "punctuation")
    - Timestamps are rounded to two decimal places.
    """
    punctuated_text = data["text"]
    idx_punc = 0  # points to offset in punctuated_text

    for idx_word, word in enumerate(data["words"], start=0):
        word_start = word["start"] # each slice's word-precise timestamp is adjusted correctly by WhisperTranscriber._adjust_timestamps()
        word_end = word.get("end", word_start)  # Get end timestamp, fallback to start if not available
        
        # Apply filtering based on dedup_method
        should_include = True
        if dedup_method == "midpoint":
            should_include = midpoint_left < word_start < midpoint_right
        elif dedup_method == "LLM":
            # TODO: Implement LLM-based deduplication, here we use midpoint as a placeholder
            should_include = midpoint_left < word_start < midpoint_right
        # else dedup_method == "none": include all words
        
        if should_include:
            # Store as (start, end, word) tuple
            merged_data["words"].append((
                round_timestamp(word_start), 
                round_timestamp(word_end), 
                word["word"]
            ))
        
        try:
            next_word = data["words"][idx_word+1]
            next_word_start = next_word["start"]
            stop_char = next_word["word"][0]
            idx_punc += len(word["word"])
            
            while punctuated_text[idx_punc] != stop_char:
                char = punctuated_text[idx_punc]
                
                if char.isspace():
                    # Whitespace represents the gap between words:
                    # - starts at previous word's END
                    # - ends at next word's START
                    # This gives the actual pause duration, useful for semantic segmentation
                    # (longer pauses often indicate sentence/clause boundaries)
                    space_start = round_timestamp(word_end)
                    space_end = round_timestamp(next_word_start)
                    if should_include:
                        merged_data["words"].append((
                            space_start,
                            space_end,
                            char,
                            "punctuation"
                        ))
                else:
                    # Non-space punctuation uses the same timestamp as the previous word
                    punc_start = round_timestamp(word_start)
                    punc_end = round_timestamp(word_end)
                    if should_include:
                        # Store punctuation as (start, end, char, "punctuation")
                        merged_data["words"].append((
                            punc_start, 
                            punc_end, 
                            char, 
                            "punctuation"
                        ))
                idx_punc += 1
        except IndexError:
            pass

    return

def merge_jsons(target_directory: str, dedup_method: str = "none") -> Dict:
    """
    Merge JSON files from the target directory.
    
    Args:
    target_directory: Directory containing the _cut_result.json files
    dedup_method: Deduplication method - "none" (default), "midpoint", or "LLM"
    
    Returns:
    Dict: Merged data with duration, text, and words
    """
    json_files, transcript_segments = initialize_json_file_names_and_transcript_segments(target_directory)
    if not json_files:
        raise ValueError(
            "No transcription JSON files found in the directory. "
            "Expected files matching *_ss<start>-t<duration>_cut_result.json."
        )
    # overlaps:[(0,0), (30,35), (60,65), ..., (90,90)]
    overlaps = get_overlap_intervals(transcript_segments)
    merged_data = OrderedDict([("duration", 0), ("text", ""), ("words", [])])

    for idx_file, file in enumerate(json_files, start=0):
        # load data
        data = load_json(os.path.join(target_directory, file))
        # process clip segment times
        segment_start_time, segment_end_time, duration = get_segment_times(
            transcript_segments, idx_file)
        midpoint_left, midpoint_right = calculate_midpoints(overlaps, idx_file)

        # preprocess: validate whisper token words add up to subsequence of
        # whisper text, then remove non subsequence chars from data["words"]
        data = test_and_remove_non_subsequential_words(data, file)

        # Merge words with specified deduplication method
        merge_words(data, segment_start_time, midpoint_left, midpoint_right, 
                   merged_data, dedup_method)
        print("\r\n\r\n")

    # Calculate duration as the time span from first segment start to last segment end
    # This gives the actual duration of the merged audio, not the absolute position
    first_segment_start = transcript_segments[0][0]
    last_segment_end = transcript_segments[-1][1]
    merged_data["duration"] = round_timestamp(last_segment_end - first_segment_start)

    # Extract text from words (word is at index 2 in the tuple)
    merged_data["text"] = "".join([w[2] for w in merged_data["words"]])
    return merged_data

def save_json(data: Dict, file_path: str):
    """Save data as JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, cls=OrderedEncoder)

def merge_and_save(target_directory: str, dedup_method: str = "none") -> str:
    """
    Merge JSON files from target directory and save the result.
    
    Args:
    target_directory: Directory containing the _cut_result.json files
    dedup_method: Deduplication method - "none" (default), "midpoint", or "LLM"
    
    Returns:
    str: Path to the saved merged JSON file
    """
    merged_data = merge_jsons(target_directory, dedup_method)
    
    # Generate output filename based on directory name
    dir_name = os.path.basename(target_directory)
    output_file = os.path.join(target_directory, f"merged_{dir_name}.json")
    
    save_json(merged_data, output_file)
    print(f"Merged JSON saved to: {output_file}")
    return output_file

def main(target_directory: str, dedup_method: str = "none"):
    """Main function to merge JSON files (for command-line usage)."""
    merge_and_save(target_directory, dedup_method)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 merge_json.py <target_directory> [dedup_method]", file=sys.stderr)
        print("  dedup_method: none (default), midpoint, or LLM", file=sys.stderr)
        sys.exit(1)
    
    target_dir = sys.argv[1]
    method = sys.argv[2] if len(sys.argv) > 2 else "none"
    main(target_dir, method)