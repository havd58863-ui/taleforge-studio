"""Story Writer — executes a StoryBrief, page by page.

Two modes, same output contract:

* **LLM mode** (recommended, production): any OpenAI-compatible endpoint or a local
  Ollama model writes the pages against the brief. See ``app/services/llm_client.py``.
* **Offline mode** (default, no key needed): a deterministic scaffold writer that obeys
  the same brief — word budget, beat order, refrain count, sentence ceiling — so the rest
  of the factory can run end to end. It is a scaffold, not a substitute for a writer.

Output contract (consumed by prompts → layout → PDF):

    {"title": str, "pages": [{"page": int, "text": str, "scene": str,
                              "beat": str, "refrain": bool, "word_count": int}]}
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.language_policy import SCAFFOLD_LANGUAGES, language_name
from app.services.llm_client import LLMClient, LLMError, get_llm
from app.services.story_director_service import Beat, StoryBrief


@dataclass
class WrittenPage:
    page: int
    text: str
    scene: str
    beat: str
    refrain: bool = False

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page": self.page,
            "text": self.text,
            "scene": self.scene,
            "beat": self.beat,
            "refrain": self.refrain,
            "word_count": self.word_count,
        }


# Offline scaffold: two or three sentences that respect the age-band word budget,
# carry one sensory detail, and end on a small page-turn hook. This is a scaffold that
# keeps the factory runnable without a model — not a substitute for a real writer.
SCAFFOLD: Dict[str, Dict[str, List[str]]] = {
    "hollow": {
        "text": [
            "{name} lives where the {place} hums all day long. Every morning {name} counts the "
            "{place} and finds one space still empty. The wind smells of wet moss and warm stone.",
            "The {place} is busy and bright, and everyone has a job to do. {name} has a job too: "
            "counting the spaces. One of them stays quiet and empty all morning.",
        ],
        "scene": [
            "wide establishing shot of {name} inside the {place}, one clearly empty space in frame, "
            "warm dappled morning light",
            "medium shot of {name} counting along the {place}, calm palette, soft depth of field",
        ],
    },
    "inciting": {
        "text": [
            "Then a {object} flickers once, then twice, and will not stay quiet. It sounds like a "
            "secret that has decided to be found, and {name}'s hands feel suddenly warm.",
            "A small sound arrives from the far edge of the {place}. It is thin and bright, like a "
            "bell underwater, and it keeps saying the same three notes.",
        ],
        "scene": [
            "close on the {object} glowing, {name}'s hand reaching in, light on the fingertips",
            "low angle from the grass, the {object} pulsing light across {name}'s face",
        ],
    },
    "refusal": {
        "text": [
            "{name} takes the safe path instead, the one that smells of warm bread and soap. It is "
            "quiet there, and kind, and it leads away from the small bright sound.",
            "The safe path has a gate, and the gate has a latch, and the latch is easy to close. "
            "{name} closes it gently, and the sound gets smaller behind the wood.",
        ],
        "scene": [
            "the safe path, cosy and enclosed, {name} small at the edge of the frame, lantern dim",
            "over-the-shoulder shot of the closing gate, the {object} dim behind the wood",
        ],
    },
    "first_attempt": {
        "text": [
            "{name} opens the gate again and tries. The {object} slips, rolls, and the wind takes the "
            "light into the tall grass, and {name}'s hands feel suddenly too small.",
            "The first try goes wrong in a very small way. A wet root, a turned ankle, a lantern on "
            "its side, and then the {place} looks much bigger than it did at breakfast.",
        ],
        "scene": [
            "dynamic shot of the {object} rolling away, motion in the grass, hair lifted by wind",
            "close on {name}'s empty hands on wet ground, shallow focus, cool shadows",
        ],
    },
    "dark_moment": {
        "text": [
            "The {place} goes grey and still. {name} sits down in the cold and listens to nothing at "
            "all, and the waiting feels longer than the whole morning.",
            "Grey light, grey grass, grey sound. {name} holds both knees and decides, very quietly, "
            "that maybe the light was never meant for small hands.",
        ],
        "scene": [
            "desaturated wide shot, {name} sitting alone, the {place} muted and quiet",
            "high angle, {name} very small in a wide grey field, single cool light source",
        ],
    },
    "turn": {
        "text": [
            "Then {friend} leans close, warm as a pocket, and shows {name} that the light was never "
            "gone. A small voice says the true thing out loud, and the grey begins to lift.",
            "{friend} does not argue. {friend} simply stays, and hums, and the hum makes a shape in "
            "the grey that {name} can finally see.",
        ],
        "scene": [
            "two-shot, {friend} beside {name}, a warm glow held between them",
            "warm close-up of {friend} speaking, colour returning to the palette",
        ],
    },
    "climax": {
        "text": [
            "{name} chooses the harder kindness and steps forward while the {place} holds its breath. "
            "The {object} answers with light that spills out across the wet ground.",
            "There is a cost, and {name} pays it: one step, then another, with the {object} held out "
            "where anyone could take it. The {place} brightens like a held breath let go.",
        ],
        "scene": [
            "heroic but gentle shot, {name} stepping forward, light spilling across the ground",
            "the {place} lit from within, {name} at the centre of the glow, warm rim light",
        ],
    },
    "resolution": {
        "text": [
            "The empty space fills, and the {place} hums a warmer note than before. Everyone can see "
            "it now: the light was made by one small choice.",
            "The neighbours come with quiet hands and warm bread, and the {place} is full of small "
            "noises again. Nobody says the lesson out loud, and everyone understands it.",
        ],
        "scene": [
            "wide warm shot of the filled space, {name} and {friend} together, full saturation",
            "medium shot of the {place} restored, soft evening light, shared warmth",
        ],
    },
    "image_of_hope": {
        "text": [
            "That night {name} counts the {place} again, and every space is full. The {object} keeps "
            "one soft spark inside it, for the next small hand.",
            "The {place} settles into its evening sound, and {name} leaves the gate open a little. "
            "The {object} keeps one soft spark, just in case someone small needs it.",
        ],
        "scene": [
            "final wide shot echoing page one, now complete, dusk palette, open gate",
            "close on the {object} resting in warm dark, one soft spark kept inside",
        ],
    },
}


# Used only when a scaffold page falls under the age-band word floor. Sensory by design.
PADDING: Dict[str, List[str]] = {
    "hollow": ["The air smells of moss and cool stone.", "Somewhere a bucket rings, once."],
    "inciting": ["The sound is warm against her fingers.", "It tastes like the inside of a bell."],
    "refusal": ["The latch is cold and smooth.", "Behind the wood, the hum goes small."],
    "first_attempt": ["Wet grass, cold knees, a stinging palm.", "The lantern knocks against a root."],
    "dark_moment": ["The cold comes up through the ground.", "Her breath makes a small grey cloud."],
    "turn": ["The warmth spreads like tea in a cup.", "Something hums, low and steady."],
    "climax": ["Light runs over wet stone and bright water.", "The whole place smells of warm resin."],
    "resolution": ["Bread steam, soft voices, a settling hush.", "The hum turns round and golden."],
    "image_of_hope": ["The dark is soft, not heavy.", "One spark glows like a held breath."],
}


class StoryWriterService:
    MAX_ATTEMPTS = 2

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self.llm = llm or get_llm()

    # ------------------------------------------------------------------ public
    def write(
        self,
        brief: StoryBrief,
        idea: Optional[Dict[str, Any]] = None,
        characters: Optional[List[Dict[str, Any]]] = None,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        idea = idea or {}
        characters = characters or []

        if use_llm and self.llm.available:
            try:
                pages = self._write_with_llm(brief, idea, characters)
                return {
                    "mode": "llm",
                    "provider": self.llm.provider,
                    "model": self.llm.model,
                    "title": brief.title,
                    "pages": [p.to_dict() for p in pages],
                    "brief": brief.to_dict(),
                }
            except (LLMError, ValueError) as exc:
                fallback_reason = f"LLM failed ({exc}); used offline scaffold"
        else:
            fallback_reason = "LLM not configured; used offline scaffold"

        pages = self._write_offline(brief, idea, characters)
        notice = fallback_reason
        if brief.language not in SCAFFOLD_LANGUAGES:
            notice = (
                f"{fallback_reason}. The offline scaffold writes English only, so this draft is English "
                f"even though the brief asks for {language_name(brief.language)}: configure LLM_* "
                "to get a native German/Spanish manuscript."
            )
        return {
            "mode": "offline" if brief.language in SCAFFOLD_LANGUAGES else "offline_en_fallback",
            "provider": None,
            "model": None,
            "title": brief.title,
            "pages": [p.to_dict() for p in pages],
            "brief": brief.to_dict(),
            "notice": notice,
        }

    # -------------------------------------------------------------------- LLM
    def _write_with_llm(
        self, brief: StoryBrief, idea: Dict[str, Any], characters: List[Dict[str, Any]]
    ) -> List[WrittenPage]:
        prompt = brief.to_writer_prompt()
        if characters:
            names = ", ".join(f"{c.get('name')} ({c.get('role', 'character')})" for c in characters)
            prompt["user"] += f"\nCHARACTERS (keep them exact, do not rename): {names}"
        if idea.get("setting"):
            prompt["user"] += f"\nSETTING: {idea['setting']}"

        result = self.llm.complete(prompt["system"], prompt["user"], json_mode=True, max_tokens=4000)
        payload = result.json()
        if not isinstance(payload, dict) or "pages" not in payload:
            raise ValueError("model did not return the required JSON contract")

        pages: List[WrittenPage] = []
        for index, item in enumerate(payload["pages"], start=1):
            text = self._clean(str(item.get("text", "")))
            if not text:
                continue
            pages.append(
                WrittenPage(
                    page=int(item.get("page", index)),
                    text=text,
                    scene=self._clean(str(item.get("scene", ""))),
                    beat=str(item.get("beat", self._beat_for_page(brief, index))),
                    refrain=bool(item.get("refrain", False)),
                )
            )
        if not pages:
            raise ValueError("model returned zero usable pages")
        return pages

    # ---------------------------------------------------------------- offline
    def _write_offline(
        self, brief: StoryBrief, idea: Dict[str, Any], characters: List[Dict[str, Any]]
    ) -> List[WrittenPage]:
        hero = next((c for c in characters if "explorer" in str(c.get("role", "")).lower()), None)
        friend = next((c for c in characters if c is not hero), None)
        name = (hero or {}).get("name") or idea.get("hero_name") or "The child"
        friend_name = (friend or {}).get("name") or "a small friend"
        place = self._place(idea)
        obj = self._object(idea)

        slots = {
            "name": name,
            "friend": friend_name,
            "place": place,
            "object": obj,
            "refrain": brief.refrain,
        }
        refrain_pages = self._refrain_pages(brief)

        pages: List[WrittenPage] = []
        for page_no in range(1, brief.page_count + 1):
            beat = self._beat_object_for_page(brief, page_no)
            variant = page_no % 2
            text = SCAFFOLD[beat.name]["text"][variant].format(**slots)
            scene = SCAFFOLD[beat.name]["scene"][variant].format(**slots)

            if page_no in refrain_pages:
                text = f"{text} {brief.refrain}"

            text = self._fit_budget(text, brief.words_per_page, beat.name, variant)
            pages.append(
                WrittenPage(page=page_no, text=text, scene=scene, beat=beat.name,
                            refrain=page_no in refrain_pages)
            )
        return pages

    def _refrain_pages(self, brief: StoryBrief) -> List[int]:
        """Refrain lands three times: inciting, dark moment, climax."""
        wanted = {"inciting", "dark_moment", "climax"}
        pages = [beat.pages[0] for beat in brief.beats if beat.name in wanted]
        while len(pages) < 3 and len(pages) < brief.page_count:
            pages.append(pages[-1] + 1 if pages else 1)
        return pages[:3]

    @staticmethod
    def _fit_budget(text: str, budget: tuple, beat: str, variant: int) -> str:
        """Keep every page inside the age-band word window (hard floor and ceiling)."""
        low, high = budget
        words = text.split()
        if len(words) > high:
            text = " ".join(words[:high]).rstrip(",;") + "."
            words = text.split()

        options = PADDING.get(beat, ["The light shifts, slow and gold."])
        attempt = 0
        while len(text.split()) < low and attempt < len(options) * 2:
            text = f"{text} {options[(variant + attempt) % len(options)]}"
            attempt += 1
        return text

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("**", "")).strip()

    @staticmethod
    def _place(idea: Dict[str, Any]) -> str:
        setting = str(idea.get("setting", "forest")).lower()
        for word in ("forest", "river", "castle", "valley", "village", "sea", "mountain"):
            if word in setting:
                return word
        return "forest"

    @staticmethod
    def _object(idea: Dict[str, Any]) -> str:
        text = f"{idea.get('world', '')} {idea.get('premise', '')}".lower()
        for word in ("lantern", "wish", "map", "key", "bell", "star", "seed"):
            if word in text:
                return word
        return "lantern"

    @staticmethod
    def _beat_for_page(brief: StoryBrief, page: int) -> str:
        for beat in brief.beats:
            if page in beat.pages:
                return beat.name
        return brief.beats[-1].name

    @staticmethod
    def _beat_object_for_page(brief: StoryBrief, page: int) -> Beat:
        for beat in brief.beats:
            if page in beat.pages:
                return beat
        return brief.beats[-1]
