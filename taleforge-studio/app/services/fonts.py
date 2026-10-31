"""Font registry for print-grade typography.

Bundled faces (SIL Open Font License 1.1, see assets/fonts/OFL-*.txt):

* **Andika** — designed by SIL for literacy learners: unambiguous letterforms
  (a/g/l/I), generous x-height, wide spacing. The right default for picture books.
* **Amiri** — classical Naskh Arabic face, fully shaped and kerned.

Any TTF dropped into ``assets/fonts`` or ``$FONT_DIR`` is picked up; if nothing is
found the renderer falls back to the built-in Helvetica metrics (Latin only).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:  # optional Arabic shaping
    import arabic_reshaper  # type: ignore
    from bidi.algorithm import get_display  # type: ignore

    ARABIC_SHAPING = True
except Exception:  # pragma: no cover
    ARABIC_SHAPING = False

FONT_DIRS = [
    Path(os.getenv("FONT_DIR", "")) if os.getenv("FONT_DIR") else None,
    Path(__file__).resolve().parent.parent.parent / "assets" / "fonts",
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/noto"),
    Path("/usr/share/fonts/truetype"),
]

# family -> {weight: filename}
CANDIDATES: Dict[str, Dict[str, str]] = {
    "andika": {"regular": "Andika-Regular.ttf", "bold": "Andika-Bold.ttf"},
    "amiri": {"regular": "Amiri-Regular.ttf", "bold": "Amiri-Bold.ttf"},
    "dejavu": {"regular": "DejaVuSans.ttf", "bold": "DejaVuSans-Bold.ttf"},
    "noto": {"regular": "NotoSans-Regular.ttf", "bold": "NotoSans-Bold.ttf"},
}

LATIN_PREFERENCE = ["andika", "dejavu", "noto"]
ARABIC_PREFERENCE = ["amiri", "noto", "dejavu"]

ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))


def is_arabic(text: str) -> bool:
    for char in text or "":
        code = ord(char)
        if any(start <= code <= end for start, end in ARABIC_RANGES):
            return True
    return False


def shape_text(text: str) -> str:
    """Arabic shaping + bidi reordering when the optional libs are installed."""
    if not text or not ARABIC_SHAPING or not is_arabic(text):
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:  # pragma: no cover
        return text


class FontBook:
    """Resolves a (script, weight) pair to a registered PDF font name."""

    _instance: Optional["FontBook"] = None

    def __init__(self) -> None:
        self.registered: Dict[str, Dict[str, str]] = {}
        self._scan()

    # ---------- registration ----------
    def _scan(self) -> None:
        for directory in FONT_DIRS:
            if directory is None or not Path(directory).exists():
                continue
            for family, files in CANDIDATES.items():
                if family in self.registered:
                    continue
                found: Dict[str, str] = {}
                for weight, filename in files.items():
                    path = Path(directory) / filename
                    if not path.exists():
                        continue
                    name = path.stem.replace("-", "")
                    try:
                        if name not in pdfmetrics.getRegisteredFontNames():
                            pdfmetrics.registerFont(TTFont(name, str(path)))
                        found[weight] = name
                    except Exception:  # pragma: no cover - corrupt font file
                        continue
                if "regular" in found:
                    found.setdefault("bold", found["regular"])
                    self.registered[family] = found

    # ---------- lookup ----------
    @property
    def has_unicode_fonts(self) -> bool:
        return bool(self.registered)

    def family_for(self, text: str = "") -> Optional[str]:
        preference = ARABIC_PREFERENCE if is_arabic(text) else LATIN_PREFERENCE
        for family in preference:
            if family in self.registered:
                return family
        return next(iter(self.registered), None)

    def get(self, text: str = "", bold: bool = False) -> str:
        family = self.family_for(text)
        if family is None:
            return "Helvetica-Bold" if bold else "Helvetica"
        weight = "bold" if bold else "regular"
        return self.registered[family][weight]

    def describe(self) -> Dict[str, object]:
        return {
            "fonts": self.registered,
            "arabic_shaping": ARABIC_SHAPING,
            "unicode_ready": self.has_unicode_fonts,
            "search_paths": [str(p) for p in FONT_DIRS if p],
        }


def get_font_book() -> FontBook:
    if FontBook._instance is None:
        FontBook._instance = FontBook()
    return FontBook._instance
