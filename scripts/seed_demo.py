"""Seed the demo story, products and vector index."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.story_service import StoryService  # noqa: E402
from app.services.vector_service import VectorService, seed_story_documents  # noqa: E402

app = create_app()

with app.app_context():
    story = StoryService().seed_demo()
    indexed = seed_story_documents()
    print(f"Story: {story.title} (id={story.id})")
    print(f"Characters: {len(story.characters)} | Scenes: {len(story.scenes)}")
    print(f"Indexed documents: {indexed} | backend: {VectorService().backend}")
