"""
Use Claude (claude-opus-4-6) to deeply analyze scraped content and
write a narrative weekly report on:
  (A) Mill Valley housing density and public transportation developments
  (B) Ideas and insights from cities around the world
"""

import os
import json
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


def analyze_content(
    mv_items: list[dict],
    global_items: list[dict],
    since: datetime,
) -> dict:
    """
    Send all scraped content to Claude claude-opus-4-6 for analysis.
    Returns a dict with 'mill_valley_section' and 'global_section' keys.
    """
    client = _get_client()

    period_start = since.strftime("%B %d, %Y")
    period_end = datetime.now().strftime("%B %d, %Y")

    mv_formatted = _format_items(mv_items)
    global_formatted = _format_items(global_items)

    system_prompt = """You are an expert urban planning analyst with deep knowledge of:
- California housing law (Housing Element law, SB 9, SB 10, ADU regulations, Builder's Remedy)
- Marin County and Mill Valley, CA local politics and community dynamics
- Public transportation policy and best practices (BRT, light rail, bike infrastructure, TOD)
- Global models of successful housing density and transit reform
- YIMBY movement, Strong Towns philosophy, and evidence-based urbanism

Key Mill Valley housing bodies you track closely:

**Housing Advisory Committee (HAC)**
- John McCauley — Committee Chair and City Council Liaison
- Urban Carmel — City Council Liaison
- Jon Yolles — Planning Commission representative
- Greg Hildebrand — Planning Commission Liaison
- Matthew Franklin — Member at Large
- Key city staff: Patrick Kelly (Director of Planning and Building) and
  Danielle Staude (Planner who presents HAC items to Council)

**Mill Valley Affordable Housing Committee (MVAHC)**
- Community advisory body focused specifically on affordable housing policy and
  advocacy within Mill Valley

You write for an engaged, informed audience who cares deeply about Mill Valley's future.
Your writing is analytical, specific, editorial, and occasionally opinionated.
You cite specific details, dates, and places. You connect local news to bigger patterns.
You are optimistic but clear-eyed about obstacles."""

    user_prompt = f"""Please write a comprehensive weekly tracker report covering the period {period_start} to {period_end}.

=== MILL VALLEY & MARIN COUNTY CONTENT ===
(City Council meetings, Planning Commission, Housing Advisory Committee (HAC),
Mill Valley Affordable Housing Committee (MVAHC), local news, transit updates)

{mv_formatted}

=== GLOBAL CITIES CONTENT ===
(Housing density wins, transit improvements, policy innovations from around the world)

{global_formatted}

---

Write the report in two clearly separated sections:

## PART A: MILL VALLEY UPDATE

Write a narrative briefing on what's happening in Mill Valley and Marin County on:

**Housing Advisory Committee (HAC)**
- Any meetings, agenda items, votes, or notable discussions this week?
- What housing projects or policy questions are before the HAC?
- Any actions by members John McCauley, Urban Carmel, Jon Yolles, Greg Hildebrand, or Matthew Franklin worth noting?
- Any items flagged by staff Patrick Kelly or Danielle Staude for Council?
- What should we watch for at the next HAC meeting?

**Mill Valley Affordable Housing Committee (MVAHC)**
- Any meetings, recommendations, or advocacy activity this week?
- What affordable housing projects or policy proposals are they engaged with?
- Any positions or communications directed to City Council or staff?

**Housing Density (General)**
- What proposals, decisions, or discussions happened this week beyond the committees?
- What stage is the city's Housing Element compliance?
- Any notable development projects, ADU activity, or zoning changes?
- What should we watch for next?

**Public Transportation**
- Any Marin Transit route changes, service improvements, or cuts?
- SMART train updates relevant to North Marin commuters?
- Bike infrastructure, pedestrian safety, or street design proposals?
- Any ferry service changes or parking/car-reduction initiatives?

**Bottom Line for Mill Valley**
A 2-3 sentence editorial summary: what's the overall direction of travel? Is Mill Valley moving toward or away from more housing and less car dependence? Be honest and specific.

---

## PART B: IDEAS FROM THE WORLD

Highlight the 4-6 most relevant and inspiring developments from other cities globally:

For EACH item:
- **[City/Country]: [What happened]** — A 2-3 sentence description
- **Why it matters for Mill Valley:** 1-2 sentences connecting the idea to Mill Valley's specific situation
- **Key lesson:** One concrete takeaway

End with a section called **"What Mill Valley Could Borrow This Week"** — a 1-paragraph synthesis of the single most actionable idea from the global section, tailored specifically to what Mill Valley could realistically adopt given its size, politics, and Marin County context.

---

If there was no relevant content found in either section, acknowledge that clearly and provide relevant background context about ongoing issues in Mill Valley housing and transit instead. Always produce a useful, substantive report even if the news cycle was quiet."""

    print("Sending content to Claude for analysis (this may take a minute)...")

    # Use streaming for long output, adaptive thinking for deep analysis
    full_text = ""
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_text += text

    print("\n\n[Analysis complete]")

    # Split the report into two sections
    part_a = ""
    part_b = ""

    # Try to split on the Part B header
    split_markers = [
        "## PART B",
        "## Part B",
        "# PART B",
        "# Part B",
        "PART B:",
    ]
    split_pos = -1
    for marker in split_markers:
        pos = full_text.find(marker)
        if pos != -1:
            split_pos = pos
            break

    if split_pos != -1:
        part_a = full_text[:split_pos].strip()
        part_b = full_text[split_pos:].strip()
    else:
        # Fallback: treat whole text as part A if split not found
        part_a = full_text
        part_b = "(See above for combined report.)"

    return {
        "mill_valley_section": part_a,
        "global_section": part_b,
        "period_start": period_start,
        "period_end": period_end,
        "mv_item_count": len(mv_items),
        "global_item_count": len(global_items),
        "raw_full_text": full_text,
    }
