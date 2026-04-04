"""
Use Claude (claude-opus-4-6) to deeply analyze scraped content and
write a narrative weekly report for book research.

Report structure:
  PART A: Current Developments — what's happening right now in the field
  PART B: Research & Academic — new studies, reports, policy papers
  PART C: Broader Context — international angles, historical parallels,
          connecting threads relevant to the book argument

TODO: Refine SYSTEM_PROMPT and USER_PROMPT once book topics are confirmed.
"""

import os
from datetime import datetime
import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _format_items(items: list[dict], max_chars_per_item: int = 800) -> str:
    """Format scraped items as a readable list for the prompt."""
    if not items:
        return "(No items found this period.)"

    lines = []
    for i, item in enumerate(items, 1):
        date_str = item["date"].strftime("%Y-%m-%d") if item.get("date") else "date unknown"
        content = item.get("content", item.get("title", ""))[:max_chars_per_item]
        lines.append(
            f"[{i}] SOURCE: {item['source']}\n"
            f"    DATE: {date_str}\n"
            f"    TITLE: {item.get('title', 'N/A')[:150]}\n"
            f"    CONTENT: {content}\n"
            f"    URL: {item.get('url', 'N/A')}\n"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompts — TODO: refine with specific book topics, key figures, arguments
# ---------------------------------------------------------------------------

# This will be replaced with a detailed expert persona once topics are known.
SYSTEM_PROMPT = """You are a skilled research analyst and writing assistant helping an author
research and write a non-fiction book.

TODO: Replace this placeholder with:
- The book's central thesis and argument
- The key topics, time periods, and geographies covered
- Important figures, organizations, datasets, and legislation to watch
- The author's analytical lens and voice
- What kind of content is most valuable for the book

Your writing is analytical, specific, and well-sourced.
You connect current events to historical patterns and larger themes.
You write for a smart general audience, not just specialists."""


def _build_user_prompt(
    primary_items: list[dict],
    news_items: list[dict],
    research_items: list[dict],
    since: datetime,
) -> str:
    period_start = since.strftime("%B %d, %Y")
    period_end = datetime.now().strftime("%B %d, %Y")

    primary_formatted = _format_items(primary_items)
    news_formatted = _format_items(news_items)
    research_formatted = _format_items(research_items)

    return f"""Please write a comprehensive weekly research tracker report for the period {period_start} to {period_end}.

=== PRIMARY / GOVERNMENT SOURCES ===
(Official agencies, policy bodies, land trusts, databases)

{primary_formatted}

=== NEWS SOURCES ===
(National and trade press)

{news_formatted}

=== RESEARCH & ACADEMIC SOURCES ===
(Journals, think tanks, university programs)

{research_formatted}

---

Write the report in three clearly separated sections:

## PART A: CURRENT DEVELOPMENTS

Summarize the most significant news and policy developments this week.

TODO: Replace with specific sub-headings matching the book's topic structure.

For each notable item:
- What happened, who was involved, where
- Why it matters for the book's argument
- What to watch next

**Bottom Line:** A 2-3 sentence editorial summary of the week's most important development.

---

## PART B: RESEARCH & ACADEMIC

Highlight new studies, reports, data releases, or academic work:

For each item:
- **[Institution/Journal]: [What was published]** — 2-3 sentence summary
- **Relevance to the book:** 1-2 sentences on how this supports, challenges, or enriches the argument
- **Key finding or data point:** One concrete takeaway

---

## PART C: BROADER CONTEXT & CONNECTIONS

Draw out 2-3 broader threads from this week's material:
- Historical parallels or long-run trends the week's news illuminates
- International comparisons or counterexamples
- Connections between items that might not be obvious

End with **"This Week's Research Priority"** — one specific action the author should take based on this week's material (e.g., a source to contact, a dataset to pull, a chapter angle to develop).

---

If no relevant content was found in a section, say so briefly and offer relevant background context instead. Always produce a useful, substantive report."""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze_content(
    primary_items: list[dict],
    news_items: list[dict],
    research_items: list[dict],
    since: datetime,
) -> dict:
    """
    Send all scraped content to Claude for analysis.
    Returns a dict with section keys and metadata.
    """
    client = _get_client()

    period_start = since.strftime("%B %d, %Y")
    period_end = datetime.now().strftime("%B %d, %Y")

    user_prompt = _build_user_prompt(primary_items, news_items, research_items, since)

    print("Sending content to Claude for analysis (this may take a minute)...")

    full_text = ""
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_text += text

    print("\n\n[Analysis complete]")

    # Split into three sections
    part_a, part_b, part_c = "", "", ""

    markers_b = ["## PART B", "## Part B", "# PART B", "# Part B", "PART B:"]
    markers_c = ["## PART C", "## Part C", "# PART C", "# Part C", "PART C:"]

    pos_b = next((full_text.find(m) for m in markers_b if full_text.find(m) != -1), -1)
    pos_c = next((full_text.find(m) for m in markers_c if full_text.find(m) != -1), -1)

    if pos_b != -1 and pos_c != -1:
        part_a = full_text[:pos_b].strip()
        part_b = full_text[pos_b:pos_c].strip()
        part_c = full_text[pos_c:].strip()
    elif pos_b != -1:
        part_a = full_text[:pos_b].strip()
        part_b = full_text[pos_b:].strip()
    else:
        part_a = full_text

    return {
        "part_a": part_a,
        "part_b": part_b,
        "part_c": part_c,
        "period_start": period_start,
        "period_end": period_end,
        "primary_item_count": len(primary_items),
        "news_item_count": len(news_items),
        "research_item_count": len(research_items),
        "raw_full_text": full_text,
    }
