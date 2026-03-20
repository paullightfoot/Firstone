"""
Use Claude (claude-opus-4-6) to analyze scraped content for relevance to
The American Farmland System book.

For each item Claude returns:
  - relevance_score: 0-100
  - stance: SUPPORTS | CHALLENGES | NEUTRAL
  - chapters: list of Roman numeral chapter numbers most relevant
  - summary: 2-3 sentence summary
  - is_fact_check_lead: bool — does this address a key statistic the author needs?
  - fact_check_note: brief note if is_fact_check_lead is true
"""

import os
import json
import hashlib
from datetime import datetime
import anthropic


# ---------------------------------------------------------------------------
# Chapter reference — abbreviated for prompt efficiency
# ---------------------------------------------------------------------------

CHAPTER_REFERENCE = """
I: Author credibility — business leader, capitalist + environmentalist
II: Patagonia Provisions — regenerative organic as commercial proof of concept
III: Climate vs. economy false choice — incumbents lose, not the whole economy
IV: Global perspective — US ag policy affects the world
V: CENTRAL THESIS — 60-70% of US cropland not growing food for humans
VI: Farming for cars — ethanol debacle (30-35M acres, RFS mandate, Haber-Bosch→corn→fuel)
VII: Farming for cows — 900M+ acres for livestock, feedlot vs. regenerative distinction
VIII: System design — follow the money; who benefits from current arrangement
IX: Input suppliers — Monsanto/Bayer, Syngenta, DuPont Pioneer seed/chemical monopoly
X: Grain buyers — Cargill, ADM, Bunge oligopoly; no free market in commodity ag
XI: Fossil food connection — ag lobbying exceeds fossil fuel lobbying
XII: Fossil fuel industry — food as fossil fuel's "escape hatch" as energy decarbonizes
XIII: Industrial livestock — Cattlemen's Association lobbying, JBS, Colorado River water capture
XIV: Politicians — Farm Bill committee members receiving subsidies; revolving door
XV: Big Food brands — Mondelez, Unilever, Nestlé, Kraft Heinz, PepsiCo; junk food subsidized
XVI: Giant farms — 7% of farms get 85% of income; top 150k avg $650k, rest avg near zero
XVII: No free market — organic demand gap ($65B sales, <1% of farmland organic) = market failure
XVIII: Human health — food as leading cause of US mortality (500k+/yr); obesity, diabetes epidemic
XIX: Biodiversity — food system as primary driver of global species loss; Silent Spring realized
XX: Waterway pollution — Gulf dead zone, Iowa lakes captured by corn/hog industry
XXI: Farmer welfare — rural hollowing out, elevated suicide rates, young people leaving
XXII: Taxpayer waste — $20-50B/yr in subsidies; paying farmers to grow wrong things wrong way
XXIII: Synthetic fertilizer treadmill — Haber-Bosch, glyphosate, fossil fuel→food cycle
XXIV: System lock-in — progressive entrapment; Bayer/Syngenta/John Deere control data too
XXV: Regulatory framework as problem — less regulation needed; current system = government fiat
XXVI: Historical context — pre-industrial farming didn't have these problems
XXVII: Systems thinking — piecemeal approaches fail; need whole-system change
XXVIII: Policy changes — end ethanol mandate, stop subsidizing synthetic treadmill
XXIX: Regenerative organic defined — composting, cover crops, crop rotation, no synthetics
XXX: Economic viability — Rodale Institute; input costs lower; margins higher long-term
XXXI: Doug Tompkins philosophy — conservation as product of production, not separate from it
XXXII: Rejecting "less harm" — incremental improvements to broken system = clean coal fallacy
XXXIII: The ocean — eat low on food chain; farmed salmon = ocean CAFOs
XXXIV: Case studies — Patagonia Provisions (ROC crackers, Kernza beer), Wild Idea Buffalo
XXXV: International examples — Denmark -50% nitrogen in 10 years; Copenhagen 90% organic procurement
XXXVI-XLIX: Reform transition scenarios — land reallocation, price effects, diet shift, health savings
L-LIII: Objections addressed — affordability, Bill Gates yield/deforestation argument, organic supply suppression
LIV-LVI: Call to action — purchasing power, school food reform, becoming an activist
LVII-LIX: Closing — helpfulness vs. helplessness; free market framing; "rigged game"
"""

# Key statistics the author needs to verify/find sources for
FACT_CHECK_TARGETS = [
    "60-70% of US cropland not growing food for humans",
    "30-35 million acres for corn ethanol",
    "900 million acres total livestock footprint",
    "7% of farms receive 85% of farm income",
    "top 150,000 farms average $650,000/year",
    "$65 billion in organic food sales annually",
    "less than 1% of farmland is organic",
    "agricultural lobbying exceeds fossil fuel lobbying",
    "food causes 500,000+ deaths per year in the US",
    "three in four Americans overweight or obese",
    "2,300 heart disease deaths per day",
    "synthetic fertilizer generates more GHG than global aviation",
    "5% of global natural gas goes to fertilizer",
    "Colorado River water: majority goes to livestock",
    "Denmark cut nitrogen fertilizer 50% in one decade",
    "Copenhagen 90% organic procurement in four years",
    "$20 billion per year baseline farm subsidies",
    "eight House Agriculture Committee members received $14M+ in subsidies",
    "corn price would drop 12% if ethanol mandate ended",
    "Adaptive multi-paddock grazing 2-4x carrying capacity improvement",
]


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _make_item_id(url: str) -> str:
    """Stable ID for deduplication — SHA256 of URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _format_batch_for_prompt(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        date_str = item["date"].strftime("%Y-%m-%d") if item.get("date") else "date unknown"
        lines.append(
            f"ITEM {i}:\n"
            f"  Title: {item.get('title', 'N/A')[:200]}\n"
            f"  Source: {item.get('source', 'N/A')} ({item.get('content_type', 'article')})\n"
            f"  Date: {date_str}\n"
            f"  Content: {item.get('content', '')[:600]}\n"
            f"  URL: {item.get('url', 'N/A')}\n"
        )
    return "\n".join(lines)


def _analyze_batch(items: list[dict], client: anthropic.Anthropic) -> list[dict]:
    """Send a batch of items to Claude. Returns list of analysis dicts."""

    system_prompt = f"""You are a research analyst helping an author write a book called
"The American Farmland System." The book argues that US farmland has been captured by a
petrochemical-agricultural complex: corn and soy monocultures, fertilized by natural gas
(Haber-Bosch process), feeding ethanol mandates and industrial feedlots, enriching a handful
of corporations (ADM, Cargill, Bunge, Tyson, Monsanto/Bayer, etc.) while producing little
actual human food. The author is a capitalist and business leader — not an ideologue.

CHAPTER STRUCTURE (abbreviated):
{CHAPTER_REFERENCE}

KEY STATISTICS AUTHOR NEEDS TO VERIFY:
{chr(10).join(f"- {s}" for s in FACT_CHECK_TARGETS)}

Your job: analyze each item and return structured JSON.
"""

    user_prompt = f"""Analyze each of the following {len(items)} items for relevance to this book.

{_format_batch_for_prompt(items)}

For EACH item, return a JSON object. Return a JSON array of {len(items)} objects, one per item,
in the same order. Each object must have EXACTLY these fields:

{{
  "relevance_score": <integer 0-100>,
  "stance": "<SUPPORTS|CHALLENGES|NEUTRAL>",
  "chapters": [<list of chapter Roman numerals as strings, e.g. "VI", "X">],
  "summary": "<2-3 sentence summary focused on what matters for this book>",
  "is_fact_check_lead": <true|false>,
  "fact_check_note": "<if is_fact_check_lead, which statistic this addresses; else empty string>"
}}

Scoring guidance:
- 80-100: Directly addresses a core argument, provides new evidence, or names key players
- 60-79: Clearly relevant to the book's topics; useful research material
- 40-59: Tangentially relevant; background context
- 0-39: Not meaningfully relevant (score these but still include them)

Stance guidance:
- SUPPORTS: Evidence or argument that backs the book's thesis
- CHALLENGES: Evidence or argument that contradicts or complicates the book's thesis
- NEUTRAL: Background information, data, or balanced coverage

IMPORTANT: Industry/conventional sources defending ethanol, industrial farming, etc. = CHALLENGES stance.
Return ONLY the JSON array. No other text."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    results = json.loads(raw)
    return results


def analyze_items(raw_items: list[dict]) -> list[dict]:
    """
    Analyze all raw scraped items with Claude.
    Returns enriched items with relevance_score, stance, chapters, summary, etc.
    Only returns items with relevance_score >= 40.
    """
    import re  # ensure re is available in this scope

    if not raw_items:
        return []

    client = _get_client()
    analyzed = []
    batch_size = 15
    batches = [raw_items[i:i + batch_size] for i in range(0, len(raw_items), batch_size)]

    print(f"  Analyzing {len(raw_items)} items in {len(batches)} batches...")

    for batch_num, batch in enumerate(batches, 1):
        print(f"  Batch {batch_num}/{len(batches)} ({len(batch)} items)...")
        try:
            results = _analyze_batch(batch, client)

            for item, analysis in zip(batch, results):
                score = int(analysis.get("relevance_score", 0))
                if score < 40:
                    continue

                date_val = item.get("date")
                enriched = {
                    "id": _make_item_id(item.get("url", item.get("title", ""))),
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "source_category": item.get("source_category", ""),
                    "source_lean": item.get("source_lean", "neutral"),
                    "date_published": date_val.strftime("%Y-%m-%d") if date_val else "",
                    "date_indexed": datetime.now().strftime("%Y-%m-%d"),
                    "content_type": item.get("content_type", "article"),
                    "relevance_score": score,
                    "stance": analysis.get("stance", "NEUTRAL"),
                    "chapters": analysis.get("chapters", []),
                    "summary": analysis.get("summary", ""),
                    "is_fact_check_lead": bool(analysis.get("is_fact_check_lead", False)),
                    "fact_check_note": analysis.get("fact_check_note", ""),
                }
                analyzed.append(enriched)

        except Exception as e:
            print(f"  [batch {batch_num} error] {e}")
            # On analysis failure, include raw items with neutral scores
            for item in batch:
                date_val = item.get("date")
                analyzed.append({
                    "id": _make_item_id(item.get("url", item.get("title", ""))),
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "source_category": item.get("source_category", ""),
                    "source_lean": item.get("source_lean", "neutral"),
                    "date_published": date_val.strftime("%Y-%m-%d") if date_val else "",
                    "date_indexed": datetime.now().strftime("%Y-%m-%d"),
                    "content_type": item.get("content_type", "article"),
                    "relevance_score": 50,
                    "stance": "NEUTRAL",
                    "chapters": [],
                    "summary": item.get("content", "")[:300],
                    "is_fact_check_lead": False,
                    "fact_check_note": "",
                })

    # Sort by relevance score descending
    analyzed.sort(key=lambda x: x["relevance_score"], reverse=True)

    supports = sum(1 for x in analyzed if x["stance"] == "SUPPORTS")
    challenges = sum(1 for x in analyzed if x["stance"] == "CHALLENGES")
    neutral = sum(1 for x in analyzed if x["stance"] == "NEUTRAL")
    fact_leads = sum(1 for x in analyzed if x["is_fact_check_lead"])

    print(f"  Analysis complete: {len(analyzed)} items kept")
    print(f"    SUPPORTS={supports}  CHALLENGES={challenges}  NEUTRAL={neutral}  fact-check leads={fact_leads}")

    return analyzed


import re
