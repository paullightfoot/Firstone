"""
Scrape local Marin County news sources for Mill Valley housing and transit coverage:
- Marin Independent Journal (marinij.com)
- Patch Mill Valley
- Marin County Board of Supervisors
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as dateparser
import feedparser
import re
import time

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

HOUSING_KEYWORDS = [
    "housing", "zoning", "density", "upzone", "apartment", "multifamily",
    "adu", "accessory dwelling", "affordable", "residential", "development",
    "permit", "housing element", "sb 9", "sb9", "infill", "mixed use",
    "mixed-use", "variance", "conditional use", "rezone", "general plan",
]

TRANSIT_KEYWORDS = [
    "transit", "bus", "transportation", "bicycle", "bike lane", "pedestrian",
    "smart train", "ferry", "marin transit", "golden gate transit", "vision zero",
    "traffic calming", "parking", "complete streets", "walkable", "cycling",
    "mobility", "commute", "carpool", "rideshare", "e-bike",
]

MV_KEYWORDS = [
    "mill valley", "tamalpais", "marin county",
]

ALL_RELEVANT = HOUSING_KEYWORDS + TRANSIT_KEYWORDS


def scrape_local_news(since: datetime) -> list[dict]:
    """Scrape all local news sources."""
    items = []
    items.extend(_scrape_patch(since))
    items.extend(_scrape_marin_ij(since))
    items.extend(_scrape_marin_supervisors(since))
    return items


def _get(url: str, timeout: int = 15) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as e:
        print(f"  [fetch error] {url}: {e}")
        return None


def _is_mv_relevant(text: str) -> bool:
    """Check if text is about Mill Valley area AND housing/transit."""
    t = text.lower()
    is_local = any(kw in t for kw in MV_KEYWORDS)
    is_topic = any(kw in t for kw in ALL_RELEVANT)
    # Accept if clearly local (Mill Valley mentioned) OR just relevant topic in Marin
    return is_topic and (is_local or "marin" in t)


def _parse_feed_date(entry) -> datetime | None:
    pub = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub:
        try:
            return datetime(*pub[:6])
        except Exception:
            pass
    for field in ["published", "updated", "dc_date"]:
        val = entry.get(field, "")
        if val:
            try:
                return dateparser.parse(val, ignoretz=True)
            except Exception:
                pass
    return None


def _scrape_patch(since: datetime) -> list[dict]:
    """Scrape Patch Mill Valley via RSS."""
    items = []
    feed_urls = [
        "https://patch.com/california/mill-valley/rss.xml",
        "https://patch.com/california/marin-county/rss.xml",
    ]
    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = BeautifulSoup(
                    entry.get("summary", "") or entry.get("description", ""), "lxml"
                ).get_text()
                text = f"{title} {summary}"
                if not _is_mv_relevant(text):
                    continue
                date = _parse_feed_date(entry)
                if date and date < since:
                    continue
                items.append({
                    "source": "Patch Mill Valley",
                    "title": title,
                    "url": entry.get("link", feed_url),
                    "date": date,
                    "type": "local_news",
                    "content": f"{title}. {summary[:600]}",
                    "relevant": True,
                })
        except Exception as e:
            print(f"  [patch feed error] {feed_url}: {e}")
        time.sleep(0.5)
    return items


def _scrape_marin_ij(since: datetime) -> list[dict]:
    """Scrape Marin IJ for local housing/transit coverage."""
    items = []

    # Try RSS feeds
    feed_urls = [
        "https://www.marinij.com/feed/",
        "https://www.marinij.com/news/feed/",
        "https://www.marinij.com/local-news/feed/",
    ]
    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                continue
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = BeautifulSoup(
                    entry.get("summary", "") or entry.get("description", ""), "lxml"
                ).get_text()
                text = f"{title} {summary}"
                if not _is_mv_relevant(text):
                    continue
                date = _parse_feed_date(entry)
                if date and date < since:
                    continue
                items.append({
                    "source": "Marin Independent Journal",
                    "title": title,
                    "url": entry.get("link", "https://www.marinij.com"),
                    "date": date,
                    "type": "local_news",
                    "content": f"{title}. {summary[:600]}",
                    "relevant": True,
                })
            if items:
                break
        except Exception as e:
            print(f"  [marin IJ feed error] {feed_url}: {e}")
        time.sleep(0.5)

    # Fallback: scrape the website directly
    if not items:
        for search_url in [
            "https://www.marinij.com/news/local-news/",
            "https://www.marinij.com/",
        ]:
            resp = _get(search_url)
            if not resp:
                continue
            soup = BeautifulSoup(resp.content, "lxml")
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True)
                href = link["href"]
                if not text or len(text) < 15 or len(text) > 200:
                    continue
                if not _is_mv_relevant(text):
                    continue
                full_url = href if href.startswith("http") else f"https://www.marinij.com{href}"
                items.append({
                    "source": "Marin Independent Journal",
                    "title": text,
                    "url": full_url,
                    "date": None,
                    "type": "local_news",
                    "content": text,
                    "relevant": True,
                })
            time.sleep(1)
            if items:
                break

    return items


def _scrape_marin_supervisors(since: datetime) -> list[dict]:
    """Scrape Marin County Board of Supervisors for housing/transit items."""
    items = []

    # Marin County uses an agenda/meeting system
    urls_to_try = [
        "https://www.marincounty.org/depts/bos/supervisors-home/agendas-and-minutes",
        "https://www.marincounty.org/main/county-government/boards-commissions-committees/board-of-supervisors",
    ]
    for url in urls_to_try:
        resp = _get(url)
        if not resp:
            continue
        soup = BeautifulSoup(resp.content, "lxml")

        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            href = link["href"]
            combined = f"{text} {href}".lower()
            if not any(kw in combined for kw in ["agenda", "minutes", "housing", "transit", "transportation"]):
                continue
            if len(text) < 5:
                continue
            date = None
            date_m = re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", combined)
            if date_m:
                try:
                    date = dateparser.parse(date_m.group(0), ignoretz=True)
                except Exception:
                    pass
            if date and date < since:
                continue
            full_url = href if href.startswith("http") else f"https://www.marincounty.org{href}"
            items.append({
                "source": "Marin County Board of Supervisors",
                "title": text[:120],
                "url": full_url,
                "date": date,
                "type": "county_government",
                "content": text,
                "relevant": True,
            })
        time.sleep(1)
        if items:
            break

    return items
