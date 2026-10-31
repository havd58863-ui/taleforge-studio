"""Original multilingual story variants (authored, not machine-dumped)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from app.services.language_policy import enabled_languages, language_name

SUPPORTED_LANGUAGES = {
    "en": "English",
    "ar": "العربية",
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
}

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "en": {
        "title": "Luna and the Lantern Forest",
        "summary": "A story about courage, empathy and belonging in a magical forest.",
        "paragraphs": [
            "In the early morning light, a little child stepped into a forest that whispered with secrets.",
            "She carried a small lantern and a brave heart, even though she felt afraid.",
            "At the edge of the forest she discovered the truth: courage is not the absence of fear, but choosing to help anyway.",
        ],
        "tone": "warm",
    },
    "ar": {
        "title": "لونا وغابة الفوانيس",
        "summary": "قصة عن الشجاعة والرحمة والانتماء في غابة سحرية.",
        "paragraphs": [
            "في ضوء الصباح الباكر، دخلت طفلة صغيرة غابةً تهمس بالأسرار.",
            "كانت تحمل فانوسًا صغيرًا وقلبًا شجاعًا، رغم أنها كانت خائفة.",
            "وعند طرف الغابة اكتشفت الحقيقة: الشجاعة ليست غياب الخوف، بل اختيار المساعدة رغم الخوف.",
        ],
        "tone": "دافئ",
    },
    "fr": {
        "title": "Luna et la Forêt des Lanternes",
        "summary": "Une histoire de courage, d'empathie et d'appartenance dans une forêt magique.",
        "paragraphs": [
            "Au matin, une petite fille entra dans une forêt qui murmurait des secrets.",
            "Elle portait une petite lanterne et un cœur courageux, même si elle avait peur.",
            "Au bord de la forêt, elle comprit la vérité : le courage n'est pas l'absence de peur, mais le choix d'aider malgré la peur.",
        ],
        "tone": "chaleureux",
    },
    "es": {
        "title": "Luna y el Bosque de las Linternas",
        "summary": "Una historia sobre el valor, la empatía y la pertenencia en un bosque mágico.",
        "paragraphs": [
            "Con la luz del amanecer, una niña entró en un bosque que susurraba secretos.",
            "Llevaba una pequeña linterna y un corazón valiente, aunque tenía miedo.",
            "Al borde del bosque descubrió la verdad: el valor no es la ausencia del miedo, sino elegir ayudar a pesar de él.",
        ],
        "tone": "cálido",
    },
    "de": {
        "title": "Luna und der Wald der Laternen",
        "summary": "Eine Geschichte über Mut, Mitgefühl und Zugehörigkeit in einem magischen Wald.",
        "paragraphs": [
            "Im frühen Morgenlicht betrat ein kleines Mädchen einen Wald, der Geheimnisse flüsterte.",
            "Sie trug eine kleine Laterne und ein mutiges Herz, obwohl sie Angst hatte.",
            "Am Waldrand entdeckte sie die Wahrheit: Mut bedeutet nicht, keine Angst zu haben, sondern trotzdem zu helfen.",
        ],
        "tone": "warm",
    },
}


@dataclass
class StoryVariant:
    language: str
    language_name: str
    title: str
    summary: str
    paragraphs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultilingualStoryService:
    @staticmethod
    def build_multilingual_versions(
        base_story: Dict[str, Any] | None = None,
        languages: List[str] | None = None,
    ) -> List[StoryVariant]:
        base_story = base_story or {}
        languages = languages or enabled_languages()

        variants: List[StoryVariant] = []
        for code in languages:
            code = code.lower()
            template = TEMPLATES.get(code)
            if template is None:
                continue
            variants.append(
                StoryVariant(
                    language=code,
                    language_name=SUPPORTED_LANGUAGES.get(code, code),
                    title=base_story.get("title") if code == "en" and base_story.get("title") else template["title"],
                    summary=template["summary"],
                    paragraphs=list(template["paragraphs"]),
                    metadata={
                        "tone": template["tone"],
                        "target_age": base_story.get("age_group", "4-8"),
                        "direction": "rtl" if code == "ar" else "ltr",
                    },
                )
            )
        return variants

    @staticmethod
    def supported_languages() -> Dict[str, str]:
        """Enabled languages only — the product scope, not every pack in the codebase."""
        return {code: SUPPORTED_LANGUAGES.get(code, language_name(code)) for code in enabled_languages()}
