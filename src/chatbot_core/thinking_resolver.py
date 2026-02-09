"""
Thinking level resolver.

Normalizes GUI-facing thinking levels:
  auto / no / low / mid / high

Into provider-specific request parameters, driven by config.yaml:
  - root.thinking-level-schemes
  - api.models.<model>.thinking-level-scheme
  - api.models.<model>.max-thinking-tokens (required for percent -> budget mapping)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .model_resolver import ResolvedModelConfig


NormalizedThinkingLevel = str  # "auto" | "no" | "low" | "mid" | "high"


SUPPORTED_NORMALIZED_LEVELS: Tuple[NormalizedThinkingLevel, ...] = (
    "auto",
    "no",
    "yes",
    "low",
    "mid",
    "high",
)


@dataclass(frozen=True)
class ThinkingResolution:
    provider_kind: str
    effective_level: NormalizedThinkingLevel
    ui_supported_levels: List[NormalizedThinkingLevel]

    # Provider-specific payload fragments
    openai_params: Dict[str, Any] = field(default_factory=dict)
    # For OpenAI-compatible SDKs that accept extra_body (e.g. Qwen enable_thinking)
    openai_extra_body: Dict[str, Any] = field(default_factory=dict)
    gemini_thinking_config: Dict[str, Any] = field(default_factory=dict)
    anthropic_params: Dict[str, Any] = field(default_factory=dict)

    warnings: List[str] = field(default_factory=list)


def _find_config() -> Path:
    """
    Find config.yaml by searching parent directories (same strategy as ModelResolver).
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        config_path = parent / "config.yaml"
        if config_path.exists():
            return config_path
    return Path("config.yaml")


_CACHED_ROOT_CONFIG: Optional[Dict[str, Any]] = None
_CACHED_ROOT_CONFIG_PATH: Optional[Path] = None


def load_root_config(config_path: Optional[Path] = None, *, force_reload: bool = False) -> Dict[str, Any]:
    global _CACHED_ROOT_CONFIG, _CACHED_ROOT_CONFIG_PATH

    path = config_path or _find_config()
    if not force_reload and _CACHED_ROOT_CONFIG is not None and _CACHED_ROOT_CONFIG_PATH == path:
        return _CACHED_ROOT_CONFIG

    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        cfg = {}
        # Keep this silent-ish; callers can still proceed without thinking config.
        print(f"[ThinkingResolver] Warning: failed to load config.yaml for thinking schemes: {e}")

    _CACHED_ROOT_CONFIG = cfg
    _CACHED_ROOT_CONFIG_PATH = path
    return cfg


def get_task_default_thinking_level(root_config: Dict[str, Any], task_key: str) -> Optional[str]:
    """
    Read defaults like:
      tasks:
        sentence-builder:
          assemble-sentence:
            default-thinking-level: low
    """
    tasks = (root_config or {}).get("tasks", {}) or {}
    sb = tasks.get("sentence-builder", {}) or {}
    task_cfg = sb.get(task_key, {}) or {}
    return task_cfg.get("default-thinking-level")


def resolve_thinking(
    model_config: ResolvedModelConfig,
    requested_level: Optional[NormalizedThinkingLevel],
    *,
    task_key: Optional[str] = None,
    root_config: Optional[Dict[str, Any]] = None,
) -> ThinkingResolution:
    """
    Resolve a normalized thinking level into provider-specific request parameters.

    - If the model has no thinking scheme: returns auto with empty params.
    - If requested_level is None: uses task default when provided, else auto.
    """
    root = root_config if root_config is not None else load_root_config()

    model_raw = model_config.raw_model_config or {}
    scheme_name = model_raw.get("thinking-level-scheme")
    max_thinking_tokens = model_raw.get("max-thinking-tokens")

    if requested_level is None:
        if task_key:
            requested_level = get_task_default_thinking_level(root, task_key)  # type: ignore[assignment]
        requested_level = requested_level or "auto"

    if requested_level not in SUPPORTED_NORMALIZED_LEVELS:
        requested_level = "auto"

    schemes = (root.get("thinking-level-schemes", {}) or {}) if isinstance(root, dict) else {}
    scheme = schemes.get(scheme_name, {}) if scheme_name else {}

    if not scheme:
        # No scheme for this model: keep behavior backward compatible.
        return ThinkingResolution(
            provider_kind="none",
            effective_level="auto",
            ui_supported_levels=list(SUPPORTED_NORMALIZED_LEVELS),
        )

    provider_kind = scheme.get("provider-kind", "none")
    ui_supported = scheme.get("supported-levels") or list(SUPPORTED_NORMALIZED_LEVELS)
    if not isinstance(ui_supported, list):
        ui_supported = list(SUPPORTED_NORMALIZED_LEVELS)

    return resolve_thinking_from_scheme(
        provider_kind=provider_kind,
        scheme=scheme,
        max_thinking_tokens=max_thinking_tokens,
        requested_level=requested_level,
        ui_supported_levels=[x for x in ui_supported if x in SUPPORTED_NORMALIZED_LEVELS],
    )


def resolve_thinking_from_scheme(
    *,
    provider_kind: str,
    scheme: Dict[str, Any],
    max_thinking_tokens: Optional[int],
    requested_level: NormalizedThinkingLevel,
    ui_supported_levels: List[NormalizedThinkingLevel],
) -> ThinkingResolution:
    """
    Pure resolution logic; suitable for unit tests.
    """
    warnings: List[str] = []

    # Best-effort minimum: even if UI disables "no", we still map it safely.
    effective_level: NormalizedThinkingLevel = requested_level

    if provider_kind == "openai-compatible":
        cfg = scheme.get("openai-compatible", {}) or {}
        param_name = cfg.get("reasoning-effort-param", "reasoning_effort")
        effort_map = cfg.get("level-effort", {}) or {}

        # "yes" is treated as "high" for schemes that don't explicitly support it.
        if requested_level == "yes":
            requested_level = "high"
            effective_level = "high"

        if requested_level == "auto":
            return ThinkingResolution(
                provider_kind=provider_kind,
                effective_level="auto",
                ui_supported_levels=ui_supported_levels,
            )

        # "no" becomes best-effort minimum
        effort = effort_map.get(requested_level) or effort_map.get("no") or "minimal"
        return ThinkingResolution(
            provider_kind=provider_kind,
            effective_level=effective_level,
            ui_supported_levels=ui_supported_levels,
            openai_params={param_name: effort},
        )

    if provider_kind == "openai-extra-body":
        ocfg = scheme.get("openai-extra-body", {}) or {}
        param_name = ocfg.get("param-name") or "enable_thinking"
        level_value = (ocfg.get("level-value", {}) or {}) if isinstance(ocfg, dict) else {}

        # Normalize "low/mid/high" into "yes" for single-toggle thinking models.
        if requested_level in ("low", "mid", "high"):
            requested_level = "yes"
            effective_level = "yes"

        if requested_level == "auto":
            # Omit (let server default)
            return ThinkingResolution(
                provider_kind=provider_kind,
                effective_level="auto",
                ui_supported_levels=ui_supported_levels,
            )

        if requested_level not in ("no", "yes"):
            requested_level = "auto"
            effective_level = "auto"
            return ThinkingResolution(
                provider_kind=provider_kind,
                effective_level="auto",
                ui_supported_levels=ui_supported_levels,
                warnings=["Unsupported thinking level for openai-extra-body; omitting extra_body."],
            )

        # Default mapping when config omitted
        if requested_level == "yes":
            value = level_value.get("yes", True)
        else:
            value = level_value.get("no", False)

        return ThinkingResolution(
            provider_kind=provider_kind,
            effective_level=effective_level,
            ui_supported_levels=ui_supported_levels,
            openai_extra_body={param_name: value},
        )

    if provider_kind == "google-gemini":
        gcfg = scheme.get("gemini", {}) or {}
        mode = gcfg.get("mode")

        # Best-effort: treat "yes" as "high" for Gemini schemes.
        if requested_level == "yes":
            requested_level = "high"
            effective_level = "high"

        if requested_level == "auto":
            if mode == "thinking_budget" and "auto-thinking-budget" in gcfg:
                return ThinkingResolution(
                    provider_kind=provider_kind,
                    effective_level="auto",
                    ui_supported_levels=ui_supported_levels,
                    gemini_thinking_config={"thinking_budget": gcfg.get("auto-thinking-budget")},
                )
            # For thinking_level mode, "auto" means omit.
            return ThinkingResolution(
                provider_kind=provider_kind,
                effective_level="auto",
                ui_supported_levels=ui_supported_levels,
            )

        if mode == "thinking_level":
            enum_map = gcfg.get("level-enum", {}) or {}
            if requested_level == "no":
                level_enum = gcfg.get("no-fallback-level") or "MINIMAL"
                warnings.append("Requested 'no' thinking for Gemini thinking_level; using minimum level fallback.")
            else:
                level_enum = enum_map.get(requested_level) or enum_map.get("low") or "LOW"
            return ThinkingResolution(
                provider_kind=provider_kind,
                effective_level=effective_level,
                ui_supported_levels=ui_supported_levels,
                gemini_thinking_config={"thinking_level": level_enum},
                warnings=warnings,
            )

        # thinking_budget mode
        if requested_level == "no":
            if "no-thinking-budget" in gcfg:
                return ThinkingResolution(
                    provider_kind=provider_kind,
                    effective_level=effective_level,
                    ui_supported_levels=ui_supported_levels,
                    gemini_thinking_config={"thinking_budget": gcfg.get("no-thinking-budget")},
                )
            # best-effort minimum for schemes that don't support 0
            min_enabled = int(gcfg.get("min-enabled-budget", 0) or 0)
            warnings.append("Requested 'no' thinking for Gemini thinking_budget; scheme has no no-thinking-budget, using minimum enabled budget.")
            return ThinkingResolution(
                provider_kind=provider_kind,
                effective_level=effective_level,
                ui_supported_levels=ui_supported_levels,
                gemini_thinking_config={"thinking_budget": min_enabled},
                warnings=warnings,
            )

        percent_map = (gcfg.get("level-budget-percent", {}) or {}) if isinstance(gcfg, dict) else {}
        percent = percent_map.get(requested_level)
        if percent is None:
            percent = percent_map.get("low", 0.15)

        if max_thinking_tokens is None:
            warnings.append("Model is missing max-thinking-tokens; falling back to fixed budget 1024.")
            budget = 1024
        else:
            budget = int(round(float(max_thinking_tokens) * float(percent)))

        min_enabled = int(gcfg.get("min-enabled-budget", 0) or 0)
        if budget < min_enabled:
            budget = min_enabled
        if budget < 0:
            budget = 0

        return ThinkingResolution(
            provider_kind=provider_kind,
            effective_level=effective_level,
            ui_supported_levels=ui_supported_levels,
            gemini_thinking_config={"thinking_budget": budget},
            warnings=warnings,
        )

    if provider_kind == "anthropic":
        acfg = scheme.get("anthropic", {}) or {}

        # Best-effort: treat "yes" as "high" for Anthropic schemes.
        if requested_level == "yes":
            requested_level = "high"
            effective_level = "high"

        if requested_level in ("auto", "no"):
            return ThinkingResolution(
                provider_kind=provider_kind,
                effective_level=requested_level,
                ui_supported_levels=ui_supported_levels,
            )

        percent_map = (acfg.get("level-budget-percent", {}) or {}) if isinstance(acfg, dict) else {}
        percent = percent_map.get(requested_level)
        if percent is None:
            percent = percent_map.get("low", 0.25)

        if max_thinking_tokens is None:
            warnings.append("Model is missing max-thinking-tokens; falling back to minimum enabled budget.")
            budget = int(acfg.get("min-enabled-budget", 1024) or 1024)
        else:
            budget = int(round(float(max_thinking_tokens) * float(percent)))

        min_enabled = int(acfg.get("min-enabled-budget", 1024) or 1024)
        if budget < min_enabled:
            budget = min_enabled

        return ThinkingResolution(
            provider_kind=provider_kind,
            effective_level=requested_level,
            ui_supported_levels=ui_supported_levels,
            anthropic_params={"thinking": {"type": "enabled", "budget_tokens": budget}},
            warnings=warnings,
        )

    # Unknown scheme kind: ignore.
    return ThinkingResolution(
        provider_kind="none",
        effective_level="auto",
        ui_supported_levels=list(SUPPORTED_NORMALIZED_LEVELS),
        warnings=["Unknown provider-kind for thinking scheme; ignoring."],
    )

