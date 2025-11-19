import math

PADDING = 9  # seconds
SLICE_DURATION_MINUTES = 10
TARGET_MAX_FILE_SIZE = 25 * 1024 * 1024  # 15MB in bytes (60% of 25MB), not hard limit
MIN_TRANSCODE_BITRATE = 128000  # 128kbps - minimum bitrate for transcoding

def get_time_slices(total_duration, audio_bitrate, can_copy_codec, has_perturbation):
    """
    Given media information, return time slices with transcoding decision.
    
    Logic:
    - can_copy = (format can copy) AND NOT (perturbation enabled)
    - If can_copy: slice by input size, each slice <= TARGET_MAX_FILE_SIZE and <= 10min
    - If not can_copy: 
        - output_bitrate = max(MIN_TRANSCODE_BITRATE, input_bitrate)
        - output_format = m4a
        - slice by output size, each slice <= TARGET_MAX_FILE_SIZE and <= 10min

    :param total_duration: Total duration of the media file in seconds
    :param audio_bitrate: Audio bitrate in bits per second
    :param can_copy_codec: Whether the audio codec can be copied without re-encoding
    :param has_perturbation: Whether audio perturbation is enabled
    :return: Tuple (slices, needs_transcoding, output_bitrate, output_format)
    """
    minutes = 60  # 1min = 60s
    target_slice_duration = SLICE_DURATION_MINUTES * minutes  # 10 minutes in seconds

    # Determine if we can copy codec
    can_copy = can_copy_codec and not has_perturbation
    
    if can_copy:
        # Can copy: use input bitrate for calculation
        effective_bitrate = audio_bitrate
        needs_transcoding = False
        output_format = None  # Keep original format
    else:
        # Need to transcode: use max(MIN_TRANSCODE_BITRATE, input_bitrate)
        effective_bitrate = max(MIN_TRANSCODE_BITRATE, audio_bitrate)
        needs_transcoding = True
        output_format = 'm4a'  # Always output to m4a when transcoding
    
    # Calculate maximum duration for a slice with TARGET_MAX_FILE_SIZE
    # Formula: duration = (file_size_bytes * 8) / bitrate_bps
    max_duration_by_size = math.floor((TARGET_MAX_FILE_SIZE * 8) / effective_bitrate)

    # Calculate maximum duration for a slice: min(10min, max_duration_by_size)
    max_duration = min(target_slice_duration, max_duration_by_size)

    slices = []
    current_time = 0

    while current_time < total_duration:
        # Each slice duration: min(max_duration, remaining_time)
        slice_duration = min(max_duration, math.ceil(total_duration - current_time))
        
        # Round start time to nearest 30 seconds for human-friendliness
        rounded_start = round(current_time / 30) * 30
        
        # Adjust slice duration to maintain overall timing
        adjusted_duration = slice_duration - (rounded_start - current_time)
        
        slices.append((rounded_start, adjusted_duration))
        current_time = rounded_start + adjusted_duration

    # New logic to adjust the last two slices if needed
    if len(slices) > 1:
        last_slice = slices[-1]
        second_last_slice = slices[-2]

        if last_slice[1] < max_duration / 2:
            total_time = second_last_slice[1] + last_slice[1]
            new_duration = round(total_time / 2 / 30) * 30
            
            slices[-2] = (second_last_slice[0], new_duration)
            slices[-1] = (second_last_slice[0] + new_duration, math.ceil(total_time - new_duration))

    return pad_intervals_right(slices, PADDING), needs_transcoding, effective_bitrate, output_format

def pad_intervals_right(intervals, padding):
    """
    Extend each interval to the right by a given amount to create overlapping.
    
    :param intervals: List of tuples representing time intervals (start, duration)
    :param padding: Amount to extend each interval by (in seconds)
    :return: List of extended intervals
    """
    padded_intervals = []
    for i, (start, duration) in enumerate(intervals):
        if i == len(intervals) - 1:
            # Don't pad the last interval
            padded_intervals.append((start, duration))
        else:
            padded_intervals.append((start, duration + padding))
    return padded_intervals

# Usage example:
# file_path = "path/to/your/media/file.mp4"
# total_duration = float(ffmpeg.probe(file_path)['streams'][0]['duration'])
# time_slices = get_time_slices(total_duration, file_path)
# for start, duration in time_slices:
#     print(f"Start: {start}, Duration: {duration}")

def mock_calling_function():
    total_duration = 3600  # 1 hour in seconds
    audio_bitrate = 320000  # 320kbps
    
    print("Test 1: Can copy, no perturbation")
    time_slices, needs_transcoding, eff_br, fmt = get_time_slices(total_duration, audio_bitrate, True, False)
    print(f"  Needs transcoding: {needs_transcoding}, Effective bitrate: {eff_br/1000:.0f}kbps, Format: {fmt}")
    print(f"  Slices: {len(time_slices)}")
    
    print("\nTest 2: Can copy, with perturbation")
    time_slices, needs_transcoding, eff_br, fmt = get_time_slices(total_duration, audio_bitrate, True, True)
    print(f"  Needs transcoding: {needs_transcoding}, Effective bitrate: {eff_br/1000:.0f}kbps, Format: {fmt}")
    print(f"  Slices: {len(time_slices)}")
    
    print("\nTest 3: Cannot copy, no perturbation")
    time_slices, needs_transcoding, eff_br, fmt = get_time_slices(total_duration, audio_bitrate, False, False)
    print(f"  Needs transcoding: {needs_transcoding}, Effective bitrate: {eff_br/1000:.0f}kbps, Format: {fmt}")
    print(f"  Slices: {len(time_slices)}")

# Call the mock function to demonstrate
#mock_calling_function()
