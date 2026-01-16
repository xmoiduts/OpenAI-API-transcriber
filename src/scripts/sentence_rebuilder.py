"""
Sentence Rebuilder - Rebuilds sentences from word timestamps

Input:
- sentence_only_timestamp.csv: Contains sentence start timestamps (one per line)
- merged_word_timestamps.csv: Contains word-level timestamps in format: start end "word"

Output:
- Sentence file in format: {start} {end} sentence_content
- For space-only sentences: {start} {end} " "
- For normal sentences: no quotes around the content
"""

import argparse
import re
from pathlib import Path
from typing import List, Tuple


def parse_word_timestamps(filepath: Path) -> List[Tuple[float, float, str]]:
    """
    Parse merged_word_timestamps.csv
    Format: start_time end_time "word"
    Returns list of (start, end, word) tuples
    """
    words = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Parse: 74.00 75.00 "あ"
            # Match: start end "content" where content can contain anything
            match = re.match(r'^([\d.]+)\s+([\d.]+)\s+"(.*)"\s*$', line)
            if match:
                start = float(match.group(1))
                end = float(match.group(2))
                word = match.group(3)
                words.append((start, end, word))
    return words


def parse_sentence_timestamps(filepath: Path) -> List[float]:
    """
    Parse sentence_only_timestamp.csv
    Format: one timestamp per line (sentence start time)
    Returns list of sentence start timestamps
    """
    timestamps = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                timestamps.append(float(line))
            except ValueError:
                continue
    return timestamps


def build_sentences(
    words: List[Tuple[float, float, str]],
    sentence_starts: List[float]
) -> List[Tuple[float, float, str]]:
    """
    Build sentences from words based on sentence start timestamps.
    
    Returns list of (start, end, sentence_text) tuples.
    
    Note: Space-only tokens (" ") at sentence boundaries are treated as separators.
    - Trailing space tokens are excluded from sentence end time
    - Leading space tokens are excluded from sentence content
    - But if a sentence contains ONLY space, preserve it as " "
    """
    if not words or not sentence_starts:
        return []
    
    sentences = []
    word_idx = 0
    num_words = len(words)
    
    for i, sent_start in enumerate(sentence_starts):
        # Determine sentence end boundary (next sentence start or end of words)
        if i + 1 < len(sentence_starts):
            sent_end_boundary = sentence_starts[i + 1]
        else:
            sent_end_boundary = float('inf')
        
        # Collect words for this sentence (with their timestamps)
        sentence_word_data = []  # List of (start, end, word)
        
        # Move to words that belong to this sentence
        while word_idx < num_words:
            w_start, w_end, word = words[word_idx]
            
            # Word belongs to this sentence if its start >= sentence start
            # and its start < next sentence start
            if w_start >= sent_start and w_start < sent_end_boundary:
                sentence_word_data.append((w_start, w_end, word))
                word_idx += 1
            elif w_start >= sent_end_boundary:
                # This word belongs to next sentence
                break
            else:
                # Skip words before sentence start (shouldn't happen normally)
                word_idx += 1
        
        # Process the collected words
        # Remove trailing space-only tokens (separator between sentences)
        while sentence_word_data and sentence_word_data[-1][2] == ' ':
            sentence_word_data.pop()
        
        # Build sentence text and find end time
        if sentence_word_data:
            sentence_words = [w[2] for w in sentence_word_data]
            sentence_text = ''.join(sentence_words)
            sentence_end = max(w[1] for w in sentence_word_data)
        else:
            # Empty sentence (only had space separators)
            sentence_text = ' '
            sentence_end = sent_start
        
        sentences.append((sent_start, sentence_end, sentence_text))
    
    return sentences


def format_output(sentences: List[Tuple[float, float, str]]) -> str:
    """
    Format sentences for output.
    - Normal sentences: {start} {end} content
    - Space-only sentences: {start} {end} " "
    """
    lines = []
    for start, end, text in sentences:
        # Check if text is only whitespace
        if text.strip() == '':
            # For space-only sentences, wrap in quotes
            lines.append(f'{{{start:.2f}}} {{{end:.2f}}} " "')
        else:
            # Normal sentences without quotes
            lines.append(f'{{{start:.2f}}} {{{end:.2f}}} {text}')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Rebuild sentences from word timestamps'
    )
    parser.add_argument(
        '-i', '--input-dir',
        type=str,
        required=True,
        help='Input directory containing sentence_only_timestamp.csv and merged_word_timestamps.csv'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output file path (default: input_dir/句轴原文.txt)'
    )
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    
    sentence_ts_file = input_dir / 'sentence_only_timestamp.csv'
    word_ts_file = input_dir / 'merged_word_timestamps.csv'
    
    if not sentence_ts_file.exists():
        print(f"Error: {sentence_ts_file} not found")
        return 1
    
    if not word_ts_file.exists():
        print(f"Error: {word_ts_file} not found")
        return 1
    
    # Parse input files
    print(f"Reading word timestamps from: {word_ts_file}")
    words = parse_word_timestamps(word_ts_file)
    print(f"  Found {len(words)} words")
    
    print(f"Reading sentence timestamps from: {sentence_ts_file}")
    sentence_starts = parse_sentence_timestamps(sentence_ts_file)
    print(f"  Found {len(sentence_starts)} sentences")
    
    # Build sentences
    print("Building sentences...")
    sentences = build_sentences(words, sentence_starts)
    
    # Format output
    output_text = format_output(sentences)
    
    # Write output
    output_path = Path(args.output) if args.output else input_dir / '句轴原文.txt'
    print(f"Writing output to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output_text)
    
    print(f"Done! Generated {len(sentences)} sentences.")
    return 0


if __name__ == '__main__':
    exit(main())
