"""Story, character and scene persistence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.extensions import db
from app.models import Character, Product, Scene, Story
from app.services.prompt_service import PromptService


@dataclass
class StoryIdea:
    title: str
    premise: str
    genre: str
    setting: str
    age_min: int = 4
    age_max: int = 8
    language: str = "en"


class StoryService:
    def __init__(self) -> None:
        self.prompts = PromptService()

    # ---------- creation ----------
    def create_story(self, idea: StoryIdea) -> Story:
        story = Story(
            title=idea.title,
            premise=idea.premise,
            genre=idea.genre,
            setting=idea.setting,
            age_min=idea.age_min,
            age_max=idea.age_max,
            language=idea.language,
        )
        db.session.add(story)
        db.session.commit()
        return story

    def add_character(
        self,
        story_id: int,
        name: str,
        role: str,
        personality: str,
        visual_summary: str,
        values: str = "kindness, courage",
        flaws: str = "self-doubt",
        strengths: str = "empathy, bravery",
        emotional_arc: str = "fear to confidence",
        age: Optional[int] = None,
    ) -> Character:
        character = Character(
            story_id=story_id,
            name=name,
            role=role,
            age=age,
            personality=personality,
            visual_summary=visual_summary,
            values=values,
            flaws=flaws,
            strengths=strengths,
            emotional_arc=emotional_arc,
            # Stable token keeps the character visually consistent between scenes.
            consistency_token=f"[{name.lower().replace(' ', '_')}_ref: {visual_summary}]",
        )
        db.session.add(character)
        db.session.commit()
        return character

    def add_scene(
        self,
        story_id: int,
        title: str,
        summary: str,
        page_type: Optional[str] = None,
        camera_angle: Optional[str] = None,
    ) -> Scene:
        recipe = self.prompts.build_prompt(title, summary)

        scene = Scene(
            story_id=story_id,
            number=(Scene.query.filter_by(story_id=story_id).count() + 1),
            title=title,
            summary=summary,
            page_type=page_type or recipe.page_type,
            camera_angle=camera_angle or recipe.camera,
            mood=recipe.mood,
            lighting=recipe.lighting,
            palette=", ".join(recipe.palette),
            prompt=recipe.prompt,
            negative_prompt=recipe.negative_prompt,
            print_ready=True,
        )
        db.session.add(scene)
        db.session.commit()
        return scene

    # ---------- demo seeding ----------
    def seed_demo(self) -> Story:
        existing = Story.query.first()
        if existing:
            return existing

        story = self.create_story(
            StoryIdea(
                title="Luna and the Lantern Forest",
                premise="A child learns that courage is choosing kindness even when she is afraid.",
                genre="fantasy",
                setting="Whispering forest at dawn",
                age_min=4,
                age_max=8,
                language="en",
            )
        )

        self.add_character(
            story.id,
            "Luna",
            "young explorer",
            "gentle, brave, curious",
            "soft oval face, curly brown hair, forest green dress, small brass lantern",
        )
        self.add_character(
            story.id,
            "Pip",
            "lantern spirit companion",
            "playful, loyal, easily distracted",
            "palm-sized glowing creature, amber light, translucent wings",
        )

        self.add_scene(
            story.id,
            "Whispering Forest",
            "Luna enters the magical forest at sunrise carrying a glowing lantern; wide cinematic shot.",
        )
        self.add_scene(
            story.id,
            "Hidden Bridge",
            "Luna meets Pip across a stone bridge under soft moonlight; close, warm grouping.",
        )
        self.add_scene(
            story.id,
            "The Lantern Bloom",
            "The forest lanterns bloom like tiny stars and reveal the path home; full page finale.",
        )

        demo_products = [
            dict(
                title="Luna and the Lantern Forest",
                subtitle="A story of courage and friendship",
                category="Picture Book",
                age_group="4-8",
                language="en",
                format_type="paperback",
                page_count=32,
                price=12.99,
            ),
            dict(
                title="Luna and the Lantern Forest — Coloring Book",
                subtitle="32 original coloring pages",
                category="Coloring Book",
                age_group="4-8",
                language="en",
                format_type="coloring",
                page_count=32,
                price=8.99,
            ),
            dict(
                title="Luna et la Forêt des Lanternes",
                subtitle="Une histoire de courage et d'amitié",
                category="Picture Book",
                age_group="4-8",
                language="fr",
                format_type="ebook",
                page_count=32,
                price=6.99,
            ),
        ]
        for payload in demo_products:
            db.session.add(Product(story_id=story.id, **payload))
        db.session.commit()
        return story

    # ---------- queries ----------
    @staticmethod
    def story_outline(story_id: int) -> dict:
        story = Story.query.get_or_404(story_id)
        return {
            "story": story.to_dict(),
            "characters": [c.to_dict() for c in story.characters],
            "scenes": [s.to_dict() for s in story.scenes],
        }

    @staticmethod
    def list_stories() -> List[Story]:
        return Story.query.order_by(Story.created_at.desc()).all()
