"""Release calendar: when does new data come out for each tracked indicator?

The macro team named "checking when the data is released, what is released"
as the repetitive part of its week (interview, 08:21), and its weekly deck ends
with a slide on what is coming out next week (08:00). FRED publishes the
official release schedule for every series, so the agent reads it:

    series/release   -> which release a series belongs to (e.g. "Consumer Price Index")
    release/dates    -> that release's scheduled dates, including future ones

Daily series (Treasury yields) come out every business day, so they get one
line ("every business day, next ...") instead of a row per day.

A missing schedule is reported, never guessed: if FRED has no future date the
entry says so.
"""

from __future__ import annotations

import pandas as pd

from .fred import FredError, _get

HORIZON_DAYS = 45          # how far ahead to list releases
NEXT_WEEK_DAYS = 7         # what counts as "coming up next week"


def expected_period(release_date: pd.Timestamp, frequency: str) -> str:
    """Which reference period a release will most likely cover (label only)."""
    if frequency == "M":
        p = release_date.replace(day=1) - pd.offsets.MonthBegin(1)   # monthly data comes out the following month
        return p.strftime("%B %Y data")
    if frequency == "Q":
        q = (release_date - pd.offsets.QuarterBegin(1, startingMonth=1))
        return f"{q.year} Q{q.quarter} data"
    if frequency == "W":
        return "prior week's data"
    return "prior business day's data"


def _entries(ind: dict, release_name: str, dates: list[pd.Timestamp], today: pd.Timestamp, source: str) -> list[dict]:
    future = sorted(d for d in dates if today <= d <= today + pd.Timedelta(days=HORIZON_DAYS))
    base = {"series_id": ind["id"], "indicator": ind["name"], "release": release_name, "source": source}
    if not future:
        return [{**base, "date": None, "covers": None, "next_week": False,
                 "note": f"No scheduled release date published within {HORIZON_DAYS} days. Check the release calendar."}]
    if ind["frequency"] == "D":
        d = future[0]
        return [{**base, "date": d.strftime("%Y-%m-%d"), "covers": expected_period(d, "D"),
                 "next_week": (d - today).days < NEXT_WEEK_DAYS,
                 "note": "Published every business day; next date shown."}]
    return [{**base, "date": d.strftime("%Y-%m-%d"), "covers": expected_period(d, ind["frequency"]),
             "next_week": (d - today).days < NEXT_WEEK_DAYS, "note": ""} for d in future]


def live_calendar(indicators: list[dict], today: pd.Timestamp, session) -> tuple[list[dict], list[str]]:
    out, errors = [], []
    for ind in indicators:
        try:
            rel = _get("series/release", {"series_id": ind["id"]}, session)["releases"][0]
            data = _get("release/dates", {
                "release_id": rel["id"],
                "realtime_start": today.strftime("%Y-%m-%d"),
                "realtime_end": "9999-12-31",
                "include_release_dates_with_no_data": "true",
                "sort_order": "asc",
                "limit": 1000,
            }, session)
            dates = [pd.Timestamp(x["date"]) for x in data.get("release_dates", [])]
            src = f"https://fred.stlouisfed.org/releases/calendar?rid={rel['id']}"
            out += _entries(ind, rel["name"], dates, today, src)
        except (FredError, KeyError, IndexError) as e:
            errors.append(f"{ind['id']}: could not read the release calendar ({e}).")
    return _sorted(out), errors


def demo_calendar(indicators: list[dict], today: pd.Timestamp) -> tuple[list[dict], list[str]]:
    """Synthetic schedule built from the demo publication lags (labeled DEMO upstream)."""
    from .demo import release_date
    out = []
    names = {"M": "Demo monthly release", "D": "Demo daily release", "W": "Demo weekly release", "Q": "Demo quarterly release"}
    for ind in indicators:
        refs = pd.date_range(today - pd.Timedelta(days=200), today + pd.Timedelta(days=HORIZON_DAYS),
                             freq={"D": "B", "W": "W-SAT", "M": "MS", "Q": "QS"}[ind["frequency"]])
        dates = [release_date(ind["id"], ind["frequency"], d) for d in refs]
        out += _entries(ind, names[ind["frequency"]], dates, today, "demo")
    return _sorted(out), []


def _sorted(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda e: (e["date"] is None, e["date"] or "", e["series_id"]))


def calendar_lines(entries: list[dict]) -> list[str]:
    """Plain-English 'coming up next week' lines for the status file."""
    nxt = [e for e in entries if e["next_week"]]
    if not nxt:
        return ["Coming up in the next 7 days: no scheduled releases for the tracked indicators."]
    lines = ["Coming up in the next 7 days:"]
    for e in nxt:
        day = pd.Timestamp(e["date"]).strftime("%a %b %-d")
        extra = " (then every business day)" if e["note"].startswith("Published every") else ""
        lines.append(f"  {day}: {e['indicator']} ({e['release']}), {e['covers']}{extra}")
    return lines
