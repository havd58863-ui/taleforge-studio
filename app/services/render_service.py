"""PDF rendering for covers and interior pages.

Geometry  : :mod:`app.services.page_layout_service` (single source of truth)
Typography: :mod:`app.services.text_layout_service` (justification, hyphenation, widows)
Fonts     : :mod:`app.services.fonts` (bundled Andika + Amiri, OFL licensed)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.fonts import FontBook, get_font_book
from app.services.page_layout_service import (
    DEFAULT_BLEED_MM,
    DEFAULT_DPI,
    MM_PER_INCH,
    TRIM_SIZES_MM,
    Block,
    PageLayoutService,
    PageLayoutSpec,
)
from app.services.text_layout_service import TextLayoutService, TextStyle

__all__ = ["RenderService", "TRIM_SIZES_MM", "MM_PER_INCH"]

INK = "#1F2733"
MUTED = "#4A5669"
PAPER = "#FFFDF9"
WASH = "#F6F3EE"
ACCENT = "#7DB8A4"
GOLD = "#F5D58C"
PLACEHOLDER_FILL = "#F3EFE7"
PLACEHOLDER_LINE = "#D8D2C4"


class RenderService:
    def __init__(self, output_dir: str = "./output", fonts: Optional[FontBook] = None) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.font_book = fonts or get_font_book()
        self.text = TextLayoutService(self.font_book)
        # kept for backwards compatibility with earlier integrations
        self.font = self.font_book.get("", bold=False) if self.font_book.has_unicode_fonts else None

    # ------------------------------------------------------------------ helpers
    @property
    def _regular(self) -> str:
        return self.font_book.get("", bold=False)

    def _bold(self, text: str = "") -> str:
        return self.font_book.get(text, bold=True)

    @staticmethod
    def _layout(trim_size: str, page_type: str, bleed_mm: float, dpi: int = DEFAULT_DPI) -> PageLayoutSpec:
        return PageLayoutService.build_layout(trim_size=trim_size, page_type=page_type, bleed_mm=bleed_mm, dpi=dpi)

    @staticmethod
    def _metadata(
        c: canvas.Canvas,
        title: str,
        author: str = "",
        subject: str = "",
        keywords: str = "",
    ) -> None:
        """Embed XMP-friendly document info so printers and stores read clean metadata."""
        c.setTitle(title)
        c.setAuthor(author or "TaleForge Studio")
        c.setSubject(subject or "Children's picture book")
        c.setCreator("TaleForge Studio")
        c.setKeywords(keywords or "children's book, picture book, print-ready")
        c.setProducer("TaleForge Studio / ReportLab")

    def _draw_crop_marks(self, c: canvas.Canvas, total_w: float, total_h: float, bleed_mm: float) -> None:
        """Printer crop marks drawn inside the bleed margin (kept off the artwork)."""
        bleed = bleed_mm * mm
        if bleed < 2 * mm:
            return
        length = min(4 * mm, bleed * 0.9)
        c.saveState()
        c.setStrokeColor(colors.HexColor("#101010"))
        c.setLineWidth(0.25)
        corners = [
            (bleed, bleed, 1, 1),
            (total_w - bleed, bleed, -1, 1),
            (bleed, total_h - bleed, 1, -1),
            (total_w - bleed, total_h - bleed, -1, -1),
        ]
        for x, y, dx, dy in corners:
            c.line(x, y, x + dx * length, y)
            c.line(x, y, x, y + dy * length)
        c.restoreState()

    def _draw_trim_guides(self, c: canvas.Canvas, total_w: float, total_h: float, bleed_mm: float) -> None:
        c.saveState()
        c.setStrokeColor(colors.HexColor("#C9CED8"))
        c.setLineWidth(0.4)
        c.setDash(3, 3)
        bleed = bleed_mm * mm
        c.rect(bleed, bleed, total_w - 2 * bleed, total_h - 2 * bleed, fill=0, stroke=1)
        c.restoreState()

    # ------------------------------------------------------------------- cover
    def render_cover_pdf(
        self,
        title: str,
        subtitle: str = "",
        author: str = "",
        output_name: str = "cover.pdf",
        trim_size: str = "US_6_X_9",
        bleed_mm: float = DEFAULT_BLEED_MM,
        include_guides: bool = False,
        accent: str = ACCENT,
        crop_marks: bool = False,
        language: str = "en",
    ) -> str:
        layout = self._layout(trim_size, "single", bleed_mm)
        total_w = layout.page_box_mm[0] * mm
        total_h = layout.page_box_mm[1] * mm

        path = self.output_dir / output_name
        c = canvas.Canvas(str(path), pagesize=(total_w, total_h))
        self._metadata(c, title, author, subtitle, keywords="children's picture book, cover")

        unit = min(total_w, total_h)
        c.setFillColor(colors.HexColor(WASH))
        c.rect(0, 0, total_w, total_h, fill=1, stroke=0)

        c.setFillColor(colors.HexColor(accent))
        c.circle(total_w * 0.97, total_h * 0.90, unit * 0.22, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(GOLD))
        c.circle(total_w * 0.03, total_h * 0.10, unit * 0.15, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(PAPER))
        c.rect(0, total_h * 0.34, total_w, total_h * 0.30, fill=1, stroke=0)

        # Title block, set with the typography engine
        title_mm = total_w / mm
        block_w_mm = title_mm * 0.78
        result = self.text.layout(title, block_w_mm, 40, TextStyle(
            font_size=28 if len(title) < 34 else 24,
            alignment="center",
            color=INK,
            bold=True,
            hyphenate=False,
            language=language,
            leading_ratio=1.15,
        ))
        title_style = TextStyle(
            font_size=result.font_size,
            alignment="center",
            color=INK,
            bold=True,
            hyphenate=False,
            language=language,
            leading_ratio=1.15,
        )
        title_top_mm = (total_h / mm) * 0.60
        self.text.draw_block(
            c, title, block_w_mm, 40, (title_mm - block_w_mm) / 2, title_top_mm, bleed_mm, title_style
        )

        y_cursor_mm = title_top_mm - (result.used_height_mm + 6)
        if subtitle:
            sub = self.text.layout(subtitle, title_mm * 0.72, 24, TextStyle(
                font_size=13, alignment="center", color=MUTED, hyphenate=False, language=language
            ))
            self.text.draw_block(
                c, subtitle, title_mm * 0.72, 24, title_mm * 0.14, y_cursor_mm, bleed_mm,
                TextStyle(font_size=sub.font_size, alignment="center", color=MUTED, hyphenate=False, language=language),
            )
            y_cursor_mm -= sub.used_height_mm + 4

        if author:
            c.setFillColor(colors.HexColor(MUTED))
            c.setFont(self._bold(), 11)
            c.drawCentredString(total_w / 2, (total_h / mm) * 0.20 * mm, author)

        bleed = bleed_mm * mm
        c.setStrokeColor(colors.HexColor("#E3DED2"))
        c.setLineWidth(0.8)
        c.rect(bleed + 8 * mm, bleed + 8 * mm, total_w - 2 * bleed - 16 * mm, total_h - 2 * bleed - 16 * mm, fill=0, stroke=1)

        if include_guides:
            self._draw_trim_guides(c, total_w, total_h, bleed_mm)
        if crop_marks:
            self._draw_crop_marks(c, total_w, total_h, bleed_mm)

        c.showPage()
        c.save()
        return str(path)

    def render_wrap_cover_pdf(
        self,
        title: str,
        subtitle: str = "",
        author: str = "",
        back_blurb: str = "",
        page_count: int = 32,
        trim_size: str = "US_6_X_9",
        paper: str = "white",
        output_name: str = "cover_wrap.pdf",
        bleed_mm: float = DEFAULT_BLEED_MM,
        crop_marks: bool = True,
        include_guides: bool = False,
        accent: str = ACCENT,
        language: str = "en",
    ) -> dict:
        """Full paperback wrap: back cover + spine + front cover + barcode clear area."""
        spec = PageLayoutService.build_cover_layout(
            trim_size=trim_size, page_count=page_count, paper=paper, bleed_mm=bleed_mm
        )
        total_w = spec.wrap_width_mm * mm
        total_h = spec.wrap_height_mm * mm

        path = self.output_dir / output_name
        c = canvas.Canvas(str(path), pagesize=(total_w, total_h))
        self._metadata(c, title, author, subtitle, keywords="children's picture book, cover wrap")

        bleed = bleed_mm * mm

        def box(block: Block) -> tuple:
            return (
                (block.x_mm) * mm,
                (block.y_mm) * mm,
                block.width_mm * mm,
                block.height_mm * mm,
            )

        # paper base
        c.setFillColor(colors.HexColor(WASH))
        c.rect(0, 0, total_w, total_h, fill=1, stroke=0)

        bx, by, bw, bh = box(spec.front)
        # front cover artwork panel
        c.setFillColor(colors.HexColor(PAPER))
        c.rect(bx, by, bw, bh, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(accent))
        c.circle(bx + bw * 0.86, by + bh * 0.88, min(bw, bh) * 0.24, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(GOLD))
        c.circle(bx + bw * 0.14, by + bh * 0.12, min(bw, bh) * 0.13, fill=1, stroke=0)
        # quiet band behind the title so artwork never fights the type
        c.setFillColor(colors.HexColor(PAPER))
        c.rect(bx, by + bh * 0.40, bw, bh * 0.26, fill=1, stroke=0)

        # title / subtitle on the front panel
        margin = spec.safe_margin_mm
        front_text_w = spec.front.width_mm - 2 * margin
        title_top = spec.front.y_mm + spec.front.height_mm * 0.62
        result = self.text.draw_block(
            c, title, front_text_w, 46, spec.front.x_mm + margin, title_top, bleed_mm,
            TextStyle(font_size=30 if len(title) < 34 else 25, alignment="center", color=INK,
                      bold=True, hyphenate=False, language=language, leading_ratio=1.15),
        )
        y_after_title = title_top - result.used_height_mm - 6
        if subtitle:
            sub = self.text.draw_block(
                c, subtitle, front_text_w, 26, spec.front.x_mm + margin, y_after_title, bleed_mm,
                TextStyle(font_size=14, alignment="center", color=MUTED, hyphenate=False, language=language),
            )
            y_after_title -= sub.used_height_mm + 4
        if author:
            c.setFillColor(colors.HexColor(MUTED))
            c.setFont(self._bold(), 12)
            c.drawCentredString(bx + bw / 2, (spec.front.y_mm + margin) * mm, author)

        # back cover blurb (justified)
        bx_b, by_b, bw_b, bh_b = box(spec.back)
        c.setFillColor(colors.HexColor(PAPER))
        c.rect(bx_b, by_b, bw_b, bh_b, fill=1, stroke=0)
        if back_blurb:
            self.text.draw_block(
                c,
                back_blurb,
                spec.back.width_mm - 2 * margin,
                spec.back.height_mm - 2 * margin - 40,
                spec.back.x_mm + margin,
                spec.back.y_mm + spec.back.height_mm - margin,
                bleed_mm,
                TextStyle(font_size=11.5, alignment="justify", color=INK, language=language),
            )

        # barcode clear area (printers print the barcode here themselves)
        bcx, bcy, bcw, bch = box(spec.barcode)
        c.setFillColor(colors.white)
        c.rect(bcx, bcy, bcw, bch, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#D9D4C7"))
        c.setLineWidth(0.4)
        c.setDash(2, 2)
        c.rect(bcx, bcy, bcw, bch, fill=0, stroke=1)
        c.setDash()
        c.setFillColor(colors.HexColor("#A9A192"))
        c.setFont(self._regular, 6)
        c.drawCentredString(bcx + bcw / 2, bcy + bch / 2 - 2, "ISBN / barcode area — keep clear (2 × 1.2 in)")

        # spine
        if spec.spine_text_allowed and title:
            sx, sy, sw, sh = box(spec.spine)
            c.saveState()
            c.translate(sx + sw / 2, sy + sh / 2)
            c.rotate(90)
            c.setFillColor(colors.HexColor(INK))
            font_name = self._bold(title)
            size = 9 if spec.spine_mm < 6 else 10
            c.setFont(font_name, size)
            text_w = c.stringWidth(title, font_name, size)
            if text_w < sh - 12:
                c.drawCentredString(0, -size * 0.35, title)
            c.restoreState()

        # fold guides
        if include_guides:
            c.saveState()
            c.setStrokeColor(colors.HexColor("#C9CED8"))
            c.setDash(3, 3)
            c.setLineWidth(0.4)
            for fold_mm in (bleed_mm + spec.front.width_mm - spec.spine_mm,
                            bleed_mm + spec.front.width_mm):
                c.line(fold_mm * mm, 0, fold_mm * mm, total_h)
            c.line((bleed_mm + spec.front.width_mm - spec.spine_mm) * mm, 0,
                   (bleed_mm + spec.front.width_mm - spec.spine_mm) * mm, total_h)
            c.restoreState()

        if crop_marks:
            self._draw_crop_marks(c, total_w, total_h, bleed_mm)

        c.showPage()
        c.save()

        return {
            "path": str(path),
            "spec": spec.to_dict(),
        }

    # ---------------------------------------------------------------- interior
    def render_story_pdf(
        self,
        pages: List[str],
        output_name: str = "storybook.pdf",
        title: str = "",
        trim_size: str = "US_6_X_9",
        bleed_mm: float = DEFAULT_BLEED_MM,
        page_images: Optional[List[Optional[str]]] = None,
        page_types: Optional[List[str]] = None,
        include_guides: bool = False,
        crop_marks: bool = False,
        language: str = "en",
    ) -> str:
        if not pages:
            pages = [""]

        layouts = [
            self._layout(
                trim_size,
                (page_types[i] if page_types and i < len(page_types) else "single"),
                bleed_mm,
            )
            for i in range(len(pages))
        ]

        path = self.output_dir / output_name
        first_w = layouts[0].page_box_mm[0] * mm
        first_h = layouts[0].page_box_mm[1] * mm
        c = canvas.Canvas(str(path), pagesize=(first_w, first_h))
        self._metadata(c, title or "Storybook", subject="Children's picture book interior")

        bleed_pt = bleed_mm * mm
        overflow_report: List[dict] = []

        for index, (text, layout) in enumerate(zip(pages, layouts), start=1):
            page_w = layout.page_box_mm[0] * mm
            page_h = layout.page_box_mm[1] * mm
            if (page_w, page_h) != (first_w, first_h) or index > 1:
                c.setPageSize((page_w, page_h))

            c.setFillColor(colors.HexColor(PAPER))
            c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

            # ---- image block ----
            img = layout.image_block
            img_x = bleed_pt + img.x_mm * mm
            img_y = bleed_pt + img.y_mm * mm
            img_w = img.width_mm * mm
            img_h = img.height_mm * mm

            image_path = page_images[index - 1] if page_images and index - 1 < len(page_images) else None
            if image_path and Path(image_path).exists():
                c.drawImage(
                    image_path, img_x, img_y, width=img_w, height=img_h,
                    preserveAspectRatio=True, anchor="c", mask="auto",
                )
            elif layout.page_type != "full_bleed":
                c.saveState()
                c.setFillColor(colors.HexColor(PLACEHOLDER_FILL))
                c.rect(img_x, img_y, img_w, img_h, fill=1, stroke=0)
                c.setStrokeColor(colors.HexColor(PLACEHOLDER_LINE))
                c.setDash(4, 4)
                c.setLineWidth(0.8)
                c.rect(img_x, img_y, img_w, img_h, fill=0, stroke=1)
                c.setFillColor(colors.HexColor("#A9A192"))
                c.setFont(self._regular, 9)
                c.drawCentredString(img_x + img_w / 2, img_y + img_h / 2, "illustration area — 300 dpi, full bleed")
                c.restoreState()

            # ---- text block (justified, hyphenated, widow-controlled) ----
            txt = layout.text_block
            fit = self.text.draw_block(
                c,
                text,
                txt.width_mm,
                max(10.0, txt.height_mm - 6),
                txt.x_mm,
                txt.y_mm + txt.height_mm - 3,
                bleed_mm,
                TextStyle(font_size=15, alignment="justify", color=INK, language=language, leading_ratio=1.5),
                min_font_size=11,
            )
            if not fit.fitted or fit.overflow_text:
                overflow_report.append({"page": index, "overflow": fit.overflow_text})

            # folio
            c.setFillColor(colors.HexColor("#9AA3B2"))
            c.setFont(self._regular, 8)
            c.drawCentredString(
                bleed_pt + (layout.safe_area.x_mm + layout.safe_area.width_mm / 2) * mm,
                bleed_pt + (layout.safe_area.y_mm / 2) * mm,
                str(index),
            )

            if include_guides:
                self._draw_trim_guides(c, page_w, page_h, bleed_mm)
            if crop_marks:
                self._draw_crop_marks(c, page_w, page_h, bleed_mm)

            if index < len(pages):
                c.showPage()

        c.save()
        self.last_layout_report = {"overflow": overflow_report, "pages": len(pages)}
        return str(path)


    # ------------------------------------------------------------ bilingual book
    def render_bilingual_pdf(
        self,
        pages: List[Dict[str, str]],
        output_name: str = "bilingual_book.pdf",
        title: str = "",
        trim_size: str = "US_6_X_9",
        bleed_mm: float = DEFAULT_BLEED_MM,
        page_types: Optional[List[str]] = None,
        page_images: Optional[List[Optional[str]]] = None,
        language_primary: str = "en",
        language_secondary: str = "de",
        crop_marks: bool = False,
    ) -> str:
        """Two languages on one page (stacked) or one per page (facing).

        ``pages`` items need ``primary`` and ``secondary`` keys. For ``facing`` pages the
        renderer expects ``text`` only — pass the already-interleaved list from
        ``BilingualService.build(mode="facing")``.
        """
        if not pages:
            pages = [{"primary": "", "secondary": ""}]

        layouts = [
            self._layout(trim_size, (page_types[i] if page_types and i < len(page_types) else "single"), bleed_mm)
            for i in range(len(pages))
        ]
        path = self.output_dir / output_name
        c = canvas.Canvas(str(path), pagesize=(layouts[0].page_box_mm[0] * mm, layouts[0].page_box_mm[1] * mm))
        self._metadata(c, title or "Bilingual Storybook", subject="Bilingual children's picture book interior")

        bleed_pt = bleed_mm * mm
        overflow: List[Dict[str, object]] = []

        for index, (page, layout) in enumerate(zip(pages, layouts), start=1):
            page_w = layout.page_box_mm[0] * mm
            page_h = layout.page_box_mm[1] * mm
            if index > 1:
                c.setPageSize((page_w, page_h))

            c.setFillColor(colors.HexColor(PAPER))
            c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

            img = layout.image_block
            img_x = bleed_pt + img.x_mm * mm
            img_y = bleed_pt + img.y_mm * mm
            if page_images and index - 1 < len(page_images) and page_images[index - 1]:
                candidate = page_images[index - 1]
                if Path(candidate).exists():
                    c.drawImage(candidate, img_x, img_y, width=img.width_mm * mm, height=img.height_mm * mm,
                                preserveAspectRatio=True, anchor="c", mask="auto")
            elif layout.page_type != "full_bleed":
                c.saveState()
                c.setFillColor(colors.HexColor(PLACEHOLDER_FILL))
                c.rect(img_x, img_y, img.width_mm * mm, img.height_mm * mm, fill=1, stroke=0)
                c.setStrokeColor(colors.HexColor(PLACEHOLDER_LINE))
                c.setDash(4, 4)
                c.rect(img_x, img_y, img.width_mm * mm, img.height_mm * mm, fill=0, stroke=1)
                c.restoreState()

            txt = layout.text_block
            primary_text = str(page.get("primary", page.get("text", "")) or "")
            secondary_text = str(page.get("secondary", "") or "")

            if secondary_text:
                gap = 5.0
                half = max(12.0, (txt.height_mm - gap) / 2)
                top_fit = self.text.draw_block(
                    c, primary_text, txt.width_mm, half,
                    txt.x_mm, txt.y_mm + txt.height_mm - 2, bleed_mm,
                    TextStyle(font_size=13, alignment="left", color=INK,
                              language=language_primary, leading_ratio=1.45),
                    min_font_size=9,
                )
                rule_y = bleed_pt + (txt.y_mm + half + gap / 2) * mm
                c.saveState()
                c.setStrokeColor(colors.HexColor("#D8D2C4"))
                c.setLineWidth(0.6)
                c.line(bleed_pt + txt.x_mm * mm, rule_y,
                       bleed_pt + (txt.x_mm + txt.width_mm) * mm, rule_y)
                c.restoreState()
                bottom_fit = self.text.draw_block(
                    c, secondary_text, txt.width_mm, half,
                    txt.x_mm, txt.y_mm + half + gap / 2 - 2, bleed_mm,
                    TextStyle(font_size=13, alignment="left", color="#3F3A33",
                              language=language_secondary, leading_ratio=1.45),
                    min_font_size=9,
                )
                if not top_fit.fitted or top_fit.overflow_text:
                    overflow.append({"page": index, "language": language_primary, "overflow": top_fit.overflow_text})
                if not bottom_fit.fitted or bottom_fit.overflow_text:
                    overflow.append({"page": index, "language": language_secondary, "overflow": bottom_fit.overflow_text})
            else:
                single_language = str(page.get("language", language_primary))
                fit = self.text.draw_block(
                    c, primary_text, txt.width_mm, max(10.0, txt.height_mm - 6),
                    txt.x_mm, txt.y_mm + txt.height_mm - 3, bleed_mm,
                    TextStyle(font_size=14, alignment="left", color=INK,
                              language=single_language, leading_ratio=1.5),
                    min_font_size=10,
                )
                if not fit.fitted or fit.overflow_text:
                    overflow.append({"page": index, "overflow": fit.overflow_text})

            c.setFillColor(colors.HexColor("#9AA3B2"))
            c.setFont(self._regular, 8)
            c.drawCentredString(
                bleed_pt + (layout.safe_area.x_mm + layout.safe_area.width_mm / 2) * mm,
                bleed_pt + (layout.safe_area.y_mm / 2) * mm,
                str(index),
            )
            if crop_marks:
                self._draw_crop_marks(c, page_w, page_h, bleed_mm)
            if index < len(pages):
                c.showPage()

        c.save()
        self.last_layout_report = {"overflow": overflow, "pages": len(pages), "bilingual": True}
        return str(path)


    # --------------------------------------------------- picture book (trade)
    def render_picture_book_pdf(
        self,
        pages: List[Dict[str, Any]],
        output_name: str = "picture_book.pdf",
        title: str = "",
        trim_size: str = "US_6_X_9",
        bleed_mm: float = DEFAULT_BLEED_MM,
        page_images: Optional[List[Optional[str]]] = None,
        crop_marks: bool = False,
        include_guides: bool = False,
    ) -> str:
        """Full-bleed trade picture book: art reaches the trim edge on every story page.

        * story pages: the illustration covers the whole page (bleed included); the text
          sits in a soft panel strictly inside the **safe area**, so nothing important is
          ever lost to trimming.
        * spread pages: one wide illustration spans the two facing pages (``spread`` =
          ``left``/``right``); the text goes on the right half only.
        * front/back matter: typographic pages with generous margins (no art).
        """
        if not pages:
            raise ValueError("no pages supplied")

        path = self.output_dir / output_name
        bleed_pt = bleed_mm * mm
        first_layout = self._layout(trim_size, "full_bleed", bleed_mm)
        page_w = first_layout.page_box_mm[0] * mm
        page_h = first_layout.page_box_mm[1] * mm

        c = canvas.Canvas(str(path), pagesize=(page_w, page_h))
        self._metadata(c, title or "Picture book", subject="Children's picture book interior — full bleed")
        overflow: List[Dict[str, Any]] = []

        for index, page in enumerate(pages):
            c.setPageSize((page_w, page_h))
            c.setFillColor(colors.HexColor(PAPER))
            c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

            kind = str(page.get("kind", "story"))
            image_path = page_images[index] if page_images and index < len(page_images) else None
            has_image = bool(image_path and Path(image_path).exists())

            if kind != "story":
                self._draw_matter_page(c, page, page_w, page_h, bleed_pt, title)
            else:
                layout = self._layout(trim_size, "full_bleed", bleed_mm)
                if has_image:
                    spread = str(page.get("spread", "") or "")
                    self._draw_cover_image(
                        c, image_path, page_w, page_h,
                        offset_x=0.0 if spread in ("", "left") else -page_w,
                        wide=bool(spread),
                    )
                else:
                    c.setFillColor(colors.HexColor("#EFE9DC"))
                    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

                # A spread carries the text once, on its left page; the right half is pure art.
                fit = None
                if str(page.get("spread", "") or "") != "right":
                    fit = self._draw_text_panel(c, page, layout, bleed_pt, page_w)
                if fit and (not fit.fitted or fit.overflow_text):
                    overflow.append({"page": index + 1, "overflow": fit.overflow_text})

                c.setFillColor(colors.HexColor("#7C7364"))
                c.setFont(self._regular, 8)
                c.drawCentredString(
                    bleed_pt + (layout.safe_area.x_mm + layout.safe_area.width_mm / 2) * mm,
                    bleed_pt + (layout.safe_area.y_mm / 2) * mm,
                    str(page.get("page", index + 1)),
                )

            if include_guides:
                self._draw_trim_guides(c, page_w, page_h, bleed_mm)
            if crop_marks:
                self._draw_crop_marks(c, page_w, page_h, bleed_mm)
            if index < len(pages) - 1:
                c.showPage()

        c.save()
        self.last_layout_report = {"overflow": overflow, "pages": len(pages), "full_bleed": True}
        return str(path)

    def _draw_cover_image(self, c, image_path: str, page_w: float, page_h: float,
                          offset_x: float = 0.0, wide: bool = False) -> None:
        """Cover-fit the art so it fills the page(s) edge to edge, then clip."""
        from PIL import Image as _Image

        with _Image.open(image_path) as probe:
            image_w, image_h = probe.size
        target_w = page_w * (2 if wide else 1)
        scale = max(target_w / image_w, page_h / image_h)
        draw_w, draw_h = image_w * scale, image_h * scale
        x = offset_x - (draw_w - target_w) / 2
        y = -(draw_h - page_h) / 2

        c.saveState()
        clip = c.beginPath()
        clip.rect(0, 0, page_w, page_h)
        c.clipPath(clip, stroke=0, fill=0)
        c.drawImage(image_path, x, y, width=draw_w, height=draw_h, mask="auto")
        c.restoreState()

    def _draw_text_panel(self, c, page: Dict[str, Any], layout, bleed_pt: float, page_w: float):
        """Text sits in a soft panel inside the safe area — never under the trim."""
        safe = layout.safe_area
        primary = str(page.get("text", "") or "")
        secondary = str(page.get("text_secondary", "") or "")
        language = str(page.get("language", "en") or "en")
        language_secondary = str(page.get("language_secondary", "") or "de")

        panel_h_mm = 34.0 if not secondary else 46.0
        panel_x = bleed_pt + safe.x_mm * mm
        panel_w = safe.width_mm * mm
        panel_h = panel_h_mm * mm
        panel_y = bleed_pt + safe.y_mm * mm

        c.saveState()
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.88))
        c.setStrokeColor(colors.Color(0, 0, 0, alpha=0.06))
        c.roundRect(panel_x, panel_y, panel_w, panel_h, 3 * mm, stroke=1, fill=1)
        c.restoreState()

        pad = 4.0
        width_mm = panel_w / mm - pad * 2
        top_y_mm = safe.y_mm + panel_h_mm - pad

        if secondary:
            half = (panel_h_mm - pad * 2 - 4) / 2
            fit = self.text.draw_block(
                c, primary, width_mm, half, safe.x_mm + pad, top_y_mm, bleed_pt / mm,
                TextStyle(font_size=13, alignment="left", color=INK, language=language, leading_ratio=1.4),
                min_font_size=9,
            )
            rule_y = bleed_pt + (safe.y_mm + pad + half + 2) * mm
            c.saveState()
            c.setStrokeColor(colors.HexColor("#DDD6C7"))
            c.setLineWidth(0.5)
            c.line(panel_x + 2 * mm, rule_y, panel_x + panel_w - 2 * mm, rule_y)
            c.restoreState()
            self.text.draw_block(
                c, secondary, width_mm, half, safe.x_mm + pad, safe.y_mm + pad + half, bleed_pt / mm,
                TextStyle(font_size=13, alignment="left", color="#3F3A33", language=language_secondary,
                          leading_ratio=1.4),
                min_font_size=9,
            )
            return fit

        return self.text.draw_block(
            c, primary, width_mm, panel_h_mm - pad * 2, safe.x_mm + pad, top_y_mm, bleed_pt / mm,
            TextStyle(font_size=15, alignment="left", color=INK, language=language, leading_ratio=1.5),
            min_font_size=10,
        )

    def _draw_matter_page(self, c, page: Dict[str, Any], page_w: float, page_h: float,
                          bleed_pt: float, book_title: str) -> None:
        """Half-title, title page, copyright, dedication, the end, colophon…"""
        kind = str(page.get("kind", ""))
        text = str(page.get("text", "") or "")
        language = str(page.get("language", "en") or "en")
        centre_x = page_w / 2

        if kind == "half_title":
            c.setFillColor(colors.HexColor("#6C655A"))
            c.setFont(self._regular, 10)
            c.drawCentredString(centre_x, page_h - 30 * mm, (book_title or "").upper())
        elif kind == "title_page":
            lines = [line for line in text.split("\n") if line.strip()]
            c.setFillColor(colors.HexColor(INK))
            c.setFont(self._bold(text), 26)
            c.drawCentredString(centre_x, page_h * 0.62, lines[0] if lines else book_title)
            if len(lines) > 1:
                c.setFont(self._regular, 13)
                c.setFillColor(colors.HexColor("#5C5648"))
                c.drawCentredString(centre_x, page_h * 0.56, lines[1])
            c.setFont(self._regular, 11)
            c.setFillColor(colors.HexColor("#6C655A"))
            c.drawCentredString(centre_x, page_h * 0.46, "TaleForge Studio")
        elif kind == "the_end":
            c.setFillColor(colors.HexColor(INK))
            c.setFont(self._bold(text), 22)
            c.drawCentredString(centre_x, page_h * 0.52, text or "The End")
        else:
            box_w = page_w - 36 * mm
            self.text.draw_block(
                c, text, box_w / mm, (page_h - 90 * mm) / mm,
                18.0, (page_h - 45 * mm) / mm, bleed_pt / mm,
                TextStyle(font_size=10.5, alignment="left", color="#4A4438", language=language,
                          leading_ratio=1.6),
                min_font_size=9,
            )

    # -------------------------------------------------------- coloring book
    def render_coloring_book_pdf(
        self,
        pages: List[Dict[str, Any]],
        output_name: str = "coloring_book.pdf",
        title: str = "",
        trim_size: str = "US_8_5_X_8_5",
        bleed_mm: float = DEFAULT_BLEED_MM,
    ) -> str:
        """Title page + one line-art page per illustration, full page, KDP-friendly."""
        layout = self._layout(trim_size, "full_bleed", bleed_mm)
        page_w = layout.page_box_mm[0] * mm
        page_h = layout.page_box_mm[1] * mm
        path = self.output_dir / output_name
        c = canvas.Canvas(str(path), pagesize=(page_w, page_h))
        self._metadata(c, title or "Coloring book", subject="Children's coloring book interior")

        for index, page in enumerate(pages):
            c.setPageSize((page_w, page_h))
            c.setFillColor(colors.white)
            c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
            image_path = page.get("image")
            if page.get("kind") == "title":
                c.setFillColor(colors.HexColor(INK))
                c.setFont(self._bold(title), 24)
                c.drawCentredString(page_w / 2, page_h * 0.58, title or "Coloring Book")
                c.setFont(self._regular, 12)
                c.setFillColor(colors.HexColor("#6C655A"))
                c.drawCentredString(page_w / 2, page_h * 0.52, page.get("text", ""))
            elif image_path and Path(image_path).exists():
                self._draw_cover_image(c, image_path, page_w, page_h)
                c.setFillColor(colors.HexColor("#8A8375"))
                c.setFont(self._regular, 9)
                c.drawCentredString(page_w / 2, 8 * mm, str(page.get("page", index + 1)))
            if index < len(pages) - 1:
                c.showPage()
        c.save()
        self.last_layout_report = {"pages": len(pages), "coloring": True}
        return str(path)

    # ------------------------------------------------------------ coloring book
    def render_coloring_pdf(
        self,
        image_paths: Iterable[str],
        output_name: str = "coloring_book.pdf",
        trim_size: str = "US_8_5_X_8_5",
        bleed_mm: float = 0.0,
        crop_marks: bool = False,
    ) -> str:
        layout = self._layout(trim_size, "single", bleed_mm)
        total_w = layout.page_box_mm[0] * mm
        total_h = layout.page_box_mm[1] * mm

        path = self.output_dir / output_name
        c = canvas.Canvas(str(path), pagesize=(total_w, total_h))
        self._metadata(c, "Coloring Book", subject="Children's coloring book interior")

        margin = 8 * mm
        box_w = total_w - 2 * margin
        box_h = total_h - 2 * margin

        items = [p for p in image_paths if Path(p).exists()]
        if not items:
            c.setFont(self._regular, 11)
            c.drawString(margin, total_h / 2, "No coloring pages were supplied.")

        for idx, image_path in enumerate(items):
            c.drawImage(
                image_path, margin, margin, width=box_w, height=box_h,
                preserveAspectRatio=True, anchor="c", mask="auto",
            )
            c.setFont(self._regular, 8)
            c.drawCentredString(total_w / 2, margin / 2, str(idx + 1))
            if crop_marks:
                self._draw_crop_marks(c, total_w, total_h, max(bleed_mm, 0))
            if idx < len(items) - 1:
                c.showPage()

        c.save()
        return str(path)

    # ------------------------------------------------------------------- utils
    @staticmethod
    def wrap_text(text: str, max_chars: int = 50) -> List[str]:
        words = text.split()
        lines: List[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _draw_wrapped_center(
        self, c, text: str, cx: float, top_y: float, max_width: float, font_size: int, font_name: str
    ) -> None:
        approximate_chars = max(12, int(max_width / (font_size * 0.52)))
        y = top_y
        for line in self.wrap_text(text, approximate_chars):
            c.drawCentredString(cx, y, line)
            y -= font_size * 1.25
