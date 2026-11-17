# Handoff guide for future teams

## Weekly routine (10 minutes)

1. Open the dashboard. Check the status chips at the top.
2. Work through the **Review queue**: open each flagged series on FRED with "Check source", confirm the number, tick **Verified**. (Ticks are saved in your browser only; record anything important in the committee notes.)
3. Read **What changed**, then do the human part: what does it mean for the allocation and sector-weight recommendation?

## When something breaks

| Symptom | Likely cause | Fix |
|---|---|---|
| Red run in Actions, `fetch_failed` on every series | FRED key missing or expired | Re-add `FRED_API_KEY` secret |
| `fetch_failed` on one series | Series discontinued or renamed on FRED | Find the replacement ID, update `config/indicators.yaml` |
| `stale` on a monthly series | Release delayed (e.g., government shutdown) or `stale_days` too tight | Check the release calendar; adjust `stale_days` if needed |
| Dashboard says "agent has not run" | Scheduled workflows pause after 60 days without repo activity | Actions → Update macro data → Enable / Run workflow |
| Dashboard can't load data | `docs/data/latest.json` missing or Pages misconfigured | Run the workflow; check Settings → Pages |

## Start of each semester

- Add the new maintainers as repo collaborators; remove graduates.
- Confirm the watchlist with the incoming Macroeconomic Committee.
- Run `pytest -q` and one manual workflow run.

## Ideas for next semesters

- Release calendar (FRED `releases/dates`) so the dashboard shows what's coming this week.
- Store verifications as GitHub Issues instead of browser ticks, for an audit trail.
- Add yield-curve and real-rate charts.
