# Verification report

Generated 2026-11-23 01:01 UTC by `verify/verify_fred.py`, which does not use the agent's code. Source of truth: FRED public graph CSV (`fredgraph.csv`), a different endpoint from the API the agent calls.

## 1. Source comparison (2 dates per indicator)

| Indicator | Date | Agent CSV | FRED | Result |
|---|---|---|---|---|
| DGS10 | 2026-11-19 | 5.04 | 5.04 | PASS |
| DGS10 | 2025-11-19 | 4.13 | 4.13 | PASS |
| CPIAUCSL | 2026-10-01 | 337.476 | 337.476 | PASS |
| CPIAUCSL | 2025-09-01 | 324.245 | 324.245 | PASS |
| CPILFESL | 2026-10-01 | 339.9 | 339.9 | PASS |
| CPILFESL | 2025-09-01 | 330.418 | 330.418 | PASS |

## 2. Hand calculation

| Indicator | Date | Formula | By hand (from FRED) | Agent CSV | Result |
|---|---|---|---|---|---|
| DGS10 | 2026-11-19 | 5.04 − 5.07  [vs 2026-11-18] | -0.0300 | -0.0300 | PASS |
| CPIAUCSL | 2026-10-01 | y/y needs 2025-10-01 | FRED has no 2025-10-01 value | blank | PASS |
| CPIAUCSL | 2026-09-01 | (336.298 / 324.245 − 1) × 100  [vs 2025-09-01] | 3.7173 | 3.7172 | PASS |
| CPILFESL | 2026-10-01 | y/y needs 2025-10-01 | FRED has no 2025-10-01 value | blank | PASS |
| CPILFESL | 2026-09-01 | (338.896 / 330.418 − 1) × 100  [vs 2025-09-01] | 2.5658 | 2.5658 | PASS |

## 3. Run twice

- Second run changed a CSV: **no**
- Files with duplicate dates: **none**
- Result: **PASS**

Status file after the second run:

```
Run at 2026-11-23T01:01:21+00:00 (live)
[live] 3 indicators · 0 rows added · 2 to review · 0 errors
No new data for any indicator since the last run.
DGS10: no new data since the last run (latest 2026-11-19).
CPIAUCSL: no new data since the last run (latest 2026-10-01).
CPILFESL: no new data since the last run (latest 2026-10-01).
```

## 4. Invalid series ID

- Exit code: **2** (non-zero expected)
- Saved CSVs unchanged: **yes**
- Result: **PASS**

Status file:

```
Run at 2026-11-23T01:01:23+00:00 (live)
[live] 3 indicators · 0 rows added · 2 to review · 1 errors
No new data for any indicator since the last run.
NOTAREALSERIES123: ERROR, could not refresh (series/observations failed: HTTP 400: {"error_code":400,"error_message":"Bad Request.  The series does not exist."}). Saved CSV left unchanged.
CPIAUCSL: no new data since the last run (latest 2026-10-01).
CPILFESL: no new data since the last run (latest 2026-10-01).
```

## Overall

**ALL CHECKS PASSED**
