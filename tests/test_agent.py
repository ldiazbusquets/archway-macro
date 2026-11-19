"""Offline tests. No API key or network needed."""

import json

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

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


# ---------- end to end (demo data, offline) ----------

import csv
import shutil

import agent.run as run_mod
from agent import demo as demo_mod


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_demo_scenario_raises_each_flag(tmp_path):
    out = tmp_path / "data"
    assert main(["--demo", "--out", str(out), "--today", "2026-11-03"]) == 0
    code = main(["--demo", "--scenario", "--out", str(out), "--today", "2026-11-17"])
    assert code == 2                                          # errors must fail the run visibly
    d = json.loads((out / "latest.json").read_text())
    assert d["mode"] == "demo" and len(d["indicators"]) == 3
    kinds = {f["kind"] for r in d["indicators"] for f in r["flags"]}
    assert {"revision", "unusual_move", "missing_value", "new_release"} <= kinds
    assert len((out / "run_log.jsonl").read_text().splitlines()) == 2


def test_run_twice_adds_no_duplicate_dates(tmp_path):
    """Brief: run the agent twice; the second run must not duplicate rows."""
    out = tmp_path / "data"
    main(["--demo", "--out", str(out), "--today", "2026-11-17"])
    first = {p.name: p.read_bytes() for p in (out / "csv").glob("*.csv")}
    main(["--demo", "--out", str(out), "--today", "2026-11-17"])
    for p in (out / "csv").glob("*.csv"):
        assert p.read_bytes() == first[p.name]                # nothing appended or rewritten
        dates = [r["date"] for r in _rows(p)]
        assert len(dates) == len(set(dates))


def test_no_new_data_is_reported(tmp_path):
    """Brief: the status must say plainly when nothing new came out."""
    out = tmp_path / "data"
    main(["--demo", "--out", str(out), "--today", "2026-11-17"])
    main(["--demo", "--out", str(out), "--today", "2026-11-17"])
    status = (out / "status.txt").read_text()
    assert "No new data for any indicator" in status
    assert status.count("no new data since the last run") == 3


def test_new_observations_are_appended_in_order(tmp_path):
    out = tmp_path / "data"
    main(["--demo", "--out", str(out), "--today", "2026-11-03"])
    before = len(_rows(out / "csv" / "CPIAUCSL.csv"))
    main(["--demo", "--out", str(out), "--today", "2026-11-17"])   # October CPI released Nov 13
    rows = _rows(out / "csv" / "CPIAUCSL.csv")
    assert len(rows) == before + 1 and rows[-1]["date"] == "2026-10-01"
    assert [r["date"] for r in rows] == sorted(r["date"] for r in rows)


def test_csv_calculation_matches_hand_calculation(tmp_path):
    """Brief: check one calculated value by hand. y/y % = (this month / same month last year - 1) x 100."""
    out = tmp_path / "data"
    main(["--demo", "--out", str(out), "--today", "2026-11-17"])
    rows = {r["date"]: r for r in _rows(out / "csv" / "CPIAUCSL.csv")}
    now, year_ago = float(rows["2026-10-01"]["value"]), float(rows["2025-10-01"]["value"])
    assert float(rows["2026-10-01"]["yoy_pct"]) == pytest.approx((now / year_ago - 1) * 100, abs=1e-3)
    u = {r["date"]: r for r in _rows(out / "csv" / "UNRATE.csv")}
    assert float(u["2026-10-01"]["change"]) == pytest.approx(float(u["2026-10-01"]["value"]) - float(u["2026-09-01"]["value"]), abs=1e-6)


def test_failed_fetch_keeps_saved_csv_and_last_good_values(tmp_path, monkeypatch):
    """Brief: when retrieval fails, keep the last valid results and report the problem."""
    out = tmp_path / "data"
    main(["--demo", "--out", str(out), "--today", "2026-11-03"])
    saved = (out / "csv" / "CPIAUCSL.csv").read_bytes()
    good = next(r for r in json.loads((out / "latest.json").read_text())["indicators"] if r["id"] == "CPIAUCSL")

    real = demo_mod.demo_series
    def flaky(sid, *a, **k):
        if sid == "CPIAUCSL":
            raise ConnectionError("simulated timeout")
        return real(sid, *a, **k)
    monkeypatch.setattr(run_mod, "demo_series", flaky)

    assert main(["--demo", "--out", str(out), "--today", "2026-11-17"]) == 2
    assert (out / "csv" / "CPIAUCSL.csv").read_bytes() == saved
    cpi = next(r for r in json.loads((out / "latest.json").read_text())["indicators"] if r["id"] == "CPIAUCSL")
    assert cpi["latest_value"] == good["latest_value"] and cpi["flags"][0]["kind"] == "fetch_failed"
    assert "Saved CSV left unchanged" in (out / "status.txt").read_text()


def test_invalid_series_id_is_reported_and_others_still_run(tmp_path):
    """Brief: test an invalid series ID."""
    cfg = tmp_path / "bad.yaml"
    text = open("config/indicators.yaml").read().replace("id: UNRATE,", "id: UNRATEXX,")
    cfg.write_text(text)
    out = tmp_path / "data"
    assert main(["--demo", "--config", str(cfg), "--out", str(out), "--today", "2026-11-17"]) == 2
    status = (out / "status.txt").read_text()
    assert "UNRATEXX: ERROR" in status and "does not exist" in status
    assert (out / "csv" / "CPIAUCSL.csv").exists() and not (out / "csv" / "UNRATEXX.csv").exists()


def test_demo_defaults_to_its_own_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copytree(Path(__file__).resolve().parents[1] / "config", tmp_path / "config")
    main(["--demo", "--today", "2026-11-17"])
    assert (tmp_path / "demo_output" / "latest.json").exists()
    assert not (tmp_path / "docs").exists()


def test_live_run_never_reuses_demo_values(tmp_path, monkeypatch):
    out = tmp_path / "data"
    main(["--demo", "--out", str(out), "--today", "2026-11-17"])
    monkeypatch.delenv("FRED_API_KEY", raising=False)         # live run with no key: every fetch fails
    assert main(["--out", str(out), "--today", "2026-11-17"]) == 2
    d = json.loads((out / "latest.json").read_text())
    assert d["mode"] == "live"
    assert all(r.get("latest_value") is None for r in d["indicators"])
    assert all(r["flags"][0]["kind"] == "fetch_failed" for r in d["indicators"])


def test_yoy_matches_by_date_across_a_data_gap():
    """FRED has no Oct 2025 CPI (2025 shutdown). y/y must still compare the same month, by date."""
    from agent.compute import yoy_by_date
    idx = pd.date_range("2024-09-01", "2026-10-01", freq="MS").drop(pd.Timestamp("2025-10-01"))
    s = pd.Series(range(100, 100 + len(idx)), index=idx, dtype=float)
    y = yoy_by_date(s)
    assert pd.isna(y.loc["2026-10-01"])                                              # year-earlier month missing: blank
    assert y.loc["2026-09-01"] == pytest.approx((s.loc["2026-09-01"] / s.loc["2025-09-01"] - 1) * 100)
    assert pd.isna(yoy_by_date(s).get(pd.Timestamp("2025-10-01"), float("nan")))   # gap month: no value
    # the month after the gap compares to the same month a year earlier, not 13 months back
    assert y.loc["2025-11-01"] == pytest.approx((s.loc["2025-11-01"] / s.loc["2024-11-01"] - 1) * 100)


def test_headline_is_blank_not_stale_when_yoy_cannot_be_computed():
    idx = pd.date_range("2024-01-01", "2026-10-01", freq="MS").drop(pd.Timestamp("2025-10-01"))
    s = pd.Series([100 + i for i in range(len(idx))], index=idx, dtype=float)
    ind = {"id": "CPIAUCSL", "name": "CPI", "frequency": "M", "units": "Index", "headline": "yoy_pct",
           "stale_days": 75, "z_flag": 2.0}
    m = compute_metrics(s, ind, 5)
    assert m["latest_date"] == "2026-10-01" and m["headline"] is None and m["headline_gap"] == "2025-10-01"
    flags = check_series(s, ind, m, None, pd.Timestamp("2026-11-17"))
    assert any(f["kind"] == "calc_gap" for f in flags)
