"""
Render the analysis report as a clean HTML email and send via Gmail SMTP.
"""

import os
import smtplib
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "paul.lightfoot@gmail.com")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "paul.lightfoot@gmail.com")


def _markdown_to_html(text: str) -> str:
    """
    Convert a subset of Markdown to HTML for email:
    - ## headings -> <h2>
    - ### headings -> <h3>
    - **bold** -> <strong>
    - *italic* -> <em>
    - --- -> <hr>
    - Blank lines -> paragraph breaks
    - Bullet lists
    """
    lines = text.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append('<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">')
            continue

        # H2 heading
        if stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            heading_text = stripped[3:].strip()
            heading_text = _inline_format(heading_text)
            html_lines.append(f'<h2 style="color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 6px; margin-top: 28px;">{heading_text}</h2>')
            continue

        # H3 heading
        if stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            heading_text = stripped[4:].strip()
            heading_text = _inline_format(heading_text)
            html_lines.append(f'<h3 style="color: #2e86c1; margin-top: 20px;">{heading_text}</h3>')
            continue

        # H1 heading
        if stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            heading_text = stripped[2:].strip()
            heading_text = _inline_format(heading_text)
            html_lines.append(f'<h1 style="color: #0d3349;">{heading_text}</h1>')
            continue

        # Bullet list items
        if stripped.startswith(("- ", "* ", "• ")):
            if not in_list:
                html_lines.append('<ul style="padding-left: 20px;">')
                in_list = True
            item_text = _inline_format(stripped[2:].strip())
            html_lines.append(f"<li>{item_text}</li>")
            continue

        # Close list if we hit a non-list line
        if in_list and stripped:
            html_lines.append("</ul>")
            in_list = False

        # Blank line
        if not stripped:
            html_lines.append("")
            continue

        # Regular paragraph text
        html_lines.append(_inline_format(stripped))

    if in_list:
        html_lines.append("</ul>")

    # Wrap consecutive non-tag lines in <p>
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
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic (but not inside bold)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r'<code style="background:#f4f4f4;padding:1px 4px;border-radius:3px;">\1</code>', text)
    # Markdown links [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        r'<a href="\2" style="color:#2980b9;">\1</a>',
        text,
    )
    # Plain URLs
    text = re.sub(
        r'(?<!["\'>])(https?://[^\s<>"]+)',
        r'<a href="\1" style="color:#2980b9;">\1</a>',
        text,
    )
    return text


def render_report(report: dict, since: datetime) -> str:
    """Render the analysis report as a full HTML email."""
    period_start = report.get("period_start", since.strftime("%B %d, %Y"))
    period_end = report.get("period_end", datetime.now().strftime("%B %d, %Y"))
    mv_section_html = _markdown_to_html(report.get("mill_valley_section", ""))
    global_section_html = _markdown_to_html(report.get("global_section", ""))

    mv_count = report.get("mv_item_count", 0)
    global_count = report.get("global_item_count", 0)
    generated_at = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p PT")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mill Valley Tracker — Weekly Report</title>
</head>
<body style="font-family: Georgia, 'Times New Roman', serif; background-color: #f5f5f0; margin: 0; padding: 0;">

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f0;">
    <tr>
      <td align="center" style="padding: 30px 20px;">

        <!-- Email container -->
        <table width="680" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #0d3349 0%, #1a5276 100%); padding: 36px 40px; text-align: center;">
              <div style="font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #7fb3d3; margin-bottom: 10px;">Weekly Report</div>
              <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: bold; letter-spacing: 1px;">🏘️ Mill Valley Tracker</h1>
              <div style="color: #aed6f1; margin-top: 10px; font-size: 14px;">Housing Density &amp; Public Transportation</div>
              <div style="color: #7fb3d3; margin-top: 8px; font-size: 13px;">{period_start} – {period_end}</div>
            </td>
          </tr>

          <!-- Stats bar -->
          <tr>
            <td style="background-color: #eaf2ff; padding: 12px 40px; border-bottom: 1px solid #d6eaf8;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="font-size: 12px; color: #2e86c1;">
                    📊 Analyzed <strong>{mv_count}</strong> Mill Valley items &nbsp;·&nbsp;
                    <strong>{global_count}</strong> global items
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
                <div style="background-color: #0d3349; color: #ffffff; padding: 10px 16px; border-radius: 4px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; display: inline-block; margin-bottom: 20px;">
                  Part A — Mill Valley Update
                </div>
                <div style="font-size: 15px; color: #2c3e50; line-height: 1.7;">
                  {mv_section_html}
                </div>
              </div>

              <!-- Divider -->
              <hr style="border: none; border-top: 2px solid #e8e8e8; margin: 40px 0;">

              <!-- Part B -->
              <div>
                <div style="background-color: #1a7a4a; color: #ffffff; padding: 10px 16px; border-radius: 4px; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; display: inline-block; margin-bottom: 20px;">
                  Part B — Ideas from the World
                </div>
                <div style="font-size: 15px; color: #2c3e50; line-height: 1.7;">
                  {global_section_html}
                </div>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8f9fa; border-top: 1px solid #e8e8e8; padding: 24px 40px; text-align: center;">
              <p style="font-size: 12px; color: #7f8c8d; margin: 0 0 8px 0;">
                This report was generated automatically by the Mill Valley Tracker.
              </p>
              <p style="font-size: 12px; color: #7f8c8d; margin: 0 0 8px 0;">
                Sources: City of Mill Valley, Marin Transit, SMART Train, Marin IJ, Patch, and global urbanist publications.
              </p>
              <p style="font-size: 11px; color: #95a5a6; margin: 0;">
                Analysis powered by Claude (Anthropic) · Delivered every Friday
              </p>
            </td>
          </tr>

        </table>
        <!-- End email container -->

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

    # Strip spaces from the app password (Google shows it with spaces)
    gmail_password = gmail_password.replace(" ", "")

    sender = SENDER_EMAIL
    recipient = RECIPIENT_EMAIL
    subject = f"Mill Valley Tracker — Weekly Report ({datetime.now().strftime('%B %d, %Y')})"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Mill Valley Tracker <{sender}>"
    msg["To"] = recipient

    # Plain text fallback
    plain_text = (
        "Mill Valley Tracker — Weekly Report\n\n"
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
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        path = filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report saved to: {path}")
    return path
