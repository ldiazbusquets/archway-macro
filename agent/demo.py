"""Synthetic data for offline demos and tests.

DEMO DATA IS NOT REAL. It lets the pipeline and dashboard run without a FRED
key (classroom demos, CI tests). Every output produced in demo mode is labeled
"DEMO" in the JSON and on the dashboard.
"""

from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

FREQ = {"D": "B", "W": "W-SAT", "M": "MS", "Q": "QS"}

# (start level, drift per period, noise per period, floor) -- loose shapes only
SHAPES = {
    "CPIAUCSL": (170, 0.0022, 0.0018, None, "pct"),
    "CPILFESL": (180, 0.0021, 0.0012, None, "pct"),
    "PCEPILFE": (75, 0.0018, 0.0010, None, "pct"),
    "UNRATE": (4.5, 0.0, 0.12, 3.4, "abs_mr"),
    "PAYEMS": (131000, 0.0010, 0.0012, None, "pct"),
    "ICSA": (230000, 0.0, 0.05, 180000, "pct_mr"),
    "GDPC1": (13000, 0.0050, 0.0060, None, "pct"),
    "INDPRO": (90, 0.0007, 0.0060, None, "pct"),
    "RSAFS": (250000, 0.0030, 0.0080, None, "pct"),
    "UMCSENT": (85, 0.0, 3.0, 50, "abs_mr"),
    "FEDFUNDS": (3.0, 0.0, 0.12, 0.05, "abs_mr"),
    "DGS2": (3.4, 0.0, 0.045, 0.10, "abs_mr"),
    "DGS10": (4.0, 0.0, 0.045, 0.50, "abs_mr"),
}


# Approximate day-of-month each monthly series is released (month after the reference month)
RELEASE_DAY = {"CPIAUCSL": 13, "CPILFESL": 13, "PCEPILFE": 28, "UNRATE": 7, "PAYEMS": 7,
               "INDPRO": 17, "RSAFS": 15, "UMCSENT": 1, "FEDFUNDS": 1}


def release_date(series_id: str, frequency: str, d: pd.Timestamp) -> pd.Timestamp:
    if frequency == "M":
        return d + pd.offsets.MonthBegin(1) + pd.Timedelta(days=RELEASE_DAY.get(series_id, 15) - 1)
    if frequency == "Q":
        return d + pd.offsets.QuarterBegin(1, startingMonth=1) + pd.Timedelta(days=28)
    if frequency == "W":
        return d + pd.Timedelta(days=5)
    return d


# Demo-only "events" so every flag type shows up in a classroom demo.
SCENARIO = {
    "CPILFESL": "revise",      # an already-published value changes
    "RSAFS": "spike",          # unusual move
    "DGS10": "missing",        # FRED returns "." for the latest date
    "FEDFUNDS": "fetch_fail",  # API request fails
}


def apply_scenario(series_id: str, s: pd.Series) -> pd.Series:
    kind = SCENARIO.get(series_id)
    s = s.copy()
    if kind == "revise" and len(s) > 2:
        s.iloc[-2] = round(s.iloc[-2] * 1.0015, 3)
    elif kind == "spike":
        s.iloc[-1] = round(s.iloc[-2] * 1.032, 3)
    elif kind == "missing":
        s.iloc[-1] = float("nan")
    elif kind == "fetch_fail":
        raise ConnectionError("demo scenario: FRED request timed out")
    return s


def demo_series(series_id: str, frequency: str, start: str, end: str | None = None) -> pd.Series:
    """Deterministic synthetic series (same id -> same data every run)."""
    end = end or pd.Timestamp.today().normalize()
    end = pd.Timestamp(end)
    idx = pd.date_range(start, end, freq=FREQ[frequency])
    # Mimic publication lags: an observation only "exists" once it is released.
    idx = idx[[release_date(series_id, frequency, d) <= end for d in idx]]
    rng = np.random.default_rng(zlib.crc32(series_id.encode()))
    n = len(idx)

    if series_id == "T10Y2Y":
        a, b = demo_series("DGS10", frequency, start, end), demo_series("DGS2", frequency, start, end)
        return (a - b).rename(series_id).round(2)

    lvl, drift, noise, floor, kind = SHAPES.get(series_id, (100, 0.001, 0.005, None, "pct"))
    k = {"D": 0.004, "W": 0.02, "M": 0.08, "Q": 0.2}[frequency]  # mean reversion speed
    x = np.empty(n)
    x[0] = lvl
    for i in range(1, n):
        e = rng.normal(0, noise)
        if kind == "pct":
            x[i] = x[i - 1] * (1 + drift + e)
        elif kind == "pct_mr":  # mean-reverting in logs
            x[i] = x[i - 1] * np.exp(0.05 * np.log(lvl / x[i - 1]) + e)
        elif kind == "abs_mr":
            x[i] = x[i - 1] + k * (lvl - x[i - 1]) + e
        else:  # random walk in levels
            x[i] = x[i - 1] + e
        if floor is not None:
            x[i] = max(x[i], floor)
    return pd.Series(x, index=idx, name=series_id).round(3)
