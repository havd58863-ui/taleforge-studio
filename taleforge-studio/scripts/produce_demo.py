"""Produce a full demo product pack from the CLI (cover, interior, metadata, zip)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.export_service import ExportService  # noqa: E402
from app.services.metadata_service import MetadataService  # noqa: E402
from app.services.page_layout_service import PageLayoutService  # noqa: E402
from app.services.render_service import RenderService  # noqa: E402
from app.services.story_service import StoryService  # noqa: E402

app = create_app()

with app.app_context():
    out = Path(app.config["OUTPUT_DIR"])
    story = StoryService().seed_demo()

    scene_page_types = [(scene.page_type or "single") for scene in story.scenes] or ["single"]

    renderer = RenderService(str(out))
    cover = renderer.render_cover_pdf(story.title, "A story of courage and friendship", "TaleForge Studio")
    interior = renderer.render_story_pdf(
        [scene.summary or "" for scene in story.scenes],
        title=story.title,
        page_types=scene_page_types,
    )

    page_count = max(24, len(story.scenes) * 8)
    metadata = MetadataService.create_metadata(
        product_id=f"story-{story.id}",
        title=story.title,
        subtitle="A story of courage and friendship",
        category="Picture Book",
        age_group=f"{story.age_min}-{story.age_max}",
        language=story.language,
        price=12.99,
        page_count=page_count,
    )
    wrap = renderer.render_wrap_cover_pdf(
        title=story.title,
        subtitle="A story of courage and friendship",
        author="TaleForge Studio",
        back_blurb=metadata.listing_description,
        page_count=page_count,
        crop_marks=True,
    )
    meta_path = out / "metadata.json"
    meta_path.write_text(metadata.to_json(), encoding="utf-8")

    exporter = ExportService(str(out))
    bundle = exporter.create_bundle(
        story.title,
        [cover, wrap["path"], interior, str(meta_path)],
        metadata=json.loads(meta_path.read_text(encoding="utf-8")),
    )
    zip_path = exporter.zip_bundle(bundle)

    print("layouts: ", [PageLayoutService.build_layout(page_type=t).trim_size + "/" + t for t in scene_page_types])
    print("cover:   ", cover)
    print("wrap:    ", wrap["path"], "| spine", round(wrap["spec"]["spine_mm"], 2), "mm")
    print("interior:", interior)
    print("metadata:", meta_path)
    print("bundle:  ", bundle)
    print("zip:     ", zip_path)
