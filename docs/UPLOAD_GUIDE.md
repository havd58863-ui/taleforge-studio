# كيف ترفع المشروع إلى GitHub — خطوة بخطوة (بدقّة)

> **المستودع:** `https://github.com/havd58863-ui/taleforge-studio.git`
> **الملف:** `taleforge-studio.zip` — 200 مدخلًا، 2.8 م.ب، فُحص سلامة الضغط: سليم. يفكّ إلى مجلد واحد اسمه `taleforge-studio/`.
> المشروع **جاهز للرفع** ومُختبَر من نسخة نظيفة: 42 اختبارًا ناجحًا + `smoke_test` ALL PASSED + 5 كتب مولودة.

---

## 0) قبل أن تبدأ: ماذا يوجد في الحزمة وماذا **لا** يوجد

| موجود ✅ | غير موجود (بالتصميم) ❌ |
|---|---|
| الكود كامل: `app/` + `scripts/` + `tests/` + `docs/` | `.env` (مفاتيحك) — فقط `.env.example` |
| `.github/workflows/ci.yml` (يشغّل الاختبارات تلقائيًا) | `secure_data/` بمحتواه الخاص |
| الخطوط `assets/fonts/` + تراخيص OFL | قواعد بيانات `*.db` |
| الكتب الخمسة داخل `output/library/` | أي مفتاح `HF_TOKEN` / `KAGGLE_KEY` |
| وثائق: `MASTER_PLAN.md` · `TOOLCHAIN.md` · `N8N.md` · `FIXES.md` · `QUALITY.md` | `__pycache__` و`.pytest_cache` |

**الأرقام الفعلية بعد `git add .`:** يُرفَع **107 ملفات** (منها **103 ملفات مصدرية** حرجة + 4 ملفات README لحفظ بنية المجلدات الخاصة) (الكود + الخطوط + الوثائق + الاختبارات)، ولا يُرفع أي `.env` ولا `secure_data/` ولا `.db`.

⚠️ **مهم:** `.gitignore` يستثني `output/*` — أي أن **الكتب الخمسة لن تُرفع افتراضيًا** مع `git add .`
(وهذا صحيح: المستودع يحتفظ بالمولِّد، والكتب مخرجات). إن أردت أن تظهر الكتب على GitHub، عندك خيارَان في الخطوة 2-ج.

---

## 1) فكّ الضغط

- **Windows:** زر يمين على الملف → `Extract All…` → اختر مجلدًا سهلًا مثل `C:\projects`.
- **macOS:** نقر مزدوج على الملف.
- **Linux:** `unzip taleforge-studio.zip -d ~/projects`

بعد الفك ستحصل على مجلد اسمه **`taleforge-studio`**، وداخله مباشرة: `app/`، `scripts/`، `README.md`…
(إن رأيت مجلدًا داخل مجلد بنفس الاسم، ادخل إلى الداخلي — هذا هو جذر المشروع.)

---

> ⚠️ **خطأ شائع يُفسد المشروع:** السحب والإفلات للملفات **بدون مجلداتها** يجعل كل شيء في جذر
> المستودع، فتختفي `app/` و`scripts/` وتضيع ملفات بنفس الاسم. المستودع يبدو «مرفوعًا» لكنه لا يعمل.
> العلامة: وجود `config.py` و`__init__.py` في الجذر بدلًا من داخل `app/`.

**إصلاح سريع إن حدث ذلك (من طرفية على جهازك):**

```bash
git clone https://github.com/havd58863-ui/taleforge-studio.git repo
cd repo
git rm -r --cached . 2>/dev/null; rm -rf * .github     # تفريغ المحتوى المسطّح (المستودع فقط)
cp -r /path/to/taleforge-studio/. .                     # انسخ المشروع الصحيح ببنية مجلداته
git add -A && git commit -m "Restore project structure"
git push
```

## 1.5) الرفع **دفعة واحدة** (استبدال كامل للمستودع)

هذه هي الطريقة الوحيدة التي ترفع ١٠٤ ملفًا ببنيتها الصحيحة **في أمر واحد**.
`--force` يستبدل تاريخ المستودع الحالي بالكامل — آمن هنا لأن الموجود حاليًا مسطّح وخاطئ.

```bash
cd taleforge-studio          # بعد فك الضغط (داخل المجلد الذي فيه app/ و scripts/)

git init
git add -A
git status                   # تحقّق: يجب أن ترى app/... scripts/... لا ملفات مسطّحة
git commit -m "TaleForge Studio — full project, correct structure"
git branch -M main
git remote add origin https://github.com/havd58863-ui/taleforge-studio.git
git push -u origin main --force
```

ثم تحقّق:

```bash
python scripts/verify_upload.py --path .     # المتوقع: verdict : COMPLETE
```

> **لماذا لا يكفي الرفع من المتصفح؟** الواجهة تقبل ~١٠٠ ملف في الدفعة الواحدة، وسحب
> *الملفات* يفقد المجلدات (وهو ما حدث). سحب **المجلد** يحافظ على البنية لكنه يحتاج دفعتين
> مع ١٠٧ ملفات. لذلك: git هو «الدفعة الواحدة».

## 2) الرفع — اختر طريقة واحدة

### أ) سطر الأوامر (الأدقّ والموصى به)

```bash
cd taleforge-studio                 # جذر المشروع (حيث README.md)

git init
git add .
git status                          # راجع القائمة: يجب ألا ترى .env إطلاقًا
git commit -m "TaleForge Studio — gated pipeline, EN/DE/ES library, bilingual editions"
git branch -M main
git remote add origin https://github.com/havd58863-ui/taleforge-studio.git
git push -u origin main
```

**إذا كان المستودع يحتوي README أو LICENSE من إنشاء GitHub** (خطأ `rejected`/`fetch first`):

```bash
git pull origin main --rebase --allow-unrelated-histories
git push -u origin main
```

**إذا طلب كلمة سر:** GitHub لا يقبل كلمة سر الحساب. استخدم **Personal Access Token** (Settings → Developer settings → Tokens → Fine-grained → صلاحية `Contents: Read and write`) وألصقه مكان كلمة السر، أو:

```bash
gh auth login          # أسهل: يفتح المتصفح
```

**إذا كان `origin` موجودًا مسبقًا:** `git remote set-url origin https://github.com/havd58863-ui/taleforge-studio.git`

### ج-إضافة اختيارية: ارفع الكتب الخمسة أيضًا

```bash
git add -f output/library           # -f يتجاوز استثناء .gitignore (1.3 م.ب فقط)
git commit -m "Add 5 print-ready books (EN, DE, ES, EN-DE, ES-EN)"
git push
```

### ب) من الموقع بدون أوامر (للمبتدئ)

1. افتح المستودع → زر **Add file** → **Upload files**.
2. اسحب **محتويات** المجلد `taleforge-studio` (لا المجلد نفسه) إلى الصفحة.
3. اكتب رسالة ثم **Commit changes**.
4. **حدّ مهم:** الواجهة تقبل ~100 ملف في المرة الواحدة. إن رفضت، أضف الباقي في دفعة ثانية — أو استخدم الطريقة (أ).
5. المجلدات الفارغة لا تُرفع (لا مشكلة: `secure_data/*` تُنشأ تلقائيًا عند التشغيل).

### ج) GitHub Desktop (واجهة رسومية)

`File → Add local repository` → اختر مجلد المشروع → `Publish repository` → أزل علامة *Keep this code private* إن أردته عامًا → `Publish`.

---

## 3) الأسرار (Secrets) — بعد الرفع، لا قبله

`Settings → Secrets and variables → Actions → New repository secret`

| الاسم | القيمة | لِماذا |
|---|---|---|
| `HF_TOKEN` | `hf_...` | الكاتب + توليد المشاهد عبر Hugging Face |
| `KAGGLE_USERNAME` | اسم المستخدم | بيانات السوق (اختياري) |
| `KAGGLE_KEY` | المفتاح | بيانات السوق (اختياري) |

- **لا تلصق أي مفتاح في المحادثة ولا في أي ملف داخل المستودع.**
- الاختبارات في CI لا تحتاج أي سر — تعمل كاملة بدونه.
- للتشغيل على جهازك: انسخ `.env.example` إلى `.env` واملأه (`.env` مُستثنى من git).

---

## 4) التحقّق بعد الرفع (٥ دقائق)

1. **الصفحة الرئيسية للمستودع** تُظهر: `app/` `scripts/` `tests/` `docs/` `assets/` `output/` + `README.md`.
2. تبويب **Actions** → أحدث تشغيل `CI` → يجب أن يكون ✅ أخضر (يشغّل `pytest` + `smoke_test`).
3. **ملف لم يُرفع؟** افتح `README.md` وتأكد أنه ليس صفحة GitHub الافتراضية.
4. **فحص آلي للاكتمال** (أقوى وأسرع من العدّ اليدوي):

```bash
python scripts/verify_upload.py --path .
# المخرَج المتوقع: verdict : COMPLETE  (103 ملفات مصدرية، 70 ملفًا حرجًا، كل المجلدات OK)

# أو افحص المستودع على GitHub مباشرة (رمزك يبقى على جهازك):
GITHUB_TOKEN=ghp_... python scripts/verify_upload.py --remote havd58863-ui/taleforge-studio
```

5. اختبار نسخة نظيفة:

```bash
git clone https://github.com/havd58863-ui/taleforge-studio.git test-clone
cd test-clone
python -m pip install -r requirements-lite.txt pytest
python -m pytest -q            # المتوقع: 42 passed
python scripts/smoke_test.py   # المتوقع: ALL PASSED
```

---

## 5) أخطاء شائعة وحلولها

| الرسالة/المشكلة | السبب | الحل |
|---|---|---|
| `remote origin already exists` | أضفت الريموت مرتين | `git remote set-url origin <URL>` |
| `failed to push some refs` / `fetch first` | المستودع فيه commits (README) | `git pull origin main --rebase --allow-unrelated-histories` |
| `Authentication failed` | استخدمت كلمة السر | استخدم Token أو `gh auth login` |
| `file is 100.00 MB` | ملف أكبر من حدّ GitHub | لا يوجد هنا (الأكبر ~1 م.ب) |
| رفضت الواجهة الرفع | أكثر من 100 ملف | رفع على دفعتين أو استخدام git |
| الكتب غير ظاهرة على GitHub | `output/*` مُستثنى | `git add -f output/library` |
| `Permission denied (publickey)` | SSH بلا مفتاح | استخدم HTTPS + Token |

---

## 6) ماذا بعد الرفع؟

```bash
python scripts/produce_library.py     # 5 كتب جاهزة → output/library/
python scripts/ideate.py --demo       # قرار السوق والسلسلة
python scripts/write_book.py --demo   # كتابة + بوابة التحرير
python run_server.py                  # واجهة على http://localhost:5000
```

الخطة الكاملة (7 بوابات ومعايير القبول): `docs/MASTER_PLAN.md`.
