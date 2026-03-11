"""
Audio strength extraction for the VAD experimental timeline.

Pipeline:
- ffmpeg decodes the full media audio track to mono PCM
- RMS strength is aggregated incrementally into fixed-rate bins
- output is normalized to [0, 1] for timeline rendering
"""

import math
import subprocess

import ffmpeg
import numpy as np


class AudioStrengthExtractionCancelled(Exception):
    """Raised when a long-running audio extraction is cancelled."""


def extract_audio_strength_series(
    media_path: str,
    duration_sec: float,
    points_per_second: int = 50,
    sample_rate: int = 8000,
    should_stop=None,
) -> np.ndarray:
    """Extract full-length normalized RMS bins for a media file."""
    if points_per_second <= 0:
        raise ValueError("points_per_second must be positive")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if sample_rate % points_per_second != 0:
        raise ValueError("sample_rate must be divisible by points_per_second")

    expected_bins = max(int(math.ceil(max(duration_sec, 0.0) * points_per_second)), 1)
    samples_per_bin = sample_rate // points_per_second

    cmd = (
        ffmpeg
        .input(media_path)
        .output("pipe:", format="s16le", acodec="pcm_s16le", ac=1, ar=sample_rate)
        .global_args("-loglevel", "error")
        .overwrite_output()
        .compile()
    )

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=samples_per_bin * 2 * 256,
    )

    rms_bins = []
    accum_sq = 0.0
    accum_count = 0
    chunk_bytes = samples_per_bin * 2 * 512

    try:
        while True:
            if should_stop is not None and should_stop():
                process.terminate()
                raise AudioStrengthExtractionCancelled()

            chunk = process.stdout.read(chunk_bytes)
            if not chunk:
                break

            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            cursor = 0
            while cursor < len(samples):
                if should_stop is not None and should_stop():
                    process.terminate()
                    raise AudioStrengthExtractionCancelled()

                take = min(samples_per_bin - accum_count, len(samples) - cursor)
                segment = samples[cursor:cursor + take]
                accum_sq += float(np.dot(segment, segment))
                accum_count += take
                cursor += take

                if accum_count == samples_per_bin:
                    rms_bins.append(math.sqrt(accum_sq / accum_count))
                    accum_sq = 0.0
                    accum_count = 0

        if accum_count > 0:
            rms_bins.append(math.sqrt(accum_sq / accum_count))

        stderr_output = process.stderr.read()
        return_code = process.wait()
        if return_code != 0:
            message = stderr_output.decode(errors="replace")[:800]
            raise RuntimeError(f"ffmpeg decode failed (rc={return_code}): {message}")

    finally:
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
        if process.poll() is None:
            process.kill()
            process.wait()

    if not rms_bins:
        return np.zeros(expected_bins, dtype=np.float32)

    series = np.asarray(rms_bins, dtype=np.float32)
    if len(series) < expected_bins:
        series = np.pad(series, (0, expected_bins - len(series)))
    elif len(series) > expected_bins:
        series = series[:expected_bins]

    peak = float(series.max())
    if peak > 0:
        series /= peak

    return series.astype(np.float32)
