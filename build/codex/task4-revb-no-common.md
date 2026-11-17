# Task 4 — Rev B without `Common` and `Sys`

Worktree: `D:\tasks\burner\.claude\worktrees\simplify-revb` (branch `simplify-revb`). Read `AGENTS.md` first.
Gas/flame project. You will NOT commit; the orchestrator reviews, commits, imports into TIA and simulates.
You cannot run TIA Portal or PLCSIM.

## Goal
`tools/build_blocks.py` here generates "Rev B": 13 blocks, 78 networks, one rung per network. Remove the
`Common` FC (FC1) and the `Sys` global DB (DB2) — their markers (`Sys.EStopOK`, `Sys.ResetPulse`,
`Sys.ResetMem`, `Sys.FirstScan`, `Sys.Alm_EStop`) are read from inside other blocks and make the program hard
to follow. Keep everything else of Rev B's structure: `Par`, `HmiAlm`, `Scrubber`(+DB), `Burner`(+2 DBs),
`Outputs`, `HmiMap`, `Startup`, `Main`, **one rung per network**, same titles style `N('Title', 'English …')`.

A sibling worktree already did the same replacements in a different layout; read it for reference only (do
not copy its multi-rung layout): `D:\tasks\burner\.claude\worktrees\manager-style\tools\build_blocks.py`
(commit `255ed92`) and its decision `docs/decisions/0011-manager-style-program.md`.

## Replacements (exact)
1. **E-STOP read directly.** Every use of `"Sys".EStopOK` becomes the raw input:
   - `Scrubber` gets a new Input `EStopOK` (Bool, 1 = released), wired in `Main` to `"S0_EStopStatus"`;
     use `#EStopOK` inside it.
   - `Burner` gets a new Input `EStopOK`, wired in `Main` to `"S0_EStopStatus"`; its Trip uses `!#EStopOK`.
   - `Outputs` gates TL/TR/L/T2 with `"S0_EStopStatus"` instead of `"Sys".EStopOK`.
   - `HmiMap` alarm `Common.x0` reads `!"S0_EStopStatus"`; text `'E-STOP pressed'`, clears
     `'Release E-STOP; then RESET the scrubber and START the burners'`.
2. **RESET edge moves into `Scrubber`.** Its Input `Reset` becomes `ResetPB` (raw button, `Main` wires
   `"S2_FaultReset"`); new Static `ResetMem`, `ResetPulse`; first two networks:
   `ResetPB & !ResetMem → ResetPulse`, `ResetPB → ResetMem`; every former `#Reset` use reads `#ResetPulse`.
3. **First scan → `Startup` (OB100).** Remove every `"Sys".FirstScan` term. OB100's single network sets
   `"Scrubber_DB".Tripped`, `"Scrubber_DB".FlareTrip`, `"Scrubber_DB".ResetMem`, `"BR01_DB".StartMem`,
   `"BR02_DB".StartMem` (parallel S coils from the rail). `FuelMem` stays FALSE at power-up. Remove `Main`'s
   "First scan done" network.
4. **Setting limits move to `Main`** as its first six networks (same rungs as in `Common` now), before the calls.
   Remove `Main`'s `Common` call.
5. Delete `common_fc`, `sys_db`, `SYS`; drop `Sys.xml` and `Common.xml` from `BLOCKS` and delete those two files
   from `build/blocks/` when the generator runs (only those two).

Behaviour must stay Rev B except the consequence of reading E-STOP directly: the drain is held closed only while
E-STOP is pressed (after release it follows the level without RESET); the E-STOP alarm clears on release. The
scrubber trip and flare trip still latch until RESET with all causes healthy; burners still need a new START.
Keep rung order inside each block as today; `Scrubber`'s two new RESET networks go first.

## Also
- `tools/Remove-Blocks.ps1`: copy it from the manager-style worktree path above and allow only `Sys`, `Common`.
- `tools/build_hmi.py`: drop `Sys`; replace HMI tags `Sys_EStopOK` and `Sys_Alm_EStop` with one tag
  `Scrub_EStopOK` → `Scrubber_DB.EStopOK` (banner visible at 0, "E-STOP ready" lamps read it). Keep every other
  tag name. Regenerate `build/hmi/*`. Never generate the `Alarms` screen.
- `tools/build_alarms.py`: E-STOP row title/info for "pressed, clears on release". Keep IDs and trigger tags.
  Regenerate `build/hmi/Alarms_LCP01.xlsx`.
- `tools/tests/test_panel_rules.py`: update to the new blocks; keep every test that still applies; add: drain held
  only while E-STOP pressed, scrubber stays tripped after E-STOP release until RESET, OB100 effects (held START/
  RESET ignored), each `%Q` written once (in `Outputs`).
- Docs (Arabic, Egyptian, like the existing files): short `docs/decisions/0012-revb-without-common.md` (what
  moved where, what was rejected), add it to `docs/decisions/README.md`; update `docs/التشغيل.md` only where E-STOP
  /RESET/power-up/drain wording changed; a short entry in `docs/STATE.md` under "شغّال دلوقتي". Run
  `py tools\check_docs.py`; if it fails for reasons unrelated to your change, report it rather than rewriting
  the checker.

## Do not touch
`deliverables/`, `tia/`, `export/`, `tools/plcsim/`, anything under `build/` except what the generators write.

## Gates (paste literal output)
```
py tools\build_blocks.py
py tools\build_hmi.py
py tools\build_alarms.py
py tools\check_hmi_xml.py
py -m unittest discover -s tools\tests -v
py tools\check_docs.py
```

## Report contract
1. Files changed, one line each. 2. Network count per block, before and after. 3. Gate output (literal).
4. Anything you could not do or did differently, and why.
