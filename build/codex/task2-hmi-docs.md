# Task 2 — HMI generator, alarm file and docs for the "manager style" program

Worktree: `D:\tasks\burner\.claude\worktrees\manager-style` (branch `manager-style`). Read `AGENTS.md` first.
Gas/flame project. You will NOT commit; the orchestrator reviews and commits. You cannot run TIA Portal.

## Context
Task 1 (already done, see `build/codex/task1-plc.md` and the current `tools/build_blocks.py`) rewrote the PLC
generator: only `Par`, `Burner`+`BR01_DB`/`BR02_DB`, `Scrubber`+`Scrubber_DB`, `Startup`, `Main` remain.
`Sys`, `HmiAlm`, `Common`, `Outputs`, `HmiMap` are gone. Alarm words now live in the instance DBs:
`"Scrubber_DB".Alarms`, `"BR01_DB".Alarms`, `"BR02_DB".Alarms` (Word). E-STOP is read directly
(`Scrubber` input `EStopOK`, stored as `"Scrubber_DB".EStopOK`); there is no latch and no `Sys` DB.
`HMI_ALARMS` keeps its tuple shape and words `Common`/`BR01`/`BR02`.

## What to change
1. `tools/build_hmi.py`
   - Build `MEMBERS` / `TAGS` / comments from the new `build_blocks.py` tables only (no `Sys`, no `HmiAlm`).
   - **Keep the HMI tag names** the screens and the alarm file already use, and only change what they connect
     to: `Alm_Common` → `Scrubber_DB.Alarms`, `Alm_BR01` → `BR01_DB.Alarms`, `Alm_BR02` → `BR02_DB.Alarms`.
   - Replace `Sys_EStopOK` and `Sys_Alm_EStop` with one tag `Scrub_EStopOK` → `Scrubber_DB.EStopOK`
     (1 = E-STOP released). The E-STOP banner is visible when it is 0; the burner screens' "E-STOP ready" lamp
     reads it. Keep any other tag the screens use; if a burner member was removed or renamed in Task 1, map it
     and say so in your report.
   - Do not generate the `Alarms` screen (unchanged rule: it holds a hand-made Alarm View).
   - Run `tools/check_hmi_xml.py` (or whatever HMI check exists in `tools/`) and make it pass.
2. `tools/build_alarms.py`: only what the new table needs — the E-STOP row text/info now says the alarm
   clears when E-STOP is released (then RESET for the scrubber and START for the burners). Keep IDs 1–16 and
   the trigger tag names. Regenerate `build/hmi/Alarms_LCP01.xlsx`.
3. Docs (Arabic, Egyptian, plain; tags and terms stay English in backticks; follow the style of the existing
   files; read `docs/decisions/README.md` for the decision format):
   - New `docs/decisions/0011-manager-style-program.md`: why (the manager's crane project layout: every
     I/O visible on the `Main` calls, several rungs per network), what was rejected (Rev B's 13 blocks; a
     fourth variant), the two behaviour changes from Task 1, and that the three programs live side by side:
     135-network original in `D:\tasks\burner` (branch `codex/readability-english`), Rev B 78-network in
     worktree `simplify-revb`, this one in worktree `manager-style`. Add it to `docs/decisions/README.md`.
   - `docs/التشغيل.md`: update only what changed — E-STOP (drain held closed only while pressed; E-STOP
     alarm clears on release), the block layout if the file describes it, and the alarm list text for E-STOP.
   - `docs/STATE.md`: a short entry under "شغّال دلوقتي" for `manager-style`: generator done, not yet
     imported/compiled/simulated in TIA (the orchestrator does that).
   - Run `py tools\check_docs.py` and make it pass.

## Do not touch
`tools/build_blocks.py`, `tools/ladxml.py`, `tools/panel_text.py` (Task 1 owns them; if something there blocks
you, stop and report it), `tools/plcsim/`, `deliverables/`, `tia/`, `export/`.

## Gates (paste literal output)
```
py tools\build_blocks.py
py tools\build_hmi.py
py tools\build_alarms.py
py -m unittest discover -s tools\tests -v
py tools\check_docs.py
```
plus the HMI XML check you found.

## Report contract
1. Files changed, one line each. 2. HMI tag count before/after and every tag whose PLC connection changed.
3. Gate output (literal). 4. Anything you could not do or did differently, and why.
