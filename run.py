#!/usr/bin/env python3
"""
ROC Tracker — Entry Point

Usage:
  python run.py                   # Start web UI + scheduler (default, port 5001)
  python run.py --scrape          # Run all scrapers now, then exit
  python run.py --standards       # Check all standards now, then exit
  python run.py --targeting       # Run sales targeting now, then exit
  python run.py --report          # Generate PDF + send email now, then exit
  python run.py --dry-run-report  # Generate PDF only, don't email
  python run.py --port 8080       # Use a different port

First-time setup:
  pip install -r requirements.txt
  python run.py                   # Creates roc_tracker.db automatically
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="ROC Tracker")
    parser.add_argument("--scrape", action="store_true", help="Run all scrapers and exit")
    parser.add_argument("--standards", action="store_true", help="Check standards and exit")
    parser.add_argument("--targeting", action="store_true", help="Run sales targeting and exit")
    parser.add_argument("--report", action="store_true", help="Generate + email report and exit")
    parser.add_argument("--dry-run-report", action="store_true", help="Generate PDF only (no email)")
    parser.add_argument("--port", type=int, default=5001, help="Port for web server (default: 5001)")
    parser.add_argument("--no-scheduler", action="store_true", help="Start web UI without scheduler")
    args = parser.parse_args()

    from app import create_app
    app = create_app()

    with app.app_context():
        from scrapers.standards import seed_standards_attributes
        seed_standards_attributes(app.app_context())

    # ── One-off commands ──────────────────────────────────────────────────────

    if args.scrape:
        logger.info("Running all scrapers…")
        with app.app_context():
            from run_scrapers import run_all_scrapers
            run_all_scrapers(app.app_context())
        logger.info("Done.")
        return

    if args.standards:
        logger.info("Checking standards…")
        from scrapers.standards import StandardsMonitor
        monitor = StandardsMonitor()
        changes = monitor.monitor_all(app.app_context())
        logger.info(f"Done. {len(changes)} change(s) detected.")
        return

    if args.targeting:
        logger.info("Running sales targeting…")
        with app.app_context():
            from sales_targeting import run_targeting
            targets = run_targeting()
            logger.info(f"Done. {len(targets) if targets else 0} targets created.")
        return

    if args.report or args.dry_run_report:
        from datetime import datetime, timedelta
        with app.app_context():
            from reports.pdf_generator import generate_report
            since = datetime.utcnow() - timedelta(days=7)
            pdf_path = generate_report(since=since)
            logger.info(f"PDF saved to: {pdf_path}")
            if args.report:
                from reports.email_sender import send_weekly_report
                success = send_weekly_report(pdf_path)
                logger.info("Email sent." if success else "Email failed.")
        return

    # ── Web server + scheduler ─────────────────────────────────────────────────

    if not args.no_scheduler:
        import scheduler
        scheduler.start(app)

    print()
    print("=" * 55)
    print("  ROC Tracker — Regenerative Organic Alliance")
    print("=" * 55)
    print(f"  Web UI:    http://localhost:{args.port}")
    print(f"  Scheduler: {'OFF (--no-scheduler)' if args.no_scheduler else 'ON (weekly, Monday 7 AM Pacific)'}")
    print(f"  Database:  roc_tracker.db")
    print()
    print("  First run? Go to Admin → Run Scraper to populate data.")
    print("=" * 55)
    print()

    app.run(debug=False, port=args.port, use_reloader=False)


if __name__ == "__main__":
    main()
