"""
Sentence Builder Module - LLM-powered sentence assembly from word-level timestamps.

This module provides tools to:
1. Identify duplicate/repeated words in ASR output
2. Find optimal sentence cutpoints
3. Assemble words into proper sentences

Uses ChatCore for LLM interactions.
"""

from .reverse_dedup import (
    TimeReversal,
    TimestampEntry,
    find_time_reversals,
    get_reversal_contexts,
    parse_timestamp_file,
)

from .response_converter import (
    parse_context_to_line_mapping,
    convert_response_to_timestamps,
    convert_response_incremental,
    convert_response_incremental_multiregion,
)

__all__ = [
    'TimeReversal',
    'TimestampEntry',
    'find_time_reversals',
    'get_reversal_contexts',
    'parse_timestamp_file',
    'parse_context_to_line_mapping',
    'convert_response_to_timestamps',
    'convert_response_incremental',
    'convert_response_incremental_multiregion',
]
