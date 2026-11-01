# Market data → commercial decisions (data first)

روzjات. لا كتاب يخرج من المشروع على أساس تخمين: كل قرار تجاري (نيش، عنوان، كلمات SEO)
يُبنى على أرقام من بيانات حقيقية على القرص، ومعها إثبات المصدر.

---

## ١) السلسلة الكاملة

```
Kaggle API (أساسي)  ─┐
                     ├─→ secure_data/datasets/*.csv ─→ MarketResearchService
Open Library (عام)  ─┘        + provenance.json            │
                                                           ├─→ NicheService
                                                           │      ├─ niches (فجوات حقيقية)
                                                           │      ├─ عناوين عمل مفحوصة ضد التشابه
                                                           │      └─ KDP (٧ × ٥٠ حرفًا) + Etsy (١٣ × ٢٠ حرفًا)
                                                           └─→ MetadataService → kdp_listing.json / etsy_listing.json
```

## ٢) مزوّدان، ومصداقية واحدة

| المزوّد | يحتاج مفتاحًا | الإشارة | متى تستخدمه |
|---|---|---|---|
| **Kaggle** (أساسي) | `KAGGLE_USERNAME` + `KAGGLE_KEY` | `signal = bestsellers` — رتب مبيعات وتقييمات | للتحقق التجاري النهائي |
| **Open Library** (عام) | لا | `signal = catalogue` — عناوين ومواضيع وعدد طبعات | للبدء فورًا أو عند غياب مفاتيح Kaggle |

`MarketDataService` يكتب `secure_data/datasets/provenance.json` في كل التقاط:

```json
{ "source": "openlibrary", "signal": "catalogue", "fetched_at": "2026-10-31T17:45:16Z",
  "rows": 2809, "files": [".../openlibrary_children_20261031.csv"],
  "signal_note": "Open Library is a catalogue — not sales data. Use Kaggle bestsellers for sales ranking." }
```

**قاعدة صارمة:** إذا لم توجد بيانات، يعلن النظام `basis = "curated_baseline"` ويخفض سقف الثقة،
ولا يقدّم أي رقم كأنه بيانات سوق — لا في التقرير ولا في الإعلان.

## ٣) الأوامر

```bash
python scripts/market_brief.py --fetch auto          # Kaggle إن كان مضبوطًا، وإلا Open Library
python scripts/market_brief.py --fetch kaggle        # بيانات مبيعات (يحتاج المفتاحين)
python scripts/market_brief.py --fetch openlibrary   # كتالوج عام فقط
python scripts/market_brief.py --top 8               # تحليل ما هو موجود على القرص
python scripts/market_brief.py --title "The Lantern Who Waited"   # قياس عنوان تختاره
```

المخرجات:

| الملف | المحتوى |
|---|---|
| `output/market/market_report.json` | الأدلة الكاملة: الطلب، التشبّع، الفجوات، العناوين، SEO، المصدر |
| `output/market/niche_brief.md` | ورقة قرار من صفحة واحدة |

## ٤) كيف تُحسب الأرقام

| المقياس | المعادلة (كما في الكود) |
|---|---|
| **التشبّع** | نسبة العناوين في العيّنة التي تحتوي نمط النيش (مثال: `bedtime` في ١٦.٠٪ من ٢٨٠٩ عنوانًا) |
| **إشارة الطلب** | مجموع تكرارات كلمات النيش في العيّنة |
| **الفرصة** | `demand / (1 + saturation × 12)` — طلب عالٍ مع تشبّع منخفض = فرصة |
| **المنافسة على العنوان** | تشابه Jaccard ≥ 0.45 بين كلمات عنوانك وعناوين السوق (تُرفض العناوين المتصادمة) |
| **درجة السوق** | `42% (1−تشبّع) + 33% تميّز + 25% طلب/منافسة` — بحد أقصى ١٠٠ |

الضوضاء مُستثناة عمدًا (`fiction`, `juvenile`, `published`, `editions`, `literature`…) لأنها
مصطلحات فهرسة لا نيّة شراء.

## ٥) نتائج حقيقية من تشغيل فعلي (Open Library، ٢٨٠٩ عنوانًا)

| الرف | التشبّع | إشارة الطلب | القراءة |
|---|---|---|---|
| `moving_house` | 0.2% | 430 | رف مفتوح |
| `fear_of_dark` | 1.6% | 238 | رف مفتوح |
| `new_sibling` | 4.5% | 325 | رف مفتوح |
| `first_day_school` | 4.5% | 2952 | رف مفتوح بطلب عالٍ — أفضل فرصة |
| `adventure_quest` | 15.3% | 541 | مزدحم |
| `bedtime_sleep` | 16.0% | 1051 | مزدحم |
| `talking_animals` | 16.2% | — | الأكثر ازدحامًا |

عناوين العمل الناتجة (بعد فحص التصادم): `Nora and the Brave Bear` · `When the Cat Waits` ·
`The Dog Who Would Not Listen` — كل عنوان مبني على كلمات موجودة فعلًا في السوق ومفحوص ضد التشابه.

## ٦) الربط بالإنتاج

```bash
python scripts/market_brief.py --fetch auto     # ١) بيانات + ورقة قرار
python scripts/produce_library.py               # ٢) يستخدم كلمات السوق تلقائيًا للطبعات الإنجليزية
python scripts/produce_library.py --no-market   #    أو تجاهلها صراحةً
```

`produce_library` يبني كلمات SEO من **عنوان الكتاب نفسه** + مفردات السوق (لا ينسخ عنوانًا آخر)،
ثم يمرّرها إلى `MetadataService` فتظهر في `metadata.json` و`kdp_listing.json` و`etsy_listing.json`.

## ٧) الحدود الصادقة

- **Kaggle ليس ضمان مبيعات.** أعلى مبيعًا لا يساوي أعلى ربحًا؛ والبيانات تاريخية.
- **Open Library كتالوج لا مبيعات**: يقيس المنشور لا المشترى. لذلك `signal = catalogue`.
- **لا كشط للمتاجر** (يخالف شروط Amazon/Etsy) ولا اتصال حيّ بواجهاتها.
- **Etsy tags ≤ ٢٠ حرفًا، KDP keywords ≤ ٥٠ حرفًا و٧ خانات** — الكود يفرضها وتُختبر آليًا.
- **لا يتّخذ النظام قرار النشر بدلًا عنك**: يعطي الأدلة والدرجة، والقرار لك.
