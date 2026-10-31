"""Image prompt compiler — one scene in, engine-ready prompts out.

A single sentence per scene is never enough for professional illustration. This compiler
combines four sources into a deterministic prompt set:

1. the **scene** (action, camera, lighting, mood) from `prompt_service`
2. the **character consistency tokens** from the story bible (same face every page)
3. the **style bible** from the Story Director (palette, line, texture, faces)
4. the **engine dialect** — SDXL/Flux tag syntax or DALL·E natural language, with the
   CLIP 77-token ceiling respected for SDXL-family models

Engines: ``sdxl``, ``flux``, ``midjourney``, ``dalle3``, ``generic``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ENGINES = ("sdxl", "flux", "midjourney", "dalle3", "generic")

NEGATIVE_BASE = (
    "text, letters, watermark, signature, logo, frame, border, cropped head, cut hands, "
    "extra fingers, extra limbs, deformed anatomy, blurry face, dead eyes, plastic skin, "
    "harsh flash, oversaturated, cluttered background, scary imagery, weapons, blood"
)

SAFETY_SUFFIX = {
    "sdxl": "children's book illustration, safe for children, gentle, warm, print quality",
    "flux": "premium children's picture book illustration, soft light, print quality",
    "midjourney": "children's picture book illustration, warm, gentle, print quality",
    "dalle3": "A gentle, age-appropriate children's picture-book illustration.",
    "generic": "children's book illustration, print quality",
}


@dataclass
class CompiledPrompt:
    engine: str
    positive: str
    negative: str
    aspect_ratio: str
    width_px: int
    height_px: int
    tokens_estimate: int
    truncated: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "positive": self.positive,
            "negative": self.negative,
            "aspect_ratio": self.aspect_ratio,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "tokens_estimate": self.tokens_estimate,
            "truncated": self.truncated,
            "notes": self.notes,
        }


class ImagePromptCompiler:
    CLIP_TOKEN_BUDGET = 75  # 77 minus BOS/EOS

    def compile(
        self,
        scene: Dict[str, Any],
        style_bible: Optional[Dict[str, Any]] = None,
        characters: Optional[List[Dict[str, Any]]] = None,
        engine: str = "sdxl",
        width_px: int = 1871,
        height_px: int = 2771,
        aspect_ratio: Optional[str] = None,
    ) -> CompiledPrompt:
        engine = (engine or "sdxl").lower()
        if engine not in ENGINES:
            engine = "generic"
        style_bible = style_bible or {}
        characters = characters or []
        notes: List[str] = []

        subject = ", ".join(
            part for part in [
                str(scene.get("title", "")).strip(),
                str(scene.get("summary", "")).strip(),
            ] if part
        )
        camera = str(scene.get("camera", scene.get("camera_angle", "three_quarter")))
        lighting = str(scene.get("lighting", "soft_daylight"))
        mood = str(scene.get("mood", "warm_and_curious"))
        palette = scene.get("palette") or style_bible.get("palette") or []
        if isinstance(palette, str):
            palette = [p.strip() for p in palette.split(",") if p.strip()]

        cast = []
        for character in characters:
            token = character.get("consistency_token") or character.get("visual_summary")
            if token:
                cast.append(str(token).strip("[] "))

        style_bits = [
            style_bible.get("line", ""),
            style_bible.get("texture", ""),
            style_bible.get("lighting", ""),
            style_bible.get("faces", ""),
        ]
        style_text = ", ".join(bit for bit in style_bits if bit)

        ratio = aspect_ratio or self._ratio(width_px, height_px)
        negative = NEGATIVE_BASE
        if engine == "dalle3":
            negative = ""  # DALL·E has no negative prompt; folded into the instruction

        if engine in ("sdxl", "flux", "generic"):
            segments = [
                subject,
                "characters: " + "; ".join(cast) if cast else "",
                style_text,
                f"palette {', '.join(palette)}" if palette else "",
                f"{camera}, {lighting}, {mood}",
                SAFETY_SUFFIX[engine],
            ]
            positive = ", ".join(s for s in segments if s)
            positive, truncated = self._fit_clip(positive) if engine == "sdxl" else (positive, False)
            if truncated:
                notes.append("prompt trimmed to the 77-token CLIP window (SDXL); cast kept first")
        elif engine == "midjourney":
            positive = (
                f"{subject} --ar {ratio} --style raw --stylize 250 "
                f"--no {NEGATIVE_BASE}"
            )
            truncated = False
            if cast:
                notes.append("Midjourney has no character reference in text; use --cref with a reference sheet")
        else:  # dalle3 natural language
            positive = (
                f"{SAFETY_SUFFIX['dalle3']} {subject}. "
                f"Style: {style_text or 'soft watercolour, gentle linework'}. "
                f"Palette: {', '.join(palette) or 'warm, gentle'}. "
                f"Camera: {camera.replace('_', ' ')}; lighting: {lighting.replace('_', ' ')}; mood: {mood.replace('_', ' ')}. "
                "No text, no lettering, no logos, no watermark anywhere in the image. "
                "Keep the scene gentle and appropriate for very young children."
            )
            truncated = False

        return CompiledPrompt(
            engine=engine,
            positive=positive,
            negative=negative,
            aspect_ratio=ratio,
            width_px=width_px,
            height_px=height_px,
            tokens_estimate=self._tokens(positive),
            truncated=truncated,
            notes=notes,
        )

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _tokens(text: str) -> int:
        return int(len(text.split()) * 1.35)

    def _fit_clip(self, text: str) -> tuple:
        if self._tokens(text) <= self.CLIP_TOKEN_BUDGET:
            return text, False
        parts = [p.strip() for p in text.split(",") if p.strip()]
        kept: List[str] = []
        for part in parts:
            candidate = ", ".join(kept + [part])
            if self._tokens(candidate) > self.CLIP_TOKEN_BUDGET:
                break
            kept.append(part)
        return ", ".join(kept), True

    @staticmethod
    def _ratio(width: int, height: int) -> str:
        from math import gcd

        divisor = gcd(width, height) or 1
        return f"{width // divisor}:{height // divisor}"
