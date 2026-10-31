"""Bilingual picture books — two languages on one spread, or facing pages.

Product scope: English, German, Spanish (`language_policy`). Supported pairs today:
**EN↔DE** and **ES↔EN** (any pair of enabled languages also works).

Two layouts:

* ``stacked`` — primary language on the upper half of the page, secondary below a rule.
  The standard format for bilingual children's books: the child sees both texts at once.
* ``facing`` — primary on the left page, secondary on the right page (doubles page count,
  better for older readers who read one language at a time).

Nothing here writes or translates text: it takes two already-approved manuscripts that
are aligned page by page, so the editorial gate stays the single source of quality.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.language_policy import enabled_languages, language_name

SUPPORTED_PAIRS = (("en", "de"), ("es", "en"), ("en", "es"), ("de", "en"))
MODES = ("stacked", "facing")


@dataclass
class BilingualBook:
    title_primary: str
    title_secondary: str
    language_primary: str
    language_secondary: str
    mode: str
    pages: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title_primary": self.title_primary,
            "title_secondary": self.title_secondary,
            "language_primary": self.language_primary,
            "language_secondary": self.language_secondary,
            "language_primary_name": language_name(self.language_primary),
            "language_secondary_name": language_name(self.language_secondary),
            "mode": self.mode,
            "page_count": self.page_count,
            "pages": self.pages,
            "warnings": self.warnings,
        }


class BilingualService:
    def build(
        self,
        pages_primary: List[str],
        pages_secondary: List[str],
        language_primary: str = "en",
        language_secondary: str = "de",
        title_primary: str = "",
        title_secondary: str = "",
        mode: str = "stacked",
    ) -> BilingualBook:
        primary = (language_primary or "en").strip().lower()
        secondary = (language_secondary or "de").strip().lower()
        mode = (mode or "stacked").strip().lower()

        if primary not in enabled_languages() or secondary not in enabled_languages():
            raise ValueError(
                f"languages must be enabled ({', '.join(enabled_languages())}); "
                f"got {primary}/{secondary}"
            )
        if primary == secondary:
            raise ValueError("the two languages must differ")
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")

        warnings: List[str] = []
        if len(pages_primary) != len(pages_secondary):
            warnings.append(
                f"page counts differ ({len(pages_primary)} vs {len(pages_secondary)}); "
                "the shorter manuscript was padded with empty pages"
            )
        total = max(len(pages_primary), len(pages_secondary))
        pages: List[Dict[str, Any]] = []

        if mode == "facing":
            for index in range(total):
                text_primary = pages_primary[index] if index < len(pages_primary) else ""
                text_secondary = pages_secondary[index] if index < len(pages_secondary) else ""
                pages.append({
                    "page": len(pages) + 1, "spread": index + 1, "side": "left",
                    "language": primary, "text": text_primary, "primary": text_primary, "secondary": "",
                })
                pages.append({
                    "page": len(pages) + 1, "spread": index + 1, "side": "right",
                    "language": secondary, "text": text_secondary, "primary": text_secondary, "secondary": "",
                })
        else:
            for index in range(total):
                pages.append({
                    "page": index + 1,
                    "language": f"{primary}+{secondary}",
                    "primary": pages_primary[index] if index < len(pages_primary) else "",
                    "secondary": pages_secondary[index] if index < len(pages_secondary) else "",
                })

        return BilingualBook(
            title_primary=title_primary or title_secondary,
            title_secondary=title_secondary or title_primary,
            language_primary=primary,
            language_secondary=secondary,
            mode=mode,
            pages=pages,
            warnings=warnings,
        )

    @staticmethod
    def alignment_report(book: BilingualBook) -> List[str]:
        """Cheap structural check: catches pages where one language is missing."""
        problems: List[str] = []
        for page in book.pages:
            if book.mode == "stacked":
                if not page["primary"] or not page["secondary"]:
                    problems.append(f"page {page['page']}: missing one language")
                else:
                    ratio = len(page["primary"].split()) / max(1, len(page["secondary"].split()))
                    if ratio < 0.5 or ratio > 2.0:
                        problems.append(
                            f"page {page['page']}: word counts differ a lot "
                            f"({len(page['primary'].split())} vs {len(page['secondary'].split())})"
                        )
        return problems

    @staticmethod
    def available_pairs() -> List[Dict[str, str]]:
        return [
            {"primary": a, "secondary": b, "label": f"{language_name(a)} → {language_name(b)}"}
            for a, b in SUPPORTED_PAIRS
            if a in enabled_languages() and b in enabled_languages()
        ]
