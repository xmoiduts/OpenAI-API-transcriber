"""
Core ASR postprocessing functions.

Provides pure Python functions for processing Whisper transcription results.
These functions have no GUI dependencies and can be used from CLI or imported
by GUI code.
"""

import json
import os
import sys
from typing import List

from .utils import find_cut_result_json_files
from .exporters import (
    convert_raw_json_to_csv as _convert_raw_json_to_csv,
    convert_merged_json_to_csv as _convert_merged_json_to_csv,
    convert_merged_json_to_delta_csv as _convert_merged_json_to_delta_csv,
)


def merge_text_to_txt(target_directory: str, output_filename: str = "原文未分段.txt") -> str:
    """
    Merge text content from all transcription JSON files into a single TXT file.
    
    Args:
        target_directory: Path to directory containing _cut_result.json files
        output_filename: Name of the output file (default: "原文未分段.txt")
    
    Returns:
        Path to the created TXT file
    
    Raises:
        FileNotFoundError: If directory doesn't exist
        ValueError: If no JSON files found or no text content extracted
    """
    json_files = find_cut_result_json_files(target_directory)
    
    all_text = []
    for file_path in json_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "text" in data:
                all_text.append(data["text"])
    
    if not all_text:
        raise ValueError("No text content found in the JSON files.")
    
    output_content = "\n\n".join(all_text)
    output_file_path = os.path.join(target_directory, output_filename)
    
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(output_content)
    
    return output_file_path


def convert_raw_json_to_csv(target_directory: str, output_filename: str = "word_timestamps.csv") -> str:
    """Compatibility wrapper. Implementation moved to `src.asr_postprocess.exporters`."""
    return _convert_raw_json_to_csv(target_directory, output_filename)


def convert_merged_json_to_csv(target_directory: str, output_filename: str = "merged_word_timestamps.csv") -> str:
    """Compatibility wrapper. Implementation moved to `src.asr_postprocess.exporters`."""
    return _convert_merged_json_to_csv(target_directory, output_filename)


def convert_merged_json_to_delta_csv(target_directory: str, output_filename: str = "merged_words_centi_delta.csv") -> str:
    """
    Convert merged JSON to delta format CSV with centisecond timestamps.
    
    # Output Format (Mode 3: word-timestamp, delta)
    # =============================================
    # Each line: {start_centiseconds} +{duration_centiseconds} {word}
    # 
    # - start_centiseconds: Word start time in centiseconds (1/100 sec), integer
    # - duration_centiseconds: Word duration (end - start) in centiseconds, with '+' prefix
    # - word: The word text, unquoted for normal words
    #
    # Special Case: Quoting Words with Spaces
    # ----------------------------------------
    # Words containing space characters are wrapped in quotes to ensure safe parsing:
    #   15378 +56 なん       → normal word, no quotes
    #   15522 +72 " "        → whitespace-only word, quoted to be visible
    #   12345 +10 "New York" → word with embedded space, quoted to prevent split issues
    #
    # This hybrid approach balances:
    # - Compactness: most words have no quote overhead
    # - Correctness: words with spaces are unambiguously preserved
    # - Robustness: handles edge cases like multi-word entries
    #
    # Parsing this format:
    # - Use csv.reader(f, delimiter=' ', quotechar='"') for automatic handling
    # - Or use line.split(' ', 2) and strip quotes from word if present
    #
    # Example output:
    #   15378 +56 なん
    #   15434 +16 で
    #   15522 +72 " "
    #   15594 +4 い
    #   25506 +46 1
    #
    # Benefits:
    # - Compact: integers, delta format, minimal quoting
    # - Parseable: standard CSV libraries handle quoted fields correctly
    # - Lossless: centisecond precision matches Whisper's typical output
    
    Args:
        target_directory: Path to directory containing the merged JSON file
        output_filename: Name of the output file (default: "merged_words_centi_delta.csv")
    
    Returns:
        Path to the created CSV file
    
    Raises:
        FileNotFoundError: If merged JSON file doesn't exist
        ValueError: If no word timestamps found in merged JSON
    """
    return _convert_merged_json_to_delta_csv(target_directory, output_filename)


def main():
    """CLI entrypoint for ASR postprocessing functions."""
    if len(sys.argv) < 3:
        print("Usage: python -m src.asr_postprocess.core <command> <target_directory>")
        print()
        print("Commands:")
        print("  merge_txt        - Merge JSON text fields to TXT file")
        print("  raw_to_csv       - Convert raw JSON word timestamps to CSV")
        print("  merged_to_csv    - Convert merged JSON to CSV (Mode 2: offset format)")
        print("  merged_to_delta  - Convert merged JSON to delta CSV (Mode 3: centisecond delta)")
        sys.exit(1)
    
    command = sys.argv[1]
    target_dir = sys.argv[2]
    
    try:
        if command == "merge_txt":
            output = merge_text_to_txt(target_dir)
            print(f"Successfully created: {output}")
        elif command == "raw_to_csv":
            output = convert_raw_json_to_csv(target_dir)
            print(f"Successfully created: {output}")
        elif command == "merged_to_csv":
            output = convert_merged_json_to_csv(target_dir)
            print(f"Successfully created: {output}")
        elif command == "merged_to_delta":
            output = convert_merged_json_to_delta_csv(target_dir)
            print(f"Successfully created: {output}")
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

