"""Check the project docs against each other and against the tree.

    py tools\check_docs.py

Rules:
  1. every backticked path in AGENTS.md and docs/*.md that looks like a repo path exists
  2. docs/STATE.md stays under 60 lines
  3. Q/F numbers in docs/ISSUES.md are unique
  4. every docs/decisions/NNNN-*.md is listed in docs/decisions/README.md
  5. the C&E workbook is newer than its generator
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIXES = ("docs/", "tools/", "inputs/", "deliverables/", "tia/", "export/", "build/", "baseline/")
errors = []


def md_files():
    yield ROOT / "AGENTS.md"
    yield from sorted((ROOT / "docs").rglob("*.md"))


# 1 — paths
for f in md_files():
    for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        for p in re.findall(r"`([^`\s]+)`", line):
            p = p.replace("\\", "/").rstrip("/")
            if not p.startswith(PREFIXES) or any(c in p for c in "*<>"):
                continue
            if re.fullmatch(r"docs/decisions/\d{4}", p) and list((ROOT / "docs/decisions").glob(p[-4:] + "-*.md")):
                continue
            if not (ROOT / p).exists() and not (f.parent / p).exists():
                errors.append(f"{f.relative_to(ROOT)}:{n}: path does not exist: {p}")

# 2 — STATE length
state = (ROOT / "docs/STATE.md").read_text(encoding="utf-8").splitlines()
if len(state) > 60:
    errors.append(f"docs/STATE.md: {len(state)} lines (max 60)")

# 3 — unique issue numbers
ids = re.findall(r"^\|\s*([QF]\d+)\s*\|", (ROOT / "docs/ISSUES.md").read_text(encoding="utf-8"), re.M)
for i in sorted({i for i in ids if ids.count(i) > 1}):
    errors.append(f"docs/ISSUES.md: {i} used more than once")

# 4 — decisions indexed
dec = ROOT / "docs/decisions"
index = (dec / "README.md").read_text(encoding="utf-8")
for f in sorted(dec.glob("[0-9][0-9][0-9][0-9]-*.md")):
    if f.name not in index:
        errors.append(f"docs/decisions/README.md: {f.name} not listed")

# 5 — C&E regenerated
gen = ROOT / "tools/build_ce.py"
for x in (ROOT / "deliverables").glob("PH-LCP-01-CE_*.xlsx"):
    if x.stat().st_mtime < gen.stat().st_mtime:
        errors.append(f"{x.relative_to(ROOT)} is older than tools/build_ce.py — run py tools\build_ce.py")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print("OK — docs consistent")
