"""The independent checker must pass on correct data and catch a wrong value."""

import importlib

from agent.demo import demo_series
from agent.run import main


def _setup(tmp_path, monkeypatch):
    out = tmp_path / "data"
    main(["--demo", "--out", str(out), "--today", "2026-11-17"])
    v = importlib.import_module("verify.verify_fred")
    monkeypatch.setattr(v, "DATA", out)
    monkeypatch.setattr(v, "REPORT", tmp_path / "REPORT.md")
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    freq = {"CPIAUCSL": "M", "UNRATE": "M", "T10Y2Y": "D"}
    def fake_graph(sid):
        s = demo_series(sid, freq[sid], "2000-01-01", "2026-11-17").dropna()
        return {d.strftime("%Y-%m-%d"): float(x) for d, x in s.items()}
    monkeypatch.setattr(v, "fred_graph", fake_graph)
    return v, out


def test_checker_passes_on_correct_data(tmp_path, monkeypatch):
    v, _ = _setup(tmp_path, monkeypatch)
    assert v.main() == 0
    report = (tmp_path / "REPORT.md").read_text()
    assert "ALL CHECKS PASSED" in report and "FAIL |" not in report


def test_checker_catches_a_wrong_saved_value(tmp_path, monkeypatch):
    v, out = _setup(tmp_path, monkeypatch)
    p = out / "csv" / "UNRATE.csv"
    lines = p.read_text().splitlines()
    parts = lines[-1].split(",")
    parts[2] = "9.99"                                  # corrupt the latest saved value
    lines[-1] = ",".join(parts)
    p.write_text("\n".join(lines) + "\n")
    assert v.main() == 1
    assert "SOME CHECKS FAILED" in (tmp_path / "REPORT.md").read_text()
