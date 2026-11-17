"""Checks that decide what a student must look at. The agent flags; students decide.

Severity
  error   the data may be wrong or missing; do not use until a student checks it
  review  the data looks right but deserves human attention (unusual move, revision)
  info    nothing to do (e.g. new release arrived)
"""

from __future__ import annotations

import pandas as pd


def flag(kind: str, severity: str, message: str) -> dict:
    return {"kind": kind, "severity": severity, "message": message}


def check_series(s: pd.Series, ind: dict, metrics: dict, prior_state: dict | None, today: pd.Timestamp) -> list[dict]:
    flags = []
    clean = s.dropna()

    # 1. Missing latest value (FRED publishes "." for some dates)
    if pd.isna(s.iloc[-1]):
        flags.append(flag("missing_value", "error",
                          f"Latest FRED row ({s.index[-1].date()}) has no value; showing {clean.index[-1].date()} instead."))

    # 2. Stale series: no new observation in longer than expected
    age = (today - clean.index[-1]).days
    if age > ind["stale_days"]:
        flags.append(flag("stale", "error",
                          f"No new data for {age} days (expected within {ind['stale_days']}). Check the source or release calendar."))

    # 3. Unusual move vs trailing history
    z = metrics.get("z_move")
    if z is not None and abs(z) >= ind["z_flag"]:
        flags.append(flag("unusual_move", "review",
                          f"Latest move is {z:+.1f} standard deviations from the trailing average. Verify against the source before discussing."))

    # 4. Revisions to values already published
    if prior_state and prior_state.get("recent"):
        revised = []
        for d, old in prior_state["recent"].items():
            ts = pd.Timestamp(d)
            if ts in clean.index:
                new = float(clean.loc[ts])
                if abs(new - old) > max(1e-6, abs(old) * 1e-5):
                    revised.append(f"{d}: {old:g} → {new:g}")
        if revised:
            flags.append(flag("revision", "review", "Previously published values were revised: " + "; ".join(revised[:3])))

    # 5. New release
    if prior_state and prior_state.get("last_obs_date") and metrics["latest_date"] > prior_state["last_obs_date"]:
        flags.append(flag("new_release", "info", f"New observation for {metrics['latest_date']}."))

    return flags


def snapshot(s: pd.Series, n: int = 6) -> dict:
    """What we remember about a series for next run's revision and new-release checks."""
    clean = s.dropna()
    return {
        "last_obs_date": clean.index[-1].strftime("%Y-%m-%d"),
        "recent": {d.strftime("%Y-%m-%d"): float(v) for d, v in clean.iloc[-n:].items()},
    }
