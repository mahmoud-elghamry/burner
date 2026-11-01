# 2026-11-01 — import بلوكات الشاشة في المشروع الأصلي (P2 وP3 من 0007)

**قبل التعديل (P2):**
- نسخة كاملة: `baseline/tia-before-hmi-plc_2026-11-01_2256.zip` (1.2 MB).
- export قبل التعديل: `baseline/export_2026-11-01_2256/`.
- أرقام `Par` في المشروع (offline) = الافتراضي: `SP`=700، و`HYST`=50، و`STG`=100، و`TStart`=`T#2M`.

**الـ import:** `Apply-Blocks.ps1` على الـ 13 ملف بالترتيب اللي في `docs/TOOLS.md`. TIA كان مقفول.
آخر التقرير بالنص:

```
  Main: state=Success errors=0 warnings=0
      [Success] Compiling finished (errors: 0; warnings: 0)

=== CONSISTENCY ===
  consistent 13/13

CLEAN. PROJECT SAVED.
```

- كل بلوك اتعمله compile لوحده، و`errors=0 warnings=0`. ومعناه إن **TIA قبل الـ slice access** (`"HmiAlm".Common.%X0`).
- `Main` فيه `Number of updated calls` في network 2 و3 و4، وده عادي لأن interface الـ `Scrubber` والـ `Burner` اتغيّر.

**الـ diff مع الـ export اللي قبله:** بعد ما شلنا الـ `ID` والـ `Created`، البلوكات اللي ماتغيّرتش (`Common`
و`Outputs` و`Par` و`Sys` و`Startup`) **مطابقة سطر بسطر**. واللي اتغيّر هو `Scrubber` و`Burner` والـ DBs
بتاعتهم و`Main`، وزيادة عليهم `HmiAlm` و`HmiMap` الجداد.

**لسه:** PLCSIM. الـ 17 سيناريو لازم يتعادوا على البرنامج الجديد.
