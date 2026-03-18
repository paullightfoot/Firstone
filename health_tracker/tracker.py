#!/usr/bin/env python3
"""
Health Tracking Dashboard
=========================
Pulls data from Oura (sleep), Wyze Scale (weight), and Insight Timer
(meditation) and writes a unified daily CSV.

Usage:
    python -m health_tracker.tracker [OPTIONS]

Options:
    --days N            How many days back to fetch (default: 30)
    --start YYYY-MM-DD  Start date (overrides --days)
    --end   YYYY-MM-DD  End date (default: today)
    --out FILE          Output CSV path (default: health_log.csv)
    --insight-csv FILE  Path to Insight Timer sessions CSV export

Environment variables (put in a .env file, then: source .env):
    OURA_TOKEN          Oura personal access token
    WYZE_EMAIL          Wyze account email
    WYZE_PASSWORD       Wyze account password
    INSIGHT_TIMER_CSV   Path to Insight Timer CSV export file
"""

import argparse
import csv
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()

from health_tracker import oura, wyze_scale, insight_timer


CSV_COLUMNS = [
    "date",
    "meditated",
    "meditation_mins",
    "weight_lbs",
    "sleep_score",
    "sleep_hours",
    "sleep_efficiency",
]


def date_range(start: str, end: str) -> list[str]:
    """Return list of YYYY-MM-DD strings from start to end inclusive."""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    return [(s + timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]


def run(start_date: str, end_date: str, out_path: str, insight_csv: str):
    print(f"Fetching health data from {start_date} to {end_date}...\n")

    # --- Oura ---
    sleep_data = {}
    try:
        print("[1/3] Fetching Oura sleep data...")
        sleep_data = oura.fetch_sleep(start_date, end_date)
        print(f"      Got {len(sleep_data)} days of sleep data.")
    except EnvironmentError as e:
        print(f"      SKIPPED: {e}")
    except Exception as e:
        print(f"      ERROR: {e}")

    # --- Wyze ---
    weight_data = {}
    try:
        print("[2/3] Fetching Wyze Scale weight data...")
        weight_data = wyze_scale.fetch_weight(start_date, end_date)
        print(f"      Got {len(weight_data)} days of weight data.")
    except EnvironmentError as e:
        print(f"      SKIPPED: {e}")
    except ImportError as e:
        print(f"      SKIPPED: {e}")
    except Exception as e:
        print(f"      ERROR: {e}")

    # --- Insight Timer ---
    meditation_data = {}
    try:
        print("[3/3] Reading Insight Timer meditation data...")
        meditation_data = insight_timer.fetch_meditation(insight_csv, start_date, end_date)
        print(f"      Got {len(meditation_data)} days of meditation data.")
    except Exception as e:
        print(f"      ERROR: {e}")

    # --- Merge ---
    print(f"\nWriting CSV to: {out_path}")
    days = date_range(start_date, end_date)
    rows_written = 0

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for day in days:
            m = meditation_data.get(day, {})
            w = weight_data.get(day, {})
            s = sleep_data.get(day, {})

            row = {
                "date": day,
                "meditated": "Yes" if m.get("meditated") else ("No" if meditation_data else ""),
                "meditation_mins": m.get("meditation_mins", ""),
                "weight_lbs": w.get("weight_lbs", ""),
                "sleep_score": s.get("sleep_score", ""),
                "sleep_hours": s.get("sleep_hours", ""),
                "sleep_efficiency": s.get("sleep_efficiency", ""),
            }
            writer.writerow(row)
            rows_written += 1

    print(f"Done. {rows_written} rows written to {out_path}")
    print("\nTip: Open health_log.csv in Excel or Google Sheets for a clean table view.")


def main():
    parser = argparse.ArgumentParser(description="Health Tracking Dashboard")
    parser.add_argument("--days", type=int, default=30, help="Days back from today (default: 30)")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--out", default="health_log.csv", help="Output CSV path")
    parser.add_argument("--insight-csv", default="", help="Path to Insight Timer sessions CSV")
    args = parser.parse_args()

    end_date = args.end or date.today().isoformat()
    if args.start:
        start_date = args.start
    else:
        start_date = (date.today() - timedelta(days=args.days)).isoformat()

    run(start_date, end_date, args.out, args.insight_csv)


if __name__ == "__main__":
    main()
