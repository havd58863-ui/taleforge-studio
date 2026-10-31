"""Print-grade text setting: justified paragraphs, hyphenation, widow control.

The story engine hands raw strings to this service; it returns real typographic
results (line count, used height, overflow remainder) so the renderer can flow text
into a fixed print block without guessing character counts.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph

from app.services.fonts import FontBook, get_font_book, is_arabic, shape_text

MM_PER_INCH = 25.4
ALIGNMENTS = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT, "justify": TA_JUSTIFY}

# Language codes -> pyphen/reportlab hyphenation dictionaries
HYPHENATION_LANG = {
    "en": "en_US",
    "fr": "fr_FR",
    "es": "es_ES",
    "de": "de_DE",
    "ar": None,  # Arabic is not hyphenated
    "it": "it_IT",
    "pt": "pt_PT",
    "nl": "nl_NL",
}


@dataclass
class TextStyle:
    font_size: float = 13.0
    leading_ratio: float = 1.45
    alignment: str = "justify"
    hyphenate: bool = True
    language: str = "en"
    color: str = "#1F2733"
    first_line_indent_mm: float = 0.0
    space_after_pt: float = 6.0
    bold: bool = False

    @property
    def leading(self) -> float:
        return round(self.font_size * self.leading_ratio, 2)


@dataclass
class TextFitResult:
    fitted: bool
    font_size: float
    leading: float
    lines: int
    used_height_mm: float
    overflow_text: str
    font_name: str
    hyphenated: bool
    rendered_text: str = ""
    widow_adjustment: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "fitted": self.fitted,
            "font_size": self.font_size,
            "leading": self.leading,
            "lines": self.lines,
            "used_height_mm": round(self.used_height_mm, 2),
            "overflow_text": self.overflow_text,
            "font_name": self.font_name,
            "hyphenated": self.hyphenated,
            "rendered_text": self.rendered_text,
            "widow_adjustment": self.widow_adjustment,
        }


class TextLayoutService:
    """Sets text into a measured block (millimetres in, typographic result out)."""

    MIN_FONT_SIZE = 9.0
    WIDOW_STEP = 0.03          # shrink block width by 3% per attempt
    WIDOW_MAX_ATTEMPTS = 3

    def __init__(self, font_book: Optional[FontBook] = None) -> None:
        self.font_book = font_book or get_font_book()

    # ---------- styles ----------
    def build_style(self, text: str, style: TextStyle, width_pt: float) -> ParagraphStyle:
        font_name = self.font_book.get(text, bold=style.bold)
        hyphen_lang = HYPHENATION_LANG.get(style.language, None) if style.hyphenate else None
        kwargs = dict(
            fontName=font_name,
            fontSize=style.font_size,
            leading=style.leading,
            alignment=ALIGNMENTS.get(style.alignment, TA_JUSTIFY),
            textColor=colors.HexColor(style.color),
            firstLineIndent=style.first_line_indent_mm * 72 / MM_PER_INCH,
            spaceAfter=style.space_after_pt,
            allowWidows=0,
            allowOrphans=0,
        )
        if hyphen_lang:
            try:
                kwargs["hyphenationLang"] = hyphen_lang
            except Exception:  # pragma: no cover - older ReportLab
                pass
        return ParagraphStyle("body", **kwargs)

    @staticmethod
    def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
        safe = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return Paragraph(shape_text(safe), style)

    def _measure(self, text: str, width_pt: float, pstyle: ParagraphStyle) -> tuple[int, float]:
        paragraph = self._paragraph(text, pstyle)
        _, height = paragraph.wrap(width_pt, 10_000)
        lines = len(getattr(paragraph.blPara, "lines", []) or [])
        return lines, height

    # ---------- fitting ----------
    def layout(
        self,
        text: str,
        width_mm: float,
        height_mm: float,
        style: Optional[TextStyle] = None,
        min_font_size: Optional[float] = None,
    ) -> TextFitResult:
        """Fit ``text`` into a box, shrinking type and finally splitting the overflow."""
        style = style or TextStyle()
        min_size = min_font_size or self.MIN_FONT_SIZE
        width_pt = max(10.0, width_mm * 72 / MM_PER_INCH)
        height_pt = max(10.0, height_mm * 72 / MM_PER_INCH)

        if is_arabic(text) or style.language == "ar":
            font_name = self.font_book.get(text, bold=style.bold)
            size = style.font_size
            while size >= min_size:
                lines, height = self._rtl_measure(text, width_pt, height_pt, style, size, font_name)
                if height <= height_pt:
                    return TextFitResult(
                        fitted=True, font_size=size, leading=round(size * style.leading_ratio, 2),
                        lines=lines, used_height_mm=round(height / 72 * MM_PER_INCH, 2),
                        overflow_text="", font_name=font_name, hyphenated=False, rendered_text=text,
                    )
                size -= 0.5
            lines, height = self._rtl_measure(text, width_pt, height_pt, style, min_size, font_name)
            return TextFitResult(
                fitted=False, font_size=min_size, leading=round(min_size * style.leading_ratio, 2),
                lines=lines, used_height_mm=round(height / 72 * MM_PER_INCH, 2),
                overflow_text="", font_name=font_name, hyphenated=False, rendered_text=text,
            )

        size = style.font_size
        while size >= min_size:
            pstyle = self.build_style(text, replace(style, font_size=size), width_pt)
            lines, height = self._measure(text, width_pt, pstyle)
            if height <= height_pt:
                result = TextFitResult(
                    fitted=True,
                    font_size=size,
                    leading=round(size * style.leading_ratio, 2),
                    lines=lines,
                    used_height_mm=height / 72 * MM_PER_INCH,
                    overflow_text="",
                    font_name=pstyle.fontName,
                    hyphenated=bool(getattr(pstyle, "hyphenationLang", None)),
                    rendered_text=text,
                )
                return self._control_widows(text, width_pt, height_pt, style, size, result)
            size -= 0.5

        # Still too long at the minimum size: split at a word boundary.
        head, tail = self._split_to_fit(text, width_pt, height_pt, style, min_size)
        pstyle = self.build_style(head, replace(style, font_size=min_size), width_pt)
        lines, height = self._measure(head, width_pt, pstyle)
        return TextFitResult(
            fitted=False,
            font_size=min_size,
            leading=round(min_size * style.leading_ratio, 2),
            lines=lines,
            used_height_mm=height / 72 * MM_PER_INCH,
            overflow_text=tail,
            font_name=pstyle.fontName,
            hyphenated=bool(getattr(pstyle, "hyphenationLang", None)),
            rendered_text=head,
        )

    def _split_to_fit(
        self, text: str, width_pt: float, height_pt: float, style: TextStyle, size: float
    ) -> tuple[str, str]:
        words = text.split()
        best = 0
        low, high = 1, len(words)
        while low <= high:
            mid = (low + high) // 2
            candidate = " ".join(words[:mid])
            pstyle = self.build_style(candidate, replace(style, font_size=size), width_pt)
            _, height = self._measure(candidate, width_pt, pstyle)
            if height <= height_pt:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        best = max(1, best)
        return " ".join(words[:best]), " ".join(words[best:])

    def _control_widows(
        self,
        text: str,
        width_pt: float,
        height_pt: float,
        style: TextStyle,
        size: float,
        result: TextFitResult,
    ) -> TextFitResult:
        """If the last line is a single word, tighten the measure and re-wrap."""
        for attempt in range(1, self.WIDOW_MAX_ATTEMPTS + 1):
            pstyle = self.build_style(text, replace(style, font_size=size), width_pt)
            paragraph = self._paragraph(text, pstyle)
            paragraph.wrap(width_pt, height_pt)
            lines = getattr(paragraph.blPara, "lines", []) or []
            if len(lines) < 2:
                return result
            last_line = lines[-1]
            words_in_last = len(str(getattr(last_line, "words", [])))
            if words_in_last > 1:
                return result

            narrowed = width_pt * (1 - self.WIDOW_STEP * attempt)
            narrowed_style = self.build_style(text, replace(style, font_size=size), narrowed)
            new_lines, new_height = self._measure(text, narrowed, narrowed_style)
            if new_height <= height_pt and new_lines < len(lines):
                result.widow_adjustment = round(1 - narrowed / width_pt, 3)
                result.lines = new_lines
                result.used_height_mm = new_height / 72 * MM_PER_INCH
                return result
        return result

    # ---------- right-to-left (Arabic) ----------
    @staticmethod
    def _break_logical_lines(text: str, width_pt: float, font_name: str, font_size: float) -> list:
        """Wrap in logical order — required for RTL, where bidi must run per line."""
        words = text.split()
        lines: list = []
        current: list = []
        for word in words:
            trial = " ".join(current + [word])
            width = pdfmetrics.stringWidth(trial, font_name, font_size)
            if width <= width_pt or not current:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines

    def _rtl_measure(self, text: str, width_pt: float, height_pt: float, style: TextStyle,
                     size: float, font_name: str) -> tuple[int, float]:
        lines = self._break_logical_lines(text, width_pt, font_name, size)
        leading = size * style.leading_ratio
        return len(lines), len(lines) * leading

    def draw_rtl_block(
        self,
        c: rl_canvas.Canvas,
        text: str,
        width_mm: float,
        height_mm: float,
        x_mm: float,
        top_y_mm: float,
        bleed_mm: float,
        style: Optional[TextStyle] = None,
        min_font_size: Optional[float] = None,
    ) -> TextFitResult:
        style = style or TextStyle()
        min_size = min_font_size or self.MIN_FONT_SIZE
        width_pt = max(10.0, width_mm * 72 / MM_PER_INCH)
        height_pt = max(10.0, height_mm * 72 / MM_PER_INCH)
        font_name = self.font_book.get(text, bold=style.bold)

        size = style.font_size
        lines: list = []
        while size >= min_size:
            lines = self._break_logical_lines(text, width_pt, font_name, size)
            if len(lines) * size * style.leading_ratio <= height_pt:
                break
            size -= 0.5

        leading = size * style.leading_ratio
        max_lines = max(1, int(height_pt // leading))
        fitted = len(lines) <= max_lines
        drawn_lines = lines[:max_lines]
        overflow = " ".join(lines[max_lines:])

        k = 72 / MM_PER_INCH
        x_right_pt = (x_mm + width_mm + bleed_mm) * k
        y = (top_y_mm + bleed_mm) * k - leading

        c.saveState()
        c.setFillColor(colors.HexColor(style.color))
        c.setFont(font_name, size)
        for line in drawn_lines:
            c.drawRightString(x_right_pt, y, shape_text(line))
            y -= leading
        c.restoreState()

        return TextFitResult(
            fitted=fitted,
            font_size=size,
            leading=round(leading, 2),
            lines=len(drawn_lines),
            used_height_mm=round(len(drawn_lines) * leading / k, 2),
            overflow_text=overflow,
            font_name=font_name,
            hyphenated=False,
            rendered_text=" ".join(drawn_lines),
        )

    # ---------- drawing ----------
    def draw_block(
        self,
        c: rl_canvas.Canvas,
        text: str,
        width_mm: float,
        height_mm: float,
        x_mm: float,
        top_y_mm: float,
        bleed_mm: float,
        style: Optional[TextStyle] = None,
        min_font_size: Optional[float] = None,
    ) -> TextFitResult:
        """Draw text inside a block. Coordinates are millimetres from the page corner."""
        style = style or TextStyle()
        if is_arabic(text) or style.language == "ar":
            return self.draw_rtl_block(
                c, text, width_mm, height_mm, x_mm, top_y_mm, bleed_mm, style, min_font_size
            )

        result = self.layout(text, width_mm, height_mm, style, min_font_size)

        width_pt = max(10.0, width_mm * 72 / MM_PER_INCH)
        effective_style = replace(style, font_size=result.font_size)
        if result.widow_adjustment:
            width_pt *= (1 - result.widow_adjustment)
        pstyle = self.build_style(result.rendered_text, effective_style, width_pt)
        paragraph = self._paragraph(result.rendered_text, pstyle)
        paragraph.wrap(width_pt, height_mm * 72 / MM_PER_INCH)

        x_pt = (x_mm + bleed_mm) * 72 / MM_PER_INCH
        top_pt = (top_y_mm + bleed_mm) * 72 / MM_PER_INCH
        used_pt = paragraph.height
        paragraph.drawOn(c, x_pt, top_pt - used_pt)
        return result
