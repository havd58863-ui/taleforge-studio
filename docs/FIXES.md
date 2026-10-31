# Corrections applied to the original spec draft

The pasted package was a good blueprint but several files would have failed at import or
runtime. These are the fixes shipped in this repository.

| # | Original issue | Effect | Fix |
|---|---|---|---|
| 1 | `redis_client.init_app(app)` in `app/__init__.py` | `AttributeError` — `Redis` has no `init_app` | `init_redis(app)` builds a lazy client; `redis_healthy()` guards failures |
| 2 | `app/services/__init__.py` missing from the tree | `from app.services.x import y` broke on some setups | package file added |
| 3 | `api_bp` had routes `"/api/health"` **and** `url_prefix="/api"` | every endpoint served at `/api/api/...` | routes are prefix-free (`/health`), prefix applied once |
| 4 | Same double-prefix problem for `admin_bp` (`/admin/admin`) | broken admin URLs | routes are `/` and `/overview` |
| 5 | `create_app()` imported `ensure_vector_storage` → torch + faiss at boot | multi-GB install before the app can start | vector service is lazy, with a numpy fallback backend |
| 6 | `AppConfig` was an instance, `from_object` used directly on it | works, but no env switching / DEBUG wiring | `Development/Production/Testing` config classes + `CONFIG_MAP` |
| 7 | `.gitignore` ignored `*.json` | would have dropped `vector_store/metadata.json`, listings and any config JSON | replaced with explicit path rules |
| 8 | `.gitignore` ignored `secure_data/`, `output/`, `vector_store/` entirely | folders vanished from the repo | folders kept via `README.txt` + negation rules |
| 9 | `ImageFitService` **cropped the safe area out** of the canvas | printed page lost its margins/bleed; output smaller than the trim | fits to the full trim+bleed page (`cover`/`contain`), adds `safe_area_box` + `check_print_resolution` |
| 10 | `dashboard.html` used `products` that the public route never passed | silently rendered 0 / Jinja undefined | route passes `products` and `ready_for_export` |
| 11 | Catalog was always empty (no `Product` rows were ever created) | dead storefront | demo seeding creates three products |
| 12 | `StoryService.add_scene` ignored `PromptService` | two divergent prompt engines | `add_scene` uses `PromptService.build_prompt` |
| 13 | Arabic variant title was `" luna في غابة الشموع"` (mixed-case Latin + stray space) | unshipped-looking copy | `لونا وغابة الفوانيس` + ES/DE variants, RTL metadata |
| 14 | PDFs used `Helvetica` only | Arabic/CJK text cannot render in ReportLab | optional Unicode TTF auto-registration + `arabic-reshaper`/`python-bidi` when installed |
| 15 | `run_server.py` hard-coded debug + port | no env control | reads `APP_ENV` / `PORT`; gunicorn + `wsgi.py` for production |
| 16 | `docker-compose.yml` had no wait/health strategy and a stale `version:` key | API could boot before Postgres | healthcheck + `depends_on: condition`, service DNS for DB/Redis/MinIO |
| 17 | `Dockerfile` ran the Flask dev server and missed system libs | not deployable, opencv import errors | gunicorn CMD, `libgl1`/`libglib2.0-0`/`poppler-utils`, HEALTHCHECK, non-ignored volumes |
| 18 | `opencv-python` (GUI build) in a server image | unnecessary X11 deps | `opencv-python-headless` |
| 19 | No tests, no seed script, no way to verify the app | "runs" was unproven | `tests/`, `scripts/seed_demo.py`, `scripts/produce_demo.py`, `scripts/smoke_test.py` |
| 20 | `kaggle.json` written without strict permissions in one code path | credential exposure risk | `0600` on write, credentials never logged |
| 21 | `ExportService.create_bundle` returned a folder with no manifest/metadata | not auditable | writes `manifest.json` (+ optional `metadata.json`), `zip_bundle()` added |
| 22 | `EbookService` only wrote `.txt` | not a usable digital product | real EPUB 3 writer (uncompressed `mimetype`, OPF/nav/chapter, RTL) |
| 23 | No validation on KDP/Etsy listings | failed uploads discovered at the end | `validate()` returns concrete warnings (trim list, 24-page minimum, 7 keywords, 13 tags, 140-char title) |
| 24 | Vector search crashed when the index was empty / metadata missing | 500 on first search | guard clauses + reindex endpoint |
| 25 | A catch-all `errorhandler(Exception)` also swallowed `HTTPException` | real 404/405/413 became 500s | `HTTPException` handler preserves the original status code as JSON |

| 26 | `page_layout_service.py` appears in the tree but nothing imports it, and its numbers (125×180 mm) contradict the margins used by `render_service` and `image_fit_service` | three conflicting copies of the same geometry | the service is now the single source of truth (trim/bleed/safe/text block/image block) and is wired into `render_service`, `image_fit_service.fit_to_layout()` and `/api/layout`, with `validate()` warnings |
| 27 | Page math was pixel-only: no mm↔px conversion, no gutter for spreads, no trim list | wrong physical output sizes | `to_pixels()`, `gutter_mm`, extra trims (`US_7_X_10`, `US_8_5_X_11`, `A5`), and warnings when bleed < 3 mm or dpi < 300 |
| 28 | Interior PDF used one page size for the whole book | spread pages were clipped or squashed | each page carries its own size via `setPageSize()` (single / spread / full-bleed can mix) |
| 29 | `README-private.md` is listed both at the root and as `app/README-private.md` | ambiguous repo structure | root file is the real one; `app/README.txt` documents the app layer |
| 30 | `render_service` كتب النص بـ `drawString` وحساب أحرف تقديري؛ لا محاذاة، لا تقسيم كلمات، لا معالجة فيض | نص غير احترافي ونص يضيع بصمت | محرّك طباعة `text_layout_service`: justify + hyphenation + widows + تصغير تلقائي + إرجاع الفيض |
| 31 | الخطوط: Helvetica فقط، والعربية كانت تُرسم مشوّهة | لا كتاب عربي قابل للطباعة | خطوط OFL مدمجة (Andika + Amiri) + تشكيل عربي + اختيار الخط حسب النص |
| 32 | الغلاف كان صورة أمامية واحدة فقط | مستحيل الرفع كغلاف paperback | `render_wrap_cover_pdf`: خلفي + كعب محسوب + أمامي + bleed + باركود + علامات قص |
| 33 | لا وجود لأي إعداد CMYK أو ضبط حِدّة بعد التصغير | ألوان غير متوقعة عند المطبعة وصور ناعمة | `convert_to_cmyk()` + Unsharp Mask + إزالة EXIF |
| 34 | `quality_service` أعاد أرقامًا ثابتة لا تقيس شيئًا | «جودة 91» بلا معنى | `analyze_image()` + `evaluate_image()`: قياس فعلي (Laplacian/تباين/إضاءة/DPI) مع gate |
| 35 | `kaggle_service` كتب المفاتيح بلا تحقق ولم يستخدم عند غياب الاعتماد | تجربة سيئة ومخاطر أمنية | `status()` / `search_datasets()` / manifest للتنزيل + `scripts/kaggle_sync.py` + صلاحيات 0600 |
| 36 | عكس النص العربي كاملًا ثم تقطيعه يُنتج أسطرًا بترتيب مقلوب | الصفحة العربية تُقرأ من نهاية الفقرة | التقطيع بالترتيب المنطقي ثم تشكيل كل سطر ورسمه `drawRightString` (اختبار يتحقق أن أول سطر يبدأ بأول كلمة) |
| 37 | أوزان تقييم الأفكار تجمع 1.2 فتصل كل فكرة إلى 100.0 («Strong» دائمًا) | الترتيب بلا معنى والقرار بلا قيمة | مجموع الأوزان = 1.0 + مكافآت محدودة (15/5) + اختبار انحدار يمنع التكرار |

| 38 | لا توجد طبقة كتابة نثر أصلي (الفجوة المعلنة في `STORY_PIPELINE.md`) | المشروع يبني هيكلًا لا كتابًا | `llm_client` + `story_director_service` + `story_writer_service` (LLM أو سقالة حتمية) — دون المساس بأي مسار قائم |
| 39 | تخصيص صفحات القصص لكل فكرة لم يكن مقيّدًا بميزانية كلمات أو عمر | نصوص أطول/أقصر من قدرة الطفل | `StoryBrief`: ميزانية كلمات لكل صفحة + 9 نقاط سرد + لازمة ×3 + دستور بصري |
| 40 | لا شيء يمنع نصًا ضعيفًا من الوصول إلى PDF | كتاب يُرفض أو يُراجَع من الناشر | `editorial_review_service`: بوابة `passed` تفحص الميزانية، مستوى القراءة (Flesch-Kincaid)، السلامة، تغطية النقاط، اللازمة |
| 41 | اختيار الفكرة كان تخمينًا داخليًا بلا دليل سوق | «فكرة قوية» بلا سند | `market_research_service`: تشبّع + طلب + عناوين متشابهة من بياناتك، مع `confidence` صريح وسقف 65 بلا بيانات |
| 42 | لا قرار مبني على أدلة: كتاب فردي أم سلسلة | خسارة قيمة الملكية الفكرية | `series_service`: 7 أبعاد بأوزان ظاهرة + hooks للجزء التالي + قواعد العلامة |
| 43 | وصفة المشهد كانت عامة لا تصلح لأي محرّك صور | نتائج غير متسقة ووجوه تختلف كل صفحة | `image_prompt_compiler`: لهجة كل محرّك، حد 77 توكن لـ SDXL، negatives، توكن الشخصية أولًا |
| 44 | لا محرّك صور قابل للتوصيل | توقف المصنع عند الصور | `image_engine_service`: a1111 / comfyui / replicate / fal / openai — ويُصرّح بأنه غير مهيّأ بدلًا من الفشل الصامت |
| 45 | لا مسار لرفع دقة رسم صغير إلى 300 dpi | رفض من المطبعة | `print_image_service`: Real-ESRGAN عند توفره، Lanczos + Unsharp بديلًا، ثم fit + CMYK + gate |
| 46 | لا طريقة لاختبار الطبقات الجديدة | إضافات بلا إثبات | 11 اختبارًا جديدًا (المجموع 32) تغطي المدير، الكاتب، المحرر، السوق، السلسلة، المحرّكات، الطباعة، ونقاط الـ API |
| 47 | لا مرجع «أي أداة في أي مرحلة» | المستخدم لا يعرف ماذا يركّب | `docs/TOOLCHAIN.md`: جدول مرحلة→أداة→ترخيص + أوامر تركيب + حدود معلنة |
| 48 | بيانات Kaggle تُحمَّل بلا مكان تُستخدم فيه | Dataset بلا فائدة | `KAGGLE_DATASET_PATH` يُقرأ مباشرة بواسطة `market_research_service` (CSV/JSON/JSONL، بلا pandas) |
| 49 | لا فحص للـ PDF النهائي قبل الإرسال للمطبعة | رفض أو طباعة بمقاس خاطئ | `scripts/preflight.py`: مقاس الصفحات بالمليمتر مقابل المطلوب، ثبات المقاس، OutputIntent/PDF-X، الخطوط، عدد الصور، حكم PASS/PROBLEMS |
| 50 | المخطوط المكتوب لا يصل إلى PDF | الطبقات الجديدة معزولة عن المصنع | `scripts/produce_book.py`: مخطوط → PDF داخلي + غلاف كامل + Metadata + حزمة (يرفض الإخراج إن لم يجتز المحرر) |

| 51 | نطاق اللغات لم يكن محدّدًا: خمس حزم معروضة بلا سياسة | منتج بلا هوية لغوية واضحة | `language_policy` + `OUTPUT_LANGUAGES=en,de,es` (الافتراضي)؛ طلب لغة معطّلة يُرفض بـ 400 مع سبب |
| 52 | `StoryBrief` لا يحمل اللغة، فالكاتب قد يكتب بالإنجليزية لعقد ألماني | مخطوط بلغة خاطئة بلا تحذير | حقل `language` + تعليم صريح في `to_writer_prompt()` + منع اللغات المعطّلة عند بناء العقد |
| 53 | السقالة الحتمية إنجليزية فقط ويمكن أن تُسلَّم كأنها ألمانية/إسبانية | خداع للمستخدم | وضع `offline_en_fallback` + `notice` يشرح أن المخطوط إنجليزي ويطلب ضبط `LLM_*` للغة الأصلية |
| 54 | Flesch-Kincaid يُعرض كأنه دقيق لكل اللغات | قرار تحريري مبني على رقم مضلّل | حقل `reading_grade_language` + ملاحظة أن القيمة تقريبية لغير الإنجليزية |
| 55 | لا تقييم لأدوات التنسيق (n8n) قبل إدخالها | تعقيد بلا فائدة أو مخاطر أمنية | `docs/N8N.md`: مقارنة الخيارين + القاعدة «n8n ينادي ولا يحكم» + طريقة Docker الصحيحة |

| 56 | لا كتب مكتملة تُسلَّم للمستخدم، فقط قطع غيار | لا شيء جاهز للرفع أو الطباعة | `scripts/produce_library.py` + `app/content/library_texts.py`: خمسة كتب (EN/DE/ES/EN-DE/ES-EN) بأغلفة وEPUB وحزم |
| 57 | لا دعم للكتب ثنائية اللغة | سوق كامل مفقود (مغتربون، مدارس لغتين) | `bilingual_service` + `render_bilingual_pdf` (stacked/facing) + تقرير محاذاة + نقطتا API |
| 58 | فحص الكلمات الممنوعة إنجليزي فقط → كلمة «die» الألمانية (أداة تعريف) تُعامل كعنف | رفض كل صفحة ألمانية | قوائم منفصلة لكل لغة (en/de/es) + حدود كلمات + مفردات حسّية لكل لغة |
| 59 | Flesch-Kincaid يُصدر «خطأً» قاطعًا لغير الإنجليزية | رفض نصوص ألمانية/إسبانية سليمة | الدرجة تصبح «تحذيرًا» لغير الإنجليزية مع تنبيه أنها تقريبية |
| 60 | لا مسار Hugging Face رغم طلب المستخدم | لا توليد صور/نثر بلا جهاز قوي | مزوّد `huggingface` للصور + تمرير `HF_TOKEN` للكاتب عبر موجّه HF المتوافق OpenAI |
| 61 | لا طريقة لمقارنة نماذج الكتابة | اختيار النموذج بالحدس | `scripts/bench_writers.py`: نفس العقد على عدة نماذج + درجة المحرر + زمن + نقد أسلوبي |
| 62 | خريطة الطريق مراحل مبهمة بلا معايير قبول | تجاوز مراحل وتداخل قرارات | `docs/MASTER_PLAN.md`: ٧ بوابات + معيار قبول لكل بوابة + جدول مالك الحقيقة + بدائل n8n مفتوحة المصدر |

| 63 | لا طريقة للتأكد أن المستودع رُفع كاملًا (عدّ يدوي لا يُثبت شيئًا) | شك دائم: هل نقص ملف؟ | `scripts/verify_upload.py`: يفحص 101 ملفًا + 67 ملفًا حرجًا + تسرّب الأسرار، محليًا أو عبر GitHub API، ويطبع COMPLETE/INCOMPLETE |

| 64 | الصورة داخل مربع يشغل نصف الصفحة | ليس مستوى دور النشر العالمية | `render_picture_book_pdf`: الرسم يغطي الصفحة كاملة حتى حدّ القص، والنص في لوحة داخل المنطقة الآمنة |
| 65 | لا نشرات مزدوجة (double spread) | ذروة القصة لا تُبنى بصريًا | `book_structure_service`: نشرتان محسوبتان (الذروة + الصورة الختامية) ترسمان من صورة واحدة عريضة عبر الصفحتين |
| 66 | الكتاب ٢٤ صفحة فقط بلا صفحة عنوان/إهداء/كولوفون | لا يشبه كتب الدور | ٣٢ صفحة = ٤ مقدمة + ٢٤ حكاية + ٤ خاتمة (The End، عن المؤلف، السلسلة، الكولوفون) |
| 67 | لا كتاب تلوين لكل قصة | منتج ثانٍ مفقود | `line_art_service` + `render_coloring_book_pdf`: ٢٤ صفحة تلوين بمقاس 8.5×8.5 |
| 68 | لا تحويل إلى فيكتور | خطوط ناعمة/مهترئة عند التكبير | `vectorize()` عبر VTracer (MIT) → SVG، مع بديل صريح إن لم تُثبَّت |
| 69 | الإخراج كان PDF واحدًا | لا رفع على KDP/Etsy ولا نسخة رقمية | لكل طبعة: PDF مطبوع + كتاب تلوين + غلاف كامل + EPUB + `kdp_listing.json` + `etsy_listing.json` + حزمة |
| 70 | لا تحكّم في لغة الطبعة | لا يمكن اختيار إنجليزية/ألمانية/إسبانية/ثنائية | `--only en de es en-de es-en` (الثنائية: صفحة واحدة للغتين) |

Nothing in the original feature list was removed — every service still exists, and all of them
are now reachable from the API.

## Round 4 — the creative chain

The factory could plan, lay out and print, but it could not **write**. Round 4 closes that
gap without touching a single existing route, service signature or default behaviour:

```
idea → market_research (evidence) → series (property) → StoryBrief (contract)
     → story_writer (LLM | scaffold) → editorial_review (gate) → scene prompts
     → image engine (optional) → print prep + gate → existing PDF pipeline
```

Verified: `pytest` **32 passed**, `smoke_test.py` **ALL PASSED**, and the offline scaffold
produces a 32-page manuscript that **passes the editorial gate with 0 errors**.
