"""
Context formatter for LLM prompts.

Provides reformatting and retiming functions to compress context sent to LLM:
- reformat_context: Add line numbers to CSV-like timestamp data
- retime_context: Subtract time offset to shorten timestamp strings
- compress_consecutive_times: Replace duplicate end times with ~ symbol
"""

import re
from typing import Tuple, List


def _normalize_word(word: str) -> str:
    """
    Normalize word for output: only quote spaces, strip quotes from others.
    
    Rules (matching merged_word_timestamps.csv convention):
    - Space or empty string -> " "
    - Other words -> no quotes
    """
    # Strip surrounding quotes if present
    if word.startswith('"') and word.endswith('"'):
        word = word[1:-1]
    
    # Only quote spaces/empty
    if word == '' or word == ' ' or word.strip() == '':
        return '" "'
    
    return word


def reformat_context(csv_text: str) -> str:
    """
    Reformat CSV-like timestamp data by adding line numbers.
    
    Input format (each line):
        start_time end_time "word"
    
    Output format:
        line-number start(s) end(s) word
        1 114.51 116.73 か
        2 116.73 118.57 " "
    
    Quote handling: Only spaces are quoted, other words are unquoted.
    
    Args:
        csv_text: CSV-like text with lines in format: start end "word"
        
    Returns:
        Reformatted text with line numbers starting from 1
    """
    lines = csv_text.strip().split('\n')
    output_lines = ["line-number start(s) end(s)"]  # Header
    
    line_num = 1
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Parse: start end "word" or start end word
        match = re.match(r'^([\d.]+)\s+([\d.]+)\s+(.+)$', line)
        if match:
            start, end, word = match.groups()
            # Normalize word: strip quotes, only quote spaces
            normalized_word = _normalize_word(word)
            output_lines.append(f"{line_num} {start} {end} {normalized_word}")
            line_num += 1
    
    return '\n'.join(output_lines)


def retime_context(csv_text: str) -> Tuple[str, int]:
    """
    Subtract time offset from timestamps to shorten string representation.
    
    Calculates offset as: floor(min_time / 10) * 10
    This ensures timestamps become shorter (e.g., 114.51 -> 4.51 with offset=110).
    
    Input format:
        line-number start(s) end(s) word
        1 114.51 116.73 か
        2 116.73 118.57 " "
    
    Output format (with offset subtracted):
        line-number start(s) end(s) word
        1 4.51 6.73 か
        2 6.73 8.57 " "
    
    Args:
        csv_text: Reformatted CSV text (output from reformat_context)
        
    Returns:
        Tuple of (retimed_text, offset_seconds)
    """
    lines = csv_text.strip().split('\n')
    if not lines:
        return csv_text, 0
    
    # First pass: find minimum time to calculate offset
    min_time = float('inf')
    data_lines = []  # Store parsed data lines (skip header)
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Skip header line
        if line.startswith('line-number'):
            continue
        
        # Parse: line-number start end word
        match = re.match(r'^(\d+)\s+([\d.]+)\s+([\d.]+)\s+(.+)$', line)
        if match:
            line_num, start, end, word = match.groups()
            start_f = float(start)
            end_f = float(end)
            min_time = min(min_time, start_f)
            data_lines.append((line_num, start_f, end_f, word))
    
    if min_time == float('inf') or not data_lines:
        return csv_text, 0
    
    # Calculate offset: floor(min_time / 10) * 10
    offset = int(min_time // 10) * 10
    
    if offset == 0:
        # No benefit from retiming
        return csv_text, 0
    
    # Second pass: apply offset
    output_lines = ["line-number start(s) end(s)"]
    for line_num, start_f, end_f, word in data_lines:
        new_start = start_f - offset
        new_end = end_f - offset
        # Format with 2 decimal places
        output_lines.append(f"{line_num} {new_start:.2f} {new_end:.2f} {word}")
    
    return '\n'.join(output_lines), offset


def compress_consecutive_times(csv_text: str) -> str:
    """
    Replace duplicate end times with ~ symbol when end time equals next start time.
    
    This saves tokens in continuous speech where words flow seamlessly.
    The ~ symbol is 1 token and semantically suggests "continues to next".
    
    Input format:
        line-number start(s) end(s) word
        1 0.70 1.22 例えば
        2 1.22 1.74 極
        3 1.74 1.86 端
    
    Output format (consecutive times compressed):
        line-number start(s) end(s) word
        1 0.70 ~ 例えば
        2 1.22 ~ 極
        3 1.74 1.86 端
    
    Args:
        csv_text: Reformatted/retimed CSV text
        
    Returns:
        Text with consecutive duplicate times replaced by ~
    """
    lines = csv_text.strip().split('\n')
    if not lines:
        return csv_text
    
    # Parse all data lines
    header = None
    data_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('line-number'):
            header = line
            continue
        
        # Parse: line-number start end word
        match = re.match(r'^(\d+)\s+([\d.]+)\s+([\d.]+)\s+(.+)$', line)
        if match:
            line_num, start, end, word = match.groups()
            data_lines.append({
                'line_num': line_num,
                'start': float(start),
                'end': float(end),
                'word': word
            })
    
    if not data_lines:
        return csv_text
    
    # Compare consecutive entries and mark duplicates
    output_lines = []
    if header:
        output_lines.append(header)
    
    for i, entry in enumerate(data_lines):
        end_str = f"{entry['end']:.2f}"
        
        # Check if this end time equals next start time
        if i < len(data_lines) - 1:
            next_start = data_lines[i + 1]['start']
            # Use small epsilon for float comparison
            if abs(entry['end'] - next_start) < 0.001:
                end_str = "~"
        
        output_lines.append(f"{entry['line_num']} {entry['start']:.2f} {end_str} {entry['word']}")
    
    return '\n'.join(output_lines)


def format_and_retime_context(csv_text: str) -> Tuple[str, int]:
    """
    Convenience function: reformat, retime, and compress in one call.
    
    Pipeline:
    1. reformat_context: Add line numbers, normalize quotes
    2. retime_context: Subtract time offset
    3. compress_consecutive_times: Replace duplicate end times with ~
    
    Args:
        csv_text: Raw CSV-like text with lines in format: start end "word"
        
    Returns:
        Tuple of (formatted_and_retimed_text, offset_seconds)
    """
    reformatted = reformat_context(csv_text)
    retimed, offset = retime_context(reformatted)
    compressed = compress_consecutive_times(retimed)
    return compressed, offset


def format_with_source_labeling(
    segment_a_entries: List[Tuple[float, float, str]],
    segment_b_entries: List[Tuple[float, float, str]],
    reversal_time: float
) -> Tuple[str, int]:
    """
    Format overlapping segments with source labeling (A/B) and line numbers.
    
    Merges two overlapping segments by:
    1. Separating entries into A (before reversal) and B (after reversal)
    2. Sorting all entries by time (monotonically increasing)
    3. Labeling each entry with source (A or B) and line number
    4. Applying retime and compression
    
    Args:
        segment_a_entries: List of (start, end, text) tuples from segment A
        segment_b_entries: List of (start, end, text) tuples from segment B
        reversal_time: The time point where reversal occurs
        
    Returns:
        Tuple of (formatted_text, offset_seconds)
        
    Example output:
        Line Source start(s) end(s)
        1 A 101.11 ~ So,
        2 A 101.34 ~ this
        3 B 101.36 ~ This
        4 B 102.10 ~ is
        5 A 101.11 ~ is
        6 B 104.00 ~ a
    """
    # Combine all entries with source labels
    all_entries = []
    
    for start, end, text in segment_a_entries:
        all_entries.append({
            'source': 'A',
            'start': start,
            'end': end,
            'text': text
        })
    
    for start, end, text in segment_b_entries:
        all_entries.append({
            'source': 'B',
            'start': start,
            'end': end,
            'text': text
        })
    
    # Sort by start time (monotonically increasing)
    all_entries.sort(key=lambda x: x['start'])
    
    if not all_entries:
        return "Line Source start(s) end(s)", 0
    
    # Calculate time offset
    min_time = min(e['start'] for e in all_entries)
    offset = int(min_time // 10) * 10
    
    # Build output with line numbers and source labels
    output_lines = ["Line Source start(s) end(s)"]
    
    for i, entry in enumerate(all_entries, start=1):
        start = entry['start'] - offset
        end = entry['end'] - offset
        text = _normalize_word(f'"{entry["text"]}"')  # Normalize quotes
        source = entry['source']
        
        # Check if end time equals next start time
        end_str = f"{end:.2f}"
        if i < len(all_entries):
            next_start = all_entries[i]['start'] - offset  # i is 1-based, list is 0-based
            if abs(end - next_start) < 0.001:
                end_str = "~"
        
        output_lines.append(f"{i} {source} {start:.2f} {end_str} {text}")
    
    return '\n'.join(output_lines), offset
