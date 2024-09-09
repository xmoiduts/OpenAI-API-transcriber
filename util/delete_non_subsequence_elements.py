import json
import sys
import os
from typing import List, Dict
import difflib
from collections import OrderedDict
import re
import time

def locate_non_subsequence_elements(A_raw: list, B: str):
    """
    input:
        A_raw: list of {"word": str, "start": str(float), "end": str(float)}
            and each "word" has length of >= 1
        B: str
    A_raw["word"], when removing some minor elements, should add up to a subsequence of B
    Our mission is to find their indexes in "words" list.
    """
    A, mapping = [], [] # flattened A_raw["word"] that forms a str; idx of each char in that str.
    for i, s in enumerate(A_raw): A.extend(s["word"]); mapping.extend([i] * len(s["word"])) # build index LUT
    #print("      " + " ".join([b if b != " " else " ␣" for b in B])) # 横轴
    m, n = len(A), len(B)
    #print(m, n)
    # --- LCS variant ---
    dp = [[0] * (n + 1) for _ in range(m + 1)] 
    # I didn't check this, claude 3.5 sonnet did them all.
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if A[i-1] == B[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    #[print( "  " if i == 0 else A[i-1], # 纵轴
    #        ' '.join(f'{num:{2}}' for num in dp[i])) 
    #        for i in range(m+1)]
    to_delete_indices = set()
    i, j = m, n
    while i > 0 and j > 0:
        if A[i-1] == B[j-1]:
            i -= 1
            j -= 1
        elif dp[i-1][j] > dp[i][j-1]:
            to_delete_indices.add(i-1)
            i -= 1
        else:
            j -= 1

    while i > 0:
        to_delete_indices.add(i-1)
        i -= 1
    
    to_delete_in_A_raw = [mapping[i] for i in to_delete_indices]
    to_delete_in_A_raw = set(to_delete_in_A_raw)
    #print(mapping) # 横轴
    print("delete: ", [A[i] for i in to_delete_indices])
    
    return to_delete_in_A_raw

def is_subsequence(A2: list, B: str):
    # Test if A2 (token-precise words) join up to the subsequence of B (full text of a segment returned by transcribe API like whisper)
    # A2: list of dict item: {"word", "start", "end"}
    A = "".join([w["word"] for w in A2])
    i = j = 0
    while i < len(A) and j < len(B):
        if A[i] == B[j]:
            i += 1
        j += 1
    print("i:", i, A[i])
    return i == len(A)

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

def print_test_result(file, probe_subsequence):
    color = GREEN if probe_subsequence else RED
    result = "passed" if probe_subsequence else "failed"
    print(f"{file} {color}{result}{RESET} the subsequence test")

def load_json(file_path: str) -> Dict:
    """Load JSON file."""
    print(f"loading file {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file {file_path}.", file=sys.stderr)
        sys.exit(1)

file = 'nnhr-unsubsequenced.json'

data = load_json(os.path.join('./transcription_result', file))

probe_subsequence = is_subsequence(data["words"], data["text"])
print_test_result(file, probe_subsequence)

remove_indexes = locate_non_subsequence_elements(data["words"], data["text"])
print(remove_indexes)
