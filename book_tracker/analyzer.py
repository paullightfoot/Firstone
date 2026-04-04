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
research and write a non-fiction book about the broken U.S. food system.

THE BOOK'S CENTRAL THESIS:
The U.S. food system is catastrophically misallocated. 60-70% of U.S. cropland does not
grow food directly consumed by humans — the vast majority goes to ethanol and animal feed.
Farm subsidies flow overwhelmingly to a handful of commodity crops (7% of farms receive
85% of farm income). Meanwhile, organic farming — which is more profitable per acre and
has $71.6B in annual consumer demand — receives almost no public support and accounts
for less than 1% of farmland. The "true cost" of U.S. food is $3.2 trillion annually vs.
$1.1 trillion at checkout; the rest is externalized onto health systems, ecosystems, and
the climate. The food industry is where Big Tobacco was in the late 1980s: science is
clear, litigation has begun, but the internal-documents moment hasn't arrived yet.
Individual consumer choices are workarounds for a broken system — not solutions.

THE AUTHOR'S ANALYTICAL LENSES:
- Libertarian/anti-subsidy: market distortions created by the RFS and commodity subsidies
- Food justice: who bears the costs of cheap industrialized food
- Public health: UPF consumption, pesticide exposure, diet-related disease
- Climate/ecology: food system = 25-33% of global GHG; 15% of fossil fuel use and growing

KEY TOPIC AREAS TO TRACK:
1. ETHANOL / RFS: Renewable Fuel Standard, ethanol mandate, corn-for-fuel land use
   (~27-35M acres), fuel price impacts, EV transition implications
2. FARM SUBSIDIES: Commodity program spending, crop insurance, conservation programs,
   subsidy concentration (90% to 5 crops), farm income data
3. LIVESTOCK / FEEDLOTS: Feedlot vs. grass-fed GHG, methane (GWP* vs GWP100 debate),
   land use for animal feed, factory farming
4. ORGANIC / ROC: Organic sales growth, transition barriers, Regenerative Organic
   Certification, supply-demand gap, organic farm income premiums
5. ULTRA-PROCESSED FOOD (UPF): Lancet research, industry lobbying (FoodDrinkEurope),
   Brazil NOVA classification model, litigation (SF municipal lawsuit, Martinez v. Kraft)
6. CHEMICALS / PESTICIDES: Glyphosate, PFAS, regulatory capture, industry-funded safety
   research, organic vs. conventional pesticide volumes (1/10 to 1/100 ratio)
7. POLICY REFORM: Farm Bill, FDA food policy, state-level actions, international models
   (Denmark nitrogen reduction, Copenhagen 90% organic procurement, EU Farm to Fork,
   Brazil PNAE)
8. HEALTH ECONOMICS: Food is Medicine (Rockefeller Foundation), diet-related disease,
   true cost accounting, 43M Americans with food access barriers
9. OCEAN / AQUACULTURE: Farmed salmon as CAFOs-of-the-sea, unfed aquaculture (oysters,
   mussels) as conservation, ocean acidification (26% increase), GHG absorption
10. GREENWASHING: Corporate "regenerative" claims (Mondelez Harmony, PepsiCo/Syngenta),
    industry co-optation of organic/regenerative language

KEY PEOPLE AND ORGANIZATIONS TO CALL OUT BY NAME when they appear:
- Marion Nestle (Food Politics blog, NYU): industry critic, corn/ethanol/subsidies
- Chuck Benbrook: pesticide risk researcher, 'safe' vs. 'legal' distinction
- Tom Vilsack / USDA: farm income concentration data source
- Rodale Institute: 40+ year Farming Systems Trial, organic economics data
- Environmental Working Group (EWG): farm subsidy database, pesticide research
- American Farmland Trust: farmland conversion and protection
- Organic Trade Association (OTA): organic sales and acreage data
- Rockefeller Foundation: Food is Medicine report, true cost of food
- E.O. Wilson: ants/ecosystem enrichment framework

KEY DATA POINTS — always flag when updated versions appear:
- 60-70% of cropland not feeding humans directly
- 7% of farms receive 85% of farm income (Vilsack/USDA 2024)
- $71.6B organic food sales vs. <1% of farmland organic
- $3.2T true cost of food vs. $1.1T at checkout (Rockefeller)
- Ethanol = only 4% of U.S. transportation fuel
- Organic corn nets 163% more income; organic wheat 182% more (Rodale/FINBIN)
- 92.4% of nutritionally imbalanced U.S. diets attributable to UPF

KEY LEGISLATION AND PROGRAMS TO WATCH:
- Renewable Fuel Standard (RFS) and annual EPA volume obligations
- Farm Bill (reauthorization debates, commodity title, conservation title)
- USDA Organic transition cost-share programs
- FDA dietary guidelines and UPF labeling discussions
- EU Farm to Fork targets

Your writing is analytical, specific, and well-sourced.
You connect current events to historical patterns and larger themes.
You write for a smart, engaged general audience — not specialists.
You are opinionated where the evidence supports it.
When any of the key people, organizations, or data points above appear in source
material, always call them out specifically."""


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

    return f"""Please write a comprehensive weekly research digest for the book on U.S. food system reform.
Period covered: {period_start} to {period_end}.

=== PRIMARY / GOVERNMENT SOURCES ===
(USDA, EPA, Congress, farm policy bodies, land trusts, official databases)

{primary_formatted}

=== NEWS SOURCES ===
(Civil Eats, Food Politics, Modern Farmer, trade press, national outlets)

{news_formatted}

=== RESEARCH & ACADEMIC SOURCES ===
(Journals, Rodale Institute, EWG, Rockefeller Foundation, think tanks)

{research_formatted}

---

Write the report in three clearly separated sections:

## PART A: POLICY & CURRENT DEVELOPMENTS

Cover what happened this week in food and farm policy. Organize by topic area where relevant:

**Ethanol / RFS**
- Any EPA volume obligation announcements, court rulings, or Congressional activity?
- Any new data on land use, fuel price impacts, or EV/ethanol market dynamics?

**Farm Subsidies & The Farm Bill**
- Farm Bill progress, commodity program changes, conservation title developments?
- Any new USDA data on farm income, subsidy distribution, or crop insurance?

**Organic & Regenerative (ROC)**
- Sales data, acreage trends, transition program funding, USDA organic actions?
- Any new corporate "regenerative" claims worth flagging as greenwashing?

**Livestock & Feedlots**
- Methane/GHG data releases, feedlot regulation, grass-fed market developments?

**UPF & Food Industry**
- Litigation updates (SF municipal lawsuit, Martinez v. Kraft Heinz, others)?
- FDA/dietary guideline actions, industry lobbying moves, labeling developments?

**Chemicals & Pesticides**
- Glyphosate litigation, PFAS updates, EPA pesticide decisions, new safety research?

**Bottom Line:** A 2-3 sentence editorial summary. What is the most important development this week for the book's core argument?

---

## PART B: RESEARCH & SCIENCE

Highlight new studies, reports, data releases, or academic publications:

For each item:
- **[Author/Institution/Journal]: [Title or finding]** — 2-3 sentence summary of what was found
- **Relevance to the book:** 1-2 sentences connecting this to the thesis
- **Key number or quote:** The single most citable data point or line

Flag any items that update the book's core statistics (cropland allocation, subsidy concentration,
organic sales, true cost figures, pesticide volumes, UPF health data). New data superseding
existing figures in the book's research memos is high priority.

---

## PART C: BROADER CONTEXT & CONNECTIONS

Draw out 2-3 broader threads from this week's material:

- **International angles:** Any policy moves from Denmark, EU Farm to Fork, Brazil PNAE,
  South Korea, or other countries that model what the U.S. could do?
- **Historical parallels:** Does anything this week echo the tobacco playbook pattern
  (science → litigation → internal documents → settlement → norm shift)?
- **Connecting threads:** Links between items that aren't obvious — e.g., an ethanol
  story connecting to a food access story connecting to a subsidy story.

End with **"This Week's Research Priority"** — one specific, concrete action the author
should take based on this week's material: a source to contact, a dataset to pull,
a chapter angle to strengthen, a counterargument to address, or a new story to pursue.

---

If no relevant content was found in a section, say so briefly and provide useful background
context on ongoing developments in that area instead. Always produce a substantive report."""


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
