# 2026-11-01 — PLCSIM بعد بلوكات الشاشة: الـ 17 سيناريو PASS

**إزاي:** المستخدم نزّل البرنامج الجديد (commit `5f3e1b6`، فيه `HmiAlm` و`HmiMap` وأسباب تريب الـ scrubber وD6) على PLCSIM من TIA، و`Loading completed (errors: 0; warnings: 0)`. وبعدين `py tools\plcsimun_scenarios.py` زي `2026-10-28-plcsim-scenarios-pass.md` بالظبط. وكان محاكي الشاشة شغال ومتوصّل في نفس الوقت.

**النتيجة: `PASS`، و`exit=0`، و70 خطوة `ok` من غير ولا `FAIL`.** يعني التعديلات مابوّظتش أي سلوك قديم.

**الجديد نفسه مااتختبرش هنا:** الأسباب و`FirstOut` وD6 و`ParPending` وبتات `HmiAlm` كلهم جوه DBs، وPLCSIM مش بيقرا DB (`2026-10-28-plcsim-automation.md`). دول هيتختبروا من الشاشة في P7.

## المخرج بالنص

```
T1 - normal day, AUTO: 40 -> 60 -> 62 -> 70 -> 65 degC
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
T1b - temperature = the higher of the two thermocouples
  ok   outlet 70, inlet 40: stops on the higher one  TL1=0
T2 - tank empty while running
  ok   LSL lost: stop (C07a)  TL1=0
  ok   LSL back: restarts by itself (AUTO)  TL1=1
T3 - flame out (lockout)
  ok   lockout: request off (C07e)  TL1=0 TR1=0
  ok   lockout cleared at burner, START without RESET: refused  TL1=0
  ok   RESET: still off, needs START (B-02)  TL1=0
  ok   START after RESET: runs  TL1=1
T4 - no ignition within T_START (120 s)
  ok   STARTING  TL1=1
  ok   118 s: still waiting  TL1=1
  ok   122 s, no RUN: FAULT (C07f)  TL1=0
  ok   START without RESET: refused  TL1=0
  ok   RESET + START: runs  TL1=1
T5 - stopped by itself while running
  ok   RUN lost, no lockout: FAULT (C07g)  TL1=0
  ok   START without RESET: refused  TL1=0
  ok   RESET + START: runs  TL1=1
T6 - thermocouple broken: 32767, -32768, 2500 on one channel
  ok   TE-501 = 32767: request off at once  TL1=0
  ok   TE-501 good again, START without RESET: refused (C07d FAULT)  TL1=0
  ok   RESET + START: runs  TL1=1
  ok   TE-501 = -32768: request off at once  TL1=0
  ok   TE-501 good again, START without RESET: refused (C07d FAULT)  TL1=0
  ok   RESET + START: runs  TL1=1
  ok   TE-501 = 2500: request off at once  TL1=0
  ok   TE-501 good again, START without RESET: refused (C07d FAULT)  TL1=0
  ok   RESET + START: runs  TL1=1
T6p - R-10: TC card reads 32767 for seconds after power-up
  ok   TC still calibrating: START refused, no heat  TL1=0
  ok   TC valid within 10 s: START accepted  TL1=1
T6b - STOP and START together, START jammed
  ok   STOP + START together: off (STOP wins)  TL1=0
  ok   STOP released, START still held: off  TL1=0
  ok   START held through PLC STOP/RUN: off (R-05)  TL1=0
  ok   released and pressed again: runs  TL1=1
T7 - scrubber high pressure / high-high level: burners keep running
  ok   PSH-101: valves safe, BR01 keeps running (C03)  TL1=1 XV401=0 XV402=0 XV403=0
  ok   PSH back: valves stay safe until RESET  XV401=0 XV402=0 XV403=0
  ok   RESET: valves normal, BR01 untouched (R-07)  TL1=1 XV401=1 XV402=1 XV403=1
  ok   LSHH-103: valves safe (C05)  TL1=1 XV401=0 XV402=0 XV403=0
  ok   RESET while LSHH still open: stays tripped  XV401=0 XV402=0 XV403=0
  ok   LSH-102: alarm only, valves stay (C04)  XV401=1 XV402=1 XV403=1
T8 - E-STOP
  ok   both burners running  L2=1 TL1=1
  ok   E-STOP: everything off, valves safe (C01)  L2=0 T2=0 TL1=0 TR1=0 XV401=0 XV402=0 XV403=0
  ok   E-STOP released: still off  L2=0 TL1=0 XV403=0
  ok   RESET: scrubber back, burners stay off (B-02)  L2=0 TL1=0 XV401=1 XV403=1
  ok   START each: both run  L2=1 TL1=1
T9 - power lost and back
  ok   PLC STOP: all outputs off (C02)  TL1=0 XV401=0 XV403=0
  ok   RUN again: scrubber tripped, burner off (S-01, B-02)  TL1=0 XV401=0 XV403=0
  ok   RESET: scrubber normal, burner still off  TL1=0 XV401=1 XV403=1
T10 - MAN: one cycle only
  ok   MAN + START: runs  TL1=1
  ok   70 degC: stops  TL1=0
  ok   60 degC: does NOT restart (MAN)  TL1=0
  ok   new START: runs  TL1=1
R01 - START refused while tank level is low
  ok   START with LSL low was refused: off (R-01)  TL1=0
R02 - AUTO/MAN changed while running
  ok   AUTO -> MAN while running: off (R-02)  TL1=0
  ok   back to AUTO: stays off, needs START  TL1=0
R09 - RUN on without our request for 30 s
  ok   RUN without request 30 s: FAULT, START refused (R-09)  TL1=0
  ok   RESET + START: runs  TL1=1
BR02 - BR02: lamps, diesel change, STOP, independent of BR01
  ok   BR02 START: L and lamp H5  H5=1 H6=0 L2=1 T2=0
  ok   BR02 RUN below 60: T2 and lamp H6  H5=1 H6=1 L2=1 T2=1
  ok   BR01 lockout: BR02 keeps running  L2=1 TL1=0
  ok   RESET for BR01: BR02 untouched (R-07)  L2=1 T2=1
  ok   fuel changed while running: BR02 off (R-12)  H5=0 L2=0
  ok   new START: BR02 runs  L2=1
  ok   S7 STOP: BR02 off  L2=0
PASS
```
