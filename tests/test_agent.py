"""Offline tests. No API key or network needed."""

import json

import numpy as np
import pandas as pd
import pytest

from agent.compute import compute_metrics, headline_series, zscore_latest
from agent.run import main
from agent.validate import check_series, snapshot

IND_M = {"id": "X", "name": "Test index", "frequency": "M", "units": "Index", "headline": "yoy_pct",
         "stale_days": 75, "z_flag": 2.0}


def monthly(values, start="2020-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


# ---------- calculations ----------

def test_yoy_matches_hand_calc():
    s = monthly([100 + i for i in range(24)])           # Jan 2020 .. Dec 2021
    h = headline_series(s, "yoy_pct", "M")
    assert h.iloc[-1] == pytest.approx((123 / 111 - 1) * 100)


def test_mom_and_diff_and_qoq():
    s = monthly([100, 102, 101])
    assert headline_series(s, "mom_pct", "M").iloc[-1] == pytest.approx((101 / 102 - 1) * 100)
    assert headline_series(s, "diff", "M").iloc[-1] == pytest.approx(-1)
    q = pd.Series([100.0, 101.0], index=pd.to_datetime(["2026-01-01", "2026-04-01"]))
    assert headline_series(q, "qoq_saar", "Q").iloc[-1] == pytest.approx((1.01 ** 4 - 1) * 100)


def test_missing_values_are_skipped_not_zeroed():
    s = monthly([100, 101, np.nan, 103])
    m = compute_metrics(s, {**IND_M, "headline": "level"}, 5)
    assert m["latest_value"] == 103 and m["prior_value"] == 101


def test_zscore_flags_only_big_moves():
    rng = np.random.default_rng(0)
    moves = pd.Series(rng.normal(0, 1, 80))
    assert abs(zscore_latest(moves, "M", 5)) < 4
    moves.iloc[-1] = 10
    assert zscore_latest(moves, "M", 5) > 5


# ---------- validation ----------

def test_stale_and_missing_flags():
    s = monthly([100] * 30 + [np.nan], start="2023-01-01")   # last row Jul 2025 is "."
    m = compute_metrics(s, IND_M, 5)
    kinds = {f["kind"] for f in check_series(s, IND_M, m, None, pd.Timestamp("2026-11-17"))}
    assert {"missing_value", "stale"} <= kinds


def test_revision_and_new_release():
    old = monthly([100, 101, 102, 103])
    state = snapshot(old)
    new = monthly([100, 101, 102.5, 103, 104])               # Mar revised, May is new
    m = compute_metrics(new, {**IND_M, "headline": "level"}, 5)
    flags = check_series(new, IND_M, m, state, pd.Timestamp("2020-06-15"))
    kinds = {f["kind"] for f in flags}
    assert {"revision", "new_release"} <= kinds and "stale" not in kinds


# ---------- end to end ----------

def test_demo_run_writes_dashboard_json(tmp_path):
    out = tmp_path / "data"
    assert main(["--demo", "--out", str(out), "--today", "2026-11-03"]) == 0
    code = main(["--demo", "--scenario", "--out", str(out), "--today", "2026-11-17"])
    assert code == 2                                          # errors must fail the run visibly
    d = json.loads((out / "latest.json").read_text())
    assert d["mode"] == "demo" and len(d["indicators"]) == 14
    kinds = {f["kind"] for r in d["indicators"] for f in r["flags"]}
    assert {"revision", "unusual_move", "missing_value", "fetch_failed", "new_release"} <= kinds
    fed = next(r for r in d["indicators"] if r["id"] == "FEDFUNDS")
    assert fed["latest_value"] is not None                    # last good data kept, and flagged
    assert len((out / "run_log.jsonl").read_text().splitlines()) == 2
