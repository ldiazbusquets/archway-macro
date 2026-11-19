"""Independent verification of the agent's saved output (Assignment 3 evidence).

Deliberately does NOT import the agent's code. It downloads each series from
FRED's public graph CSV (a different endpoint from the API the agent uses, no
key needed), then checks the agent's CSVs against it:

  1. Source comparison  - 2 dates per indicator: the agent's value equals FRED's.
  2. Hand calculation   - recompute the latest calculated value from FRED's raw
                          numbers with the textbook formula and compare.
  3. Run twice          - run the agent twice on a copy of the data; the second
                          run must add no rows and no CSV may contain a duplicate date.
  4. Invalid series ID  - run the agent with one bad ID on a copy of the data;
                          the run must report the error, exit non-zero, and leave
                          every saved CSV unchanged.

Writes verification/REPORT.md. Exit code 1 if any check fails.

    python verify/verify_fred.py            # needs FRED_API_KEY for checks 3-4
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "indicators.yaml"
DATA = ROOT / "docs" / "data"
REPORT = ROOT / "verification" / "REPORT.md"
GRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
PERIODS = {"D": 252, "W": 52, "M": 12, "Q": 4}


def fred_graph(series_id: str) -> dict[str, float]:
    r = requests.get(GRAPH.format(series_id), timeout=60)
    r.raise_for_status()
    rows = list(csv.reader(io.StringIO(r.text)))
    out = {}
    for row in rows[1:]:                      # header is DATE/observation_date, <ID>
        if len(row) >= 2 and row[1] not in (".", ""):
            out[row[0]] = float(row[1])
    return out


def agent_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def close(a: float, b: float) -> bool:
    return abs(a - b) <= max(1e-6, abs(b) * 1e-6)


def run_agent(out: Path, config: Path = CFG) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "agent.run", "--config", str(config), "--out", str(out)],
                          cwd=ROOT, capture_output=True, text=True)


def main() -> int:
    cfg = yaml.safe_load(CFG.read_text())
    lines, ok_all = [], True
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines += [f"# Verification report", "",
              f"Generated {now} by `verify/verify_fred.py`, which does not use the agent's code. "
              "Source of truth: FRED public graph CSV (`fredgraph.csv`), a different endpoint from the API the agent calls.", ""]

    # ---- 1 & 2: source comparison and hand calculation -------------------------
    lines += ["## 1. Source comparison (2 dates per indicator)", "",
              "| Indicator | Date | Agent CSV | FRED | Result |", "|---|---|---|---|---|"]
    calc_lines = ["## 2. Hand calculation", "",
                  "| Indicator | Date | Formula | By hand (from FRED) | Agent CSV | Result |", "|---|---|---|---|---|---|"]
    for ind in cfg["indicators"]:
        sid = ind["id"]
        path = DATA / "csv" / f"{sid}.csv"
        if not path.exists():
            lines.append(f"| {sid} | n/a | no CSV yet | | FAIL |")
            ok_all = False
            continue
        rows = agent_csv(path)
        fred = fred_graph(sid)
        step = PERIODS[ind["frequency"]]
        picks = [rows[-1], rows[max(0, len(rows) - 1 - step)]]   # latest, and about a year earlier
        for r in picks:
            fv = fred.get(r["date"])
            good = fv is not None and close(float(r["value"]), fv)
            ok_all &= good
            lines.append(f"| {sid} | {r['date']} | {float(r['value']):g} | {fv if fv is not None else 'missing'} | {'PASS' if good else 'FAIL'} |")

        latest = rows[-1]
        dates = sorted(fred)
        i = dates.index(latest["date"]) if latest["date"] in dates else None
        for c in ind.get("csv_calcs", []):
            if i is None:
                calc_lines.append(f"| {sid} | {latest['date']} | {c} | date not on FRED | {latest.get(c)} | FAIL |")
                ok_all = False
                continue
            if c == "yoy_pct":
                prev_d = dates[i - step]
                hand = (fred[latest["date"]] / fred[prev_d] - 1) * 100
                formula = f"({fred[latest['date']]:g} / {fred[prev_d]:g} − 1) × 100  [vs {prev_d}]"
            else:
                prev_d = dates[i - 1]
                hand = fred[latest["date"]] - fred[prev_d]
                formula = f"{fred[latest['date']]:g} − {fred[prev_d]:g}  [vs {prev_d}]"
            agent_v = float(latest[c])
            good = abs(hand - agent_v) < 5e-4
            ok_all &= good
            calc_lines.append(f"| {sid} | {latest['date']} | {formula} | {hand:.4f} | {agent_v:.4f} | {'PASS' if good else 'FAIL'} |")
    lines += [""] + calc_lines + [""]

    # ---- 3 & 4: behaviour tests on a copy of the data --------------------------
    if not os.environ.get("FRED_API_KEY"):
        lines += ["## 3–4. Run twice / invalid series ID", "", "Skipped: FRED_API_KEY not set.", ""]
    else:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "data"
            shutil.copytree(DATA, work)
            run_agent(work)                                  # bring the copy up to date
            snap = {p.name: p.read_bytes() for p in (work / "csv").glob("*.csv")}
            second = run_agent(work)
            unchanged = all((work / "csv" / n).read_bytes() == b for n, b in snap.items())
            dupes = [p.name for p in (work / "csv").glob("*.csv")
                     if len({r["date"] for r in agent_csv(p)}) != len(agent_csv(p))]
            status = (work / "status.txt").read_text()
            good3 = unchanged and not dupes and "rows added" in status
            ok_all &= good3
            lines += ["## 3. Run twice", "",
                      f"- Second run changed a CSV: **{'no' if unchanged else 'YES'}**",
                      f"- Files with duplicate dates: **{', '.join(dupes) or 'none'}**",
                      f"- Result: **{'PASS' if good3 else 'FAIL'}**", "",
                      "Status file after the second run:", "", "```", status.strip(), "```", ""]

            bad = Path(tmp) / "bad.yaml"
            first_id = cfg["indicators"][0]["id"]
            bad.write_text(CFG.read_text().replace(f"id: {first_id},", "id: NOTAREALSERIES123,", 1))
            snap = {p.name: p.read_bytes() for p in (work / "csv").glob("*.csv")}
            res = run_agent(work, bad)
            kept = all((work / "csv" / n).read_bytes() == b for n, b in snap.items())
            status = (work / "status.txt").read_text()
            good4 = res.returncode != 0 and "NOTAREALSERIES123: ERROR" in status and kept
            ok_all &= good4
            lines += ["## 4. Invalid series ID", "",
                      f"- Exit code: **{res.returncode}** (non-zero expected)",
                      f"- Saved CSVs unchanged: **{'yes' if kept else 'NO'}**",
                      f"- Result: **{'PASS' if good4 else 'FAIL'}**", "",
                      "Status file:", "", "```", status.strip(), "```", ""]

    lines += ["## Overall", "", f"**{'ALL CHECKS PASSED' if ok_all else 'SOME CHECKS FAILED'}**", ""]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines))
    print("\n".join(lines))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
