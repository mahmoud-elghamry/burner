# 2026-11-02 — PLCSIM بعد تعديل الدرين NC

**البرنامج:** `tools/build_blocks.py` بعد قرار الاجتماع (`2026-11-02-scrubber-drain-nc.md`). اتعمله import:
- التاجات: `consistent 13/13`، و`CLEAN. PROJECT SAVED.`
- البلوكات الـ 13: كل بلوك `0 errors 0 warnings`، و`consistent 13/13`، و`CLEAN. PROJECT SAVED.`
- الشاشة: Tags وRoot screen وScrubber وSettings بس، و`HMI compile 0 errors 0 warnings`، و`SAVED`.
  شاشة Alarms ماتعملهاش import، عشان مانمسحش أي حاجة اتحطت عليها بالإيد.

**التنزيل:** المستخدم نزّل من TIA. أول مرة نزّل من نسخة قديمة في `D:\tia\Burner` (من قبل الاجتماع)، فالاختبار
اتوقف من غير نتيجة. بعدين اتأكدت من عنوان شباك TIA: `D:\tasks\burner\tia\Burner\Burner`، وده اللي اتختبر.

## النتيجة: 18 سيناريو، 83 خطوة، PASS

`py tools\plcsim\run_scenarios.py`. السيناريو الجديد `T7b`، و`T7` اتكتب من الأول، و`T1` و`T8` اتظبطوا على
الدرين NC (الطبيعي `Q0.3`=0).

```
T7 - scrubber high pressure / high-high level: burners keep running
  ok   PSH-101: flare open, suction closed, drain untouched, BR01 runs (C03)  TL1=1 XV401=0 XV402=0 XV403=0
  ok   PSH back: flare/suction stay until RESET  XV401=0 XV403=0
  ok   RESET: valves normal, BR01 untouched (R-07)  TL1=1 XV401=1 XV402=0 XV403=1
  ok   LSHH-103: suction closed at once, flare untouched (C05)  TL1=1 XV401=1 XV403=0
  ok   LSHH-103 + 3 s: drain open (C05)  XV401=1 XV402=1 XV403=0
  ok   RESET while LSHH still open: suction stays closed  XV402=1 XV403=0
  ok   level down: drain still open (TDRN_OFF), suction closed until RESET  XV402=1 XV403=0
  ok   level gone 5 s: drain closed, suction still closed  XV402=0 XV403=0
  ok   RESET: all normal  TL1=1 XV401=1 XV402=0 XV403=1
T7b - scrubber high level: drain follows the level (C04), E-STOP, power-up
  ok   LSH-102: drain not yet (debounce TDRN_ON)  XV401=1 XV402=0 XV403=1
  ok   LSH-102 + 3 s: drain open, flare/suction untouched (C04)  XV401=1 XV402=1 XV403=1
  ok   float bounce: drain stays open  XV402=1
  ok   level gone 5 s: drain closed, no RESET needed  XV401=1 XV402=0 XV403=1
  ok   high level again: drain open  XV402=1
  ok   E-STOP: drain closed even on high level (C01)  XV401=0 XV402=0 XV403=0
  ok   E-STOP released, no RESET: drain still closed  XV402=0
  ok   RESET: drain follows the level again  XV401=1 XV402=1 XV403=1
  ok   PLC STOP: drain closed (NC, C02)  XV401=0 XV402=0 XV403=0
  ok   power back, high level, no RESET: drain opens, flare/suction tripped  XV401=0 XV402=1 XV403=0
...
PASS
```

باقي السيناريوهات (T1…T6b وT8…BR02) كلها `ok`، ومفيش تغيير عن `2026-11-01-plcsim-regression-after-hmi-plc.md`.

## `T7d`: مهلة الدرين (`C04a`)، 10 دقايق، PASS

`py tools\plcsimun_scenarios.py T7d`

```
T7d - LSH-102 stuck open: drain closes after TDRN_MAX (C04a), 10 min
  ok   LSH-102 open: drain open  XV402=1
  ok   9.5 min: drain still open  XV402=1
  ok   10 min: drain closed by timeout (C04a)  XV401=1 XV402=0 XV403=1
  ok   RESET: drain follows the level again  XV402=1
  ok   level back: drain closed  XV402=0
PASS
```

## مش متختبر هنا

- `C04b` (إنذار `LSH-102` بايظ) وبتات `HmiAlm` `x6`/`x7`: مالهمش مخرج، والاختبار بيقرا `Q` بس. يتجرّبوا من watch table.
- `TDRN_*` من الشاشة: نفس قيد R-11 (مفيش كتابة على الـ DB).
