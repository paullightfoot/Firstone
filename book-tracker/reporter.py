"""
Generate the weekly email digest and update the master research index.

Email: HTML digest via Gmail SMTP (same pattern as Mill Valley tracker).
Index: master_index.json (accumulated) + index.html (browsable, password-gated).
"""

import os
import json
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "paul.lightfoot@gmail.com")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "paul.lightfoot@gmail.com")
INDEX_DIR = Path(__file__).parent / "index"
INDEX_JSON_PATH = INDEX_DIR / "master_index.json"
INDEX_HTML_PATH = INDEX_DIR / "index.html"

STANCE_EMOJI = {"SUPPORTS": "✓", "CHALLENGES": "✗", "NEUTRAL": "○"}
STANCE_COLOR = {"SUPPORTS": "#1a7a4a", "CHALLENGES": "#c0392b", "NEUTRAL": "#7f8c8d"}
TYPE_EMOJI = {"article": "📰", "podcast": "🎙️", "paper": "📄", "web": "🌐"}


# ---------------------------------------------------------------------------
# Index persistence
# ---------------------------------------------------------------------------

def load_index() -> dict:
    """Load existing index or return empty structure."""
    if INDEX_JSON_PATH.exists():
        try:
            with open(INDEX_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_updated": "", "total_items": 0, "items": []}


def save_index(index: dict) -> None:
    INDEX_DIR.mkdir(exist_ok=True)
    with open(INDEX_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def merge_new_items(index: dict, new_items: list[dict]) -> tuple[dict, list[dict]]:
    """Add new items to index, deduplicating by ID. Returns (updated_index, truly_new_items)."""
    existing_ids = {item["id"] for item in index.get("items", [])}
    truly_new = [item for item in new_items if item["id"] not in existing_ids]

    if truly_new:
        index["items"] = truly_new + index.get("items", [])
        index["total_items"] = len(index["items"])
        index["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    return index, truly_new


# ---------------------------------------------------------------------------
# HTML index generation
# ---------------------------------------------------------------------------

def generate_index_html(index: dict, index_password: str = "") -> str:
    """Generate a self-contained, filterable HTML index file."""
    items_json = json.dumps(index.get("items", []), ensure_ascii=False)
    total = index.get("total_items", 0)
    last_updated = index.get("last_updated", "")

    password_js = ""
    password_gate_html = ""
    if index_password:
        password_js = f"""
const INDEX_PASSWORD = "{index_password}";
function checkPassword() {{
    const stored = localStorage.getItem('bookTrackerAuth');
    if (stored === INDEX_PASSWORD) return true;
    const entered = prompt('Enter password to access the research index:');
    if (entered === INDEX_PASSWORD) {{
        localStorage.setItem('bookTrackerAuth', entered);
        return true;
    }}
    document.body.innerHTML = '<div style="text-align:center;padding:100px;font-family:Georgia,serif;"><h2>Access Denied</h2><p>Reload to try again.</p></div>';
    return false;
}}
"""
        password_gate_html = "if (!checkPassword()) { /* blocked */ } else {"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The American Farmland System — Research Index</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Georgia, serif; background: #f5f5f0; color: #2c3e50; }}
  .header {{ background: linear-gradient(135deg, #1a3a1a 0%, #2d6a2d 100%); color: white; padding: 32px 40px; }}
  .header h1 {{ font-size: 26px; margin-bottom: 6px; }}
  .header .sub {{ color: #a8d5a8; font-size: 14px; }}
  .stats-bar {{ background: #e8f5e9; border-bottom: 1px solid #c8e6c9; padding: 12px 40px; font-size: 13px; color: #2e7d32; }}
  .controls {{ background: white; padding: 20px 40px; border-bottom: 1px solid #e0e0e0; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.08); }}
  .controls input, .controls select {{ padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; font-family: Georgia, serif; }}
  .controls input {{ width: 260px; }}
  .controls label {{ font-size: 13px; color: #555; }}
  .results-count {{ font-size: 13px; color: #888; margin-left: auto; }}
  .items {{ padding: 24px 40px; max-width: 1100px; margin: 0 auto; }}
  .item {{ background: white; border-radius: 6px; padding: 18px 22px; margin-bottom: 14px; border-left: 4px solid #ccc; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  .item.SUPPORTS {{ border-left-color: #1a7a4a; }}
  .item.CHALLENGES {{ border-left-color: #c0392b; }}
  .item.NEUTRAL {{ border-left-color: #95a5a6; }}
  .item-header {{ display: flex; align-items: flex-start; gap: 12px; margin-bottom: 8px; }}
  .stance-badge {{ font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 3px; white-space: nowrap; flex-shrink: 0; }}
  .stance-badge.SUPPORTS {{ background: #e8f5e9; color: #1a7a4a; }}
  .stance-badge.CHALLENGES {{ background: #fdecea; color: #c0392b; }}
  .stance-badge.NEUTRAL {{ background: #f5f5f5; color: #7f8c8d; }}
  .item-title {{ font-size: 15px; font-weight: bold; color: #1a3a1a; text-decoration: none; flex: 1; }}
  .item-title:hover {{ color: #2d6a2d; text-decoration: underline; }}
  .item-meta {{ font-size: 12px; color: #888; margin-bottom: 8px; }}
  .item-summary {{ font-size: 14px; line-height: 1.6; color: #444; }}
  .item-chapters {{ margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }}
  .chapter-tag {{ font-size: 11px; background: #f0f4f8; color: #2c5282; padding: 2px 7px; border-radius: 10px; }}
  .fact-check {{ margin-top: 8px; background: #fff8e1; border: 1px solid #ffc107; border-radius: 4px; padding: 6px 10px; font-size: 12px; color: #7b5e00; }}
  .score-bar {{ display: inline-block; width: 40px; height: 6px; background: #e0e0e0; border-radius: 3px; vertical-align: middle; margin-right: 4px; overflow: hidden; }}
  .score-fill {{ height: 100%; background: #2d6a2d; border-radius: 3px; }}
  .no-results {{ text-align: center; padding: 60px; color: #888; font-size: 16px; }}
  @media (max-width: 600px) {{ .controls {{ padding: 12px 16px; }} .items {{ padding: 12px 16px; }} .header {{ padding: 20px 16px; }} }}
</style>
</head>
<body>

<div class="header">
  <h1>The American Farmland System</h1>
  <div class="sub">Research Index &nbsp;·&nbsp; {total} items &nbsp;·&nbsp; Last updated: {last_updated}</div>
</div>

<div class="stats-bar" id="statsBar">Loading...</div>

<div class="controls">
  <input type="text" id="searchBox" placeholder="Search titles, sources, summaries..." oninput="filterItems()">
  <select id="stanceFilter" onchange="filterItems()">
    <option value="">All stances</option>
    <option value="SUPPORTS">✓ Supports argument</option>
    <option value="CHALLENGES">✗ Challenges argument</option>
    <option value="NEUTRAL">○ Neutral</option>
  </select>
  <select id="typeFilter" onchange="filterItems()">
    <option value="">All content types</option>
    <option value="article">📰 Articles</option>
    <option value="podcast">🎙️ Podcasts</option>
    <option value="paper">📄 Papers</option>
  </select>
  <select id="chapterFilter" onchange="filterItems()">
    <option value="">All chapters</option>
  </select>
  <select id="sortOrder" onchange="filterItems()">
    <option value="score">Sort: Relevance</option>
    <option value="date">Sort: Newest first</option>
    <option value="date_asc">Sort: Oldest first</option>
  </select>
  <span class="results-count" id="resultsCount"></span>
</div>

<div class="items" id="itemsContainer"></div>

<script>
{password_js}

const ALL_ITEMS = {items_json};

// Populate chapter filter
const chapterSet = new Set();
ALL_ITEMS.forEach(item => (item.chapters || []).forEach(ch => chapterSet.add(ch)));
const chapterOrder = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX","XXI","XXII","XXIII","XXIV","XXV","XXVI","XXVII","XXVIII","XXIX","XXX","XXXI","XXXII","XXXIII","XXXIV","XXXV","XXXVI","XXXVII","XXXVIII","XXXIX","XL","XLI","XLII","XLIII","XLIV","XLV","XLVI","XLVII","XLVIII","XLIX","L","LI","LII","LIII","LIV","LV","LVI","LVII","LVIII","LIX"];
const sortedChapters = chapterOrder.filter(ch => chapterSet.has(ch));
const chapterFilter = document.getElementById('chapterFilter');
sortedChapters.forEach(ch => {{
  const opt = document.createElement('option');
  opt.value = ch;
  opt.textContent = 'Ch. ' + ch;
  chapterFilter.appendChild(opt);
}});

function updateStats(items) {{
  const supports = items.filter(x => x.stance === 'SUPPORTS').length;
  const challenges = items.filter(x => x.stance === 'CHALLENGES').length;
  const neutral = items.filter(x => x.stance === 'NEUTRAL').length;
  document.getElementById('statsBar').innerHTML =
    `Showing ${{items.length}} of ${{ALL_ITEMS.length}} items &nbsp;·&nbsp; ` +
    `<strong style="color:#1a7a4a">✓ ${{supports}} supporting</strong> &nbsp;·&nbsp; ` +
    `<strong style="color:#c0392b">✗ ${{challenges}} challenging</strong> &nbsp;·&nbsp; ` +
    `<strong style="color:#7f8c8d">○ ${{neutral}} neutral</strong>`;
}}

function renderItem(item) {{
  const stanceLabel = item.stance === 'SUPPORTS' ? '✓ Supports' : item.stance === 'CHALLENGES' ? '✗ Challenges' : '○ Neutral';
  const typeEmoji = {{'article':'📰','podcast':'🎙️','paper':'📄','web':'🌐'}}[item.content_type] || '📄';
  const scorePct = Math.round(item.relevance_score);
  const chapterTags = (item.chapters || []).map(ch => `<span class="chapter-tag">Ch. ${{ch}}</span>`).join('');
  const factCheck = item.is_fact_check_lead ?
    `<div class="fact-check">📌 Fact-check lead: ${{item.fact_check_note || 'Addresses a key statistic'}}</div>` : '';
  const dateStr = item.date_published ? new Date(item.date_published + 'T00:00:00').toLocaleDateString('en-US', {{month:'short', day:'numeric', year:'numeric'}}) : '';

  return `<div class="item ${{item.stance}}">
    <div class="item-header">
      <span class="stance-badge ${{item.stance}}">${{stanceLabel}}</span>
      <a href="${{item.url}}" target="_blank" rel="noopener" class="item-title">${{escHtml(item.title)}}</a>
    </div>
    <div class="item-meta">
      ${{typeEmoji}} ${{escHtml(item.source)}} &nbsp;·&nbsp; ${{dateStr}}
      &nbsp;·&nbsp; <span class="score-bar"><span class="score-fill" style="width:${{scorePct}}%"></span></span> ${{scorePct}}/100
    </div>
    <div class="item-summary">${{escHtml(item.summary)}}</div>
    ${{chapterTags ? `<div class="item-chapters">${{chapterTags}}</div>` : ''}}
    ${{factCheck}}
  </div>`;
}}

function escHtml(str) {{
  return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function filterItems() {{
  const search = document.getElementById('searchBox').value.toLowerCase();
  const stance = document.getElementById('stanceFilter').value;
  const type = document.getElementById('typeFilter').value;
  const chapter = document.getElementById('chapterFilter').value;
  const sort = document.getElementById('sortOrder').value;

  let filtered = ALL_ITEMS.filter(item => {{
    if (stance && item.stance !== stance) return false;
    if (type && item.content_type !== type) return false;
    if (chapter && !(item.chapters || []).includes(chapter)) return false;
    if (search) {{
      const haystack = (item.title + ' ' + item.source + ' ' + item.summary).toLowerCase();
      if (!haystack.includes(search)) return false;
    }}
    return true;
  }});

  if (sort === 'score') filtered.sort((a,b) => b.relevance_score - a.relevance_score);
  else if (sort === 'date') filtered.sort((a,b) => (b.date_published||'').localeCompare(a.date_published||''));
  else if (sort === 'date_asc') filtered.sort((a,b) => (a.date_published||'').localeCompare(b.date_published||''));

  document.getElementById('itemsContainer').innerHTML =
    filtered.length ? filtered.map(renderItem).join('') :
    '<div class="no-results">No items match your filters.</div>';
  document.getElementById('resultsCount').textContent = filtered.length + ' items';
  updateStats(filtered);
}}

{''; if (password_gate_html) print('') }
filterItems();
{'}}' if password_gate_html else ''}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Email rendering
# ---------------------------------------------------------------------------

def _inline_format(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        r'<a href="\2" style="color:#2d6a2d;">\1</a>',
        text,
    )
    text = re.sub(
        r'(?<!["\'>])(https?://[^\s<>"]+)',
        r'<a href="\1" style="color:#2d6a2d;">\1</a>',
        text,
    )
    return text


def _render_item_card(item: dict) -> str:
    stance = item.get("stance", "NEUTRAL")
    color = STANCE_COLOR.get(stance, "#7f8c8d")
    emoji = STANCE_EMOJI.get(stance, "○")
    type_emoji = TYPE_EMOJI.get(item.get("content_type", "article"), "📄")
    chapters = item.get("chapters", [])
    chapter_str = "Ch. " + ", ".join(chapters) if chapters else ""
    score = item.get("relevance_score", 0)
    url = item.get("url", "#")
    title = item.get("title", "")
    source = item.get("source", "")
    date = item.get("date_published", "")
    summary = _inline_format(item.get("summary", ""))
    fact_note = item.get("fact_check_note", "")
    is_fact_lead = item.get("is_fact_check_lead", False)

    meta_parts = [f"{type_emoji} {source}"]
    if date:
        meta_parts.append(date)
    if chapter_str:
        meta_parts.append(f"<span style='color:{color};font-weight:bold;'>{chapter_str}</span>")
    meta_parts.append(f"relevance: {score}/100")
    meta_str = " &nbsp;·&nbsp; ".join(meta_parts)

    fact_html = ""
    if is_fact_lead:
        fact_html = f"""
        <div style="margin-top:8px;background:#fff8e1;border-left:3px solid #ffc107;padding:6px 10px;font-size:12px;color:#7b5e00;">
          📌 <strong>Fact-check lead:</strong> {_inline_format(fact_note)}
        </div>"""

    return f"""
    <div style="border-left:4px solid {color};padding:14px 16px;margin-bottom:16px;background:#fafafa;border-radius:0 4px 4px 0;">
      <div style="margin-bottom:6px;">
        <a href="{url}" style="color:#1a3a1a;font-size:15px;font-weight:bold;text-decoration:none;">{_inline_format(title)}</a>
      </div>
      <div style="font-size:12px;color:#888;margin-bottom:8px;">{meta_str}</div>
      <div style="font-size:14px;line-height:1.6;color:#333;">{summary}</div>
      {fact_html}
    </div>"""


def render_email(new_items: list[dict], index: dict, since: datetime) -> str:
    """Render the weekly digest as HTML."""
    period_start = since.strftime("%B %d, %Y")
    period_end = datetime.now().strftime("%B %d, %Y")
    generated_at = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    total_indexed = index.get("total_items", len(new_items))

    supports = [x for x in new_items if x["stance"] == "SUPPORTS"]
    challenges = [x for x in new_items if x["stance"] == "CHALLENGES"]
    neutral = [x for x in new_items if x["stance"] == "NEUTRAL"]
    fact_leads = [x for x in new_items if x.get("is_fact_check_lead")]

    def section(items: list[dict], heading: str, color: str, emoji: str) -> str:
        if not items:
            return ""
        cards = "".join(_render_item_card(item) for item in items)
        return f"""
        <div style="margin-bottom:36px;">
          <div style="background:{color};color:white;padding:10px 16px;border-radius:4px;font-size:13px;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;">
            {emoji} {heading} ({len(items)})
          </div>
          {cards}
        </div>"""

    supports_html = section(supports, "Supports Your Argument", "#1a7a4a", "✓")
    challenges_html = section(challenges, "Challenges Your Argument", "#c0392b", "✗")
    neutral_html = section(neutral, "Background / Neutral", "#7f8c8d", "○")

    fact_html = ""
    if fact_leads:
        cards = "".join(_render_item_card(item) for item in fact_leads)
        fact_html = f"""
        <div style="margin-bottom:36px;">
          <div style="background:#e67e22;color:white;padding:10px 16px;border-radius:4px;font-size:13px;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;">
            📌 Fact-Check Leads ({len(fact_leads)})
          </div>
          {cards}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Book Research Digest</title>
</head>
<body style="font-family:Georgia,'Times New Roman',serif;background:#f5f5f0;margin:0;padding:0;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f0;">
  <tr><td align="center" style="padding:30px 20px;">
    <table width="680" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">

      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#1a3a1a 0%,#2d6a2d 100%);padding:36px 40px;text-align:center;">
        <div style="font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#a8d5a8;margin-bottom:10px;">Weekly Research Digest</div>
        <h1 style="color:#ffffff;margin:0;font-size:26px;font-weight:bold;">The American Farmland System</h1>
        <div style="color:#c8e6c9;margin-top:8px;font-size:14px;">Book Research Tracker</div>
        <div style="color:#a8d5a8;margin-top:6px;font-size:13px;">{period_start} – {period_end}</div>
      </td></tr>

      <!-- Stats bar -->
      <tr><td style="background:#e8f5e9;padding:14px 40px;border-bottom:1px solid #c8e6c9;">
        <table width="100%" cellpadding="0" cellspacing="0"><tr>
          <td style="font-size:13px;color:#2e7d32;">
            <strong>{len(new_items)}</strong> new items this week &nbsp;·&nbsp;
            <strong style="color:#1a7a4a">✓ {len(supports)}</strong> supporting &nbsp;·&nbsp;
            <strong style="color:#c0392b">✗ {len(challenges)}</strong> challenging &nbsp;·&nbsp;
            <strong style="color:#7f8c8d">○ {len(neutral)}</strong> neutral
            {f' &nbsp;·&nbsp; <strong style="color:#e67e22">📌 {len(fact_leads)}</strong> fact-check leads' if fact_leads else ''}
          </td>
          <td align="right" style="font-size:12px;color:#888;">{total_indexed} total indexed</td>
        </tr></table>
      </td></tr>

      <!-- Body -->
      <tr><td style="padding:36px 40px;">
        {supports_html}
        {challenges_html}
        {fact_html}
        {neutral_html}
      </td></tr>

      <!-- Footer -->
      <tr><td style="background:#f8f9fa;border-top:1px solid #e8e8e8;padding:24px 40px;text-align:center;">
        <p style="font-size:12px;color:#7f8c8d;margin:0 0 6px;">
          Generated automatically by the Book Research Tracker · {generated_at}
        </p>
        <p style="font-size:11px;color:#95a5a6;margin:0;">
          Analysis powered by Claude (Anthropic) · 60+ sources monitored weekly
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Send email
# ---------------------------------------------------------------------------

def send_email(html: str, new_item_count: int, since: datetime) -> None:
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not gmail_password:
        raise ValueError("GMAIL_APP_PASSWORD environment variable is not set.")

    subject = (
        f"Book Research Digest — {new_item_count} new items "
        f"({datetime.now().strftime('%B %d, %Y')})"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Book Research Tracker <{SENDER_EMAIL}>"
    msg["To"] = RECIPIENT_EMAIL

    plain = (
        f"Book Research Digest — {new_item_count} new items\n\n"
        "This email requires an HTML-capable email client. Please view in Gmail."
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    print(f"  Sending to {RECIPIENT_EMAIL} via Gmail SMTP...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SENDER_EMAIL, gmail_password)
        smtp.sendmail(SENDER_EMAIL, [RECIPIENT_EMAIL], msg.as_string())
    print(f"  Email sent successfully.")


def save_email_to_file(html: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Email HTML saved to: {path}")
