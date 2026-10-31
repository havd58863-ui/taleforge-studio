"""Print page geometry: trim, bleed, safe area, text and image blocks.

This is the single source of truth for page maths. ``render_service`` and
``image_fit_service`` read their numbers from here instead of hard-coding them.

All public values are millimetres unless the name ends in ``_px``.
Coordinates are measured from the bottom-left corner of the page (PDF convention)
with the bleed included in the page box.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

MM_PER_INCH = 25.4

# Canonical KDP-style trim sizes (width_mm, height_mm)
TRIM_SIZES_MM: Dict[str, Tuple[float, float]] = {
    "US_6_X_9": (152.4, 228.6),
    "US_7_X_10": (177.8, 254.0),
    "US_8_X_10": (203.2, 254.0),
    "US_8_5_X_8_5": (215.9, 215.9),
    "US_8_5_X_11": (215.9, 279.4),
    "SQUARE_8": (203.2, 203.2),
    "A5": (148.0, 210.0),
    "A4": (210.0, 297.0),
}

DEFAULT_TRIM = "US_6_X_9"
DEFAULT_BLEED_MM = 3.0        # 0.125 in
DEFAULT_SAFE_MARGIN_MM = 12.0  # 0.5 in
DEFAULT_GUTTER_MM = 6.0        # inner margin allowance for spreads
DEFAULT_DPI = 300

PAGE_TYPES = ("single", "spread", "full_bleed")


@dataclass
class Block:
    """A rectangular area in millimetres, measured from the trim origin."""

    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float

    def to_pixels(self, dpi: int = DEFAULT_DPI, bleed_mm: float = DEFAULT_BLEED_MM) -> Dict[str, int]:
        k = dpi / MM_PER_INCH
        bleed_px = int(round(bleed_mm * k))
        return {
            "x_px": int(round(self.x_mm * k)) + bleed_px,
            "y_px": int(round(self.y_mm * k)) + bleed_px,
            "width_px": int(round(self.width_mm * k)),
            "height_px": int(round(self.height_mm * k)),
        }

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class PageLayoutSpec:
    trim_size: str
    page_type: str
    page_width_mm: float
    page_height_mm: float
    bleed_mm: float
    safe_margin_mm: float
    gutter_mm: float
    dpi: int
    text_block: Block
    image_block: Block
    safe_area: Block
    warnings: List[str] = field(default_factory=list)

    # ---------- derived values ----------
    @property
    def page_box_mm(self) -> Tuple[float, float]:
        """Full PDF page box including bleed on all four sides."""
        return (self.page_width_mm + 2 * self.bleed_mm, self.page_height_mm + 2 * self.bleed_mm)

    @property
    def page_px(self) -> Tuple[int, int]:
        k = self.dpi / MM_PER_INCH
        return (int(round(self.page_box_mm[0] * k)), int(round(self.page_box_mm[1] * k)))

    @property
    def bleed_px(self) -> int:
        return int(round(self.bleed_mm * self.dpi / MM_PER_INCH))

    @property
    def is_valid(self) -> bool:
        return not self.warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trim_size": self.trim_size,
            "page_type": self.page_type,
            "page_width_mm": self.page_width_mm,
            "page_height_mm": self.page_height_mm,
            "page_box_mm": {"width": round(self.page_box_mm[0], 2), "height": round(self.page_box_mm[1], 2)},
            "page_px": {"width": self.page_px[0], "height": self.page_px[1]},
            "bleed_mm": self.bleed_mm,
            "bleed_px": self.bleed_px,
            "safe_margin_mm": self.safe_margin_mm,
            "gutter_mm": self.gutter_mm,
            "dpi": self.dpi,
            "safe_area": self.safe_area.to_dict(),
            "text_block": {**self.text_block.to_dict(), **self.text_block.to_pixels(self.dpi, self.bleed_mm)},
            "image_block": {**self.image_block.to_dict(), **self.image_block.to_pixels(self.dpi, self.bleed_mm)},
            "warnings": self.warnings,
            "is_valid": self.is_valid,
        }


class PageLayoutService:
    """Builds print layouts for the three page types used by the story engine."""

    @staticmethod
    def available_trim_sizes() -> Dict[str, Tuple[float, float]]:
        return dict(TRIM_SIZES_MM)

    @staticmethod
    def _resolve_trim(trim_size: str) -> Tuple[str, float, float, List[str]]:
        key = (trim_size or DEFAULT_TRIM).upper().replace(" ", "")
        warnings: List[str] = []
        if key not in TRIM_SIZES_MM:
            warnings.append(
                f"unknown trim size '{trim_size}', falling back to {DEFAULT_TRIM} "
                f"(valid: {', '.join(TRIM_SIZES_MM)})"
            )
            key = DEFAULT_TRIM
        width, height = TRIM_SIZES_MM[key]
        return key, width, height, warnings

    @classmethod
    def build_layout(
        cls,
        trim_size: str = DEFAULT_TRIM,
        page_type: str = "single",
        bleed_mm: float = DEFAULT_BLEED_MM,
        safe_margin_mm: float = DEFAULT_SAFE_MARGIN_MM,
        gutter_mm: float = DEFAULT_GUTTER_MM,
        dpi: int = DEFAULT_DPI,
        image_ratio: float = 0.60,
    ) -> PageLayoutSpec:
        """Return a validated layout for one page.

        page_type:
          single     — illustration above, text block below
          spread     — doubled width (two facing pages), image full width, text band at the bottom
          full_bleed — illustration covers the whole page, text sits in the safe area
        """
        key, trim_w, trim_h, warnings = cls._resolve_trim(trim_size)

        page_type = (page_type or "single").lower()
        if page_type not in PAGE_TYPES:
            warnings.append(f"unknown page_type '{page_type}', falling back to 'single'")
            page_type = "single"

        if page_type == "spread":
            page_w = 2 * trim_w + gutter_mm
        else:
            page_w = trim_w
        page_h = trim_h

        # --- safe area (inside the trim) ---
        inner_margin = safe_margin_mm
        if page_type == "spread":
            inner_margin = safe_margin_mm + gutter_mm / 2
        safe_area = Block(
            x_mm=inner_margin,
            y_mm=safe_margin_mm,
            width_mm=page_w - 2 * inner_margin,
            height_mm=page_h - 2 * safe_margin_mm,
        )

        # --- image / text split ---
        gap_mm = 6.0
        if safe_area.width_mm <= 0 or safe_area.height_mm <= 0:
            warnings.append("safe area is empty — safe margin is larger than the page")
            image_block = Block(0, 0, 0, 0)
            text_block = Block(0, 0, 0, 0)
        elif page_type == "full_bleed":
            # artwork covers the full page including bleed
            image_block = Block(-bleed_mm, -bleed_mm, page_w + 2 * bleed_mm, page_h + 2 * bleed_mm)
            text_height = round(safe_area.height_mm * 0.30, 2)
            text_block = Block(
                x_mm=safe_area.x_mm,
                y_mm=safe_area.y_mm,
                width_mm=safe_area.width_mm,
                height_mm=text_height,
            )
        elif page_type == "spread":
            image_height = round(safe_area.height_mm * 0.70, 2)
            image_block = Block(
                x_mm=safe_area.x_mm,
                y_mm=safe_area.y_mm + (safe_area.height_mm - image_height),
                width_mm=safe_area.width_mm,
                height_mm=image_height,
            )
            text_block = Block(
                x_mm=safe_area.x_mm,
                y_mm=safe_area.y_mm,
                width_mm=safe_area.width_mm,
                height_mm=round(safe_area.height_mm - image_height - gap_mm, 2),
            )
        else:  # single
            image_height = round(safe_area.height_mm * image_ratio, 2)
            image_block = Block(
                x_mm=safe_area.x_mm,
                y_mm=safe_area.y_mm + (safe_area.height_mm - image_height),
                width_mm=safe_area.width_mm,
                height_mm=image_height,
            )
            text_block = Block(
                x_mm=safe_area.x_mm,
                y_mm=safe_area.y_mm,
                width_mm=safe_area.width_mm,
                height_mm=round(safe_area.height_mm - image_height - gap_mm, 2),
            )

        spec = PageLayoutSpec(
            trim_size=key,
            page_type=page_type,
            page_width_mm=page_w,
            page_height_mm=page_h,
            bleed_mm=bleed_mm,
            safe_margin_mm=safe_margin_mm,
            gutter_mm=gutter_mm,
            dpi=dpi,
            text_block=text_block,
            image_block=image_block,
            safe_area=safe_area,
            warnings=warnings,
        )
        spec.warnings.extend(cls.validate(spec))
        return spec

    @staticmethod
    def validate(spec: PageLayoutSpec) -> List[str]:
        """Structural checks that would fail at the printer."""
        problems: List[str] = []

        if spec.bleed_mm < 3.0:
            problems.append("bleed below 3 mm risks white edges after trimming")
        if spec.dpi < 300:
            problems.append("interior artwork below 300 dpi is not print-grade")
        if spec.text_block.height_mm < 20:
            problems.append("text block shorter than 20 mm cannot hold a paragraph")
        if spec.text_block.width_mm < 60:
            problems.append("text block narrower than 60 mm causes excessive hyphenation")

        # text must live inside the safe area
        if spec.text_block.y_mm < spec.safe_area.y_mm - 0.01:
            problems.append("text block starts below the safe area")
        if spec.text_block.y_mm + spec.text_block.height_mm > spec.safe_area.y_mm + spec.safe_area.height_mm + 0.01:
            problems.append("text block overflows the safe area")
        if spec.text_block.x_mm + spec.text_block.width_mm > spec.safe_area.x_mm + spec.safe_area.width_mm + 0.01:
            problems.append("text block is wider than the safe area")

        # a full-bleed image must actually reach beyond the bleed line
        if spec.page_type == "full_bleed" and spec.image_block.x_mm > -spec.bleed_mm + 0.01:
            problems.append("full-bleed artwork does not cover the bleed area")

        return problems

    @classmethod
    def build_story_page_layout(cls, width_mm: float = 152.4, height_mm: float = 228.6, **kwargs) -> PageLayoutSpec:
        """Backward-compatible helper used by early integrations.

        Accepts explicit millimetre dimensions instead of a named trim size.
        """
        for name, (w, h) in TRIM_SIZES_MM.items():
            if abs(w - width_mm) < 0.1 and abs(h - height_mm) < 0.1:
                return cls.build_layout(trim_size=name, **kwargs)
        spec = cls.build_layout(**kwargs)
        spec.trim_size = f"custom_{int(round(width_mm))}x{int(round(height_mm))}"
        spec.page_width_mm = width_mm
        spec.page_height_mm = height_mm
        return spec

    @classmethod
    def build_book_plan(
        cls,
        trim_size: str = DEFAULT_TRIM,
        page_types: Optional[List[str]] = None,
        bleed_mm: float = DEFAULT_BLEED_MM,
        dpi: int = DEFAULT_DPI,
    ) -> Dict[str, Any]:
        """Layout for every page of a book, plus a summary used by the dashboard."""
        page_types = page_types or ["single"]
        pages = [
            cls.build_layout(trim_size=trim_size, page_type=page_type, bleed_mm=bleed_mm, dpi=dpi)
            for page_type in page_types
        ]
        return {
            "trim_size": pages[0].trim_size,
            "page_count": len(pages),
            "pages": [p.to_dict() for p in pages],
            "valid": all(p.is_valid for p in pages),
            "warnings": sorted({w for p in pages for w in p.warnings}),
        }


# ---------------------------------------------------------------------------
# Covers (paperback wrap: back cover + spine + front cover)
# ---------------------------------------------------------------------------

# Paper thickness per sheet (mm) — KDP print-on-demand stock.
PAPER_THICKNESS_MM: Dict[str, float] = {
    "white": 0.0572,        # 0.002252 in/page
    "cream": 0.0635,        # 0.0025 in/page
    "premium_color": 0.0572,
    "standard_color": 0.0572,
}

KDP_MIN_PAGES = 24
KDP_MAX_PAGES = 828
KDP_SPINE_TEXT_MIN_PAGES = 100
BARCODE_W_MM = 50.8   # 2 in
BARCODE_H_MM = 30.48  # 1.2 in
BARCODE_MARGIN_MM = 6.35  # 0.25 in


@dataclass
class CoverLayoutSpec:
    trim_size: str
    page_count: int
    paper: str
    spine_mm: float
    bleed_mm: float
    dpi: int
    wrap_width_mm: float
    wrap_height_mm: float
    front: Block
    back: Block
    spine: Block
    barcode: Block
    safe_margin_mm: float
    warnings: List[str] = field(default_factory=list)

    @property
    def page_px(self) -> Tuple[int, int]:
        k = self.dpi / MM_PER_INCH
        return (int(round(self.wrap_width_mm * k)), int(round(self.wrap_height_mm * k)))

    @property
    def spine_text_allowed(self) -> bool:
        return self.page_count >= KDP_SPINE_TEXT_MIN_PAGES and self.spine_mm >= 3.2

    @property
    def is_valid(self) -> bool:
        return not [w for w in self.warnings if w.startswith("ERROR")]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trim_size": self.trim_size,
            "page_count": self.page_count,
            "paper": self.paper,
            "spine_mm": round(self.spine_mm, 3),
            "bleed_mm": self.bleed_mm,
            "dpi": self.dpi,
            "wrap_width_mm": round(self.wrap_width_mm, 2),
            "wrap_height_mm": round(self.wrap_height_mm, 2),
            "page_px": {"width": self.page_px[0], "height": self.page_px[1]},
            "safe_margin_mm": self.safe_margin_mm,
            "spine_text_allowed": self.spine_text_allowed,
            "front": self.front.to_dict(),
            "back": self.back.to_dict(),
            "spine": self.spine.to_dict(),
            "barcode": self.barcode.to_dict(),
            "warnings": self.warnings,
            "is_valid": self.is_valid,
        }


def _build_cover_layout(
    trim_size: str = DEFAULT_TRIM,
    page_count: int = 32,
    paper: str = "white",
    bleed_mm: float = DEFAULT_BLEED_MM,
    safe_margin_mm: float = DEFAULT_SAFE_MARGIN_MM,
    dpi: int = DEFAULT_DPI,
) -> CoverLayoutSpec:
    """Full paperback wrap: back cover | spine | front cover, bleed included."""
    key, trim_w, trim_h, warnings = PageLayoutService._resolve_trim(trim_size)
    paper = (paper or "white").lower()
    if paper not in PAPER_THICKNESS_MM:
        warnings.append(f"unknown paper '{paper}', assuming white")
        paper = "white"

    page_count = int(page_count or 0)
    if page_count < KDP_MIN_PAGES:
        warnings.append(f"ERROR: page count {page_count} is below the KDP minimum of {KDP_MIN_PAGES}")
    if page_count > KDP_MAX_PAGES:
        warnings.append(f"ERROR: page count {page_count} exceeds the KDP maximum of {KDP_MAX_PAGES}")

    spine_mm = page_count * PAPER_THICKNESS_MM[paper]
    if spine_mm < 3.2:
        warnings.append(
            f"spine is {spine_mm:.2f} mm — most printers require >= 3.2 mm (about 56 pages on white paper)"
        )
    if page_count < KDP_SPINE_TEXT_MIN_PAGES:
        warnings.append(
            f"spine text is not allowed below {KDP_SPINE_TEXT_MIN_PAGES} pages — keep the spine blank"
        )

    wrap_w = 2 * (bleed_mm + trim_w) + spine_mm
    wrap_h = trim_h + 2 * bleed_mm

    back = Block(x_mm=bleed_mm, y_mm=bleed_mm, width_mm=trim_w, height_mm=trim_h)
    spine = Block(x_mm=bleed_mm + trim_w, y_mm=bleed_mm, width_mm=spine_mm, height_mm=trim_h)
    front = Block(x_mm=bleed_mm + trim_w + spine_mm, y_mm=bleed_mm, width_mm=trim_w, height_mm=trim_h)
    barcode = Block(
        x_mm=back.x_mm + trim_w - BARCODE_MARGIN_MM - BARCODE_W_MM,
        y_mm=back.y_mm + BARCODE_MARGIN_MM,
        width_mm=BARCODE_W_MM,
        height_mm=BARCODE_H_MM,
    )

    if safe_margin_mm * 2 >= trim_w:
        warnings.append("ERROR: safe margin does not fit inside the trim width")

    return CoverLayoutSpec(
        trim_size=key,
        page_count=page_count,
        paper=paper,
        spine_mm=spine_mm,
        bleed_mm=bleed_mm,
        dpi=dpi,
        wrap_width_mm=wrap_w,
        wrap_height_mm=wrap_h,
        front=front,
        back=back,
        spine=spine,
        barcode=barcode,
        safe_margin_mm=safe_margin_mm,
        warnings=warnings,
    )


PageLayoutService.build_cover_layout = staticmethod(_build_cover_layout)  # type: ignore[attr-defined]
PageLayoutService.PAPER_THICKNESS_MM = PAPER_THICKNESS_MM  # type: ignore[attr-defined]
