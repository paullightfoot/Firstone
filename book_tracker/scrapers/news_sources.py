"""
News sources scraper — national and regional newspapers, trade publications,
and online outlets covering the book's subject matter.

TODO: Populate RSS_FEEDS with specific outlets once book topics are confirmed.
"""

import re
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError


# ---------------------------------------------------------------------------
# NEWS RSS FEEDS — fill in after book topics are confirmed
# ---------------------------------------------------------------------------

RSS_FEEDS: list[dict] = [
    # Example structure:
    # {
    #     "name": "The Land Report",
    #     "url": "https://landreport.com/feed/",
    # },
    # {
    #     "name": "Civil Eats",
    #     "url": "https://civileats.com/feed/",
    # },
    # {
    #     "name": "High Country News",
    #     "url": "https://www.hcn.org/rss.xml",
    # },
]


# ---------------------------------------------------------------------------
# Helpers (shared logic duplicated here to keep scrapers self-contained)
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

def scrape_news_sources(since: datetime) -> list[dict]:
    """
    Scrape news outlets and trade publications.
    Returns a list of item dicts with keys: source, title, url, date, content.
    """
    all_items: list[dict] = []

    if not RSS_FEEDS:
        print("    [INFO] No news sources configured yet — add feeds to RSS_FEEDS")
        return all_items

    for feed in RSS_FEEDS:
        print(f"    Fetching: {feed['name']} ...")
        xml = _fetch_url(feed["url"])
        if xml:
            items = _parse_rss(xml, feed["name"], since)
            print(f"      → {len(items)} items")
            all_items.extend(items)

    return all_items
