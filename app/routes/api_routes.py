"""JSON API for the production pipeline."""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db, redis_healthy
from app.models import Product, Story
from app.services.amazon_kdp_service import AmazonKDPService
from app.services.bilingual_service import BilingualService
from app.services.coloring_service import ColoringService
from app.services.ebook_service import EbookService
from app.services.etsy_service import EtsyService
from app.services.export_service import ExportService
from app.services.idea_service import IdeaService
from app.services.image_fit_service import ImageFitService
from app.services.kaggle_service import KaggleService
from app.services.metadata_service import MetadataService
from app.services.page_layout_service import PageLayoutService
from app.services.multilingual_story_service import MultilingualStoryService
from app.services.print_bundle_service import PrintBundleService
from app.services.prompt_service import PromptService
from app.services.text_layout_service import TextLayoutService, TextStyle
from app.services.editorial_review_service import EditorialReviewService
from app.services.image_engine_service import ImageEngineService
from app.services.image_prompt_compiler import ImagePromptCompiler
from app.services.llm_client import get_llm
from app.services import language_policy
from app.services.market_research_service import MarketResearchService
from app.services.print_image_service import PrintImageService
from app.services.series_service import SeriesService
from app.services.story_director_service import StoryDirectorService
from app.services.story_writer_service import StoryWriterService
from app.services.quality_service import QualityService
from app.services.render_service import RenderService
from app.services.story_service import StoryIdea, StoryService
from app.services.vector_service import VectorService, seed_story_documents

api_bp = Blueprint("api", __name__)


def _payload() -> dict:
    return request.get_json(force=True, silent=True) or {}


def _out_dir() -> Path:
    path = Path(current_app.config["OUTPUT_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------- health ----------
@api_bp.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": current_app.config["APP_NAME"],
            "env": current_app.config["APP_ENV"],
            "redis": redis_healthy(),
        }
    )


# ---------- ideas ----------
@api_bp.route("/ideas", methods=["GET"])
def ideas():
    service = IdeaService()
    return jsonify({"items": service.ranked_candidates()})


# ---------- stories ----------
@api_bp.route("/stories", methods=["GET"])
def stories():
    items = [s.to_dict() for s in Story.query.order_by(Story.created_at.desc()).all()]
    return jsonify({"items": items})


@api_bp.route("/stories", methods=["POST"])
def create_story():
    payload = _payload()
    if not payload.get("title"):
        return jsonify({"error": "title_required"}), 400
    story = StoryService().create_story(
        StoryIdea(
            title=payload["title"],
            premise=payload.get("premise", ""),
            genre=payload.get("genre", "fantasy"),
            setting=payload.get("setting", ""),
            age_min=int(payload.get("age_min", 4)),
            age_max=int(payload.get("age_max", 8)),
            language=payload.get("language", "en"),
        )
    )
    return jsonify(story.to_dict()), 201


@api_bp.route("/stories/<int:story_id>", methods=["GET"])
def story_detail(story_id: int):
    story = db.session.get(Story, story_id)
    if story is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(
        {
            "story": story.to_dict(),
            "characters": [c.to_dict() for c in story.characters],
            "scenes": [s.to_dict() for s in story.scenes],
        }
    )


@api_bp.route("/stories/<int:story_id>/scenes", methods=["POST"])
def add_scene(story_id: int):
    payload = _payload()
    if not payload.get("summary"):
        return jsonify({"error": "summary_required"}), 400
    service = StoryService()
    story = db.session.get(Story, story_id)
    if story is None:
        return jsonify({"error": "story_not_found"}), 404
    scene = service.add_scene(
        story_id,
        payload.get("title", f"Scene {len(story.scenes) + 1}"),
        payload["summary"],
        payload.get("page_type"),
        payload.get("camera_angle"),
    )
    return jsonify(scene.to_dict()), 201


# ---------- prompts ----------
@api_bp.route("/prompt", methods=["POST"])
def prompt_preview():
    payload = _payload()
    if not payload.get("summary"):
        return jsonify({"error": "summary_required"}), 400
    recipe = PromptService().build_prompt(
        payload.get("title", "Untitled Scene"),
        payload["summary"],
        payload.get("page_size", "US_6_X_9"),
        payload.get("character_tokens"),
    )
    return jsonify(recipe.to_dict())


# ---------- page layout ----------
@api_bp.route("/layout", methods=["POST", "GET"])
def layout():
    payload = _payload() if request.method == "POST" else request.args.to_dict()
    trim_size = payload.get("trim_size", "US_6_X_9")
    bleed = float(payload.get("bleed_mm", 3.0))
    dpi = int(payload.get("dpi", 300))

    page_types = payload.get("page_types")
    if isinstance(page_types, str):
        page_types = [p.strip() for p in page_types.split(",") if p.strip()]
    if not page_types:
        return jsonify(PageLayoutService.build_layout(trim_size=trim_size, bleed_mm=bleed, dpi=dpi).to_dict())
    return jsonify(PageLayoutService.build_book_plan(trim_size=trim_size, page_types=page_types, bleed_mm=bleed, dpi=dpi))


@api_bp.route("/layout/trim-sizes", methods=["GET"])
def trim_sizes():
    return jsonify(
        {name: {"width_mm": w, "height_mm": h} for name, (w, h) in PageLayoutService.available_trim_sizes().items()}
    )


@api_bp.route("/layout/cover", methods=["POST"])
def cover_layout():
    payload = _payload()
    spec = PageLayoutService.build_cover_layout(
        trim_size=payload.get("trim_size", "US_6_X_9"),
        page_count=int(payload.get("page_count", 32)),
        paper=payload.get("paper", "white"),
        bleed_mm=float(payload.get("bleed_mm", 3.0)),
        dpi=int(payload.get("dpi", 300)),
    )
    return jsonify(spec.to_dict())


@api_bp.route("/text/fit", methods=["POST"])
def text_fit():
    """Preview how a paragraph sets into a block (fonts, hyphenation, widows)."""
    payload = _payload()
    text = payload.get("text", "")
    if not text:
        return jsonify({"error": "text_required"}), 400
    result = TextLayoutService().layout(
        text,
        float(payload.get("width_mm", 128)),
        float(payload.get("height_mm", 70)),
        TextStyle(
            font_size=float(payload.get("font_size", 15)),
            alignment=payload.get("alignment", "justify"),
            language=payload.get("language", "en"),
            hyphenate=bool(payload.get("hyphenate", True)),
        ),
    )
    return jsonify(result.to_dict())



# ---------- creative toolchain ----------
@api_bp.route("/tools/status")
def tools_status():
    from app.services.fonts import get_font_book

    return jsonify(
        {
            "llm": get_llm().status(),
            "image_engine": ImageEngineService().status(),
            "print": PrintImageService().status(),
            "fonts": get_font_book().describe(),
            "kaggle": KaggleService().status(),
        }
    )


@api_bp.route("/market/summary")
def market_summary():
    return jsonify(MarketResearchService().summary())


@api_bp.route("/market/analyze", methods=["POST"])
def market_analyze():
    idea = _payload()
    if not idea.get("title"):
        return jsonify({"error": "title_required"}), 400
    return jsonify(MarketResearchService().analyze_idea(idea))


@api_bp.route("/series/assess", methods=["POST"])
def series_assess():
    payload = _payload()
    idea = payload.get("idea", payload)
    if not idea.get("title"):
        return jsonify({"error": "title_required"}), 400
    market = MarketResearchService().analyze_idea(idea) if payload.get("with_market", True) else None
    return jsonify(SeriesService().assess(idea, payload.get("characters"), market).to_dict())


@api_bp.route("/story/brief", methods=["POST"])
def story_brief():
    payload = _payload()
    idea = payload.get("idea", payload)
    if not idea.get("title"):
        return jsonify({"error": "title_required"}), 400
    director = StoryDirectorService()
    brief = director.build_brief(
        idea,
        age_min=int(payload.get("age_min", idea.get("age_min", 4))),
        age_max=int(payload.get("age_max", idea.get("age_max", 8))),
        page_count=payload.get("page_count"),
        refrain=payload.get("refrain"),
        format_hint=payload.get("format_hint", "single"),
    )
    return jsonify({"brief": brief.to_dict(), "problems": director.validate_brief(brief)})


@api_bp.route("/story/write", methods=["POST"])
def story_write():
    payload = _payload()
    idea = payload.get("idea", payload)
    if not idea.get("title"):
        return jsonify({"error": "title_required"}), 400

    director = StoryDirectorService()
    brief = director.build_brief(
        idea,
        age_min=int(payload.get("age_min", idea.get("age_min", 4))),
        age_max=int(payload.get("age_max", idea.get("age_max", 8))),
        page_count=payload.get("page_count"),
        refrain=payload.get("refrain"),
    )
    written = StoryWriterService().write(
        brief, idea, payload.get("characters"), use_llm=bool(payload.get("use_llm", True))
    )
    review = EditorialReviewService().review(
        written["pages"], brief, use_llm=bool(payload.get("use_llm_review", False))
    )
    return jsonify({**written, "review": review.to_dict()})


@api_bp.route("/story/review", methods=["POST"])
def story_review():
    payload = _payload()
    pages = payload.get("pages")
    if not pages:
        return jsonify({"error": "pages_required"}), 400
    idea = payload.get("idea", {"title": payload.get("title", "Untitled")})
    brief = StoryDirectorService().build_brief(
        idea,
        age_min=int(payload.get("age_min", 4)),
        age_max=int(payload.get("age_max", 8)),
        page_count=payload.get("page_count"),
    )
    report = EditorialReviewService().review(pages, brief, use_llm=bool(payload.get("use_llm", False)))
    return jsonify(report.to_dict())


@api_bp.route("/prompts/compile", methods=["POST"])
def prompts_compile():
    payload = _payload()
    scene = payload.get("scene")
    if not scene:
        return jsonify({"error": "scene_required"}), 400
    compiled = ImagePromptCompiler().compile(
        scene,
        payload.get("style_bible"),
        payload.get("characters"),
        engine=payload.get("engine", "sdxl"),
        width_px=int(payload.get("width_px", 1871)),
        height_px=int(payload.get("height_px", 2771)),
    )
    return jsonify(compiled.to_dict())


@api_bp.route("/images/generate", methods=["POST"])
def images_generate():
    payload = _payload()
    prompt = payload.get("prompt")
    if not prompt:
        return jsonify({"error": "prompt_required"}), 400
    try:
        result = ImageEngineService().generate(
            prompt,
            payload.get("output_path", str(_out_dir() / "scene.png")),
            seed=payload.get("seed"),
            steps=int(payload.get("steps", 32)),
            cfg_scale=float(payload.get("cfg_scale", 5.5)),
        )
    except Exception as exc:
        return jsonify({"error": "image_generation_failed", "message": str(exc)}), 400
    return jsonify(result.to_dict())


@api_bp.route("/print/prepare", methods=["POST"])
def print_prepare():
    payload = _payload()
    source = payload.get("source_image")
    if not source or not Path(source).exists():
        return jsonify({"error": "source_image_not_found"}), 400
    layout = PageLayoutService.build_layout(
        trim_size=payload.get("trim_size", "US_6_X_9"),
        page_type=payload.get("page_type", "full_bleed"),
        bleed_mm=float(payload.get("bleed_mm", 3.0)),
    )
    try:
        result = PrintImageService().prepare(
            source,
            layout,
            payload.get("output_path"),
            mode=payload.get("mode", "cover"),
            cmyk=bool(payload.get("cmyk", False)),
            icc_profile=payload.get("icc_profile"),
        )
    except Exception as exc:
        return jsonify({"error": "print_prepare_failed", "message": str(exc)}), 400
    return jsonify(result)


# ---------- rendering / export ----------
@api_bp.route("/render/cover", methods=["POST"])
def render_cover():
    payload = _payload()
    service = RenderService(_out_dir())
    path = service.render_cover_pdf(
        payload.get("title", "Luna and the Lantern Forest"),
        payload.get("subtitle", "A story of courage and friendship"),
        payload.get("author", ""),
        output_name=payload.get("output_name", "cover_output.pdf"),
        trim_size=payload.get("trim_size", "US_6_X_9"),
        include_guides=bool(payload.get("guides", False)),
    )
    return jsonify({"path": path, "exists": Path(path).exists()})


@api_bp.route("/render/story", methods=["POST"])
def render_story():
    payload = _payload()
    pages = payload.get("pages") or [
        "In the early morning light, a little child stepped into a forest that whispered with secrets.",
        "She carried a small lantern and a brave heart, even though she felt afraid.",
        "And she learned that courage is choosing to help, even when fear is strong.",
    ]
    service = RenderService(_out_dir())
    path = service.render_story_pdf(
        pages,
        output_name=payload.get("output_name", "storybook.pdf"),
        title=payload.get("title", "Luna and the Lantern Forest"),
        trim_size=payload.get("trim_size", "US_6_X_9"),
        page_images=payload.get("page_images"),
        include_guides=bool(payload.get("guides", False)),
    )
    return jsonify({"path": path, "pages": len(pages)})


@api_bp.route("/render/wrap-cover", methods=["POST"])
def render_wrap_cover():
    payload = _payload()
    service = RenderService(_out_dir())
    result = service.render_wrap_cover_pdf(
        title=payload.get("title", "Luna and the Lantern Forest"),
        subtitle=payload.get("subtitle", "A story of courage and friendship"),
        author=payload.get("author", "TaleForge Studio"),
        back_blurb=payload.get("back_blurb", ""),
        page_count=int(payload.get("page_count", 32)),
        trim_size=payload.get("trim_size", "US_6_X_9"),
        paper=payload.get("paper", "white"),
        output_name=payload.get("output_name", "cover_wrap.pdf"),
        crop_marks=bool(payload.get("crop_marks", True)),
        include_guides=bool(payload.get("guides", False)),
        language=payload.get("language", "en"),
    )
    return jsonify(result)


@api_bp.route("/export/bundle", methods=["POST"])
def export_bundle():
    payload = _payload()
    service = ExportService(_out_dir())
    directory = service.create_bundle(
        payload.get("product_name", "demo_product"),
        payload.get("files", []),
        metadata=payload.get("metadata"),
    )
    zip_path = service.zip_bundle(directory) if payload.get("zip", True) else None
    return jsonify({"path": directory, "zip": zip_path})


@api_bp.route("/export/print-bundle", methods=["POST"])
def print_bundle():
    payload = _payload()
    manifest = PrintBundleService.create_print_bundle(
        payload.get("product_name", "demo_product"),
        payload.get("files", []),
        payload.get("output_dir", str(_out_dir() / "print_bundle")),
        payload.get("specs"),
    )
    return jsonify(manifest)


# ---------- products / metadata ----------
@api_bp.route("/products", methods=["GET"])
def products():
    items = [p.to_dict() for p in Product.query.all()]
    return jsonify({"items": items})


@api_bp.route("/metadata", methods=["POST"])
def metadata():
    payload = _payload()
    if not payload.get("title"):
        return jsonify({"error": "title_required"}), 400
    metadata_obj = MetadataService.create_metadata(
        product_id=str(payload.get("product_id", "demo-001")),
        title=payload["title"],
        subtitle=payload.get("subtitle", ""),
        category=payload.get("category", "Picture Book"),
        age_group=payload.get("age_group", "4-8"),
        language=payload.get("language", "en"),
        format_type=payload.get("format_type", "paperback"),
        price=float(payload.get("price", 12.99)),
        trim_size=payload.get("trim_size", "6x9"),
        page_count=int(payload.get("page_count", 32)),
        digital_files=payload.get("digital_files", []),
        print_files=payload.get("print_files", []),
    )
    body = metadata_obj.to_dict() if not payload.get("as_text") else {
        "metadata": metadata_obj.to_dict(),
        "json": metadata_obj.to_json(),
    }
    return jsonify(body)


@api_bp.route("/channels/kdp", methods=["POST"])
def kdp_listing():
    payload = _payload()
    listing = AmazonKDPService.build_listing(payload)
    return jsonify({"listing": listing.to_dict(), "warnings": AmazonKDPService.validate(payload)})


@api_bp.route("/channels/etsy", methods=["POST"])
def etsy_listing():
    payload = _payload()
    listing = EtsyService.build_listing(payload)
    return jsonify({"listing": listing.to_dict(), "warnings": EtsyService.validate(listing)})


# ---------- bilingual editions ----------
@api_bp.route("/bilingual/build", methods=["POST"])
def bilingual_build():
    payload = _payload()
    pages_primary = payload.get("pages_primary") or []
    pages_secondary = payload.get("pages_secondary") or []
    if not pages_primary or not pages_secondary:
        return jsonify({"error": "pages_primary_and_pages_secondary_required"}), 400
    try:
        book = BilingualService().build(
            pages_primary, pages_secondary,
            language_primary=payload.get("language_primary", "en"),
            language_secondary=payload.get("language_secondary", "de"),
            title_primary=payload.get("title_primary", ""),
            title_secondary=payload.get("title_secondary", ""),
            mode=payload.get("mode", "stacked"),
        )
    except ValueError as exc:
        return jsonify({"error": "invalid_bilingual_request", "message": str(exc)}), 400
    return jsonify({**book.to_dict(), "alignment_problems": BilingualService.alignment_report(book)})


@api_bp.route("/bilingual/pairs", methods=["GET"])
def bilingual_pairs():
    return jsonify({"pairs": BilingualService.available_pairs()})


@api_bp.route("/library", methods=["GET"])
def library_index():
    path = Path(current_app.config["OUTPUT_DIR"]) / "library" / "library_index.json"
    if not path.exists():
        return jsonify({"books": [], "editions": [], "note": "run: python scripts/produce_library.py"})
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("books", payload.get("editions", []))
    return jsonify(payload)


# ---------- multilingual ----------
@api_bp.route("/languages", methods=["GET"])
def languages():
    return jsonify({"languages": MultilingualStoryService.supported_languages(), "policy": language_policy.policy()})


@api_bp.route("/story/multilingual", methods=["POST"])
def multilingual_story():
    payload = _payload()
    allowed, rejected = language_policy.split_requested(payload.get("languages"))
    if rejected and not payload.get("allow_extra"):
        return (
            jsonify(
                {
                    "error": "language_disabled",
                    "rejected": rejected,
                    "enabled": language_policy.enabled_languages(),
                    "message": "Product scope is English, German and Spanish. "
                               "Set OUTPUT_LANGUAGES / ALLOW_EXTRA_LANGUAGES=1 to change it.",
                }
            ),
            400,
        )
    variants = MultilingualStoryService.build_multilingual_versions(
        payload.get("base_story", {}), allowed
    )
    return jsonify({"items": [v.to_dict() for v in variants]})


# ---------- coloring / ebook ----------
@api_bp.route("/coloring/page", methods=["POST"])
def coloring_page():
    payload = _payload()
    source = payload.get("source_image")
    if not source or not Path(source).exists():
        return jsonify({"error": "source_image_not_found"}), 400
    path = ColoringService.generate_coloring_page(
        source, payload.get("output_path", str(_out_dir() / "coloring_page.png"))
    )
    return jsonify({"path": path})


@api_bp.route("/ebook", methods=["POST"])
def ebook():
    payload = _payload()
    variants = MultilingualStoryService.build_multilingual_versions(
        payload.get("base_story", {}), [payload.get("language", "en")]
    )
    if not variants:
        return jsonify({"error": "unsupported_language"}), 400
    variant = variants[0]
    path = EbookService.create_epub(
        variant.title,
        variant.paragraphs,
        str(_out_dir() / f"ebook_{variant.language}.epub"),
        language=variant.language,
    )
    return jsonify({"path": path, "language": variant.language})


# ---------- quality / images ----------
@api_bp.route("/quality/evaluate", methods=["POST"])
def quality():
    payload = _payload()
    score = QualityService().evaluate(
        **{k: float(v) for k, v in payload.items() if k in {
            "character_consistency", "facial_clarity", "anatomy_quality",
            "lighting_quality", "composition_quality", "color_harmony", "print_suitability",
        }}
    )
    return jsonify({"score": score.to_dict(), "passed": score.passed})


@api_bp.route("/images/fit", methods=["POST"])
def images_fit():
    payload = _payload()
    source = payload.get("source_image")
    if not source or not Path(source).exists():
        return jsonify({"error": "source_image_not_found"}), 400
    path = ImageFitService.fit_to_page(
        source,
        payload.get("output_image", str(_out_dir() / "page_fitted.png")),
        float(payload.get("page_width_mm", 152.4)),
        float(payload.get("page_height_mm", 228.6)),
        float(payload.get("bleed_mm", 3.0)),
        float(payload.get("safe_margin_mm", 12.0)),
        int(payload.get("dpi", 300)),
        payload.get("mode", "cover"),
    )
    return jsonify({"path": path, "resolution": ImageFitService.check_print_resolution(path)})


@api_bp.route("/quality/image", methods=["POST"])
def quality_image():
    payload = _payload()
    path = payload.get("image")
    if not path or not Path(path).exists():
        return jsonify({"error": "image_not_found"}), 400
    page = (
        float(payload.get("page_width_mm", 152.4)),
        float(payload.get("page_height_mm", 228.6)),
    )
    return jsonify(QualityService.evaluate_image(path, page_mm=page))


@api_bp.route("/images/cmyk", methods=["POST"])
def images_cmyk():
    payload = _payload()
    source = payload.get("source_image")
    if not source or not Path(source).exists():
        return jsonify({"error": "source_image_not_found"}), 400
    return jsonify(
        ImageFitService.convert_to_cmyk(
            source,
            payload.get("output_image", str(_out_dir() / "artwork_cmyk.jpg")),
            payload.get("icc_profile"),
            int(payload.get("dpi", 300)),
        )
    )


# ---------- vector search ----------
@api_bp.route("/search/reindex", methods=["POST"])
def reindex():
    StoryService().seed_demo()
    return jsonify({"indexed": seed_story_documents(), "stats": VectorService().stats()})


# ---------- kaggle ----------
@api_bp.route("/kaggle/status")
def kaggle_status():
    return jsonify(KaggleService().status())


@api_bp.route("/kaggle/search")
def kaggle_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "query_required"}), 400
    try:
        return jsonify({"items": KaggleService().search_datasets(query)})
    except Exception as exc:
        return jsonify({"error": "kaggle_failed", "message": str(exc)}), 400


@api_bp.route("/kaggle/download", methods=["POST"])
def kaggle_download():
    dataset_ref = _payload().get("dataset_ref")
    if not dataset_ref:
        return jsonify({"error": "dataset_ref_required"}), 400
    try:
        manifest = KaggleService().download_dataset(dataset_ref, _payload().get("unzip", True))
    except Exception as exc:  # credentials / network issues
        return jsonify({"error": "kaggle_failed", "message": str(exc)}), 400
    return jsonify({"status": "ok", **manifest})


# ---------- full demo pipeline ----------
@api_bp.route("/pipeline/demo", methods=["POST"])
def pipeline_demo():
    """Runs the whole chain end-to-end and returns every produced artifact."""
    payload = _payload()
    out = _out_dir()
    title = payload.get("title", "Luna and the Lantern Forest")

    story = StoryService().seed_demo()

    prompt_recipes = [
        PromptService().build_prompt(s.title or "Scene", s.summary or "", character_tokens=[
            c.consistency_token for c in story.characters if c.consistency_token
        ]).to_dict()
        for s in story.scenes
    ]

    scene_page_types = [(s.page_type or "single") for s in story.scenes] or ["single"]
    book_plan = PageLayoutService.build_book_plan(trim_size="US_6_X_9", page_types=scene_page_types)

    renderer = RenderService(str(out))
    cover = renderer.render_cover_pdf(title, "A story of courage and friendship", "TaleForge Studio")
    interior = renderer.render_story_pdf(
        [s.summary or "" for s in story.scenes] or ["A short demo page."],
        title=title,
        page_types=scene_page_types,
    )

    metadata_obj = MetadataService.create_metadata(
        product_id=f"story-{story.id}",
        title=title,
        subtitle="A story of courage and friendship",
        category="Picture Book",
        age_group=f"{story.age_min}-{story.age_max}",
        language=story.language,
        price=12.99,
        page_count=max(24, len(story.scenes) * 8),
    )
    meta_path = out / "metadata.json"
    meta_path.write_text(metadata_obj.to_json(), encoding="utf-8")

    page_count = max(24, len(story.scenes) * 8)
    wrap = renderer.render_wrap_cover_pdf(
        title=title,
        subtitle="A story of courage and friendship",
        author="TaleForge Studio",
        back_blurb=metadata_obj.listing_description,
        page_count=page_count,
        crop_marks=True,
    )

    exporter = ExportService(str(out))
    bundle = exporter.create_bundle(
        title,
        [cover, wrap["path"], interior, str(meta_path)],
        metadata=json.loads(meta_path.read_text(encoding="utf-8")),
    )
    zip_path = exporter.zip_bundle(bundle)

    return jsonify(
        {
            "story": story.to_dict(),
            "prompts": prompt_recipes,
            "page_layouts": book_plan,
            "cover_pdf": cover,
            "cover_wrap_pdf": wrap["path"],
            "cover_spec": wrap["spec"],
            "typography": renderer.last_layout_report,
            "interior_pdf": interior,
            "metadata": metadata_obj.to_dict(),
            "bundle_dir": bundle,
            "zip": zip_path,
            "kdp": AmazonKDPService.build_listing(metadata_obj.metadata_json).to_dict(),
            "etsy": EtsyService.build_listing(metadata_obj.metadata_json).to_dict(),
        }
    )
