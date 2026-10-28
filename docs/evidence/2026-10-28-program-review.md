# 2026-10-28 — البرنامج اتبنى، واتراجع مراجعة مستقلة

## البناء

- `tools/build_blocks.py` بيولّد 11 بلوك لادر حسب `0006`: `Par` و`Sys` (DBs)، و`Common` و`Outputs`
  (FCs)، و`Scrubber` و`Burner` (FBs)، و`Scrubber_DB` و`BR01_DB` و`BR02_DB`، و`Startup` (OB100)
  و`Main` (OB1). كل network عنوانه رقم من الـ C&E أو من `التشغيل.md`.
- الاستيراد بـ `Apply-Blocks.ps1`. الكومبايل اتعمل بلوك بلوك: **`consistent 11/11` و`CLEAN. PROJECT SAVED.`**
- الـ export رجع، واتحوّل لنص في `export/code.txt` (`lad2text.py`).

### قواعد SimaticML اتعلمناها هنا (مش في الـ skill)

| القاعدة | رسالة TIA |
|---|---|
| المقارنة (`Eq`/`Ge`…) دخل القدرة بتاعها اسمه **`pre`**، مش `in` | `references a connection named 'in' … which does not exist` |
| `Sub` مالوش `Card` | `The node 'TemplateValue' with the name 'Card' … is invalid at the element 'Sub'` |
| MOVE على Bool مش مسموح في LAD | `Data type Bool is not permitted here` |
| تايمر جوه فرع توازي مش مسموح | `The network is not supported in this language version` |
| تايمر لازم قبله كونتاكت، مايتوصّلش بالـ rail على طول | `A preceding Boolean logic operation is missing` |

## المراجعة المستقلة

اتعملت بـ subagent على **Claude Opus**، fresh ومن غير أي سياق من اللي كتب الكود. اتديله
`export/code.txt` والمواصفات، وقراية بس.

- **النتيجة:** مفيش عيب بيولّع بيرنر فجأة، أو بيفوّت تريب، أو بيسيب صمامات الـ scrubber في وضع غلط.
  `HeatReq` دايمًا = STARTING أو RUNNING، و`Stage2` = RUNNING بس، وكل طريق وقوف بيشيل الطلب في
  نفس الـ scan.
- **مشى السيناريوهات العشرة و6ب على الورق، scan بـ scan:** كلهم PASS.
- **عيب اتصلّح:** `F40`، مهلة الثيرموكابل. اتصلّح، واتعمل import وكومبايل `11/11` تاني.
- **مقترحات اتسجّلت ومااتنفّذتش** لأنها مش في الـ C&E أو `التشغيل.md` (القاعدة 0002):
  `F41` و`F42` و`F43` و`F44` و`F45` و`F46`، والتفسيرات في `F47`.

**ده مش اختبار.** الاختبار على PLCSIM لسه: `docs/evidence/2026-10-28-plcsim-automation.md`.
