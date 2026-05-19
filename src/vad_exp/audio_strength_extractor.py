"""Audio strength extraction helpers for the VAD experimental timeline."""

from __future__ import annotations

import math
import subprocess

import ffmpeg
import numpy as np

from src.vad.models import VadTimeRange


class AudioStrengthExtractionCancelled(Exception):
    """Raised when a long-running audio extraction is cancelled."""


def strength_bin_count(duration_sec: float, points_per_second: int) -> int:
    return max(int(math.ceil(max(float(duration_sec), 0.0) * int(points_per_second))), 1)


def extract_audio_strength_series(
    media_path: str,
    duration_sec: float,
    points_per_second: int = 50,
    sample_rate: int = 8000,
    should_stop=None,
    normalize: bool = True,
) -> np.ndarray:
    """Extract full-length RMS bins for a media file."""
    expected_bins = strength_bin_count(duration_sec, points_per_second)
    return _extract_audio_strength_bins(
        media_path=media_path,
        expected_bins=expected_bins,
        points_per_second=points_per_second,
        sample_rate=sample_rate,
        should_stop=should_stop,
        normalize=normalize,
    )


def extract_audio_strength_range_series(
    media_path: str,
    time_range: VadTimeRange,
    points_per_second: int = 50,
    sample_rate: int = 8000,
    should_stop=None,
    normalize: bool = False,
) -> np.ndarray:
    """Extract range-scoped RMS bins aligned to the provided range."""
    expected_bins = strength_bin_count(time_range.duration_sec, points_per_second)
    return _extract_audio_strength_bins(
        media_path=media_path,
        expected_bins=expected_bins,
        points_per_second=points_per_second,
        sample_rate=sample_rate,
        should_stop=should_stop,
        normalize=normalize,
        start_sec=time_range.start_sec,
        duration_sec=time_range.duration_sec,
    )


def _extract_audio_strength_bins(
    media_path: str,
    expected_bins: int,
    points_per_second: int,
    sample_rate: int,
    should_stop=None,
    normalize: bool = True,
    start_sec: float | None = None,
    duration_sec: float | None = None,
) -> np.ndarray:
    if points_per_second <= 0:
        raise ValueError("points_per_second must be positive")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if sample_rate % points_per_second != 0:
        raise ValueError("sample_rate must be divisible by points_per_second")

    samples_per_bin = sample_rate // points_per_second
    input_kwargs = {}
    if start_sec is not None:
        input_kwargs["ss"] = float(start_sec)
    if duration_sec is not None:
        input_kwargs["t"] = float(duration_sec)

    cmd = (
        ffmpeg
        .input(media_path, **input_kwargs)
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

            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
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

    if normalize:
        peak = float(series.max())
        if peak > 0:
            series /= peak

    return series.astype(np.float32)
