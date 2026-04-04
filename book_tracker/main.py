#!/usr/bin/env python3
"""
Book Research Tracker — Main Entry Point

Scrapes primary sources (government/policy), news outlets, and academic/research
sources, analyzes content with Claude, and emails a weekly research digest.

Usage:
  python book_tracker/main.py                      # Run normally (7-day lookback)
  python book_tracker/main.py --days 365           # Initial run with 1-year lookback
  python book_tracker/main.py --dry-run            # Analyze and save HTML, don't email
  python book_tracker/main.py --save-html          # Save HTML report (and email)
  python book_tracker/main.py --days 30 --dry-run  # Test with 30 days, no email

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

# Ensure imports work when run from repo root
sys.path.insert(0, os.path.dirname(__file__))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Book Research Tracker — Weekly Digest"
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
        for var in missing:
            print(f"  export {var}=your_value_here")
        sys.exit(1)


def main():
    args = parse_args()

    lookback_days = int(os.environ.get("LOOKBACK_DAYS", args.days))
    since = datetime.now() - timedelta(days=lookback_days)

    print("=" * 65)
    print("  Book Research Tracker — Weekly Digest")
    print("=" * 65)
    print(f"  Period: {since.strftime('%Y-%m-%d')} → {datetime.now().strftime('%Y-%m-%d')}")
    print(f"  Lookback: {lookback_days} days")
    print(f"  Mode: {'DRY RUN (no email)' if args.dry_run else 'LIVE (will send email)'}")
    print("=" * 65)
    print()

    if not args.dry_run:
        check_env()
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ERROR: ANTHROPIC_API_KEY is required even for dry runs.")
            sys.exit(1)

    # --- STEP 1: Scrape ---
    print("STEP 1: Scraping sources...")
    print()

    print("  [Primary / government sources]")
    from scrapers.primary_sources import scrape_primary_sources
    primary_items = scrape_primary_sources(since)
    print(f"  → {len(primary_items)} items found")
    print()

    print("  [News sources]")
    from scrapers.news_sources import scrape_news_sources
    news_items = scrape_news_sources(since)
    print(f"  → {len(news_items)} items found")
    print()

    print("  [Research & academic sources]")
    from scrapers.research_sources import scrape_research_sources
    research_items = scrape_research_sources(since)
    print(f"  → {len(research_items)} items found")
    print()

    total_items = len(primary_items) + len(news_items) + len(research_items)
    print(f"Total items to analyze: {total_items} "
          f"({len(primary_items)} primary + {len(news_items)} news + {len(research_items)} research)")
    print()

    # --- STEP 2: Analyze with Claude ---
    print("STEP 2: Analyzing content with Claude claude-opus-4-6...")
    print("-" * 65)

    from analyzer import analyze_content
    report = analyze_content(primary_items, news_items, research_items, since)

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
        output_path = args.output or f"book_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
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
