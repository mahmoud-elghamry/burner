"""Check the project docs against each other and against the tree.

    py tools\check_docs.py

Rules:
  1. repo paths exist; historical build/baseline evidence may live in the main worktree
  2. docs/STATE.md stays under 60 lines
  3. Q/F numbers in docs/ISSUES.md are unique
  4. every docs/decisions/NNNN-*.md is listed in docs/decisions/README.md
  5. the active C&E workbook is newer than its generator, or committed with it unchanged
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIXES = ("docs/", "tools/", "inputs/", "deliverables/", "tia/", "export/", "build/", "baseline/")
errors = []


def git(*args):
    result = subprocess.run(['git', '-C', str(ROOT), *args],
                            capture_output=True, text=True, encoding='utf-8')
    return result.stdout.strip() if result.returncode == 0 else None


# Worktrees do not copy ignored historical evidence. Only build/baseline links
# may resolve there: current source/spec/deliverable links must still exist here.
common_dir = git('rev-parse', '--git-common-dir')
MAIN_ROOT = (ROOT / common_dir).resolve().parent if common_dir else ROOT


def historical_path_exists(path, document):
    historical = (path.startswith('baseline/') or
                  (path.startswith('build/') and
                   document.is_relative_to(ROOT / 'docs/evidence')))
    return historical and (MAIN_ROOT / path).exists()


def committed_together_unchanged(*paths):
    relative = [p.relative_to(ROOT).as_posix() for p in paths]
    if git('status', '--porcelain', '--', *relative) != '':
        return False
    commits = [git('log', '-1', '--format=%H', '--', p) for p in relative]
    return bool(commits[0]) and len(set(commits)) == 1


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
            if not (ROOT / p).exists() and not (f.parent / p).exists() and not historical_path_exists(p, f):
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

# 5 — Active C&E regenerated. Rev A is an intentionally frozen archive;
# build_ce.py produces Rev B only. Checkout mtimes do not establish staleness
# when the unchanged workbook and generator were committed together.
gen = ROOT / "tools/build_ce.py"
x = ROOT / "deliverables/PH-LCP-01-CE_RevB.xlsx"
if not x.exists():
    errors.append(f"{x.relative_to(ROOT)} does not exist")
elif x.stat().st_mtime < gen.stat().st_mtime and not committed_together_unchanged(gen, x):
    errors.append(f"{x.relative_to(ROOT)} is older than tools/build_ce.py — run py tools\build_ce.py")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print("OK — docs consistent")
