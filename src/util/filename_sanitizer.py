"""
Filename sanitizer utility for preventing Windows MAX_PATH errors.

This module provides a centralized implementation of filename sanitization
and truncation logic used by both the transcriber and GUI components.
"""

import re
import hashlib
import platform
from pathlib import Path


class FilenameSanitizer:
    """
    Sanitizes and truncates filenames to prevent Windows MAX_PATH (260 char) errors.
    """
    
    def __init__(self, result_dir: Path, max_path_length: int = 240):
        """
        Initialize the sanitizer.
        
        Args:
            result_dir: The base directory where results will be stored
            max_path_length: Maximum path length (default 240, conservative for Windows)
        """
        self.result_dir = Path(result_dir)
        self.max_path_length = max_path_length
        self.max_stem_length = self._calculate_max_stem_length()
    
    def _calculate_max_stem_length(self) -> int:
        """
        Calculate the maximum safe filename stem length.
        
        Returns:
            int: Maximum length for filename stems
        """
        default_max = 200  # Default for non-Windows systems
        
        if platform.system() != "Windows":
            return default_max
        
        # Account for the longest possible suffix we generate:
        # /<safe_stem>/<safe_stem>_ss{start}-t{duration}_cut_result.json
        # Estimate: subdirectory separator + filename with timestamps + extension
        FILENAME_SUFFIX_MARGIN = 80
        
        abs_result_dir_len = len(str(self.result_dir.resolve()))
        
        # Calculate available length for stem (used twice: in directory and filename)
        available_length = self.max_path_length - abs_result_dir_len - FILENAME_SUFFIX_MARGIN
        calculated_stem_length = available_length // 2
        
        # Ensure minimum viable length
        return max(20, calculated_stem_length)
    
    def sanitize(self, filename: str) -> str:
        """
        Sanitize filename and apply hash-based truncation if needed.
        
        Args:
            filename: Original filename to sanitize
            
        Returns:
            str: Sanitized filename, potentially with hash suffix if truncated
        """
        # Step 1: Basic sanitization of illegal characters
        # Remove/replace: < > : " | ? * and control characters
        sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '_', filename)
        
        # Replace brackets with parentheses (safer for paths)
        sanitized = sanitized.replace('[', '(').replace(']', ')')
        
        # Remove multiple consecutive spaces and replace with single space
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        sanitized = sanitized.rstrip('.-_ ')
        
        # Ensure the result is not empty
        if not sanitized:
            sanitized = "unnamed_file"
        
        # Step 2: Check if truncation and hashing are needed
        if len(sanitized) <= self.max_stem_length:
            return sanitized
        
        # Generate deterministic hash from original filename to ensure uniqueness
        hash_suffix = hashlib.sha1(filename.encode('utf-8')).hexdigest()[:8]
        
        # Calculate prefix length to fit within our limit
        prefix_length = self.max_stem_length - len(hash_suffix) - 1  # -1 for underscore
        prefix_length = max(1, prefix_length)  # Ensure at least 1 character for prefix
        
        # Truncate and combine with hash
        truncated_prefix = sanitized[:prefix_length].rstrip('.-_ ')
        if not truncated_prefix:  # Fallback if prefix becomes empty
            truncated_prefix = "file"
        
        result = f"{truncated_prefix}_{hash_suffix}"
        return result
    
    def get_max_stem_length(self) -> int:
        """Get the calculated maximum stem length."""
        return self.max_stem_length

