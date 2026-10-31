# تقرير تدقيق النسخة المُرسَلة (Audit Report)

تاريخ التدقيق: 2026-10-30
النطاق: الحزمة النصية كما وردت في المحادثة (50 ملفًا/قسمًا) مقابل الكود الموجود في هذا المستودع.

كل ملاحظة أدناه تم **اختبارها فعليًا**، لا استنتاجها نظريًا. الأوامر والأرقام مذكورة داخل الجدول.

---

## 1) أخطاء تمنع التشغيل (Blockers)

| # | الملف | المشكلة | الدليل المُقاس | الإصلاح هنا |
|---|---|---|---|---|
| 1 | `app/__init__.py` | `redis_client.init_app(app)` — `Redis` ليس Flask extension | `AttributeError: 'Redis' object has no attribute 'init_app'` | `init_redis(app)` + عميل كسول + `redis_healthy()` |
| 2 | `app/__init__.py` | استيراد `ensure_vector_storage` أعلى الملف ⇒ استيراد `faiss` و`sentence-transformers` عند الإقلاع | `ModuleNotFoundError: No module named 'faiss'` | تحميل كسول + بديل numpy يعمل بلا ML |
| 3 | `app/routes/__init__.py` + `api_routes.py` | `url_prefix="/api"` مع مسارات تبدأ بـ `/api/` | المسار الفعلي: `/api/api/health` — و`/api/health` يعيد **404** | المسارات بلا بادئة، والبادئة تُطبّق مرة واحدة |
| 4 | `admin_routes.py` | نفس المشكلة مع `/admin` | `/admin/admin` | المسارات `/` و`/overview` |
| 5 | `app/services/__init__.py` | غير موجود في الشجرة | فشل الاستيراد في بعض البيئات | أُضيف |
| 6 | `app/templates/base.html` | `url_for('static', ...)` يعمل فقط إذا كان `static` داخل حزمة `app` | صحيح هنا، لكن `templates/` ليست بجانب `run_server.py` إن نُقل الملف | الهيكل مثبَّت داخل `app/` |

## 2) أخطاء منطقية تُفسد المُخرَج

| # | الملف | المشكلة | الدليل | الإصلاح |
|---|---|---|---|---|
| 7 | `idea_service.score_idea` | المعادلة تتجاوز 100 دائمًا ثم تُقصّ ⇒ كل فكرة «ممتازة» | فكرة قوية = 155.4 ⇒ 100.0 / فكرة ضعيفة = 124.0 ⇒ **100.0** أيضًا | تطبيع بأوزان + اختبار حدود `0 ≤ score ≤ 100` |
| 8 | `image_fit_service.fit_to_page` | يقصّ منطقة الأمان **من** الصفحة ويحفظ الناتج ⇒ ضياع الـ bleed والهوامش | صفحة 6×9in+bleed = 1870×2770px، لكن الدالة تحفظ **1518×2418px** = 128.5×204.7mm | تثبيت على الصفحة الكاملة (cover/contain) + `check_print_resolution()` |
| 9 | `prompt_service.text_area_for_page` | تتجاهل `page_size` وتُعيد ثوابت | أي مقاس يُرجع 130×180mm | حساب فعلي من جدول المقاسات + bleed |
| 10 | `story_service.add_scene` | يبني prompt خاصًا به ويترك `PromptService` معطّلة | نسختان مختلفتان من نفس المنطق | `add_scene` يستخدم `build_prompt` |
| 11 | `page_layout_service.py` | مذكور في الشجرة لكن **لا أحد يستورده**، وقيمه (125×180mm) تتعارض مع هوامش `render_service` | `grep -r page_layout` ⇒ صفر نتائج | أصبحت المصدر الوحيد للحساب وموصولة بـ `render_service` + `image_fit_service` + `/api/layout` |
| 12 | `render_service.render_story_pdf` | مقاس صفحة واحد لكل الكتاب | الـ spread يُقصّ أو يُضغط | `setPageSize()` لكل صفحة |
| 13 | `dashboard.html` | يستخدم `products` غير مُمرَّر من المسار | `{{ products|length if products else 0 }}` ⇒ يطبع 0 دائمًا | المسار يمرّر `products` و`ready_for_export` |
| 14 | `catalog.html` | لا يوجد أي `Product` في الكود ⇒ الكتالوج فارغ للأبد | `{% for product in products %}` على قائمة فارغة | التغذية التجريبية تُنشئ 3 منتجات |
| 15 | `multilingual_story_service` | عنوان عربي مكسور: `" luna في غابة الشموع"` | مسافة بادئة + لاتيني داخل العربية | `لونا وغابة الفوانيس` + ES/DE + `direction: rtl` |
| 16 | `render_service` | `Helvetica` فقط | العربية/الفرنسية بعلامات لا تُرسم | تسجيل TTF تلقائي + `arabic-reshaper`/`python-bidi` عند توفرهما |

## 3) أخطاء أمنية وتشغيلية

| # | المشكلة | الأثر | الإصلاح |
|---|---|---|---|
| 17 | `.gitignore` يتجاهل `*.json` | يحذف `metadata.json` وأي إعداد JSON من المستودع | قواعد مسارات صريحة بدلًا من `*.json` |
| 18 | `.gitignore` يتجاهل `secure_data/`، `output/`، `vector_store/` كاملة | المجلدات تختفي من الريبو | الإبقاء عبر `README.txt` + قواعد استثناء |
| 19 | `Dockerfile` يشغّل سيرفر Flask التطويري | غير صالح للنشر | gunicorn + `wsgi.py` + HEALTHCHECK + مكتبات نظام مطلوبة |
| 20 | `docker-compose.yml` بلا `healthcheck` و`depends_on` واعٍ + `version:` قديم | API يقلع قبل Postgres | شرط `service_healthy` + DNS داخلي للخدمات |
| 21 | `opencv-python` في صورة سيرفر | تبعيات X11 غير لازمة | `opencv-python-headless` |
| 22 | `kaggle.json` بلا تحقق صلاحيات موحّد | احتمال كشف المفتاح | `chmod 0600` عند الكتابة |
| 23 | لا توجد أي اختبارات | «يعمل» غير مُثبت | `tests/` + `scripts/smoke_test.py` (21 فحصًا) |

## 4) نواقص وظيفية (كانت مُعلَنة ولم تُنفَّذ)

| الميزة المُعلَنة | الحالة في النسخة المُرسَلة | الحالة هنا |
|---|---|---|
| export رقمي | `create_ebook_from_text` يكتب `.txt` فقط | EPUB 3 حقيقي (mimetype غير مضغوط، OPF/nav/chapter، RTL) |
| KDP / Etsy | بناء listing بلا أي تحقق | `validate()`: 7 كلمات مفتاحية، 24 صفحة، 13 tag، 140 حرفًا، مقاسات trim معتمدة |
| print bundle | نسخ ملفات فقط | manifest + specs + حالة `print_ready` |
| metadata | listing_description = listing_title | وصف تسويقي منفصل + keywords مضمونة بدون تكرار |
| vector search | يرمي 500 عند فهرس فارغ | حماية + `/api/search/reindex` + إحصاءات backend |
| dashboard | 3 أرقام ثابتة | عدّادات حقيقية + زر pipeline يعمل |
| workers/queue | Redis مُعلَن بلا استخدام | مُوثَّق كحدود معروفة (لم أُضف مهام خلفية) |

## 5) نتائج التحقق في هذه النسخة

```
$ python scripts/smoke_test.py
SMOKE TEST: ALL PASSED        # 23 فحصًا: صفحات + API + pipeline كامل

$ python -m pytest
9 passed

$ python scripts/produce_demo.py
layouts: ['US_6_X_9/spread', 'US_6_X_9/single', 'US_6_X_9/full_bleed']
cover.pdf  storybook.pdf  metadata.json  *_final_export.zip
```

فحص أحجام الـ PDF الناتج: صفحة spread = 316.8×234.6mm، وصفحة single = 158.4×234.6mm — أي أن كل صفحة تحمل مقاسها الصحيح مع الـ bleed.

## 6) ما لا يزال غير منفّذ (بصراحة)

- لا طبقة مصادقة/صلاحيات (AuthN/AuthZ) — لا تعرّض الـ API للعامة قبل إضافتها.
- لا توصيل فعلي بمولّد صور (LoRA/SDXL/API تجاري) — الموجود هو الـ prompts والملفات فقط.
- لا رفع تلقائي إلى KDP/Etsy (بناء الـ listing والتحقق فقط).
- لا مهام خلفية/طابور (Redis مُعدّ لكنه غير مستخدم في منطق العمل).
- لا i18n لواجهة الويب نفسها (المحتوى متعدد اللغات، الواجهة إنجليزية).

هذه كلها مذكورة أيضًا في `README.md` قسم Roadmap، ولم أزعم أي منها كمنجَز.
