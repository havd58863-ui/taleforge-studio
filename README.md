# TaleForge Studio

A private commercial publishing platform for original children's stories, storybook illustration
systems, coloring books, and market-ready print products.

> **Status:** runs out of the box. `python run_server.py` → http://localhost:5000
> Verified with Flask 3.1 on Python 3.11+ (tested on 3.11 and 3.13).

---

## Highlights

| Area | What it does |
|---|---|
| Idea selection | Scores concepts on originality / market / visual / novelty, returns a go-no-go verdict |
| Market research | Saturation + demand + near-duplicate titles from your own Kaggle export, with an explicit `confidence` flag |
| Series decision | Seven-dimension property score → `single_book` / `sequel_optional` / `trilogy` / `open_series` |
| Story Director | A hard `StoryBrief`: page count, word budget, 9-beat arc, refrain ×3, style bible, constraints |
| Real writer | Any OpenAI-compatible model or local Ollama writes inside the brief; deterministic offline scaffold when unset |
| Editorial gate | Word budget, reading level (Flesch-Kincaid), refrain discipline, safety, beat coverage — pass/fail |
| Scene prompts | Per-engine recipes (SDXL/Flux/Midjourney/DALL·E) with character tokens, CLIP limit, negatives |
| Print prep | Upscale (Real-ESRGAN or Lanczos), fit to bleed page, CMYK, gate |
| Story engine | Story, character bible with consistency tokens, scene outlines persisted in SQLAlchemy |
| Prompt engine | Deterministic scene recipes: style, mood, lighting, camera, palette, safe text area |
| Page layout | One geometry service: trim, bleed, safe area, gutter, text/image blocks, mm↔px, validation warnings |
| Typography | Bundled Andika + Amiri (OFL), justified setting, hyphenation per language, widow control, auto-shrink, overflow reporting, real Arabic shaping |
| Wrap covers | Back cover + spine + front cover + bleed, spine width from page count/paper, barcode clear area, crop marks, fold guides |
| Colour | CMYK conversion (ICC-managed when a profile is supplied), unsharp mask after downscale, EXIF stripping |
| Measured quality gate | Sharpness (Laplacian variance), contrast, exposure, clipping, saturation, effective DPI — with pass/fail gate |
| Rendering | Trim + bleed aware cover, interior and coloring-book PDFs (ReportLab); per-page sizes for single / spread / full-bleed |
| Image fitting | Cover/contain fitting with trim, bleed and safe-margin math at 300 dpi + DPI auditing |
| Quality gate | Weighted score with pass/fail, incl. character-consistency minimum |
| Bilingual editions | Two languages on every page (EN-DE, ES-EN): same approved manuscripts, stacked layout, alignment report |
| Trade structure | 32 pages = 4 front matter + 24 story pages + 4 back matter; two double-page spreads at the emotional peaks |
| Full-bleed art | Illustrations reach the trim edge on every story page; text sits in a panel strictly inside the safe area |
| Coloring books | Profressional line art (contour extraction, crayon-safe weight) + optional SVG vectorisation (VTracer, MIT) per story |
| Ready library | `scripts/produce_library.py` builds 5 editions (EN, DE, ES, EN-DE, ES-EN): picture book + coloring book + wrap cover + EPUB + KDP/Etsy listings + bundle |
| Multilingual | **Product scope: English, German, Spanish** (authored variants). FR/AR packs remain in the code but are disabled — `OUTPUT_LANGUAGES` / `ALLOW_EXTRA_LANGUAGES` control it |
| Metadata | Listing title, description, SEO keywords, machine-readable metadata JSON |
| Channels | Amazon KDP listing builder + validator, Etsy listing builder + validator |
| Bundles | Print bundle + manifest, export bundle + zip, EPUB 3 e-book |
| Vector search | FAISS + sentence-transformers when installed, numpy fallback when not |
| Ops | Docker + compose (Postgres/Redis/MinIO), healthcheck, gunicorn, smoke test, pytest |

*Per-stage open-source tool matrix, licences and install commands: **[docs/TOOLCHAIN.md](docs/TOOLCHAIN.md)**.*
*Roadmap as seven gated stages with acceptance criteria: **[docs/MASTER_PLAN.md](docs/MASTER_PLAN.md)**.*
*Should you add n8n to orchestrate the chain? Honest comparison of Cloud trial vs Kaggle+LocalTunnel: **[docs/N8N.md](docs/N8N.md)**.*

### The production chain (six commands)

```bash
python scripts/ideate.py --demo --datasets secure_data/datasets   # idea → market → series → brief
python scripts/write_book.py --demo --out output/book.json        # brief → manuscript → editorial gate
python scripts/generate_scenes.py --book output/book.json --engine sdxl   # page → engine-ready prompt
python scripts/print_prep.py --image art.png --trim US_6_X_9      # artwork → press-ready + measured gate
python scripts/produce_book.py --book output/book.json            # manuscript → interior PDF + wrap cover + bundle
python scripts/preflight.py --pdf output/*_interior.pdf           # page geometry / PDF-X / fonts / verdict
python scripts/produce_library.py                                 # 5 editions → output/library/
python scripts/produce_library.py --only en-de --no-art           # quick dry run of one edition
python scripts/verify_upload.py --path .                          # is the repository complete?
```

Everything runs with **no keys and no GPU**; adding `LLM_*` and `IMAGE_PROVIDER` upgrades the
writer and the illustrator without changing any other stage. See `docs/TOOLCHAIN.md`.

---

## Project layout

```
taleforge-studio/
├── app/
│   ├── __init__.py            # application factory, error handlers
│   ├── config.py              # Config / Development / Production / Testing
│   ├── extensions.py          # db + lazy redis
│   ├── models.py              # Story, Character, Scene, Product, ExportArtifact, VectorDocument
│   ├── routes/
│   │   ├── __init__.py        # blueprint registration
│   │   ├── public_routes.py   # storefront + demo pages
│   │   ├── api_routes.py      # JSON API + full demo pipeline
│   │   └── admin_routes.py    # /admin dashboard
│   ├── services/              # 19 services (idea → layout → typography → export)
│   ├── templates/             # base, home, catalog, dashboard, story_demo
│   └── static/                # css + js
├── assets/fonts/              # Andika + Amiri (OFL) + licences; drop more TTFs here
├── output/                    # generated PDFs, bundles, zips (git-ignored)
├── secure_data/               # private LoRAs, references, datasets, generated (git-ignored)
├── vector_store/              # FAISS index + metadata (git-ignored)
├── scripts/                   # init_db, seed_demo, produce_demo, smoke_test, kaggle_sync
├── tests/                     # pytest suite
├── docs/                      # MASTER_PLAN.md, TOOLCHAIN.md, N8N.md, FIXES.md, QUALITY.md, UPLOAD_GUIDE.md
├── run_server.py  wsgi.py  api_app.py  database.py
├── Dockerfile  docker-compose.yml  .dockerignore
├── requirements.txt  requirements-lite.txt  requirements-dev.txt
├── .env.example  .gitignore  .gitattributes  .dockerignore
├── LICENSE  SECURITY.md  Makefile  pytest.ini
```

---

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # full stack (ML included)
# or, for a fast boot without torch/faiss/opencv:
pip install -r requirements-lite.txt

cp .env.example .env               # then edit SECRET_KEY
python scripts/init_db.py          # create tables
python scripts/seed_demo.py        # demo story + products + vector index
python run_server.py               # http://localhost:5000
```

### Useful commands

```bash
make install      # venv + requirements
make run          # dev server
make seed         # demo data + index
make produce      # build cover + interior + metadata + zip into output/
make test         # pytest
make smoke        # end-to-end test-client checks
make docker       # docker compose up --build
```

---

## Endpoints

### Pages
| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Storefront hero + idea score card |
| GET | `/catalog` | Product catalogue |
| GET | `/dashboard` | Production dashboard (+ "Generate demo bundle" button) |
| GET | `/story-demo` | Character bible + scene prompts |
| GET | `/admin` | Admin dashboard |

### JSON API
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + redis state |
| GET | `/api/ideas` | Ranked story concepts with scores |
| GET/POST | `/api/stories` | List / create stories |
| GET | `/api/stories/<id>` | Story with characters + scenes |
| POST | `/api/stories/<id>/scenes` | Add a scene (prompt auto-generated) |
| POST | `/api/prompt` | Preview a scene prompt recipe |
| POST/GET | `/api/layout` | Page layout spec (trim, bleed, safe area, text/image blocks) |
| GET | `/api/layout/trim-sizes` | Available trim sizes |
| POST | `/api/render/cover` | Front cover PDF (trim/bleed aware) |
| POST | `/api/render/wrap-cover` | Full paperback wrap: back + spine + front + barcode area |
| POST | `/api/layout/cover` | Cover wrap geometry + spine width + KDP warnings |
| POST | `/api/text/fit` | Typography preview: justification, hyphenation, widows, overflow |
| POST | `/api/images/cmyk` | CMYK conversion (ICC-managed when a profile is given) |
| POST | `/api/quality/image` | Measured quality gate on a real illustration |
| POST | `/api/render/story` | Interior PDF (optional images per page) |
| POST | `/api/export/bundle` | Bundle + zip |
| POST | `/api/export/print-bundle` | Print bundle + manifest |
| GET | `/api/products` | Products |
| POST | `/api/metadata` | Listing metadata (title, description, keywords) |
| POST | `/api/channels/kdp` | KDP listing + validation warnings |
| POST | `/api/channels/etsy` | Etsy listing + validation warnings |
| GET | `/api/languages` | Supported languages |
| POST | `/api/story/multilingual` | Original variants per language |
| POST | `/api/coloring/page` | Line-art extraction from an illustration |
| POST | `/api/ebook` | EPUB 3 export |
| POST | `/api/quality/evaluate` | Quality gate score |
| POST | `/api/images/fit` | Fit image to page + DPI audit |
| GET | `/api/search?q=` | Vector search |
| POST | `/api/search/reindex` | Re-index stories |
| GET | `/api/kaggle/status` | Kaggle credentials present? |
| POST | `/api/kaggle/download` | Download a dataset |
| POST | `/api/pipeline/demo` | **Full chain**: prompts → cover → interior → metadata → KDP/Etsy → zip |

### Try it

```bash
curl -X POST localhost:5000/api/pipeline/demo | python -m json.tool
curl -X POST localhost:5000/api/prompt -H 'Content-Type: application/json' \
  -d '{"title":"Lantern Bloom","summary":"Luna watches lanterns bloom at sunrise."}'
curl 'localhost:5000/api/search?q=forest'
```

---

## Print geometry (what "print-ready" means here)

All of these numbers live in **one** place: `app/services/page_layout_service.py`.
`render_service` and `image_fit_service` read from it, so nothing can drift.

* Trim sizes: `US_6_X_9` (default), `US_7_X_10`, `US_8_X_10`, `US_8_5_X_8_5`,
  `US_8_5_X_11`, `SQUARE_8`, `A5`, `A4`
* Bleed: 3 mm (0.125") added on every side of the PDF page
* Safe margin: 12 mm (0.5") inside the trim — the text zone returned by
  `PromptService.text_area_for_page()`
* Guides: dashed trim box drawn only when `guides: true` / `include_guides=True`
* Page types: `single` (image 60% + text), `spread` (double width + gutter),
  `full_bleed` (artwork past the bleed line, text inside the safe area)
* Validation: `PageLayoutService.validate()` flags bleed < 3 mm, dpi < 300,
  text blocks outside the safe area, artwork that misses the bleed
* Images: 300 dpi, `Pillow` LANCZOS resampling, `ImageFitService` keeps the **full page**
  (it never crops the margins away) and can audit effective DPI
* Colours: sRGB; convert to the printer's ICC profile at proofing time

## Publishing-grade output

Full checklist with measurements: **`docs/QUALITY.md`**. Short version:

* **Type**: Andika (literacy-optimised Latin) + Amiri (Naskh Arabic), embedded and subset.
  Justified setting, real hyphenation per language, widow control, 9 pt floor,
  and overflow returned as text instead of being silently clipped.
* **Geometry**: 3 mm bleed, 12 mm safe margin, per-page sizes for single / spread /
  full-bleed, crop marks, trim guides.
* **Wrap cover**: spine width = `pages × 0.0572 mm` (white) or `× 0.0635 mm` (cream),
  barcode clear area 2 × 1.2 in, spine text blocked below 100 pages.
* **Colour**: CMYK conversion (ICC-managed on request), unsharp mask after downscale,
  EXIF stripped, effective-DPI audit at 300 dpi.
* **Gate**: `POST /api/quality/image` measures sharpness/contrast/exposure/clipping/DPI and
  returns pass/fail per criterion. Anatomy and character consistency are **not** measurable
  from pixels and are flagged as estimated — never faked.

## Fonts / Arabic

ReportLab's built-in fonts are Latin-1 only. Drop a Unicode TTF
(`DejaVuSans.ttf`, `NotoSans-Regular.ttf`, `Amiri-Regular.ttf`, `Cairo-Regular.ttf`)
into `assets/fonts/` and it is embedded automatically. For correct Arabic shaping and
RTL ordering also install:

```bash
pip install arabic-reshaper python-bidi
```

Without those, Arabic renders as unshaped, left-to-right glyphs — the text is stored
correctly, only the PDF shaping degrades. The EPUB export is unaffected (`dir="rtl"`).

---

## Kaggle research data

Credentials belong in **GitHub Secrets** (or your server env), never in the repo:

```
KAGGLE_USERNAME=your_username
KAGGLE_KEY=your_api_key
```

```bash
python scripts/kaggle_sync.py --status
python scripts/kaggle_sync.py --search "children book illustration"
python scripts/kaggle_sync.py --download owner/dataset-name
```

Downloads land in `secure_data/datasets/<owner__dataset>/` with a `_manifest.json`
(file count, size, timestamp) so every reference asset is traceable. The API exposes
`GET /api/kaggle/status`, `GET /api/kaggle/search?q=` and `POST /api/kaggle/download`.
Kaggle is optional: the platform boots and works without it.

## Docker

```bash
cp .env.example .env
docker compose up --build
# API      → http://localhost:5000
# Postgres → localhost:5432
# Redis    → localhost:6379
# MinIO    → http://localhost:9000 (console :9001)
```

The API container waits for Postgres to be healthy and overrides `DATABASE_URL`,
`REDIS_URL` and `MINIO_ENDPOINT` to point at the compose services.

---

## Environment variables

Everything lives in `.env` (see `.env.example`). Never commit it.

| Key | Purpose |
|---|---|
| `SECRET_KEY`, `APP_ENV`, `PORT` | Flask basics |
| `DATABASE_URL` | `sqlite:///...` locally, `postgresql+psycopg2://...` in Docker |
| `REDIS_URL` | Cache/queue (optional at boot) |
| `MINIO_*` | Object storage for generated assets |
| `KAGGLE_USERNAME`, `KAGGLE_KEY` | Research datasets (optional) |
| `EMBEDDING_MODEL`, `VECTOR_DB_PATH`, `VECTOR_METADATA_PATH` | Vector search |
| `PRIVATE_DATA_DIR`, `LORA_DIR`, `REFERENCE_DIR`, `DATASET_DIR`, `GENERATED_DIR` | Private assets |
| `OUTPUT_DIR` | Generated artifacts |

### GitHub Actions secrets
`SECRET_KEY`, `DATABASE_URL` (prod), `KAGGLE_USERNAME`, `KAGGLE_KEY`.

---

## Testing

```bash
pytest                 # unit/integration tests
python scripts/smoke_test.py   # 21 end-to-end checks through the test client
```

Expected output: `SMOKE TEST: ALL PASSED`.

---

## Security notes

* `.env` is git-ignored; `.env.example` contains placeholders only
* `secure_data/`, `vector_store/` and `output/` content is git-ignored (folders kept via README files)
* Kaggle credentials are written to `~/.kaggle/kaggle.json` with `0600` permissions at use time
* Set `APP_ENV=production` to enable secure cookies and disable debug
* There is no public authentication layer yet — put the app behind a reverse proxy with auth
  before exposing it, or add Flask-Login + RBAC before any multi-user use

## Repository hygiene

* `.gitattributes` normalises line endings (LF) and marks binaries
* `.gitignore` keeps `output/`, `secure_data/`, `vector_store/`, `.env`, `*.db` out of git
  while keeping the folders (each has a `README.txt`)
* `LICENSE` = proprietary / all rights reserved; `SECURITY.md` = reporting + baseline
* Push instructions: `docs/UPLOAD_GUIDE.md`

## Roadmap (not implemented yet)

* Auth + multi-tenant projects
* Image-generation provider adapters (LoRA / SDXL / commercial APIs) behind `render_service`
* Training pipeline for private LoRAs
* Direct KDP/Etsy upload via their APIs (listing builders exist; submission does not)

How a story is planned and produced, stage by stage: `docs/STORY_PIPELINE.md`.
Audit of the original spec draft: `docs/AUDIT.md` (evidence + measurements).
File-by-file change log: `docs/FIXES.md`. Push instructions: `docs/UPLOAD_GUIDE.md`.
