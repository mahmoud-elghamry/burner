# 2026-10-28 — اختبار PLCSIM: سيناريوهات §6 كلها PASS

**إزاي:** البرنامج اتنزّل على S7-PLCSIM V15.1 من TIA (Start simulation، ثم Load). وبعدها
`py tools\plcsim\run_scenarios.py` غيّر المداخل وقرا المخارج أوتوماتيك، عن طريق `build/plcsim/PlcSimCtl.exe`
(`evidence/2026-10-28-plcsim-automation.md`). كل سيناريو بيبدأ بـ PLC STOP ثم RUN، وبعدها RESET.
الكود اللي اتختبر هو commit `55789c1` (فيه فرق الدرجتين `F41`).

**النتيجة: 17 سيناريو، 75 خطوة، `PASS`، و`exit=0`.**

## الـ 17 سيناريو في جدول واحد

| # | السيناريو | المرجع | خطوات | النتيجة |
|---|---|---|---|---|
| T1 | يوم عادي في AUTO: يولّع، والعالي تحت 60، والواطي عند 62، ويقف عند 70، ويرجع عند 65 | `C07b` `C07c` `F41` §6-1 | 10 | ✅ |
| T1b | الحرارة = الأعلى بين الثيرموكابلين | `C07b` | 1 | ✅ |
| T2 | التانك فضي وهو شغال: يقف، ويرجع لوحده | `C07a` §6-2 | 2 | ✅ |
| T3 | اللهب طفى (lockout): عطل، ومحتاج RESET وبعده START | `C07e` §6-3 | 4 | ✅ |
| T4 | مولّعش في 120 ث: عطل | `C07f` §6-4 | 5 | ✅ |
| T5 | وقف لوحده وهو شغال: عطل | `C07g` §6-5 | 3 | ✅ |
| T6 | ثيرموكابل بايظ (32767، و−32768، و250 درجة): يقف فورًا، وعطل | `C07d` §6-6 | 9 | ✅ |
| T6p | بعد رجوع الكهربا الكارت بيدّي 32767 لثواني: مش عطل | R-10 | 2 | ✅ |
| T6b | STOP وSTART مع بعض، وSTART محشور وقت رجوع الكهربا | R-05 §6-6ب | 4 | ✅ |
| T7 | ضغط الـ scrubber أو المستوى العالي جدًا: صمامات آمنة، والبيرنرات تكمّل | `C03` `C04` `C05` §6-7 | 6 | ✅ |
| T8 | E-STOP: كله يقف، وبعد RESET الـ scrubber يرجع والبيرنرات لأ | `C01` B-02 §6-8 | 5 | ✅ |
| T9 | الكهربا قطعت ورجعت | `C02` S-01 §6-9 | 3 | ✅ |
| T10 | MAN: دورة واحدة | R-03 §6-10 | 4 | ✅ |
| R01 | START والتانك واطي بيترفض | R-01 | 1 | ✅ |
| R02 | تغيير AUTO/MAN وهو شغال: يقف، ومحتاج START | R-02 | 2 | ✅ |
| R09 | RUN من غير طلب لمدة 30 ث: عطل | R-09 | 2 | ✅ |
| BR02 | BR02: اللمبات، والديزل، والـ STOP، ومستقل عن BR01 | `C08*` R-07 R-12 `F13` | 7 | ✅ |

## المخرج بالنص

```
T1 — يوم عادي: AUTO، 40 ثم 60 ثم 70 ثم 65
  ok   after power-up + RESET: burners off, valves normal  TL1=0 TR1=0 XV401=1 XV402=1 XV403=1
  ok   START at 40 degC -> STARTING: TL on, no 2nd stage  TL1=1 TR1=0
  ok   RUN -> RUNNING below 60: 2nd stage  TL1=1 TR1=1
  ok   60 degC: 2nd stage stays (2 degC band, F41)  TL1=1 TR1=1
  ok   62 degC: 1st stage only  TL1=1 TR1=0
  ok   59.9 degC: 2nd stage again  TL1=1 TR1=1
  ok   61 degC: still 2nd stage (band)  TL1=1 TR1=1
  ok   70 degC: stop (C07b)  TL1=0 TR1=0
  ok   68 degC: stays off (hysteresis)  TL1=0
  ok   65 degC: restarts by itself in AUTO  TL1=1
T1b — الحرارة = الأعلى بين الاتنين (C07b)
  ok   outlet 70, inlet 40: stops on the higher one  TL1=0
T2 — التانك فضي وهو شغال
  ok   LSL lost: stop (C07a)  TL1=0
  ok   LSL back: restarts by itself (AUTO)  TL1=1
T3 — اللهب طفى (lockout)
  ok   lockout: request off (C07e)  TL1=0 TR1=0
  ok   lockout cleared at burner, START without RESET: refused  TL1=0
  ok   RESET: still off, needs START (B-02)  TL1=0
  ok   START after RESET: runs  TL1=1
T4 — مولّعش خلال T_START (120 ث)
  ok   STARTING  TL1=1
  ok   118 s: still waiting  TL1=1
  ok   122 s, no RUN: FAULT (C07f)  TL1=0
  ok   START without RESET: refused  TL1=0
  ok   RESET + START: runs  TL1=1
T5 — وقف لوحده وهو شغال
  ok   RUN lost, no lockout: FAULT (C07g)  TL1=0
  ok   START without RESET: refused  TL1=0
  ok   RESET + START: runs  TL1=1
T6 — ثيرموكابل بايظ: 32767، و-32768، و2500 — على قناة واحدة
  ok   TE-501 = 32767: request off at once  TL1=0
  ok   TE-501 good again, START without RESET: refused (C07d FAULT)  TL1=0
  ok   RESET + START: runs  TL1=1
  ok   TE-501 = -32768: request off at once  TL1=0
  ok   TE-501 good again, START without RESET: refused (C07d FAULT)  TL1=0
  ok   RESET + START: runs  TL1=1
  ok   TE-501 = 2500: request off at once  TL1=0
  ok   TE-501 good again, START without RESET: refused (C07d FAULT)  TL1=0
  ok   RESET + START: runs  TL1=1
T6p — R-10: بعد رجوع الكهربا الكارت بيدّي 32767 لثواني — مش عطل لو رجع قبل 10 ث
  ok   TC still calibrating: START refused, no heat  TL1=0
  ok   TC valid within 10 s: START accepted  TL1=1
T6b — STOP وSTART مع بعض، وSTART محشور
  ok   STOP + START together: off (STOP wins)  TL1=0
  ok   STOP released, START still held: off  TL1=0
  ok   START held through PLC STOP/RUN: off (R-05)  TL1=0
  ok   released and pressed again: runs  TL1=1
T7 — ضغط الـ scrubber عالي — البيرنرات تكمّل
  ok   PSH-101: valves safe, BR01 keeps running (C03)  TL1=1 XV401=0 XV402=0 XV403=0
  ok   PSH back: valves stay safe until RESET  XV401=0 XV402=0 XV403=0
  ok   RESET: valves normal, BR01 untouched (R-07)  TL1=1 XV401=1 XV402=1 XV403=1
  ok   LSHH-103: valves safe (C05)  TL1=1 XV401=0 XV402=0 XV403=0
  ok   RESET while LSHH still open: stays tripped  XV401=0 XV402=0 XV403=0
  ok   LSH-102: alarm only, valves stay (C04)  XV401=1 XV402=1 XV403=1
T8 — E-STOP
  ok   both burners running  L2=1 TL1=1
  ok   E-STOP: everything off, valves safe (C01)  L2=0 T2=0 TL1=0 TR1=0 XV401=0 XV402=0 XV403=0
  ok   E-STOP released: still off  L2=0 TL1=0 XV403=0
  ok   RESET: scrubber back, burners stay off (B-02)  L2=0 TL1=0 XV401=1 XV403=1
  ok   START each: both run  L2=1 TL1=1
T9 — الكهربا قطعت ورجعت
  ok   PLC STOP: all outputs off (C02)  TL1=0 XV401=0 XV403=0
  ok   RUN again: scrubber tripped, burner off (S-01, B-02)  TL1=0 XV401=0 XV403=0
  ok   RESET: scrubber normal, burner still off  TL1=0 XV401=1 XV403=1
T10 — MAN: دورة واحدة
  ok   MAN + START: runs  TL1=1
  ok   70 degC: stops  TL1=0
  ok   60 degC: does NOT restart (MAN)  TL1=0
  ok   new START: runs  TL1=1
R01 — START والمستوى واطي بيترفض
  ok   START with LSL low was refused: off (R-01)  TL1=0
R02 — تغيير AUTO/MAN وهو شغال
  ok   AUTO -> MAN while running: off (R-02)  TL1=0
  ok   back to AUTO: stays off, needs START  TL1=0
R09 — RUN شغال من غير طلب 30 ث
  ok   RUN without request 30 s: FAULT, START refused (R-09)  TL1=0
  ok   RESET + START: runs  TL1=1
BR02 — BR02: نفس المنطق، واللمبات، والديزل، والاستقلال عن BR01
  ok   BR02 START: L and lamp H5  H5=1 H6=0 L2=1 T2=0
  ok   BR02 RUN below 60: T2 and lamp H6  H5=1 H6=1 L2=1 T2=1
  ok   BR01 lockout: BR02 keeps running  L2=1 TL1=0
  ok   RESET for BR01: BR02 untouched (R-07)  L2=1 T2=1
  ok   fuel changed while running: BR02 off (R-12)  H5=0 L2=0
  ok   new START: BR02 runs  L2=1
  ok   S7 STOP: BR02 off  L2=0
PASS
```

## حدود الاختبار

- **بيشوف المخارج بس (`%Q`).** نوع العطل نفسه (`F_TC` و`F_NoStart`…) مش باين، لأن PLCSIM مش بيقرا DB.
  الـ FAULT بيتعرف من السلوك: الطلب بيقع، وSTART من غير RESET بيترفض، وRESET وبعده START بيشغّل.
- **رد `SetInput` مش دقيق:** بيقول `AddressOutOfRange` للبايتات غير 0، مع إن الكتابة بتوصل. والدليل إن كل خطوة
  "RESET + START: runs" نجحت، ودي محتاجة `I1.1` و`I0.4` و`I12.3` يوصلوا فعلاً.
- **مااتختبرش هنا:** إيقاف الـ 24 ساعة (`C07h`/R-08)، والأرقام بره المدى (R-11)، وإنذارات الشاشة. دول بالإيد من
  watch table. وكمان الحاجات اللي محتاجة الموقع: الأسلاك fail-safe، و`32767` من الكارت الحقيقي، ووقت الولعة الحقيقي.
