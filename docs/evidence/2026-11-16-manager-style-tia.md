# 2026-11-16 — manager-style: تعذّر اتصال TIA، ولم تُنفّذ المحاكاة

**النتيجة: المهمة غير مكتملة.** محاولة التصدير الحالية فشلت مرتين قبل فتح المشروع. لم يحصل import أو compile أو download أو اختبار PLCSIM في هذه الجلسة، ولا commit. ملفات TIA وسكربت السيناريوهات كانت معدّلة قبل البداية ولم أغيّرها.

## ما اتنفّذ فعلًا

كل أوامر Openness استُدعيت بـWindows PowerShell 5.1 (`powershell -NoProfile -ExecutionPolicy Bypass`)، وليس `pwsh`.

| السكربت | المعاملات / عدد التشغيل | exit |
|---|---|---|
| `tools/Export-TiaProject.ps1` | `-OutDir baseline/2026-11-16-manager-hmi/xml`، محاولة أولى | 1 |
| `tools/Export-TiaProject.ps1` | نفس الأمر، محاولة ثانية | 1 |
| `build/_stage_hmi_mgr.py` | تشغيلان بـ`py`؛ الناتج النهائي **عينة فقط ممنوع استيرادها** | 0، 0 |
| `tools/check_docs.py` | `py`، بعد تحديث الحالة والدليل | 0 |

مخرجات محاولتي التصدير كاملة في [المحاولة الأولى](2026-11-16-manager-style-tia/export-attempt-1.txt) و[الثانية](2026-11-16-manager-style-tia/export-attempt-2.txt). الخطأ الحرفي المشترك:

```text
argument(s): "Connection to TiaPortal failed."
    + CategoryInfo          : NotSpecified: (:) [Export-TiaProject.ps1], MethodInvocationException
    + FullyQualifiedErrorId : NonRecoverableException,Export-TiaProject.ps1
```

لم تظهر عملية `Siemens.Automation.Portal` قبل المحاولات أو بعدها، ولم يظهر رفض «TIA running»؛ لذلك لم يلزم انتظار عملية سابقة. لم أقتل عمليات أو أحذف lock files. السبب الحالي غير محسوم؛ توجد سابقة لنفس الرسالة داخل sandbox في `2026-11-01-user-hmi-decisions.md`، وليست إثباتًا لسبب هذه المحاولة.

## تعديل HMI — عينة غير مطبّقة

الـexport الموجود `export/xml/HMI_HMI_RT_1/Screens/Alarms.xml` يحتوي البانر القديم، لكنه **لا يحتوي Alarm View اليدوي**؛ أنواع عناصر الشاشة فيه Rectangle وTextField وButton فقط، و`Panel_Alarm_list` مجرد Rectangle. لا يصلح لاستبدال شاشة TIA الحالية. لم أضع نسخة منه داخل مجلد import، ولم ألمس `build/hmi`.

العينة تغيّر ثلاثة حقول فقط: اسم العنصر من `Text_E_STOP_RESET_Sys_Alm_EStop` إلى `Text_E_STOP_Scrub_EStopOK`، وتاج Visibility من `Sys_Alm_EStop` إلى `Scrub_EStopOK`، و`Visible` من `true` إلى `false` (الظهور عند 0؛ `BitPosition=0`). [الفرق](2026-11-16-manager-style-tia/Alarms-preview.diff)، [قبل](2026-11-16-manager-style-tia/Alarms-before.xml)، [العينة الممنوع استيرادها](2026-11-16-manager-style-tia/Alarms-preview.xml)، [فحص التطابق](2026-11-16-manager-style-tia/preview-check.txt).

الفحص عكس الحقول الثلاثة وأثبت رجوع **كل بايت** للأصل. هذا يحفظ محتويات الملف القديم فقط؛ لا يثبت حفظ Alarm View الموجود داخل المشروع. المطلوب export جديد ناجح للشاشة الحقيقية، ثم نفس التعديل المحدود وإعادة الاستيراد مع ملفات المولّد في مجلد منفصل.

## تقارير compile — سابقة للجلسة وليست إعادة تحقق

التقرير الكامل الموجود من المنسّق محفوظ في [PLC السابق](2026-11-16-manager-style-tia/prior-plc-compile.txt). أهم سطوره حرفيًا:

```text
=== 1. HARDWARE ===
state=Success  errors=0  warnings=0
=== 2. SOFTWARE ===
state=Success  errors=0  warnings=0
=== 3. BLOCK CONSISTENCY ===
  Par                      consistent=True
  Burner                   consistent=True
  Scrubber                 consistent=True
  BR01_DB                  consistent=True
  BR02_DB                  consistent=True
  Scrubber_DB              consistent=True
  Startup                  consistent=True
  Main                     consistent=True
CLEAN. PROJECT SAVED.
```

فشل HMI السابق، من `build/_apply_hmi_mgr.log` حرفيًا؛ [الملف الكامل](2026-11-16-manager-style-tia/prior-hmi-apply.txt):

```text
HMI compile: state=Error errors=1 warnings=0
  Error: HMI_1
    Error: Screens
      Error: Alarms
        Error: Text_E_STOP_RESET_Sys_Alm_EStop
          Error:  Animation 'Visibility' has invalid parameters. The tag does not exist.
  Error:  Compiling aborted (errors: 1; warnings: 0)
NOT SAVED (import failures or compile errors)
```

لم أشغّل `Apply-Hmi` أو `Compile-Project` بعد تعذّر فتح المشروع؛ لا يوجد تقرير HMI ناجح جديد. سكربت `Compile-Project` الحالي يجمع hardware وPLC فقط؛ HMI يُجمع في `Apply-Hmi`، فلا يُنسب له فحص HMI.

## export وPLCSIM

**export check: NOT RUN.** لا يوجد export جديد ناجح؛ لم أغيّر `export/` ولم أقارن الملف القديم بالمولّد على أنه البرنامج الحالي. مطابقة البلوكات الثمانية وعناوين الشبكات وأعداد الرنجات باقية.

**PLCSIM: NOT RUN — لا يوجد سطر PASS/FAIL صادر من السيناريوهات.** قرأت `Download-Plcsim.ps1`: يحتاج PLCSIM شغّالًا، S7-1200 وPower ON، ولا يبدأه بنفسه. فحص العمليات لم يجد PLCSIM. حسب تعليمات المهمة توقفت قبل التنزيل والسيناريوهات؛ لا توجد خطوات assertions فاشلة لتشخيصها. لم أعدّل السيناريوهات.

`build/blocks/Par.xml` يحمل StartValue ‏SP=700 وHYST=50 وSTG=100 مع Retain. **لم أضمن القيم الفعلية** لعدم حصول fresh download؛ STOP/RUN وحده ليس إثباتًا لإعادة تهيئة retain. بعد توفير اتصال TIA وPLCSIM: يلزم تنزيل جديد يهيّئ DB بهذه القيم ثم تشغيل المجموعة الافتراضية مع `PYTHONUNBUFFERED=1`.

لم تُختبر الـ18 سيناريو الافتراضية، ولا تشغيل 24 ساعة/توقف 60 ثانية، ولا حد الدرين 10 دقائق، ولا انتظار 120 ثانية، ولا بتات الإنذارات عبر HMI، ولا عرض البانر وAlarm View على Runtime، ولا الهاردوير أو أمان اللهب الفعلي.

**للاستكمال:** جلسة تستطيع الاتصال بـTIA Openness، وPLCSIM V15.1 مفتوح على S7-1200 وPower ON، مع بقاء TIA UI مغلقًا. بعدها export للشاشة الحالية ثم patch/import/compile/save/export round-trip/download/default scenarios. لا تستخدم عينة Alarms القديمة للاستيراد.
