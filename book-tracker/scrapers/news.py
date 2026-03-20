"""
Scrape RSS feeds from ~60+ news, journalism, advocacy, and trade sources
relevant to The American Farmland System book.

Covers: investigative ag journalism, environmental news, trade press,
advocacy organizations (reform and industry), academic institutions.
"""

import feedparser
import re
from bs4 import BeautifulSoup
from datetime import datetime


# ---------------------------------------------------------------------------
# Keywords — any match pulls the item in for Claude to score
# ---------------------------------------------------------------------------

KEYWORDS = [
    # Core thesis
    "farmland", "cropland", "agricultural land", "farm land",
    # Ethanol / energy
    "corn ethanol", "ethanol", "biofuel", "renewable fuel standard", "RFS",
    "ethanol mandate", "ethanol plant", "cellulosic", "E15", "E10",
    # Synthetic fertilizer
    "synthetic fertilizer", "nitrogen fertilizer", "Haber-Bosch",
    "anhydrous ammonia", "urea fertilizer", "nitrous oxide emission",
    "fertilizer runoff", "glyphosate", "pesticide", "herbicide", "agrochemical",
    # Industrial livestock
    "CAFO", "factory farm", "feedlot", "industrial livestock",
    "concentrated animal feeding", "confined animal", "industrial beef",
    "industrial pork", "industrial poultry", "industrial chicken",
    # Corporate players
    "Cargill", "Archer Daniels Midland", "ADM grain", "Bunge grain",
    "Syngenta", "Monsanto", "Bayer crop", "DuPont Pioneer",
    "John Deere", "seed monopoly", "agribusiness", "Big Ag",
    "JBS beef", "Tyson Foods", "National Cattlemen", "Cattlemen's Association",
    # Subsidies / policy
    "farm subsidy", "crop subsidy", "Farm Bill", "crop insurance subsidy",
    "agricultural subsidy", "commodity subsidy", "corn subsidy", "soy subsidy",
    "SNAP reform", "food policy", "agricultural policy",
    # Regenerative / organic
    "regenerative agriculture", "regenerative organic", "cover crop",
    "soil health", "no-till", "adaptive grazing", "AMP grazing",
    "grass-fed", "grass fed", "pasture-raised", "regenerative ranching",
    "Kernza", "perennial grain", "Rodale Institute", "Savory Institute",
    "regenerative organic certified", "ROC certified",
    # Food systems
    "food system", "industrial agriculture", "industrial farming",
    "food desert", "food insecurity", "ultra-processed food",
    "processed food health", "organic farming", "organic food",
    "organic demand", "organic supply",
    # Environmental
    "Gulf of Mexico dead zone", "nitrogen runoff", "agricultural runoff",
    "agricultural pollution", "farmland biodiversity", "pollinator decline",
    "bee colony collapse", "insect decline", "bird decline agriculture",
    "soil degradation", "topsoil loss", "soil carbon", "soil microbiome",
    # Rural / social
    "rural community", "farm income", "small farmer", "family farm",
    "farm consolidation", "rural depopulation", "farmer suicide",
    "farm bankruptcy", "rural economy",
    # Health
    "diet-related disease", "chronic disease food", "gut microbiome",
    "nutrition density", "food mortality", "food-related death",
    "obesity food system", "diabetes food", "heart disease diet",
    # Water
    "Colorado River agriculture", "agricultural water use", "irrigation water",
    "farm water", "water rights farming",
    # Market / economics
    "farmland financialization", "farmland investment", "crony capitalism",
    "agricultural monopoly", "food monopoly", "organic market failure",
    # Specific cases
    "Patagonia Provisions", "Wild Idea Buffalo", "Denmark fertilizer",
    "Copenhagen organic", "regenerative seafood",
    # Lobbying
    "agricultural lobby", "farm lobby", "food industry lobby",
    "Renewable Fuels Association", "Growth Energy ethanol",
]

# De-duplicate and lowercase for matching
_KEYWORDS_LOWER = list({kw.lower() for kw in KEYWORDS})


# ---------------------------------------------------------------------------
# RSS Feed Registry — 60+ sources
# ---------------------------------------------------------------------------

RSS_FEEDS = [
    # ── Investigative & Specialty Journalism ──────────────────────────────
    {"name": "Civil Eats", "url": "https://civileats.com/feed/",
     "category": "journalism", "lean": "reform"},
    {"name": "FERN (Food & Environment Reporting Network)", "url": "https://thefern.org/feed/",
     "category": "journalism", "lean": "reform"},
    {"name": "Modern Farmer", "url": "https://modernfarmer.com/feed/",
     "category": "journalism", "lean": "neutral"},
    {"name": "The Counter", "url": "https://thecounter.org/feed/",
     "category": "journalism", "lean": "reform"},
    {"name": "Agri-Pulse", "url": "https://www.agri-pulse.com/rss/all.rss",
     "category": "trade", "lean": "neutral"},
    {"name": "Harvest Public Media", "url": "https://www.harvestpublicmedia.org/feed/",
     "category": "journalism", "lean": "neutral"},
    {"name": "Morning Ag Clips", "url": "https://www.morningagclips.com/feed/",
     "category": "trade", "lean": "neutral"},
    {"name": "Midwest Center for Investigative Reporting", "url": "https://investigatemidwest.org/feed/",
     "category": "journalism", "lean": "reform"},
    {"name": "Food Politics (Marion Nestle)", "url": "https://www.foodpolitics.com/feed/",
     "category": "blog", "lean": "reform"},
    {"name": "AgFunder News", "url": "https://agfundernews.com/feed/",
     "category": "business", "lean": "neutral"},
    {"name": "The Spoon", "url": "https://thespoon.tech/feed/",
     "category": "business", "lean": "neutral"},
    {"name": "Food Navigator USA", "url": "https://www.foodnavigator-usa.com/rss/editorial/",
     "category": "trade", "lean": "neutral"},

    # ── Environmental & Climate ────────────────────────────────────────────
    {"name": "Grist (Food)", "url": "https://grist.org/tag/food/feed/",
     "category": "journalism", "lean": "reform"},
    {"name": "Inside Climate News", "url": "https://insideclimatenews.org/feed/",
     "category": "journalism", "lean": "reform"},
    {"name": "Yale Environment 360", "url": "https://e360.yale.edu/feed",
     "category": "journalism", "lean": "reform"},
    {"name": "Mongabay", "url": "https://news.mongabay.com/feed/",
     "category": "journalism", "lean": "reform"},
    {"name": "Ensia", "url": "https://ensia.com/feed/",
     "category": "journalism", "lean": "reform"},
    {"name": "GreenBiz", "url": "https://www.greenbiz.com/rss.xml",
     "category": "business", "lean": "reform"},

    # ── General News (Ag/Food Coverage) ───────────────────────────────────
    {"name": "The Guardian (Food)", "url": "https://www.theguardian.com/food/rss",
     "category": "journalism", "lean": "reform"},
    {"name": "The Guardian (Environment)", "url": "https://www.theguardian.com/environment/rss",
     "category": "journalism", "lean": "reform"},
    {"name": "Mother Jones (Environment)", "url": "https://www.motherjones.com/tag/environment/feed/",
     "category": "journalism", "lean": "reform"},
    {"name": "Vox (Future Perfect)", "url": "https://www.vox.com/future-perfect/rss/index.xml",
     "category": "journalism", "lean": "reform"},
    {"name": "Reuters (Environment)", "url": "https://feeds.reuters.com/reuters/environmentNews",
     "category": "journalism", "lean": "neutral"},

    # ── Farm & Trade Press ─────────────────────────────────────────────────
    {"name": "Farm Progress", "url": "https://www.farmprogress.com/rss.xml",
     "category": "trade", "lean": "industry"},
    {"name": "AgWeb", "url": "https://www.agweb.com/rss/news",
     "category": "trade", "lean": "industry"},
    {"name": "Successful Farming", "url": "https://www.agriculture.com/rss/news.xml",
     "category": "trade", "lean": "industry"},
    {"name": "Farm Journal", "url": "https://www.farmjournal.com/rss/",
     "category": "trade", "lean": "industry"},

    # ── Reform-Oriented Advocacy ───────────────────────────────────────────
    {"name": "EWG (Environmental Working Group)", "url": "https://www.ewg.org/feed",
     "category": "advocacy", "lean": "reform"},
    {"name": "NRDC", "url": "https://www.nrdc.org/rss.xml",
     "category": "advocacy", "lean": "reform"},
    {"name": "Food & Water Watch", "url": "https://www.foodandwaterwatch.org/feeds/all",
     "category": "advocacy", "lean": "reform"},
    {"name": "Rodale Institute", "url": "https://rodaleinstitute.org/feed/",
     "category": "research", "lean": "reform"},
    {"name": "Center for Food Safety", "url": "https://www.centerforfoodsafety.org/feed",
     "category": "advocacy", "lean": "reform"},
    {"name": "Cornucopia Institute", "url": "https://www.cornucopia.org/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "Friends of the Earth", "url": "https://foe.org/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "Center for Rural Affairs", "url": "https://cfra.org/news/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "Farm Aid", "url": "https://www.farmaid.org/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "Land Stewardship Project", "url": "https://www.landstewardshipproject.org/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "American Farmland Trust", "url": "https://farmland.org/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "National Sustainable Agriculture Coalition", "url": "https://sustainableagriculture.net/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "Pesticide Action Network", "url": "https://www.panna.org/feed",
     "category": "advocacy", "lean": "reform"},
    {"name": "Beyond Pesticides", "url": "https://beyondpesticides.org/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "Institute for Agriculture and Trade Policy", "url": "https://www.iatp.org/feed",
     "category": "advocacy", "lean": "reform"},
    {"name": "Organic Trade Association", "url": "https://ota.com/feed",
     "category": "advocacy", "lean": "reform"},
    {"name": "Regenerative Organic Alliance", "url": "https://regenorganic.org/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "Farmers Footprint", "url": "https://farmersfootprint.us/feed/",
     "category": "advocacy", "lean": "reform"},
    {"name": "Savory Institute", "url": "https://savory.global/feed/",
     "category": "research", "lean": "reform"},

    # ── Industry / Conventional (opposing views) ──────────────────────────
    {"name": "American Farm Bureau", "url": "https://www.fb.org/news/rss",
     "category": "advocacy", "lean": "industry"},
    {"name": "Renewable Fuels Association", "url": "https://ethanolrfa.org/feed/",
     "category": "advocacy", "lean": "industry"},
    {"name": "Growth Energy (Ethanol)", "url": "https://growthenergy.org/feed/",
     "category": "advocacy", "lean": "industry"},
    {"name": "National Corn Growers Association", "url": "https://www.ncga.com/feed",
     "category": "advocacy", "lean": "industry"},
    {"name": "American Soybean Association", "url": "https://soygrowers.com/feed/",
     "category": "advocacy", "lean": "industry"},

    # ── Academic & Research ────────────────────────────────────────────────
    {"name": "USDA Economic Research Service", "url": "https://www.ers.usda.gov/rss/",
     "category": "research", "lean": "neutral"},
    {"name": "Tufts Friedman School", "url": "https://nutrition.tufts.edu/news/rss.xml",
     "category": "research", "lean": "neutral"},
    {"name": "Johns Hopkins Center for a Livable Future", "url": "https://clf.jhsph.edu/feed",
     "category": "research", "lean": "reform"},

    # ── Business / Finance ─────────────────────────────────────────────────
    {"name": "FAIRR Initiative", "url": "https://www.fairr.org/feed/",
     "category": "business", "lean": "reform"},
]


# ---------------------------------------------------------------------------
# Core scraping logic
# ---------------------------------------------------------------------------

def _is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _KEYWORDS_LOWER)


def _parse_date(entry) -> datetime | None:
    pub = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub:
        try:
            return datetime(*pub[:6])
        except Exception:
            pass
    return None


def _clean_html(raw: str) -> str:
    if not raw:
        return ""
    try:
        return BeautifulSoup(raw, "lxml").get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw).strip()


def _scrape_feed(feed_config: dict, since: datetime) -> list[dict]:
    items = []
    try:
        feed = feedparser.parse(
            feed_config["url"],
            agent="Mozilla/5.0 BookResearchTracker/1.0",
            request_headers={"Accept": "application/rss+xml, application/xml, */*"},
        )
        if not feed.entries:
            print(f"    [no entries] {feed_config['name']}")
            return []

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            summary_raw = entry.get("summary", "") or entry.get("description", "")
            summary = _clean_html(summary_raw)
            tags = " ".join(t.get("term", "") for t in entry.get("tags", []))
            combined = f"{title} {summary} {tags}"

            if not _is_relevant(combined):
                continue

            date = _parse_date(entry)
            if date and date < since:
                continue

            items.append({
                "source": feed_config["name"],
                "source_category": feed_config["category"],
                "source_lean": feed_config["lean"],
                "title": title,
                "url": entry.get("link", feed_config["url"]),
                "date": date,
                "content_type": "article",
                "content": f"{title}. {summary[:1000]}" if summary else title,
            })

        count_label = f"{len(items)} relevant" if items else f"0 relevant (of {len(feed.entries)})"
        print(f"    [ok] {feed_config['name']}: {count_label}")

    except Exception as e:
        print(f"    [err] {feed_config['name']}: {e}")

    return items


def scrape_news(since: datetime) -> list[dict]:
    """Scrape all RSS feeds. Returns list of raw item dicts."""
    all_items = []
    for feed_config in RSS_FEEDS:
        all_items.extend(_scrape_feed(feed_config, since))
    return all_items
