# 2026-11-01 — مراجعة Codex Astra لخطة الشاشة (0007 Rev A)

**مين:** Codex `gpt-6-astra`، effort xhigh، read-only. البريف في آخر الملف. الرد بالنص تحت (إنجليزي).
**النتيجة:** 19 ملاحظة، و"needs rework". اتراجعوا على الكود (`F_EStop` لكل بيرنر، و`_Act`، ومفيش feedback للصمامات: صح)، واتاخدوا كلهم في Rev B.

---

Read-only review of [plan 0007](D:/tasks/burner/docs/decisions/0007-hmi-plan.md). No files were changed, and no TIA, Openness scripts or git commands were run.

1. **High — §1 D6, §3, P2/P6: F45 is acknowledged but not carried into implementation.**  
   D6 mentions raising `SP`, but F45 also covers reducing `HYST`. For example, an enabled AUTO burner waiting at 68°C can restart when `SP` changes from 70°C to 80°C. P2 lists no corresponding parameter-policy work, while P6 says nothing on the HMI should start or stop anything—an impossible criterion when permitted parameter changes affect heating. **Fix:** decide both F45 cases before P2, specify exactly when each parameter change takes effect, and test the chosen behavior. Express the boundary as “no process-command writes outside the four parameters.”

2. **High — §2 Settings and burner screens: validated values are confused with active values.**  
   `Par.*_V` means validated, but each burner uses its own `SP_Act`, `HYST_Act`, `STG_Act` and `TStart_Act`. During deferred application, `_V` can differ from the value controlling that burner. Both burners also share the same four settings. **Fix:** label the shared requested/validated settings clearly; show each burner’s active values and pending changes. Display thresholds from `TOn`, `TStg` and `TStgOff`, including the omitted second-stage return threshold, `SP_Act − STG_Act + 2°C`. See [parameter application](D:/tasks/burner/tools/build_blocks.py:504).

3. **High — §2 Scrubber/Overview: commands are presented as physical feedback.**  
   The available valve interface provides commands, not valve-position confirmation. Likewise, `Stage2` is a stage request; it does not prove high fire. **Fix:** use “commanded open/closed” for valves and “stage request” for burners. Keep `RUN` feedback distinct, and show an OFF/no-request state rather than forcing every burner into “1st/2nd.”

4. **High — §2 Settings, P6: the parameter write and retention contract is incomplete.**  
   Both entry values and `_V` values are retained in [Par](D:/tasks/burner/tools/build_blocks.py:310). The plan does not specify startup ownership, HMI reconnection behavior, or protection against stale/default HMI values overwriting retained settings. **Fix:** whitelist the four entry destinations; make `_V`, active values and status fields output-only. Specify PLC-owned validation and startup recovery, then test valid retention, invalid retained values, panel restart, PLC restart and reconnection. HMI field limits must not be the only validation.

5. **High — §1 D3, §2, P4/P6: the “four writes only” boundary needs an auditable exit criterion.**  
   No explicit START/STOP/RESET control is proposed, which is correct. However, screen fields alone do not account for function-key events, screen events, alarm functions or other configured writes. **Fix:** review all write-capable events against the four-tag whitelist. Apply authorization to each editable field, including after logout/session expiry, rather than relying only on protected navigation. Keep `HmiMap` writes confined to display data.

6. **Medium — §1 D5, §3.1: first-out behavior is underspecified and misses startup.**  
   The scrubber also trips on startup, when PSH, LSHH and E-STOP may all be healthy. The proposed three causes therefore still allow “TRIP” with no explanation. “Latched causes” and “first cause” also require different rules. **Fix:** define startup/reset-required indication, simultaneous-cause priority, subsequent-cause recording, reset eligibility and power-cycle behavior. If startup capture is placed in `HmiMap`, account for `Main` currently clearing `FirstScan` before the proposed end-of-cycle call.

7. **Medium — §4: alarm coverage and provenance need correction.**  
   The existing C&E rows marked for HMI alarming are represented. However, `BR01_DB.F_EStop` and `BR02_DB.F_EStop` are omitted; the common `Sys.Alm_EStop` does not fully represent their independently latched fault states. Conversely, `C07a/C08a` currently have no E8 alarm action, so the proposed low-level warnings are additions. **Fix:** include the burner E-STOP causes in fault indication, and record the low-level warning additions through decision 0002 with explicit provenance. Give every alarm a complete symbolic source, polarity, ID and clearing rule.

8. **Medium — §3.2/§4: one alarm word is insufficient; exact V15.1 trigger typing remains UNVERIFIED.**  
   The table expands to **17 bits** before adding the two burner E-STOP flags. Siemens’ later documentation distinguishes PLC `Word/Int` from HMI `UInt/Int`; that supports the approach but does not confirm V15.1. **Fix:** allocate at least two words, publish the bit mapping, and demonstrate every bit independently in P1/P6. Record the actual accepted PLC and HMI types. [Siemens discrete-alarm documentation, V20](https://docs.tia.siemens.cloud/r/en-us/v20/working-with-alarms-basic-panels-panels-comfort-panels-rt-advanced-rt-professional/working-with-alarms-basic-panels-panels-comfort-panels-rt-advanced-rt-professional/configuring-alarms-basic-panels-panels-comfort-panels-rt-advanced-rt-professional/configure-alarms-basic-panels-panels-comfort-panels-rt-advanced/configuring-discrete-alarms-basic-panels-panels-comfort-panels-rt-advanced?contentId=2QJt6TWUWlM4GutyTtzY5A).

9. **Medium — §1 D4/§4: alarm lifecycle descriptions conflict.**  
   D4 suggests every alarm remains until physical RESET, but LSH and the proposed low-level warnings clear automatically. `Sys.Alm_EStop` also remains active after S0 is released until RESET, making “E-STOP pressed” misleading during that interval. **Fix:** distinguish live conditions from latched trips in the text and clearing rules. Explicitly configure classes without acknowledgement and remove acknowledgement controls. Define whether “history” means the panel’s bounded alarm buffer, including persistence and timestamps.

10. **Medium — §2 and P0: important operating states and F47 are missing.**  
    `IDLE` cannot distinguish “START permission absent” from “enabled and waiting for temperature.” The screens also omit BR01’s planned 24-hour pause and thermocouple startup inhibition. F47’s unresolved mode/fuel/START semantics are absent from P0. **Fix:** show `Enabled`, relevant waiting/inhibit reasons and `Pause24`; reconcile F47 with the numbered operating rules before freezing acceptance tests. These are indications, not new controls.

11. **High — P1/P3–P5/P7: the Openness strategy exceeds confirmed V15.1 support.**  
    Siemens confirms screen, HMI tag-table and text-list import. It explicitly excludes alarm views/windows/indicators from screen import/export, and integrated connections cannot be exported; connection support is for non-integrated connections. **Alarm-definition import, user/group import and the proposed XLSX fallback remain UNVERIFIED.**  
    **Fix:** plan manual creation of the integrated connection and alarm controls, preserve them during later imports, and verify the remaining routes in P1. Do not make automated import of unsupported objects an exit requirement. [V15.1 Openness manual, §§4.4 and 8.3](https://cache.industry.siemens.com/dl/files/163/109477163/att_926042/v1/TIAPortalOpennessenUS_en-US.pdf).

12. **Medium — §2 temperature scaling: device capability is confirmed, but this conversion path is UNVERIFIED.**  
    Siemens lists input/output linear scaling for second-generation Basic panels. That does not prove the proposed V15.1 tag configuration preserves tenths correctly. **Fix:** verify `701 ↔ 70.1°C`, negative temperatures, parameter boundaries and rounding, using exactly one scaling mechanism. Show invalid thermocouple readings as invalid—not ordinary temperatures such as 3276.7°C—and invalidate `Tmax` when either required channel is invalid. [Basic Panels manual, §8.9](https://cache.industry.siemens.com/dl/files/350/90114350/att_904652/v2/HWBasicPanels2GenUS_en-US.pdf).

13. **Medium — §2 `TStart`: TIME I/O-field handling on the selected Basic/V15.1 combination is UNVERIFIED.**  
    Adding an integer-seconds copy could introduce competing retained values or bypass R-11. **Fix:** first prove native display/edit behavior. If an adapter is needed, make it the single HMI entry path for that parameter, validate 90–300 seconds, and convert using sufficiently wide arithmetic before multiplying by 1000. Document readback, rejection, retention and application timing; do not leave both representations independently writable.

14. **Medium — §1 D1, P1/P3, §6: product identity is confirmed; the exact `CreateWithItem` identifier is UNVERIFIED.**  
    `6AV2123-2DB03-0AX0` is a KTP400 Basic with 480×272 resolution and four function keys. The bare order number is not proof of the complete API identifier, which can require version/orientation information. **Fix:** confirm the installed panel and image version, then record the catalog-derived identifier and successful creation result. Treat Basic-to-Comfort conversion as requiring revalidation. [Siemens 2019 catalog](https://cache.industry.siemens.com/dl/files/146/109744146/att_1013417/v1/simatic-st80-stpc-complete-english-2019.pdf).

15. **Medium — P1/P6, §6: simulation is supported, but local integration remains UNVERIFIED.**  
    Siemens documents local Basic-panel simulation with WinCC V15.1 and PLCSIM V15.1. Therefore the general capability is confirmed; this project’s installed runtime, interface selection and symbolic communication are not. **Fix:** make P1 demonstrate a live read, one validated parameter write and one alarm through the intended connection. Record the versions and interface configuration. [Siemens simulation example, §3](https://cache.industry.siemens.com/dl/files/099/109748099/att_998491/v1/109748099_Simulation_of_WinCCTIA_Protal_and_PLCs_en.pdf).

16. **High — P2/P6: the existing 17 tests are insufficient acceptance evidence.**  
    Their [recorded limitations](D:/tasks/burner/docs/evidence/2026-10-28-plcsim-scenarios-pass.md) explicitly exclude direct fault-bit verification, R-11, HMI alarms and the 24-hour stop. Rejecting one out-of-range entry does not complete R-11. **Fix:** retain those regressions and add direct checks of alarm bits/texts, simultaneous faults, first-out, all four parameter boundaries, immediate/deferred application, F45, retention and both burner instances. If HMI input limits intercept invalid entries, separately inject invalid requests in PLCSIM to prove PLC rejection.

17. **High — P1–P7: backup, baseline and final verification gates are incomplete.**  
    A disposable probe copy is sensible, but the plan requires no full backup before modifying the original, no normalized baseline comparison, and no preservation of existing parameter values. Calling every change “additive” does not remove these needs. P7 also changes the UI after testing without an exit criterion. **Fix:** require a recoverable full-project backup, baseline exports, reviewed diffs, literal compile reports and final runtime verification after P7. Preserve the complete project because XML exports omit some HMI content. Clarify that TIA must be closed for script writes; manual editing necessarily uses TIA.

18. **Low — context, §2/§4b: navigation and drawing references need cleanup.**  
    No route to Settings or login/logout is listed. Also, drawing sheet 10 is PLC DI, not an Ethernet-switch layout; sheet 9 identifies the switch supply and contains cross-references that do not establish the complete network arrangement. **Fix:** add explicit Settings/login navigation and verify readability at 480×272. Correct the drawing citation and distinguish the proposed network/IP arrangement from drawing-confirmed facts.

19. **Low — §3.3/P4: keep automation and fault summarization bounded.**  
    A single `FaultCode` adds priority logic and can conceal simultaneous faults; an FC-local temporary value would also be unsuitable as the persistent HMI interface. Full XML generation for six screens may create more maintenance than it saves where manual controls are unavoidable. **Fix:** retain the complete alarm list, define any summary’s priority and persistent DB destination, and use a small proven template workflow. Defer the seconds adapter until necessary; consider latched causes without first-out chronology if that meets the agreed diagnostic need.

**Verdict: needs rework before execution.** The basic scope respects decision 0001 and proposes no direct process controls beyond parameter editing. The principal blockers are parameter semantics and truthful active-value display, incomplete diagnostic definitions, known V15.1 Openness limitations, and insufficient acceptance/backup gates. A revised plan should resolve those points before PLC or production-project changes begin.

---

## البريف

```
You are reviewing a PLAN (not code) for the HMI of control panel LCP-01 (S7-1200 CPU 1214C, KTP400, TIA Portal V15.1, Openness). Gas burners: treat as safety-related.

Read first (read-only): AGENTS.md, docs/decisions/0007-hmi-plan.md (THE PLAN), docs/التشغيل.md (esp. §5 HMI, R-11, §6 scenarios), docs/ISSUES.md (F44, F45, F47, F48), docs/decisions/0001, 0002, 0006, tools/build_blocks.py (Par, Sys, Burner and Scrubber interfaces), deliverables/PH-LCP-01-CE_RevA.xlsx if useful, inputs/drawings/Burner_V1.pdf (sheets 9, 10, 14).

Review the plan for:
1. Correctness against the sources: does any screen field, alarm, or PLC change contradict the drawing, the C&E, التشغيل.md, or decision 0001/0002? Any signal missing from the alarm table or screens?
2. Safety: can anything on the HMI start, stop, reset or otherwise command the process beyond the four parameters? Any risk in the parameter path (R-11, F45, retain, scaling)?
3. TIA V15.1 / WinCC Basic / Openness feasibility: which claims are wrong or unverified (discrete alarm trigger tag types, linear scaling on HMI tags, Time-type IO fields on Basic panels, importing screens/tags/connections/alarms/text lists/users via Openness V15.1, CreateWithItem order-number string for KTP400 Basic PN, WinCC RT simulator with PLCSIM V15.1). Mark each UNVERIFIED unless you can confirm from a primary source.
4. Phase order and exit criteria: anything missing (backups/baseline, regression, evidence)?
5. Anything over-engineered or that should be cut.

Rules: read-only. Do not edit any file, do not run TIA or Openness scripts, no git.
Output: a numbered findings list, each with severity (high/medium/low), the plan section it concerns, the problem, and a concrete fix. Then a one-paragraph verdict: ready to execute after fixes, or needs rework. Write in English.
```
