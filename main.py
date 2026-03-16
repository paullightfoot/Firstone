#!/usr/bin/env python3
"""
Mill Valley Tracker — Main Entry Point

Scrapes Mill Valley government sources and global urbanist publications,
analyzes content with Claude, and emails a weekly report.

Usage:
  python main.py                          # Run normally (7-day lookback)
  python main.py --days 365              # Initial run with 1-year lookback
  python main.py --dry-run               # Analyze and save HTML, don't email
  python main.py --save-html             # Save HTML report to file (and email)
  python main.py --days 30 --dry-run    # Test with 30 days, no email

Environment variables (required):
  ANTHROPIC_API_KEY    - Your Anthropic API key
  GMAIL_APP_PASSWORD   - Your Gmail app password (16-char code)

Optional environment variables:
  SENDER_EMAIL         - Gmail address to send FROM (default: paul.lightfoot@gmail.com)
  RECIPIENT_EMAIL      - Email address to send TO (default: paul.lightfoot@gmail.com)
  LOOKBACK_DAYS        - Override --days from env (useful in GitHub Actions)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta


def parse_args():
    parser = argparse.ArgumentParser(
        description="Mill Valley Housing & Transit Weekly Tracker"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back for content (default: 7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate report and save HTML, but do NOT send email",
    )
    parser.add_argument(
        "--save-html",
        action="store_true",
        help="Save HTML report to file (in addition to sending email)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path for saved HTML file (used with --dry-run or --save-html)",
    )
    return parser.parse_args()


def check_env():
    """Validate that required environment variables are set."""
    missing = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not os.environ.get("GMAIL_APP_PASSWORD"):
        missing.append("GMAIL_APP_PASSWORD")
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print()
        print("Set them before running:")
        for var in missing:
            print(f"  export {var}=your_value_here")
        sys.exit(1)


def main():
    args = parse_args()

    # Allow LOOKBACK_DAYS env var to override --days (useful in GitHub Actions)
    lookback_days = int(os.environ.get("LOOKBACK_DAYS", args.days))
    since = datetime.now() - timedelta(days=lookback_days)

    print("=" * 65)
    print("  Mill Valley Housing & Transit Weekly Tracker")
    print("=" * 65)
    print(f"  Period: {since.strftime('%Y-%m-%d')} → {datetime.now().strftime('%Y-%m-%d')}")
    print(f"  Lookback: {lookback_days} days")
    print(f"  Mode: {'DRY RUN (no email)' if args.dry_run else 'LIVE (will send email)'}")
    print("=" * 65)
    print()

    if not args.dry_run:
        check_env()
    else:
        # For dry run, only ANTHROPIC_API_KEY is required
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ERROR: ANTHROPIC_API_KEY is required even for dry runs.")
            sys.exit(1)

    # --- STEP 1: Scrape ---
    print("STEP 1: Scraping sources...")
    print()

    print("  [Mill Valley government sources]")
    from scrapers.mill_valley import scrape_mill_valley
    mv_gov_items = scrape_mill_valley(since)
    print(f"  → {len(mv_gov_items)} items found")
    print()

    print("  [Local news sources]")
    from scrapers.local_news import scrape_local_news
    local_news_items = scrape_local_news(since)
    print(f"  → {len(local_news_items)} items found")
    print()

    print("  [Global urbanist sources]")
    from scrapers.global_cities import scrape_global_cities
    global_items = scrape_global_cities(since)
    print(f"  → {len(global_items)} items found")
    print()

    # Combine Mill Valley items
    mv_items = mv_gov_items + local_news_items

    total_items = len(mv_items) + len(global_items)
    print(f"Total items to analyze: {total_items} ({len(mv_items)} MV + {len(global_items)} global)")
    print()

    # --- STEP 2: Analyze with Claude ---
    print("STEP 2: Analyzing content with Claude claude-opus-4-6...")
    print("-" * 65)

    from analyzer import analyze_content
    report = analyze_content(mv_items, global_items, since)

    print("-" * 65)
    print()

    # --- STEP 3: Render HTML ---
    print("STEP 3: Rendering HTML email...")
    from reporter import render_report, send_report, save_report_to_file
    html = render_report(report, since)
    print(f"  → HTML rendered ({len(html):,} characters)")
    print()

    # --- STEP 4: Send or save ---
    if args.dry_run or args.save_html:
        output_path = args.output or f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        save_report_to_file(html, since, output_path)

    if not args.dry_run:
        print("STEP 4: Sending email...")
        send_report(html, since)

    print()
    print("=" * 65)
    if args.dry_run:
        print("  DRY RUN COMPLETE — report saved, no email sent.")
    else:
        print("  COMPLETE — report sent to", os.environ.get("RECIPIENT_EMAIL", "paul.lightfoot@gmail.com"))
    print("=" * 65)


if __name__ == "__main__":
    main()
