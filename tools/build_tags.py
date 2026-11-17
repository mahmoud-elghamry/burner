"""Build the PLC tag table (SimaticML) from the IO List.

    py tools/build_tags.py

Reads the "IO List" sheet of deliverables/PH-LCP-01-CE_RevA.xlsx, column "PLC Tag",
and writes build/tags/IO.xml: a PlcTagTable named "IO" for tools/Apply-Tags.ps1.
Naming rule: docs/decisions/0005-tag-naming.md. Address rule: %I/%Q bit -> Bool,
%IW word -> Int. The comment of each tag is the Description column (en-US).

Rows whose PLC Tag is "—" or empty (spare, reserved, range) are skipped.

Exits with code 1 and writes no XML (an old build/tags/IO.xml is removed) on:
  - a name that breaks 0005 (regex, lowercase-only part, or not PascalCase)
  - a duplicate name (case-insensitive: TIA symbol names are not case-sensitive)
  - a duplicate address
  - an address that cannot be parsed (I<byte>.<bit>, Q<byte>.<bit>, IW<byte>)
"""
import datetime
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "deliverables" / "PH-LCP-01-CE_RevA.xlsx"
OUT = ROOT / "build" / "tags" / "IO.xml"
TABLE_NAME = "IO"
NO_TAG = {"", "—"}

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)*$")
BIT_RE = re.compile(r"^([IQ])(\d+)\.([0-7])$")
WORD_RE = re.compile(r"^IW(\d+)$")

# Same header as the TIA export in export/xml/PLC_PLC_1/PlcTags (V15.1).
INSTALLED_PRODUCTS = [
    ("Product", "Totally Integrated Automation Portal", "V15.1"),
    ("OptionPackage", "TIA Portal Openness", "V15.1"),
    ("Product", "STEP 7 Professional", "V15.1"),
    ("Product", "WinCC Professional", "V15.1"),
]


def name_problem(name):
    """Return why a PLC tag name breaks decisions/0005, or None."""
    if not NAME_RE.match(name):
        return "does not match ^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)*$"
    for part in name.split("_"):
        letters = [c for c in part if c.isalpha()]
        if letters and not any(c.isupper() for c in letters):
            return f"has a lowercase-only part '{part}'"
        if part[0].isalpha() and not part[0].isupper():
            return f"has a part '{part}' that is not PascalCase"
    return None


def tia_address(addr):
    """Map the IO List address to (TIA logical address, data type), or (None, None)."""
    m = BIT_RE.match(addr)
    if m:
        return f"%{m.group(1)}{m.group(2)}.{m.group(3)}", "Bool"
    m = WORD_RE.match(addr)
    if m:
        return f"%IW{m.group(1)}", "Int"
    return None, None


def find_io_header(ws):
    """Return (header row, {column name: column index}) for the IO List sheet."""
    for r in range(1, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
        if "Address" in vals and "PLC Tag" in vals:
            cols = {str(v).strip(): c for c, v in enumerate(vals, 1) if v not in (None, "")}
            for need in ("Tag", "Description"):
                if need not in cols:
                    raise SystemExit(f"IO List header has no '{need}' column")
            return r, cols
    raise SystemExit("IO List: no header row with 'Address' and 'PLC Tag'")


def text_of(v):
    return "" if v is None else str(v).strip()


def build_document(entries):
    doc = ET.Element("Document")
    ET.SubElement(doc, "Engineering", version="V15.1")
    info = ET.SubElement(doc, "DocumentInfo")
    created = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    ET.SubElement(info, "Created").text = created
    ET.SubElement(info, "ExportSetting").text = "WithDefaults"
    products = ET.SubElement(info, "InstalledProducts")
    for kind, name, version in INSTALLED_PRODUCTS:
        p = ET.SubElement(products, kind)
        ET.SubElement(p, "DisplayName").text = name
        ET.SubElement(p, "DisplayVersion").text = version

    table = ET.SubElement(doc, "SW.Tags.PlcTagTable", ID="0")
    ET.SubElement(ET.SubElement(table, "AttributeList"), "Name").text = TABLE_NAME
    tags = ET.SubElement(table, "ObjectList")

    nid = 1
    for taddr, dtype, name, desc, _tag, _row in entries:
        tag = ET.SubElement(tags, "SW.Tags.PlcTag", ID=str(nid), CompositionName="Tags")
        nid += 1
        a = ET.SubElement(tag, "AttributeList")
        ET.SubElement(a, "DataTypeName").text = dtype
        ET.SubElement(a, "ExternalAccessible").text = "true"
        ET.SubElement(a, "ExternalVisible").text = "true"
        ET.SubElement(a, "ExternalWritable").text = "true"
        ET.SubElement(a, "LogicalAddress").text = taddr
        ET.SubElement(a, "Name").text = name

        comment = ET.SubElement(ET.SubElement(tag, "ObjectList"), "MultilingualText",
                                ID=str(nid), CompositionName="Comment")
        nid += 1
        item = ET.SubElement(ET.SubElement(comment, "ObjectList"), "MultilingualTextItem",
                             ID=str(nid), CompositionName="Items")
        nid += 1
        ia = ET.SubElement(item, "AttributeList")
        ET.SubElement(ia, "Culture").text = "en-US"
        ET.SubElement(ia, "Text").text = desc
    ET.indent(doc, space="  ")
    return doc


def main():
    if not SRC.exists():
        raise SystemExit(f"missing {SRC} - run py tools/build_ce.py first")
    wb = load_workbook(SRC, data_only=True)
    if "IO List" not in wb.sheetnames:
        raise SystemExit("workbook has no 'IO List' sheet")
    ws = wb["IO List"]
    header_row, cols = find_io_header(ws)

    errors = []
    entries = []        # (tia address, data type, PLC name, description, drawing tag, row)
    names = {}          # lower-case name -> row
    addresses = {}      # TIA address -> row

    for r in range(header_row + 1, ws.max_row + 1):
        cell = {k: ws.cell(r, c).value for k, c in cols.items()}
        plc = text_of(cell.get("PLC Tag"))
        if plc in NO_TAG:
            continue
        addr = text_of(cell.get("Address"))
        tag = text_of(cell.get("Tag"))
        desc = text_of(cell.get("Description"))
        where = f"IO List row {r} ({addr} / {tag} -> {plc})"

        problem = name_problem(plc)
        if problem:
            errors.append(f"{where}: name {problem} (decisions/0005)")

        taddr, dtype = tia_address(addr)
        if taddr is None:
            errors.append(f"{where}: address '{addr}' cannot be parsed "
                          "(expected I<byte>.<bit>, Q<byte>.<bit> or IW<byte>)")
            continue

        if plc.lower() in names:
            errors.append(f"{where}: duplicate name, same as row {names[plc.lower()]} "
                          "(case-insensitive)")
        else:
            names[plc.lower()] = r
        if taddr in addresses:
            errors.append(f"{where}: duplicate address {taddr}, same as row {addresses[taddr]}")
        else:
            addresses[taddr] = r

        if not problem:
            entries.append((taddr, dtype, plc, desc, tag, r))

    if not entries and not errors:
        errors.append("no PLC tags found in the IO List")

    if errors:
        for e in errors:
            print("ERROR: " + e)
        if OUT.exists():
            OUT.unlink()
        print(f"FAILED: {len(errors)} problem(s); no tag table written.")
        sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build_document(entries)
    text = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(doc, encoding="unicode")
    OUT.write_text("﻿" + text + "\n", encoding="utf-8")

    # re-read what was written: it must parse, and hold every tag once
    back = ET.parse(OUT).getroot()
    found = back.findall(".//SW.Tags.PlcTag")
    if len(found) != len(entries):
        raise SystemExit(f"self-check failed: wrote {len(entries)} tags, read back {len(found)}")

    print(f"wrote {OUT}")
    print(f"{len(entries)} tags in table '{TABLE_NAME}' (well-formed XML)")
    print("")
    print(f"{'Address':<10}{'Drawing':<11}{'PLC tag':<20}{'Type':<6}Comment")
    for taddr, dtype, name, desc, tag, _row in entries:
        print(f"{taddr:<10}{tag:<11}{name:<20}{dtype:<6}{desc}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
