"""Render an .xlsx to PDF with LibreOffice so it can be looked at.

    py tools\render_xlsx.py deliverables\PH-LCP-01-CE_RevA.xlsx

The PDF goes to build\ next to nothing else; the xlsx is never modified.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = [
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
]


def find_soffice():
    for p in CANDIDATES:
        if p.exists():
            return str(p)
    return shutil.which("soffice")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1]).resolve()
    if not src.exists():
        sys.exit(f"not found: {src}")
    soffice = find_soffice()
    if not soffice:
        sys.exit("LibreOffice not found — install it: winget install TheDocumentFoundation.LibreOffice")
    out = ROOT / "build"
    out.mkdir(exist_ok=True)
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out), str(src)],
                   check=True, capture_output=True, timeout=180)
    pdf = out / (src.stem + ".pdf")
    if not pdf.exists():
        sys.exit("conversion produced no PDF")
    print(pdf)


if __name__ == "__main__":
    main()
