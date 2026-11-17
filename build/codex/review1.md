Read-only review. Do not edit any file.

You are reviewing a task brief that another model will implement: build/codex/task1-plc.md in this repository
(a Siemens S7-1200 gas scrubber + two burner control project; read AGENTS.md for the rules). The current
generator is tools/build_blocks.py ("Rev B"); the behaviour spec is docs/التشغيل.md and
deliverables/PH-LCP-01-CE_RevB.xlsx (via tools/build_ce.py).

Check the brief against the current code and tell me, concretely:
1. Any place where the proposed blocks change behaviour versus Rev B beyond the two changes the brief allows
   (E-STOP read directly / drain held only while pressed; TL/TR not AND-ed with the E-STOP latch). Think about
   scan order, first scan / OB100, edges, set/reset priority, the BR02 fuel-change edge at power-up, and the
   removed Sys.FirstScan uses.
2. Safety problems (gas/flame): anything that could let a burner request heat, or the suction open, when Rev B
   would not.
3. Anything ambiguous or missing that would make the implementer guess (interfaces, names, ordering, the
   multi-rung SimaticML power rail, call output wiring, OB100 writing instance-DB members).
4. Whether writing "Scrubber_DB".Tripped (an FB Output) from OB100 and reading it as an input of the burner
   calls is sound on S7-1200 / TIA V15.1.
Answer as a numbered list, most important first, each with the file/line evidence. Say "no issue" for a
question with none. Keep it under 600 words.
