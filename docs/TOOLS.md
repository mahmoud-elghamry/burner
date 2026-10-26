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

## الفحص

```powershell
py tools\check_docs.py
```

بيتأكد إن: كل مسار مكتوب في `docs/` وفي `AGENTS.md` موجود فعلًا، وإن `STATE.md` أقل من 60 سطر،
وإن أرقام `Q`/`F` مش متكررة، وإن كل قرار متسجّل في `decisions/README.md`، وإن الـ xlsx
أحدث من `build_ce.py`.

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
