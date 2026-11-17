# Task 2 — تقرير التسليم

تم التنفيذ والفحص المحلي، من غير تشغيل TIA أو commit.

## 1. الملفات

- `tools/build_hmi.py` — ربط التاجات وتعليقاتها بجداول Task 1، والبانر ولمبات الطوارئ، وحفظ الأسماء العامة.
- `tools/build_alarms.py` — عنوان وشرح E-STOP يوضحوا إنه بيختفي مع فك الزرار.
- `tools/check_docs.py` — مراعاة أدلة النسخة الأساسية وتوقيت checkout، وفحص Rev. B الحالية بدل أرشيف Rev. A.
- `tools/tests/test_hmi_rules.py` — 4 اختبارات لعقد الربط والأنواع والبانر ولمبات الطوارئ وثبات الإنذارات.
- `tools/tests/test_panel_rules.py` — تحديث العدد المتوقع من 58 إلى 57 بس؛ باقي الملف زي Task 1.
- `build/hmi/Tags_LCP01.xml` — إعادة توليد 57 تاج بالربط والتعليقات الحالية.
- `build/hmi/Screen_Root_screen.xml` — بانر E-STOP على الدخل الخام عند 0.
- `build/hmi/Screen_BR01.xml` — البانر ولمبة E-STOP ready مع تباعد اللمبات المناسب.
- `build/hmi/Screen_BR02.xml` — البانر ولمبة E-STOP ready مع تباعد اللمبات المناسب.
- `build/hmi/Screen_Scrubber.xml` — البانر ولمبة E-STOP على التاج الجديد.
- `build/hmi/Screen_Settings.xml` — بانر E-STOP على التاج الجديد.
- `build/hmi/Alarms_LCP01.xlsx` — إعادة التوليد؛ قيم C2 وN2 بس اتغيّروا، IDs وtrigger tags ثابتين.
- `docs/decisions/0011-manager-style-program.md` — سبب الترتيب والبدائل وتغييرا السلوك والنسخ الثلاث وحدود التحقق.
- `docs/decisions/README.md` — فهرسة 0011.
- `docs/التشغيل.md` — تحديث الطوارئ وترتيب البلوكات وكلمات الإنذارات والسيناريو المرتبط.
- `docs/STATE.md` — حالة manager-style واختصار الملف إلى 49 سطر من غير حذف التاريخ المحفوظ.
- `docs/evidence/2026-11-16-manager-style/state-before.md` — نسخة الحالة القديمة قبل الاختصار، من غير إعادة تفسيرها كمصدر أصلي.
- `docs/evidence/2026-11-16-manager-style/hmi-docs.md` — سجل التنفيذ والمقارنة وحدود الفحص والتغيير المتزامن.
- `docs/evidence/2026-11-16-manager-style/gates.txt` — المخرجات الحرفية للـgates الستة.
- `build/codex/task2-hmi-docs-report.md` — تقرير التسليم ده، بكل البنود المطلوبة.

## 2. التاجات

العدد: **58 → 57**. التوصيلات اللي اتغيّرت:

| التاج | قبل | بعد |
|---|---|---|
| `Alm_Common` | `HmiAlm.Common` | `Scrubber_DB.Alarms` |
| `Alm_BR01` | `HmiAlm.BR01` | `BR01_DB.Alarms` |
| `Alm_BR02` | `HmiAlm.BR02` | `BR02_DB.Alarms` |
| `Sys_EStopOK` و`Sys_Alm_EStop` | `Sys.EStopOK` و`Sys.Alm_EStop` | اتشالوا؛ بدالهم `Scrub_EStopOK` على `Scrubber_DB.EStopOK` |

التاج الجديد `1` = الطوارئ متفكوكة؛ البانر عند `0`، ولمبات E-STOP ready عند `1`. كل توصيل تاني ثابت مقارنة بالـXML السابق.

أسماء أعضاء البيرنر القديمة محفوظة كأسماء HMI للاتنين: `Tmax` → `ControlTemp`، و`Enabled` → `StartEnabled`، و`TOn` → `AutoRestartTemp`، و`TStg` → `SecondStageOnTemp`، و`TStgOff` → `SecondStageOffTemp`. دي توصيلات موجودة قبل المهمة، ومفيش عضو تاني ناقص احتاج تعويض. أسماء التاجات الكاملة بتبدأ بـ`BR01_` أو `BR02_` والاتصال على الـDB المناظر.

## 3. المخرجات الحرفية

الطرفية اتظبطت بـ`PYTHONIOENCODING=utf-8` لعرض العربي. الأوامر نفسها زي التكليف:

```text
> py tools\build_blocks.py
wrote 8 files to build\blocks
import order: -Files blocks\Par.xml,blocks\Burner.xml,blocks\Scrubber.xml,blocks\BR01_DB.xml,blocks\BR02_DB.xml,blocks\Scrubber_DB.xml,blocks\Startup.xml,blocks\Main.xml

> py tools\build_hmi.py
wrote 6 files to build\hmi (57 tags)

> py tools\build_alarms.py
 1 Common    x0 Fault   14 chars | E-STOP pressed | C01
 2 Common    x1 Fault   32 chars | Scrubber tripped: reset required | C02 / C03 / C05
 3 Common    x2 Fault   28 chars | Scrubber trip: high pressure | C03 / C06a
 4 Common    x3 Fault   30 chars | Scrubber trip: very high level | C05 / C06a
 5 Common    x4 Warning 29 chars | Scrubber high level (LSH-102) | C04
 6 Common    x5 Fault   33 chars | Scrubber drain time limit reached | C04a
 7 BR01      x0 Fault   19 chars | BR01 burner lockout | C07e
 8 BR01      x1 Fault   28 chars | BR01 temperature input fault | C07d
 9 BR01      x2 Warning 21 chars | BR01 RUN not received | C07f
10 BR01      x3 Fault   24 chars | BR01 RUN without request | C07g
11 BR01      x4 Warning 27 chars | TK01 level too low for BR01 | C07a
12 BR02      x0 Fault   19 chars | BR02 burner lockout | C08e
13 BR02      x1 Fault   28 chars | BR02 temperature input fault | C08d
14 BR02      x2 Warning 21 chars | BR02 RUN not received | C08f
15 BR02      x3 Fault   24 chars | BR02 RUN without request | C08g
16 BR02      x4 Warning 27 chars | TK02 level too low for BR02 | C08a
wrote build\hmi\Alarms_LCP01.xlsx (16 alarms)
11 Faults, 5 Warning; maximum alarm text: 33/40 chars

> py -m unittest discover -s tools\tests -v
test_alarm_ids_triggers_and_release_guidance (test_hmi_rules.HmiRules) ... ok
test_alarm_words_continuous_and_unsigned (test_hmi_rules.HmiRules) ... ok
test_all_screen_references_exist_and_estop_banner_uses_zero (test_hmi_rules.HmiRules) ... ok
test_public_tags_and_plc_types (test_hmi_rules.HmiRules) ... ok
test_auto_hysteresis_stops_at_sp_and_restarts_at_sp_minus_hyst (test_panel_rules.BurnerRules) ... ok
test_every_trip_needs_a_new_start (test_panel_rules.BurnerRules) ... ok
test_low_tank_level_waits_in_auto (test_panel_rules.BurnerRules) ... ok
test_man_runs_one_cycle (test_panel_rules.BurnerRules) ... ok
test_run_alarms_are_alarms_only (test_panel_rules.BurnerRules) ... ok
test_stage2_waits_for_run_and_its_timer_and_stops_at_62 (test_panel_rules.BurnerRules) ... ok
test_start_gives_heat_request_and_stop_removes_it (test_panel_rules.BurnerRules) ... ok
test_thermocouple_fault_after_10_s (test_panel_rules.BurnerRules) ... ok
test_settings_are_kept_inside_their_range (test_panel_rules.CommonRules) ... ok
test_alarm_words_are_continuous_and_ids_are_stable (test_panel_rules.HmiContracts) ... ok
test_bindings_and_object_names_are_complete (test_panel_rules.HmiContracts) ... ok
test_operator_lamps_distinguish_healthy_inputs_from_commands (test_panel_rules.HmiContracts) ... ok
test_v15_fields_do_not_create_duplicate_info_text_entries (test_panel_rules.HmiContracts) ... ok
test_br02_lamps_follow_final_l_and_t2 (test_panel_rules.ManagerRules) ... ok
test_br02_power_up_in_diesel_keeps_one_scan_fuel_change (test_panel_rules.ManagerRules) ... ok
test_daily_stop_reads_previous_request_and_reset_wins (test_panel_rules.ManagerRules) ... ok
test_drain_timeout_scan_delay_and_reset_priority (test_panel_rules.ManagerRules) ... ok
test_estop_drain_closes_only_while_pressed_and_trip_stays_after_release (test_panel_rules.ManagerRules) ... ok
test_reset_with_present_trip_cause_cannot_clear_or_queue_reset (test_panel_rules.ManagerRules) ... ok
test_run_without_request_is_alarm_only_and_clears (test_panel_rules.ManagerRules) ... ok
test_start_while_trip_present_is_not_queued (test_panel_rules.ManagerRules) ... ok
test_startup_and_stop_to_run_ignore_held_buttons (test_panel_rules.ManagerRules) ... ok
test_trip_removes_all_burner_requests_and_lamps_in_same_scan (test_panel_rules.ManagerRules) ... ok
test_drain_follows_the_level_without_delay (test_panel_rules.ScrubberRules) ... ok
test_drain_time_limit_closes_and_reset_reopens (test_panel_rules.ScrubberRules) ... ok
test_power_up_trips_until_reset (test_panel_rules.ScrubberRules) ... ok
test_pressure_trip_keeps_its_cause_until_reset (test_panel_rules.ScrubberRules) ... ok
test_very_high_level_trips_suction_not_flare_and_opens_drain (test_panel_rules.ScrubberRules) ... ok
test_alarm_table_ids_and_local_word_slices (test_panel_rules.XmlContracts) ... ok
test_block_set_counts_single_flgnet_and_one_shared_rail (test_panel_rules.XmlContracts) ... ok
test_every_physical_input_is_visible_on_main_calls (test_panel_rules.XmlContracts) ... ok
test_fb_instance_sections_types_and_defaults_match (test_panel_rules.XmlContracts) ... ok
test_panel_text_covers_current_blocks_and_topics (test_panel_rules.XmlContracts) ... ok
test_physical_outputs_written_once_only_by_main_call_pins (test_panel_rules.XmlContracts) ... ok

----------------------------------------------------------------------
Ran 38 tests in 5.353s

OK

> py tools\check_docs.py
OK — docs consistent

> py tools\check_hmi_xml.py
OK - 6 generated XML files checked against 10 reference files (27 object types)
OK - attributes, links, child compositions/types, alphabetical attributes; IDs unique per document

```

فحص إضافي: `git diff --check` انتهى بكود 0 ومن غير مخرجات. المقارنة أثبتت إن C2 وN2 بس اتغيّروا في قيم ملف الإنذارات، والأنواع والتنسيق والـIDs وباقي أجزاء XLSX ثابتة باستثناء core metadata. فحص حراس الوثائق أكد إن استثناء نفس الـcommit يقبل الملفات الثابتة ويرفض التعديلات المحلية، وإن ملفات build الحالية ما بترجعش للنسخة الأساسية.

## 4. الاختلافات وحدود التنفيذ

- أضفت لمبة E-STOP ready على البيرنرين حسب الطلب؛ النسخة السابقة كان فيها اللمبة على السكرابر بس. صفحة Alarms ما اتولّدتش.
- فحص الوثائق كان بيفشل قبل الشغل: 93 سطر حالة، ومراجع أدلة مش متنسخة للـworktree، وتوقيت checkout جعل C&E أقدم من المولّد بثانية. الحالة القديمة اتحفظت كاملة، واتصلح الفحص من غير تغيير deliverables أو الأدلة القديمة. Rev. A تفضل أرشيف ثابت، وRev. B هي ناتج المولّد الحالي.
- لم أغيّر build_blocks.py أو ladxml.py أو panel_text.py؛ تشغيل مولّد PLC المطلوب ما نتجش عنه فرق في الملفات المتتبعة. deliverables وtia وexport ما اتلمسوش.
- ظهر تعديل متزامن في tools/plcsim/run_scenarios.py مش من Task 2؛ اتساب من غير لمس. build/_apply_mgr.log وملفات التكليف الموجودة أصلًا في build/codex مش من تسليم المهمة.
- مفيش TIA import أو compile أو PLCSIM أو hardware أو commit من عندي. المعاينة المؤقتة لنص Excel مش إثبات لعرض العربي في TIA؛ ملف الاستيراد فضل على التنسيق الأصلي. المنسّق يراجع ويعمل الاستيراد والكومبايل والمحاكاة.
