# 2026-11-12 — التحقق من مصدر الـ DLX 53 SHFP على النت

**السؤال:** هل الملف اللي عندنا في `inputs/manuals/` هو الداتاشيت المنشور، ولا فيه نسخة أكبر
وأكمل منه؟

**الحالة:** تأكد من النت، وقارن بالمحلي. **لم يتغيّر أي قرار** — ده دليل إضافي فقط.

---

## 1. الطريقة

- بحث بالاسم: `Oxilon DLX 53 SHFP`، `Oxilon DLX series catalogue`، `SQ DUAL sequence controller`.
- نُزّل ملفّين من موقع Oxilon الرسمي (`oxilonburners.com`) ومن أرشيف بائع قديم.
- استُخرج النص بـ `pypdf` (نص + جداول + صور مضمّنة)، وقُورن بالمحلي.

## 2. المحصّل: عندنا في `inputs/` ≠ المنشور على النت

| الملف | هوية الملف | مصدره |
|---|---|---|
| `inputs/manuals/DLX 53 SHFP.pdf` (1 صفحة) | **مخطط توصيلات خاص بالمشروع**، `Rev A1`، تاريخ `31-12-2025`، `Created by: Hemant Patel` / `Pass by: Vinod Yadav` | Oxilon — **مصمم للوظيفة دي**، مش كتالوج |
| `inputs/manuals/Operational Manual - DLX 53 SHFP.pdf` (18 صفحة) | الكتالوج التشغيلي الرسمي من Oxilon (`General Information and Operating Manual`، `ISO 9001:2015`) | Oxilon — **منشور** |

**المهم:** مخطط التوصيلات المحلي **أثمن من الكتالوج** لأنه الواجهة الحقيقية للوحدة في الموقع.
هو اللي بيقول لنا الأطراف والـ socket والـ SV1/SV2.

## 3. المنشور على النت (نُزّل إلى `references/`)

| الملف | حجم | مصدره |
|---|---|---|
| `references/Oxilon_DLX_Series_Catalogue.pdf` | 2 صفحة | الرسمي: `oxilonburners.com/static/images/technical-data-sheet/dual-fuel-burner/light-gas-oil/DLX Series Catalogue.pdf` |
| `references/Oxilon_Master_Catalogue_48p.pdf` | 48 صفحة | أرشيف بائع (`imimg.com`) — الكتالوج العام لكل السلاسل |

**اللي في الكتالوج العام (48 صفحة) — العائلات:**

| السلسلة | نوع التشغيل | صفحة |
|---|---|---|
| `DLX` | **Single Stage** (غاز + زيت خفيف) | 20–21 |
| `ABDX` | **Two Stage** (Hi/Low) | 22–23 |
| `DMDX` | Fully Modulating | 25–26 |
| `DLXZ` | Single Stage (غاز + زيت ثقيل) | 36–37 |
| `ABXZ` | Two Stage (غاز + زيت ثقيل) | 38–39 |

**مهم:** الكتالوج فيه `DLX 53 SH/EH/CH` — **مفيش `SHFP`**. ولاحقة `SH/EH/CH` موجودة على
كل موديل في كل السلاسل والكتالوج **بيفسرّها**، فما نعرفش معناها.

**مهم 2:** `SQ DUAL` (الـ sequence controller) — **مالوش أي وجود علني**. البحث على النت رجّع
صفر نتيجة. مش Baltic/Baltur/Siemens ولا حاجة معروفة. Manual بتاعه غير متاح إلا من Oxilon.

## 4. نتيجة `F16` / `F25` — التعارض اتحدد، بس اتقفلش

اللي اتأكد:

1. الكتالوج الرسمي وصف موقع Oxilon: سلسلة `DLX` = **"Single Stage Dual Fuel Burners"**،
   "Single Stage Operation (ON/OFF)"، "Single switch operation to change the fuel".
2. ومخطط المشروع المحلي (ص1) مكتوب فيه **"Stage: Single Stage Operation"** — متوافق مع العائلة.
3. **بس نفس مخطط المشروع** بيوصل `SV1` (low) و`SV2` (high)، وبيوصل `T1`/`T2` = "high/Low
   Interlocks" جوّه الـ `SQ DUAL`، وفيه "High/Low Switch".
4. والرسم `Burner_V1.pdf` ص8 بيوصّل `R7` → `BR02:T2` → **`SV2 / high fire`**، و`T1` = "high/low
   interlock"؛ والصنف `BR02 HIGH FIRE`.

**يعني التعارض مش بين مستندين — التعارض جوّه مستند العميل نفسه:**
مخطط واحد مكتوب فيه "Single Stage" وفي نفس الوقت بيوصّل صمام الغاز العالي `SV2` والـ `T1`/`T2`.

**التفسير الأقرب (استنتاج، مش حقيقة):** عائلة `DLX` معروضة كـ Single Stage في الكتالوج،
ووحدة المشروع فيها خيار الـ Hi/Low (صمامين غاز + مfachيل عالي/منخفض). يمكن يكون `SHFP`
Suffix عميل لنوع بناء معيّن (أسطوانة/لوح/مروحة/باور) مش معروف للكتالوج.
**مش دليل** — ماينفعش نقفل بيه `F16`.

**قرار التشغيل ما يتغيرش:** `F25` قائم بالفعل — «الرسم هو الأساس» بتأكيد المستخدم 2026-10-27،
والـ C&E بيمشي على `R7` → high fire حسب الرسم. المراجع العلنية **دعمت** إن التعارض حقيقي
ومسجّل، **يعني هي اللي هتحسم `F16`** مش الكتالوج.

## 5. مراجعة الكتالوج التشغيلي المحلي (18 صفحة) — نفس التعارض القديم

نص الكتالوج المحلي فيه تناقضات داخلية، زي ما كان مسجّل في `F25`:

- ص14: `Blower pre-purge timing cycle - 50 seconds`
- ص15: `prepurging ... about 13 seconds`
- ص14: `Safety ignition timing - 5 seconds` · `Ignition valve safety time - 5 seconds` ·
  `Main valve modulation signal time - 10 seconds`
- ص15: `switches the burner into safety condition within 10 seconds` ·
  `manual rearming ... not before 30 seconds are elapsed`

**تدقيق جديد:** الكتالوج المحلي فيه **كتابة منقولت من manual بيرنر زيت** — `oil cock`،
`oil filter`، `fuel pump pressure 12 bar diesel / 8 bar kerosene`، `oil return pipe`،
`Please do not allow the oil pump working without oil for more than three minutes` —
ووحدة `DLX 53 SHFP` **غاز/زيت (Dual Fuel)**، والوش Fire monitoring = `Multi fuel flame sensor`.
يعني الص14 (المابتس séquence) هو المظبوط للوحدة دي، وص15 boilerplate بيرنر زيت.

## 6. تغيير الوقود (`C08h`) — متسق مع المنشور

- `Burner_V1.pdf` ص11 و ص16: `XI2:1 → I12.0` = `Rfuel2` **"BR02 DIESEL MODE"** — سلك **field supply**
  من عند العميل، موصّل على تاج `S4` (BR01 AUTO/MAN) بنفس الكلة.
- المنشور: "Single switch operation to change the fuel" + "**Standard version running on manual
  fuel selection mode** and on request **automatic fuel changeover** is available. The automatic
  changeover system can be trigged by gas pressure or by a timer."

**النتيجة:** اختيار الوقود في المعيار **مفتاح يدوي**، والتغيير الآلي **بالحسب** (غاز/تايمر).
يعني الـ PLC **يقرأ** حالة المفتاح (`I12.0`) — وده بالظبط اللي `C08h` بيعمله (Trip لو المفتاح
اتغيّر والـ START شغّال). **ما فيه تعارض**، و`C08h` مؤكَّد بالرس��م.

## 7. حدود النتيجة

- الكتالوج المنشور **لا يغطي `SHFP`** ولا يشرح `SH/EH/CH`، فمالوش قيمة في تحديد behaviour
  الوحدة بالتحديد.
- `SQ DUAL` غير موثّق علنيًا → `F49` (هل DLX بيقبل remote reset؟) **يفضل مفتوح** لحد ما
  Oxilon يدي manual أو Engineers يقرروا في الموقع.
- الأرقام (50 ث / 13 ث purge) مش متحسمّة من أي مصدر عام — تفضل إعدادات تشغيل، مش متطلبات.
- التحقق على **النص المكتوب** في الملفات فقط. لو عايز نثبّت الواجهة لازم فحص بصري للوحدة في الموقع
  أو letter من Oxilon.

## 8. بصمات

SHA-256، وقت التحقق:

| الملف | SHA-256 |
|---|---|
| `inputs/manuals/DLX 53 SHFP.pdf` | `7dc1c268beff78f1ab87630c3ddb3dba44bf897b0fe36e030e79d5eb2ff43db5` |
| `inputs/manuals/Operational Manual - DLX 53 SHFP.pdf` | `92d6c33c328013e8c173426663b0e7bcdb3d30345fa624f75e5e9d90092015a7` |
| `references/Oxilon_DLX_Series_Catalogue.pdf` | `5f74eb6093aa7ab8134fd337e4238e82b30c2d19f6e8d5808386747cfffd929d` |
| `references/Oxilon_Master_Catalogue_48p.pdf` | `0b587f4e2f0a03cee21f06c4258c921df9ba918e0d44225ca518e39c1ad85a46` |

> الهاش بتاع الملفين المحليين **مطابق** للمسجّل في
> `docs/evidence/2026-10-27-original-sources-review.md` — يعني الملفات دي ماتغيّرتش.

**ملاحظة على `references/`:** ده مجلد جديد في شجرة المشروع، مش جزء من `inputs/`.
محتواه **مش أصول العميل** — ملفات منشورة على النت، مرفوعة كمرجع. `inputs/` ما اتلمسش.
