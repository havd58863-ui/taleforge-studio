"""Stage 3 — turn each page into an engine-ready prompt (and optionally render it).

    python scripts/generate_scenes.py --book output/book.json --engine sdxl
    python scripts/generate_scenes.py --book output/book.json --generate      # needs IMAGE_PROVIDER

Writes output/scene_prompts.json so prompts are versioned with the manuscript, and
saves images to output/scenes/ when a provider is configured.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.image_engine_service import ImageEngineService  # noqa: E402
from app.services.image_prompt_compiler import ImagePromptCompiler  # noqa: E402
from app.services.page_layout_service import PageLayoutService  # noqa: E402
from app.services.prompt_service import PromptService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile scene prompts / render scenes")
    parser.add_argument("--book", default="output/book.json")
    parser.add_argument("--engine", default="sdxl", choices=["sdxl", "flux", "midjourney", "dalle3", "generic"])
    parser.add_argument("--trim", default="US_6_X_9")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--out", default="output/scene_prompts.json")
    args = parser.parse_args()

    create_app()
    book = json.loads(Path(args.book).read_text(encoding="utf-8"))
    brief = book.get("brief", {})
    style_bible = brief.get("style_bible", {})
    characters = [{"consistency_token": c} for c in []]

    layout = PageLayoutService.build_layout(trim_size=args.trim, page_type="full_bleed")
    compiler = ImagePromptCompiler()
    prompt_service = PromptService()
    engine = ImageEngineService()

    compiled = []
    for page in book["pages"]:
        recipe = prompt_service.build_prompt(book.get("title", "Scene"), page["scene"], args.trim)
        spec = compiler.compile(
            {
                "title": f"Page {page['page']}",
                "summary": page["scene"],
                "camera": recipe.camera,
                "lighting": recipe.lighting,
                "mood": recipe.mood,
                "palette": recipe.palette,
            },
            style_bible,
            characters,
            engine=args.engine,
            width_px=layout.page_px[0],
            height_px=layout.page_px[1],
        )
        entry = {"page": page["page"], "beat": page.get("beat"), "spec": spec.to_dict()}

        if args.generate and engine.available:
            result = engine.generate(
                spec.to_dict(), f"output/scenes/page_{page['page']:03d}.png", seed=1000 + page["page"]
            )
            entry["image"] = result.to_dict()

        compiled.append(entry)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"engine": args.engine, "page_px": layout.page_px, "items": compiled,
             "provider": engine.status()},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    print(f"pages compiled : {len(compiled)}")
    print(f"engine         : {args.engine} | page px: {layout.page_px}")
    print(f"provider ready : {engine.available} ({engine.provider or 'none'})")
    print(f"saved          : {out}")
    if not engine.available:
        print("note           : prompts saved; set IMAGE_PROVIDER to render them automatically")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
