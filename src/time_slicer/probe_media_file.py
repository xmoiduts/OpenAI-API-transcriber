import ffmpeg

def probe_media_file(file_path):
    """
    Probes the media file to get its duration and audio bitrate.

    :param file_path: Path to the media file
    :return: Tuple (duration, audio_bitrate)
    """
    probe = ffmpeg.probe(file_path)
    duration = float(probe['streams'][0]['duration'])
    audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
    if audio_stream is None:
        raise ValueError("No audio stream found in the file")
    
    audio_bitrate = int(audio_stream.get('bit_rate', 0))
    if audio_bitrate == 0:
        raise ValueError("Could not determine audio bit rate")
    
    return duration, audio_bitrate