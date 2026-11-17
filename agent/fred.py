"""FRED API client. The API key comes from the FRED_API_KEY environment variable
(a GitHub Actions secret owned by the fund, never a student's personal key)."""

from __future__ import annotations

import os
import time

import pandas as pd
import requests

BASE = "https://api.stlouisfed.org/fred"


class FredError(RuntimeError):
    pass


def _get(path: str, params: dict, session: requests.Session, retries: int = 3) -> dict:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise FredError("FRED_API_KEY is not set. Add it as a repository secret, or run with --demo.")
    params = {**params, "api_key": key, "file_type": "json"}
    last_err = None
    for attempt in range(retries):
        try:
            r = session.get(f"{BASE}/{path}", params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            # 429 = rate limited, 5xx = FRED side; both are worth a retry
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        except requests.RequestException as e:
            last_err = str(e)
        time.sleep(2 ** attempt)
    raise FredError(f"{path} failed: {last_err}")


def fetch_series(series_id: str, start: str, session: requests.Session | None = None) -> tuple[pd.Series, dict]:
    """Return (observations, metadata).

    Observations keep FRED's missing values ('.') as NaN so the validator can
    flag them instead of silently dropping them.
    """
    session = session or requests.Session()
    obs = _get("series/observations", {"series_id": series_id, "observation_start": start}, session)
    meta = _get("series", {"series_id": series_id}, session)["seriess"][0]

    rows = obs.get("observations", [])
    if not rows:
        raise FredError(f"{series_id}: no observations returned")
    s = pd.Series(
        [float(o["value"]) if o["value"] not in (".", "") else float("nan") for o in rows],
        index=pd.to_datetime([o["date"] for o in rows]),
        name=series_id,
    )
    return s, {
        "title": meta.get("title"),
        "last_updated": meta.get("last_updated"),
        "units": meta.get("units"),
        "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
    }
