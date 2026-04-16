from __future__ import annotations

import subprocess
from typing import Callable, Optional

import ffmpeg
import numpy as np

from src.vad.models import SpeechSegment, VadProcessingCancelled, VadTimeRange
from src.vad.ports import VadEnginePort


class SileroVadEngine(VadEnginePort):
    """Silero-backed VAD engine with range-scoped ffmpeg decode.

    Parameter notes and the checklist for adding sibling engines live in
    `doc/vad-engine-silero-integration.md`.
    """

    def __init__(
        self,
        sample_rate: int = 8000,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100,
    ):
        self.sample_rate = int(sample_rate)
        self.threshold = float(threshold)
        self.min_speech_duration_ms = int(min_speech_duration_ms)
        self.min_silence_duration_ms = int(min_silence_duration_ms)
        self._model = None

    @property
    def engine_key(self) -> str:
        return "silero"

    def analyze_range(
        self,
        media_path: str,
        time_range: VadTimeRange,
        media_duration_sec: float,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> list[SpeechSegment]:
        clamped_range = time_range.clamp(0.0, media_duration_sec)
        audio = _decode_audio_range(
            media_path=media_path,
            time_range=clamped_range,
            sample_rate=self.sample_rate,
            should_stop=should_stop,
        )

        if should_stop is not None and should_stop():
            raise VadProcessingCancelled()

        if audio.size == 0:
            return []

        model = self._load_model()
        torch = _import_torch()
        get_speech_timestamps = _import_silero_getter()
        audio_tensor = torch.from_numpy(audio.copy())
        speech_timestamps = get_speech_timestamps(
            audio_tensor,
            model,
            sampling_rate=self.sample_rate,
            threshold=self.threshold,
            min_speech_duration_ms=self.min_speech_duration_ms,
            min_silence_duration_ms=self.min_silence_duration_ms,
            return_seconds=True,
        )

        normalized_segments = []
        for item in speech_timestamps:
            start_sec = float(item["start"]) + clamped_range.start_sec
            end_sec = float(item["end"]) + clamped_range.start_sec
            if end_sec <= start_sec:
                continue
            normalized_segments.append(
                SpeechSegment(
                    start_sec=start_sec,
                    end_sec=end_sec,
                    source_range=clamped_range,
                )
            )
        return normalized_segments

    def _load_model(self):
        if self._model is None:
            load_silero_vad = _import_silero_loader()
            self._model = load_silero_vad()
        return self._model


def _decode_audio_range(
    media_path: str,
    time_range: VadTimeRange,
    sample_rate: int,
    should_stop: Optional[Callable[[], bool]] = None,
) -> np.ndarray:
    cmd = (
        ffmpeg
        .input(media_path, ss=time_range.start_sec, t=time_range.duration_sec)
        .output("pipe:", format="s16le", acodec="pcm_s16le", ac=1, ar=sample_rate)
        .global_args("-loglevel", "error")
        .overwrite_output()
        .compile()
    )

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=sample_rate * 4,
    )
    chunks: list[bytes] = []

    try:
        while True:
            if should_stop is not None and should_stop():
                process.terminate()
                raise VadProcessingCancelled()

            chunk = process.stdout.read(32768)
            if not chunk:
                break
            chunks.append(chunk)

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

    if not chunks:
        return np.zeros(0, dtype=np.float32)

    pcm = np.frombuffer(b"".join(chunks), dtype=np.int16).astype(np.float32)
    if pcm.size == 0:
        return np.zeros(0, dtype=np.float32)
    return pcm / 32768.0


def _import_torch():
    try:
        import torch  # type: ignore
    except ImportError as exc:
        raise ImportError("torch is required for Silero VAD") from exc
    return torch


def _import_silero_loader():
    try:
        from silero_vad import load_silero_vad
    except ImportError as exc:
        raise ImportError("silero-vad is required for Silero VAD") from exc
    return load_silero_vad


def _import_silero_getter():
    try:
        from silero_vad import get_speech_timestamps
    except ImportError as exc:
        raise ImportError("silero-vad is required for Silero VAD") from exc
    return get_speech_timestamps
