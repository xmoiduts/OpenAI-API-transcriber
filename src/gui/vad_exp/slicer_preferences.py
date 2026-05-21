from __future__ import annotations

from pathlib import Path

import yaml


class VadSlicerPreferences:
    STORAGE_DIR = Path("gui-state") / "vad-slicer"
    STORAGE_FILENAME = "preferences.yaml"
    DEFAULT_PRESET = "~10min"

    def __init__(self):
        self._storage_path = self._project_root() / self.STORAGE_DIR / self.STORAGE_FILENAME

    def load_slice_length_preset(self) -> str:
        try:
            with open(self._storage_path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
        except Exception:
            return self.DEFAULT_PRESET

        slice_length = data.get("slice_length", {})
        preset = slice_length.get("preset")
        if preset in {"~10min", "<3min", "<1min", "<30s"}:
            return preset
        return self.DEFAULT_PRESET

    def save_slice_length_preset(self, preset: str):
        if preset not in {"~10min", "<3min", "<1min", "<30s"}:
            return
        data = {
            "version": 1,
            "slice_length": {
                "preset": preset,
            },
            "lookaround": {
                "~10min": {"before_seconds": 60, "after_seconds": 60},
                "<3min": {"before_seconds": 60, "after_seconds": 0},
                "<1min": {"before_seconds": 30, "after_seconds": 0},
                "<30s": {"before_seconds": 30, "after_seconds": 0},
            },
        }
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "w", encoding="utf-8") as file:
                yaml.safe_dump(data, file, allow_unicode=True, default_flow_style=False)
        except Exception as exc:
            print(f"[VadSlicerPreferences] Error saving preferences: {exc}")

    @staticmethod
    def _project_root() -> Path:
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "config.yaml").exists() or (parent / "config.example.yaml").exists():
                return parent
        return Path(".")
