# كيف «يكتب» المشروع القصة — المراحل بالتفصيل

> **تحديث (الجولة الرابعة):** الطبقة الناقصة **أُضيفت**. أصبح في المشروع الآن:
> `story_director_service` (عقد صارم) + `story_writer_service` (كاتب LLM مع بديل حتمي) +
> `editorial_review_service` (بوابة تحرير) + `market_research_service` و`series_service`
> (قرار السوق والسلسلة) + `scripts/produce_book.py` الذي يحوّل المخطوط إلى PDF وغلاف وحزمة.
> راجع `docs/TOOLCHAIN.md`. الفقرة التالية محفوظة كتاريخ للتغيير.
>
> **الخلاصة أولًا (بصراحة):** المشروع **لا يؤلّف نثرًا أصليًا** بنفسه اليوم. هو يبني
> **هيكل القصة** (فكرة → شخصيات → مشاهد → وصف بصري → صفحة مطبوعة) ويكتب **نصوصًا جاهزة
> معدّة يدويًا** بخمس لغات. توليد النثر لأي فكرة جديدة يحتاج طبقة إضافية
> (`story_writer_service`) — القسم 6 يشرح كيف تُضاف دون تغيير أي شيء قائم.

---

## 1) خريطة المراحل

```
[1] بنك الأفكار        idea_service.generate_candidates()      → StoryIdea[]
        │
        ▼  تقييم
[2] بوابة القرار        idea_service.score_idea(idea)           → score 0-100 + قرار
        │
        ▼  اعتماد الفكرة
[3] سجل القصة           story_service.create_story(idea)         → جدول stories
        │
        ├──▶ [4] bible الشخصيات  add_character()                 → جدول characters
        │
        └──▶ [5] المشاهد          add_scene()                    → جدول scenes
                    │
                    ▼
[6] وصفة الرسم          prompt_service.build_prompt()            → prompt + negative + palette
        │
        ▼
[7] حساب الصفحة         page_layout_service.build_layout()        → single / spread / full_bleed
        │
        ▼
[8] التنضيد             text_layout_service.draw_block()          → سطور + فيض + أحجام
        │
        ▼
[9] الإخراج             render_service + metadata_service         → PDF + metadata.json
        │
        ▼
[10] التسويق            amazon_kdp_service / etsy_service          → listing + تحقق
```

---

## 2) المرحلة 1–2: الفكرة والقرار

**الملف:** `app/services/idea_service.py`

كل فكرة `StoryIdea` تحمل 13 حقلًا: العنوان، الفكرة، النوع، العمر، المكان، العالم، الصراع
المركزي، النواة العاطفية، القيمة التعليمية، وأربع درجات (أصالة/سوق/بصري/جدة).

التقييم الحالي:

```
quality       = (أصالة×0.40 + سوق×0.30 + بصري×0.15 + جدة×0.15) / 1.0
theme_bonus   = min(15, مجموع إشارات القيم × 0.5)     # kindness/courage/empathy...
setting_bonus = min(5,  إشارات المكان × 0.4)          # forest/magic/river...
score         = min(100, quality×0.80 + theme_bonus + setting_bonus)
```

النتيجة الفعلية الآن على الفكرتين المدمجتين:

| الفكرة | quality | bonus | **النتيجة** | القرار |
|---|---|---|---|---|
| Luna and the Lantern Forest | 86.6 | 15 + 5 | **89.28** | Strong concept |
| Mila and the River of Lost Wishes | 83.25 | 10 + 2.8 | **79.40** | Viable with refinement |
| (اختبار) فكرة ضعيفة | 42.75 | 0 | **34.20** | Needs rework |

> **إصلاح جوهري:** كانت الأوزان تجمع 1.2 فتصبح كل فكرة 100.0 («Strong» دائمًا).
> صُحّحت إلى مجموع 1.0 + مكافآت محدودة، وأُضيف اختبار انحدار (`test_idea_scores_discriminate`)
> يمنع تكرار الخطأ.

حد القبول: `score ≥ 75` = قابلة للإنتاج.

---

## 3) المرحلة 3: سجل القصة

**الملف:** `app/services/story_service.py` → `create_story()`

يُخزَّن في جدول `stories`: العنوان، الفكرة، النوع، المكان، العمر (min/max)، اللغة.
هذا السجل هو «العقد» الذي تبنيه بقية المراحل عليه.

---

## 4) المرحلة 4: bible الشخصيات

**الدالة:** `add_character(name, role, personality, visual_summary, values, flaws, strengths, emotional_arc)`

كل شخصية تأخذ **token ثبات** يُحقن في كل مشهد لكي لا يتغيّر شكلها بين الصفحات:

```
[luna_ref: soft oval face, curly brown hair, forest green dress, small brass lantern]
[pip_ref:  palm-sized glowing creature, amber light, translucent wings]
```

هذا أهم ما يمنع «الطفلة نفسها» من أن تصبح طفلة مختلفة في الصفحة 7 — وهو أكبر مشكلة في
كتب الأطفال المولّدة آليًا.

---

## 5) المرحلة 5–6: المشاهد ووصفة الرسم

**الدالة:** `add_scene(title, summary)` — وهي **المرحلة الوحيدة التي يكتب فيها النظام نصًا
جديدًا**، ومصدره أنت (ملخّص المشهد بجملة واحدة بالإنكليزية).

من الجملة الواحدة يستنتج `PromptService`:

| الاستنتاج | القاعدة | مثال فعلي |
|---|---|---|
| النمط | وجود forest/magic → `storybook_whimsical` | `storybook_whimsical` |
| المزاج | hope/sunrise → `hopeful` | `hopeful` |
| الإضاءة | sunrise/dawn → `soft_golden_morning_light` | `soft_golden_morning_light` |
| نوع الصفحة | wide/forest → `spread`، finale → `full_bleed` | `spread` |
| الكاميرا | close/face → `close_up`، forest/sky → `wide_shot` | `wide_shot` |
| التكوين | spread → `wide_background_with_primary_subject_balanced_center` | ✔ |
| اللوحة اللونية | forest → `#7AAE72 #D9E7AD #F5D58C #2E4A3A` | ✔ |

الناتج prompt حقيقي مُخزَّن في قاعدة البيانات (مثال مشهد 1):

```
Whispering Forest, Luna enters the magical forest at sunrise carrying a glowing lantern;
wide cinematic shot., premium children's book illustration, storybook_whimsical, hopeful,
soft_golden_morning_light, wide_shot, wide_background_with_primary_subject_balanced_center,
soft palette #7AAE72, #D9E7AD, #F5D58C, #2E4A3A, clean anatomy, expressive faces,
storybook quality, gentle emotional clarity, highly detailed, safe text area,
negative space for text, polished print-ready illustration
```

و`negative_prompt` ثابت يحمي من الأخطاء الشائعة: `blurry face, distorted anatomy, extra limbs,
duplicate hands, ... text covering face`.

---

## 6) أين «النص»؟ وما الذي يجب إضافته ليصبح تأليفًا حقيقيًا

### الحالة الحالية
`multilingual_story_service.py` يحتوي **3 فقرات جاهزة لكل لغة** (en/ar/fr/es/de)
لنفس القصة. مفيدة كـ sample وكقالب اختبار، لكنها **ليست توليدًا** لأي فكرة جديدة.

### الطبقة الناقصة: `story_writer_service`
لتوليد نثر حقيقي لأي فكرة، أضف خدمة بنفس نمط الخدمات الموجودة:

```python
class StoryWriterService:
    PARAMS = dict(age_band="4-8", pages=32)
    WORDS_PER_PAGE = {"4-8": (25, 60), "8-12": (60, 120)}   # ميزانية كلمات لكل صفحة

    def write(self, story, characters, beats) -> list[Page]:
        ...
```

شرطها الوحيد أن تُخرج نفس العقد الحالي: `list` من نصوص الصفحات + ملخّص مشهد لكل صفحة.
بذلك تعمل مع بقية المراحل (prompt → layout → PDF) **دون تغيير أي ملف آخر**.

قواعد جودة يجب أن تلتزمها الطبقة الجديدة (معايير كتب الأطفال):
1. **ميزانية الكلمات لكل صفحة** حسب العمر (4–8 سنوات: 25–60 كلمة).
2. **إيقاع القراءة الجهرية**: جملة واحدة طويلة أو جملتان قصيرتان لكل صفحة.
3. **قوس عاطفي** معلن مسبقًا (خوف → محاولة → مساعدة → اطمئنان) وكل مشهد يخدم نقطة منه.
4. **تكرار مقصود** (repetition) لأن الأطفال يحبّونه — جملة مفتاحية تتكرر 3 مرات.
5. **التحقق بعد التوليد**: عدد الكلمات، طول الجملة، مستوى المفردات، وغياب العنف/الخوف الشديد.
6. **البشر في النهاية**: مراجعة لغوية بشرية قبل النشر — لا يوجد بديل عنها للجودة الأدبية.

---

## 7) مراحل ما بعد النص (مختصر)

| المرحلة | الملف | المخرج |
|---|---|---|
| حساب الصفحة | `page_layout_service` | single / spread (+gutter) / full_bleed، bleed 3mm، آمن 12mm |
| التنضيد | `text_layout_service` | justify + hyphenation + منع أرامل + فيض مُرجَع |
| الرسم | `render_service` | PDF داخلي بمقاس كل صفحة + علامات قص + ميتاداتا |
| الغلاف | `render_wrap_cover_pdf` | خلفي + كعب محسوب + أمامي + باركود |
| البيانات | `metadata_service` | عنوان بيع + وصف + 8 كلمات مفتاحية |
| القنوات | `amazon_kdp_service` / `etsy_service` | listing + تحقق آلي |

---

## 8) أمر تجربة سريع

```bash
python scripts/seed_demo.py        # ينشئ القصة والشخصيات والمشاهد
python -m pytest -q                # 21 اختبارًا
python scripts/produce_demo.py     # يخرج PDF + غلاف كامل + metadata + bundle
```
أو عبر الـ API: `POST /api/pipeline/demo` ثم الرد يحتوي `prompts` و`page_layouts` و`typography`.
