"""
ROC Tracker — Email Sender (Gmail SMTP)
"""
import smtplib
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

import config

logger = logging.getLogger(__name__)


def send_weekly_report(pdf_path: str, changes_summary: list = None):
    """
    Send the weekly PDF report via Gmail SMTP.
    changes_summary: list of dicts from standards monitor (optional).
    """
    if not config.GMAIL_APP_PASSWORD:
        logger.error("[Email] GMAIL_APP_PASSWORD not set — cannot send email.")
        return False

    subject = f"ROC Tracker Weekly Report — {datetime.now().strftime('%B %d, %Y')}"

    # Build plain-text body
    body_lines = [
        "Hi Paul,",
        "",
        "Your weekly ROC Tracker report is attached.",
        "",
        "HIGHLIGHTS THIS WEEK:",
    ]

    if changes_summary:
        body_lines.append(f"  • {len(changes_summary)} certification standard change(s) detected:")
        for chg in changes_summary:
            flags = []
            if chg.get("synth_fert"):
                flags.append("synthetic fertilizer language changed")
            if chg.get("synth_pest"):
                flags.append("synthetic pesticide language changed")
            flag_str = " | ".join(flags) if flags else "content change"
            body_lines.append(f"    - {chg['cert']}: {flag_str}")
    else:
        body_lines.append("  • No certification standards changes this week.")

    body_lines += [
        "",
        "See the attached PDF for full details including:",
        "  • ROC certified brands, farms, and organizations",
        "  • Other regenerative certification lists",
        "  • Standards comparison table",
        "  • Updated sales targets",
        "",
        "— ROC Tracker (automated)",
    ]

    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg["From"] = config.SENDER_EMAIL
    msg["To"] = ", ".join(config.RECIPIENT_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Attach PDF
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = os.path.basename(pdf_path)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)
    else:
        logger.warning(f"[Email] PDF not found at {pdf_path} — sending without attachment.")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.SENDER_EMAIL, config.GMAIL_APP_PASSWORD)
            server.sendmail(config.SENDER_EMAIL, config.RECIPIENT_EMAILS, msg.as_string())
        logger.info(f"[Email] Report sent to {config.RECIPIENT_EMAILS}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("[Email] Gmail authentication failed. Check GMAIL_APP_PASSWORD.")
        return False
    except Exception as e:
        logger.error(f"[Email] Failed to send: {e}")
        return False
