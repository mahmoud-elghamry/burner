# 2026-10-26 — قراءة المدخلات

**المصدر:** كل الملفات في `inputs/`. النص اتاخد بـ `pdftotext`، والرسم اتقرى صفحة صفحة.

## الإيميل (`inputs/client/WhatsApp Image …jpeg`) — Amr Farag، 4 أكتوبر

الـ proposal اتوافق عليه. **مطلوب من PH: Cause & Effect Matrix** يغطي:
إنذارات وتريبات مستوى الـ scrubber، وأثر الـ ESD على البيرنر، وAuto/Manual "including energization
and tripping of the pilot and main flame gas solenoid valves"، ووضع الديزل، والاتصال بالـ Master PLC.
وقال "Please find attached the Burner Sequence of Operation".

**م. عمرو أكّد إن مفيش مرفقات غير اللي اتبعتت.** يعني الـ "Sequence" هي ورقة الحرارة.

## ورقة الحرارة (`inputs/client/Temprature control of burner .pdf`) — ختم CUBIC

الشرط: المستوى وصل لـ level switch low، والحرارة تحت الحد → البيرنر جاهز. 4 حالات (مترقّمة 1، 2، 3، 6):
LSL ON مع T < 70 → ON · LSL ON مع T ≥ 70 → OFF · LSL OFF → OFF. والـ setpoint يتغيّر من SCADA.

## RS100 (`inputs/manuals/Burner RS100 Product Manual (1).pdf`) — Riello، 20144609

- §6.8.1: `TL` يقفل ← 0 ث يبدأ ← 2 ث المروحة ← purge 25 ث ← 43 ث شرارة وصمامات VS+VR
  ← 53 ث المرحلة التانية لو `TR` مقفول.
- §6.8.3: لو مولّعش، lockout خلال 3 ث من فتح الغاز. ولو اللهب طفى وهو شغال، lockout خلال 1 ث.
- §6.8.2: `TR` بيبدّل بين المرحلة الأولى والتانية. `TL` بيقفل البيرنر.
- §5.10: "approved for intermittent use… must be stopped at least once every 24 hours".

## DLX 53 SHFP (`inputs/manuals/`) — Oxilon

- علبة `SQ DUAL`، وزمن السيكوانس 30 ث على اللوحة. Pre-purge 50 ث، وsafety ignition 5 ث.
- صمامات الغاز `SV1` (low) و`SV2` (high)، وصمام الزيت `SV1`، وكلهم من العلبة.
- الطرف `L` = "Main Phase From All Interlocks"، و`T1`/`T2` = high/low، و`S3` = lockout، و`B4` = low.

## إجابات المهندس زين (المحادثة، 2026-10-26)

| النقطة | الإجابة |
|---|---|
| الموقع | حقل بترول وغاز طبيعي، مش مصنع. الـ scrubber بينضّف الغاز الداخل للبيرنر |
| حساسات التريب | fail-safe، والرسم يتعدّل |
| تريب الـ scrubber | يفتح الفلير، ويفتح الدرين، ويقفل الساكشن. **ميقفلش البيرنرات** |
| حاجة "مش متركبة، فكّنا منها" | اتفهمت إنها LSL الـ scrubber (`Q1`) |
| وضع الديزل | قراءة بس |
| الـ Master PLC | مؤجّل |
| الهيستريسيس | أي رقم من 3 لـ 6 مقبول، واخترنا 5 |
