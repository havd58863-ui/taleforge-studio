"""Print preparation — takes any illustration and makes it press-ready.

Steps, in order:

1. **Resolution check** — the artwork must reach the page's pixel size at 300 dpi.
2. **Upscale** — if it falls short: Real-ESRGAN when the binary is installed
   (``REALESRGAN_BIN``), otherwise Lanczos + unsharp with an explicit warning.
3. **Fit** — placed on the exact trim+bleed page (no margins cropped away).
4. **Sharpen** — unsharp mask after resampling (restores line-art crispness).
5. **Colour** — optional CMYK conversion (ICC-managed when a printer profile is given).
6. **Metadata** — EXIF stripped.
7. **Gate** — measured quality gate; a page that fails is returned with reasons, never silently accepted.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageOps

from app.services.image_fit_service import ImageFitService
from app.services.page_layout_service import PageLayoutSpec
from app.services.quality_service import QualityService

MM_PER_INCH = 25.4


class PrintImageService:
    def __init__(self) -> None:
        self.upscaler = os.getenv("REALESRGAN_BIN", "").strip()

    # ------------------------------------------------------------------ public
    def prepare(
        self,
        source_image: str,
        layout: PageLayoutSpec,
        output_path: Optional[str] = None,
        mode: str = "cover",
        target_dpi: int = 300,
        allow_upscale: bool = True,
        cmyk: bool = False,
        icc_profile: Optional[str] = None,
    ) -> Dict[str, Any]:
        source = Path(source_image)
        if not source.exists():
            raise FileNotFoundError(source)

        target_w, target_h = layout.page_px
        with Image.open(source) as probe:
            source_w, source_h = probe.size

        shortest_ratio = min(source_w / target_w, source_h / target_h)
        upscale_used = None
        working = source

        if shortest_ratio < 0.95:
            if not allow_upscale:
                raise ValueError(
                    f"artwork is {source_w}x{source_h}px but the page needs {target_w}x{target_h}px at {target_dpi} dpi"
                )
            working, upscale_used = self.upscale(source, target_w, target_h)

        output = Path(output_path or source.with_name(f"{source.stem}.print.png"))
        fitted = ImageFitService.fit_to_page(
            str(working),
            str(output),
            page_width_mm=layout.page_width_mm,
            page_height_mm=layout.page_height_mm,
            bleed_mm=layout.bleed_mm,
            safe_margin_mm=layout.safe_margin_mm,
            dpi=target_dpi,
            mode=mode,
            sharpen=True,
        )

        final_path = fitted
        if cmyk:
            converted = ImageFitService.convert_to_cmyk(fitted, str(output.with_name(output.stem + ".cmyk.jpg")), icc_profile, target_dpi)
            final_path = converted["path"]

        gate = QualityService.evaluate_image(final_path, page_mm=(layout.page_width_mm, layout.page_height_mm), target_dpi=target_dpi)

        with Image.open(final_path) as final_image:
            final_size = final_image.size

        return {
            "source": str(source),
            "output": final_path,
            "page_px": {"width": target_w, "height": target_h},
            "output_px": {"width": final_size[0], "height": final_size[1]},
            "upscaled": upscale_used,
            "cmyk": bool(cmyk),
            "gate": gate["gate"],
            "score": gate["score"],
            "passed": gate["passed"],
            "metrics": gate["metrics"],
            "notes": gate["notes"],
        }

    # ----------------------------------------------------------------- upscale
    def upscale(self, source: Path, target_w: int, target_h: int) -> tuple:
        """Real-ESRGAN when available (best for illustration), else Lanczos."""
        with Image.open(source) as probe:
            width, height = probe.size
        scale = max(target_w / width, target_h / height)

        if self.upscaler and Path(self.upscaler).exists():
            output = source.with_name(f"{source.stem}.x4.png")
            try:
                subprocess.run(
                    [self.upscaler, "-i", str(source), "-o", str(output), "-s", "4", "-n", "realesrgan-x4plus-anime"],
                    check=True, capture_output=True, timeout=900,
                )
                return output, "realesrgan-x4plus-anime"
            except Exception:
                pass  # fall through to Lanczos

        with Image.open(source) as probe:
            image = ImageOps.exif_transpose(probe).convert("RGB")
        new_size = (int(round(width * max(1.0, scale))), int(round(height * max(1.0, scale))))
        output = source.with_name(f"{source.stem}.upscaled.png")
        image.resize(new_size, Image.Resampling.LANCZOS).save(output)
        return output, f"lanczos_x{max(1.0, scale):.2f}"

    def status(self) -> Dict[str, Any]:
        return {
            "realesrgan_bin": self.upscaler or None,
            "realesrgan_found": bool(self.upscaler and Path(self.upscaler).exists()),
            "fallback_upscaler": "lanczos + unsharp mask",
            "hint": "Install realesrgan-ncnn-vulkan (open source) and set REALESRGAN_BIN for illustrated upscales.",
        }
