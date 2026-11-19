# Archway Macro-Monitoring Agent

FIN 414 · Archway Investment Fund · Macroeconomic Committee

An agent that **retrieves** 3 macro indicators from FRED, **saves** new observations to a CSV per indicator (never duplicating a date), **computes** the changes Archway uses, **flags** anything a student needs to check, and **reports** a plain-English status, including "no new data". Choosing indicators, verifying flags and interpreting the numbers stay with students.

**Start here:** [RUN_GUIDE.md](RUN_GUIDE.md) (how to run and check it) · [verification/REPORT.md](verification/REPORT.md) (latest independent check against FRED)

```
FRED API ─► retrieve ─► save new rows (csv/<ID>.csv) ─► calculate ─► validate & flag ─► status.txt + dashboard
                                                                                     └─► students verify & interpret
```

**Scope:** the course brief allows 1–3 indicators that Archway already monitors. The current three (CPI y/y, unemployment rate, 10Y–2Y yield curve) are placeholders from the Macroeconomic Committee's published reports, to confirm with Archway.

## Quick start

```bash
pip install -r requirements.txt

# Offline demo (synthetic data, labeled DEMO, written to demo_output/)
python -m agent.run --demo --today 2026-11-03
python -m agent.run --demo --scenario --today 2026-11-17   # injects a revision, a spike and a missing value

# Live
export FRED_API_KEY=...        # free key: https://fred.stlouisfed.org/docs/api/api_key.html
python -m agent.run

# View the dashboard
cd docs && python -m http.server 8000   # open http://localhost:8000
```

Tests (offline): `pytest -q`. Independent check against FRED: `python verify/verify_fred.py` (or the **Verify against FRED** workflow).

## Repository layout

| Path | What it is | Who changes it |
|---|---|---|
| `config/indicators.yaml` | The watchlist: series, calculations, flag thresholds | **Students** (Macroeconomic Committee) |
| `agent/fred.py` | FRED API client with retries | Maintainers |
| `agent/history.py` | Per-indicator CSV: append new dates only, never rewrite saved rows | Maintainers |
| `agent/compute.py` | Dashboard numbers: y/y, changes, trend, z-scores. Deterministic, no AI | Maintainers |
| `agent/validate.py` | Flags: missing value, stale, unusual move, revision, new release | Maintainers |
| `agent/summarize.py` | Rule-based notes; optional AI digest (off without a key) | Maintainers |
| `agent/run.py` | Orchestrates one run, writes outputs, sets exit code | Maintainers |
| `agent/demo.py` | Synthetic data for demos and tests | Maintainers |
| `docs/index.html` | Dashboard (static, no build step) | Maintainers |
| `docs/data/` | Agent output: `csv/<ID>.csv`, `status.txt`, `latest.json`, `state.json`, `run_log.jsonl` | **The agent only** |
| `verify/verify_fred.py` | Independent checker (no agent code): source comparison, hand calc, run twice, invalid ID | Maintainers |
| `verification/REPORT.md` | Latest checker output, for Assignment 3 | **The checker only** |
| `.github/workflows/` | Manual data run, verification run, tests on every push | Maintainers |

## Flags

| Flag | Severity | Meaning | What a student does |
|---|---|---|---|
| `fetch_failed` | error | FRED request failed; last good data is shown | Check the Actions log; re-run |
| `missing_value` | error | FRED returned "." for the latest date | Check the series on FRED |
| `stale` | error | No new observation in longer than expected | Check the release calendar |
| `unusual_move` | review | Latest move is beyond the z-score threshold | Verify against the source before discussing |
| `revision` | review | An already-published value changed | Note the revision; update any saved analysis |
| `calc_gap` | review | y/y can't be computed because the year-earlier value is missing at FRED | Left blank (never estimated); decide how to report it |
| `new_release` | info | A new observation arrived | Nothing; it shows in "What changed" |

Any **error** makes the run exit with code 2, so the GitHub Actions run turns red and maintainers get an email. A failed fetch never changes a saved CSV; the last good values stay visible and marked. The dashboard warns if the agent hasn't run in a week. Nothing fails silently.

## Deploying (one time, fund-owned account)

1. Create the repo under a **fund or course GitHub organization**, not a personal account.
2. Settings → Secrets and variables → Actions → add `FRED_API_KEY` (registered to the fund's email). Optional: `ANTHROPIC_API_KEY` for the AI digest.
3. Settings → Pages → Deploy from branch → `main` / `/docs`.
4. Actions → "Update macro data" → **Run workflow** whenever you want fresh data (manual by design; see the comment in the workflow file to add a schedule).
5. Demo runs write to `demo_output/` (ignored by git), so demo values never reach `docs/data/`.

## Changing the watchlist

Edit `config/indicators.yaml`, open a pull request, and have a Macroeconomic Committee lead approve it. Find series IDs at fred.stlouisfed.org (the ID is in the URL). Run `python -m agent.run` locally to check it before merging.

## Design principles (from the project brief)

- **Reliability:** retries, explicit error flags, red runs, stale-data banner.
- **Safety & control:** read-only public data; the only write access is to this repo's `docs/data/`. No trading systems.
- **Reproducibility:** runs in GitHub Actions (or `python -m agent.run` locally), not tied to one laptop. Same input → same numbers.
- **Maintainability:** plain Python, one config file, tests, this README and `HANDOFF.md`.
- **Cost:** FRED is free; GitHub Actions and Pages are free for public repos. The AI digest is optional.
