"""Deterministic calculations. No AI here: every number is reproducible from FRED."""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = {"D": 252, "W": 52, "M": 12, "Q": 4}


def yoy_by_date(clean: pd.Series) -> pd.Series:
    """Year-over-year % change matched by DATE (same date one year earlier).

    Not by position: FRED series can have gaps (e.g. no October 2025 CPI or
    unemployment rate after the 2025 government shutdown), and "12 rows back"
    would then compare against the wrong month. Where the year-earlier date
    has no value, the result is blank rather than a wrong number.
    """
    clean = clean.dropna()
    prior = clean.copy()
    prior.index = prior.index + pd.DateOffset(years=1)
    prior = prior[~prior.index.duplicated()]
    return (clean / prior.reindex(clean.index) - 1) * 100


def headline_series(s: pd.Series, headline: str, frequency: str) -> pd.Series:
    """The series shown as the indicator's main number."""
    s = s.dropna()
    if headline == "yoy_pct":
        return yoy_by_date(s)
    if headline == "mom_pct":
        return s.pct_change(1, fill_method=None) * 100
    if headline == "qoq_saar":
        return ((s / s.shift(1)) ** 4 - 1) * 100
    if headline == "diff":
        return s.diff()
    if headline == "level":
        return s
    raise ValueError(f"unknown headline transform: {headline}")


def move_series(s: pd.Series, headline: str) -> pd.Series:
    """Period-to-period moves used to judge whether the latest print is unusual."""
    s = s.dropna()
    if headline in ("yoy_pct", "mom_pct", "qoq_saar"):
        return s.pct_change(1, fill_method=None) * 100
    return s.diff()


def zscore_latest(moves: pd.Series, frequency: str, window_years: int) -> float | None:
    """z-score of the latest move against the trailing window (latest excluded)."""
    moves = moves.dropna()
    n = PERIODS_PER_YEAR[frequency] * window_years
    if len(moves) < 12:
        return None
    hist = moves.iloc[-(n + 1):-1]
    sd = hist.std()
    if not np.isfinite(sd) or sd == 0:
        return None
    return float((moves.iloc[-1] - hist.mean()) / sd)


def spark(h: pd.Series, frequency: str) -> list[list]:
    """Compact chart history: ~5 years, weekly points for daily series."""
    h = h.dropna()
    if frequency == "D":
        h = h.resample("W-FRI").last().dropna()
    keep = {"D": 260, "W": 260, "M": 60, "Q": 20}[frequency]
    h = h.iloc[-keep:]
    return [[d.strftime("%Y-%m-%d"), round(float(v), 3)] for d, v in h.items()]


def _num(v, nd):
    return None if v is None or pd.isna(v) else round(float(v), nd)


def compute_metrics(s: pd.Series, ind: dict, window_years: int) -> dict:
    clean = s.dropna()
    hfull = headline_series(clean, ind["headline"], ind["frequency"]).reindex(clean.index)
    h = hfull.dropna()
    moves = move_series(s, ind["headline"])
    latest_date = clean.index[-1]
    prior_date = clean.index[-2] if len(clean) > 1 else None
    out = {
        "latest_date": latest_date.strftime("%Y-%m-%d"),
        "latest_value": round(float(clean.iloc[-1]), 4),
        "prior_date": prior_date.strftime("%Y-%m-%d") if prior_date is not None else None,
        "prior_value": round(float(clean.iloc[-2]), 4) if len(clean) > 1 else None,
        # The headline belongs to the LATEST date. If it can't be computed for that
        # date (e.g. y/y with no value a year earlier), it is None, never an older number.
        "headline": _num(hfull.iloc[-1], 3),
        "headline_prior": _num(hfull.iloc[-2], 3) if len(hfull) > 1 else None,
        "headline_gap": None,
        "z_move": None,
        "spark": spark(h, ind["frequency"]),
    }
    if out["headline"] is None and ind["headline"] == "yoy_pct":
        out["headline_gap"] = (latest_date - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    if out["headline"] is not None and out["headline_prior"] is not None:
        out["headline_change"] = round(out["headline"] - out["headline_prior"], 3)
    else:
        out["headline_change"] = None
    if ind["headline"] in ("yoy_pct", "mom_pct"):
        mom = clean.pct_change(1, fill_method=None) * 100
        out["mom_pct"] = _num(mom.iloc[-1], 3)
        out["yoy_pct"] = out["headline"] if ind["headline"] == "yoy_pct" else _num(yoy_by_date(clean).iloc[-1], 3)
    z = zscore_latest(moves, ind["frequency"], window_years)
    out["z_move"] = round(z, 2) if z is not None else None
    return out
