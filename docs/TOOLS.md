# الأدوات — اللي اتجرّب واشتغل

## Python

**استخدم `py` مش `python`.** `python` على الـ PATH هنا هو venv بتاع hermes، ومفيهوش `openpyxl`.
`py` بيشغّل Python 3.10، وفيه `openpyxl`.

## الـ C&E

```powershell
py tools\build_ce.py                                    # يطلّع deliverables\PH-LCP-01-CE_RevA.xlsx
py tools\build_tags.py                                  # يطلّع build\tags\IO.xml من IO List
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

## TIA Openness (منقولة من مشروع الأوناش)

`Export-TiaProject.ps1` و`Compile-Project.ps1` و`Apply-Blocks.ps1` و`Apply-Tags.ps1` و`List-Blocks.ps1` و`lad2text.py`
و`ladxml.py`. **بتلاقي المشروع كأول `*.ap15_1` جوه `tia\`**. TIA لازم يكون مقفول للي بيكتب (Compile وApply)، **ودول
بترفض تشتغل لو مفتوح. `Apply-Tags` بياخد ملفات XML من `build\`، زي `-Files tags\IO.xml`، وبيعمل overwrite
لجدول التاجات بنفس الاسم، وبعدها بيعمل compile للـ PLC. `-DryRun` موجود في `Apply-Blocks` و`Apply-Tags`
و`Compile-Project` (Export وList مش
بيحفظوا أصلًا). الشروط (جروب Openness، وأي حاجة تانية) في الـ skill `tia-openness`.

**الحفظ:** `Apply-Blocks` و`Compile-Project` بيحفظوا **بس** لو الهاردوير والسوفتوير وكل البلوكات
نضيفة. `Apply-Tags` كمان بيحفظ بس بعد compile نضيف. أي "aborted" أو Error أو بلوك inconsistent بيمنع
الحفظ ويطلع exit 1 (`F28`).

**سكريبتات** `Export-TiaProject.ps1` و`Compile-Project.ps1` و`Apply-Blocks.ps1` و`List-Blocks.ps1`
و`lad2text.py` و`ladxml.py` منقولة من مشروع الأوناش والـ skill؛ أي تصليح فيها يتعمل في النسخ التلاتة
مرة واحدة، والفرق الوحيد المسموح بيه هو سطر مسار المشروع. `Apply-Tags.ps1` إضافة للمشروع ده، وبتتبع
نفس قواعد الاستيراد والـ compile والحفظ.

**اتجرّبت هنا يوم 2026-10-27، والأربعة شغّالين** (`docs/evidence/2026-10-27-openness-tools-first-run.md`).
أول تشغيل لقى عيبين في Export واتصلّحوا في كل النسخ (`F39`). Export بقى يطلع **exit 1** لو أي بلوك
مااتصدّرش. **بلوك inconsistent مش بيتصدّر، فاعمل Compile (بحفظ) الأول.**

**أول مرة PowerShell يكلّم TIA بتظهر رسالة Siemens `Openness access`.** اضغط Yes.

**لو TIA مفتوح:** Export و`List-Blocks` **بيدخلوا عليه للقراية بس**، بشرط إن مشروع البيرنر هو
المفتوح. مش بيحفظوا ولا بيقفلوا، وبيشوفوا التعديلات حتى لو مش محفوظة. Compile وApply-Blocks لسه
بيرفضوا. التفاصيل في `docs/TOOLS.md` بتاع الأوناش.

## موجود على الجهاز

| الأداة | الحالة |
|---|---|
| TIA Portal V15.1 | متسطّب |
| S7-PLCSIM V15.1 | متسطّب. **دي أداة الاختبار الأساسية** |
| WinCC RT Advanced + Simulator | متسطّب. بيشغّل شاشة KTP400 على الكمبيوتر |
| LibreOffice | اتسطّب 2026-10-26 عشان نشوف الـ xlsx |
