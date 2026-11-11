# 2026-11-11 — Import Rev. B في نسخة من مشروع المستخدم

- المستخدم اختار مشروعه `D:\tasks\burner\tia\Burner`، وآخر حفظ ليه 3:16 PM. `TIA` كان مقفول.
  اتنسخ بـ robocopy `/MIR` لـ `tia\Burner` جوه الـ worktree `simplify-revb`، والملفات المنسوخة 51.
  **الأصل ما اتلمسش**، وهو المرجع لو احتجنا نرجع.
- **Apply-Blocks:** اتعمل Import للـ 13 بلوك بالترتيب، ومعاه `CompileOrder`. كل بلوك طلع `Success`، و**0 errors و0 warnings**، و**consistent 13/13**،
  و`CLEAN. PROJECT SAVED.`
  - `Main` كتب Information: "updated calls" في networks 2 و3 و4. ده متوقع، لإن واجهة `Burner` اتشال منها `Reset`.
  - التقرير الحرفي: `2026-11-11-revb-import/apply-blocks.log`.
- **Apply-Hmi:** اتعمل Import لجدول `Tags_LCP01` والـ 5 صفحات: Overview وBR01 وBR02 وScrubber وSettings.
  **صفحة Alarms ما اتعملهاش Import**، فالـ Alarm View اليدوي فضل. HMI compile: `Success`، و0 errors و0 warnings، و`SAVED`.
  التقرير الحرفي: `2026-11-11-revb-import/apply-hmi.log`.
- **Export للتحقق ما اتعملش:** المستخدم فتح `D:\New folder\Burner` في `TIA` الساعة 7:16 PM، والـ Export بيرفض يشتغل على مشروع غير المفتوح. `TIA` ما اتقفلش.
- **لسه:**
  - Export ومقارنة.
  - إنذارات الشاشة: تتمسح الـ 24 القديمة، ويتعمل Import للـ 16 الجديدة من `build/hmi/Alarms_LCP01.xlsx` بالإيد.
    الـ compile عدّى، لإن الإنذارات القديمة بتشاور على بتات لسه موجودة، بس **نصوصها غلط**.
  - صلاحيات Settings لو كانت متعملة.
  - `PLCSIM`.
  - **ما اتنزّلش أي حاجة على PLC الورشة.**
