"""Original story-idea generation and viability scoring."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class StoryIdea:
    title: str
    premise: str
    genre: str
    target_age_min: int
    target_age_max: int
    setting: str
    world: str
    central_conflict: str
    emotional_core: str
    lesson_value: str
    originality_score: float = 0.0
    market_score: float = 0.0
    visual_score: float = 0.0
    novelty_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Weights must sum to 1.0 — otherwise the weighted average can exceed 100 and
# every idea clamps to a perfect score (which makes ranking meaningless).
WEIGHTS = {
    "originality_score": 0.40,
    "market_score": 0.30,
    "visual_score": 0.15,
    "novelty_score": 0.15,
}
WEIGHT_TOTAL = sum(WEIGHTS.values())

# Theme/setting signals act as bounded bonuses, never as the bulk of the score.
MAX_THEME_BONUS = 15.0
MAX_SETTING_BONUS = 5.0
QUALITY_SHARE = 0.80

# Commercial signals used by a premium children's-book catalogue.
THEME_SIGNALS = {
    "kindness": 18,
    "friendship": 18,
    "courage": 16,
    "bravery": 16,
    "curiosity": 12,
    "belonging": 12,
    "empathy": 14,
    "patience": 10,
    "listening": 10,
    "family": 12,
}
SETTING_SIGNALS = {"forest": 8, "magic": 10, "ocean": 8, "river": 7, "castle": 7, "mountain": 6}


class IdeaService:
    """Scores concepts on originality, market fit, visual potential and novelty."""

    def score_idea(self, idea: StoryIdea) -> Dict[str, Any]:
        haystack = " ".join(
            [idea.setting, idea.world, idea.lesson_value, idea.emotional_core, idea.premise]
        ).lower()

        theme_points = sum(points for key, points in THEME_SIGNALS.items() if key in haystack)
        setting_points = sum(points for key, points in SETTING_SIGNALS.items() if key in haystack)

        weighted = sum(getattr(idea, field) * weight for field, weight in WEIGHTS.items())
        quality = weighted / WEIGHT_TOTAL  # 0-100, never above 100

        theme_bonus = min(MAX_THEME_BONUS, theme_points * 0.5)
        setting_bonus = min(MAX_SETTING_BONUS, setting_points * 0.4)

        score = round(min(100.0, quality * QUALITY_SHARE + theme_bonus + setting_bonus), 2)

        if score >= 85:
            recommendation = "Strong concept — green-light for production"
        elif score >= 75:
            recommendation = "Viable with refinement"
        else:
            recommendation = "Needs rework before production"

        return {
            "total_score": score,
            "is_viable": score >= 75.0,
            "recommendation": recommendation,
            "breakdown": {
                "quality": round(quality, 2),
                "theme_points": theme_points,
                "theme_bonus": round(theme_bonus, 2),
                "setting_points": setting_points,
                "setting_bonus": round(setting_bonus, 2),
            },
        }

    def generate_candidates(self) -> List[StoryIdea]:
        return [
            StoryIdea(
                title="Luna and the Lantern Forest",
                premise="A curious child learns that courage is choosing kindness even when she is afraid.",
                genre="fantasy",
                target_age_min=4,
                target_age_max=8,
                setting="Whispering forest at dawn",
                world="A magical forest where lanterns bloom like tiny stars",
                central_conflict="Luna must find her friend before dawn fades and the forest closes its secret paths",
                emotional_core="Bravery, empathy, belonging",
                lesson_value="True courage is choosing kindness even when fear is strong",
                originality_score=86,
                market_score=88,
                visual_score=90,
                novelty_score=82,
            ),
            StoryIdea(
                title="Mila and the River of Lost Wishes",
                premise="A shy girl discovers the power of listening before speaking.",
                genre="fantasy",
                target_age_min=5,
                target_age_max=9,
                setting="River valley under moonlight",
                world="The river carries forgotten wishes and reveals hidden truths",
                central_conflict="Mila must return a wish before dawn destroys it forever",
                emotional_core="Listening, patience, trust",
                lesson_value="Sometimes the gentlest answer heals the most",
                originality_score=84,
                market_score=81,
                visual_score=89,
                novelty_score=80,
            ),
        ]

    def ranked_candidates(self) -> List[Dict[str, Any]]:
        out = []
        for idea in self.generate_candidates():
            out.append({"idea": idea.to_dict(), "score": self.score_idea(idea)})
        return sorted(out, key=lambda item: item["score"]["total_score"], reverse=True)
