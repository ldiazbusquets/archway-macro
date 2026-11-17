"""Run the agent once.

    python -m agent.run            # live: needs FRED_API_KEY
    python -m agent.run --demo     # offline synthetic data, labeled DEMO

Writes to <output_dir> (default docs/data):
    latest.json     everything the dashboard shows
    state.json      memory between runs (last dates, recent values for revision checks)
    run_log.jsonl   one line per run, for the audit trail

Exit code 0 = clean run, 2 = at least one error flag (GitHub marks the run red
and emails the maintainers, so problems are never silent).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from . import __version__
from .compute import compute_metrics
from .demo import apply_scenario, demo_series
from .summarize import SUFFIX, ai_digest, rule_note
from .validate import check_series, flag, snapshot

HEADLINE_LABEL = {"level": "Level", "diff": "Change", **{k: v.strip() for k, v in SUFFIX.items()}}


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/indicators.yaml")
    ap.add_argument("--demo", action="store_true", help="use synthetic data (no API key needed)")
    ap.add_argument("--scenario", action="store_true", help="demo only: inject a revision, a spike, a missing value and a failed fetch")
    ap.add_argument("--out", help="override output directory")
    ap.add_argument("--today", help="pretend today is YYYY-MM-DD (testing)")
    args = ap.parse_args(argv)

    cfg = yaml.safe_load(Path(args.config).read_text())
    st = cfg["settings"]
    out = Path(args.out or st["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    today = pd.Timestamp(args.today) if args.today else pd.Timestamp.today().normalize()
    state = load_json(out / "state.json", {})
    mode = "demo" if args.demo else "live"
    prev_file = load_json(out / "latest.json", {})
    # Never carry demo numbers into a live run (or the reverse) as "last good data".
    previous = {r["id"]: r for r in prev_file.get("indicators", [])} if prev_file.get("mode") == mode else {}
    if prev_file.get("mode") and prev_file.get("mode") != mode:
        state = {}

    session = None
    if not args.demo:
        import requests
        from .fred import fetch_series
        session = requests.Session()

    rows, new_state = [], {}
    for ind in cfg["indicators"]:
        sid = ind["id"]
        row = {"id": sid, "name": ind["name"], "group": ind["group"], "frequency": ind["frequency"],
               "units": ind["units"], "headline_type": ind["headline"],
               "headline_label": HEADLINE_LABEL[ind["headline"]],
               "source_url": f"https://fred.stlouisfed.org/series/{sid}"}
        try:
            if args.demo:
                s, meta = demo_series(sid, ind["frequency"], st["history_start"], today), {"last_updated": None}
                if args.scenario:
                    s = apply_scenario(sid, s)
            else:
                s, meta = fetch_series(sid, st["history_start"], session)
            m = compute_metrics(s, ind, st["z_window_years"])
            row.update(m)
            row["fred_last_updated"] = meta.get("last_updated")
            row["flags"] = check_series(s, ind, m, state.get(sid), today)
            row["note"] = rule_note(ind, m)
            new_state[sid] = snapshot(s)
        except Exception as e:
            # Fail visibly: keep the last good numbers but mark them clearly.
            prev = previous.get(sid, {})
            row.update({k: v for k, v in prev.items() if k not in ("flags", "note")})
            row["flags"] = [flag("fetch_failed", "error",
                                 f"Could not refresh this run ({e}). Showing last good data from {prev.get('latest_date', 'n/a')}.")]
            row["note"] = prev.get("note", f"{ind['name']}: no data available yet.")
            if sid in state:
                new_state[sid] = state[sid]
        rows.append(row)

    n_err = sum(f["severity"] == "error" for r in rows for f in r["flags"])
    n_rev = sum(f["severity"] == "review" for r in rows for f in r["flags"])
    n_new = sum(f["kind"] == "new_release" for r in rows for f in r["flags"])
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    latest = {
        "agent_version": __version__,
        "mode": mode,
        "run_at": run_at,
        "as_of": today.strftime("%Y-%m-%d"),
        "summary": {"indicators": len(rows), "errors": n_err, "to_review": n_rev, "new_releases": n_new},
        "ai_digest": ai_digest(rows) if not args.demo else None,
        "indicators": rows,
    }
    (out / "latest.json").write_text(json.dumps(latest, indent=1))
    (out / "state.json").write_text(json.dumps(new_state, indent=1))
    with open(out / "run_log.jsonl", "a") as f:
        f.write(json.dumps({"run_at": run_at, "mode": mode, **latest["summary"],
                            "flags": [f"{r['id']}:{x['kind']}" for r in rows for x in r["flags"] if x["severity"] != "info"]}) + "\n")

    msg = f"[{mode}] {len(rows)} indicators · {n_new} new releases · {n_rev} to review · {n_err} errors"
    print(msg)
    for r in rows:
        for x in r["flags"]:
            if x["severity"] != "info":
                print(f"  {x['severity'].upper():6} {r['id']:9} {x['message']}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"### Macro agent run\n{msg}\n\n" + "\n".join(
                f"- **{x['severity']}** `{r['id']}` {x['message']}" for r in rows for x in r["flags"] if x["severity"] != "info") + "\n")
    return 2 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
