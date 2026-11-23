# Run guide (1 page)

For anyone on the team, or a future Archway student, who needs to run the agent. No coding needed.

## What it does

Pulls 3 indicators from FRED, adds any new observations to a CSV per indicator, calculates the changes, and puts it **all on one Excel workbook** (`macro_update.xlsx`) with a plain-English status. That workbook is the "getting it all onto one sheet" step the macro team called repetitive (interview, 08:21). **Students still make the charts for the deck and decide what the numbers mean.**

| Indicator | FRED ID | Saved calculation |
|---|---|---|
| Risk-free rate: 10-year Treasury | DGS10 | change from prior day (pp) |
| Inflation: CPI (headline) | CPIAUCSL | year-over-year % change |
| Inflation: core CPI | CPILFESL | year-over-year % change |

Chosen from the macro team interview: Treasuries / risk-free rate (updated weekly) and inflation, "both core and regular". **To confirm with Archway:** which Treasury maturity is their risk-free rate, CPI or PCE, and which calculations they show. Edit `config/indicators.yaml` if any change.

## Run it (GitHub, recommended)

1. Open the repo → **Actions** → **Update macro data** → **Run workflow** → **Run workflow**.
2. Wait about 1 minute. Green check = done. Red X = something needs a look (step 4).
3. Read the result:
   - `docs/data/status.txt`: one line per indicator, e.g. *"UNRATE: 1 new observation(s) added (2026-10-01)"* or *"no new data since the last run"*.
   - `docs/data/macro_update.xlsx`: everything on one workbook ("This week" summary + one sheet per indicator). Download it from GitHub and open in Excel.
   - `docs/data/csv/<ID>.csv`: the saved history per indicator.
   - The dashboard: https://ldiazbusquets.github.io/archway-macro/
4. If the run is red: open the run → **Run agent** step. The message names the indicator and the problem. The saved CSVs are never changed by a failed fetch.

## Check it (Assignment 3 evidence)

**Actions** → **Verify against FRED** → **Run workflow**. It writes `verification/REPORT.md`, which checks:

1. **Source comparison:** 2 dates per indicator, matched against FRED.
2. **Hand calculation:** the latest calculated value, redone from FRED's raw numbers.
3. **Run twice:** the second run adds nothing and creates no duplicate dates.
4. **Invalid series ID:** the error is reported and saved data stays untouched.

It uses a different FRED endpoint from the agent and none of the agent's code, so it's an independent check.

## Run it on a laptop (optional)

```bash
pip install -r requirements.txt
export FRED_API_KEY=your_key          # Windows PowerShell: $env:FRED_API_KEY="your_key"
python -m agent.run                   # live run, writes docs/data/
python -m agent.run --demo            # practice run with fake data, writes demo_output/
pytest -q                             # offline tests
```

Never put the API key in a file, a notebook or a commit. On GitHub it lives in **Settings → Secrets and variables → Actions → FRED_API_KEY**.

## What the flags mean

| Flag | Meaning | What to do |
|---|---|---|
| **Error:** fetch failed | FRED didn't respond or the ID is wrong | Check the ID on fred.stlouisfed.org; rerun |
| **Error:** missing value | FRED shows "." for the newest date | Check the series page; usually fills in a day later |
| **Error:** stale | No new data for longer than expected | Check the release calendar (e.g., a government shutdown) |
| **Review:** unusual move | Latest change is far outside the last 5 years' range | Confirm on FRED before discussing it |
| **Review:** revision | FRED changed a value we already saved | Note it; the CSV keeps the original, so update any analysis by hand |
| **Review:** calc gap | A calculation can't be done because FRED is missing a value (e.g. no Oct 2025 CPI after the 2025 shutdown) | Left blank on purpose; agree with the committee how to report that month |
