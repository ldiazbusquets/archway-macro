"""Plain-English notes.

1. Rule-based notes (always on): one factual sentence per indicator, built from
   the computed numbers. No AI, so no risk of an invented figure.
2. AI digest (optional, off unless ANTHROPIC_API_KEY is set): an LLM drafts a
   short "what changed this week" paragraph from the computed JSON only.
   It is labeled as a draft that a student must review, and it is told not to
   forecast or interpret economic significance. That stays human.
"""

from __future__ import annotations

import json
import os

import pandas as pd
import requests

SUFFIX = {"yoy_pct": "% y/y", "mom_pct": "% m/m", "qoq_saar": "% q/q annualized"}


def period_label(date: str, frequency: str) -> str:
    d = pd.Timestamp(date)
    if frequency == "M":
        return d.strftime("%b %Y")
    if frequency == "Q":
        return f"{d.year} Q{d.quarter}"
    if frequency == "W":
        return "the week ending " + d.strftime("%b %-d, %Y")
    return d.strftime("%b %-d, %Y")


def fmt_headline(v: float | None, ind: dict, signed: bool = False) -> str:
    if v is None:
        return "n/a"
    h = ind["headline"]
    if h in SUFFIX:
        return f"{v:+.1f}{SUFFIX[h]}" if signed else f"{v:.1f}{SUFFIX[h]}"
    if h == "diff" and ind["units"] == "Thousands":
        return f"{v:+,.0f}K"
    if ind["units"] in ("%", "pp"):
        return f"{v:+.2f} pp" if signed else f"{v:.2f}%" if ind["units"] == "%" else f"{v:.2f} pp"
    nd = 0 if abs(v) >= 1000 else 1
    return f"{v:+,.{nd}f}" if signed else f"{v:,.{nd}f}"


def rule_note(ind: dict, m: dict) -> str:
    when = period_label(m["latest_date"], ind["frequency"])
    if m["headline"] is None:
        return f"{ind['name']}: not enough history to compute the headline figure."
    prep = "in" if ind["frequency"] in ("M", "Q") else "for" if ind["frequency"] == "W" else "on"
    if ind["headline"] == "diff" and ind["units"] == "Thousands":
        s = f"{ind['name']} changed by {fmt_headline(m['headline'], ind)} {prep} {when}"
    else:
        s = f"{ind['name']} was {fmt_headline(m['headline'], ind)} {prep} {when}"
    ch = m.get("headline_change")
    if ch is not None and m.get("headline_prior") is not None:
        if abs(ch) < 1e-9:
            s += ", unchanged from the prior reading"
        else:
            word = "up" if ch > 0 else "down"
            if ind["headline"] == "diff" and ind["units"] == "Thousands":
                s += f" (prior period: {fmt_headline(m['headline_prior'], ind)})"
            elif ind["headline"] in SUFFIX:
                s += f", {word} {abs(ch):.1f} pp from {m['headline_prior']:.1f}"
            elif ind["units"] in ("%", "pp"):
                s += f", {word} {abs(ch)*100:.0f} bp"
            else:
                nd = 0 if abs(ch) >= 100 else 1
                s += f", {word} {abs(ch):,.{nd}f}"
    return s + "."


DIGEST_PROMPT = """You are drafting a short factual update for the student Macroeconomic Committee of a university investment fund.
Using ONLY the JSON below, write 4-6 sentences on what changed since the prior readings, leading with the largest or most unusual moves and any data-quality flags.
Rules: do not forecast, do not give investment advice, do not explain economic significance or causes (students do that). Do not state any number that is not in the JSON. Plain prose, no bullets.

JSON:
"""


def ai_digest(rows: list[dict]) -> dict | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
    compact = [{k: r[k] for k in ("name", "latest_date", "headline_label", "headline", "headline_prior", "z_move")} |
               {"flags": [f["message"] for f in r["flags"] if f["severity"] != "info"]} for r in rows]
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 400,
                  "messages": [{"role": "user", "content": DIGEST_PROMPT + json.dumps(compact)}]},
            timeout=60,
        )
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        return {"text": text.strip(), "model": model, "status": "AI draft: a student must review before sharing"}
    except Exception as e:  # never let the optional digest break the run
        return {"text": "", "model": model, "status": f"AI digest failed: {e}"}
