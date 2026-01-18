"""
Sentence Builder Module - LLM-powered sentence assembly from word-level timestamps.

This module provides tools to:
1. Identify duplicate/repeated words in ASR output
2. Find optimal sentence cutpoints
3. Assemble words into proper sentences

Uses ChatCore for LLM interactions.
"""

from .reverse_dedup import find_reverse_duplicates, get_duplicate_contexts

__all__ = ['find_reverse_duplicates', 'get_duplicate_contexts']
