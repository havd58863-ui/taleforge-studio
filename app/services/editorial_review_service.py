"""Editorial review — the gate a page must pass before it is allowed into a book.

Two layers:

1. **Deterministic craft checks** (always on, no model needed): word budget per page,
   sentence ceiling, reading level (Flesch-Kincaid implemented here), long-word density,
   refrain discipline, dialogue ratio, sensory detail, banned content, beat coverage,
   repeated sentence openers, scene-description presence.
2. **LLM critique** (optional, when ``LLM_*`` is configured): a senior-editor pass that
   returns craft notes — not a replacement for the deterministic gate.

Every failure is reported as ``error`` (blocks the book) or ``warning`` (fix if possible).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.llm_client import LLMClient, LLMError, get_llm
from app.services.story_director_service import StoryBrief

# Banned words are language-specific: applying the English list to German flags every
# "die" (the article), which is exactly the kind of false positive that destroys trust.
BANNED_BY_LANGUAGE: Dict[str, set] = {
    "en": {
        "kill", "killed", "killing", "die", "died", "death", "dead", "blood", "bloody",
        "gun", "knife", "weapon", "hate", "hated", "stupid", "idiot", "ugly", "shut up",
    },
    "de": {
        "töten", "getötet", "tot", "tote", "tod", "blut", "blutig", "messer", "waffe",
        "gewehr", "hassen", "hasst", "dumm", "idiot", "hässlich", "schweig",
    },
    "es": {
        "matar", "mató", "mataron", "muerto", "muerta", "muerte", "sangre", "arma",
        "pistola", "cuchillo", "odio", "odiar", "estúpido", "idiota", "feo", "cállate",
    },
}

SENSORY_BY_LANGUAGE: Dict[str, set] = {
    "de": {
        "warm", "kalt", "weich", "rau", "summt", "summen", "geruch", "riecht", "riechen",
        "süß", "salzig", "hell", "dunkel", "flüstern", "flüstert", "klingelt", "glüht",
        "leuchtet", "licht", "moos", "harz", "brot", "regen", "feucht", "brise", "atem",
    },
    "es": {
        "cálido", "tibio", "frío", "suave", "áspero", "zumba", "zumbido", "olor", "huele",
        "oler", "sabor", "dulce", "salado", "brillante", "oscuro", "susurra", "suena",
        "brilla", "brillo", "luz", "musgo", "resina", "pan", "lluvia", "húmedo", "brisa",
    },
}

BANNED = {
    "kill", "killed", "killing", "die", "died", "death", "dead", "blood", "bloody",
    "gun", "knife", "weapon", "hate", "hated", "stupid", "idiot", "ugly", "shut up",
}

SENSORY = {
    "warm", "cold", "soft", "rough", "hum", "hummed", "smell", "smelled", "scent",
    "taste", "salty", "sweet", "bright", "dark", "whisper", "whispered", "ring",
    "rang", "glow", "glowed", "flicker", "flickered", "breeze", "damp", "sticky",
}

VOWELS = "aeiouy"


def _syllables(word: str) -> int:
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    count, previous_vowel = 0, False
    for char in word:
        is_vowel = char in VOWELS
        if is_vowel and not previous_vowel:
            count += 1
        previous_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def flesch_kincaid_grade(text: str) -> float:
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    words = re.findall(r"[A-Za-z']+", text)
    if not words:
        return 0.0
    syllables = sum(_syllables(w) for w in words)
    return round(0.39 * (len(words) / sentences) + 11.8 * (syllables / len(words)) - 15.59, 2)


@dataclass
class Finding:
    code: str
    severity: str  # error | warning
    message: str
    page: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "severity": self.severity, "message": self.message, "page": self.page}


@dataclass
class ReviewReport:
    score: float
    passed: bool
    findings: List[Finding] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    craft_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "errors": [f.to_dict() for f in self.findings if f.severity == "error"],
            "warnings": [f.to_dict() for f in self.findings if f.severity == "warning"],
            "metrics": self.metrics,
            "craft_notes": self.craft_notes,
        }


class EditorialReviewService:
    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self.llm = llm or get_llm()

    # ------------------------------------------------------------------ public
    def review(
        self,
        pages: List[Dict[str, Any]],
        brief: StoryBrief,
        use_llm: bool = False,
    ) -> ReviewReport:
        findings: List[Finding] = []
        metrics: Dict[str, Any] = {}

        low, high = brief.words_per_page
        banned_words = BANNED_BY_LANGUAGE.get(brief.language, BANNED)
        sensory_words = SENSORY_BY_LANGUAGE.get(brief.language, SENSORY) if brief.language != "en" else SENSORY
        max_sentences = int(brief.style_bible.get("max_sentences_per_page", 4))

        total_words = 0
        refrain_hits: List[str] = []
        dialogue_pages = 0
        sensory_pages = 0
        openers: Dict[str, int] = {}

        for item in pages:
            page = int(item.get("page", 0))
            text = str(item.get("text", "")).strip()
            scene = str(item.get("scene", "")).strip()
            words = text.split()
            total_words += len(words)

            if not text:
                findings.append(Finding("empty_page", "error", "page has no text", page))
                continue

            if not (low <= len(words) <= high):
                findings.append(
                    Finding("word_budget", "error",
                            f"{len(words)} words; target {low}-{high} for the {brief.age_band} band", page)
                )

            sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
            if len(sentences) > max_sentences:
                findings.append(
                    Finding("sentence_count", "error",
                            f"{len(sentences)} sentences; max {max_sentences} at this age", page)
                )

            average_sentence = len(words) / max(1, len(sentences))
            if average_sentence > 14:
                findings.append(
                    Finding("sentence_length", "warning",
                            f"average sentence is {average_sentence:.1f} words — hard to read aloud", page)
                )

            lowered = text.lower()
            tokens = set(re.findall(r"[a-zà-ÿäöüß']+", lowered))
            banned = sorted({
                w for w in re.findall(r"[a-zà-ÿäöüß']+", lowered)
                if w in banned_words or any(
                    re.search(rf"\b{re.escape(b)}\b", w) for b in banned_words
                )
            } | (tokens & banned_words))
            if banned:
                findings.append(
                    Finding("unsafe_content", "error", f"unacceptable words: {', '.join(banned)}", page)
                )

            if "?" in text:
                pass
            if '"' in text or "\u201c" in text:
                dialogue_pages += 1

            if any(word in lowered for word in sensory_words):
                sensory_pages += 1
            else:
                findings.append(
                    Finding("no_sensory_detail", "warning", "no concrete sensory detail on this page", page)
                )

            if not scene or len(scene.split()) < 5:
                findings.append(
                    Finding("weak_scene", "error", "scene description missing or too thin for the illustrator", page)
                )

            if brief.refrain.lower() in lowered:
                refrain_hits.append(page)

            first_word = (words[0].lower().strip(",.") if words else "")
            openers[first_word] = openers.get(first_word, 0) + 1

        # ---- book-level checks
        budget_low = int(brief.total_word_budget * 0.8)
        budget_high = int(brief.total_word_budget * 1.2)
        if not (budget_low <= total_words <= budget_high):
            findings.append(
                Finding("total_budget", "warning",
                        f"{total_words} words total; brief expected {budget_low}-{budget_high}")
            )

        if len(refrain_hits) != 3:
            findings.append(
                Finding("refrain_count", "error",
                        f"refrain appears {len(refrain_hits)} times; the brief requires exactly 3")
            )

        all_text = " ".join(str(p.get("text", "")) for p in pages)
        grade = flesch_kincaid_grade(all_text)
        target_grade = {"0-3": 1.0, "3-5": 2.0, "4-8": 3.5, "6-9": 5.0, "8-12": 6.5}.get(brief.age_band, 4.0)
        # Flesch-Kincaid is calibrated on English. For German/Spanish the number is an
        # indicator, never a verdict — a native read-aloud check is the real gate.
        severity = "error" if brief.language == "en" else "warning"
        suffix = "" if brief.language == "en" else " (approximate: FK is English-calibrated)"
        if grade > target_grade + 1.5:
            findings.append(
                Finding("reading_level", severity,
                        f"Flesch-Kincaid grade {grade} vs target {target_grade} for {brief.age_band}{suffix}")
            )
        elif grade > target_grade:
            findings.append(
                Finding("reading_level", "warning",
                        f"grade {grade} is slightly above target {target_grade}{suffix}")
            )

        long_words = [w for w in re.findall(r"[A-Za-z']+", all_text) if len(w) >= 9]
        long_ratio = len(long_words) / max(1, len(re.findall(r"[A-Za-z']+", all_text)))
        if long_ratio > 0.12:
            findings.append(
                Finding("vocabulary", "warning", f"{long_ratio:.0%} long words — simplify for this age")
            )

        if pages and dialogue_pages / len(pages) > 0.4:
            findings.append(
                Finding("dialogue_ratio", "warning",
                        f"dialogue on {dialogue_pages}/{len(pages)} pages; keep it under 40%")
            )

        if pages and sensory_pages / len(pages) < 0.6:
            findings.append(
                Finding("sensory_coverage", "warning",
                        f"sensory detail on {sensory_pages}/{len(pages)} pages — aim for most pages")
            )

        covered = {str(p.get("beat", "")) for p in pages}
        missing = [beat.name for beat in brief.beats if beat.name not in covered]
        if missing:
            findings.append(
                Finding("arc_incomplete", "error", f"beats with no page: {', '.join(missing)}")
            )

        if openers:
            top_word, top_count = max(openers.items(), key=lambda kv: kv[1])
            if top_count > max(2, len(pages) * 0.35):
                findings.append(
                    Finding("repetitive_openers", "warning",
                            f"{top_count} pages start with '{top_word}' — vary sentence openings")
                )

        metrics.update(
            {
                "pages": len(pages),
                "total_words": total_words,
                "average_words_per_page": round(total_words / max(1, len(pages)), 1),
                "reading_grade": grade,
                "target_grade": target_grade,
                "reading_grade_language": brief.language,
                "refrain_pages": refrain_hits,
                "sensory_pages": sensory_pages,
                "dialogue_pages": dialogue_pages,
            }
        )

        if brief.language != "en":
            metrics["reading_grade_note"] = (
                f"Flesch-Kincaid is calibrated for English; the value is an approximation for "
                f"{brief.language}. A native-speaker read-aloud check is still required."
            )

        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        score = max(0.0, 100.0 - errors * 9.0 - warnings * 2.5)

        craft_notes: List[str] = []
        if use_llm and self.llm.available:
            try:
                craft_notes = self._llm_critique(pages, brief)
            except LLMError:
                craft_notes = ["LLM critique unavailable; deterministic checks only"]

        return ReviewReport(
            score=score,
            passed=errors == 0,
            findings=findings,
            metrics=metrics,
            craft_notes=craft_notes,
        )

    # -------------------------------------------------------------------- LLM
    def _llm_critique(self, pages: List[Dict[str, Any]], brief: StoryBrief) -> List[str]:
        body = "\n".join(f"p{p['page']} [{p.get('beat')}]: {p['text']}" for p in pages)
        system = (
            "You are a senior children's-book editor. You give short, specific, actionable notes. "
            "You never rewrite the whole book."
        )
        user = (
            f"Age band {brief.age_band}. Refrain: \"{brief.refrain}\".\nManuscript:\n{body}\n\n"
            'Return JSON: {"craft_notes":["..."],"strengths":["..."]} — at most 6 craft notes, '
            "each tied to a page number, each about rhythm, imagery, page-turn hooks or show-don't-tell."
        )
        payload = self.llm.complete(system, user, temperature=0.4, json_mode=True, max_tokens=900).json() or {}
        notes = payload.get("craft_notes", []) if isinstance(payload, dict) else []
        return [str(n) for n in notes][:6]
