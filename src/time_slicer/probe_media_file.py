import ffmpeg
from pathlib import Path

def probe_media_file(file_path):
    """
    Probes the media file to get its duration, audio bitrate, and format information.

    :param file_path: Path to the media file
    :return: Tuple (duration, audio_bitrate, can_copy_codec)
    """
    probe = ffmpeg.probe(file_path)
    
    # Try to get duration from format, fallback to streams if needed
    try:
        duration = float(probe['format']['duration'])
    except (KeyError, ValueError, TypeError):
        # Fallback to stream duration if format duration is missing
        try:
            duration = float(probe['streams'][0]['duration'])
        except (KeyError, ValueError, TypeError):
            # Try to find any stream with duration
            found_duration = False
            for stream in probe['streams']:
                if 'duration' in stream:
                    duration = float(stream['duration'])
                    found_duration = True
                    break
            
            if not found_duration:
                 raise ValueError("Could not determine file duration")

    audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
    if audio_stream is None:
        raise ValueError("No audio stream found in the file")
    
    audio_bitrate = int(audio_stream.get('bit_rate', 0))
    
    # Heuristics for missing bitrate
    if audio_bitrate == 0:
        # 1. If codec is opus, default to 128k (common for youtube/web)
        audio_codec = audio_stream.get('codec_name', '').lower()
        if audio_codec == 'opus':
             audio_bitrate = 128000
        
        # 2. Fallback to container bitrate (upper bound, safe for slicing size)
        if audio_bitrate == 0:
            try:
                audio_bitrate = int(probe['format']['bit_rate'])
            except (KeyError, ValueError, TypeError):
                pass
    
    if audio_bitrate == 0:
        raise ValueError("Could not determine audio bit rate")
    
    # Check if we can copy the codec without re-encoding
    # Whisper API supports: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm
    # For copy, we need both container and codec to match
    file_ext = Path(file_path).suffix.lower()
    audio_codec = audio_stream.get('codec_name', '').lower()
    
    # Can copy if: 
    # 1. File is .mp3 and codec is mp3
    # 2. File is .m4a/.mp4 and codec is aac
    can_copy_codec = (
        (file_ext == '.mp3' and audio_codec == 'mp3') or
        (file_ext in ['.m4a', '.mp4'] and audio_codec == 'aac')
    )
    
    return duration, audio_bitrate, can_copy_codec
