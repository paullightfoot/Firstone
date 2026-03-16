"""
ROC Tracker — Weekly Scheduler
Runs automatically when the Flask app is started.
Jobs:
  1. Weekly scrape of all registries (Monday 6:00 AM)
  2. Weekly standards check (Monday 6:30 AM)
  3. Weekly sales targeting (Monday 6:45 AM)
  4. Weekly PDF report + email (Monday 7:00 AM)
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config

logger = logging.getLogger(__name__)
_scheduler = None


def start(app):
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="US/Pacific")

    day = config.WEEKLY_REPORT_DAY       # "mon"
    hour = config.WEEKLY_REPORT_HOUR     # 7
    minute = config.WEEKLY_REPORT_MINUTE # 0

    # 1. Scrape all registries
    _scheduler.add_job(
        func=lambda: _run_scrape(app),
        trigger=CronTrigger(day_of_week=day, hour=hour - 1, minute=0),
        id="weekly_scrape",
        replace_existing=True,
    )

    # 2. Check standards
    _scheduler.add_job(
        func=lambda: _run_standards(app),
        trigger=CronTrigger(day_of_week=day, hour=hour - 1, minute=30),
        id="weekly_standards",
        replace_existing=True,
    )

    # 3. Run targeting
    _scheduler.add_job(
        func=lambda: _run_targeting(app),
        trigger=CronTrigger(day_of_week=day, hour=hour - 1, minute=45),
        id="weekly_targeting",
        replace_existing=True,
    )

    # 4. Generate PDF + send email
    _scheduler.add_job(
        func=lambda: _send_report(app),
        trigger=CronTrigger(day_of_week=day, hour=hour, minute=minute),
        id="weekly_email",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"[Scheduler] Started. Weekly jobs run every {day.capitalize()} at "
        f"~{hour - 1:02d}:00–{hour:02d}:00 Pacific."
    )


def stop():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped.")


def _run_scrape(app):
    logger.info("[Scheduler] Running weekly scrape…")
    with app.app_context():
        from run_scrapers import run_all_scrapers
        run_all_scrapers(app.app_context())


def _run_standards(app):
    logger.info("[Scheduler] Running standards check…")
    with app.app_context():
        from scrapers.standards import StandardsMonitor, seed_standards_attributes
        seed_standards_attributes(app.app_context())
        monitor = StandardsMonitor()
        return monitor.monitor_all(app.app_context())


def _run_targeting(app):
    logger.info("[Scheduler] Running sales targeting…")
    with app.app_context():
        from sales_targeting import run_targeting
        run_targeting()


def _send_report(app):
    logger.info("[Scheduler] Generating and sending weekly report…")
    with app.app_context():
        from reports.pdf_generator import generate_report
        from reports.email_sender import send_weekly_report
        since = datetime.utcnow() - timedelta(days=7)
        pdf_path = generate_report(since=since)

        # Get changes from this week for the email body
        from models import StandardsChange
        changes = (StandardsChange.query
                   .filter(StandardsChange.change_date >= since)
                   .all())
        changes_summary = [
            {"cert": chg.certification.name if chg.certification else "?",
             "synth_fert": chg.synthetic_fertilizer_changed,
             "synth_pest": chg.synthetic_pesticide_changed}
            for chg in changes
        ]
        send_weekly_report(pdf_path, changes_summary)
