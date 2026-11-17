# Task 5 — finish TIA import, PLCSIM run, evidence (manager-style)

Worktree: `D:\tasks\burner\.claude\worktrees\manager-style` (branch `manager-style`). Read `AGENTS.md` and
`docs/TOOLS.md` (section "Codex وسكريبتات Openness": run Openness scripts with Windows PowerShell 5.1
`powershell`, never `pwsh`). Gas/flame project. You will NOT commit; the orchestrator reviews and commits.
You MAY run TIA Openness scripts and PLCSIM here. TIA Portal must not be open in the UI; every script refuses
if it is. If a script says TIA is running, wait (up to 2 min, check every 5 s) for the previous script's
`Siemens.Automation.Portal` process to exit — never kill TIA processes or delete lock files.

## State now
- PLC: the 8 manager-style blocks are imported into `tia\Burner\Burner.ap15_1`, the 5 old blocks removed,
  PLC compile 0 errors / 0 warnings, consistent, saved (logs `build\_apply_mgr.log`, `build\_remove_mgr.log`,
  `build\_compile_mgr.log`).
- HMI: `tools\Apply-Hmi.ps1` (imports `build\hmi\Tags_*.xml` + `Screen_*.xml`, then compiles HMI) failed and did
  NOT save. Log `build\_apply_hmi_mgr.log`:
  `Screens > Alarms > Text_E_STOP_RESET_Sys_Alm_EStop: Animation 'Visibility' has invalid parameters. The tag does not exist.`
  The `Alarms` screen is hand-made in TIA (it holds a manual Alarm View) and is NOT generated — do not import a
  generated Alarms screen over it. The HMI tag `Sys_Alm_EStop` no longer exists; its replacement is
  `Scrub_EStopOK` (1 = E-STOP released), and the generated screens show their E-STOP banner when it is 0
  (see `tools/build_hmi.py`, search `Scrub_EStopOK`).

## Do
1. Fix only that one object on the `Alarms` screen: its Visibility animation must use `Scrub_EStopOK` and be
   visible when the tag is 0 (same as the generated banner). Rename the object to
   `Text_E_STOP_Scrub_EStopOK` if the export/import path allows it. Suggested path: export the Alarms screen
   with Openness to XML (there may be an export script/function in `tools\Export-TiaProject.ps1`), patch that one
   animation, re-import that screen together with the generated files in one `Apply-Hmi.ps1` run (put the
   patched `Screen_Alarms.xml` in a separate build dir with copies of the generated files so the original
   `build\hmi` stays generator output). Keep the Alarm View and everything else on that screen unchanged; diff
   the exported XML before/after and keep the diff.
2. HMI compile must be 0 errors, saved. Then a full `tools\Compile-Project.ps1` (PLC + HMI), literal output.
3. `tools\Export-TiaProject.ps1` into `export\`, then confirm the exported PLC blocks match `build\blocks\`
   (same check style as `docs/evidence/2026-11-11-revb-export-roundtrip*` if present; otherwise compare network
   titles and rung counts per block) and list any difference.
4. PLCSIM: download the PLC to PLCSIM with `tools\Download-Plcsim.ps1` (read it first; if it needs PLCSIM
   started or a UI step it cannot do, stop and report exactly what is needed). Then run
   `py tools\plcsim\run_scenarios.py` (default set). `build\plcsim\PlcSimCtl.exe` is now present. Retained `Par`
   values must be SP=700, HYST=50, STG=100 — they are the DB start values after a fresh download; say how you
   ensured it. Set `PYTHONUNBUFFERED=1`. If a scenario fails, decide whether the scenario or the program is
   wrong by reading `docs/التشغيل.md`, `tools/tests/test_panel_rules.py` and the generator; you may fix the
   **scenario script only**, never the program, and report every failure and its cause either way.
5. Write `docs/evidence/2026-11-16-manager-style-tia.md` (Arabic, short, like other evidence files): literal
   compile reports, export check, PLCSIM output, what was not tested (24 h, 10 min, 120 s long runs; alarm bits
   via HMI). Update the manager-style entry in `docs/STATE.md`.

## Do not touch
`tools/build_*.py`, `tools/ladxml.py`, `tools/panel_text.py`, `tools/tests/`, `deliverables/`, other worktrees.

## Report contract
1. Every script you ran with its exit code. 2. HMI fix: object name, diff. 3. Compile reports (literal).
4. PLCSIM: PASS/FAIL line and every failing step with its cause. 5. Files changed.
