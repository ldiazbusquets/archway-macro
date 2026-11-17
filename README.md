# Archway Macro-Monitoring Agent

FIN 414 · Archway Investment Fund · Macroeconomic Committee

An agent that **retrieves** the fund's macro indicators from FRED, **detects** new releases, **computes** changes, **flags** anything a student needs to check, and **publishes** a dashboard. Choosing indicators, verifying flags and interpreting what the numbers mean stay with students.

```
FRED API ─► fetch ─► detect release ─► compute ─► validate & flag ─► docs/data/latest.json ─► dashboard (GitHub Pages)
                                                                                         └─► Review queue ─► students verify & interpret
```

## Quick start

```bash
pip install -r requirements.txt

# Offline demo (synthetic data, labeled DEMO everywhere)
python -m agent.run --demo --today 2026-11-03
python -m agent.run --demo --scenario --today 2026-11-17   # injects a revision, spike, missing value, failed fetch

# Live
export FRED_API_KEY=...        # free key: https://fred.stlouisfed.org/docs/api/api_key.html
python -m agent.run

# View the dashboard
cd docs && python -m http.server 8000   # open http://localhost:8000
```

Tests (offline): `pytest -q`

## Repository layout

| Path | What it is | Who changes it |
|---|---|---|
| `config/indicators.yaml` | The watchlist: series, transforms, flag thresholds | **Students** (Macroeconomic Committee) |
| `agent/fred.py` | FRED API client with retries | Maintainers |
| `agent/compute.py` | y/y, m/m, q/q annualized, changes, z-scores. Deterministic, no AI | Maintainers |
| `agent/validate.py` | Flags: missing value, stale, unusual move, revision, new release | Maintainers |
| `agent/summarize.py` | Rule-based notes; optional AI digest (off without a key) | Maintainers |
| `agent/run.py` | Orchestrates one run, writes outputs, sets exit code | Maintainers |
| `agent/demo.py` | Synthetic data for demos and tests | Maintainers |
| `docs/index.html` | Dashboard (static, no build step) | Maintainers |
| `docs/data/` | Agent output: `latest.json`, `state.json`, `run_log.jsonl` | **The agent only** |
| `.github/workflows/` | Scheduled runs and tests | Maintainers |

## Flags

| Flag | Severity | Meaning | What a student does |
|---|---|---|---|
| `fetch_failed` | error | FRED request failed; last good data is shown | Check the Actions log; re-run |
| `missing_value` | error | FRED returned "." for the latest date | Check the series on FRED |
| `stale` | error | No new observation in longer than expected | Check the release calendar |
| `unusual_move` | review | Latest move is beyond the z-score threshold | Verify against the source before discussing |
| `revision` | review | An already-published value changed | Note the revision; update any saved analysis |
| `new_release` | info | A new observation arrived | Nothing; it shows in "What changed" |

Any **error** makes the run exit with code 2, so the GitHub Actions run turns red and maintainers get an email. The dashboard also warns if the agent hasn't run in 3 days. Nothing fails silently.

## Deploying (one time, fund-owned account)

1. Create the repo under a **fund or course GitHub organization**, not a personal account.
2. Settings → Secrets and variables → Actions → add `FRED_API_KEY` (registered to the fund's email). Optional: `ANTHROPIC_API_KEY` for the AI digest.
3. Settings → Pages → Deploy from branch → `main` / `/docs`.
4. Actions → "Update macro data" → **Run workflow** once. After that it runs every weekday at 14:17 and 22:17 UTC.
5. Delete the demo data in `docs/data/` before the first live run (or just let the live run overwrite it).

## Changing the watchlist

Edit `config/indicators.yaml`, open a pull request, and have a Macroeconomic Committee lead approve it. Find series IDs at fred.stlouisfed.org (the ID is in the URL). Run `python -m agent.run` locally to check it before merging.

## Design principles (from the project brief)

- **Reliability:** retries, explicit error flags, red runs, stale-data banner.
- **Safety & control:** read-only public data; the only write access is to this repo's `docs/data/`. No trading systems.
- **Reproducibility:** runs in GitHub Actions, not on a laptop. Same input → same numbers.
- **Maintainability:** plain Python, one config file, tests, this README and `HANDOFF.md`.
- **Cost:** FRED is free; GitHub Actions and Pages are free for public repos. The AI digest is optional.
