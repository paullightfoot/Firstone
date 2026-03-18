"""
Wyze Scale — fetches weight records via the unofficial wyze-sdk.

Required env vars:
  WYZE_EMAIL     your Wyze account email
  WYZE_PASSWORD  your Wyze account password

Note: wyze-sdk is unofficial and reverse-engineered. It may break if
Wyze changes their internal API. Install with: pip install wyze-sdk
"""

import os


def fetch_weight(start_date: str, end_date: str) -> dict[str, dict]:
    """
    Returns a dict keyed by date string (YYYY-MM-DD) with weight info:
      - weight_lbs
    """
    try:
        from wyze_sdk import Client
        from wyze_sdk.errors import WyzeApiError
    except ImportError:
        raise ImportError(
            "wyze-sdk is not installed. Run: pip install wyze-sdk"
        )

    email = os.environ.get("WYZE_EMAIL")
    password = os.environ.get("WYZE_PASSWORD")
    if not email or not password:
        raise EnvironmentError("WYZE_EMAIL and WYZE_PASSWORD must be set")

    client = Client(email=email, password=password)

    # Retrieve all scales from the account
    scales = client.scales.list()
    if not scales:
        print("  [wyze] No scale devices found on this account.")
        return {}

    # Use the first scale found
    scale = scales[0]
    print(f"  [wyze] Using scale: {scale.nickname or scale.mac}")

    records = client.scales.get_records(
        device_mac=scale.mac,
        start_date=start_date,
        end_date=end_date,
    )

    result = {}
    for rec in records:
        # rec.measure_ts is a Unix timestamp in ms
        rec_date = _ts_to_date(rec.measure_ts)
        if start_date <= rec_date <= end_date:
            weight_kg = rec.weight  # wyze returns kg
            result[rec_date] = {
                "weight_lbs": round(weight_kg * 2.20462, 1) if weight_kg else None,
            }

    return result


def _ts_to_date(ts_ms) -> str:
    """Convert a millisecond Unix timestamp to YYYY-MM-DD."""
    from datetime import datetime, timezone
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")
