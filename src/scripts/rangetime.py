#!/usr/bin/env python3
# immature tool, for reference only, may be used as template to generate ad-hoc scripts.
"""
rangetime.py - Time-based Text ROI Extractor

Extract text from word timestamp CSV by time range with optional context extension.
Similar to grep -A -B but for time-based selection.

The parser accepts the project's multi-mode word-timestamp CSV payload:
- Canonical mode: `start end word`
- Whitespace-only payloads: `start end " "`
- Legacy fully-quoted payloads: `start end "word"`

Usage:
    python rangetime.py -i merged_word_timestamps.csv -s 114.51 -t 120.31 -A 10 -B 10
"""

import argparse
import sys
import re


def parse_line(line: str) -> tuple[float, float, str] | None:
    """
    Parse a line from the word timestamps file.

    Supported payload modes after the two timestamps:
    - canonical unquoted text: `74.00 75.00 あ`
    - whitespace-only token: `74.00 75.00 " "`
    - legacy fully-quoted text: `74.00 75.00 "あ"`
    """
    line = line.strip()
    if not line:
        return None

    # Parse the two numeric fields first, then treat the remainder as the raw
    # payload so unquoted multi-word text is preserved.
    match = re.match(r'^([\d.]+)\s+([\d.]+)\s+(.+)$', line)
    if not match:
        return None

    try:
        start = float(match.group(1))
        end = float(match.group(2))
    except ValueError:
        return None

    payload = match.group(3)

    # Legacy/full quoted mode: unwrap one layer of CSV-style quotes.
    if len(payload) >= 2 and payload.startswith('"') and payload.endswith('"'):
        payload = payload[1:-1].replace('""', '"')

    return (start, end, payload)


def format_word_payload(text: str) -> str:
    """
    Format a parsed payload back into the project's canonical text form.

    Normal words remain unquoted. Whitespace-only payloads are quoted so they
    stay visible when printed or copied.
    """
    if text.strip() == "":
        escaped = text.replace('"', '""')
        return f'"{escaped}"'
    return text


def extract_time_range(
    input_file: str,
    start_time: float,
    end_time: float,
    after_context: float = 0.0,
    before_context: float = 0.0
) -> list[tuple[float, float, str]]:
    """
    Extract rows from the CSV where timestamps fall within the effective range.
    
    Args:
        input_file: Path to the word timestamps CSV
        start_time: Start of selection (-s)
        end_time: End of selection (-t)
        after_context: Seconds to extend after end_time (-A)
        before_context: Seconds to extend before start_time (-B)
    
    Returns:
        List of (start, end, text) tuples within the range
    """
    effective_start = start_time - before_context
    effective_end = end_time + after_context
    
    results = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            parsed = parse_line(line)
            if parsed is None:
                continue
            
            row_start, row_end, text = parsed
            
            # Include row if it overlaps with the effective range
            # Row is included if: row_start >= effective_start AND row_start <= effective_end
            # This captures all words that start within our time window
            if row_start >= effective_start and row_start <= effective_end:
                results.append(parsed)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Extract text regions of interest from word timestamps CSV by time range.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    python rangetime.py -i merged_word_timestamps.csv -s 114.51 -t 120.31
    python rangetime.py -i merged_word_timestamps.csv -s 114.51 -t 120.31 -A 10 -B 10
        '''
    )
    
    parser.add_argument('-i', '--input', required=True,
                        help='Input CSV file with word timestamps')
    parser.add_argument('-s', '--start', type=float, required=True,
                        help='Start time in seconds')
    parser.add_argument('-t', '--to', type=float, required=True,
                        help='End time in seconds')
    parser.add_argument('-A', '--after', type=float, default=0.0,
                        help='Extend selection by N seconds after end time (default: 0)')
    parser.add_argument('-B', '--before', type=float, default=0.0,
                        help='Extend selection by N seconds before start time (default: 0)')
    
    args = parser.parse_args()
    
    try:
        results = extract_time_range(
            input_file=args.input,
            start_time=args.start,
            end_time=args.to,
            after_context=args.after,
            before_context=args.before
        )
        
        # Output results to stdout
        for start, end, text in results:
            print(f'{start:.2f} {end:.2f} {format_word_payload(text)}')
        
        # Print summary to stderr
        print(f'\n# Selected {len(results)} entries', file=sys.stderr)
        print(f'# Time range: {args.start - args.before:.2f} to {args.to + args.after:.2f}', file=sys.stderr)
        
    except FileNotFoundError:
        print(f'Error: File not found: {args.input}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
