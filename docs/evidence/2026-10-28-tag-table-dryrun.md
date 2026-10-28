# 2026-10-28 — جدول التاجات: اتولّد واتجرّب استيراده على المشروع (DryRun)

**مين:** Codex (`gpt-6-luna`، xhigh) كتب الأدوات، وأنا (Claude) راجعت وشغّلت. وفي نفس الوقت
Haiku عمل نفس المهمة في worktree منفصل للمقارنة، ومااتدمجش.

## اللي اتعمل

- `tools/build_ce.py`: الـ IO List بقى فيه عمود **PLC Tag** (31 اسم حسب `0005`). الاحتياطي ومفيش له اسم.
- `tools/build_tags.py`: بيقرا الـ IO List من الـ workbook، ويطلّع `build/tags/IO.xml` (جدول `IO`). وبيقف
  بـ exit 1 لو فيه اسم متكرر، أو عنوان متكرر، أو اسم مخالف لـ `0005`، أو عنوان مش مفهوم.
- `tools/Apply-Tags.ps1`: import overwrite، وبعده compile للهاردوير والسوفتوير والبلوكات، والحفظ بيحصل
  بس لو مفيش errors. فيه `-DryRun`، وبيرفض يشتغل لو TIA مفتوح.

## الفحوصات (اتشغّلت هنا)

```
py tools\build_ce.py     -> saved ...PH-LCP-01-CE_RevA.xlsx
py tools\build_tags.py   -> wrote build\tags\IO.xml (31 tags)
py tools\check_docs.py   -> OK — docs consistent
minidom                  -> 31 tags parse ok
```

## الاستيراد على المشروع الحقيقي، من غير حفظ

TIA كان مقفول. `Apply-Tags.ps1 -Files tags\IO.xml -DryRun`:

```
imported: IO (31 tags)
COMPILING (hardware)     state=Success  errors=0  warnings=0
COMPILING (PLC software) state=Success  errors=0  warnings=0
consistent 1/1
CLEAN. DRY RUN - project NOT saved.   exit=0
```

يعني الـ SimaticML اتقبل من TIA V15.1 فعلاً. **المشروع مااتحفظش**، فالجدول لسه مش جوه `tia\`.

## مفتوح

- **أسماء محتاجة رأي المستخدم.** دي الحاجات اللي فيها اختيار. والبديل اللي بين القوسين هو اختيار Haiku:
  `S0_EStopStatus` (`S0_EStop`)، `S2_FaultReset` (`S2_Reset`)، `Rfuel2_BR02_DieselMode` (`BR02_Diesel`)،
  `BR02_Stage1Lamp_Cmd` (`BR02_Stage1_Lamp`)، `BR02_Stage2Lamp_Cmd`. أما الأسماء الستة اللي في أمثلة `0005`،
  فالاتنين اتفقوا عليها بالظبط.
- **الـ PDF بتاع الـ C&E بقى قديم** مقارنة بالـ xlsx، لأن عمود PLC Tag مش فيه. محتاج `render_xlsx.py`.
- **ملاحظة من Haiku مااتطبّقتش:** تاجات TIA غالبًا مش بتفرّق بين الحروف الكبيرة والصغيرة، فالفحص على
  التكرار الأحسن يبقى case-insensitive. الأسماء الحالية مفيهاش تعارض.
