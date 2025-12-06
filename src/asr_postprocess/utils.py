"""
Utility functions for ASR postprocessing.

Provides shared file-finding and sorting utilities used across
the postprocessing module.
"""

import os
import re
from typing import List


# Regex pattern for Whisper transcription result files
# Format: {file_stem}_ss{start}-t{duration}_cut_result.json
CUT_RESULT_PATTERN = re.compile(r".*_ss\d+-t\d+_cut_result\.json$")


def extract_start_time(filename: str) -> int:
    """
    Extract the start time (ss number) from a transcription result filename.
    
    Args:
        filename: The filename to parse (can be full path or just filename)
    
    Returns:
        The start time as an integer, or 0 if pattern doesn't match
    
    Example:
        >>> extract_start_time("audio_ss30-t35_cut_result.json")
        30
    """
    basename = os.path.basename(filename)
    match = re.search(r"_ss(\d+)-t\d+_cut_result\.json$", basename)
    return int(match.group(1)) if match else 0


def find_cut_result_json_files(target_directory: str) -> List[str]:
    """
    Find all _cut_result.json files in the target directory and return them
    sorted by start time.
    
    Args:
        target_directory: Path to the directory containing transcription results
    
    Returns:
        List of full paths to JSON files, sorted by start time (ss number)
    
    Raises:
        FileNotFoundError: If the target directory doesn't exist
        ValueError: If no matching JSON files are found
    """
    if not os.path.isdir(target_directory):
        raise FileNotFoundError(f"Directory not found: {target_directory}")
    
    json_files = []
    for f in os.listdir(target_directory):
        if CUT_RESULT_PATTERN.match(f):
            json_files.append(os.path.join(target_directory, f))
    
    if not json_files:
        raise ValueError("No transcription JSON files found in the directory.")
    
    # Sort by start time
    json_files.sort(key=extract_start_time)
    
    return json_files

