def find_overlapping_intervals(intervals):
    """
    Find all overlapping intervals between adjacent pairs.
    
    :param intervals: List of tuples representing time intervals (start, end)
    :return: List of overlapping intervals
    """
    overlapping = []
    for i in range(len(intervals) - 1):
        current_end = intervals[i][1]
        next_start = intervals[i+1][0]
        
        if next_start < current_end:
            overlap_start = next_start
            overlap_end = min(current_end, intervals[i+1][1])
            overlapping.append((overlap_start, overlap_end))

    return overlapping

def pad_intervals(intervals, padding):
    """
    Extend each interval by a given amount in both directions.
    
    :param intervals: List of tuples representing time intervals (start, end)
    :param extension: Amount to extend each interval by (in seconds)
    :return: List of extended intervals
    """
    # usage: overlaps_padded = pad_intervals(overlaps, 10) # for llm
    return [(max(0, start-padding), end+padding) for start, end in intervals]

    from typing import List, Tuple

def is_subsequence(A2: list, B: str):
    # Test if A2 (token-precise words) join up to the subsequence of B (full text of a segment returned by transcribe API like whisper)
    # A2: list of dict item: {"word", "start", "end"}
    A = "".join([w["word"] for w in A2])
    i = j = 0
    while i < len(A) and j < len(B):
        if A[i] == B[j]:
            i += 1
        j += 1
    print("i:", i)
    return i == len(A)

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

def print_test_result(file, probe_subsequence):
    color = GREEN if probe_subsequence else RED
    result = "passed" if probe_subsequence else "failed"
    print(f"{file} {color}{result}{RESET} the subsequence test")

def locate_non_subsequence_elements(A_raw: list, B: str):
    """
    Identifies elements in A_raw that need to be removed to form a subsequence
    of B.

    Args:
    A_raw (list): List of dictionaries, each containing:
        'word' (str), 'start' (str(float)), and 'end' (str(float)).
        Each 'word' has a length of 1 or more.
    B (str): The target string to form a subsequence of.

    Returns:
    set: Indices in A_raw of elements to be removed.

    The function uses a variant of the Longest Common Subsequence (LCS)
    algorithm to identify which elements in A_raw need to be removed so that 
    the remaining elements, when concatenated, form a subsequence of B.
    """

    # Flatten A_raw['word'] into a single string and create an index mapping
    A, mapping = [], []
    for i, s in enumerate(A_raw):
        A.extend(s["word"])
        mapping.extend([i] * len(s["word"]))

    m, n = len(A), len(B)

    # LCS variant: Dynamic Programming
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if A[i-1] == B[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    # Backtrack to find elements to delete
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

    # Add remaining elements in A to deletion set if any
    while i > 0:
        to_delete_indices.add(i-1)
        i -= 1
    
    # Map flattened indices back to A_raw indices
    to_delete_in_A_raw = set(mapping[i] for i in to_delete_indices)

    print("delete: ", [A[i] for i in to_delete_indices])
    
    return to_delete_in_A_raw