"""
Response converter for merge overlaps task.

Converts LLM response (line numbers + content) back to original timestamp format.
"""

import re
from typing import Dict, Tuple, Optional


def parse_context_to_line_mapping(
    formatted_context: str,
    time_offset: int
) -> Dict[int, Tuple[float, float, str]]:
    """
    Parse formatted context (with source labeling) to build line number mapping.
    
    Input format:
        Line Source start(s) end(s)
        1 A 1.11 ~ So,
        2 A 1.34 ~ this
        3 B 1.36 2.10 This
    
    Args:
        formatted_context: Context text with line numbers and source labels
        time_offset: Time offset that was subtracted (to restore original times)
        
    Returns:
        Dict mapping line_num -> (original_start, original_end, word)
    """
    mapping = {}
    lines = formatted_context.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('Line Source'):
            continue
        
        # Parse: line_num source start end_or_tilde word
        # Example: "1 A 1.11 ~ So,"
        match = re.match(r'^(\d+)\s+([AB])\s+([\d.]+)\s+([\d.~]+)\s+(.+)$', line)
        if match:
            line_num = int(match.group(1))
            source = match.group(2)
            start = float(match.group(3))
            end_str = match.group(4)
            word = match.group(5)
            
            # Restore original time (add offset back)
            original_start = start + time_offset
            
            # Handle ~ symbol (will need to look up actual end time)
            if end_str == '~':
                # For now, store None - we'll resolve it when converting
                original_end = None
            else:
                original_end = float(end_str) + time_offset
            
            mapping[line_num] = (original_start, original_end, word)
    
    # Resolve ~ symbols by looking at next entry's start time
    # First pass: identify which entries need resolution
    needs_resolution = {}
    for line_num, (start, end, word) in mapping.items():
        if end is None:
            needs_resolution[line_num] = (start, word)
    
    # Second pass: resolve by finding the next entry chronologically
    for line_num, (start, word) in needs_resolution.items():
        # Find the next entry by start time
        next_start = None
        min_diff = float('inf')
        for other_line, (other_start, other_end, _) in mapping.items():
            if other_line != line_num and other_start > start:
                diff = other_start - start
                if diff < min_diff:
                    min_diff = diff
                    next_start = other_start
        
        if next_start is not None:
            mapping[line_num] = (start, next_start, word)
        else:
            # No next entry found, use start + 1.0 as fallback
            mapping[line_num] = (start, start + 1.0, word)
    
    return mapping


def convert_response_to_timestamps(
    response_text: str,
    line_mapping: Dict[int, Tuple[float, float, str]]
) -> str:
    """
    Convert LLM response (line numbers + content) back to timestamp format.
    
    Input format:
        Time offset: -580s
        1 " "
        2 例えば
        3 極
        
        Time offset: -1190s
        1 " "
        2 そ
    
    Output format:
        Time offset: -580s
        589.12 590.70 " "
        590.70 591.22 例えば
        591.22 591.74 極
        
        Time offset: -1190s
        1199.12 1200.70 " "
        1200.70 1201.22 そ
    
    Args:
        response_text: LLM response text
        line_mapping: Dict mapping line_num -> (original_start, original_end, word)
        
    Returns:
        Converted text with timestamps restored
    """
    lines = response_text.strip().split('\n')
    output_lines = []
    current_offset = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            output_lines.append('')
            continue
        
        # Check for offset header
        offset_match = re.match(r'^Time offset:\s*-?(\d+)s?$', line)
        if offset_match:
            current_offset = int(offset_match.group(1))
            output_lines.append(line)
            continue
        
        # Parse line: line_num content
        # Example: "1 " "" or "2 例えば"
        match = re.match(r'^(\d+)\s+(.+)$', line)
        if match:
            line_num = int(match.group(1))
            content = match.group(2)
            
            # Look up original timestamps
            if line_num in line_mapping:
                start, end, original_word = line_mapping[line_num]
                # Use the original timestamps, format to 2 decimal places
                output_lines.append(f"{start:.2f} {end:.2f} {content}")
            else:
                # Line number not found in mapping, keep as-is
                output_lines.append(line)
        else:
            # Not a recognized format, keep as-is
            output_lines.append(line)
    
    return '\n'.join(output_lines)


def convert_response_incremental(
    response_chunk: str,
    line_mapping: Dict[int, Tuple[float, float, str]],
    buffer: str = ""
) -> Tuple[str, str]:
    """
    Incrementally convert response chunks during streaming.
    
    Args:
        response_chunk: New chunk of response text
        line_mapping: Dict mapping line_num -> (original_start, original_end, word)
        buffer: Accumulated incomplete lines from previous chunks
        
    Returns:
        Tuple of (converted_output, remaining_buffer)
    """
    # Add chunk to buffer
    buffer += response_chunk
    
    # Split by newlines, keep incomplete last line in buffer
    lines = buffer.split('\n')
    if not buffer.endswith('\n'):
        # Last line is incomplete, keep it in buffer
        buffer = lines[-1]
        lines = lines[:-1]
    else:
        buffer = ""
    
    # Convert complete lines
    converted_lines = []
    current_offset = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            converted_lines.append('')
            continue
        
        # Check for offset header
        offset_match = re.match(r'^Time offset:\s*-?(\d+)s?$', line)
        if offset_match:
            current_offset = int(offset_match.group(1))
            converted_lines.append(line)
            continue
        
        # Parse line: line_num content
        match = re.match(r'^(\d+)\s+(.+)$', line)
        if match:
            line_num = int(match.group(1))
            content = match.group(2)
            
            if line_num in line_mapping:
                start, end, original_word = line_mapping[line_num]
                converted_lines.append(f"{start:.2f} {end:.2f} {content}")
            else:
                converted_lines.append(line)
        else:
            converted_lines.append(line)
    
    converted_output = '\n'.join(converted_lines)
    if converted_output:
        converted_output += '\n'
    
    return converted_output, buffer


def convert_response_incremental_multiregion(
    response_chunk: str,
    line_mappings: Dict[int, Dict[int, Tuple[float, float, str]]],
    buffer: str = "",
    current_offset: int = 0
) -> Tuple[str, str, int]:
    """
    Incrementally convert response chunks during streaming (multi-region support).
    
    Supports multiple regions with different Time offsets but overlapping line numbers.
    
    Args:
        response_chunk: New chunk of response text
        line_mappings: Dict mapping offset -> {line_num -> (original_start, original_end, word)}
        buffer: Accumulated incomplete lines from previous chunks
        current_offset: Current Time offset being processed
        
    Returns:
        Tuple of (converted_output, remaining_buffer, updated_offset)
    """
    # Add chunk to buffer
    buffer += response_chunk
    
    # Split by newlines, keep incomplete last line in buffer
    lines = buffer.split('\n')
    if not buffer.endswith('\n'):
        # Last line is incomplete, keep it in buffer
        buffer = lines[-1]
        lines = lines[:-1]
    else:
        buffer = ""
    
    # Convert complete lines
    converted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            converted_lines.append('')
            continue
        
        # Check for offset header
        offset_match = re.match(r'^Time offset:\s*-?(\d+)s?$', line)
        if offset_match:
            current_offset = int(offset_match.group(1))
            converted_lines.append(line)
            continue
        
        # Parse line: line_num content
        match = re.match(r'^(\d+)\s+(.+)$', line)
        if match:
            line_num = int(match.group(1))
            content = match.group(2)
            
            # Look up in the mapping for current offset
            if current_offset in line_mappings:
                region_mapping = line_mappings[current_offset]
                if line_num in region_mapping:
                    start, end, original_word = region_mapping[line_num]
                    converted_lines.append(f"{start:.2f} {end:.2f} {content}")
                else:
                    converted_lines.append(line)
            else:
                # Offset not found, keep original
                converted_lines.append(line)
        else:
            converted_lines.append(line)
    
    converted_output = '\n'.join(converted_lines)
    if converted_output:
        converted_output += '\n'
    
    return converted_output, buffer, current_offset
