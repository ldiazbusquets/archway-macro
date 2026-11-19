# Verification report

Generated 2026-11-19 15:41 UTC by `verify/verify_fred.py`, which does not use the agent's code. Source of truth: FRED public graph CSV (`fredgraph.csv`), a different endpoint from the API the agent calls.

## 1. Source comparison (2 dates per indicator)

| Indicator | Date | Agent CSV | FRED | Result |
|---|---|---|---|---|
| CPIAUCSL | 2026-10-01 | 337.476 | 337.476 | PASS |
| CPIAUCSL | 2025-09-01 | 324.245 | 324.245 | PASS |
| UNRATE | 2026-10-01 | 4.1 | 4.1 | PASS |
| UNRATE | 2025-09-01 | 4.4 | 4.4 | PASS |
| T10Y2Y | 2026-11-18 | 0.27 | 0.27 | PASS |
| T10Y2Y | 2025-11-18 | 0.54 | 0.54 | PASS |

## 2. Hand calculation

| Indicator | Date | Formula | By hand (from FRED) | Agent CSV | Result |
|---|---|---|---|---|---|
| CPIAUCSL | 2026-10-01 | y/y needs 2025-10-01 | FRED has no 2025-10-01 value | blank | PASS |
| UNRATE | 2026-10-01 | 4.1 − 4.2  [vs 2026-09-01] | -0.1000 | -0.1000 | PASS |
| T10Y2Y | 2026-11-18 | 0.27 − 0.3  [vs 2026-11-17] | -0.0300 | -0.0300 | PASS |

## 3. Run twice

- Second run changed a CSV: **no**
- Files with duplicate dates: **none**
- Result: **PASS**

Status file after the second run:

```
Run at 2026-11-19T15:41:04+00:00 (live)
[live] 3 indicators · 0 rows added · 1 to review · 0 errors
No new data for any indicator since the last run.
CPIAUCSL: no new data since the last run (latest 2026-10-01).
UNRATE: no new data since the last run (latest 2026-10-01).
T10Y2Y: no new data since the last run (latest 2026-11-18).
```

## 4. Invalid series ID

- Exit code: **2** (non-zero expected)
- Saved CSVs unchanged: **yes**
- Result: **PASS**

Status file:

```
Run at 2026-11-19T15:41:05+00:00 (live)
[live] 3 indicators · 0 rows added · 0 to review · 1 errors
No new data for any indicator since the last run.
NOTAREALSERIES123: ERROR, could not refresh (series/observations failed: HTTP 400: {"error_code":400,"error_message":"Bad Request.  The series does not exist."}). Saved CSV left unchanged.
UNRATE: no new data since the last run (latest 2026-10-01).
T10Y2Y: no new data since the last run (latest 2026-11-18).
```

## Overall

**ALL CHECKS PASSED**
