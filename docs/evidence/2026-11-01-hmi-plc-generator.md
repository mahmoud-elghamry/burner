# 2026-11-01 — تجهيز جانب الـ `PLC` للشاشة

**النطاق:** تنفيذ `0007` §1 و§3 و§4 وقرارات المستخدم في `docs/evidence/2026-11-01-user-hmi-decisions.md`.
المطلوب توثيق الأول، وبعده تعديل المولّد. مفيش تشغيل لـ `Openness` أو تعديل لمشروع `TIA` أو أوامر `git` في الجلسة دي.

## خطة التنفيذ

1. تحديث `C07a` و`C08a` بإنذار المستوى، وإضافة `C06a` لذاكرة الأسباب و`FirstOut` كـ `PH proposal`.
2. تثبيت `D6` في `R-11` وجدول `Parameters`، وقراري `F47` في §8. توثيق صلاحيات الشاشة وجدول البتات في §5.
3. توليد الـ `C&E` وفحص التوثيق قبل الكود.
4. إضافة شبكات الأسباب للـ `Scrubber` مع مسح في الآخر، واستبدال شبكات `R-11` بس في `Burner`.
5. إضافة `HmiAlm` و`HmiMap`، وبعدها فحص الـ `XML` وفك اللادر ومقارنة الشبكات اللي مش مطلوب تتغير.

## نقط المراجعة

- `RESET` السليم يمسح كل الأسباب و`FirstOut`، ومفيش شبكة تسجيل بعد شبكة المسح. `Common` بيمنع نبضة `RESET` في أول `scan`.
- أول سبب يفضل ثابت. الأسباب اللي تيجي بعده تتمسك برضه. الأولوية في نفس الـ `scan`: `E-STOP` ثم `PSH` ثم `LSHH` ثم `power-up`.
- `D6` بيستنى `Enabled=0` للتغيير اللي بيزوّد الحرارة. `Active=0` لوحدها مش كفاية. `TStart` يتاخد عند `Active=0`.
- جدول الإنذارات بيتراجع ضد وجهة كل ملف `Coil` في الـ `XML`، لأن مفكك اللادر الحالي مش بيعرض الـ `slice`.
- `F41` فرق `2 °C` يفضل زي ما هو. `HmiMap` مابيكتبش غير في `HmiAlm`.

## اللي اتأكد قبل الكود

- الـ `schema` المحلية الرسمية `SW.PlcBlocks.Access_v3.xsd` في `PublicAPI/V15.1/Schemas` بتعرّف
  `Component_T` وفيه `SliceAccessModifier`. نوعه `SliceAccessModifier_TP`، والنمط `([xbwdXBWD]\d+)|undef`.
  يعني `Component Name="Common" SliceAccessModifier="x0"` موافق للـ `schema`. القبول في الاستيراد الحقيقي لسه مطلوب.
- جدول `0007` §4 بيقول إن إنذار الرقم المرفوض يختفي بتصحيح الرقم. `Common` الحالي بيمسكه لحد `RESET`،
  وبيرجّع الرقم القديم عند الرفض. اتوثّق السلوك الحالي في §5، من غير تغيير شبكات `Common` خارج المطلوب.
- خطة المستخدم هي خطة التنفيذ المحددة. مفيش تصميم بديل أو تغيير في حدود حماية اللهب.

## نتيجة التنفيذ المحلي

- اتولّد الـ `C&E` من المصدر، وبعده `check_docs.py` طلع `OK`. بعد كده اتعدّل مولّد البلوكات.
- اتولّد `13` ملف `XML`: اتضاف `HmiAlm` (`DB6`) و`HmiMap` (`FC3`). ترتيب الاستيراد في `docs/TOOLS.md`.
- فحص سلوكي محلي بيقرا `Parts` و`Wires` شاف أربع مجموعات تفشل قبل التعديل، وبعده الأربع نجحوا:
  أسباب الـ `scrubber` وأول سبب والمسح، واتجاهات `D6` و`ParPending`، وكل بت إنذار لوحده ومع غيره، وثبات الشبكات والواجهات.
- المراجعة المستقلة قرت نفس الملفات من غير كتابة، وماطلعتش بعيب مُدخل بالتعديل. راجعت `2560` تركيبة
  للأسباب والأولوية والمسح، و`324` تركيبة للأرقام والحالة على الـ `netlist` المتولد. **ده مش `PLCSIM`.**
- اتفحصوا `113` شبكة بنيويًا، وكل `485` عنصر `Access` وافقوا الـ `XSD` الرسمية المحلية لـ `V15.1`.
  واتراجع جدول الإنذارات كامل ضد الكود: `20` صف بنفس الكلمة والبت والقطبية والنص.
- `Common` و`Outputs` و`Par` و`Startup` و`Sys` مطابقين بايت ببايت لنسخة المولّد قبل التعديل.
  أول ست شبكات `Scrubber` زي ما هي. شبكات `Burner` اللي مش `R-11` زي ما هي، بما فيها `F41`.
  الواجهات بين الـ `FBs` ونسخ الـ `DBs` متطابقة في الاسم والنوع والترتيب.
- `ISSUES.md`: التغيير في حالة `F44` و`F45` و`F47` بس. موافقة المستخدم داخلية؛ صف `C06a` وإنذار المستوى فضلوا `PH proposal`.
- فحص مساعد واحد وقف لأن `PowerShell` بدّل حروف مسار عربي بـ `?` وهو بيبعته على `stdin`.
  اتعاد الفحص بمسار `Unicode` صريح ونجح. مفيش تغيير في منطق الـ `PLC` بسبب ده.

**الدليل المحلي:** `docs/evidence/2026-11-01-hmi-plc-generator/offline-checks.txt`، وفك اللادر الأصلي الكامل في
`docs/evidence/2026-11-01-hmi-plc-generator/decoded-all.txt`، والشبكات الجديدة والمتغيرة في `docs/evidence/2026-11-01-hmi-plc-generator/changed-networks.txt`.
الملفات دي محلية ومتولدة، والسجل ده هو دليل التسليم المستمر في `docs/`.

## ترتيب المسح واللي لسه مااتثبتش

- شبكات تسجيل الأسباب `7`…`10`، وبعدها `FirstOut` بأولوية `11`…`14`، وشبكة المسح `15` آخر واحدة.
  مفيش تسجيل بعد المسح. لما السبب يروح وتيجي نبضة `RESET` سليمة، مفيش سبب قديم بيتعاد تسجيله.
- لو حقنّا `FirstScan` و`ResetPulse` مع بعض يدويًا جوه الـ `FB`، مسح الأسباب يكسب لأنه في الآخر.
  لكن `Tripped` القديم بيخلي `FirstScan` يكسب التريب. التركيبة دي مش بتوصل من `Main`:
  `Common` بيمنع `ResetPulse` في `FirstScan` وبيتنادى قبل `Scrubber`. الشبكات القديمة مالمسناهاش.
- شبكات الأرقام قبل معالجة `START` و`STOP`، زي ترتيب الكود السابق. بعد `STOP`، نسخ القيم المؤجلة يحصل
  في أول `scan` يشوف `Enabled=0`. الوقوف الحراري مع `Enabled=1` ماينقلش القيم اللي بتزوّد الحرارة.
- صيغة الـ `slice` متأكدة من الـ `schema` واتحطت في `symbol_component` في مكان واحد.
  **الاستيراد والكومبايل الحقيقي لسه مطلوبين.** `lad2text.py` الحالي بيخفي الـ `slice`، فاتضاف دعم عرض
  في الذاكرة وقت تجهيز نص المراجعة بس؛ ملف المفكك نفسه و`ladxml.py` مالمسناهمش.
- مفيش استيراد أو `compile` أو `re-export` أو اختبار `PLCSIM` في الجلسة دي. مفيش تعديل لـ `tia/` أو
  `export/` أو `baseline/` أو `inputs/` أو `tools/plcsim/`. مفيش تشغيل لأي سكريبت `ps1` أو أي أمر `git`.
- الجاي عند الـ `orchestrator`: `P1` و`P2` حسب `0007`، وبعدهم استيراد وكومبايل وفرق مع النسخة الأصلية،
  وإعادة الـ `17` سيناريو وزيادة اختبارات كل بت والأسباب المتزامنة والمسح و`D6` والبيرنرين.

## النص المفكوك لكل شبكة جديدة أو متغيرة

النص تحت من المفكك، مع إظهار الـ `slice` من الـ `XML` في العرض بس. `S` ملف مسك، و`R` ملف مسح.

```text
Decoded using lad2text, with display-only slice support from raw XML.
No decoder source file was changed.

Scrubber.xml NETWORK 7 -- C06a / F44 / 0007 D5 — latch cause: E-STOP
  #Cause_EStop := S NOT #EStopOK

Scrubber.xml NETWORK 8 -- C06a / F44 / 0007 D5 — latch cause: PSH-101
  #Cause_PSH := S NOT #PSH

Scrubber.xml NETWORK 9 -- C06a / F44 / 0007 D5 — latch cause: LSHH-103
  #Cause_LSHH := S NOT #LSHH

Scrubber.xml NETWORK 10 -- C06a / F44 / 0007 D5 — latch cause: power-up
  #Cause_PwrUp := S #FirstScan

Scrubber.xml NETWORK 11 -- C06a / F44 / 0007 D5 — first-out 1: E-STOP (only if none)
  IF (#FirstOut = 0) AND NOT #EStopOK THEN  MOVE  1  ->  #FirstOut

Scrubber.xml NETWORK 12 -- C06a / F44 / 0007 D5 — first-out 2: PSH-101 (only if none)
  IF (#FirstOut = 0) AND NOT #PSH THEN  MOVE  2  ->  #FirstOut

Scrubber.xml NETWORK 13 -- C06a / F44 / 0007 D5 — first-out 3: LSHH-103 (only if none)
  IF (#FirstOut = 0) AND NOT #LSHH THEN  MOVE  3  ->  #FirstOut

Scrubber.xml NETWORK 14 -- C06a / F44 / 0007 D5 — first-out 4: power-up (only if none)
  IF (#FirstOut = 0) AND #FirstScan THEN  MOVE  4  ->  #FirstOut

Scrubber.xml NETWORK 15 -- C06a / F44 / 0007 D5 — healthy RESET clears all causes and first-out last
  #Cause_EStop := R #ResetPulse AND #PSH AND #LSHH AND #EStopOK
  #Cause_PSH := R #ResetPulse AND #PSH AND #LSHH AND #EStopOK
  #Cause_LSHH := R #ResetPulse AND #PSH AND #LSHH AND #EStopOK
  #Cause_PwrUp := R #ResetPulse AND #PSH AND #LSHH AND #EStopOK
  IF #ResetPulse AND #PSH AND #LSHH AND #EStopOK THEN  MOVE  0  ->  #FirstOut

Burner.xml NETWORK 15 -- R-11 / D6 / 0007 — not Enabled: take all four parameters
  IF NOT #Enabled THEN  MOVE  #SP  ->  #SP_Act
  IF NOT #Enabled THEN  MOVE  #HYST  ->  #HYST_Act
  IF NOT #Enabled THEN  MOVE  #STG  ->  #STG_Act
  IF NOT #Enabled THEN  MOVE  #TStart  ->  #TStart_Act

Burner.xml NETWORK 16 -- R-11 / D6 / 0007 — not Active: take TStart
  IF NOT #Active THEN  MOVE  #TStart  ->  #TStart_Act

Burner.xml NETWORK 17 -- R-11 / D6 / 0007 — lower SP applies at once
  IF (#SP <= #SP_Act) THEN  MOVE  #SP  ->  #SP_Act

Burner.xml NETWORK 18 -- R-11 / D6 / 0007 — higher HYST applies at once
  IF (#HYST >= #HYST_Act) THEN  MOVE  #HYST  ->  #HYST_Act

Burner.xml NETWORK 19 -- R-11 / D6 / 0007 — higher STG (less 2nd stage) applies at once
  IF (#STG >= #STG_Act) THEN  MOVE  #STG  ->  #STG_Act

Burner.xml NETWORK 20 -- R-11 / D6 / 0007 — pending while any entry differs from its active copy
  #ParPending := ((#SP <> #SP_Act) OR (#HYST <> #HYST_Act) OR (#STG <> #STG_Act) OR (#TStart <> #TStart_Act))

HmiMap.xml NETWORK 1 -- C01 / 0007 H-05 — Common.x0: E-STOP active or not reset; clears: Release E-STOP and RESET
  "HmiAlm.Common.%X0" := "Sys.Alm_EStop"

HmiMap.xml NETWORK 2 -- C03 / C06a (PH proposal: cause memory) / 0007 H-05 — Common.x1: Scrubber trip: high pressure PSH-101; clears: RESET with all scrubber trip causes healthy
  "HmiAlm.Common.%X1" := "Scrubber_DB.Cause_PSH"

HmiMap.xml NETWORK 3 -- C05 / C06a (PH proposal: cause memory) / 0007 H-05 — Common.x2: Scrubber trip: high-high level LSHH-103; clears: RESET with all scrubber trip causes healthy
  "HmiAlm.Common.%X2" := "Scrubber_DB.Cause_LSHH"

HmiMap.xml NETWORK 4 -- S-01 / C06a (PH proposal) / 0007 H-05 — Common.x3: Scrubber held after power-up: RESET required; clears: RESET with all scrubber trip causes healthy
  "HmiAlm.Common.%X3" := "Scrubber_DB.Cause_PwrUp"

HmiMap.xml NETWORK 5 -- C04 (Client) / 0007 H-05 — Common.x4: Scrubber high level LSH-102; clears: Automatically when level returns
  "HmiAlm.Common.%X4" := "Scrubber_DB.Alm_LSH"

HmiMap.xml NETWORK 6 -- R-11 / 0007 H-05 — Common.x5: Setting rejected: out of range; clears: RESET; old value restored on rejection (existing Common latch)
  "HmiAlm.Common.%X5" := "Sys.Alm_ParRejected"

HmiMap.xml NETWORK 7 -- C01 / 0007 H-05 — BR01.x0: BR01 stopped by E-STOP: RESET + START; clears: RESET after fault causes clear; START to run
  "HmiAlm.BR01.%X0" := "BR01_DB.F_EStop"

HmiMap.xml NETWORK 8 -- C07d / 0007 H-05 — BR01.x1: BR01 thermocouple fault; clears: RESET after repair
  "HmiAlm.BR01.%X1" := "BR01_DB.F_TC"

HmiMap.xml NETWORK 9 -- C07e / 0007 H-05 — BR01.x2: BR01 burner lockout; clears: RESET after burner control box lockout cleared
  "HmiAlm.BR01.%X2" := "BR01_DB.F_Lockout"

HmiMap.xml NETWORK 10 -- C07f / 0007 H-05 — BR01.x3: BR01 failed to start; clears: RESET after fault causes clear
  "HmiAlm.BR01.%X3" := "BR01_DB.F_NoStart"

HmiMap.xml NETWORK 11 -- C07g / 0007 H-05 — BR01.x4: BR01 stopped by itself; clears: RESET after fault causes clear
  "HmiAlm.BR01.%X4" := "BR01_DB.F_RunLost"

HmiMap.xml NETWORK 12 -- R-09 / 0007 H-05 — BR01.x5: BR01 RUN without request; clears: RESET with RUN off and fault causes clear
  "HmiAlm.BR01.%X5" := "BR01_DB.F_RunWrong"

HmiMap.xml NETWORK 13 -- C07a (PH proposal: alarm; Client: permissive) / 0007 H-05 — BR01.x6: TK01 level low: burner held; clears: Automatically when level returns
  "HmiAlm.BR01.%X6" := NOT "BR01_DB.LevelOK"

HmiMap.xml NETWORK 14 -- C01 / 0007 H-05 — BR02.x0: BR02 stopped by E-STOP: RESET + START; clears: RESET after fault causes clear; START to run
  "HmiAlm.BR02.%X0" := "BR02_DB.F_EStop"

HmiMap.xml NETWORK 15 -- C08d / 0007 H-05 — BR02.x1: BR02 thermocouple fault; clears: RESET after repair
  "HmiAlm.BR02.%X1" := "BR02_DB.F_TC"

HmiMap.xml NETWORK 16 -- C08e / 0007 H-05 — BR02.x2: BR02 burner lockout; clears: RESET after burner control box lockout cleared
  "HmiAlm.BR02.%X2" := "BR02_DB.F_Lockout"

HmiMap.xml NETWORK 17 -- C08f / 0007 H-05 — BR02.x3: BR02 failed to start; clears: RESET after fault causes clear
  "HmiAlm.BR02.%X3" := "BR02_DB.F_NoStart"

HmiMap.xml NETWORK 18 -- C08g / 0007 H-05 — BR02.x4: BR02 stopped by itself; clears: RESET after fault causes clear
  "HmiAlm.BR02.%X4" := "BR02_DB.F_RunLost"

HmiMap.xml NETWORK 19 -- R-09 / 0007 H-05 — BR02.x5: BR02 RUN without request; clears: RESET with RUN off and fault causes clear
  "HmiAlm.BR02.%X5" := "BR02_DB.F_RunWrong"

HmiMap.xml NETWORK 20 -- C08a (PH proposal: alarm; Client: permissive) / 0007 H-05 — BR02.x6: TK02 level low: burner held; clears: Automatically when level returns
  "HmiAlm.BR02.%X6" := NOT "BR02_DB.LevelOK"

Main.xml NETWORK 6 -- 0007 / H-05 — HMI alarms (writes HmiAlm only)
  CALL FC "HmiMap"
```


## مخرجات بوابات التسليم بالنص

`py tools\build_ce.py` — `exit 0`:

```text
saved D:\tasks\burner\tools\..\deliverables\PH-LCP-01-CE_RevA.xlsx
```

`py tools\build_blocks.py` — `exit 0`:

```text
wrote 13 files to build\blocks
import order: -Files blocks\Par.xml,blocks\Sys.xml,blocks\HmiAlm.xml,blocks\Common.xml,blocks\Scrubber.xml,blocks\Scrubber_DB.xml,blocks\Burner.xml,blocks\BR01_DB.xml,blocks\BR02_DB.xml,blocks\Outputs.xml,blocks\HmiMap.xml,blocks\Startup.xml,blocks\Main.xml
```

`py tools\check_docs.py` — `exit 0`:

```text
OK — docs consistent
```

نتيجة المراجعة المستقلة بالنص (فحص محلي للـ `netlist`، من غير كتابة ملفات):

```text
PASS: all 13 generated XML files equal in-memory generator output
PASS: raw Scrubber Parts/Wires cause/first-out/reset behavior 2560 input/state combinations
PASS: raw Burner R-11 Parts/Wires apply/pending behavior 324 boundary-direction/state combinations
PASS: all 20 HmiMap raw coil targets are HmiAlm Word slices
PASS: all mirrored FB/instance DB member name/type/order signatures match
```

