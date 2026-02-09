"""
reverse_dedup.py - Detect time reversal points in subtitle timestamps.

Identifies time reversals caused by segmented transcription overlaps.
When processing long audio in segments, the segments may overlap in time,
creating sequences like:
    1→2→3→...→11 (segment 1)
    3→4→5→...→13 (segment 2, starts at 3, creating reversal)

This tool detects these reversal points and extracts the overlapping regions
with padding for manual inspection and deduplication.

Usage:
    python reverse_dedup.py -i path/to/merged_word_timestamps.csv
    python reverse_dedup.py  # auto-detect latest transcription result
"""

import sys
from pathlib import Path
from typing import List, Tuple, Optional, NamedTuple
from dataclasses import dataclass

# Add parent to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from scripts.rangetime import parse_line, extract_time_range


class TimestampEntry(NamedTuple):
    """A single timestamp entry from the CSV."""
    start: float
    end: float
    text: str
    line_num: int


@dataclass
class TimeReversal:
    """Represents a detected time reversal point."""
    reversal_line: int          # Line number where reversal starts
    reversal_start_time: float  # Time when reversal begins
    overlap_end_time: float     # Time when overlap ends (catches up)
    overlap_end_line: int       # Line number where overlap ends
    max_time_before: float      # Maximum time before reversal occurred
    
    def get_overlap_duration(self) -> float:
        """Get duration of the overlapping region."""
        return self.overlap_end_time - self.reversal_start_time
    
    def __str__(self) -> str:
        return (
            f"Time Reversal at line {self.reversal_line}:\n"
            f"  Reversal starts: {self.reversal_start_time:.2f}s (was at {self.max_time_before:.2f}s)\n"
            f"  Overlap region: {self.reversal_start_time:.2f}s - {self.overlap_end_time:.2f}s "
            f"({self.get_overlap_duration():.2f}s duration)\n"
            f"  Overlap ends at line: {self.overlap_end_line}"
        )


def parse_timestamp_file(filepath: str) -> List[TimestampEntry]:
    """
    Parse word timestamps CSV file.
    
    Args:
        filepath: Path to merged_word_timestamps.csv
        
    Returns:
        List of TimestampEntry objects
    """
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            parsed = parse_line(line)
            if parsed:
                start, end, text = parsed
                entries.append(TimestampEntry(start, end, text, line_num))
    return entries


def find_time_reversals(
    filepath: str,
    min_reversal_gap: float = 1.0
) -> List[TimeReversal]:
    """
    Find all time reversal points in the timestamp file.
    
    A time reversal occurs when timestamps go backwards, indicating
    overlapping segments from the transcription process.
    
    Args:
        filepath: Path to merged_word_timestamps.csv
        min_reversal_gap: Minimum time gap (seconds) to consider a reversal
                         Filters out minor jitter in timestamps
        
    Returns:
        List of TimeReversal objects
    """
    entries = parse_timestamp_file(filepath)
    if not entries:
        return []
    
    reversals = []
    max_end_time = 0.0
    i = 0
    
    while i < len(entries):
        entry = entries[i]
        
        # Check if current start time is less than max seen end time
        # This indicates a time reversal
        if entry.start < max_end_time - min_reversal_gap:
            # Found a reversal!
            reversal_start = entry.start
            reversal_line = entry.line_num
            max_before = max_end_time
            
            # Find where the overlap ends (where time catches up)
            overlap_end_time = reversal_start
            overlap_end_line = reversal_line
            overlap_end_index = i
            
            # Continue from this entry to find where we catch up
            for j in range(i, len(entries)):
                future_entry = entries[j]
                overlap_end_time = future_entry.end
                overlap_end_line = future_entry.line_num
                overlap_end_index = j
                
                # If we've caught up to or exceeded the previous max time
                if future_entry.end >= max_before:
                    break
            
            reversals.append(TimeReversal(
                reversal_line=reversal_line,
                reversal_start_time=reversal_start,
                overlap_end_time=overlap_end_time,
                overlap_end_line=overlap_end_line,
                max_time_before=max_before
            ))
            
            # Skip to the end of overlap region to avoid duplicate detections
            i = overlap_end_index + 1
            # Update max_end_time to the overlap end time
            max_end_time = overlap_end_time
        else:
            # Normal progression, update max
            max_end_time = max(max_end_time, entry.end)
            i += 1
    
    return reversals


def get_reversal_contexts(
    filepath: str,
    reversals: List[TimeReversal],
    padding_seconds: float = 10.0
) -> List[dict]:
    """
    Extract text context around each time reversal with padding.
    
    Args:
        filepath: Path to merged_word_timestamps.csv
        reversals: List of TimeReversal objects
        padding_seconds: Seconds to add before/after overlap region
        
    Returns:
        List of dicts containing reversal info and padded context
    """
    results = []
    
    for reversal in reversals:
        # Extract the overlap region with padding
        context_entries = extract_time_range(
            filepath,
            start_time=reversal.reversal_start_time,
            end_time=reversal.overlap_end_time,
            before_context=padding_seconds,
            after_context=padding_seconds
        )
        
        # Format as text
        context_text = "\n".join(
            f'{start:.2f} {end:.2f} "{text}"'
            for start, end, text in context_entries
        )
        
        # Also get just the words as a readable string
        text_only = "".join(text for _, _, text in context_entries)
        
        results.append({
            'reversal': reversal,
            'padded_start': reversal.reversal_start_time - padding_seconds,
            'padded_end': reversal.overlap_end_time + padding_seconds,
            'context_entries': context_entries,
            'context_text': context_text,
            'text_only': text_only,
            'num_entries': len(context_entries)
        })
    
    return results


def get_reversal_segments(
    filepath: str,
    reversals: List[TimeReversal],
    padding_seconds: float = 10.0
) -> List[dict]:
    """
    Extract overlapping segments as separate A/B sources.
    
    For each reversal, extracts:
    - Segment A: Entries before reversal line (with time-based padding)
    - Segment B: Entries after reversal line (with time-based padding)
    
    This allows source-labeled formatting where both segments are shown
    in time-sorted order with their origin marked.
    
    Args:
        filepath: Path to merged_word_timestamps.csv
        reversals: List of TimeReversal objects
        padding_seconds: Seconds to add before/after the overlap time range
        
    Returns:
        List of dicts containing:
            - reversal: TimeReversal object
            - segment_a: List of (start, end, text) tuples from before reversal
            - segment_b: List of (start, end, text) tuples from after reversal
    """
    results = []
    
    # Load all entries once
    all_entries = parse_timestamp_file(filepath)
    
    for reversal in reversals:
        # Time range for filtering (with padding)
        time_start = reversal.reversal_start_time - padding_seconds
        time_end = max(reversal.max_time_before, reversal.overlap_end_time) + padding_seconds
        
        # Segment A: Entries BEFORE reversal line, within time range
        segment_a_entries = []
        for entry in all_entries:
            if entry.line_num < reversal.reversal_line:
                # Check if within time range
                if time_start <= entry.start <= time_end or time_start <= entry.end <= time_end:
                    segment_a_entries.append((entry.start, entry.end, entry.text))
        
        # Segment B: Entries FROM reversal line onwards, within time range
        segment_b_entries = []
        for entry in all_entries:
            if entry.line_num >= reversal.reversal_line:
                # Check if within time range
                if time_start <= entry.start <= time_end or time_start <= entry.end <= time_end:
                    segment_b_entries.append((entry.start, entry.end, entry.text))
                # Stop when we pass the overlap end line
                if entry.line_num > reversal.overlap_end_line + 100:  # Some buffer
                    break
        
        results.append({
            'reversal': reversal,
            'segment_a': segment_a_entries,
            'segment_b': segment_b_entries,
            'reversal_time': reversal.reversal_start_time
        })
    
    return results


def find_latest_transcription_result() -> Optional[Path]:
    """
    Find the most recently modified transcription result directory.
    
    Returns:
        Path to the latest result directory, or None if not found
    """
    # Try both possible directory names
    base_paths = [
        Path(__file__).parent.parent.parent / 'transcription_result',
        Path(__file__).parent.parent.parent / 'transcription_results'
    ]
    
    candidates = []
    
    for result_base in base_paths:
        if not result_base.exists():
            continue
        
        # Find directories with merged_word_timestamps.csv
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
    """CLI entrypoint."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Detect time reversals in subtitle timestamps',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    # Auto-detect latest transcription result
    python reverse_dedup.py
    
    # Specify input file
    python reverse_dedup.py -i path/to/merged_word_timestamps.csv
    
    # Adjust padding around overlap regions
    python reverse_dedup.py -p 15.0
    
    # Only show time summary (avoid CJK text output)
    python reverse_dedup.py --summary-only
        '''
    )
    
    parser.add_argument('-i', '--input',
                        help='Input CSV file (default: auto-detect latest)')
    parser.add_argument('-p', '--padding', type=float, default=10.0,
                        help='Padding seconds around overlap regions (default: 10.0)')
    parser.add_argument('-g', '--gap', type=float, default=1.0,
                        help='Minimum reversal gap to detect (default: 1.0s)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show detailed output')
    parser.add_argument('--summary-only', action='store_true',
                        help='Only output time summary info, skip all text content (avoids CJK encoding issues)')
    
    args = parser.parse_args()
    
    # Find input file
    if args.input:
        input_file = args.input
    else:
        result_dir = find_latest_transcription_result()
        if not result_dir:
            print("Error: No transcription results found", file=sys.stderr)
            print("Searched in: transcription_result/ and transcription_results/", file=sys.stderr)
            sys.exit(1)
        input_file = str(result_dir / 'merged_word_timestamps.csv')
        print(f"Using: {input_file}\n", file=sys.stderr)
    
    # Find reversals
    reversals = find_time_reversals(input_file, min_reversal_gap=args.gap)
    
    if not reversals:
        print("No time reversals detected!", file=sys.stderr)
        print("This is good - it means your subtitle timestamps are monotonic.", file=sys.stderr)
        return
    
    print(f"Found {len(reversals)} time reversal(s)\n", file=sys.stderr)
    
    # Get contexts
    contexts = get_reversal_contexts(input_file, reversals, padding_seconds=args.padding)
    
    # Output results
    for i, ctx in enumerate(contexts, 1):
        reversal = ctx['reversal']
        
        print(f"{'='*70}")
        print(f"REVERSAL #{i}")
        print(f"{'='*70}")
        print(reversal)
        print(f"\nPadded time range: {ctx['padded_start']:.2f}s - {ctx['padded_end']:.2f}s")
        print(f"Total entries in context: {ctx['num_entries']}\n")
        
        # Skip text content if summary-only mode
        if args.summary_only:
            continue
        
        if args.verbose:
            print("Context with timestamps:")
            print(ctx['context_text'])
            print()
        
        print("Text only:")
        print(ctx['text_only'])
        print()


if __name__ == '__main__':
    main()
