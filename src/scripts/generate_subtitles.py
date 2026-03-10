import re
import os
from typing import Optional


def sec_to_srt(seconds):
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm"""
    seconds = float(seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    if s >= 60:
        m += 1
        s = 0
    if m >= 60:
        h += 1
        m = 0
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def parse_line(line):
    """Parse a line to extract start time, end time (optional), and text.
    Returns dict {'start': float, 'end': float|None, 'text': str} or None.
    """
    match = re.match(r'\{([\d\.]+)\} \{([\d\.]+)\}\s*(.*)', line)
    if match:
        return {'start': float(match.group(1)), 'end': float(match.group(2)), 'text': match.group(3).strip()}

    match = re.match(r'\{([\d\.]+)\}\s*(.*)', line)
    if match:
        return {'start': float(match.group(1)), 'end': None, 'text': match.group(2).strip()}

    return None


def check_monotonicity(entries: list) -> list:
    """Check that timestamp entries have non-decreasing start times.

    Returns a list of violation dicts:
        {index, expected_min_start, actual_start, text}
    """
    violations = []
    for i in range(1, len(entries)):
        if entries[i]['start'] < entries[i - 1]['start']:
            violations.append({
                'index': i,
                'expected_min_start': entries[i - 1]['start'],
                'actual_start': entries[i]['start'],
                'text': entries[i]['text'],
            })
    return violations


def generate_subtitles(orig_path, trans_path, output_path) -> Optional[dict]:
    """Generate bilingual SRT subtitles from original and translation files.

    Returns a result dict on success::

        {
            'num_entries': int,
            'monotonicity_warnings': list[dict],
            'orphan_merges': list[dict],
            'unmatched_originals': int,
        }

    Returns None when input files are missing.
    """
    if not os.path.exists(orig_path) or not os.path.exists(trans_path):
        print(f"Error: Input files not found. Expected {orig_path} and {trans_path}")
        return None

    with open(trans_path, 'r', encoding='utf-8') as f_trans, \
         open(orig_path, 'r', encoding='utf-8') as f_orig:
        lines_trans = f_trans.readlines()
        lines_orig = f_orig.readlines()

    trans_entries = []
    for line in lines_trans:
        p = parse_line(line)
        if p:
            trans_entries.append(p)

    orig_entries = []
    for line in lines_orig:
        p = parse_line(line)
        if p and p['end'] is not None:
            orig_entries.append(p)

    monotonicity_warnings = check_monotonicity(trans_entries)

    # --- Matching loop with orphan-merge ---------------------------------
    # "宁可错位不要缺失": when a translation entry cannot find a matching
    # original, merge its text into the most recently matched subtitle
    # rather than discarding it.

    tolerance = 0.1  # seconds
    trans_idx = 0
    n_trans = len(trans_entries)

    # Each element: {'start', 'end', 'text_orig', 'text_trans'}
    subtitle_records: list[dict] = []
    orphan_merges: list[dict] = []
    unmatched_originals = 0
    # Orphan translations that arrive before any original record exists
    # are stashed here and prepended to the first record.
    deferred_orphan_texts: list[str] = []

    for orig in orig_entries:
        start = orig['start']
        end = orig['end']
        text_orig = orig['text']

        # Collect orphan translations whose start time is before this
        # original (outside tolerance).  Merge them upward into the
        # previous subtitle record instead of discarding.
        while trans_idx < n_trans and trans_entries[trans_idx]['start'] < start - tolerance:
            orphan = trans_entries[trans_idx]
            if subtitle_records:
                prev = subtitle_records[-1]
                prev['text_trans'] += " " + orphan['text']
                orphan_merges.append({
                    'trans_index': trans_idx,
                    'trans_start': orphan['start'],
                    'merged_into_orig_start': prev['start'],
                    'text': orphan['text'],
                })
            else:
                deferred_orphan_texts.append(orphan['text'])
                orphan_merges.append({
                    'trans_index': trans_idx,
                    'trans_start': orphan['start'],
                    'merged_into_orig_start': start,
                    'text': orphan['text'],
                })
            trans_idx += 1

        text_trans = ""
        if trans_idx < n_trans:
            t_entry = trans_entries[trans_idx]
            if abs(t_entry['start'] - start) <= tolerance:
                text_trans = t_entry['text']
                trans_idx += 1
            else:
                unmatched_originals += 1
        else:
            unmatched_originals += 1

        if deferred_orphan_texts:
            prefix = " ".join(deferred_orphan_texts)
            text_trans = (prefix + " " + text_trans) if text_trans else prefix
            deferred_orphan_texts.clear()

        if not text_trans:
            text_trans = "-"

        subtitle_records.append({
            'start': start,
            'end': end,
            'text_orig': text_orig,
            'text_trans': text_trans,
        })

    # Remaining translation entries after the last original: merge upward
    while trans_idx < n_trans:
        orphan = trans_entries[trans_idx]
        if subtitle_records:
            prev = subtitle_records[-1]
            prev['text_trans'] += " " + orphan['text']
            orphan_merges.append({
                'trans_index': trans_idx,
                'trans_start': orphan['start'],
                'merged_into_orig_start': prev['start'],
                'text': orphan['text'],
            })
        trans_idx += 1

    # --- Build SRT blocks ------------------------------------------------
    subtitles = []
    for counter, rec in enumerate(subtitle_records, 1):
        block = f"{counter}\n{sec_to_srt(rec['start'])} --> {sec_to_srt(rec['end'])}\n"
        block += f"{rec['text_trans']}\n"
        block += f"{rec['text_orig']}\n\n"
        subtitles.append(block)

    with open(output_path, 'w', encoding='utf-8') as f_out:
        f_out.writelines(subtitles)

    num_entries = len(subtitle_records)
    print(f"Generated subtitles at: {output_path} with {num_entries} entries.")

    return {
        'num_entries': num_entries,
        'monotonicity_warnings': monotonicity_warnings,
        'orphan_merges': orphan_merges,
        'unmatched_originals': unmatched_originals,
    }

if __name__ == "__main__":
    # Input files
    file_orig = "句轴原文.txt"
    file_trans = "句轴译文.txt"
    # Output file
    file_out = "whisper-transcribed-subtitles.srt"
    
    generate_subtitles(file_orig, file_trans, file_out)
