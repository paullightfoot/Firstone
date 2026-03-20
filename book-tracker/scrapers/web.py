"""
Supplemental web search using Brave Search API (optional).
Set BRAVE_SEARCH_API_KEY env var to enable.

Free tier: 2,000 queries/month.
Sign up at: https://api.search.brave.com/
"""

import os
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup


WEB_SEARCH_QUERIES = [
    # High-priority targeted searches
    "corn ethanol land use misallocation 2026",
    "industrial agriculture corporate concentration 2026",
    "regenerative agriculture commercial scale proof 2026",
    "Farm Bill subsidy reform 2026",
    "organic farming supply demand gap 2026",
    "CAFO environmental violations 2026",
    "Cargill ADM Bunge profits 2026",
    "Renewable Fuel Standard reform 2026",
    "synthetic fertilizer climate impact 2026",
    "grass fed beef nutrition comparison 2026",
    "rural community farm consolidation 2026",
    "food system chronic disease mortality 2026",
    "farmland investment financialization 2026",
    "Monsanto Bayer seed monopoly 2026",
    "Gulf Mexico dead zone agriculture 2026",
]


def _clean_snippet(raw: str) -> str:
    if not raw:
        return ""
    try:
        return BeautifulSoup(raw, "lxml").get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw).strip()


def _brave_search(query: str, api_key: str) -> list[dict]:
    items = []
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            params={
                "q": query,
                "count": 5,
                "freshness": "pw",  # past week
                "text_decorations": False,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        for result in resp.json().get("web", {}).get("results", []):
            title = result.get("title", "").strip()
            url = result.get("url", "")
            description = _clean_snippet(result.get("description", ""))
            age = result.get("age", "")  # e.g. "2 days ago"

            # Try to parse approximate date from "age" field
            date = None
            if age:
                now = datetime.now()
                try:
                    if "hour" in age or "minute" in age:
                        date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif "day" in age:
                        days = int(re.search(r"\d+", age).group())
                        from datetime import timedelta
                        date = now - timedelta(days=days)
                    elif "week" in age:
                        weeks = int(re.search(r"\d+", age).group())
                        from datetime import timedelta
                        date = now - timedelta(weeks=weeks)
                except Exception:
                    pass

            if not title or not url:
                continue

            items.append({
                "source": "Web Search",
                "source_category": "web",
                "source_lean": "neutral",
                "title": title,
                "url": url,
                "date": date,
                "content_type": "article",
                "content": f"{title}. {description}" if description else title,
            })

    except Exception as e:
        print(f"    [Brave err] '{query[:40]}...': {e}")

    return items


def scrape_web(since: datetime) -> list[dict]:
    """Run targeted web searches via Brave Search API."""
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not api_key:
        print("    [web] BRAVE_SEARCH_API_KEY not set — skipping web search")
        return []

    all_items = []
    seen_urls = set()

    for query in WEB_SEARCH_QUERIES:
        for item in _brave_search(query, api_key):
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                all_items.append(item)

    print(f"    [web search] {len(all_items)} results")
    return all_items
