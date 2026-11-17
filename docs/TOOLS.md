# الأدوات — اللي اتجرّب واشتغل

## Python

**استخدم `py` مش `python`.** `python` على الـ PATH هنا هو venv بتاع hermes، ومفيهوش `openpyxl`.
`py` بيشغّل Python 3.10، وفيه `openpyxl`.

## الـ C&E

```powershell
py tools\build_ce.py                                    # يطلّع deliverables\PH-LCP-01-CE_RevA.xlsx
py tools\render_xlsx.py deliverables\PH-LCP-01-CE_RevA.xlsx   # يطلّع PDF في build\ عشان تتشاف
```

`render_xlsx.py` محتاج LibreOffice (`soffice`). اتسطّب بـ winget في 2026-10-26.

**اللي بيروح للعميل نسختين في `deliverables/`:** الإكسيل عشان يرد فيه (العمودين الأصفر، وفيهم
قايمة منسدلة، والباقي محمي من غير باسورد)، والـ PDF كنسخة ثابتة للأرشيف والطباعة.
بعد أي تعديل: `build_ce.py` ثم `render_xlsx.py`، وانسخ الـ PDF من `build/` لـ `deliverables/`.

## الفحص

```powershell
py tools\check_docs.py
```

بيتأكد إن: كل مسار مكتوب في `docs/` وفي `AGENTS.md` موجود فعلًا، وإن `STATE.md` أقل من 60 سطر،
وإن أرقام `Q`/`F` مش متكررة، وإن كل قرار متسجّل في `decisions/README.md`، وإن الـ xlsx
أحدث من `build_ce.py`.

## جدول التاجات

```powershell
py tools\build_tags.py                                                    # يطلّع build\tags\IO.xml من عمود PLC Tag في الـ IO List
powershell -ExecutionPolicy Bypass -File tools\Apply-Tags.ps1 -Files tags\IO.xml -DryRun   # يستورد جدول التاجات ويكمّل، ومايحفظش
```

- `build_tags.py` بيقرا الـ IO List من الإكسيل نفسه، مش من قايمة تانية. بيوقف ومايكتبش الملف لو فيه
  اسم غلط حسب `docs/decisions/0005-tag-naming.md`، أو اسم مكرر (من غير فرق بين الحروف الكبيرة والصغيرة)،
  أو عنوان مكرر، أو عنوان مش مفهوم. الملف القديم بيتشال في الحالة دي.
- `Apply-Tags.ps1` شبه `Apply-Blocks.ps1`: TIA لازم يكون مقفول، وبيكمّل الـ CPU والبلوكات، وبيحفظ بس لو
  الأخطاء صفر. **مااتجرّبش على TIA لسه.**

## TIA Openness (منقولة من مشروع الأوناش)

`Export-TiaProject.ps1` و`Compile-Project.ps1` و`Apply-Blocks.ps1` و`List-Blocks.ps1` و`lad2text.py`
و`ladxml.py`. **بتلاقي المشروع كأول `*.ap15_1` جوه `tia\`**. TIA لازم يكون مقفول، وكل سكريبت فيه
`-DryRun`. الشروط (جروب Openness، وأي حاجة تانية) في الـ skill `tia-openness`.

**مااتجرّبتش في الفولدر ده لسه**، لأن مشروع TIA لسه متعملش.

## موجود على الجهاز

| الأداة | الحالة |
|---|---|
| TIA Portal V15.1 | متسطّب |
| S7-PLCSIM V15.1 | متسطّب. **دي أداة الاختبار الأساسية** |
| WinCC RT Advanced + Simulator | متسطّب. بيشغّل شاشة KTP400 على الكمبيوتر |
| LibreOffice | اتسطّب 2026-10-26 عشان نشوف الـ xlsx |
