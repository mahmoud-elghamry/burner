# Task 1 — PLC program in the "manager style" (generator only)

You are working in a git worktree of a Siemens S7-1200 project (TIA Portal V15.1):
`D:\tasks\burner\.claude\worktrees\manager-style` (branch `manager-style`).
Read `AGENTS.md` first (project rules). This is gas/flame control: behaviour must not change except where
this brief says so. You will NOT commit; the orchestrator reviews and commits. You cannot run TIA Portal
or PLCSIM; the orchestrator imports, compiles and simulates afterwards.

## Goal

Today `tools/build_blocks.py` generates "Rev B": 13 blocks, 78 networks, one rung per network, outputs
written in a separate `Outputs` FC, alarms in `HmiMap`/`HmiAlm`, E-STOP/RESET/first-scan in `Common`/`Sys`.
Rewrite it so the program reads like the company manager's crane project:

- `Main` (OB1) shows **every physical input and output on the block calls**. Open `Main` and you see:
  sensor X goes into block Y, block Y drives relay Z.
- **Several rungs per network, one topic per network** (e.g. "Buttons", "Temperature", "Trip").
- Only these blocks remain: `Par` (DB1), `Burner` (FB1), `Scrubber` (FB2), `BR01_DB` (DB3),
  `BR02_DB` (DB4), `Scrubber_DB` (DB5), `Startup` (OB100), `Main` (OB1).
  **Removed:** `Sys` (DB2), `HmiAlm` (DB6), `Common` (FC1), `Outputs` (FC2), `HmiMap` (FC3).
- About 19 networks total instead of 78.

The behaviour is Rev B's (`docs/التشغيل.md`, `deliverables/PH-LCP-01-CE_RevB.xlsx`) with exactly the
changes listed under "Behaviour changes". **Inside every network keep the rungs in the same order as Rev B**
(scan order matters for set/reset and edge logic).

## Generator infrastructure (in `tools/build_blocks.py`, and `tools/ladxml.py` only if unavoidable)

1. **Multi-rung network.** Add `network(title, rungs)` where `rungs` is a list of `(expr, *outs)`
   (same expression/output mini-language as today's `rung()`). All rungs go into ONE `<FlgNet>`; each rung's
   first element connects to the power rail. In SimaticML the power rail is a single `<Wire>` that starts
   with `<Powerrail />` and has one `<NameCon>` per rung start (and per parallel branch start). See
   `ladxml.Net.rail()` / `wire()` build wires today and make every rung hang off the same Powerrail wire —
   do not emit several `<Powerrail />` wires in one network unless you find evidence in the repo that TIA
   V15.1 accepts that. Look in `export/xml/` and in the user's other projects referenced in docs for a real
   exported multi-rung network; record what you based the choice on in your report.
   Add a module constant `MULTI_RUNG = True`. With `False`, `network()` must emit one network per rung,
   titled `"<title> (1/n)"`, `"(2/n)"` … with the same explanation — this is the fallback if TIA rejects
   multi-rung networks, so it must produce importable XML with no other change.
2. **Block calls with outputs.** Extend `call()` so params can be `Output` too: the call's output pin is wired
   to an operand (`"XV_401_Cmd"`, `"BR01_TL_Cmd"` …). Inputs may be constants: `TRUE`, `FALSE`, and global DB
   members like `"Par".SP` / `"Scrubber_DB".Tripped`. Output pins not listed stay unwired.
3. **Word bit on a local member:** support the operand `#Alarms.%X0` … `#Alarms.%X15` (slice on a local
   Word), like the existing global form `"HmiAlm".Common.%X0`.
4. `panel_text.py` (`P.BLOCK_COMMENTS`, `P.NETWORK_TEXT`, `P.SYMBOL_RENAMES`) must stay consistent:
   remove entries for deleted blocks, keep/adjust the rest. Every network title uses `N('Title', 'English
   explanation citing the C&E row')`.

## The blocks (exact interfaces — Task 2 (HMI) depends on these names)

### Scrubber (FB2), instance `Scrubber_DB` (DB5)
- Input: `PSH`, `LSH`, `LSHH` (Bool, 1 = healthy, as today), `EStopOK` (Bool, wired to `"S0_EStopStatus"`,
  1 = E-STOP released), `ResetPB` (Bool, wired to raw button `"S2_FaultReset"`).
- Output: `FlareCmd`, `DrainCmd`, `SuctionCmd`, `Tripped` (Bool), `Alarms` (Word).
- Static: `FlareTrip`, `ResetMem`, `ResetPulse`, `Cause_PSH`, `Cause_LSHH`, `F_DrainTO` (Bool),
  `T_DrnMax` (TON_TIME, multi-instance as today).
- Networks:
  1. **RESET** — `ResetPulse = ResetPB & !ResetMem`; `ResetMem = ResetPB`; then
     `ResetPulse & PSH & LSHH & EStopOK` → R `Tripped`, R `FlareTrip`, R `Cause_PSH`, R `Cause_LSHH`.
  2. **Trip** — S `Tripped` on `!PSH | !LSHH | !EStopOK`; S `FlareTrip` on `!PSH | !EStopOK`;
     S `Cause_PSH` on `!PSH`; S `Cause_LSHH` on `!LSHH`.
  3. **Valves** — `FlareCmd = !FlareTrip`; `SuctionCmd = !Tripped`;
     `DrainCmd = (!LSH | !LSHH) & EStopOK & !F_DrainTO`.
  4. **Drain time limit** — `DrainCmd & TON(T_DrnMax, T#10M)` → S `F_DrainTO`; `ResetPulse` → R `F_DrainTO`.
  5. **Alarms** — `Alarms.%X0 = !EStopOK` (E-STOP pressed), `%X1 = Tripped`, `%X2 = Cause_PSH`,
     `%X3 = Cause_LSHH`, `%X4 = !LSH`, `%X5 = F_DrainTO`.

### Burner (FB1), instances `BR01_DB` (DB3) and `BR02_DB` (DB4)
- Input: `Auto`, `StartPB`, `StopOK`, `LevelOK`, `RunFb`, `Lockout`, `Fuel` (Bool), `TeA`, `TeB` (Int),
  `EStopOK` (Bool), `ScrubTrip` (Bool), `SP`, `HYST`, `STG` (Int, 0.1 degC), `Use24h` (Bool).
- Output: `HeatReq`, `Stage2`, `HeatLamp`, `Stage2Lamp` (Bool), `Alarms` (Word).
- Static: today's `BR_STAT` minus `Use24h` (now an input), same timers `BR_TON`.
- Networks (rungs = today's Rev B rungs, same order, regrouped):
  1. **Buttons** — StartEdge (drop the `"Sys".FirstScan` term; see Startup), StartMem, FuelChg, FuelMem.
  2. **Temperature** — TcOkA, TcOkB, TcOk, TcBad, ControlTemp=A, ControlTemp=B, SUB restart / stage-2-on
     (now from `#SP`, `#HYST`, `#STG`), ADD stage-2-off.
  3. **Heat demand** — Demand S, Demand R (uses `#SP`), HeatNeed (uses `#SP`).
  4. **Trip** — `Trip = !EStopOK | ScrubTrip | Lockout | TcBad | FuelChg`.
  5. **START / STOP** — START accepted (S StartEnabled), STOP or trip (R StartEnabled).
  6. **Daily stop** — 24 h set (uses input `#Use24h`), 60 s reset.
  7. **Heat request** — `HeatReq` and, as a parallel coil on the same rung, `HeatLamp`; then the MAN
     one-cycle rung (R StartEnabled).
  8. **Stage 2** — Stage 2 ON (S), Stage 2 OFF (R), then `Stage2Lamp = Stage2`.
  9. **Alarms** — NoRun, RunWrong, then `Alarms.%X0 = Lockout`, `%X1 = TcBad`, `%X2 = NoRun`,
     `%X3 = RunWrong`, `%X4 = !LevelOK`.

### The alarm table `HMI_ALARMS`
Keep `HMI_ALARMS` in `build_blocks.py` with the **same tuple shape** `(word, bit, operand, text, clears, source)`
and the same words `'Common'`, `'BR01'`, `'BR02'` (Task 2 and `build_alarms.py` read it). `'Common'` now means
the Scrubber's `Alarms` word; `'BR01'`/`'BR02'` the burner's `Alarms` word in that instance. The operand becomes
the FB-local signal (`'#Tripped'`, `'!#LSH'`, `'#Lockout'`, `'!#LevelOK'` …) and the two "Alarms" networks above
are generated from this table, so table and code cannot drift. Bits and order stay exactly as today.
Change only the E-STOP row: text `'E-STOP pressed'`, clears `'Release E-STOP; then RESET the scrubber and START the burners'`.

### Par (DB1)
Unchanged: `SP`, `HYST`, `STG`, retain, same start values.

### Startup (OB100)
One network "Power-up", rail → S coils on `"Scrubber_DB".Tripped`, `"Scrubber_DB".FlareTrip`,
`"Scrubber_DB".ResetMem`, `"BR01_DB".StartMem`, `"BR02_DB".StartMem`. Effect = Rev B's FirstScan:
scrubber tripped until RESET, a RESET or START held during power-up is not taken as a new press.

### Main (OB1) — 4 networks
1. **Settings limits** — the six clamp rungs now in `Common` (`"Par".SP/HYST/STG` below min → min,
   above max → max, limits from `PARAMS`).
2. **Scrubber** call: `PSH:="PSH_101"`, `LSH:="LSH_102"`, `LSHH:="LSHH_103"`, `EStopOK:="S0_EStopStatus"`,
   `ResetPB:="S2_FaultReset"`; `FlareCmd=>"XV_401_Cmd"`, `DrainCmd=>"XV_402_Cmd"`, `SuctionCmd=>"XV_403_Cmd"`.
3. **BR01** call (`BR01_DB`): today's BR01 inputs + `EStopOK:="S0_EStopStatus"`,
   `ScrubTrip:="Scrubber_DB".Tripped`, `SP:="Par".SP`, `HYST:="Par".HYST`, `STG:="Par".STG`, `Use24h:=TRUE`,
   `Fuel:=FALSE`; `HeatReq=>"BR01_TL_Cmd"`, `Stage2=>"BR01_TR_Cmd"` (BR01 lamps are wired to its relays).
4. **BR02** call (`BR02_DB`): same with BR02 tags, `Fuel:="Rfuel2_BR02_DieselMode"`, `Use24h:=FALSE`;
   `HeatReq=>"BR02_L_Cmd"`, `Stage2=>"BR02_T2_Cmd"`, `HeatLamp=>"BR02_Stage1Lamp_Cmd"`,
   `Stage2Lamp=>"BR02_Stage2Lamp_Cmd"`.
No "first scan done" network (no FirstScan flag any more). Each `%Q` tag must be written exactly once in
the whole program, and only by a call output in `Main`.

## Clarifications from the plan review (binding)
- Power rail: `ladxml.Net.render()` already groups identical sources into one wire. Build each multi-rung
  network as ONE `Net` and start every rung from `net.rail()`; never emit several Powerrail wires.
- Call outputs are wired **call-pin source → operand sink** (today's helper only wires inputs, operand → pin).
- `FuelMem` must stay FALSE at power-up (non-retain default, not set in OB100): BR02 powering up in diesel
  still gives a one-scan `FuelChg` exactly like Rev B. Do not add first-scan suppression for it.
- FB interface and its instance DBs must have matching sections; moving `Tripped` to Output and `Use24h`
  to Input keeps them non-retain with the same defaults (`Use24h` now comes from the `Main` pin).
- Preserve every Rev B priority: where Rev B's SET rung comes before its RESET rung, RESET wins; where the
  trip SET comes after the RESET, the trip wins (scrubber); the drain-limit RESET comes after its SET.
  Preserve the one-scan delay of the drain time limit and the daily-stop timer reading the previous scan's
  `HeatReq`. Do not "fix" these.
- Tests must also cover: BR02 powering up in diesel, PLC STOP→RUN (OB100 again), RESET pressed while a trip
  cause is still present, START pressed while a trip is present, drain time limit then RESET.

## Behaviour changes (the only ones allowed)
- E-STOP is read directly from `S0_EStopStatus` (no `EStopOK` latch). Scrubber trip/flare trip still latch
  until RESET (S2) with all causes healthy; burners still need a new START. **The drain is held closed only
  while E-STOP is pressed**; after release it follows the level again without RESET. The E-STOP alarm clears
  on release.
- TL/TR/L/T2 are no longer AND-ed with the E-STOP latch in an Outputs block: `Trip` already cancels
  `StartEnabled` in the same scan, before `HeatReq`/`Stage2` are computed. Confirm this ordering in your
  tests.

## Also deliver
- `tools/Remove-Blocks.ps1`: modelled on `tools/Apply-Blocks.ps1` (same project discovery, same refusal when
  TIA is open, same logging style). `-Names Sys,HmiAlm,Common,Outputs,HmiMap` deletes those blocks from
  `PLC_1` and saves. Do not run it.
- Update `tools/tests/test_panel_rules.py` to the new structure (flatten multi-rung networks in order) and
  keep every existing behaviour test that still applies; add tests for: E-STOP drain held only while pressed,
  E-STOP release without RESET leaves scrubber tripped, Startup effects (scrubber tripped, held START/RESET
  ignored), every `%Q` written exactly once and only from `Main`, the BR02 lamps follow L/T2, and the generated
  XML is well-formed with one `<FlgNet>` per network. Test both `MULTI_RUNG = True` and `False`.
- Print the import order like today (DBs/FBs before instances, OBs last).

## Do not touch
`tools/build_hmi.py`, `tools/build_alarms.py`, `tools/build_ce.py`, `deliverables/`, `tia/`, `export/`,
`docs/` (Task 2 does HMI and docs), `tools/plcsim/`.

## Gates (run them, paste the literal output in your report)
```
py tools\build_blocks.py
py -m unittest discover -s tools\tests -v
```
(`py`, not `python`.) `tools/build_hmi.py` will break because it imports names you remove; that is expected
and fixed in Task 2 — do not fix it here, just list what it imports that no longer exists.

## Report contract (your final message)
1. Files changed, one line each.
2. Network count per block and total.
3. How you built the multi-rung power rail and what evidence you used.
4. Gate output (literal).
5. Anything in this brief you could not do or did differently, and why.
6. The list of names `build_hmi.py` / `build_alarms.py` used that no longer exist.
