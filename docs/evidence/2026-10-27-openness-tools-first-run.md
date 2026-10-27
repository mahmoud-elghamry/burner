# 2026-10-27 — أول تشغيل لسكريبتات Openness على مشروع البيرنر

TIA كان مقفول (`Get-Process Siemens.Automation.Portal` فاضي) قبل كل تشغيل.

## اللي اتشغّل والنتيجة

| # | الأمر | النتيجة |
|---|---|---|
| 1 | `Export-TiaProject.ps1` | **وقع قبل ما يفتح TIA:** `Join-Path : Cannot bind argument to parameter 'Path' because it is an empty string` |
| 2 | `List-Blocks.ps1` | ✅ `Main OB No.1 LAD` و`Default tag table (0 tags)`، exit 0 |
| 3 | `Compile-Project.ps1 -DryRun` | ✅ هاردوير Success 0/0، سوفتوير Success 0/0، `Block was successfully compiled @ Main (OB1)`، `CLEAN. DRY RUN - not saved.` |
| 4 | Export بعد تصليح المسار | وصل للمشروع. `FAIL Main : Inconsistent blocks ... cannot be exported` **ورجّع exit 0** |
| 5 | Export بعد تصليح الـ exit code | `EXPORT INCOMPLETE: 1 object(s) failed`، **exit 1** ✅ |
| 6 | `Compile-Project.ps1` (حفظ) | `Main consistent=True`، `CLEAN. PROJECT SAVED.`، exit 0 |
| 7 | Export تاني | ✅ `OK Main [LAD]`، `OK TagTable Default tag table`، failed 0، exit 0 |

## العيبين اللي اتلقوا (`F39`)

1. **`$PSScriptRoot` فاضي في القيم الافتراضية لـ `param()`** لما السكريبت فيه `[CmdletBinding()]`
   ويتشغّل بـ `powershell -File`. اتأكد بسكريبت اختبار صغير: من غير `CmdletBinding` بيشتغل،
   ومعاه بـ `-File` بيقع، ومعاه بـ `& .\script.ps1` بيشتغل. السكريبت الوحيد اللي فيه
   `CmdletBinding` من الأربعة هو Export. **التصليح:** المسارات الافتراضية بتتحسب جوه جسم السكريبت،
   زي `Apply-Blocks`.
2. **Export كان بيرجّع نجاح وهو ناقص.** بلوك inconsistent مش بيتصدّر، والسكريبت كان بيكمل
   ويطلع exit 0، فأي حد بيقرا `export/` يشوف بلوك قديم أو مش موجود. **التصليح:** أي object فشل
   (PLC أو HMI) أو خطأ في الـ HMI exporter = exit 1. البلوك المحمي skip مش فشل.

التصليح اتعمل مرة واحدة في النسخ التلاتة (هنا، والأوناش، والـ skill) واتعمل `Install-Skill`.
الفرق الوحيد بين نسخة هنا ونسخة الأوناش هو سطر مسار المشروع.

## ملاحظات

- **أول مرة PowerShell يكلّم TIA ظهرت رسالة Siemens `Openness access`.** زين ضغط Yes
  (للمرة دي بس، مش "Yes to all").
- كومبايل `PlcSoftware` ككل **اشتغل هنا** (`Success`)، لأن الهاردوير اتعمله كومبايل قبله.
  ملاحظة الأوناش إنه "مش شغّال في V15.1" كانت بدون كومبايل هاردوير قبله.
- الكومبايل المحفوظ غيّر ملفات `tia/` (Main بقى compiled) واتسجّل في نفس الـ commit.
