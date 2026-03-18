"""
Insight Timer — parses a CSV data export from the app.

How to export from Insight Timer:
  1. Open the app → Profile → Settings (gear icon)
  2. Tap "Account" → "Download your data"
  3. You'll receive an email with a link to download a ZIP
  4. Extract it and find the file named "sessions.csv" (or similar)
  5. Pass that path via INSIGHT_TIMER_CSV env var, or the --insight-csv flag

Expected CSV columns (Insight Timer's export format):
  date, duration_seconds, activity_type, ...
  (The parser is flexible and looks for common column name variants.)
"""

import csv
import os
from collections import defaultdict


# Column name candidates for each field (case-insensitive)
_DATE_COLS = ["date", "start_date", "session_date", "day"]
_DURATION_COLS = ["duration_seconds", "duration", "total_duration", "length_seconds"]
_TYPE_COLS = ["activity_type", "type", "session_type", "category"]


def fetch_meditation(csv_path: str, start_date: str, end_date: str) -> dict[str, dict]:
    """
    Returns a dict keyed by date string (YYYY-MM-DD):
      - meditated       (True/False)
      - meditation_mins (total minutes across all sessions that day)
    """
    if not csv_path:
        csv_path = os.environ.get("INSIGHT_TIMER_CSV", "")
    if not csv_path:
        print("  [insight] INSIGHT_TIMER_CSV not set — skipping meditation data.")
        return {}
    if not os.path.isfile(csv_path):
        print(f"  [insight] File not found: {csv_path} — skipping.")
        return {}

    daily = defaultdict(lambda: {"meditated": False, "meditation_mins": 0})

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = {h.lower().strip(): h for h in (reader.fieldnames or [])}

        date_col = _find_col(headers, _DATE_COLS)
        duration_col = _find_col(headers, _DURATION_COLS)

        if not date_col:
            print("  [insight] Could not find a date column in CSV. Check the file.")
            return {}

        for row in reader:
            raw_date = row.get(date_col, "").strip()
            if not raw_date:
                continue
            day = _parse_date(raw_date)
            if not day or not (start_date <= day <= end_date):
                continue

            daily[day]["meditated"] = True

            if duration_col:
                try:
                    secs = float(row.get(duration_col, 0) or 0)
                    daily[day]["meditation_mins"] += round(secs / 60, 1)
                except (ValueError, TypeError):
                    pass

    # Round totals
    for v in daily.values():
        v["meditation_mins"] = round(v["meditation_mins"], 1)

    return dict(daily)


def _find_col(headers_lower: dict, candidates: list[str]):
    """Return the original column name matching one of the candidates."""
    for c in candidates:
        if c in headers_lower:
            return headers_lower[c]
    return None


def _parse_date(raw: str) -> str | None:
    """Try to normalise a date string to YYYY-MM-DD."""
    from dateutil import parser as dp
    try:
        return dp.parse(raw).strftime("%Y-%m-%d")
    except Exception:
        return None
