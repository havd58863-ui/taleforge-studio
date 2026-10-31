"""Story Director — turns an approved idea into a precise, non-negotiable brief.

This is the "art director + commissioning editor" layer: before a single word is
written it fixes

* the page count and the **word budget per page for the age band**
* the emotional arc as a beat sheet (one beat per spread, with a temperature)
* the reading level, tense, POV and the refrain the writer must repeat
* the art direction (palette, line, lighting) that the prompt compiler consumes
* the series hooks, so book 1 stays expandable into a brand

The writer is not allowed to invent outside this contract; the editor then checks the
result against it. Everything here is deterministic — no model needed.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.services.language_policy import is_enabled, language_name

# Age band -> (words per page, min font size pt, max sentences per page)
AGE_BANDS: Dict[str, Dict[str, Any]] = {
    "0-3": {"words_per_page": (8, 25), "font_size": 18, "max_sentences": 2, "spreads": 24},
    "3-5": {"words_per_page": (20, 45), "font_size": 17, "max_sentences": 3, "spreads": 28},
    "4-8": {"words_per_page": (25, 60), "font_size": 15, "max_sentences": 4, "spreads": 32},
    "6-9": {"words_per_page": (45, 90), "font_size": 14, "max_sentences": 5, "spreads": 40},
    "8-12": {"words_per_page": (60, 130), "font_size": 13, "max_sentences": 6, "spreads": 48},
}

# The canonical picture-book arc. Weights are spread shares.
ARC_TEMPLATE = [
    ("hollow", "Ordinary world — show the character's want and their small lack", 0.12, 2),
    ("inciting", "Something arrives that cannot be ignored", 0.10, 3),
    ("refusal", "Fear or doubt: the character tries the safe option first", 0.12, 2),
    ("first_attempt", "First try fails in a specific, visual way", 0.14, 3),
    ("dark_moment", "The lowest point — the character nearly gives up", 0.12, 2),
    ("turn", "A truth is understood (from a friend, a memory or the world)", 0.10, 3),
    ("climax", "The choice that costs something — kindness/courage in action", 0.12, 4),
    ("resolution", "The world is repaired in a concrete, visible way", 0.10, 4),
    ("image_of_hope", "Final image that echoes page one, changed", 0.08, 3),
]

STYLE_BIBLES: Dict[str, Dict[str, Any]] = {
    "storybook_whimsical": {
        "palette": ["#7AAE72", "#D9E7AD", "#F5D58C", "#2E4A3A", "#FFFDF9"],
        "line": "soft graphite linework, gentle tapering, no harsh black",
        "texture": "cold-press watercolour paper grain, visible light washes",
        "lighting": "warm dappled light, one clear light direction",
        "faces": "round cheeks, wide expressive eyes, minimal detail, no uncanny features",
        "references": "classic picture-book painting; flat colour with soft gradients",
    },
    "soft_nature_storybook": {
        "palette": ["#7EC8E3", "#D7F0FF", "#F4E7B4", "#264653", "#FFFDF9"],
        "line": "organic ink line, loose but confident",
        "texture": "gouache with paper show-through",
        "lighting": "cool ambient light with one warm accent",
        "faces": "calm expressions, readable silhouettes",
        "references": "modern nature picture books",
    },
    "fairytale_royal": {
        "palette": ["#8F6B5B", "#F4D8A8", "#E7D5B1", "#4B2D3A", "#FFFDF9"],
        "line": "ornate but restrained line, symmetric framing",
        "texture": "rich flat colour with gold accent",
        "lighting": "directional candlelight with deep but clean shadows",
        "faces": "noble, gentle expressions",
        "references": "traditional European storybook",
    },
}

HARD_CONSTRAINTS = [
    "single point of view; the child protagonist acts, adults only assist",
    "no death, no violence, no threat that a 4-year-old cannot resolve by the next page",
    "fear may be shown but must be visually answerable (light, a hand, a small friend)",
    "one refrain line repeated exactly three times across the book",
    "every spread ends on a small hook that pulls the page turn",
    "no didactic moral sentence — the lesson lives in the action",
    "each page must carry one concrete sensory detail (sound, warmth, smell, texture)",
    "dialogue under 40% of the text, and every line of dialogue moves the action",
]


@dataclass
class Beat:
    name: str
    brief: str
    page_count: int
    temperature: int  # 1 calm .. 5 peak
    pages: List[int] = field(default_factory=list)
    art_note: str = ""


@dataclass
class StoryBrief:
    title: str
    logline: str
    audience: str
    age_band: str
    page_count: int
    words_per_page: tuple
    total_word_budget: int
    reading_level: str
    tense: str
    pov: str
    refrain: str
    beats: List[Beat]
    constraints: List[str]
    style_bible: Dict[str, Any]
    series_hooks: List[str]
    recommended_format: str
    language: str = "en"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["words_per_page"] = list(self.words_per_page)
        return data

    # ------------------------------------------------------------- prompting
    def to_writer_prompt(self) -> Dict[str, str]:
        """System + user prompt handed to the LLM writer. The brief is the contract."""
        pages = ", ".join(
            f"{b.name}: pages {b.pages[0]}-{b.pages[-1]} ({b.page_count} pages, temp {b.temperature}/5) — {b.brief}"
            for b in self.beats
        )
        system = (
            "You are a senior children's picture-book author published by major houses. "
            "You write for read-aloud performance, not for page count. You never break the brief."
        )
        user = (
            f"BRIEF\nTitle: {self.title}\nLogline: {self.logline}\nAudience: {self.audience} ({self.age_band})\n"
            f"Pages: {self.page_count} | words per page: {self.words_per_page[0]}-{self.words_per_page[1]}\n"
            f"Reading level: {self.reading_level} | tense: {self.tense} | POV: {self.pov}\n"
            f"Language: {language_name(self.language)} ({self.language}) — write the whole manuscript in it, "
            "idiomatic and natural for a native-speaking child, never a translation of an English draft\n"
            f"Refrain (repeat exactly 3 times, identical wording): \"{self.refrain}\"\n"
            f"ARC\n{pages}\n"
            "HARD CONSTRAINTS\n" + "\n".join(f"- {c}" for c in self.constraints) + "\n\n"
            "Return STRICT JSON:\n"
            '{"pages":[{"page":1,"text":"...","scene":"one sentence describing the illustration",'
            '"beat":"hollow","refrain":false}],"title":"...","logline":"..."}\n'
            "Rules: respect the word budget per page (count them), one beat per page range, "
            "no moralising, no text over the illustration, filename-safe plain text."
        )
        return {"system": system, "user": user}


class StoryDirectorService:
    """Builds and validates story briefs."""

    @staticmethod
    def age_band_for(age_min: int, age_max: int) -> str:
        key = f"{int(age_min)}-{int(age_max)}"
        if key in AGE_BANDS:
            return key
        for band, cfg in AGE_BANDS.items():
            low, high = (int(x) for x in band.split("-"))
            if age_min >= low and age_max <= high:
                return band
        return "4-8"

    def build_brief(
        self,
        idea: Dict[str, Any],
        age_min: int = 4,
        age_max: int = 8,
        page_count: Optional[int] = None,
        title: Optional[str] = None,
        refrain: Optional[str] = None,
        format_hint: str = "single",
        language: str = "en",
    ) -> StoryBrief:
        language = (language or "en").strip().lower()
        if not is_enabled(language):
            raise ValueError(
                f"language '{language}' is disabled; product scope is English, German and Spanish "
                "(set OUTPUT_LANGUAGES to change it)"
            )
        band = self.age_band_for(age_min, age_max)
        cfg = AGE_BANDS[band]
        pages = int(page_count or cfg["spreads"])

        beats = self._allocate_beats(pages)
        words_low, words_high = cfg["words_per_page"]
        total_words = int((words_low + words_high) / 2 * len(beats))
        style_key = idea.get("style") or self._infer_style(idea)

        return StoryBrief(
            title=title or idea.get("title", "Untitled"),
            logline=idea.get(
                "central_conflict",
                idea.get("premise", "A child must choose kindness when it is hard."),
            ),
            audience=f"children {age_min}-{age_max}",
            age_band=band,
            page_count=sum(beat.page_count for beat in beats),
            words_per_page=(words_low, words_high),
            total_word_budget=total_words,
            reading_level="emerging reader (simple sentences, concrete nouns, 1-2 clauses)",
            tense="present tense",
            pov="third person, close to the child protagonist",
            refrain=refrain or self._suggest_refrain(idea),
            beats=beats,
            constraints=list(HARD_CONSTRAINTS) + [
                f"write every page in {language_name(language)} — natural, idiomatic, read-aloud {language_name(language)}; no translationese",
                f"do not switch language mid-book; the manuscript language is fixed to {language}",
            ],
            style_bible={**STYLE_BIBLES.get(style_key, STYLE_BIBLES["storybook_whimsical"]),
                         "style_key": style_key, "max_sentences_per_page": cfg["max_sentences"]},
            series_hooks=self._series_hooks(idea, format_hint),
            recommended_format=format_hint,
            language=language,
        )

    # ------------------------------------------------------------------ parts
    @staticmethod
    def _allocate_beats(page_count: int) -> List[Beat]:
        """Split the book into beats so the page counts add up exactly."""
        page_count = max(len(ARC_TEMPLATE), int(page_count))
        beats: List[Beat] = []
        cursor = 1
        allocated = 0
        for index, (name, brief, weight, temperature) in enumerate(ARC_TEMPLATE):
            if index == len(ARC_TEMPLATE) - 1:
                count = page_count - allocated
            else:
                count = max(1, int(round(page_count * weight)))
                remaining_beats = len(ARC_TEMPLATE) - index - 1
                count = min(count, page_count - allocated - remaining_beats)
            pages = list(range(cursor, cursor + count))
            cursor += count
            allocated += count
            beats.append(Beat(name=name, brief=brief, page_count=count, temperature=temperature, pages=pages))
        return beats

    @staticmethod
    def _infer_style(idea: Dict[str, Any]) -> str:
        text = " ".join(str(idea.get(k, "")) for k in ("setting", "world", "premise")).lower()
        if "forest" in text or "lantern" in text or "magic" in text:
            return "storybook_whimsical"
        if "river" in text or "sea" in text or "ocean" in text:
            return "soft_nature_storybook"
        if "castle" in text or "royal" in text:
            return "fairytale_royal"
        return "storybook_whimsical"

    @staticmethod
    def _suggest_refrain(idea: Dict[str, Any]) -> str:
        lesson = str(idea.get("lesson_value", "")).lower()
        if "courage" in lesson:
            return "Small light, hold on."
        if "listen" in lesson:
            return "Listen first, then speak."
        if "kind" in lesson:
            return "Kind is a kind of brave."
        return "One small step at a time."

    @staticmethod
    def _series_hooks(idea: Dict[str, Any], format_hint: str) -> List[str]:
        hooks = [
            "a recurring companion the child can meet again",
            "a world rule that can be broken in a later book",
            "an object that passes to a new protagonist",
        ]
        if format_hint != "single":
            hooks.append("an episodic engine: each book solves one new problem in the same world")
        return hooks

    # --------------------------------------------------------------- validate
    @staticmethod
    def validate_brief(brief: StoryBrief) -> List[str]:
        problems: List[str] = []
        if brief.page_count < 24:
            problems.append("KDP requires at least 24 pages")
        if brief.page_count > 48:
            problems.append("picture books above 48 pages are a hard sell for this age band")
        low, high = brief.words_per_page
        if low > high:
            problems.append("word budget is inverted")
        if sum(beat.page_count for beat in brief.beats) != brief.page_count:
            problems.append("beat sheet does not cover every page")
        if not brief.refrain.strip():
            problems.append("a picture book without a refrain loses read-aloud rhythm")
        if not brief.style_bible.get("palette"):
            problems.append("no art direction palette — the image engine has nothing to follow")
        return problems
