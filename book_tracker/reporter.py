"""
Render the book research analysis as a clean HTML email and send via Gmail SMTP.

TODO: Update BOOK_TITLE, BOOK_SUBTITLE, and color scheme once topics are confirmed.
"""

import os
import smtplib
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "paul.lightfoot@gmail.com")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "paul.lightfoot@gmail.com")

BOOK_TITLE = "Food System Tracker"
BOOK_SUBTITLE = "Farmland · Subsidies · Organic · Health · Policy"

# Earthy/agrarian palette
COLOR_PRIMARY = "#3d2b1f"    # dark soil brown
COLOR_SECONDARY = "#5a7a3a"  # field green
COLOR_ACCENT = "#8b6914"     # wheat/amber


def _markdown_to_html(text: str) -> str:
    """Convert a subset of Markdown to HTML for email."""
    lines = text.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if stripped in ("---", "***", "___"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append('<hr style="border: none; border-top: 1px solid #e0d5c5; margin: 20px 0;">')
            continue

        if stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            heading_text = _inline_format(stripped[3:].strip())
            html_lines.append(f'<h2 style="color: {COLOR_PRIMARY}; border-bottom: 2px solid {COLOR_PRIMARY}; padding-bottom: 6px; margin-top: 28px;">{heading_text}</h2>')
            continue

        if stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            heading_text = _inline_format(stripped[4:].strip())
            html_lines.append(f'<h3 style="color: {COLOR_SECONDARY}; margin-top: 20px;">{heading_text}</h3>')
            continue

        if stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            heading_text = _inline_format(stripped[2:].strip())
            html_lines.append(f'<h1 style="color: {COLOR_PRIMARY};">{heading_text}</h1>')
            continue

        if stripped.startswith(("- ", "* ", "• ")):
            if not in_list:
                html_lines.append('<ul style="padding-left: 20px;">')
                in_list = True
            item_text = _inline_format(stripped[2:].strip())
            html_lines.append(f"<li>{item_text}</li>")
            continue

        if in_list and stripped:
            html_lines.append("</ul>")
            in_list = False

        if not stripped:
            html_lines.append("")
            continue

        html_lines.append(_inline_format(stripped))

    if in_list:
        html_lines.append("</ul>")

    result = []
    current_para = []

    def flush_para():
        if current_para:
            content = " ".join(current_para)
            if content.strip():
                result.append(f'<p style="line-height: 1.6; margin: 8px 0;">{content}</p>')
            current_para.clear()

    for line in html_lines:
        line_stripped = line.strip()
        if not line_stripped:
            flush_para()
        elif line_stripped.startswith("<") and line_stripped.endswith(">"):
            flush_para()
            result.append(line)
        else:
            current_para.append(line)

    flush_para()
    return "\n".join(result)


def _inline_format(text: str) -> str:
    """Apply inline markdown: **bold**, *italic*, `code`, [links](url)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r'<code style="background:#f4f0e8;padding:1px 4px;border-radius:3px;">\1</code>', text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        r'<a href="\2" style="color:#5a7a3a;">\1</a>',
        text,
    )
    text = re.sub(
        r'(?<!["\'>])(https?://[^\s<>"]+)',
        r'<a href="\1" style="color:#5a7a3a;">\1</a>',
        text,
    )
    return text


def render_report(report: dict, since: datetime) -> str:
    """Render the analysis report as a full HTML email."""
    period_start = report.get("period_start", since.strftime("%B %d, %Y"))
    period_end = report.get("period_end", datetime.now().strftime("%B %d, %Y"))

    part_a_html = _markdown_to_html(report.get("part_a", ""))
    part_b_html = _markdown_to_html(report.get("part_b", ""))
    part_c_html = _markdown_to_html(report.get("part_c", ""))

    primary_count = report.get("primary_item_count", 0)
    news_count = report.get("news_item_count", 0)
    research_count = report.get("research_item_count", 0)
    total_count = primary_count + news_count + research_count
    generated_at = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p PT")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{BOOK_TITLE} — Weekly Report</title>
</head>
<body style="font-family: Georgia, 'Times New Roman', serif; background-color: #f5f0e8; margin: 0; padding: 0;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f0e8;">
    <tr>
      <td align="center" style="padding: 30px 20px;">

        <table width="680" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.12);">

          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, {COLOR_PRIMARY} 0%, #6b4c35 100%); padding: 36px 40px; text-align: center;">
              <div style="font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #c8a882; margin-bottom: 10px;">Weekly Research Digest</div>
              <h1 style="color: #ffffff; margin: 0; font-size: 26px; font-weight: bold; letter-spacing: 1px;">📚 {BOOK_TITLE}</h1>
              <div style="color: #d4b896; margin-top: 10px; font-size: 14px;">{BOOK_SUBTITLE}</div>
              <div style="color: #c8a882; margin-top: 8px; font-size: 13px;">{period_start} – {period_end}</div>
            </td>
          </tr>

          <!-- Stats bar -->
          <tr>
            <td style="background-color: #faf5ec; padding: 12px 40px; border-bottom: 1px solid #e8dcc8;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="font-size: 12px; color: {COLOR_ACCENT};">
                    📊 Analyzed <strong>{total_count}</strong> items &nbsp;·&nbsp;
                    <strong>{primary_count}</strong> primary &nbsp;·&nbsp;
                    <strong>{news_count}</strong> news &nbsp;·&nbsp;
                    <strong>{research_count}</strong> research
                  </td>
                  <td align="right" style="font-size: 12px; color: #85929e;">
                    Generated {generated_at}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding: 40px;">

              <!-- Part A -->
              <div style="margin-bottom: 40px;">
                <div style="background-color: {COLOR_PRIMARY}; color: #ffffff; padding: 10px 16px; border-radius: 4px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; display: inline-block; margin-bottom: 20px;">
                  Part A — Current Developments
                </div>
                <div style="font-size: 15px; color: #2c3e50; line-height: 1.7;">
                  {part_a_html}
                </div>
              </div>

              <hr style="border: none; border-top: 2px solid #ede5d5; margin: 40px 0;">

              <!-- Part B -->
              <div style="margin-bottom: 40px;">
                <div style="background-color: {COLOR_SECONDARY}; color: #ffffff; padding: 10px 16px; border-radius: 4px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; display: inline-block; margin-bottom: 20px;">
                  Part B — Research &amp; Academic
                </div>
                <div style="font-size: 15px; color: #2c3e50; line-height: 1.7;">
                  {part_b_html}
                </div>
              </div>

              <hr style="border: none; border-top: 2px solid #ede5d5; margin: 40px 0;">

              <!-- Part C -->
              <div>
                <div style="background-color: {COLOR_ACCENT}; color: #ffffff; padding: 10px 16px; border-radius: 4px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; display: inline-block; margin-bottom: 20px;">
                  Part C — Broader Context &amp; Connections
                </div>
                <div style="font-size: 15px; color: #2c3e50; line-height: 1.7;">
                  {part_c_html}
                </div>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #faf5ec; border-top: 1px solid #e8dcc8; padding: 24px 40px; text-align: center;">
              <p style="font-size: 12px; color: #7f8c8d; margin: 0 0 8px 0;">
                This report was generated automatically by the Book Research Tracker.
              </p>
              <p style="font-size: 12px; color: #7f8c8d; margin: 0 0 8px 0;">
                Sources: USDA/ERS, EPA/RFS, EWG, Civil Eats, Food Politics, Modern Farmer, The Counter, Rodale Institute, Lancet, BMJ, Land Use Policy, and more.
              </p>
              <p style="font-size: 11px; color: #95a5a6; margin: 0;">
                Analysis powered by Claude (Anthropic) · Delivered weekly
              </p>
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""

    return html


def send_report(html: str, since: datetime) -> None:
    """Send the HTML report via Gmail SMTP."""
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_password:
        raise ValueError("GMAIL_APP_PASSWORD environment variable is not set.")

    gmail_password = gmail_password.replace(" ", "")

    sender = SENDER_EMAIL
    recipient = RECIPIENT_EMAIL
    subject = f"{BOOK_TITLE} — Weekly Report ({datetime.now().strftime('%B %d, %Y')})"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{BOOK_TITLE} <{sender}>"
    msg["To"] = recipient

    plain_text = (
        f"{BOOK_TITLE} — Weekly Report\n\n"
        "This report requires an HTML-capable email client.\n\n"
        "Please view in Gmail or another HTML email client."
    )
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html, "html"))

    print(f"Sending report to {recipient} via Gmail SMTP...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, gmail_password)
        smtp.sendmail(sender, [recipient], msg.as_string())
    print(f"Report sent successfully to {recipient}")


def save_report_to_file(html: str, since: datetime, path: str = None) -> str:
    """Save the HTML report to a file (for dry-run / debugging)."""
    if path is None:
        path = f"book_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report saved to: {path}")
    return path
