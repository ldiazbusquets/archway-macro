"""One Excel workbook per run: "getting it all onto one sheet".

The macro team named this as the repetitive, time-consuming part of the week
(interview, 08:21), and it already works in Excel (05:43). So every run writes
<output_dir>/macro_update.xlsx:

  * "This week": one row per indicator with the latest value, the comparison,
    whether new data arrived this run, any flags, and the FRED link.
  * One sheet per indicator: the saved history (same rows as csv/<ID>.csv),
    ready to chart in the presentation's own theme.

Charts and interpretation stay with the team.
"""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEAD = Font(bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="1F2A33")
NEW_FILL = PatternFill("solid", fgColor="E6F1FB")
ERR_FILL = PatternFill("solid", fgColor="FBEBEB")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v if v not in ("", None) else None


def write_workbook(out: Path, rows: list[dict], status_lines: list[str], run_at: str, mode: str) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "This week"
    ws["A1"] = "Archway macro update"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Run {run_at} ({mode}). Source: FRED, Federal Reserve Bank of St. Louis."
    if mode == "demo":
        ws["A3"] = "DEMO DATA: synthetic numbers, not real economic data."
        ws["A3"].font = Font(bold=True, color="B3261E")

    cols = ["Indicator", "FRED ID", "Latest date", "Latest value", "Headline", "Headline value",
            "Prior date", "Prior value", "New data this run", "Flags", "FRED page"]
    r0 = 5
    for j, c in enumerate(cols, 1):
        cell = ws.cell(row=r0, column=j, value=c)
        cell.font, cell.fill = HEAD, HEAD_FILL
    for i, r in enumerate(rows, r0 + 1):
        flags = "; ".join(f"{f['severity'].upper()}: {f['message']}" for f in r.get("flags", []) if f["severity"] != "info")
        added = r.get("csv", {}).get("added", 0)
        vals = [r["name"], r["id"], r.get("latest_date"), r.get("latest_value"), r.get("headline_label"),
                r.get("headline"), r.get("prior_date"), r.get("prior_value"),
                f"Yes ({added} rows)" if added else "No", flags or "None", r["source_url"]]
        for j, v in enumerate(vals, 1):
            ws.cell(row=i, column=j, value=v)
        if any(f["severity"] == "error" for f in r.get("flags", [])):
            fill = ERR_FILL
        elif added:
            fill = NEW_FILL
        else:
            fill = None
        if fill:
            for j in range(1, len(cols) + 1):
                ws.cell(row=i, column=j).fill = fill
        ws.cell(row=i, column=11).hyperlink = r["source_url"]

    s0 = r0 + len(rows) + 2
    ws.cell(row=s0, column=1, value="Status").font = Font(bold=True)
    for k, line in enumerate(status_lines, s0 + 1):
        ws.cell(row=k, column=1, value=line)
    for j, w in enumerate([34, 11, 12, 13, 14, 14, 12, 12, 17, 60, 40], 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    for row in ws.iter_rows(min_row=r0 + 1, max_row=r0 + len(rows)):
        row[9].alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = ws.cell(row=r0 + 1, column=1)

    for r in rows:
        path = out / "csv" / f"{r['id']}.csv"
        if not path.exists():
            continue
        sh = wb.create_sheet(r["id"][:31])
        with open(path, newline="") as f:
            data = list(csv.reader(f))
        for i, line in enumerate(data, 1):
            for j, v in enumerate(line, 1):
                cell = sh.cell(row=i, column=j, value=v if i == 1 or j in (1, 2) or "date" in data[0][j - 1] else _num(v))
                if i == 1:
                    cell.font, cell.fill = HEAD, HEAD_FILL
        sh.freeze_panes = "A2"
        for j in range(1, len(data[0]) + 1):
            sh.column_dimensions[get_column_letter(j)].width = 14 if j != len(data[0]) else 26

    target = out / "macro_update.xlsx"
    wb.save(target)
    return target
