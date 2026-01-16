import re
import os

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
    # Try double timestamp: {start} {end} text
    match = re.match(r'\{([\d\.]+)\} \{([\d\.]+)\}\s*(.*)', line)
    if match:
        return {'start': float(match.group(1)), 'end': float(match.group(2)), 'text': match.group(3).strip()}
    
    # Try single timestamp: {start} text
    match = re.match(r'\{([\d\.]+)\}\s*(.*)', line)
    if match:
        return {'start': float(match.group(1)), 'end': None, 'text': match.group(2).strip()}
    
    return None

def generate_subtitles(orig_path, trans_path, output_path):
    """Generate bilingual SRT subtitles from original and translation files."""
    
    if not os.path.exists(orig_path) or not os.path.exists(trans_path):
        print(f"Error: Input files not found. Expected {orig_path} and {trans_path}")
        return

    with open(trans_path, 'r', encoding='utf-8') as f_trans, \
         open(orig_path, 'r', encoding='utf-8') as f_orig:
        
        lines_trans = f_trans.readlines()
        lines_orig = f_orig.readlines()

    # Parse all translation lines first
    trans_entries = []
    for line in lines_trans:
        p = parse_line(line)
        if p:
            trans_entries.append(p)
    
    # Parse all original lines
    orig_entries = []
    for line in lines_orig:
        p = parse_line(line)
        if p and p['end'] is not None:
            orig_entries.append(p)

    subtitles = []
    counter = 1
    
    trans_idx = 0
    n_trans = len(trans_entries)
    tolerance = 0.1 # seconds

    # Process original lines and match with translation by timestamp
    for orig in orig_entries:
        start = orig['start']
        end = orig['end']
        text_orig = orig['text']
        text_trans = ""

        # Advance trans_idx if current trans entry is too old (start time < orig start - tolerance)
        while trans_idx < n_trans and trans_entries[trans_idx]['start'] < start - tolerance:
            trans_idx += 1
        
        # Check if current trans entry matches (within tolerance)
        if trans_idx < n_trans:
            t_entry = trans_entries[trans_idx]
            if abs(t_entry['start'] - start) <= tolerance:
                text_trans = t_entry['text']
                # Optional: advance trans_idx to avoid reusing same translation for next line?
                # Assuming 1-to-1 mapping for timestamps.
                # If multiple orig lines have SAME timestamp, they might share trans or consume sequential trans?
                # Given the data, unique timestamps are likely. 
                # We increment to be safe against duplicates and to move forward.
                trans_idx += 1 

        # Construct SRT entry
        # Format:
        # Seq
        # Start --> End
        # Translation (if available)
        # Original
        
        # Clean up empty translation lines
        block = f"{counter}\n{sec_to_srt(start)} --> {sec_to_srt(end)}\n"
        # Always maintain bilingual format: translation line (even if empty) + original line
        block += f"{text_trans}\n"
        block += f"{text_orig}\n\n"
        
        subtitles.append(block)
        counter += 1
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f_out:
        f_out.writelines(subtitles)
    
    print(f"Generated subtitles at: {output_path} with {counter-1} entries.")

if __name__ == "__main__":
    # Input files
    file_orig = "句轴原文.txt"
    file_trans = "句轴译文.txt"
    # Output file
    file_out = "whisper-transcribed-subtitles.srt"
    
    generate_subtitles(file_orig, file_trans, file_out)
