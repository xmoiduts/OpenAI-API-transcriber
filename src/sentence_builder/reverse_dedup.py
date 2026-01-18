"""
reverse_dedup.py - Find reverse-order timing duplicates in word timestamps.

Identifies consecutive entries with the same text and close timestamps,
which often indicate ASR repetition/stuttering that needs deduplication.

Usage:
    from sentence_builder.reverse_dedup import find_reverse_duplicates
    
    duplicates = find_reverse_duplicates("path/to/merged_word_timestamps.csv")
    contexts = get_duplicate_contexts("path/to/merged_word_timestamps.csv", duplicates)
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional
import sys

# Add parent to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from scripts.rangetime import parse_line, extract_time_range


def parse_word_timestamps(filepath: str) -> List[Tuple[float, float, str, int]]:
    """
    Parse word timestamps CSV file.
    
    Args:
        filepath: Path to merged_word_timestamps.csv
        
    Returns:
        List of (start_time, end_time, word, line_number) tuples
    """
    words = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            parsed = parse_line(line)
            if parsed:
                start, end, word = parsed
                words.append((start, end, word, line_num))
    return words


def find_reverse_duplicates(
    filepath: str,
    time_threshold: float = 2.0,
    min_word_length: int = 1
) -> List[Tuple[int, int, str, float, float]]:
    """
    Find consecutive duplicate words that may indicate ASR repetition.
    
    A "reverse duplicate" is when the same word appears multiple times
    in close succession, often due to ASR hallucination or speaker stuttering.
    
    Args:
        filepath: Path to merged_word_timestamps.csv
        time_threshold: Maximum time gap (seconds) between duplicates
        min_word_length: Minimum word length to consider (filter out single chars)
        
    Returns:
        List of (first_line, last_line, word, start_time, end_time) tuples
        representing duplicate sequences
    """
    words = parse_word_timestamps(filepath)
    if not words:
        return []
    
    duplicates = []
    i = 0
    
    while i < len(words):
        start_time, end_time, word, line_num = words[i]
        
        # Skip whitespace and short words
        if not word.strip() or len(word.strip()) < min_word_length:
            i += 1
            continue
        
        # Look for consecutive duplicates
        j = i + 1
        while j < len(words):
            next_start, next_end, next_word, next_line = words[j]
            
            # Check if same word and within time threshold
            if next_word.strip() == word.strip():
                if next_start - end_time <= time_threshold:
                    end_time = next_end
                    j += 1
                    continue
            break
        
        # If we found duplicates (more than one occurrence)
        if j > i + 1:
            first_line = words[i][3]
            last_line = words[j - 1][3]
            duplicates.append((
                first_line,
                last_line,
                word.strip(),
                words[i][0],  # start time of first
                words[j - 1][1]  # end time of last
            ))
        
        i = j if j > i + 1 else i + 1
    
    return duplicates


def get_duplicate_contexts(
    filepath: str,
    duplicates: List[Tuple[int, int, str, float, float]],
    context_seconds: float = 5.0
) -> List[dict]:
    """
    Get context around each duplicate sequence using rangetime.
    
    Args:
        filepath: Path to merged_word_timestamps.csv
        duplicates: List of duplicate tuples from find_reverse_duplicates
        context_seconds: Seconds of context before and after
        
    Returns:
        List of dicts with duplicate info and surrounding context
    """
    results = []
    
    for first_line, last_line, word, start_time, end_time in duplicates:
        # Extract context using rangetime
        context = extract_time_range(
            filepath,
            start_time,
            end_time,
            after_context=context_seconds,
            before_context=context_seconds
        )
        
        # Format context as text
        context_text = "\n".join(
            f'{s:.2f} {e:.2f} "{w}"' for s, e, w in context
        )
        
        results.append({
            'first_line': first_line,
            'last_line': last_line,
            'word': word,
            'start_time': start_time,
            'end_time': end_time,
            'context': context_text,
            'context_entries': context
        })
    
    return results


def find_latest_transcription_result() -> Optional[Path]:
    """
    Find the most recently modified transcription result directory.
    
    Returns:
        Path to the latest result directory, or None if not found
    """
    result_base = Path(__file__).parent.parent.parent / 'transcription_result'
    
    if not result_base.exists():
        return None
    
    # Find directories with merged_word_timestamps.csv
    candidates = []
    for d in result_base.iterdir():
        if d.is_dir():
            csv_file = d / 'merged_word_timestamps.csv'
            if csv_file.exists():
                candidates.append((csv_file.stat().st_mtime, d))
    
    if not candidates:
        return None
    
    # Sort by modification time, newest first
    candidates.sort(reverse=True)
    return candidates[0][1]


def main():
    """CLI entrypoint for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Find duplicate words in ASR output')
    parser.add_argument('-i', '--input', help='Input CSV file (default: auto-detect latest)')
    parser.add_argument('-t', '--threshold', type=float, default=2.0,
                        help='Time threshold for duplicates (default: 2.0s)')
    parser.add_argument('-c', '--context', type=float, default=5.0,
                        help='Context seconds around duplicates (default: 5.0s)')
    
    args = parser.parse_args()
    
    # Find input file
    if args.input:
        input_file = args.input
    else:
        result_dir = find_latest_transcription_result()
        if not result_dir:
            print("Error: No transcription results found", file=sys.stderr)
            sys.exit(1)
        input_file = str(result_dir / 'merged_word_timestamps.csv')
        print(f"Using: {input_file}", file=sys.stderr)
    
    # Find duplicates
    duplicates = find_reverse_duplicates(input_file, time_threshold=args.threshold)
    print(f"Found {len(duplicates)} duplicate sequences", file=sys.stderr)
    
    # Get contexts
    contexts = get_duplicate_contexts(input_file, duplicates, context_seconds=args.context)
    
    # Output
    for ctx in contexts:
        print(f"\n=== Duplicate: '{ctx['word']}' (lines {ctx['first_line']}-{ctx['last_line']}) ===")
        print(f"Time: {ctx['start_time']:.2f}s - {ctx['end_time']:.2f}s")
        print("Context:")
        print(ctx['context'])


if __name__ == '__main__':
    main()
