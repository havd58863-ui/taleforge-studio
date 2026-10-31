"""Coloring-page generation from illustrations (line-art extraction)."""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


class ColoringService:
    @staticmethod
    def generate_coloring_page(source_image_path: str, output_path: str, threshold: int = 180) -> str:
        """Produce clean black-and-white line art suitable for children to colour."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if cv2 is not None:
            data = np.fromfile(source_image_path, dtype=np.uint8)
            gray = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
            smoothed = cv2.medianBlur(gray, 5)
            edges = cv2.adaptiveThreshold(
                smoothed, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 9
            )
            out = Path(output).with_suffix(".png")
            cv2.imwrite(str(out), edges)
            return str(out)

        img = Image.open(source_image_path).convert("L")
        img = ImageOps.autocontrast(img)
        img = img.filter(ImageFilter.MedianFilter(5))
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(1.8)
        img = img.point(lambda p: 255 if p > threshold else 0)
        img.save(output)
        return str(output)

    @staticmethod
    def build_coloring_book(images: List[str], output_dir: str) -> List[str]:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        created: List[str] = []
        for idx, image in enumerate(images, start=1):
            target = output / f"page_{idx:03d}.png"
            created.append(ColoringService.generate_coloring_page(image, str(target)))
        return created
