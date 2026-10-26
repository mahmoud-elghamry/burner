# Burner PetroBaker — LCP-01 scrubber & burner control

Read this first. It is the entry point for every agent and every new session.
`CLAUDE.md` imports it for Claude Code. **Keep it under 150 lines** — detail
belongs in `docs/`. English here; **`docs/` stays Arabic** (tags and terms
stay English). Same convention as the tower-crane project.

---

## What this project is

Control panel **LCP-01** on a **natural-gas oil field** (not a factory). It runs:

- a **gas scrubber** that cleans the gas going to the burners
  (`PSH-101`, `LSH-102`, `LSHH-103`; valves `XV-401` flare, `XV-402` drain, `XV-403` suction);
- **two burners** heating two oil tanks: `BR01` Riello RS100 on `TK01`,
  `BR02` DLX 53 SHFP (client's, foreign 230 V) on `TK02`.

PLC: S7-1200 **CPU 1214C DC/DC/DC `6ES7214-1AG40-0XB0`** + SM 1231 TC (4× type K)
+ SM 1221 DI. HMI: KTP400. **TIA Portal V15.1** (`docs/decisions/0004`).

**Gas and flame. Treat every decision as safety-related.**

---

## The one safety boundary — do not cross it

**Flame safety belongs to each burner's own certified control box** (RS100: RMG88,
DLX 53: SQ DUAL) — purge, ignition, flame supervision, gas valves. The PLC only
gives a **heat request** (`TL` / `L`) and a **stage request** (`TR` / `T2`) and
reads **RUN** and **LOCKOUT**. **The PLC never drives a gas valve.**
E-STOP `S0` and safety thermostat `TS` are **hardwired**. `docs/decisions/0001`.

---

## The chain of truth

```
inputs/  (client docs, manuals, drawing)          ← never edited
   ↓
deliverables/PH-LCP-01-CE_*.xlsx                  ← trips / alarms / permissives (tools/build_ce.py)
docs/التشغيل.md                                   ← everything else: modes, START/STOP, RESET,
   ↓                                                power-up, lamps, HMI, test scenarios
tia/  (PLC program)                               ← every network cites a row: C07b, B-01, S-01 …
```

**Nothing goes into the code that is not a row in the C&E or a numbered line in `docs/التشغيل.md`.** If the code needs
behaviour the C&E does not have, add the row first, mark it `PH proposal`, and
it goes to the client. `docs/decisions/0002`.

Each C&E row says its source: `Client` (a client document) or `PH proposal`
(waiting for client approval). **Never present a PH proposal as a client requirement.**

---

## Where to look

| File | Holds |
|---|---|
| `docs/STATE.md` | what is done, what is next — **re-read it** |
| `docs/التشغيل.md` | **how the panel behaves** — the spec the code implements and the PLCSIM scenarios that prove it |
| `docs/ISSUES.md` | open questions and findings, numbered `Q1` / `F1` |
| `docs/decisions/` | one file per decision, with what was rejected |
| `docs/evidence/` | dated record of what was read, measured, confirmed — never overwritten |
| `docs/TOOLS.md` | the commands that actually work here |

---

## The tree

```
inputs/        client/  manuals/  drawings/    — read-only originals
deliverables/  what goes to the client (C&E, later: I/O list, FAT procedure)
docs/          see above
tools/         generators, TIA Openness scripts, checks
tia/           the TIA project (V15.1) — created in TIA, never hand-edited
export/        current export of tia/ (xml)      build/  generated XML for import
baseline/      export before a change
```

---

## Rules

1. **No "done" without the evidence.** Compile clean = the literal compile
   report. Logic works = a PLCSIM test that is written down in `docs/evidence/`.
2. **PLCSIM before hardware.** Every C&E row gets a simulated test before the
   panel. PLCSIM V15.1 and the WinCC RT Advanced simulator are installed.
3. **Inputs are the client's words; assumptions are ours.** If a drawing,
   manual and client sheet disagree, record it in `ISSUES.md` — do not pick one silently.
4. **Fail-safe by default.** Trips act on a contact *opening* / signal *lost*.
   Valve outputs are chosen so *de-energised = safe* (flare NO, drain NO, suction NC).
5. **Tag names follow `docs/decisions/0005`** — instrument tag from the drawing,
   no spaces, no typos. The tower crane taught us what a messy tag table costs.
6. **Single writer.** TIA must be **closed** before any Openness script; the
   scripts refuse otherwise. If the user has it open, ask — do not close it.
7. **Additive edits by default** (new block / new network), in-place edits need a
   `baseline/` diff. The `tia-openness` skill has the SimaticML rules — read it
   before generating any XML.
8. **Update `docs/STATE.md` before you finish**, and write anything learned in the
   chat into `docs/` — talk evaporates.
9. **Explain logic in ladder** to the user; he reads ladder in TIA.
10. **git: commit, never push.** Subject English (Conventional Commits),
    body Arabic. **No `Co-Authored-By` line** — the user asked for that.
11. **Python: use `py`, not `python`.** `python` on this PATH is another tool's
    venv without `openpyxl`.

---

## Commands

```powershell
py tools\build_ce.py                 # regenerate the C&E workbook
py tools\render_xlsx.py <file.xlsx>  # xlsx -> pdf, to look at it
py tools\check_docs.py               # docs consistency
powershell -ExecutionPolicy Bypass -File tools\Export-TiaProject.ps1
```

Full list in `docs/TOOLS.md`. The Openness scripts find the project as the
first `*.ap15_1` under `tia\`.
