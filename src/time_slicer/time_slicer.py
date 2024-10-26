import math

def get_time_slices(total_duration, audio_bitrate):
    """
    Given a total duration in seconds and a file path, return a list of time slices.
    Each slice is about 10 minutes long and the audio track should be about 10-15MB.

    :param total_duration: Total duration of the media file in seconds
    :param file_path: Path to the media file
    :return: List of tuples (start_time, duration)
    """
    target_slice_duration = 600  # 10 minutes in seconds
    max_file_size = 15 * 1024 * 1024  # 15MB in bytes (60% of 25MB)

    # Calculate maximum duration for a 15MB slice
    max_duration = (max_file_size * 8) / audio_bitrate

    slices = []
    current_time = 0

    while current_time < total_duration:
        slice_duration = min(target_slice_duration, max_duration, total_duration - current_time)
        
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
        min_duration = min(target_slice_duration, max_duration)

        if last_slice[1] < min_duration / 2:
            total_time = second_last_slice[1] + last_slice[1]
            new_duration = round(total_time / 2 / 30) * 30
            
            slices[-2] = (second_last_slice[0], new_duration)
            slices[-1] = (second_last_slice[0] + new_duration, math.ceil(total_time - new_duration))

    return pad_intervals_right(slices, 9)

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
    file_path = "mock_media_file.mp4"
    total_duration = 3600  # 1 hour in seconds
    time_slices = get_time_slices(total_duration, file_path)
    for start, duration in time_slices:
        print(f"Start: {start}, Duration: {duration}")

# Call the mock function to demonstrate
#mock_calling_function()
