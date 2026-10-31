"""Image fitting with print-safe trim, bleed and safe-area awareness."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageCms, ImageFilter, ImageOps

MM_PER_INCH = 25.4


class ImageFitService:
    @staticmethod
    def _target_pixels(page_w_mm: float, page_h_mm: float, bleed_mm: float, dpi: int) -> Tuple[int, int, int, int]:
        page_w_px = int(round((page_w_mm / MM_PER_INCH) * dpi))
        page_h_px = int(round((page_h_mm / MM_PER_INCH) * dpi))
        bleed_px = int(round((bleed_mm / MM_PER_INCH) * dpi))
        return page_w_px, page_h_px, bleed_px, int(round(((page_w_mm + 2 * bleed_mm) / MM_PER_INCH) * dpi))

    @staticmethod
    def fit_to_page(
        source_image_path: str,
        output_image_path: str,
        page_width_mm: float = 152.4,
        page_height_mm: float = 228.6,
        bleed_mm: float = 3.0,
        safe_margin_mm: float = 12.0,
        dpi: int = 300,
        mode: str = "cover",
        background_color: str = "#FFFFFF",
        max_dpi_bytes: Optional[int] = None,
        sharpen: bool = True,
    ) -> str:
        """Fit an illustration to a full print page (trim + bleed).

        mode="cover"   : fill the whole page, cropping overflow (bleed-safe).
        mode="contain" : letterbox inside the safe area (keeps whole artwork).

        The output keeps the FULL page including bleed — never crop the safe area
        away, otherwise the printed file loses its margins.
        """
        image = Image.open(source_image_path)
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")

        page_w_px = int(round((page_width_mm / MM_PER_INCH) * dpi))
        page_h_px = int(round((page_height_mm / MM_PER_INCH) * dpi))
        bleed_px = int(round((bleed_mm / MM_PER_INCH) * dpi))
        safe_px = int(round((safe_margin_mm / MM_PER_INCH) * dpi))

        target_w = page_w_px + 2 * bleed_px
        target_h = page_h_px + 2 * bleed_px

        bg_rgb = Image.new("RGB", (1, 1), background_color).getpixel((0, 0))
        canvas = Image.new("RGB", (target_w, target_h), bg_rgb)

        src_w, src_h = image.size
        src_ratio = src_w / src_h
        target_ratio = target_w / target_h

        if mode == "cover":
            scale = max(target_w / src_w, target_h / src_h)
            new_w, new_h = max(1, int(round(src_w * scale))), max(1, int(round(src_h * scale)))
        else:
            avail_w = max(1, target_w - 2 * (bleed_px + safe_px))
            avail_h = max(1, target_h - 2 * (bleed_px + safe_px))
            scale = min(avail_w / src_w, avail_h / src_h)
            new_w, new_h = max(1, int(round(src_w * scale))), max(1, int(round(src_h * scale)))

        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        if sharpen:
            # Downscaling softens line art; a light unsharp mask restores print crispness.
            resized = resized.convert("RGB").filter(
                ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2)
            )
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2
        canvas.paste(resized.convert("RGB"), (x, y))

        output = Path(output_image_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        save_kwargs = {"dpi": (dpi, dpi)}
        if output.suffix.lower() in (".jpg", ".jpeg"):
            canvas.save(output, quality=95, subsampling=0, **save_kwargs)
        else:
            canvas.save(output, **save_kwargs)
        return str(output)

    @classmethod
    def fit_to_layout(cls, source_image_path: str, output_image_path: str, layout, mode: str = "cover", **kwargs) -> str:
        """Fit an illustration using a PageLayoutSpec from the layout service."""
        return cls.fit_to_page(
            source_image_path,
            output_image_path,
            page_width_mm=layout.page_width_mm,
            page_height_mm=layout.page_height_mm,
            bleed_mm=layout.bleed_mm,
            safe_margin_mm=layout.safe_margin_mm,
            dpi=layout.dpi,
            mode=mode,
            **kwargs,
        )

    @staticmethod
    def safe_area_box(page_width_mm: float, page_height_mm: float, bleed_mm: float = 3.0,
                      safe_margin_mm: float = 12.0, dpi: int = 300) -> Tuple[int, int, int, int]:
        """Pixel box (left, top, right, bottom) of the safe text/art area."""
        bleed_px = int(round((bleed_mm / MM_PER_INCH) * dpi))
        safe_px = int(round((safe_margin_mm / MM_PER_INCH) * dpi))
        page_w_px = int(round((page_width_mm / MM_PER_INCH) * dpi))
        page_h_px = int(round((page_height_mm / MM_PER_INCH) * dpi))
        left = bleed_px + safe_px
        top = bleed_px + safe_px
        right = bleed_px + page_w_px - safe_px
        bottom = bleed_px + page_h_px - safe_px
        return left, top, right, bottom

    @staticmethod
    def check_print_resolution(image_path: str, dpi: int = 300) -> dict:
        """Estimate effective DPI for a US 6x9 page and flag print risk."""
        with Image.open(image_path) as img:
            w, h = img.size
        target_w_in = 6.0
        target_h_in = 9.0
        effective = min(w / target_w_in, h / target_h_in)
        return {
            "width_px": w,
            "height_px": h,
            "effective_dpi": round(effective, 1),
            "print_ready": effective >= dpi * 0.85,
        }


    # ------------------------------------------------------------------ colour
    @staticmethod
    def convert_to_cmyk(
        source_image_path: str,
        output_image_path: str,
        icc_profile_path: Optional[str] = None,
        dpi: int = 300,
    ) -> dict:
        """Convert artwork to CMYK for offset/digital print.

        Without an ICC profile this uses Pillow's generic CMYK conversion, which is fine
        for proofing but not a colour-managed match — supply the printer's profile
        (e.g. ``USWebCoatedSWOP.icc``) for a real conversion.
        """
        image = ImageOps.exif_transpose(Image.open(source_image_path)).convert("RGB")
        managed = False
        if icc_profile_path and Path(icc_profile_path).exists():
            try:
                src_profile = ImageCms.ImageCmsProfile(icc_profile_path)
                image = ImageCms.profileToProfile(
                    image, src_profile, src_profile, outputMode="CMYK"
                )
                managed = True
            except Exception:
                image = image.convert("CMYK")
        else:
            image = image.convert("CMYK")

        output = Path(output_image_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix.lower() not in (".jpg", ".jpeg", ".tif", ".tiff"):
            output = output.with_suffix(".jpg")
        image.save(output, quality=95, dpi=(dpi, dpi))
        return {
            "path": str(output),
            "mode": "CMYK",
            "colour_managed": managed,
            "icc_profile": icc_profile_path if managed else None,
            "warning": None if managed else "generic CMYK conversion — proof against the printer profile",
        }

    @staticmethod
    def strip_metadata(source_image_path: str, output_image_path: str) -> str:
        """Remove EXIF/GPS before a file leaves the studio."""
        image = ImageOps.exif_transpose(Image.open(source_image_path))
        clean = Image.new(image.mode, image.size)
        clean.putdata(list(image.getdata()))
        output = Path(output_image_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        clean.save(output)
        return str(output)
