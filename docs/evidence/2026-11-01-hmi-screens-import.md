# 2026-11-01 — شاشات الـ KTP400 اتعملها import (P5 من 0007)

**مين:** أنا كتبت `tools/build_hmi.py` و`tools/Apply-Hmi.ps1`. وCodex (`gpt-6.1-sol`) كتب
`tools/check_hmi_xml.py` وصلّح الخصايص. الـ check بيقارن كل خاصية وlink وchild بـ exports حقيقية
من V15.1 (عيّنة P1، وشاشات الأوناش، والـ Root screen بتاع المشروع).

**قبل:** `baseline/tia-before-hmi-screens_2026-11-01_*.zip`.

**الأخطاء اللي TIA طلّعها، واتصلّحت:**

| الخطأ | الحل |
|---|---|
| `The HMI data type Time was not found` | الـ `Time` بيتقري `DInt` على الشاشة (ms) |
| `The HMI data type Word was not found` | الـ `Word` بيتقري `UInt` |
| `CornerRadius ... Rectangle ... is not supported` | `RoundCornerHeight` و`RoundCornerWidth` |
| بعد أول import فاشل، الـ project كله بيبقى disposed | `Apply-Hmi.ps1` بيقف عند أول فشل، ومش بيحفظ |

**النتيجة بالنص:**

```
OK   Tags_LCP01.xml
OK   Screen_Alarms.xml
OK   Screen_BR01.xml
OK   Screen_BR02.xml
OK   Screen_Root_screen.xml
OK   Screen_Scrubber.xml
OK   Screen_Settings.xml
HMI compile: state=Success errors=0 warnings=0
SAVED
```

78 تاج، و6 شاشات. الشاشات الست: Overview (اسمها `Root screen` عشان تفضل start screen)، وBR01،
وBR02، وScrubber، وAlarms، وSettings.

**لسه:** الإنذارات (discrete alarms)، والـ alarm view بالإيد، والمستخدم `Engineer`، والصلاحية على حقول
Settings. وكمان الاختبار على المحاكي مع PLCSIM (P7).
