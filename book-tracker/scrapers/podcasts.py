"""
Scrape podcast episodes relevant to The American Farmland System.

Primary method: RSS feeds for known relevant podcasts.
Optional: Listen Notes API (set LISTENNOTES_API_KEY env var for broader search).
"""

import os
import re
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime


PODCAST_KEYWORDS = [
    "corn ethanol", "ethanol", "biofuel", "RFS", "renewable fuel standard",
    "synthetic fertilizer", "Haber-Bosch", "nitrogen fertilizer", "glyphosate",
    "CAFO", "factory farm", "feedlot", "industrial livestock", "industrial beef",
    "Cargill", "ADM", "Bunge", "Monsanto", "Syngenta", "Bayer crop", "Big Ag",
    "JBS", "Tyson", "Cattlemen",
    "farm subsidy", "crop subsidy", "Farm Bill", "agricultural subsidy",
    "regenerative agriculture", "regenerative organic", "cover crop", "soil health",
    "no-till", "adaptive grazing", "grass-fed", "grass fed", "Kernza",
    "food system", "industrial agriculture", "industrial farming",
    "food insecurity", "ultra-processed",
    "farmland", "cropland", "organic farming", "organic food",
    "Gulf dead zone", "nitrogen runoff", "pollinator", "bee colony",
    "soil carbon", "soil microbiome", "topsoil",
    "rural community", "farm income", "family farm", "farm consolidation",
    "diet-related disease", "gut microbiome", "nutrition density",
    "Patagonia Provisions", "Wild Idea Buffalo", "regenerative seafood",
    "agricultural lobby", "farm lobby", "food lobby",
    "farmland investment", "farmland financialization",
]

_KEYWORDS_LOWER = list({kw.lower() for kw in PODCAST_KEYWORDS})


# RSS feeds for known relevant podcasts
PODCAST_FEEDS = [
    # ── Food Systems / Sustainable Agriculture ─────────────────────────────
    {"name": "Regenerative Agriculture Podcast",
     "url": "https://www.regenerativeagriculturepodcast.com/feed.xml",
     "category": "podcast"},
    {"name": "Sustainable Dish",
     "url": "https://sustainabledish.com/feed/podcast",
     "category": "podcast"},
    {"name": "Sacred Cow Podcast",
     "url": "https://www.sacredcow.info/podcast-feed",
     "category": "podcast"},
    {"name": "Kiss the Ground Podcast",
     "url": "https://kisstheground.com/feed/podcast",
     "category": "podcast"},
    {"name": "Farmer's Footprint Podcast",
     "url": "https://farmersfootprint.us/feed/podcast",
     "category": "podcast"},
    {"name": "Acres U.S.A. Podcast",
     "url": "https://www.acresusa.com/feed/podcast",
     "category": "podcast"},
    {"name": "Soil Health Academy Podcast",
     "url": "https://soilhealthacademy.org/feed/podcast",
     "category": "podcast"},
    {"name": "FERN's Ag Insider Podcast",
     "url": "https://thefern.org/feed/podcast",
     "category": "podcast"},
    {"name": "Farm Aid Podcast",
     "url": "https://www.farmaid.org/feed/podcast",
     "category": "podcast"},
    {"name": "No-Till Farmer Podcast",
     "url": "https://www.no-tillfarmer.com/rss/podcast",
     "category": "podcast"},
    # ── Environmental / Climate ────────────────────────────────────────────
    {"name": "How to Save a Planet",
     "url": "https://feeds.simplecast.com/Y4N8p4dJ",
     "category": "podcast"},
    {"name": "Bioneers Podcast",
     "url": "https://bioneers.org/feed/podcast",
     "category": "podcast"},
    # ── Nutrition / Health ─────────────────────────────────────────────────
    {"name": "Food Sleuth Radio",
     "url": "https://www.foodsleuth.com/feed/podcast",
     "category": "podcast"},
    # ── Policy / Economics ─────────────────────────────────────────────────
    {"name": "EconTalk",
     "url": "https://feeds.simplecast.com/wgl4xEgL",
     "category": "podcast"},
    {"name": "Planet Money",
     "url": "https://feeds.npr.org/510289/podcast.xml",
     "category": "podcast"},
    {"name": "Freakonomics Radio",
     "url": "https://feeds.simplecast.com/Y4N8p4dJ",
     "category": "podcast"},
]


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


def _scrape_podcast_feed(feed_config: dict, since: datetime) -> list[dict]:
    items = []
    try:
        feed = feedparser.parse(
            feed_config["url"],
            agent="Mozilla/5.0 BookResearchTracker/1.0",
        )
        if not feed.entries:
            print(f"    [no entries] {feed_config['name']}")
            return []

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            summary_raw = (entry.get("summary", "") or
                           entry.get("description", "") or
                           entry.get("itunes_summary", ""))
            summary = _clean_html(summary_raw)
            combined = f"{title} {summary}"

            if not _is_relevant(combined):
                continue

            date = _parse_date(entry)
            if date and date < since:
                continue

            items.append({
                "source": feed_config["name"],
                "source_category": "podcast",
                "source_lean": "neutral",
                "title": title,
                "url": entry.get("link", feed_config["url"]),
                "date": date,
                "content_type": "podcast",
                "content": f"{title}. {summary[:1000]}" if summary else title,
            })

        count_label = f"{len(items)} relevant" if items else f"0 relevant (of {len(feed.entries)})"
        print(f"    [ok] {feed_config['name']}: {count_label}")

    except Exception as e:
        print(f"    [err] {feed_config['name']}: {e}")

    return items


def _search_listennotes(since: datetime) -> list[dict]:
    """Search Listen Notes API if API key is available."""
    api_key = os.environ.get("LISTENNOTES_API_KEY")
    if not api_key:
        return []

    search_queries = [
        "regenerative agriculture",
        "industrial farming food system",
        "corn ethanol farm policy",
        "soil health food",
        "factory farming CAFO",
        "farm subsidy food policy",
    ]

    since_ms = int(since.timestamp() * 1000)
    items = []
    seen_urls = set()

    for query in search_queries:
        try:
            resp = requests.get(
                "https://listen-api.listennotes.com/api/v2/search",
                headers={"X-ListenAPI-Key": api_key},
                params={
                    "q": query,
                    "type": "episode",
                    "published_after": since_ms,
                    "len_min": 10,
                    "sort_by_date": 1,
                    "page_size": 10,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                continue

            data = resp.json()
            for ep in data.get("results", []):
                url = ep.get("listennotes_url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title = ep.get("title_original", "")
                description = _clean_html(ep.get("description_original", ""))
                pub_ms = ep.get("pub_date_ms", 0)
                pub_date = datetime.fromtimestamp(pub_ms / 1000) if pub_ms else None

                combined = f"{title} {description}"
                if not _is_relevant(combined):
                    continue

                items.append({
                    "source": ep.get("podcast", {}).get("title_original", "Podcast"),
                    "source_category": "podcast",
                    "source_lean": "neutral",
                    "title": title,
                    "url": url,
                    "date": pub_date,
                    "content_type": "podcast",
                    "content": f"{title}. {description[:1000]}" if description else title,
                })

        except Exception as e:
            print(f"    [Listen Notes err] query='{query}': {e}")

    if items:
        print(f"    [Listen Notes API] {len(items)} relevant episodes")
    return items


def scrape_podcasts(since: datetime) -> list[dict]:
    """Scrape podcast RSS feeds + optional Listen Notes API."""
    all_items = []
    for feed_config in PODCAST_FEEDS:
        all_items.extend(_scrape_podcast_feed(feed_config, since))
    all_items.extend(_search_listennotes(since))
    return all_items
