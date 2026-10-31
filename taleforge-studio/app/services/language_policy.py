"""Which languages the factory is allowed to produce.

The product scope is **English, German, Spanish**. Other language packs stay in the
codebase (nothing was deleted, nothing breaks) but they are *disabled* unless you
explicitly opt in.

    OUTPUT_LANGUAGES=en,de,es      # default
    ALLOW_EXTRA_LANGUAGES=1        # opt-in: re-enable every known language
"""
from __future__ import annotations

import os
from typing import Dict, Iterable, List, Tuple

DEFAULT_LANGUAGES: Tuple[str, ...] = ("en", "de", "es")

# Every language the codebase can technically handle today.
KNOWN_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "ar": "العربية",
}

# Languages whose prose the offline scaffold can actually produce.
SCAFFOLD_LANGUAGES: Tuple[str, ...] = ("en",)

# Right-to-left scripts (engine support retained, output disabled by default).
RTL_LANGUAGES: Tuple[str, ...] = ("ar", "he", "fa", "ur")


def enabled_languages() -> List[str]:
    if os.getenv("ALLOW_EXTRA_LANGUAGES", "0").strip().lower() in {"1", "true", "yes"}:
        return list(KNOWN_LANGUAGES)
    raw = os.getenv("OUTPUT_LANGUAGES", ",".join(DEFAULT_LANGUAGES))
    codes = [code.strip().lower() for code in raw.split(",") if code.strip()]
    return [code for code in codes if code in KNOWN_LANGUAGES] or list(DEFAULT_LANGUAGES)


def is_enabled(code: str) -> bool:
    return (code or "").strip().lower() in enabled_languages()


def language_name(code: str) -> str:
    return KNOWN_LANGUAGES.get((code or "").strip().lower(), code)


def split_requested(requested: Iterable[str] | None) -> Tuple[List[str], List[str]]:
    """Return (allowed, rejected) for a requested list; None → the enabled set."""
    enabled = enabled_languages()
    if not requested:
        return enabled, []
    allowed: List[str] = []
    rejected: List[str] = []
    for code in requested:
        code = (code or "").strip().lower()
        if code in enabled:
            if code not in allowed:
                allowed.append(code)
        else:
            rejected.append(code)
    return allowed or enabled, rejected


def policy() -> Dict[str, object]:
    return {
        "enabled": enabled_languages(),
        "known": KNOWN_LANGUAGES,
        "rtl_engine_available": list(RTL_LANGUAGES),
        "extra_languages_allowed": os.getenv("ALLOW_EXTRA_LANGUAGES", "0").strip().lower() in {"1", "true", "yes"},
        "note": "Product scope: English, German, Spanish. Disabled packs remain in the codebase.",
    }
