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

__all__ = [
    'TimeReversal',
    'TimestampEntry',
    'find_time_reversals',
    'get_reversal_contexts',
    'parse_timestamp_file',
]
