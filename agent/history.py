"""Per-indicator CSV history: the agent's saved output.

One file per series (e.g. docs/data/csv/CPIAUCSL.csv) with columns:

    date, series_id, value, <calculated columns>, retrieved_at_utc

Rules (from the course brief):
  * New observations are appended; a date already in the file is never written twice.
  * Existing rows are never rewritten. If FRED revises a past value, the run
    flags it for students instead of silently changing saved history.
  * Rows with a missing FRED value (".") are not written.
  * If a fetch fails, the file is left exactly as it was.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from .compute import yoy_by_date

# A calc may add more than one column (change also records which date it compares to).
CALC_COLUMNS = {"yoy_pct": ["yoy_pct"], "change": ["change", "prior_date"]}


def calc_frame(s: pd.Series, ind: dict) -> pd.DataFrame:
    """Raw values plus only the calculations listed in the indicator's csv_calcs."""
    clean = s.dropna()
    df = pd.DataFrame({"value": clean})
    for c in ind.get("csv_calcs", []):
        if c == "yoy_pct":
            df["yoy_pct"] = yoy_by_date(clean)          # same month last year, by date
        elif c == "change":
            df["change"] = clean - clean.shift(1)      # vs the previous published observation
            df["prior_date"] = [None] + [d.strftime("%Y-%m-%d") for d in clean.index[:-1]]
        else:
            raise ValueError(f"unknown csv calc: {c}")
    return df


def read_dates(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with open(path, newline="") as f:
        return {row["date"] for row in csv.DictReader(f)}


def update_csv(path: Path, s: pd.Series, ind: dict, retrieved_at: str, start: str) -> dict:
    """Append observations not already saved. Returns what happened."""
    df = calc_frame(s, ind)
    df = df[df.index >= pd.Timestamp(start)]
    have = read_dates(path)
    calcs = [col for c in ind.get("csv_calcs", []) for col in CALC_COLUMNS[c]]
    cols = ["date", "series_id", "value", *calcs, "retrieved_at_utc"]

    new_rows = []
    for d, r in df.iterrows():
        ds = d.strftime("%Y-%m-%d")
        if ds in have:
            continue
        row = {"date": ds, "series_id": ind["id"], "value": _fmt(r["value"]), "retrieved_at_utc": retrieved_at}
        for c in calcs:
            row[c] = r[c] if c == "prior_date" else _fmt(r[c])
        new_rows.append(row)

    # Only add dates newer than what we already have, unless the file is new.
    # (Older dates missing from an existing file would mean FRED back-filled
    # history; we still add them, sorted, so the file stays complete.)
    path.parent.mkdir(parents=True, exist_ok=True)
    first = not path.exists()
    if new_rows:
        if first:
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerows(new_rows)
        else:
            with open(path, newline="") as f:
                existing = list(csv.DictReader(f))
            allrows = sorted(existing + new_rows, key=lambda r: r["date"])
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerows(allrows)
    return {
        "file": str(path),
        "created": first and bool(new_rows),
        "added": len(new_rows),
        "added_dates": [r["date"] for r in new_rows][-5:],
        "rows": len(have) + len(new_rows),
    }


def _fmt(v) -> str:
    if isinstance(v, str):
        return v
    if v is None or pd.isna(v):
        return ""
    return f"{float(v):.6g}" if abs(float(v)) < 1e6 else f"{float(v):.2f}"
