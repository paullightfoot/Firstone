"""
Scrape global urbanist publications and research sources for:
- Housing density policy wins
- Public transit improvements
- Data/rankings
- Research and analysis

RSS feeds from: Planetizen, Next City, Strong Towns, The Urbanist,
Streetsblog USA, Streetsblog SF, Sightline Institute, City Observatory,
Bloomberg CityLab, The Atlantic CityLab archive.
"""

import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
import re

HOUSING_KEYWORDS = [
    "housing", "zoning", "density", "upzone", "apartment", "multifamily",
    "adu", "accessory dwelling", "affordable housing", "social housing",
    "yimby", "infill", "missing middle", "mixed use", "mixed-use",
    "inclusionary", "rent control", "housing element", "rezone",
    "single family", "single-family", "townhouse", "condo",
    "housing shortage", "housing crisis", "housing supply",
]

TRANSIT_KEYWORDS = [
    "transit", "bus rapid transit", "brt", "light rail", "subway", "metro",
    "bike lane", "protected lane", "pedestrian", "car-free", "car free",
    "walkable", "walkability", "transit-oriented", "tod", "complete streets",
    "e-bike", "bikeshare", "scooter", "ferry", "rail", "tram", "streetcar",
    "park and ride", "congestion pricing", "low traffic neighbourhood",
    "road diet", "vision zero", "traffic calming",
]

ALL_KEYWORDS = HOUSING_KEYWORDS + TRANSIT_KEYWORDS

# RSS feed sources with descriptions
RSS_FEEDS = [
    {
        "name": "Planetizen",
        "url": "https://www.planetizen.com/rss",
        "focus": "Urban planning news and analysis",
    },
    {
        "name": "Next City",
        "url": "https://nextcity.org/feed",
        "focus": "Urban policy and solutions",
    },
    {
        "name": "Strong Towns",
        "url": "https://www.strongtowns.org/journal?format=rss",
        "focus": "Financially resilient cities",
    },
    {
        "name": "The Urbanist",
        "url": "https://www.theurbanist.org/feed",
        "focus": "Seattle-area urbanist policy",
    },
    {
        "name": "Streetsblog USA",
        "url": "https://usa.streetsblog.org/feed",
        "focus": "National streets and transit news",
    },
    {
        "name": "Streetsblog SF",
        "url": "https://sf.streetsblog.org/feed",
        "focus": "Bay Area streets and transit (closest to Mill Valley)",
    },
    {
        "name": "Sightline Institute",
        "url": "https://www.sightline.org/feed/",
        "focus": "Pacific Northwest sustainability and housing",
    },
    {
        "name": "City Observatory",
        "url": "https://cityobservatory.org/feed/",
        "focus": "Urban policy research and analysis",
    },
    {
        "name": "Curbed",
        "url": "https://www.curbed.com/rss/index.xml",
        "focus": "Real estate and urban design",
    },
    {
        "name": "CityLab / Bloomberg Cities",
        "url": "https://www.bloomberg.com/feeds/podcasts/citylab.xml",
        "focus": "Global urban innovation",
    },
    {
        "name": "YIMBY Action",
        "url": "https://yimbyaction.org/feed/",
        "focus": "Pro-housing advocacy",
    },
    {
        "name": "Transit Center",
        "url": "https://transitcenter.org/feed/",
        "focus": "US public transit advocacy and research",
    },
]


def scrape_global_cities(since: datetime) -> list[dict]:
    """Scrape all global urbanist RSS feeds and return relevant items."""
    items = []
    for feed_config in RSS_FEEDS:
        items.extend(_scrape_feed(feed_config, since))
    return items


def _is_relevant(text: str) -> bool:
    """Check if text contains housing or transit keywords."""
    t = text.lower()
    return any(kw in t for kw in ALL_KEYWORDS)


def _parse_feed_date(entry) -> datetime | None:
    pub = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub:
        try:
            return datetime(*pub[:6])
        except Exception:
            pass
    return None


def _clean_html(html: str) -> str:
    """Strip HTML tags and return plain text."""
    if not html:
        return ""
    try:
        return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html).strip()


def _scrape_feed(feed_config: dict, since: datetime) -> list[dict]:
    """Scrape a single RSS feed and return relevant items since the given date."""
    items = []
    try:
        feed = feedparser.parse(
            feed_config["url"],
            agent="Mozilla/5.0 MillValleyTracker/1.0",
            request_headers={"Accept": "application/rss+xml, application/xml, */*"},
        )
        if not feed.entries:
            print(f"  [no entries] {feed_config['name']} ({feed_config['url']})")
            return []

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            summary_raw = entry.get("summary", "") or entry.get("description", "")
            summary = _clean_html(summary_raw)
            tags = " ".join(
                t.get("term", "") for t in entry.get("tags", [])
            )
            text = f"{title} {summary} {tags}"

            if not _is_relevant(text):
                continue

            date = _parse_feed_date(entry)
            if date and date < since:
                continue

            # Categorize the item
            t_lower = text.lower()
            categories = []
            if any(kw in t_lower for kw in HOUSING_KEYWORDS):
                categories.append("housing")
            if any(kw in t_lower for kw in TRANSIT_KEYWORDS):
                categories.append("transit")

            items.append({
                "source": feed_config["name"],
                "source_focus": feed_config["focus"],
                "title": title,
                "url": entry.get("link", feed_config["url"]),
                "date": date,
                "type": "global_news",
                "content": f"{title}. {summary[:800]}" if summary else title,
                "categories": categories,
                "relevant": True,
            })

        if items:
            print(f"  [ok] {feed_config['name']}: {len(items)} relevant items")
        else:
            print(f"  [ok] {feed_config['name']}: 0 relevant items (out of {len(feed.entries)} total)")

    except Exception as e:
        print(f"  [feed error] {feed_config['name']}: {e}")

    return items
