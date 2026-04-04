"""
Primary sources scraper — government agencies, USDA, land trusts,
policy bodies, and official databases relevant to the book research.

TODO: Populate SOURCE_URLS with specific sites once book topics are confirmed.
"""

import re
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# SOURCE REGISTRY — fill in after book topics are confirmed
# ---------------------------------------------------------------------------

SOURCE_URLS: list[dict] = [
    # Example structure:
    # {
    #     "name": "USDA ERS - Farmland",
    #     "url": "https://www.ers.usda.gov/topics/farm-economy/land-use-land-value-tenure/",
    #     "type": "rss_or_html",
    # },
]

RSS_FEEDS: list[dict] = [
    # Example structure:
    # {
    #     "name": "USDA News",
    #     "url": "https://www.usda.gov/rss/home.xml",
    # },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self._skip_tags = {"script", "style", "nav", "footer", "header"}
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            text = data.strip()
            if text:
                self.text_parts.append(text)

    def get_text(self):
        return " ".join(self.text_parts)


def _fetch_url(url: str, timeout: int = 15) -> str | None:
    """Fetch a URL and return the raw content, or None on failure."""
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (BookResearchTracker/1.0)"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, Exception) as e:
        print(f"    [WARN] Failed to fetch {url}: {e}")
        return None


def _parse_rss(xml_text: str, source_name: str, since: datetime) -> list[dict]:
    """Parse an RSS/Atom feed and return items newer than `since`."""
    items = []
    # Find all <item> or <entry> blocks
    blocks = re.findall(r"<(?:item|entry)>(.*?)</(?:item|entry)>", xml_text, re.DOTALL)
    for block in blocks:
        title = re.search(r"<title[^>]*>(.*?)</title>", block, re.DOTALL)
        link = re.search(r"<link[^>]*>(.*?)</link>|<link[^>]+href=['\"]([^'\"]+)['\"]", block, re.DOTALL)
        pub_date = re.search(r"<(?:pubDate|updated|published)[^>]*>(.*?)</(?:pubDate|updated|published)>", block, re.DOTALL)
        description = re.search(r"<(?:description|summary|content)[^>]*>(.*?)</(?:description|summary|content)>", block, re.DOTALL)

        title_text = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else ""
        link_text = (link.group(1) or link.group(2) or "").strip() if link else ""
        desc_text = re.sub(r"<[^>]+>", "", description.group(1)).strip()[:600] if description else ""

        # Parse date
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

def scrape_primary_sources(since: datetime) -> list[dict]:
    """
    Scrape government agencies, policy bodies, and official databases.
    Returns a list of item dicts with keys: source, title, url, date, content.
    """
    all_items: list[dict] = []

    if not SOURCE_URLS and not RSS_FEEDS:
        print("    [INFO] No primary sources configured yet — add URLs to SOURCE_URLS / RSS_FEEDS")
        return all_items

    # Scrape RSS feeds
    for feed in RSS_FEEDS:
        print(f"    Fetching RSS: {feed['name']} ...")
        xml = _fetch_url(feed["url"])
        if xml:
            items = _parse_rss(xml, feed["name"], since)
            print(f"      → {len(items)} items")
            all_items.extend(items)

    # Scrape HTML sources
    for source in SOURCE_URLS:
        print(f"    Fetching: {source['name']} ...")
        html = _fetch_url(source["url"])
        if html:
            extractor = _TextExtractor()
            extractor.feed(html)
            text = extractor.get_text()[:1000]
            all_items.append({
                "source": source["name"],
                "title": source["name"],
                "url": source["url"],
                "date": datetime.now(),
                "content": text,
            })

    return all_items
