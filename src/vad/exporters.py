"""
Export utilities for VAD analysis results.

Pure functions with no GUI dependencies; reusable from scripts and GUI code.
"""

from __future__ import annotations

import os

from src.scripts.generate_subtitles import sec_to_srt

from .models import SpeechSegment


def build_empty_sentences_srt_filename(engine_display_name: str) -> str:
    """Build output filename: empty_sentences_<engine_name_no_spaces>.srt"""
    safe_name = engine_display_name.replace(" ", "")
    return f"empty_sentences_{safe_name}.srt"


def export_vad_blocks_to_srt(
    speech_segments: list[SpeechSegment],
    output_path: str,
    placeholder_text: str = ".",
) -> dict:
    """Write VAD speech segments as placeholder SRT entries.

    Each block uses ``placeholder_text`` (default ``.``) as the subtitle body.

    Returns:
        {"num_entries": int, "output_path": str}

    Raises:
        ValueError: when ``speech_segments`` is empty.
    """
    if not speech_segments:
        raise ValueError("No VAD blocks to export.")

    sorted_segments = sorted(speech_segments, key=lambda seg: (seg.start_sec, seg.end_sec))

    blocks: list[str] = []
    for index, segment in enumerate(sorted_segments, 1):
        block = (
            f"{index}\n"
            f"{sec_to_srt(segment.start_sec)} --> {sec_to_srt(segment.end_sec)}\n"
            f"{placeholder_text}\n\n"
        )
        blocks.append(block)

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.writelines(blocks)

    return {"num_entries": len(sorted_segments), "output_path": output_path}
