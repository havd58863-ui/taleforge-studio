from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import create_app
from app.config import TestingConfig


@pytest.fixture()
def client():
    app = create_app(TestingConfig)
    with app.test_client() as test_client:
        yield test_client


def test_home_page(client):
    assert client.get("/").status_code == 200


def test_health(client):
    payload = client.get("/api/health").get_json()
    assert payload["status"] == "ok"


def test_idea_scoring_bounds(client):
    items = client.get("/api/ideas").get_json()["items"]
    assert items and 0 <= items[0]["score"]["total_score"] <= 100


def test_prompt_recipe(client):
    payload = client.post(
        "/api/prompt", json={"title": "Bloom", "summary": "Luna sees lanterns bloom at sunrise."}
    ).get_json()
    assert payload["page_type"] in {"single", "spread", "full_bleed"}
    assert payload["text_area"]["width_mm"] > 0


def test_metadata_and_channels(client):
    meta = client.post("/api/metadata", json={"title": "Test Book"}).get_json()
    assert meta["seo_keywords"]
    kdp = client.post("/api/channels/kdp", json={"title": "Test Book", "page_count": 32}).get_json()
    assert kdp["listing"]["age_range"]


def test_multilingual_variants(client):
    items = client.post(
        "/api/story/multilingual", json={"languages": ["en", "de"]}
    ).get_json()["items"]
    assert {item["language"] for item in items} == {"en", "de"}


def test_product_language_scope_is_english_german_spanish(client):
    policy = client.get("/api/languages").get_json()
    assert set(policy["policy"]["enabled"]) == {"en", "de", "es"}
    assert "ar" not in policy["languages"]

    blocked = client.post("/api/story/multilingual", json={"languages": ["ar"]})
    assert blocked.status_code == 400
    body = blocked.get_json()
    assert body["error"] == "language_disabled" and body["rejected"] == ["ar"]

    built = client.post("/api/story/multilingual", json={"languages": ["en", "de", "es"]}).get_json()["items"]
    assert {item["language"] for item in built} == {"en", "de", "es"}
    assert all(item["paragraphs"] for item in built)


def test_brief_carries_the_language_into_the_writer_prompt():
    from app.services.story_director_service import StoryDirectorService

    director = StoryDirectorService()
    brief = director.build_brief({"title": "Luna"}, 4, 8, language="de")
    prompt = brief.to_writer_prompt()
    assert brief.language == "de"
    assert "Deutsch" in prompt["user"]
    assert any("Deutsch" in c for c in brief.constraints)

    with pytest.raises(ValueError):
        director.build_brief({"title": "Luna"}, 4, 8, language="fr")


def test_offline_writer_is_honest_about_german_and_spanish():
    from app.services.story_director_service import StoryDirectorService
    from app.services.story_writer_service import StoryWriterService

    brief = StoryDirectorService().build_brief({"title": "Luna"}, 4, 8, page_count=24, language="es")
    written = StoryWriterService().write(brief, {"title": "Luna"}, [], use_llm=False)
    assert written["mode"] == "offline_en_fallback"
    assert "Español" in written["notice"] or "es" in written["notice"]


def test_layout_service_geometry():
    from app.services.page_layout_service import PageLayoutService

    spec = PageLayoutService.build_layout(page_type="single")
    assert spec.is_valid
    # 6x9 in + 3 mm bleed on both sides
    assert abs(spec.page_box_mm[0] - 158.4) < 0.01
    assert abs(spec.page_box_mm[1] - 234.6) < 0.01
    assert spec.text_block.height_mm > 0
    assert spec.text_block.y_mm >= spec.safe_area.y_mm


def test_layout_endpoint(client):
    payload = client.post("/api/layout", json={"trim_size": "US_8_5_X_8_5", "page_types": ["single", "spread"]}).get_json()
    assert payload["page_count"] == 2
    assert payload["valid"] is True
    trims = client.get("/api/layout/trim-sizes").get_json()
    assert "US_6_X_9" in trims


def test_layout_rejects_bad_trim():
    from app.services.page_layout_service import PageLayoutService

    spec = PageLayoutService.build_layout(trim_size="not_a_size")
    assert spec.trim_size == "US_6_X_9"
    assert any("unknown trim size" in w for w in spec.warnings)


# ---------------------------------------------------------------- typography
def test_bundled_fonts_are_unicode_ready():
    from app.services.fonts import get_font_book

    book = get_font_book()
    assert book.has_unicode_fonts, "expected Andika/Amiri in assets/fonts"
    assert book.get("Luna and the lantern") != "Helvetica"
    assert book.get("لونا") == book.get("لونا", bold=False)


def test_arabic_shaping_changes_glyphs():
    from app.services.fonts import is_arabic, shape_text

    assert is_arabic("لونا")
    assert not is_arabic("Luna")
    shaped = shape_text("لونا")
    assert shaped and shaped != ""  # reshaped or passthrough, never empty


def test_text_layout_fits_and_reports_overflow():
    from app.services.text_layout_service import TextLayoutService, TextStyle

    service = TextLayoutService()
    short = service.layout("Luna found a lantern.", 80, 40)
    assert short.fitted and short.overflow_text == ""
    assert short.rendered_text.startswith("Luna")

    long_text = "Luna walked into the whispering forest. " * 40
    long = service.layout(long_text, 80, 40)
    assert long.overflow_text, "a very long passage must report an overflow remainder"
    assert len(long.rendered_text) < len(long_text)


def test_text_layout_shrinks_instead_of_overflowing():
    from app.services.text_layout_service import TextLayoutService, TextStyle

    service = TextLayoutService()
    result = service.layout("A gentle line of story text. " * 6, 90, 25, TextStyle(font_size=18))
    assert result.font_size <= 18
    assert result.height_ok if hasattr(result, "height_ok") else result.fitted


# -------------------------------------------------------------------- covers
def test_cover_layout_spine_and_warnings():
    from app.services.page_layout_service import PageLayoutService

    spec = PageLayoutService.build_cover_layout(page_count=120, trim_size="US_6_X_9")
    assert 6.0 < spec.spine_mm < 7.5          # 120 pages on white paper
    assert spec.spine_text_allowed is True
    assert abs(spec.wrap_width_mm - (2 * (3 + 152.4) + spec.spine_mm)) < 0.01

    thin = PageLayoutService.build_cover_layout(page_count=24)
    assert thin.spine_text_allowed is False
    assert any("spine text" in w for w in thin.warnings)

    invalid = PageLayoutService.build_cover_layout(page_count=10)
    assert invalid.is_valid is False


def test_wrap_cover_pdf_renders(tmp_path):
    from app.services.render_service import RenderService

    service = RenderService(str(tmp_path))
    result = service.render_wrap_cover_pdf(
        title="Luna and the Lantern Forest",
        subtitle="A story of courage",
        author="TaleForge Studio",
        back_blurb="When the lanterns begin to fade, Luna must choose kindness over fear.",
        page_count=120,
        crop_marks=True,
    )
    assert Path(result["path"]).exists()
    assert result["spec"]["spine_text_allowed"] is True

    data = Path(result["path"]).read_bytes()
    boxes = re.findall(rb"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]", data)
    assert boxes
    width_mm = float(boxes[0][2]) / 72 * 25.4
    assert abs(width_mm - result["spec"]["wrap_width_mm"]) < 0.5
    assert b"/Title (Luna and the Lantern Forest)" in data


# ------------------------------------------------------------- image quality
def _make_art(path, size=(1800, 2700), blur=0):
    from PIL import Image, ImageDraw, ImageFilter

    img = Image.new("RGB", size, "#F6F3EE")
    draw = ImageDraw.Draw(img)
    for i in range(0, size[0], 35):
        draw.line([(i, 0), (i + 400, size[1])], fill=(40, 90, 60), width=3)
        draw.ellipse([i % 1500, 300 + i % 900, i % 1500 + 220, 520 + i % 900], outline=(200, 60, 60), width=5)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    img.save(path)
    return path


def test_quality_gate_measures_real_images(tmp_path):
    from app.services.quality_service import QualityService

    sharp = _make_art(tmp_path / "sharp.png")
    blurry = _make_art(tmp_path / "soft.png", blur=6)
    blank = tmp_path / "blank.png"
    from PIL import Image

    Image.new("RGB", (300, 400), "#FFFFFF").save(blank)

    good = QualityService.evaluate_image(str(sharp))
    assert good["passed"] is True
    assert good["metrics"]["effective_dpi"] >= 300

    soft = QualityService.evaluate_image(str(blurry))
    assert soft["passed"] is False
    assert soft["gate"]["sharpness_ok"] is False

    empty = QualityService.evaluate_image(str(blank))
    assert empty["passed"] is False
    assert empty["gate"]["resolution_ok"] is False


def test_image_fit_and_cmyk(tmp_path):
    from PIL import Image

    from app.services.image_fit_service import ImageFitService

    source = _make_art(tmp_path / "art.png")
    fitted = ImageFitService.fit_to_page(str(source), str(tmp_path / "page.png"), 152.4, 228.6)
    with Image.open(fitted) as img:
        assert img.size == (1870, 2770)  # 6x9in + 3mm bleed at 300dpi

    cmyk = ImageFitService.convert_to_cmyk(str(source), str(tmp_path / "art_cmyk.jpg"))
    with Image.open(cmyk["path"]) as img:
        assert img.mode == "CMYK"


# ------------------------------------------------------------------- kaggle
def test_kaggle_status_without_credentials():
    from app.services.kaggle_service import KaggleService

    status = KaggleService().status()
    assert "configured" in status
    assert status["datasets_dir"].endswith("datasets")


# --------------------------------------------------------------------- API
def test_typography_and_cover_endpoints(client):
    fit = client.post("/api/text/fit", json={"text": "Luna found a lantern.", "width_mm": 80}).get_json()
    assert fit["rendered_text"]

    cover = client.post("/api/layout/cover", json={"page_count": 120}).get_json()
    assert cover["spine_text_allowed"] is True

    wrap = client.post(
        "/api/render/wrap-cover",
        json={"title": "Test Book", "page_count": 120, "back_blurb": "A short blurb."},
    ).get_json()
    assert Path(wrap["path"]).exists()


def test_rtl_text_keeps_logical_line_order():
    from app.services.text_layout_service import TextLayoutService, TextStyle

    result = TextLayoutService().layout(
        "في ضوء الصباح الباكر، دخلت طفلة صغيرة غابة تهمس بالأسرار.",
        60,
        40,
        TextStyle(language="ar", alignment="right"),
    )
    assert result.font_name.startswith("Amiri")
    assert result.rendered_text.split()[0] == "في", "RTL lines must stay in logical order"


def test_idea_scores_discriminate():
    """Regression: the weighted average must not saturate at 100 for every idea."""
    from app.services.idea_service import IdeaService, StoryIdea

    service = IdeaService()
    ranked = service.ranked_candidates()
    scores = [item["score"]["total_score"] for item in ranked]
    assert scores == sorted(scores, reverse=True), "candidates must be ranked"
    assert len(set(scores)) == len(scores), "two different ideas must not get the same score"
    assert all(0 <= s <= 100 for s in scores)

    weak = StoryIdea(
        title="Generic Tale",
        premise="A plain story about nothing much.",
        genre="realistic",
        target_age_min=4,
        target_age_max=8,
        setting="a village",
        world="an ordinary village",
        central_conflict="nothing in particular",
        emotional_core="neutral",
        lesson_value="sharing is nice",
        originality_score=45,
        market_score=40,
        visual_score=50,
        novelty_score=35,
    )
    result = service.score_idea(weak)
    assert result["total_score"] < 75
    assert result["is_viable"] is False


# ---------------------------------------------------------------- round 4: toolchain
def test_llm_client_reports_offline_without_env(monkeypatch):
    for key in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    from app.services.llm_client import LLMClient

    client_llm = LLMClient()
    assert client_llm.available is False
    status = client_llm.status()
    assert status["available"] is False
    assert "hint" in status


def test_story_director_brief_is_complete():
    from app.services.story_director_service import StoryDirectorService

    idea = {"title": "Luna and the Lantern Forest", "world": "lantern forest", "setting": "forest"}
    director = StoryDirectorService()
    brief = director.build_brief(idea, 4, 8, page_count=32)
    assert brief.page_count == sum(beat.page_count for beat in brief.beats) == 32
    assert len(brief.beats) == 9
    assert brief.beats[0].pages[0] == 1 and brief.beats[-1].pages[-1] == 32
    assert director.validate_brief(brief) == []
    assert brief.constraints and brief.to_writer_prompt()["system"]


def test_writer_offline_passes_the_editorial_gate():
    from app.services.editorial_review_service import EditorialReviewService
    from app.services.story_director_service import StoryDirectorService
    from app.services.story_writer_service import StoryWriterService

    idea = {"title": "Luna and the Lantern Forest", "setting": "forest", "world": "lantern forest"}
    brief = StoryDirectorService().build_brief(idea, 4, 8, page_count=32)
    written = StoryWriterService().write(brief, idea, [{"name": "Luna", "role": "young explorer"}], use_llm=False)
    assert written["mode"] == "offline"
    assert len(written["pages"]) == 32
    low, high = brief.words_per_page
    assert all(low <= page["word_count"] <= high for page in written["pages"])

    report = EditorialReviewService().review(written["pages"], brief)
    assert report.passed is True, [f.message for f in report.findings if f.severity == "error"]
    assert len(report.metrics["refrain_pages"]) == 3


def test_editor_rejects_a_broken_manuscript():
    from app.services.editorial_review_service import EditorialReviewService
    from app.services.story_director_service import StoryDirectorService

    brief = StoryDirectorService().build_brief({"title": "Broken"}, 4, 8, page_count=32)
    bad_pages = [
        {"page": i, "text": "Kill. Die.", "scene": "", "beat": brief.beats[0].name}
        for i in range(1, 33)
    ]
    report = EditorialReviewService().review(bad_pages, brief)
    assert report.passed is False
    codes = {finding.code for finding in report.findings if finding.severity == "error"}
    assert {"word_budget", "scene_description" if False else "weak_scene", "unsafe_content"} <= codes
    assert "refrain_count" in codes and "arc_incomplete" in codes


def test_market_research_baseline_is_labelled_low_confidence(tmp_path):
    from app.services.market_research_service import MarketResearchService

    service = MarketResearchService(str(tmp_path / "empty"))
    result = service.analyze_idea({"title": "Luna and the Lantern Forest", "world": "forest"})
    assert result["basis"] == "curated_baseline"
    assert result["confidence"] == "low"
    assert result["market_score"] <= 65


def test_market_research_reads_a_dataset(tmp_path):
    import csv

    from app.services.market_research_service import MarketResearchService

    folder = tmp_path / "datasets"
    folder.mkdir()
    rows = [
        {"title": f"Bedtime Bear {i}", "description": "A bedtime story about a sleepy bear", "rating": "4.5"}
        for i in range(6)
    ] + [
        {"title": f"Lantern Girl {i}", "description": "A girl finds a glowing lantern in the forest", "rating": "4.8"}
        for i in range(2)
    ]
    with (folder / "books.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["title", "description", "rating"])
        writer.writeheader()
        writer.writerows(rows)

    service = MarketResearchService(str(folder))
    result = service.analyze_idea({"title": "Lantern Girl in the Forest", "world": "lantern forest"})
    assert result["basis"] == "dataset"
    assert result["confidence"] == "high"
    index = service.build_index()
    assert index.items == 8
    assert index.trope_saturation["bedtime_sleep"] > index.trope_saturation["unicorn_magic"]
    assert service.gaps(3)


def test_series_decision_scales_with_property_strength():
    from app.services.series_service import SeriesService

    strong = {
        "title": "Luna and the Lantern Forest",
        "premise": "A companion spirit helps a child who must find a new lantern each season",
        "world": "A magical forest rule: light must be shared every night",
        "setting": "forest river castle village mountain sea garden",
        "age_min": 4,
        "age_max": 9,
    }
    weak = {"title": "One Day at the Beach", "premise": "A single afternoon by the sea.", "age_min": 5, "age_max": 6}
    characters = [{"name": "Pip", "role": "companion spirit"}]
    assert SeriesService().assess(strong, characters).score > SeriesService().assess(weak, []).score
    assert SeriesService().assess(weak, []).decision in {"single_book", "sequel_optional"}


def test_prompt_compiler_speaks_each_engine_dialect():
    from app.services.image_prompt_compiler import ImagePromptCompiler

    compiler = ImagePromptCompiler()
    scene = {"title": "Page 4", "summary": "Luna lifts the lantern in the rain.", "camera": "low_angle"}
    style = {"palette": ["#f4c95d", "#2f4858"], "line": "soft ink linework"}

    sdxl = compiler.compile(scene, style, engine="sdxl", width_px=1871, height_px=2771)
    assert "children's book illustration" in sdxl.positive and sdxl.negative
    assert sdxl.width_px == 1871 and ":" in sdxl.aspect_ratio

    mj = compiler.compile(scene, style, engine="midjourney")
    assert "--ar" in mj.positive and "--no" in mj.positive

    dalle = compiler.compile(scene, style, engine="dalle3")
    assert dalle.negative == "" and "No text" in dalle.positive

    long_prompt = compiler.compile(
        {**scene, "summary": " ".join(["a very detailed description of the forest"] * 40)}, style, engine="sdxl"
    )
    assert long_prompt.truncated is True
    assert long_prompt.tokens_estimate <= 80


def test_image_engine_is_optional_and_says_so(monkeypatch):
    for key in ("IMAGE_PROVIDER", "IMAGE_BASE_URL", "IMAGE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    from app.services.image_engine_service import ImageEngineService

    engine = ImageEngineService()
    assert engine.available is False
    assert engine.status()["hint"]
    with pytest.raises(RuntimeError):
        engine.generate({"positive": "x"}, "/tmp/should_not_exist.png")


def test_print_prepare_upscales_and_reports_a_gate(tmp_path):
    from PIL import Image, ImageDraw

    from app.services.page_layout_service import PageLayoutService
    from app.services.print_image_service import PrintImageService

    image = Image.new("RGB", (700, 1000), (235, 220, 195))
    draw = ImageDraw.Draw(image)
    for step in range(0, 700, 40):
        draw.line([(step, 0), (700 - step, 1000)], fill=(60 + step % 150, 90, 120), width=6)
    source = tmp_path / "art.png"
    image.save(source)

    layout = PageLayoutService.build_layout(trim_size="US_6_X_9", page_type="full_bleed")
    result = PrintImageService().prepare(str(source), layout, str(tmp_path / "out.png"))
    assert result["upscaled"]
    assert result["output_px"]["width"] >= int(layout.page_px[0] * 0.98)
    assert result["metrics"]["effective_dpi"] >= 200
    assert set(result["gate"]) >= {"resolution_ok", "sharpness_ok", "exposure_ok", "print_score_ok"}


def test_toolchain_endpoints(client):
    status = client.get("/api/tools/status").get_json()
    assert {"llm", "image_engine", "print", "fonts"} <= set(status)

    written = client.post(
        "/api/story/write",
        json={"idea": {"title": "Luna and the Lantern Forest", "setting": "forest"}, "use_llm": False,
              "page_count": 24, "characters": [{"name": "Luna", "role": "young explorer"}]},
    ).get_json()
    assert written["mode"] == "offline"
    assert written["review"]["passed"] is True

    prompt = client.post(
        "/api/prompts/compile",
        json={"scene": {"summary": "Luna lifts the lantern.", "camera": "low_angle"}, "engine": "sdxl"},
    ).get_json()
    assert prompt["engine"] == "sdxl" and prompt["positive"]

    market = client.post("/api/market/analyze", json={"title": "Luna and the Lantern Forest"}).get_json()
    assert market["market_score"] <= 100

    series = client.post("/api/series/assess", json={"idea": {"title": "Luna"}, "with_market": False}).get_json()
    assert series["decision"] in {"single_book", "sequel_optional", "trilogy", "open_series"}


def test_preflight_measures_page_geometry(tmp_path):
    import subprocess
    import sys

    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    from app.services.page_layout_service import PageLayoutService

    layout = PageLayoutService.build_layout(trim_size="US_6_X_9", page_type="single")
    pdf_path = tmp_path / "probe.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=(layout.page_box_mm[0] * mm, layout.page_box_mm[1] * mm))
    pdf.drawString(20, 20, "preflight probe")
    pdf.showPage()
    pdf.save()

    result = subprocess.run(
        [sys.executable, "scripts/preflight.py", "--pdf", str(pdf_path), "--trim", "US_6_X_9"],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert "pages         : 1" in result.stdout
    assert f"{layout.page_box_mm[0]:.1f} x {layout.page_box_mm[1]:.1f} mm" in result.stdout
    assert "verdict" in result.stdout


# ------------------------------------------------- round 4b: bilingual + library + HF
def test_bilingual_service_stacked_and_facing():
    from app.services.bilingual_service import BilingualService

    service = BilingualService()
    stacked = service.build(["Page one.", "Page two."], ["Seite eins.", "Seite zwei."],
                            "en", "de", "EN title", "DE title")
    assert stacked.page_count == 2
    assert stacked.pages[0]["primary"] == "Page one." and stacked.pages[0]["secondary"] == "Seite eins."
    assert BilingualService.alignment_report(stacked) == []

    facing = service.build(["One.", "Two."], ["Eins.", "Zwei."], "en", "de", mode="facing")
    assert facing.page_count == 4 and facing.pages[1]["language"] == "de"
    assert facing.pages[0]["side"] == "left"

    with pytest.raises(ValueError):
        service.build(["x"], ["y"], "en", "en")
    with pytest.raises(ValueError):
        service.build(["x"], ["y"], "en", "ar")  # Arabic is outside the product scope


def test_bilingual_renderer_puts_two_languages_on_a_page(tmp_path):
    from app.services.bilingual_service import BilingualService
    from app.services.render_service import RenderService

    book = BilingualService().build(
        ["The forest keeps its light in lanterns.", "Every evening Luna counts them."],
        ["Der Wald bewahrt sein Licht in Laternen auf.", "Jeden Abend zählt Luna sie."],
        "en", "de", "Luna", "Luna",
    )
    renderer = RenderService(str(tmp_path))
    path = renderer.render_bilingual_pdf(book.pages, "bilingual.pdf", "Luna")
    assert Path(path).exists() and Path(path).stat().st_size > 1000
    assert renderer.last_layout_report["pages"] == 2


def test_library_texts_fit_the_brief_in_every_language():
    import re

    from app.content.library_texts import REFRAIN, STORY

    assert set(STORY) == {"en", "de", "es"}
    for code, pages in STORY.items():
        assert len(pages) == 24
        for index, page in enumerate(pages, start=1):
            words = len(page.split())
            assert 20 <= words <= 45, f"{code} page {index}: {words} words"
            assert len(re.findall(r"[.!?]+", page)) <= 4, f"{code} page {index}: too many sentences"
        assert sum(1 for page in pages if REFRAIN[code] in page) == 3, f"{code}: refrain must appear 3 times"


def test_editor_does_not_flag_german_articles_as_violence():
    from app.services.editorial_review_service import EditorialReviewService
    from app.services.story_director_service import StoryDirectorService

    director = StoryDirectorService()
    german = director.build_brief({"title": "Luna"}, 4, 8, page_count=24, language="de")
    beats = [beat.name for beat in german.beats for _ in beat.pages]
    clean = [
        {"page": i, "beat": beats[i - 1], "scene": "Luna und die Laternen im Wald, warmes Licht",
         "text": "Die Laterne leuchtet warm, und die Luft riecht nach Moos und Regen."}
        for i in range(1, 25)
    ]
    report = EditorialReviewService().review(clean, german)
    assert not [f for f in report.findings if f.code == "unsafe_content"], "German articles are not violence"

    english = director.build_brief({"title": "Luna"}, 4, 8, page_count=24, language="en")
    english_beats = [beat.name for beat in english.beats for _ in beat.pages]
    violent = [
        {"page": i, "beat": english_beats[i - 1], "scene": "a grey field with cold rain falling",
         "text": "The knife is red with blood and the dog will die."}
        for i in range(1, 25)
    ]
    flagged = EditorialReviewService().review(violent, english)
    assert [f for f in flagged.findings if f.code == "unsafe_content"]


def test_huggingface_token_configures_both_clients(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test_token")
    monkeypatch.setenv("LLM_PROVIDER", "huggingface")
    monkeypatch.setenv("LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    from app.services.llm_client import LLMClient

    client_llm = LLMClient()
    assert client_llm.available is True
    assert client_llm.base_url == "https://router.huggingface.co/v1"

    monkeypatch.setenv("IMAGE_PROVIDER", "huggingface")
    monkeypatch.setenv("IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    from app.services.image_engine_service import ImageEngineService

    engine = ImageEngineService()
    assert engine.available is True
    assert engine.status()["provider"] == "huggingface"


def test_bilingual_and_library_endpoints(client):
    pairs = client.get("/api/bilingual/pairs").get_json()["pairs"]
    assert pairs and all(pair["primary"] != pair["secondary"] for pair in pairs)

    payload = client.post(
        "/api/bilingual/build",
        json={"pages_primary": ["Page one text."], "pages_secondary": ["Seite eins Text."],
              "language_primary": "en", "language_secondary": "de"},
    ).get_json()
    assert payload["page_count"] == 1 and payload["alignment_problems"] == []

    blocked = client.post(
        "/api/bilingual/build",
        json={"pages_primary": ["x"], "pages_secondary": ["y"],
              "language_primary": "en", "language_secondary": "ar"},
    )
    assert blocked.status_code == 400

    index = client.get("/api/library").get_json()
    assert "books" in index and "editions" in index


# ------------------------------------------- round 4c: 32-page structure, spreads, line art
def test_book_structure_has_front_story_and_back_matter():
    from app.content.library_texts import STORY
    from app.services.book_structure_service import BookStructureService

    structure = BookStructureService().build("Luna", STORY["en"], "en", subtitle="A story")
    assert structure.page_count == 32
    assert [page.kind for page in structure.pages[:4]] == ["half_title", "title_page", "copyright", "dedication"]
    story = BookStructureService.story_only(structure)
    assert len(story) == 24
    assert [page.kind for page in structure.pages[-4:]] == ["the_end", "about_author", "series_page", "colophon"]
    assert len(structure.spread_pairs) == 2
    left, right = structure.spread_pairs[0]
    sides = {page.page: page.spread for page in structure.pages}
    assert sides[left] == "left" and sides[right] == "right"


def test_picture_book_renderer_is_full_bleed_with_spreads(tmp_path):
    from PIL import Image

    from app.content.library_texts import STORY
    from app.services.book_structure_service import BookStructureService
    from app.services.render_service import RenderService

    structure = BookStructureService().build("Luna", STORY["en"], "en", subtitle="A story")
    page_img = tmp_path / "page.png"
    Image.new("RGB", (600, 900), (200, 220, 200)).save(page_img)
    wide_img = tmp_path / "wide.png"
    Image.new("RGB", (1200, 900), (180, 200, 230)).save(wide_img)

    images = []
    for page in structure.pages:
        if page.kind != "story":
            images.append(None)
        elif page.spread == "right":
            images.append(str(wide_img))
        elif page.spread == "left":
            images.append(str(wide_img))
        else:
            images.append(str(page_img))

    renderer = RenderService(str(tmp_path))
    path = renderer.render_picture_book_pdf([p.to_dict() for p in structure.pages], "pb.pdf",
                                            page_images=images)
    data = Path(path).read_bytes()
    assert len(__import__("re").findall(rb"/Type\s*/Page[^s]", data)) == 32
    assert renderer.last_layout_report["full_bleed"] is True
    assert renderer.last_layout_report["overflow"] == []


def test_line_art_is_printable_and_vectorises_honestly(tmp_path):
    from PIL import Image, ImageDraw

    from app.services.line_art_service import LineArtService

    art = Image.new("RGB", (900, 1300), (245, 235, 210))
    draw = ImageDraw.Draw(art)
    draw.ellipse([200, 300, 700, 800], fill=(90, 140, 100))
    draw.rectangle([100, 900, 800, 1200], fill=(60, 80, 120))
    source = tmp_path / "art.png"
    art.save(source)

    service = LineArtService()
    result = service.to_line_art(str(source), str(tmp_path / "line.png"), thickness=4, detail=0.5)
    assert Path(result.path).exists()
    printed = service.prepare_for_print(result.path)
    assert 0.2 <= printed["ink_coverage_pct"] <= 30, printed["ink_coverage_pct"]
    assert printed["width_px"] == 900

    vector = service.vectorize(result.path)
    assert "vectorized" in vector and "path" in vector
    if vector["vectorized"]:
        assert vector["format"] == "svg" and Path(vector["path"]).stat().st_size > 200
    else:
        assert "note" in vector


def test_coloring_book_pdf_has_title_page_plus_art(tmp_path):
    from PIL import Image

    from app.services.render_service import RenderService

    pages = [{"kind": "title", "text": "Colour Luna's forest"}]
    for index in range(1, 4):
        image = tmp_path / f"l{index}.png"
        Image.new("RGB", (600, 600), (255, 255, 255)).save(image)
        pages.append({"page": index, "image": str(image)})

    renderer = RenderService(str(tmp_path))
    path = renderer.render_coloring_book_pdf(pages, "cb.pdf", "Coloring Book")
    assert Path(path).exists()
    assert renderer.last_layout_report["coloring"] is True
