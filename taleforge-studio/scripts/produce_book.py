"""Stage 5 — the written book becomes a print-ready product pack.

    python scripts/produce_book.py --book output/book.json
    python scripts/produce_book.py --book output/book.json --scenes output/scenes

Reads the manuscript produced by ``scripts/write_book.py`` (with its brief and editorial
report) and renders: interior PDF, wrap cover, metadata JSON and a final export zip.
Illustrations are attached automatically when ``--scenes`` holds ``page_XXX.png`` files.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.export_service import ExportService  # noqa: E402
from app.services.metadata_service import MetadataService  # noqa: E402
from app.services.render_service import RenderService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a written book into a product pack")
    parser.add_argument("--book", default="output/book.json")
    parser.add_argument("--scenes", help="folder with page_001.png … illustrations")
    parser.add_argument("--trim", default="US_6_X_9")
    parser.add_argument("--page-type", default="single", choices=["single", "spread", "full_bleed"])
    parser.add_argument("--price", type=float, default=12.99)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        book = json.loads(Path(args.book).read_text(encoding="utf-8"))
        pages = book["pages"]
        brief = book.get("brief", {})
        review = book.get("review", {})

        if review and not review.get("passed", True):
            print("REFUSED: the manuscript did not pass the editorial gate.")
            for error in review.get("errors", [])[:5]:
                print(f"  - p{error.get('page')}: {error.get('message')}")
            return 1

        out = Path(args.out or app.config["OUTPUT_DIR"])
        out.mkdir(parents=True, exist_ok=True)

        images: Optional[List[Optional[str]]] = None
        if args.scenes:
            folder = Path(args.scenes)
            images = []
            for page in pages:
                candidate = folder / f"page_{page['page']:03d}.png"
                images.append(str(candidate) if candidate.exists() else None)
            found = sum(1 for image in images if image)
            print(f"illustrations : {found}/{len(pages)} found in {folder}")

        renderer = RenderService(str(out))
        interior = renderer.render_story_pdf(
            [page["text"] for page in pages],
            output_name=f"{_slug(book.get('title', 'book'))}_interior.pdf",
            title=book.get("title", "Storybook"),
            trim_size=args.trim,
            page_images=images,
            page_types=[args.page_type] * len(pages),
            crop_marks=False,
        )

        subtitle = brief.get("logline", "")[:120] or "A story about courage"
        page_count = max(24, len(pages))
        metadata = MetadataService.create_metadata(
            product_id=f"story-{_slug(book.get('title', 'book'))}",
            title=book.get("title", "Storybook"),
            subtitle=subtitle,
            category="Picture Book",
            age_group=brief.get("age_band", "4-8"),
            language=book.get("language", "en"),
            price=args.price,
            page_count=page_count,
        )
        wrap = renderer.render_wrap_cover_pdf(
            title=book.get("title", "Storybook"),
            subtitle=subtitle,
            author=book.get("author", "TaleForge Studio"),
            back_blurb=metadata.listing_description,
            page_count=page_count,
            crop_marks=True,
        )
        meta_path = out / "book_metadata.json"
        meta_path.write_text(metadata.to_json(), encoding="utf-8")

        bundle = ExportService(str(out)).create_bundle(
            book.get("title", "Storybook"),
            [interior, wrap["path"], str(meta_path)],
            metadata=json.loads(meta_path.read_text(encoding="utf-8")),
        )

        print(f"interior      : {interior}")
        spine = wrap.get("spine_mm") or wrap.get("spine_width_mm") or "?"
        print(f"wrap cover    : {wrap['path']}  (spine {spine} mm)")
        print(f"metadata      : {meta_path}")
        print(f"bundle        : {bundle if isinstance(bundle, str) else bundle.get('path')}")
        print(f"pages         : {len(pages)} | editorial score: {review.get('score', 'n/a')}")
    return 0


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "_" for c in text]
    return "".join(keep).strip("_")[:60] or "book"


if __name__ == "__main__":
    raise SystemExit(main())
