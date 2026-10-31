"""Deterministic placeholder artwork — a real background, not a dashed grey box.

The pipeline must be able to produce a complete, printable book even before an image model
is connected. This service paints a soft, print-safe scene (gradient light, layered hills,
lantern glow, paper grain) that:

* covers the **whole page** including bleed,
* keeps the interesting shapes inside the safe area (nothing important near the trim),
* is dark/light enough to pass the exposure gate,
* is different for every scene (seeded by the scene text) but identical on every re-run,
* yields usable **contours**, so the same art becomes a coloring page (see line_art_service).

Replace it with a real illustration any time: pass ``page_images`` to the renderer instead.
"""
from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter

DEFAULT_PALETTES: List[List[Tuple[int, int, int]]] = [
    [(244, 214, 156), (214, 232, 196), (122, 174, 114), (46, 74, 58)],
    [(240, 226, 205), (222, 199, 170), (150, 178, 160), (58, 76, 84)],
    [(236, 224, 238), (206, 214, 236), (140, 158, 190), (52, 62, 88)],
]


class PlaceholderArtService:
    def __init__(self, dpi: int = 300) -> None:
        self.dpi = dpi

    def make_scene_art(
        self,
        scene: str,
        page_size_px: Tuple[int, int],
        output_path: str,
        palette: Optional[List[Tuple[int, int, int]]] = None,
        seed_text: str = "",
        safe_inset: float = 0.12,
    ) -> Dict[str, object]:
        width, height = page_size_px
        seed = int(hashlib.sha256((seed_text or scene).encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        colors = palette or DEFAULT_PALETTES[seed % len(DEFAULT_PALETTES)]

        image = Image.new("RGB", (width, height), colors[0])
        draw = ImageDraw.Draw(image)

        # Sky: vertical gradient
        for y in range(height):
            ratio = y / max(1, height - 1)
            top, bottom = colors[0], colors[1]
            draw.line(
                [(0, y), (width, y)],
                fill=tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)),
            )

        # Soft hills, kept inside the safe area so nothing important sits near the trim
        margin_x = width * safe_inset
        horizon = height * (0.55 + 0.08 * rng.random())
        for layer, colour in enumerate((colors[2], colors[3])):
            peak = horizon + layer * height * 0.08
            points = [(0, height)]
            steps = 8
            for step in range(steps + 1):
                x = width * step / steps
                y = peak - math.sin((step / steps) * math.pi * (1 + layer)) * height * (0.06 + 0.03 * layer)
                points.append((x, y))
            points.append((width, height))
            draw.polygon(points, fill=colour)

        # Lantern glows / focal shapes inside the safe area
        for _ in range(6):
            cx = rng.uniform(margin_x, width - margin_x)
            cy = rng.uniform(height * 0.25, height * 0.7)
            radius = rng.uniform(width * 0.05, width * 0.13)
            glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow)
            glow_draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=(255, 240, 200, 190),
            )
            glow = glow.filter(ImageFilter.GaussianBlur(radius * 0.35))
            image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")

        # Soft vignette instead of grain: grain turns into speckle when the same art is
        # converted to line art for the coloring book.
        vignette = Image.new("L", (width, height), 0)
        draw_v = ImageDraw.Draw(vignette)
        draw_v.ellipse([-width * 0.25, -height * 0.15, width * 1.25, height * 1.15], fill=255)
        vignette = vignette.filter(ImageFilter.GaussianBlur(width * 0.08))
        darker = Image.new("RGB", (width, height), tuple(int(c * 0.82) for c in colors[3]))
        image = Image.composite(image, darker, vignette)

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, dpi=(self.dpi, self.dpi))
        return {
            "path": str(path),
            "width_px": width,
            "height_px": height,
            "dpi": self.dpi,
            "seed": seed,
            "source": "placeholder_art",
            "note": "Generated placeholder scene — replace with an illustration (IMAGE_PROVIDER) when available",
        }
