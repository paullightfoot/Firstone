"""
Oura Cloud API v2 — fetches daily sleep data.

Required env var: OURA_TOKEN
Get yours at: https://cloud.ouraring.com/personal-access-tokens
"""

import os
import requests
from datetime import date


def fetch_sleep(start_date: str, end_date: str) -> dict[str, dict]:
    """
    Returns a dict keyed by date string (YYYY-MM-DD) with sleep info:
      - sleep_score
      - sleep_hours  (total sleep in hours, 1 decimal)
      - sleep_efficiency (%)
    """
    token = os.environ.get("OURA_TOKEN")
    if not token:
        raise EnvironmentError("OURA_TOKEN not set")

    headers = {"Authorization": f"Bearer {token}"}
    url = "https://api.ouraring.com/v2/usercollection/daily_sleep"
    params = {"start_date": start_date, "end_date": end_date}

    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()

    result = {}
    for item in resp.json().get("data", []):
        day = item["day"]
        contributors = item.get("contributors", {})
        # total_sleep is in seconds
        total_seconds = contributors.get("total_sleep", 0) or 0
        sleep_hours = round(total_seconds / 3600, 1) if total_seconds else None

        result[day] = {
            "sleep_score": item.get("score"),
            "sleep_hours": sleep_hours,
            "sleep_efficiency": contributors.get("efficiency"),
        }

    return result
