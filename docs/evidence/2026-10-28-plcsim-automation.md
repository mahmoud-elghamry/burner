# 2026-10-28 — PLCSIM V15.1 من سكريبت

**مين:** subagent (Sonnet) عمل البحث، وأنا جرّبته هنا.

## اللي اتلقى

- PLCSIM V15.1 العادي (مش Advanced) **مالوش API موثّق**. بس `PlcSim.Interproc.dll` (في `Bin`) فيه
  واجهة WCF اسمها `ICompact`، على named pipe عنوانه `net.pipe://localhost/PlcSim14/<guid>/Compact`.
  الـ guid عشوائي مع كل تشغيل، فبنلاقيه في ذاكرة `Siemens.Simatic.PlcSim.Compact.exe`.
- اللي شغّال: `PowerOn` و`RequestCpuRunMode`/`StopMode` و`SetValues` (للمداخل I) و`ReadOutput` (للمخارج Q).
  **قراية الـ DB والـ M مش موجودة**، فالاختبار بيشوف المخارج بس.
- PLCSIM Advanced مش بيدعم S7-1200 أصلًا، وsnap7 مش هيشتغل (PLCSIM العادي مالوش TCP).

## اتجرّب هنا

- `tools/plcsim/PlcSimCtl.cs` اتعمله compile بـ `csc` لـ `build/plcsim/PlcSimCtl.exe`. شغّلت
  `Compact.exe -f S71200`، واتوصّل: `OK connected S71200`، و`power on` = `OK Success`، و`mode` = `OK Stop`.
- **التنزيل من Openness مانفعش:** `Download-Plcsim.ps1 -List` بيطلّع كروت الشبكة الحقيقية بس، ومفيش
  كارت `PLCSIM`، حتى وPLCSIM شغال: `EXCEPTION: pc interface not found: PLCSIM`. يعني **التنزيل
  لازم يتعمل من TIA** (Start simulation، ثم Download).

## الاختبار

`tools/plcsim/run_scenarios.py` فيه سيناريوهات §6 (من 1 لـ 10، و6ب)، وR-01 وR-02 وR-09 وR-10،
وBR02 (اللمبات، والديزل، والاستقلال عن BR01). كل سيناريو بيعمل PLC STOP ثم RUN، وبعدها RESET، وبيقارن
المخارج.

**مش بيتختبر هنا:** إيقاف الـ 24 ساعة (`C07h`)، لأن مفيش طريقة نسرّع الوقت. ومدى الأرقام (R-11)، لأن
مفيش كتابة على الـ DB. ودول بيتجرّبوا بالإيد من watch table.

النتايج بتتسجّل في ملف لوحدها بعد التشغيل.

## تحديث: ليه كتابة المداخل كانت بترجع `ServiceNotConnected` (subagent على Opus)

- `ServiceNotConnected` مش حالة حقيقية: `CompactService.SetValues` بيمسك أي exception ويرجّع الكلمة دي.
- في VplcHost، `IsPeripheral=false` بيروح `SetTagValue`، وده محتاج اسم تاج (`TagNameUtf8`). إحنا ماكناش
  باعتين اسم، فحصل `NullReferenceException`، و**الـ vPLC (VplcHost) مات**. وبعدها كل نداء بيفشل بنفس الكلمة.
  الدليل في `%TEMP%\PlcSimCompactServiceLog.txt` (22:24:24، 22:27:11، 22:32:51)، وفيه crash dumps لـ VplcHost.
- **الحل:** `IsPeripheral=true`، فبيروح `SetInputBit`/`SetInput` على مساحة الدخل مباشرة. الكلمة big-endian.
- يعني التنزيلات اللي ضاعت ماكانتش بسبب `RegisterFullView` بس. أول `set` غلط كان بيموّت الـ vPLC.
- **ممنوع أي `SetValues` بـ `IsPeripheral=false` من غير اسم تاج.** و`readq` بيرجّع أصفار لو الـ CPU مش شغال،
  فقبل ما نصدّقه لازم `mode` يبقى `Run`.
