"""Coloring-book tooling: professional line art + real vectorisation.

Two independent tools, both print-oriented:

* **Line art** — turns any illustration into crisp black outlines on white, thickened for
  crayons (a 1-pixel hairline is useless for a 4-year-old). Deterministic, no model needed.
* **Vectorisation** — converts the raster line art into SVG with **VTracer** (the same
  engine as the popular VTracer tool, MIT licence). If it is not installed the service says
  so and keeps the 300-dpi raster, which still prints correctly.

    pip install vtracer          # optional, enables SVG output
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageFilter, ImageOps

DEFAULT_DPI = 300


@dataclass
class LineArtResult:
    path: str
    width_px: int
    height_px: int
    method: str
    line_px: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path, "width_px": self.width_px, "height_px": self.height_px,
            "method": self.method, "line_px": self.line_px,
        }


class LineArtService:
    def __init__(self, dpi: int = DEFAULT_DPI) -> None:
        self.dpi = dpi

    # ------------------------------------------------------------------ line art
    def to_line_art(
        self,
        source: str,
        output_path: Optional[str] = None,
        thickness: int = 3,
        detail: float = 0.55,
        min_size_px: Optional[int] = None,
        mode: str = "posterize",
    ) -> LineArtResult:
        """Contour extraction tuned for coloring books (white paper, solid black lines)."""
        image = Image.open(source).convert("RGB")
        if min_size_px and image.width < min_size_px:
            ratio = min_size_px / image.width
            image = image.resize((int(image.width * ratio), int(image.height * ratio)), Image.LANCZOS)

        grey = ImageOps.grayscale(image)
        detail = max(0.0, min(1.0, detail))

        import numpy as np

        smooth = grey.filter(ImageFilter.GaussianBlur(radius=1.6))
        if mode == "posterize":
            # Flat-region method: collapse the painting into few tones, outline the borders.
            posterized = ImageOps.posterize(
                grey.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(2.0)),
                max(2, 3 + int(detail * 2)),
            )
            arr = np.asarray(posterized, dtype=np.float32)
            gx = np.abs(np.diff(arr, axis=1, append=arr[:, -1:]))
            gy = np.abs(np.diff(arr, axis=0, append=arr[-1:, :]))
            strength = gx + gy
            method = "posterize-boundaries"
        else:
            # Soft method (default): difference of Gaussians = stable, illustrator-like
            # contours that survive watercolour washes and gradients.
            fine = np.asarray(smooth.filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32)
            broad = np.asarray(smooth.filter(ImageFilter.GaussianBlur(6.0)), dtype=np.float32)
            strength = np.abs(fine - broad)
            method = "difference-of-gaussians"

        keep_percentile = 99.5 - 8.0 * detail        # detail 0.55 → ~95th percentile
        threshold = max(0.8, float(np.percentile(strength, keep_percentile)))
        mask = strength > threshold

        # Drop single-pixel noise: keep only pixels with at least two neighbours.
        padded = np.pad(mask.astype(np.uint8), 1)
        neighbours = np.zeros(mask.shape, dtype=np.uint8)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                if dy == 1 and dx == 1:
                    continue
                neighbours += padded[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
        mask = mask & (neighbours >= 2)

        dilate = max(3, int(thickness) | 1) + 2
        line_mask = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
        line_mask = line_mask.filter(ImageFilter.MaxFilter(dilate))
        lines = ImageOps.invert(line_mask)
        result = lines.point(lambda value: 0 if value < 128 else 255, mode="L").convert("RGB")

        target = Path(output_path or Path(source).with_name(f"{Path(source).stem}_lineart.png"))
        target.parent.mkdir(parents=True, exist_ok=True)
        result.save(target, dpi=(self.dpi, self.dpi))
        return LineArtResult(str(target), result.width, result.height, method, thickness)

    # ------------------------------------------------------------- vectorisation
    def vectorize(self, source: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Raster → SVG with VTracer when available; otherwise an honest raster fallback."""
        source_path = Path(source)
        target = Path(output_path or source_path.with_suffix(".svg"))
        try:
            import vtracer  # type: ignore
        except Exception:
            return {
                "path": str(source_path), "vectorized": False, "format": "png",
                "note": "vtracer is not installed (pip install vtracer) — 300 dpi raster kept",
            }

        target.parent.mkdir(parents=True, exist_ok=True)
        vtracer.convert_image_to_svg_py(
            str(source_path),
            str(target),
            colormode="binary",
            hierarchical="stacked",
            mode="spline",
            filter_speckle=6,
            corner_threshold=60,
            length_threshold=3.0,
            max_iterations=10,
            splice_threshold=45,
            path_precision=3,
        )
        return {
            "path": str(target), "vectorized": True, "format": "svg",
            "engine": "vtracer", "bytes": target.stat().st_size,
        }

    # ------------------------------------------------------------- print check
    def prepare_for_print(self, source: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """KDP-friendly colouring page: pure white paper, pure black lines, 300 dpi, no metadata."""
        image = Image.open(source).convert("L")
        cleaned = image.point(lambda value: 0 if value < 128 else 255, mode="L").convert("RGB")
        target = Path(output_path or Path(source).with_name(f"{Path(source).stem}_print.png"))
        target.parent.mkdir(parents=True, exist_ok=True)
        cleaned.save(target, dpi=(self.dpi, self.dpi), optimize=True)

        import numpy as np

        grey = np.asarray(cleaned.convert("L"), dtype=np.uint8)
        black = int((grey < 16).sum())
        total = cleaned.width * cleaned.height
        return {
            "path": str(target),
            "width_px": cleaned.width,
            "height_px": cleaned.height,
            "dpi": self.dpi,
            "ink_coverage_pct": round(100 * black / max(1, total), 2),
            "note": "pure black on pure white keeps the interior at the lowest KDP printing cost tier",
        }
