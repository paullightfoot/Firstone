#!/usr/bin/env python3
"""
Book Research Tracker — Main Entry Point

Searches 60+ sources weekly for content relevant to "The American Farmland System,"
analyzes it with Claude, sends a digest email, and updates the research index.

Usage:
  python main.py                        # Run normally (7-day lookback)
  python main.py --days 365             # Initial run with 1-year lookback
  python main.py --dry-run              # Analyze and save HTML, don't email
  python main.py --days 30 --dry-run   # Test with 30 days, no email

Environment variables (required):
  ANTHROPIC_API_KEY    - Your Anthropic API key
  GMAIL_APP_PASSWORD   - Your Gmail app password (16-char code)

Optional environment variables:
  SENDER_EMAIL         - Gmail address to send FROM (default: paul.lightfoot@gmail.com)
  RECIPIENT_EMAIL      - Email address to send TO (default: paul.lightfoot@gmail.com)
  LOOKBACK_DAYS        - Override --days (useful in GitHub Actions)
  INDEX_PASSWORD       - Password for the HTML research index
  LISTENNOTES_API_KEY  - Listen Notes API key for podcast search (optional)
  BRAVE_SEARCH_API_KEY - Brave Search API key for web search (optional)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta


def parse_args():
    parser = argparse.ArgumentParser(
        description="The American Farmland System — Book Research Tracker"
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of days to look back (default: 7)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate report and save HTML, but do NOT send email",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Path for saved HTML email (used with --dry-run)",
    )
    return parser.parse_args()


def check_env(dry_run: bool):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is required.")
        sys.exit(1)
    if not dry_run and not os.environ.get("GMAIL_APP_PASSWORD"):
        print("ERROR: GMAIL_APP_PASSWORD is required for live runs.")
        print("Use --dry-run to skip sending email.")
        sys.exit(1)


def main():
    args = parse_args()
    lookback_days = int(os.environ.get("LOOKBACK_DAYS", args.days))
    since = datetime.now() - timedelta(days=lookback_days)

    print("=" * 65)
    print("  The American Farmland System — Book Research Tracker")
    print("=" * 65)
    print(f"  Period:   {since.strftime('%Y-%m-%d')} → {datetime.now().strftime('%Y-%m-%d')}")
    print(f"  Lookback: {lookback_days} days")
    print(f"  Mode:     {'DRY RUN (no email)' if args.dry_run else 'LIVE (will send email)'}")
    print("=" * 65)
    print()

    check_env(args.dry_run)

    # ── STEP 1: Scrape ──────────────────────────────────────────────────────
    print("STEP 1: Scraping sources...")
    print()

    print("  [News & journalism — 60+ RSS feeds]")
    from scrapers.news import scrape_news
    news_items = scrape_news(since)
    print(f"  → {len(news_items)} relevant items")
    print()

    print("  [Podcasts]")
    from scrapers.podcasts import scrape_podcasts
    podcast_items = scrape_podcasts(since)
    print(f"  → {len(podcast_items)} relevant episodes")
    print()

    print("  [Academic papers]")
    from scrapers.papers import scrape_papers
    paper_items = scrape_papers(since)
    print(f"  → {len(paper_items)} papers found")
    print()

    print("  [Web search]")
    from scrapers.web import scrape_web
    web_items = scrape_web(since)
    print(f"  → {len(web_items)} web results")
    print()

    all_raw = news_items + podcast_items + paper_items + web_items
    print(f"Total raw items: {len(all_raw)}")
    print()

    if not all_raw:
        print("No items found. Check source connectivity and try --days 30 for a larger window.")
        sys.exit(0)

    # ── STEP 2: Deduplicate against existing index ──────────────────────────
    print("STEP 2: Loading index and deduplicating...")
    from reporter import load_index
    index = load_index()
    existing_ids = {item["id"] for item in index.get("items", [])}

    import hashlib
    def make_id(item):
        return hashlib.sha256(item.get("url", item.get("title", "")).encode()).hexdigest()[:16]

    new_raw = [item for item in all_raw if make_id(item) not in existing_ids]
    print(f"  {len(all_raw)} total → {len(new_raw)} new (not yet indexed)")
    print()

    if not new_raw:
        print("No new items since last run. Nothing to do.")
        sys.exit(0)

    # ── STEP 3: Analyze with Claude ─────────────────────────────────────────
    print("STEP 3: Analyzing with Claude claude-opus-4-6...")
    print("-" * 65)
    from analyzer import analyze_items
    analyzed = analyze_items(new_raw)
    print("-" * 65)
    print()

    if not analyzed:
        print("No items scored ≥40 relevance. Nothing to report.")
        sys.exit(0)

    # ── STEP 4: Update index ─────────────────────────────────────────────────
    print("STEP 4: Updating research index...")
    from reporter import merge_new_items, save_index, generate_index_html, INDEX_HTML_PATH

    index, truly_new = merge_new_items(index, analyzed)
    save_index(index)
    print(f"  Index updated: {index['total_items']} total items")

    index_password = os.environ.get("INDEX_PASSWORD", "")
    index_html = generate_index_html(index, index_password)
    INDEX_HTML_PATH.parent.mkdir(exist_ok=True)
    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"  Index HTML regenerated: {INDEX_HTML_PATH}")
    print()

    # ── STEP 5: Render email ─────────────────────────────────────────────────
    print("STEP 5: Rendering email digest...")
    from reporter import render_email
    email_html = render_email(truly_new, index, since)
    print(f"  → {len(email_html):,} characters")
    print()

    # ── STEP 6: Send or save ─────────────────────────────────────────────────
    if args.dry_run:
        output_path = args.output or f"digest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        from reporter import save_email_to_file
        save_email_to_file(email_html, output_path)
    else:
        print("STEP 6: Sending email...")
        from reporter import send_email
        send_email(email_html, len(truly_new), since)

    print()
    print("=" * 65)
    if args.dry_run:
        print("  DRY RUN COMPLETE — index updated, email saved (not sent).")
    else:
        recipient = os.environ.get("RECIPIENT_EMAIL", "paul.lightfoot@gmail.com")
        print(f"  COMPLETE — digest sent to {recipient}")
        print(f"  {len(truly_new)} new items added to index ({index['total_items']} total)")
    print("=" * 65)


if __name__ == "__main__":
    main()
