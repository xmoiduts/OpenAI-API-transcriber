"""
Audio waveform extraction for the Sentence Aligner drawing zone.

Pipeline: ffmpeg decodes a time range to raw PCM mono 16-bit,
numpy computes RMS amplitude per time bin for visualization.
"""

import subprocess
import numpy as np
import ffmpeg


def extract_amplitude_bins(
    media_path: str,
    start_sec: float,
    duration_sec: float,
    num_bins: int = 800,
    sample_rate: int = 8000,
) -> np.ndarray:
    """Extract RMS amplitude bins from a media file segment.

    Args:
        media_path: Path to the media file (any format ffmpeg supports).
        start_sec: Start time in seconds.
        duration_sec: Duration in seconds.
        num_bins: Number of output amplitude bins (matches pixel columns).
        sample_rate: Decode sample rate. 8000 Hz is sufficient for envelope.

    Returns:
        1-D numpy float32 array of length num_bins, values in [0.0, 1.0].
    """
    raw_bytes = _decode_pcm(media_path, start_sec, duration_sec, sample_rate)
    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)

    if len(samples) == 0:
        return np.zeros(num_bins, dtype=np.float32)

    return _rms_bins(samples, num_bins)


def _decode_pcm(
    media_path: str,
    start_sec: float,
    duration_sec: float,
    sample_rate: int,
) -> bytes:
    """Use ffmpeg to decode a segment to raw PCM s16le mono."""
    stream = (
        ffmpeg
        .input(media_path, ss=start_sec, t=duration_sec)
        .output("pipe:", format="s16le", acodec="pcm_s16le", ac=1, ar=sample_rate)
    )
    cmd = ["ffmpeg", *stream.get_args()]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"ffmpeg decode failed (rc={process.returncode}): {err.decode(errors='replace')[:500]}"
        )
    return out


def _rms_bins(samples: np.ndarray, num_bins: int) -> np.ndarray:
    """Compute RMS amplitude per bin then normalize to [0, 1]."""
    n = len(samples)
    if n < num_bins:
        num_bins = n

    bin_size = n // num_bins
    trimmed = samples[: bin_size * num_bins]
    reshaped = trimmed.reshape(num_bins, bin_size)

    rms = np.sqrt(np.mean(reshaped ** 2, axis=1))

    peak = rms.max()
    if peak > 0:
        rms /= peak

    return rms.astype(np.float32)
