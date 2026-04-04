"""
Research & academic sources scraper — journals, think tanks, university
programs, and research institutions relevant to the book topics.

TODO: Populate RSS_FEEDS and SOURCE_URLS once book topics are confirmed.
"""

import re
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError


# ---------------------------------------------------------------------------
# RESEARCH RSS FEEDS — fill in after book topics are confirmed
# ---------------------------------------------------------------------------

RSS_FEEDS: list[dict] = [
    # Example structure:
    # {
    #     "name": "Journal of Rural Studies",
    #     "url": "https://rss.sciencedirect.com/publication/science/07430167",
    # },
    # {
    #     "name": "Land Use Policy (journal)",
    #     "url": "https://rss.sciencedirect.com/publication/science/02648377",
    # },
    # {
    #     "name": "American Farmland Trust Blog",
    #     "url": "https://farmland.org/feed/",
    # },
]

SOURCE_URLS: list[dict] = [
    # Example structure:
    # {
    #     "name": "USDA National Agricultural Library",
    #     "url": "https://www.nal.usda.gov/",
    # },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_url(url: str, timeout: int = 15) -> str | None:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (BookResearchTracker/1.0)"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    [WARN] Failed to fetch {url}: {e}")
        return None


def _parse_rss(xml_text: str, source_name: str, since: datetime) -> list[dict]:
    items = []
    blocks = re.findall(r"<(?:item|entry)>(.*?)</(?:item|entry)>", xml_text, re.DOTALL)
    for block in blocks:
        title = re.search(r"<title[^>]*>(.*?)</title>", block, re.DOTALL)
        link = re.search(r"<link[^>]*>(.*?)</link>|<link[^>]+href=['\"]([^'\"]+)['\"]", block, re.DOTALL)
        pub_date = re.search(r"<(?:pubDate|updated|published)[^>]*>(.*?)</(?:pubDate|updated|published)>", block, re.DOTALL)
        description = re.search(r"<(?:description|summary|content)[^>]*>(.*?)</(?:description|summary|content)>", block, re.DOTALL)

        title_text = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else ""
        link_text = (link.group(1) or link.group(2) or "").strip() if link else ""
        desc_text = re.sub(r"<[^>]+>", "", description.group(1)).strip()[:600] if description else ""

        item_date = None
        if pub_date:
            date_str = pub_date.group(1).strip()
            for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    item_date = datetime.strptime(date_str[:25], fmt).replace(tzinfo=None)
                    break
                except ValueError:
                    continue

        if item_date and item_date < since:
            continue

        if title_text:
            items.append({
                "source": source_name,
                "title": title_text,
                "url": link_text,
                "date": item_date or datetime.now(),
                "content": desc_text,
            })

    return items


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scrape_research_sources(since: datetime) -> list[dict]:
    """
    Scrape academic journals, think tanks, and research institutions.
    Returns a list of item dicts with keys: source, title, url, date, content.
    """
    all_items: list[dict] = []

    if not RSS_FEEDS and not SOURCE_URLS:
        print("    [INFO] No research sources configured yet — add feeds to RSS_FEEDS")
        return all_items

    for feed in RSS_FEEDS:
        print(f"    Fetching: {feed['name']} ...")
        xml = _fetch_url(feed["url"])
        if xml:
            items = _parse_rss(xml, feed["name"], since)
            print(f"      → {len(items)} items")
            all_items.extend(items)

    return all_items
