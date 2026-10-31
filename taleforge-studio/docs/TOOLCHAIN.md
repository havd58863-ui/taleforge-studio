# عدة العمل الاحترافية — أداة مفتوحة المصدر لكل مرحلة

> هذا الملف يجيب سؤالًا واحدًا: **في كل مرحلة، ما هي الأداة المهنية التي يستخدمها الناشرون فعلًا،
> وهل هي مفتوحة المصدر، وكيف تُركَّب؟**
>
> القاعدة التي بُني عليها المشروع: **كل مرحلة تُسلِّم مخرَجًا محددًا للمرحلة التالية**، ولا مرحلة
> تعمل في الهواء. والنتيجة النهائية واحدة: **كتاب أطفال بمستوى دور النشر العالمية، جاهز للطباعة والرفع.**

---

## 0) جدول سريع: المرحلة → الأداة → الترخيص

| # | المرحلة | الأداة الاحترافية | الترخيص | داخل المشروع؟ |
|---|---|---|---|---|
| 1 | بحث السوق واختيار الفكرة | بيانات Kaggle + `market_research_service` | بيانات: حسب كل Dataset / الكود: مِلك المشروع | ✅ منفَّذ |
| 2 | قرار: كتاب فردي أم سلسلة | `series_service` (تقييم 7 أبعاد) | مِلك المشروع | ✅ منفَّذ |
| 3 | المدير الفني (Brief صارم) | `story_director_service` | مِلك المشروع | ✅ منفَّذ |
| 4 | الكتابة الحقيقية | Ollama + Qwen2.5 / Llama 3.3 (أو أي API متوافق OpenAI) | Qwen2.5: Apache-2.0 · Llama: Llama Community | ✅ منفَّذ (`llm_client`) |
| 5 | التحرير الصارم | `editorial_review_service` (+ نقد LLM اختياري) | مِلك المشروع | ✅ منفَّذ |
| 6 | توليد المشاهد | ComfyUI أو Forge + SDXL / SD 3.5 / Flux | ComfyUI: GPL-3.0 · Forge: AGPL-3.0 · SDXL: OpenRAIL++-M | ✅ محوِّل جاهز (`image_engine_service`) |
| 7 | ثبات الشخصية بين الصفحات | IP-Adapter + ControlNet + LoRA خاص بك (kohya_ss) | Apache-2.0 / MIT | ✅ prompts + وصفات، التدريب خارجيًا |
| 8 | رفع الدقة للطباعة | Real-ESRGAN (ncnn-vulkan) | BSD-3-Clause | ✅ مربوط بـ `REALESRGAN_BIN` |
| 9 | PDF والمطبعية | ReportLab + Andika/Amiri | ReportLab: BSD · الخطوط: OFL 1.1 | ✅ منفَّذ |
| 10 | فحص ما قبل الطباعة (Preflight) | Ghostscript + qpdf + veraPDF + pdffonts | AGPL / Apache-2.0 / GPL | ✅ فحص DPI/CMYK مدمج، والباقي أوامر جاهزة أدناه |
| 11 | الرفع للنشر | KDP / Etsy (يدويًا) | — | ✅ ملفات جاهزة، لا رفع تلقائي |

---

## 1) المرحلة 1 — بحث السوق: «أي فكرة تُبَاع؟»

**المشكلة الحقيقية:** أكثر الكتب لا تفشل لأنها سيئة، بل لأنها تشبه 200 كتاب موجود.

**ما ينفّذه المشروع:** `app/services/market_research_service.py`

```
secure_data/datasets/*.csv  →  فهرسة (عناوين + أوصاف + تصنيفات + تقييمات)
        ↓
تشبّع كل «تروب» (bedtime / unicorn / first day of school / …)
        ↓
market_score (0-100) + verdict + evidence + confidence
```

**قاعدة الصدق المدمجة:** إذا لم تُحمِّل أي بيانات سوق، يعمل النظام لكنه يصرّح
`confidence = low` ويسقّف النتيجة عند 65 — **لا يبيعك وهمًا**.

**كيف تجيب البيانات (مجانًا، وبدون كسر شروط المتاجر):**

1. أنشئ مفتاح Kaggle (Account → Create New API Token).
2. ضع `KAGGLE_USERNAME` و`KAGGLE_KEY` في **GitHub Secrets** (أو في `.env` محليًا فقط).
3. حمّل Dataset مثل «childrens books bestsellers» أو «Goodreads books»:

```bash
python scripts/kaggle_sync.py --search "childrens books bestsellers"
python scripts/kaggle_sync.py --download <owner/dataset> --dest secure_data/datasets
python scripts/ideate.py --demo --datasets secure_data/datasets
```

> **لا يوجد كشط (scraping) لموقع Amazon أو Etsy.** الكشط يخالف شروط المتاجر ويعطيك أرقامًا
> تختفي بعد أسبوع. البيانات التي تُنزّلها مرة واحدة وتبقى ملكك هي الطريقة المهنية.

**توسعة اختيارية مفيدة:** Google Books API (مجانية بحد استخدام) لإحصاء عدد العناوين
المتشابهة في موضوع معيّن.

---

## 2) المرحلة 2 — كتاب فردي أم سلسلة؟

الناشرون لا يشترون «عنوانًا»، بل يشترون **ملكية فكرية (Property)**.

`app/services/series_service.py` يقيّم سبعة أبعاد بأوزان ظاهرة:

| البُعد | الوزن | لماذا |
|---|---|---|
| rفرد مصاحب ثابت (recurring cast) | 20 | الطفل يريد لقاءه مرة أخرى |
| قواعد عالم قابلة للكسر | 20 | كل جزء = قاعدة تُكسَر بطريقة جديدة |
| محرّك حلقات (episodic engine) | 15 | مشكلة جديدة في نفس العالم |
| رمز تجاري (lantern / key / star) | 15 | يُعرَف على الرف في 3 ثوانٍ |
| سلّم أعمار (age ladder) | 10 | 0-3 ← 4-8 ← 6-9 بنفس العلامة |
| تنوّع بصري (6 أماكن للأغلفة) | 10 | سلسلة تحتاج 6 أغلفة مختلفة |
| طلب السوق على السلاسل | 10 | من بيانات المرحلة 1 |

النتيجة: `single_book` / `sequel_optional` / `trilogy` / `open_series` — **بقرار مكتوب وأسبابه**.

```bash
python scripts/ideate.py --demo
```

---

## 3) المرحلة 3 — المدير الفني: `StoryBrief`

مدير فني محترف لا يقول «اكتب قصة جميلة». يعطي **عقدًا**:

- 32 صفحة، 25–60 كلمة للصفحة، ميزانية إجمالية محسوبة.
- **9 نقاط سرد (beats)** بترتيب صارم: hollow → inciting → refusal → first_attempt →
  dark_moment → turn → climax → resolution → image_of_hope، ولكل نقطة صفحاتها ودرجة حرارتها.
- **لازمة (refrain)** تظهر **3 مرات بالضبط**، بنفس الصياغة.
- **دستور بصري (style bible)**: لوحة ألوان، نوع الخط، الملمس، الإضاءة، الوجوه.
- **قائمة محظورات**: لا وعظ، لا كلمات مؤذية، لا POV متغيّر، لا زمن متغيّر.

`app/services/story_director_service.py` — ومخرجاته تُغذّي الكاتب والمحرر ومولّد الصور معًا.

---

## 4) المرحلة 4 — الكاتب الحقيقي

**مبدأ التصميم:** الكاتب لا يكتب «قصة»، بل **ينفّذ Brief**. لذلك لا يخرج النص عن الميزانية
أو الترتيب أو اللازمة.

| الخيار | الترخيص | متى تختاره |
|---|---|---|
| **Ollama + Qwen2.5:14b / 32b** | Apache-2.0 (معظم الإصدارات) | خصوصية كاملة، جهازك، مجاني |
| **Ollama + Llama 3.3:70b** | Llama Community License | جودة نثر أعلى، يحتاج ذاكرة كبيرة |
| **أي API متوافق OpenAI** (OpenAI / Together / DeepInfra / Groq) | حسب المزوّد | لا تحتاج كرت شاشة قوي |

```bash
# محليًا (موصى به للبداية)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:14b

# في .env فقط (وليس في git)
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen2.5:14b
LLM_API_KEY=ollama

python scripts/write_book.py --demo
```

**بدون أي مفتاح** يعمل المشروع بـ **سقالة حتمية (offline scaffold)** تكتب 32 صفحة داخل
الميزانية وتنجح من بوابة التحرير — لكنها **سقالة لضمان أن المصنع يعمل**، وليست بديلًا عن كاتب.
وهذا مذكور صراحةً في مخرجات السكربت (`writer mode : offline scaffold`).

---

## 5) المرحلة 5 — المحرر الصارم

`app/services/editorial_review_service.py` — يمنع النشر عند:

| الفحص | النوع |
|---|---|
| عدد الكلمات لكل صفحة داخل الميزانية | ❌ خطأ |
| عدد الجمل ≤ الحد المسموح للعمر | ❌ خطأ |
| مستوى القراءة (Flesch-Kincaid) فوق الهدف | ❌ خطأ |
| اللازمة ≠ 3 مرات | ❌ خطأ |
| كلمات غير مناسبة للأطفال | ❌ خطأ |
| نقطة سرد بلا صفحة | ❌ خطأ |
| وصف مشهد ناقص (المُصمّم لن يرسم) | ❌ خطأ |
| جملة طويلة / مفردات صعبة / تكرار بدايات الجمل / حوار زائد | ⚠️ تحذير |

النتيجة: `score` + `passed` + `errors` + `warnings` + `metrics`. **الكتاب لا يُوطَّن إلا إذا `passed = true`.**

اختياريًا: نقد أسلوبي من LLM (`--llm-review`) — ملاحظات محددة بأرقام صفحات، **لا يعيد كتابة الكتاب**.

---

## 6) المرحلة 6 — توليد المشاهد بأقوى النماذج

### البرامج (مفتوحة المصدر)

| الأداة | الترخيص | لماذا |
|---|---|---|
| **ComfyUI** | GPL-3.0 | تحكّم كامل، سلاسل LoRA/ControlNet، إعادة إنتاج بنفس الـ seed |
| **Stable Diffusion WebUI Forge** | AGPL-3.0 | أسرع في التجربة، API بسيط (`/sdapi/v1/txt2img`) |
| **kohya_ss** | Apache-2.0 | تدريب LoRA لشخصيتك (أهم عامل في الثبات) |
| **chaiNNer** | MIT | واجهة رسومية لرفع الدقة والمعالجة |

### النماذج — وانتبه للترخيص التجاري

| النموذج | الترخيص | ملاحظة للاستخدام التجاري |
|---|---|---|
| **SDXL** وأبناؤه (Illustrious / DreamShaper) | CreativeML OpenRAIL++-M | ✅ مسموح تجاريًا مع قيود استخدام |
| **SD 3.5 Large/Medium** | Stability Community License | ✅ مجاني حتى سقف إيرادات سنوي محدد |
| **FLUX.1 [schnell]** | Apache-2.0 | ✅ تجاري بلا قيود تقريبًا |
| **FLUX.1 [dev]** | Non-Commercial | ❌ لا للكتب المبيعة (يحتاج ترخيص Black Forest Labs) |

**الخلاصة العملية لكتاب أطفال تجاري:** SDXL/Illustrious + LoRA خاص بشخصيتك،
أو SD 3.5، أو FLUX schnell — وليس FLUX dev.

### الطريق الأسهل بلا كرت شاشة: Hugging Face

مفتاح واحد (`HF_TOKEN`) يشغّل **الكاتب والرسّام** معًا:

```env
HF_TOKEN=hf_...                                            # Secrets فقط
LLM_PROVIDER=huggingface
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct                        # أو DeepSeek-V3 / Llama-3.3-70B
IMAGE_PROVIDER=huggingface
IMAGE_MODEL=black-forest-labs/FLUX.1-schnell               # Apache-2.0 — آمن تجاريًا
```

- الكاتب يمرّ عبر `router.huggingface.co/v1` (متوافق OpenAI) — نفس كود المشروع بلا تعديل.
- الصور عبر Inference Providers، والكود يجرّب `router` ثم `api-inference` تلقائيًا.
- **انتبه للتراخيص:** `FLUX.1-schnell` (Apache-2.0) ✅ تجاري · `FLUX.1-dev` ❌ غير تجاري · SDXL ✅ OpenRAIL++-M.
- الاختيار بالقياس: `python scripts/bench_writers.py --provider huggingface --target ...`

### الوصفة لكل مشهد (هي التي تصنع الاتساق)

`app/services/image_prompt_compiler.py` يجمع أربعة مصادر في نص واحد:

1. الحدث والكاميرا والإضاءة والمزاج.
2. **توكن الشخصية** (نفس الوجه في كل صفحة): `[luna_ref: soft oval face, curly brown hair, …]`
3. **الدستور البصري** من المدير الفني (ألوان/خط/ملمس/وجوه).
4. **لهجة المحرّك**: SDXL يقطع عند 77 توكن (نحترم الحد ونحفظ الشخصيات أولًا)،
   Midjourney يحتاج `--ar` و`--no`، وDALL·E لا يقبل negative prompt (نُدمج المحظورات في النص).

```bash
python scripts/generate_scenes.py --book output/book.json --engine sdxl
python scripts/generate_scenes.py --book output/book.json --engine sdxl --generate
```

للتشغيل التلقائي ضع في `.env`:

```bash
IMAGE_PROVIDER=a1111            # أو comfyui / replicate / fal / openai
IMAGE_BASE_URL=http://127.0.0.1:7860
IMAGE_MODEL=sdxl
# IMAGE_API_KEY=...            # لـ replicate / fal / openai
# IMAGE_WORKFLOW=secure_data/comfy_workflow.json   # لـ comfyui
```

**ثبات الشخصية عمليًا (بالترتيب):** ورقة شخصية (turnaround) → LoRA مُدرَّب → IP-Adapter
للمرجع → ControlNet للوضعية → نفس الـ seed ونفس الوصف. **بدون LoRA، الثبات يبقى تقديريًا.**

---

## 6.5) كتاب التلوين: خطوط + تحويل إلى فيكتور

| الأداة | الترخيص | الدور |
|---|---|---|
| **`line_art_service`** (داخل المشروع) | مِلك المشروع | استخراج حدود نظيفة، تكثيف الخطوط للأطفال، أبيض/أسود نقي |
| **VTracer** (`pip install vtracer`) | MIT | تحويل raster → SVG حقيقي (نفس محرّك VTracer الشهير) |
| **potrace** | GPL-2.0 | بديل كلاسيكي للأبيض/أسود |
| **ImageMagick** | ImageMagick License | معالجة دفعية (تحجيم، فصل ألوان، تنسيقات) |
| **Krita / Inkscape** | GPL-3.0 | تنظيف يدوي وضبط الخطوط قبل الطباعة |

```bash
pip install vtracer
python scripts/produce_library.py --only en     # يولّد كتاب التلوين + ٢٤ SVG تلقائيًا
```

**قاعدة الجودة:** صفحة التلوين ليست «صورة باهتة». هي خطوط **مغلقة** يمكن للطفل ملؤها،
بسماكة ≥ 3 px عند 300 dpi، وبلا ضوضاء. المشروع يقيس نسبة الحبر ويتحقق منها في الاختبارات.

## 7) المرحلة 7 — رفع الدقة إلى 300 dpi

| الأداة | الترخيص | أمر |
|---|---|---|
| **Real-ESRGAN ncnn-vulkan** | BSD-3-Clause | يُشغَّل من المشروع عبر `REALESRGAN_BIN` |
| **waifu2x** | MIT | بديل خفيف |
| **chaiNNer** | MIT | للمعالجة الدفعية بواجهة |

```bash
REALESRGAN_BIN=/opt/realesrgan/realesrgan-ncnn-vulkan
python scripts/print_prep.py --image art.png --trim US_6_X_9
```

بدون الأداة: المشروع يرفع بـ Lanczos + Unsharp Mask — **مقبول لكنه ليس مثاليًا**، ويُصرّح بذلك
في مخرجات `upscaled`.

---

## 8) المرحلة 8 — المطبعية و PDF

- **ReportLab** (BSD) لتوليد PDF من الصفر — نسخ A4/Letter/Trim، bleed، علامات قص.
- **Andika** (OFL) للاتينية — مصمّم لتعليم القراءة (شكل الحروف a/g).
- **Amiri** (OFL) للعربية — نسخ قابل للطباعة، تشكيل صحيح.
- بدائل احترافية: **Pango + Cairo** (LGPL) أو **HarfBuzz** مباشرة لتشكيل معقّد جدًا.

المشروع ينفّذ: justify + hyphenation (pyphen) + widow control + تصغير تلقائي + إرجاع الفيض،
وطول سطر 9pt كحد أدنى — وهذا ما يمنع أكثر أسباب الرفض شيوعًا.

---

## 9) المرحلة 9 — Preflight: قبل أن تُرسل للمطبعة

المشروع يفحص **DPI الفعلي / التباين / التعريض / القص / الحِدّة / السaturation** ويعطي `gate`،
وينفّذ تحويل CMYK عند الطلب (`--cmyk`) مع إدارة ICC عند توفّر البروفايل.

**فحص مدمج بلا أي تثبيت:**

```bash
python scripts/preflight.py --pdf output/luna_and_the_lantern_forest_interior.pdf --trim US_6_X_9
# يطبع: عدد الصفحات، المقاس الفعلي بالمليمتر مقابل المطلوب، وجود PDF/X، الخطوط، عدد الصور، والحكم النهائي
```

الفحص الكامل (أدوات خارجية مجانية):

```bash
# الخطوط مضمّنة؟ (poppler)
pdffonts book.pdf

# مستند سليم بنيويًا؟
qpdf --check book.pdf

# PDF/X-1a:2001 (ما تطلبه معظم المطابع) — Ghostscript
gs -dPDFX -dBATCH -dNOPAUSE -sDEVICE=pdfwrite \
   -sColorConversionStrategy=CMYK -dProcessColorModel=/DeviceCMYK \
   -sOutputFile=book_x.pdf book.pdf

# فحص PDF/X وPDF/A بدقة (veraPDF)
verapdf --format text book_x.pdf
```

> **حقيقة يجب قولها:** CMYK بدون بروفايل ICC من مطبعتك = تقريب. ألوانك لن تُطابق 100%
> إلا ببروفايل الجهاز (مثل ISO Coated v2 من ECI). المشروع يذكر ذلك في كل تقرير.

---

## 10) المرحلة 10 — النشر

المخرج جاهز ومُقاس، لكن **الرفع لا يحدث تلقائيًا** (لا يوجد API عام للنشر على KDP،
والأتمتة عبر المتصفح تخالف الشروط وتعرّض الحساب للحظر). المشروع يعطيك:

- `storybook.pdf` (316.8mm عرض للـ spread، 300 dpi، bleed).
- `cover_wrap.pdf` (غلاف كامل: خلفي + كعب محسوب + أمامي).
- `metadata.json` + قائمة KDP/Etsy مع الفحص.
- `*_final_export.zip` جاهز للرفع.

---

## 10.5) نطاق اللغات: الإنجليزية والألمانية والإسبانية فقط

```
OUTPUT_LANGUAGES=en,de,es      # الافتراضي
ALLOW_EXTRA_LANGUAGES=0        # 1 = يعيد تفعيل كل الحزم الموجودة (fr/ar)
```

- حزم `fr` و`ar` **بقيت في الكود** ولم تُحذف (لا كسر لأي وظيفة)، لكنها **معطّلة** ولن تُنتج.
- محرّك العربية (تشكيل RTL) باقٍ كإمكانية تقنية، لكن مخرجاته خارج نطاق المنتج.
- `StoryBrief` يحمل حقل `language` ويُصدر تعليمًا صريحًا للكاتب: «اكتب بالإنجليزية/الألمانية/الإسبانية الأصلية لا ترجمةً».
- مستوى القراءة (Flesch-Kincaid) معاير للإنجليزية؛ لألمانيا/إسبانيا يُعدّه المحرر **تقريبًا** ويطلب مراجعة ناطق أصلي.

## 11) المتغيّرات البيئية الجديدة (كلها اختيارية)

| المتغيّر | الافتراضي | الوظيفة |
|---|---|---|
| `LLM_PROVIDER` | (فارغ) | `ollama` أو `openai` |
| `LLM_BASE_URL` | — | عنوان الخدمة (مثل `http://127.0.0.1:11434/v1`) |
| `LLM_MODEL` | — | اسم النموذج |
| `LLM_API_KEY` | — | مفتاح (لا يُرفع إلى git) |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` / `LLM_TEMPERATURE` | 120 / 2 / 0.8 | تحكّم |
| `IMAGE_PROVIDER` | (فارغ) | `a1111` / `comfyui` / `replicate` / `fal` / `openai` |
| `IMAGE_BASE_URL` | — | عنوان الخدمة المحلية |
| `IMAGE_MODEL` | — | اسم النموذج أو نسخة Replicate |
| `IMAGE_API_KEY` | — | مفتاح (Secrets فقط) |
| `IMAGE_WORKFLOW` | — | مسار workflow لـ ComfyUI |
| `REALESRGAN_BIN` | — | مسار أداة رفع الدقة |
| `KAGGLE_DATASET_PATH` | `./secure_data/datasets` | مجلد بيانات السوق |

بلا أي متغيّر: المشروع يعمل كاملًا في الوضع الحتمي (بيانات أساسية، سقالة، تخطيط، PDF، فحص جودة).

---

## 12) الأوامر الكاملة بالترتيب

```bash
# 1) القرار: هل الفكرة تستحق؟ فردي أم سلسلة؟
python scripts/ideate.py --demo --datasets secure_data/datasets

# 2) الكتابة + بوابة التحرير (يفشل الأمر إن لم يجتز البوابة)
python scripts/write_book.py --demo --out output/book.json

# 3) وصفات المشاهد لكل صفحة (ثم التوليد إن توفّر محرّك صور)
python scripts/generate_scenes.py --book output/book.json --engine sdxl

# 4) تجهيز الرسم للطباعة + إثبات بالقياس
python scripts/print_prep.py --image output/scenes/page_001.png --trim US_6_X_9

# 5) الكتاب المكتوب ← PDF داخلي + غلاف كامل + Metadata + حزمة رفع
python scripts/produce_book.py --book output/book.json

# (اختياري) العرض التجريبي القديم بلا تغيير
python scripts/produce_demo.py
```

---

## 13) ما لا يفعله المشروع (بصراحة تامة)

| ليس موجودًا | لماذا | البديل |
|---|---|---|
| رسم الصور داخله | يحتاج GPU ونموذجًا ثقيلًا؛ أُبقِي خيارًا عبر `IMAGE_PROVIDER` | ComfyUI/Forge محليًا أو API |
| نشر تلقائي على KDP/Etsy | لا API عام، والأتمتة تخالف الشروط | ملفات جاهزة + رفع يدوي |
| ضمان «جودة فنية» بمجرد 300 dpi | 300 dpi = كثافة طباعة، وليست جمالًا | مراجعة بشرية + LoRA للشخصية |
| نص عربي أصلي بقلم LLM بلا مراجعة | النماذج تخطئ في النحو والإيقاع أحيانًا | `editorial_review_service` + مراجعة بشرية |
| تنبؤ دقيق بالمبيعات | لا أحد يملكه؛ حتى الناشرون يخمّنون | بيانات سوق + تشبّع + تمييز، والقرار لك |

هذا هو **المعيار الذي لا يُتنازل عنه**: أدوات صحيحة، قياسات حقيقية، وحدود معلنة — لا وعود.
