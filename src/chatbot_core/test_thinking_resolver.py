import unittest
import sys
from pathlib import Path

# Ensure `src/` is on sys.path so `import chatbot_core...` works when running via unittest.
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chatbot_core.thinking_resolver import resolve_thinking_from_scheme, resolve_thinking
from chatbot_core.model_resolver import ModelResolver


class TestThinkingResolver(unittest.TestCase):
    def test_openai_compatible_reasoning_effort(self):
        scheme = {
            "provider-kind": "openai-compatible",
            "openai-compatible": {
                "reasoning-effort-param": "reasoning_effort",
                "level-effort": {
                    "no": "minimal",
                    "low": "low",
                    "mid": "medium",
                    "high": "high",
                },
            },
        }

        res = resolve_thinking_from_scheme(
            provider_kind="openai-compatible",
            scheme=scheme,
            max_thinking_tokens=None,
            requested_level="mid",
            ui_supported_levels=["auto", "no", "low", "mid", "high"],
        )
        self.assertEqual(res.openai_params.get("reasoning_effort"), "medium")

    def test_openai_extra_body_enable_thinking(self):
        scheme = {
            "provider-kind": "openai-extra-body",
            "openai-extra-body": {
                "param-name": "enable_thinking",
                "level-value": {"no": False, "yes": True},
            },
        }

        res = resolve_thinking_from_scheme(
            provider_kind="openai-extra-body",
            scheme=scheme,
            max_thinking_tokens=None,
            requested_level="yes",
            ui_supported_levels=["no", "yes"],
        )
        self.assertEqual(res.openai_extra_body.get("enable_thinking"), True)

    def test_gemini_budget_percent_mapping_clamps_min(self):
        scheme = {
            "provider-kind": "google-gemini",
            "gemini": {
                "mode": "thinking_budget",
                "level-budget-percent": {"low": 0.01},
                "min-enabled-budget": 128,
            },
        }

        res = resolve_thinking_from_scheme(
            provider_kind="google-gemini",
            scheme=scheme,
            max_thinking_tokens=1000,
            requested_level="low",
            ui_supported_levels=["auto", "no", "low", "mid", "high"],
        )
        self.assertEqual(res.gemini_thinking_config.get("thinking_budget"), 128)

    def test_gemini_level_no_fallback(self):
        scheme = {
            "provider-kind": "google-gemini",
            "gemini": {
                "mode": "thinking_level",
                "level-enum": {"low": "LOW", "mid": "MEDIUM", "high": "HIGH"},
                "no-fallback-level": "MINIMAL",
            },
        }

        res = resolve_thinking_from_scheme(
            provider_kind="google-gemini",
            scheme=scheme,
            max_thinking_tokens=None,
            requested_level="no",
            ui_supported_levels=["auto", "low", "mid", "high"],
        )
        self.assertEqual(res.gemini_thinking_config.get("thinking_level"), "MINIMAL")

    def test_smoke_resolve_from_real_config(self):
        """
        Non-network smoke test: load config.yaml, resolve a model config, and resolve thinking.
        """
        resolver = ModelResolver()
        cfg = resolver.resolve("gemini-2.5-flash", "aihubmix")
        self.assertIsNotNone(cfg)
        res = resolve_thinking(cfg, None, task_key="assemble-sentence")
        self.assertIsInstance(res.ui_supported_levels, list)


if __name__ == "__main__":
    unittest.main()

