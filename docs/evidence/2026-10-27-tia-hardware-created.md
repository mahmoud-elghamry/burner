# 2026-10-27 — مشروع TIA اتعمل، والهاردوير اتعمله كومبايل

**مين:** المهندس زين في TIA V15.1، وأنا كنت بوجّهه خطوة خطوة بالصور.
**فين:** `tia/Burner/Burner.ap15_1`.

## الهاردوير

| الخانة | الجهاز | العنوان | مطابق للرسم؟ |
|---|---|---|---|
| 1 | CPU 1214C DC/DC/DC `6ES7 214-1AG40-0XB0`، FW **V4.2** (أعلى رقم في V15.1، `F38`) | — | ✅ |
| 2 | SM 1231 AI 8 x TC `6ES7 231-5QF32-0XB0` | `IW96` لـ `IW111` | ✅ صفحة 13 |
| 3 | SM 1221 DI 8 x 24VDC `6ES7 221-1BF32-0XB0` | **`I12.0` لـ `I12.7`** (اتغيّر من 8) | ✅ صفحة 11 |

الشاشة KTP400 **لسه متضافتش**، لأن مش معروف هي Basic ولا Comfort.

## إعدادات كارت الثيرموكابل (اتشافت في الصور)

- Integration time: **50 Hz (20 ms)**.
- القنوات 0 لـ 3: Thermocouple، وType K، وCelsius، وSmoothing Weak (4 cycles)، وInternal reference،
  و**broken wire** و**overflow** و**underflow** متعلّم عليهم. **الـ broken wire مكانش متعلّم
  عليه في الافتراضي، واتعلّم عليه** (ده اللي بيدّي `32767`، صف `C0xd`).
- القنوات 4 لـ 7: **Deactivated**.

## مخارج الـ CPU لما يقف (`F23`)

`Reaction to CPU STOP = Use substitute value`، و"Substitute a value of 1" فاضية في القنوات اللي
اتشافت في الصورة (Channel0 لـ 2). وزين قال إنه راجع الباقي. يعني المخارج تفصل لما الـ PLC يقف.

## الكومبايل

`Hardware (rebuild all)` ← **`Compiling finished (errors: 0; warnings: 1)`**. التحذير الوحيد:
"PLC_1 does not contain a configured protection level" (`F37`). اتحفظ، وTIA اتقفل
(اتأكدت إن مفيش `Siemens.Automation.Portal` شغال).

**السكريبتات (`F28`/`F29`) مااتجرّبتش على المشروع ده لسه.**
