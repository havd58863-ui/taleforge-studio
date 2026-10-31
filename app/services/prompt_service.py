"""Scene prompt engine: turns a scene summary into a print-ready illustration recipe."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class PromptRecipe:
    title: str
    scene_summary: str
    prompt: str
    negative_prompt: str
    style: str
    mood: str
    lighting: str
    palette: List[str] = field(default_factory=list)
    page_type: str = "single"
    camera: str = "three_quarter"
    composition: str = ""
    text_area: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


DEFAULT_NEGATIVE = (
    "blurry face, distorted anatomy, extra limbs, duplicate hands, low detail, "
    "cluttered background, poor lighting, text covering face, distorted perspective, "
    "watermark, signature, harsh shadows, oversaturated colors"
)


class PromptService:
    @staticmethod
    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip())

    @staticmethod
    def infer_style(summary: str) -> str:
        s = summary.lower()
        if "forest" in s or "magic" in s or "lantern" in s:
            return "storybook_whimsical"
        if "castle" in s or "royal" in s:
            return "fairytale_royal"
        if "river" in s or "sea" in s or "ocean" in s:
            return "soft_nature_storybook"
        return "premium_children_storybook"

    @staticmethod
    def infer_mood(summary: str) -> str:
        s = summary.lower()
        if "happy" in s or "joy" in s or "smile" in s:
            return "joyful"
        if "afraid" in s or "dark" in s or "shadow" in s:
            return "mystical_tension"
        if "hope" in s or "sunrise" in s or "gentle" in s:
            return "hopeful"
        return "warm_and_curious"

    @staticmethod
    def infer_lighting(summary: str) -> str:
        s = summary.lower()
        if "sunrise" in s or "dawn" in s or "morning" in s:
            return "soft_golden_morning_light"
        if "night" in s or "moon" in s:
            return "soft_night_light_with_subtle_glow"
        if "rain" in s or "storm" in s:
            return "dramatic_cloudy_light"
        return "soft_daylight"

    @staticmethod
    def infer_page_type(summary: str) -> str:
        s = summary.lower()
        if "opening" in s or "finale" in s or "dream" in s or "full page" in s:
            return "full_bleed"
        if "wide" in s or "forest" in s or "journey" in s or "mountain" in s:
            return "spread"
        return "single"

    @staticmethod
    def infer_camera(summary: str) -> str:
        s = summary.lower()
        if "close" in s or "face" in s or "eyes" in s:
            return "close_up"
        if "far away" in s or "wide" in s or "forest" in s or "sky" in s:
            return "wide_shot"
        if "run" in s or "jump" in s:
            return "dynamic_action"
        return "three_quarter"

    @staticmethod
    def infer_palette(summary: str) -> List[str]:
        s = summary.lower()
        if "forest" in s or "lantern" in s:
            return ["#7AAE72", "#D9E7AD", "#F5D58C", "#2E4A3A"]
        if "river" in s or "lake" in s or "ocean" in s:
            return ["#7EC8E3", "#D7F0FF", "#F4E7B4", "#264653"]
        if "castle" in s:
            return ["#8F6B5B", "#F4D8A8", "#E7D5B1", "#4B2D3A"]
        return ["#A7D8C0", "#F7D88E", "#8FB3D9", "#F7E5C6"]

    @staticmethod
    def infer_composition(summary: str, page_type: str) -> str:
        s = summary.lower()
        if page_type == "spread":
            return "wide_background_with_primary_subject_balanced_center"
        if page_type == "full_bleed":
            return "immersive_background_with_focal_subject_and_spacious_negative_area"
        if "friend" in s or "together" in s:
            return "warm_centered_grouping_with_balanced_spacing"
        return "balanced_storybook_layout_with_clear_subject_and_safe_text_zone"

    @staticmethod
    def text_area_for_page(page_size: str = "US_6_X_9", bleed_mm: float = 3.0) -> Dict:
        """Safe text zone inside the trim area (mm). Keeps text off the bleed."""
        sizes = {
            "US_6_X_9": (152.4, 228.6),
            "US_8_5_X_8_5": (215.9, 215.9),
            "US_8_X_10": (203.2, 254.0),
            "A4": (210.0, 297.0),
            "SQUARE_8": (203.2, 203.2),
        }
        width, height = sizes.get(page_size.upper(), sizes["US_6_X_9"])
        margin = 12.0
        return {
            "page_width_mm": width,
            "page_height_mm": height,
            "bleed_mm": bleed_mm,
            "x_mm": margin,
            "y_mm": margin,
            "width_mm": round(width - (2 * margin), 2),
            "height_mm": round(height - (2 * margin), 2),
            "orientation": "landscape" if width > height else "portrait",
        }

    def build_prompt(
        self,
        title: str,
        scene_summary: str,
        page_size: str = "US_6_X_9",
        character_tokens: List[str] | None = None,
    ) -> PromptRecipe:
        summary = self.normalize(scene_summary)
        style = self.infer_style(summary)
        mood = self.infer_mood(summary)
        lighting = self.infer_lighting(summary)
        page_type = self.infer_page_type(summary)
        camera = self.infer_camera(summary)
        palette = self.infer_palette(summary)
        composition = self.infer_composition(summary, page_type)
        tokens = " ".join(character_tokens or [])

        prompt = (
            f"{title}, {summary}, premium children's book illustration, "
            f"{style}, {mood}, {lighting}, {camera}, {composition}, "
            f"soft palette {', '.join(palette)}, clean anatomy, expressive faces, "
            f"storybook quality, gentle emotional clarity, highly detailed, "
            f"safe text area, negative space for text, polished print-ready illustration"
        )
        if tokens:
            prompt += f", consistent characters: {tokens}"

        return PromptRecipe(
            title=title,
            scene_summary=summary,
            prompt=prompt,
            negative_prompt=DEFAULT_NEGATIVE,
            style=style,
            mood=mood,
            lighting=lighting,
            palette=palette,
            page_type=page_type,
            camera=camera,
            composition=composition,
            text_area=self.text_area_for_page(page_size),
        )
