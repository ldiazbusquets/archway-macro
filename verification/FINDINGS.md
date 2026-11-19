# Findings log

Problems found while verifying the agent, and what was done about them. The course brief asks teams to describe failed tests accurately; this is that record.

## 1. Year-over-year compared the wrong month after a data gap (found 2026-11-19, fixed)

**How it was found:** the first live run of `verify/verify_fred.py`. Its hand-calculation row for CPIAUCSL showed the October 2026 y/y change being compared with **September 2025**, not October 2025.

**Cause:** FRED has no October 2025 value for CPIAUCSL or UNRATE. The 2025 federal government shutdown cancelled those releases. The agent calculated y/y as "12 rows back", which skips over the gap and lands 13 months back. The checker made the same mistake because it also counted rows, so the first report wrongly showed PASS. Two pieces of code agreeing doesn't prove either is right.

**Effect:** the saved October 2026 CPI y/y (4.08%) was a 13-month change, overstated compared with a true 12-month change. Every month from November 2025 onward was also measured against the wrong base month.

**Fix:**
- y/y is now matched **by date** (the same month one year earlier), in the agent and in the checker.
- When the year-earlier value doesn't exist, y/y is left **blank** and the run raises a `calc_gap` review flag. It is never estimated. For October 2026 this means CPI y/y is blank until the committee decides how to report it.
- The dashboard headline now always belongs to the latest date. Before the fix it would have shown September's y/y under an October label.
- Saved CSVs were rebuilt once from FRED. This is the one exception to "never rewrite saved rows", and it is logged here.
- New tests: `test_yoy_matches_by_date_across_a_data_gap`, `test_headline_is_blank_not_stale_when_yoy_cannot_be_computed`.

**Still open, for Archway:** how does the committee report October 2025 and October 2026 y/y? Options: leave blank, use BLS's published 12-month figure if one exists, or note the gap in the meeting. The agent will not guess.

## 2. Related: "change from prior month" spans two months after the gap

For UNRATE, the November 2025 `change` is measured against September 2025, because October 2025 doesn't exist. The CSV now records this in the `prior_date` column, so it's visible instead of implied.
