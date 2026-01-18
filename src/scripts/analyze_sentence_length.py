#!/usr/bin/env python3
# immature tool, for reference only, may be used as template to generate ad-hoc scripts.
"""
analyze_sentence_length.py - Sentence Length Analyzer

Analyze sentence lengths from subtitle text file and recommend line breaks for long sentences.

Character counting rules:
- CJK characters: 1 unit each
- English letters: 0.5 units per letter (2 letters = 1 unit)
- Spaces: ignored

Usage:
    python analyze_sentence_length.py -i 句轴原文.txt --ruler 39 --line-rec 33

Output:
    start,end,break-parts-recommendation
    start: start time of the sentence
    end: end time of the sentence
    break-parts-recommendation: number of parts to break the sentence into
"""

import argparse
import math
import re
import sys
import unicodedata


def is_cjk(char: str) -> bool:
    """Check if a character is CJK (Chinese, Japanese, Korean)."""
    try:
        name = unicodedata.name(char, '')
        return any(x in name for x in ['CJK', 'HIRAGANA', 'KATAKANA', 'HANGUL', 'IDEOGRAPH'])
    except ValueError:
        return False


def calc_length(text: str) -> float:
    """
    Calculate the weighted length of text.
    
    Rules:
    - CJK characters: 1 unit each
    - English letters: 0.5 units per letter (2 letters = 1 unit)
    - Spaces and other characters: ignored
    """
    length = 0.0
    for char in text:
        if char.isspace():
            continue
        elif is_cjk(char):
            length += 1
        elif char.isalpha():  # English/Latin letters
            length += 0.5
        # Other punctuation, numbers, etc. - could count or ignore
        # Based on the example, we'll count them as 0 (ignored)
    return length


def parse_subtitle_line(line: str) -> tuple[float, float, str] | None:
    """
    Parse a line from the subtitle text file.
    Format: {start_time} {end_time} text_content
    Example: {74.00} {76.34} あけました?
    """
    line = line.strip()
    if not line:
        return None
    
    # Match pattern: {number} {number} text
    match = re.match(r'^\{([\d.]+)\}\s*\{([\d.]+)\}\s*(.*)$', line)
    if match:
        start = float(match.group(1))
        end = float(match.group(2))
        text = match.group(3)
        return (start, end, text)
    
    return None


def analyze_sentences(
    input_file: str,
    ruler_length: float = 39.0,
    line_length_rec: float = 33.0
) -> list[tuple[float, float, int, float]]:
    """
    Analyze sentences and find those exceeding the ruler length.
    
    Args:
        input_file: Path to the subtitle text file
        ruler_length: Threshold length to trigger segmentation recommendation
        line_length_rec: Target length per line for recommendation calculation
    
    Returns:
        List of (start, end, recommended_parts, actual_length) for long sentences
    """
    results = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            parsed = parse_subtitle_line(line)
            if parsed is None:
                continue
            
            start, end, text = parsed
            length = calc_length(text)
            
            if length > ruler_length:
                recommended_parts = math.ceil(length / line_length_rec)
                results.append((start, end, recommended_parts, length))
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Analyze sentence lengths and recommend line breaks for long sentences.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Character counting rules:
  - CJK characters (Japanese, Chinese, Korean): 1 unit each
  - English letters: 0.5 units per letter (2 letters = 1 unit)
  - Spaces: ignored

Examples:
    python analyze_sentence_length.py -i 句轴原文.txt
    python analyze_sentence_length.py -i 句轴原文.txt --ruler 39 --line-rec 33

Output:
    start,end,break-parts-recommendation
    start: start time of the sentence
    end: end time of the sentence
    break-parts-recommendation: number of parts to break the sentence into
        '''
    )
    
    parser.add_argument('-i', '--input', required=True,
                        help='Input subtitle text file')
    parser.add_argument('--ruler', type=float, default=39.0,
                        help='Ruler length threshold to trigger segmentation (default: 39)')
    parser.add_argument('--line-rec', type=float, default=33.0,
                        help='Target line length for recommendation calculation (default: 33)')
    
    args = parser.parse_args()
    
    try:
        results = analyze_sentences(
            input_file=args.input,
            ruler_length=args.ruler,
            line_length_rec=args.line_rec
        )
        
        # Output CSV header
        print('start,end,break-parts-recommendation')
        
        # Output results
        for start, end, parts, length in results:
            print(f'{start:.2f},{end:.2f},{parts}')
        
        # Print summary to stderr
        print(f'\n# Found {len(results)} sentences exceeding ruler length ({args.ruler})', file=sys.stderr)
        
    except FileNotFoundError:
        print(f'Error: File not found: {args.input}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
