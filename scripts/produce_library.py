"""Build the complete library: picture book + coloring book + digital + listings.

    python scripts/produce_library.py                       # all five editions
    python scripts/produce_library.py --only en de          # a subset
    python scripts/produce_library.py --only en-de --no-art  # fast, flat backgrounds

Every edition is a 32-page trade picture book (24 story pages + front/back matter),
with the art bleeding to the page edge and text kept inside the safe area. Each story page
may be a single page or half of a double-page spread — decided by the book structure
service, not by chance.

Output per edition (output/library/<slug>/):
    picture book PDF · coloring book PDF (+ SVG vector pages) · wrap cover PDF
    EPUB · metadata.json · KDP listing · Etsy listing · bundle zip
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.content.library_texts import REFRAIN, STORY, SUBTITLES, TITLES  # noqa: E402
from app.services.amazon_kdp_service import AmazonKDPService  # noqa: E402
from app.services.bilingual_service import BilingualService  # noqa: E402
from app.services.book_structure_service import BookStructureService  # noqa: E402
from app.services.ebook_service import EbookService  # noqa: E402
from app.services.editorial_review_service import EditorialReviewService  # noqa: E402
from app.services.etsy_service import EtsyService  # noqa: E402
from app.services.export_service import ExportService  # noqa: E402
from app.services.line_art_service import LineArtService  # noqa: E402
from app.services.metadata_service import MetadataService  # noqa: E402
from app.services.placeholder_art_service import PlaceholderArtService  # noqa: E402
from app.services.render_service import RenderService  # noqa: E402
from app.services.story_director_service import StoryDirectorService  # noqa: E402

AUTHOR = "TaleForge Studio"
TRIM = "US_6_X_9"
COLOR_TRIM = "US_8_5_X_8_5"
PAGE_PX = (1871, 2771)          # 6x9 in + 3 mm bleed at 300 dpi
SPREAD_PX = (3742, 2771)
IDEA = {
    "title": "Luna and the Lantern Forest",
    "setting": "A forest of lanterns at dusk",
    "world": "A forest where every path is lit by a shared lantern",
    "central_conflict": "Luna must give her own light to fill a dark lantern",
    "lesson_value": "Courage is choosing to share",
    "genre": "fantasy",
}
EDITIONS: Dict[str, Dict[str, Any]] = {
    "en":    {"primary": "en", "secondary": None, "price": 9.99, "digital": 3.99},
    "de":    {"primary": "de", "secondary": None, "price": 9.99, "digital": 3.99},
    "es":    {"primary": "es", "secondary": None, "price": 9.99, "digital": 3.99},
    "en-de": {"primary": "en", "secondary": "de", "price": 12.99, "digital": 4.99},
    "es-en": {"primary": "es", "secondary": "en", "price": 12.99, "digital": 4.99},
}


def gate(code: str) -> Dict[str, Any]:
    director = StoryDirectorService()
    brief = director.build_brief(IDEA, 3, 8, page_count=len(STORY[code]), language=code,
                                 refrain=REFRAIN[code])
    beats = [beat.name for beat in brief.beats for _ in beat.pages]
    pages = [
        {"page": i + 1, "text": text, "scene": text, "beat": beats[i],
         "refrain": REFRAIN[code] in text}
        for i, text in enumerate(STORY[code])
    ]
    return {"brief": brief, "beats": beats, "report": EditorialReviewService().review(pages, brief)}


# Art and line art depend on the scene, not on the language: build once, reuse everywhere.
_ART_CACHE: Dict[str, str] = {}
_LINE_CACHE: Dict[str, Dict[str, Any]] = {}


def _cached_art(art_service: PlaceholderArtService, scene: str, size_px, path: str) -> str:
    key = f"{size_px[0]}x{size_px[1]}:{scene[:80]}"
    if key not in _ART_CACHE:
        _ART_CACHE[key] = art_service.make_scene_art(scene, size_px, path)["path"]
    return _ART_CACHE[key]


def _cached_line(line_service: LineArtService, image: str, base: Path) -> Dict[str, Any]:
    if image not in _LINE_CACHE:
        line = line_service.to_line_art(image, str(base / f"{Path(image).stem}_line.png"),
                                        thickness=4, detail=0.55)
        vector = line_service.vectorize(line.path, str(base / f"{Path(image).stem}_line.svg"))
        printed = line_service.prepare_for_print(line.path, str(base / f"{Path(image).stem}_print.png"))
        _LINE_CACHE[image] = {"print": printed["path"], "svg": vector["path"],
                              "vectorized": vector["vectorized"]}
    return _LINE_CACHE[image]


def build_market(dataset_dir: str):
    """SEO from real market data, for the real title of each edition (data-first default)."""
    try:
        from app.services.market_research_service import MarketResearchService
        from app.services.niche_service import NicheService

        market = MarketResearchService(dataset_dir)
        index = market.build_index()
        if index.basis != "dataset" or index.items == 0:
            print("  market: no dataset — keywords fall back to the built-in rules "
                  "(run: python scripts/market_brief.py --fetch auto)")
            return None
        print("  market: %s titles analysed (%s)" % (index.items, ", ".join(index.sources[:2])))
        return NicheService(dataset_dir, market)
    except Exception as exc:
        print(f"  market: unavailable ({type(exc).__name__}) — using built-in keyword rules")
        return None


def build_edition(name: str, out_root: Path, art_service: PlaceholderArtService,
                  line_service: LineArtService, with_art: bool, force: bool,
                  market: Optional[Any] = None) -> Dict[str, Any]:
    spec = EDITIONS[name]
    primary, secondary = spec["primary"], spec["secondary"]
    gates = {code: gate(code) for code in {primary, secondary or primary}}
    failures = {code: g["report"].passed for code, g in gates.items()}
    if not all(failures.values()) and not force:
        return {"edition": name, "skipped": True,
                "errors": {c: [f.message for f in g["report"].findings if f.severity == "error"][:4]
                           for c, g in gates.items()}}

    folder = out_root / f"luna-{name}"
    folder.mkdir(parents=True, exist_ok=True)
    art_dir = folder / "art"
    line_dir = folder / "line_art"

    structure = BookStructureService().build(
        title=TITLES[primary],
        story=STORY[primary],
        language=primary,
        subtitle=SUBTITLES[primary],
        author=AUTHOR,
        story_secondary=STORY[secondary] if secondary else None,
        language_secondary=secondary or "",
        beats=gates[primary]["beats"],
    )

    images: List[Optional[str]] = []
    coloring_pages: List[Dict[str, Any]] = []
    last_wide: Optional[str] = None

    for page in structure.pages:
        if page.kind != "story":
            images.append(None)
            continue

        if with_art:
            if page.spread == "left":
                last_wide = _cached_art(art_service, page.scene, SPREAD_PX, str(art_dir / f"wide_{page.page}.png"))
                image = last_wide
            elif page.spread == "right":
                image = last_wide
            else:
                image = _cached_art(art_service, page.scene, PAGE_PX, str(art_dir / f"p{page.page:02d}.png"))
        else:
            image = None
        images.append(image)

        if image:
            line = _cached_line(line_service, image, line_dir)
            coloring_pages.append({"page": page.page, "image": line["print"],
                                   "svg": line["svg"], "vectorized": line["vectorized"]})

    renderer = RenderService(str(folder))
    picture_book = renderer.render_picture_book_pdf(
        [page.to_dict() for page in structure.pages],
        output_name=f"luna_{name}_picture_book.pdf",
        title=TITLES[primary],
        trim_size=TRIM,
        page_images=images,
    )
    coloring_pdf = renderer.render_coloring_book_pdf(
        [{"kind": "title", "text": SUBTITLES[primary]}] + coloring_pages,
        output_name=f"luna_{name}_coloring_book.pdf",
        title=f"{TITLES[primary]} — Coloring Book",
        trim_size=COLOR_TRIM,
    )

    digital_title = TITLES[primary] if not secondary else f"{TITLES[primary]} / {TITLES[secondary]}"
    paragraphs: List[str] = []
    for page in structure.pages:
        if page.kind == "story":
            paragraphs.append(page.text)
            if page.text_secondary:
                paragraphs.append(page.text_secondary)
    epub = EbookService.create_epub(digital_title, paragraphs, str(folder / f"luna_{name}.epub"),
                                    author=AUTHOR, language=primary)

    cover = renderer.render_wrap_cover_pdf(
        title=digital_title,
        subtitle=SUBTITLES[primary],
        author=AUTHOR,
        back_blurb=(f"{digital_title}. {SUBTITLES[primary]}. 32 pages, 6x9 in, 300 dpi, "
                    "full-bleed colour interior."),
        page_count=32,
        crop_marks=True,
        output_name=f"luna_{name}_cover_wrap.pdf",
    )

    metadata = MetadataService.create_metadata(
        product_id=f"luna-{name}", title=digital_title,
        subtitle=SUBTITLES[primary], category="Picture Book",
        age_group="3-8", language=primary, price=spec["price"], page_count=32,
        keywords=(market.keywords(digital_title)["kdp"] if (market and primary == "en") else None),
    )
    meta_path = folder / "metadata.json"
    meta_path.write_text(metadata.to_json(), encoding="utf-8")

    kdp_listing = AmazonKDPService.build_listing({
        "title": digital_title, "subtitle": SUBTITLES[primary],
        "description": metadata.listing_description, "keywords": metadata.seo_keywords,
        "language": primary, "price": spec["price"], "page_count": 32,
        "trim_size": "6x9", "age_range": "3-8",
    })
    kdp = kdp_listing.to_dict() if hasattr(kdp_listing, "to_dict") else vars(kdp_listing)
    (folder / "kdp_listing.json").write_text(json.dumps(kdp, ensure_ascii=False, indent=2), encoding="utf-8")

    etsy_listing = EtsyService.build_listing({
        "title": f"{digital_title} — printable picture book PDF",
        "description": metadata.listing_description,
        "tags": metadata.seo_keywords, "price": spec["digital"],
    })
    etsy = etsy_listing.to_dict() if hasattr(etsy_listing, "to_dict") else vars(etsy_listing)
    (folder / "etsy_listing.json").write_text(json.dumps(etsy, ensure_ascii=False, indent=2), encoding="utf-8")

    bundle = ExportService(str(folder)).create_bundle(
        f"luna_{name}", [picture_book, coloring_pdf, cover["path"], epub, str(meta_path)],
        metadata=json.loads(meta_path.read_text(encoding="utf-8")),
    )

    return {
        "edition": name,
        "languages": [primary] + ([secondary] if secondary else []),
        "title": digital_title,
        "pages": structure.page_count,
        "spreads": structure.spread_pairs,
        "spread_count": len(structure.spread_pairs),
        "editorial_score": round(sum(g["report"].score for g in gates.values()) / len(gates), 2),
        "gates_passed": all(failures.values()),
        "picture_book": picture_book,
        "coloring_book": coloring_pdf,
        "coloring_pages": len(coloring_pages),
        "vectorized_pages": sum(1 for page in coloring_pages if page.get("vectorized")),
        "cover": cover["path"],
        "epub": epub,
        "metadata": str(meta_path),
        "kdp": str(folder / "kdp_listing.json"),
        "etsy": str(folder / "etsy_listing.json"),
        "bundle": bundle,
        "folder": str(folder),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Produce the full library")
    parser.add_argument("--only", nargs="*", choices=list(EDITIONS), help="editions to build")
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-art", action="store_true", help="skip illustrations (fast dry run)")
    parser.add_argument("--force", action="store_true", help="publish even if the editorial gate fails")
    parser.add_argument("--no-market", action="store_true",
                        help="ignore the market brief (default: use its keywords when present)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        out_root = Path(args.out or (Path(app.config["OUTPUT_DIR"]) / "library"))
        out_root.mkdir(parents=True, exist_ok=True)
        art_service, line_service = PlaceholderArtService(), LineArtService()
        market = None if args.no_market else build_market(
            app.config.get("KAGGLE_DATASET_PATH", "./secure_data/datasets"))

        wanted = args.only or list(EDITIONS)
        results = []
        for name in wanted:
            started = time.time()
            print(f"\n=== {name} ===")
            result = build_edition(name, out_root, art_service, line_service, not args.no_art,
                                   args.force, market)
            result["seconds"] = round(time.time() - started, 1)
            results.append(result)
            if result.get("skipped"):
                print(f"  SKIPPED: {result['errors']}")
            else:
                print(f"  {result['pages']} pages | {result['spread_count']} spreads | "
                      f"coloring {result['coloring_pages']} pages ({result['vectorized_pages']} SVG) | "
                      f"gate {result['editorial_score']} | {result['seconds']}s")

        index = {
            "story": IDEA["title"],
            "languages": ["en", "de", "es"],
            "author": AUTHOR,
            "editions": results,
            "available": {
                "picture_book_pages": 32,
                "story_pages": 24,
                "front_matter": ["half-title", "title page", "copyright", "dedication"],
                "back_matter": ["the end", "about the author", "series page", "colophon"],
                "trim": TRIM,
                "coloring_trim": COLOR_TRIM,
            },
        }
        (out_root / "library_index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        built = [r for r in results if not r.get("skipped")]
        print(f"\nlibrary: {len(built)} editions built, {len(results) - len(built)} skipped")
        print(f"index  : {out_root / 'library_index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
