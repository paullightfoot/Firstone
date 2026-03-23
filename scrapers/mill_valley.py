"""
Scrape Mill Valley city government sources:
- City Council agendas and minutes (cityofmillvalley.org)
- Planning Commission agendas and minutes
- Housing Advisory Committee (HAC) agendas and minutes
- Mill Valley Affordable Housing Committee (MVAHC)
- City news/press releases
- Marin Transit and SMART train updates
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
    "adu", "accessory", "affordable", "residential", "development", "permit",
    "general plan", "housing element", "sb 9", "sb9", "yimby", "infill",
    "mixed use", "mixed-use", "variance", "conditional use",
    "housing advisory", "hac", "affordable housing committee", "mvahc",
    "mccauley", "urban carmel", "yolles", "hildebrand", "matthew franklin",
    "patrick kelly", "danielle staude",
]

TRANSIT_KEYWORDS = [
    "transit", "bus", "transportation", "bicycle", "bike", "pedestrian",
    "smart train", "ferry", "marin transit", "golden gate", "vision zero",
    "traffic", "parking", "complete streets", "walkable", "cycling",
    "mobility", "commute",
]

ALL_KEYWORDS = HOUSING_KEYWORDS + TRANSIT_KEYWORDS


def scrape_mill_valley(since: datetime) -> list[dict]:
    """Scrape all Mill Valley government sources. Returns list of items."""
    items = []
    items.extend(_scrape_agenda_center(since))
    items.extend(_scrape_hac(since))
    items.extend(_scrape_affordable_housing_committee(since))
    items.extend(_scrape_city_news(since))
    items.extend(_scrape_marin_transit(since))
    items.extend(_scrape_smart_train(since))
    return items


def _get(url: str, timeout: int = 15) -> requests.Response | None:
    """GET with error handling."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as e:
        print(f"  [fetch error] {url}: {e}")
        return None


def _is_relevant(text: str) -> bool:
    """Check if text contains housing or transit keywords."""
    t = text.lower()
    return any(kw in t for kw in ALL_KEYWORDS)


def _extract_date(text: str) -> datetime | None:
    """Try to extract a date from a string."""
    # Common patterns: "January 15, 2025", "01/15/2025", "2025-01-15"
    patterns = [
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
        r'\b\d{1,2}/\d{1,2}/\d{4}',
        r'\b\d{4}-\d{2}-\d{2}',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return dateparser.parse(m.group(0), ignoretz=True)
            except Exception:
                continue
    return None


def _scrape_agenda_center(since: datetime) -> list[dict]:
    """
    Scrape Mill Valley's CivicPlus Agenda Center for recent meetings.
    Tries the standard CivicPlus URL and fallback paths.
    """
    items = []
    urls_to_try = [
        "https://www.cityofmillvalley.org/AgendaCenter",
        "https://www.cityofmillvalley.org/government/city-council/agendas-minutes",
        "https://www.cityofmillvalley.org/1119/City-Council",
        "https://www.cityofmillvalley.org/government/city-council",
    ]

    found_urls = set()
    for base_url in urls_to_try:
        resp = _get(base_url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.content, "lxml")

        # Look for meeting/agenda links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if not text or len(text) < 5:
                continue

            # Look for agenda, minutes, or packet links
            combined = (text + " " + href).lower()
            if not any(kw in combined for kw in ["agenda", "minutes", "packet", "meeting"]):
                continue

            full_url = href if href.startswith("http") else f"https://www.cityofmillvalley.org{href}"
            if full_url in found_urls:
                continue
            found_urls.add(full_url)

            date = _extract_date(text) or _extract_date(href)

            items.append({
                "source": "Mill Valley City Council / Planning Commission",
                "title": text,
                "url": full_url,
                "date": date,
                "type": "government_meeting",
                "content": text,
                "relevant": _is_relevant(text),
            })

        # Also grab any page text blocks about upcoming items
        for elem in soup.find_all(["h2", "h3", "p", "li"]):
            text = elem.get_text(strip=True)
            if len(text) < 20 or len(text) > 500:
                continue
            if _is_relevant(text):
                date = _extract_date(text)
                if date and date >= since:
                    items.append({
                        "source": "Mill Valley City Website",
                        "title": text[:120],
                        "url": base_url,
                        "date": date,
                        "type": "government_notice",
                        "content": text,
                        "relevant": True,
                    })

        if items:
            break  # Stop trying URLs once we get results
        time.sleep(1)

    # Filter by date
    filtered = []
    for item in items:
        if item.get("date") is None or item["date"] >= since:
            filtered.append(item)

    return filtered


def _scrape_hac(since: datetime) -> list[dict]:
    """
    Scrape Housing Advisory Committee (HAC) agendas, minutes, and meeting pages.
    Members: John McCauley (Chair/Council Liaison), Urban Carmel (Council Liaison),
    Jon Yolles (Planning Commission rep), Greg Hildebrand (Planning Commission Liaison),
    Matthew Franklin (Member at Large).
    Key staff: Patrick Kelly (Director of Planning & Building), Danielle Staude (Planner).
    """
    items = []
    urls_to_try = [
        "https://www.cityofmillvalley.org/government/boards-commissions/housing-advisory-committee",
        "https://www.cityofmillvalley.org/AgendaCenter/Housing-Advisory-Committee",
        "https://www.cityofmillvalley.org/HAC",
        "https://www.cityofmillvalley.org/government/housing-advisory-committee",
        "https://www.cityofmillvalley.org/AgendaCenter",
    ]

    found_urls = set()
    for base_url in urls_to_try:
        resp = _get(base_url)
        if not resp:
            time.sleep(1)
            continue

        soup = BeautifulSoup(resp.content, "lxml")
        page_text = soup.get_text(" ", strip=True).lower()

        # Only dig into this page if it has HAC-related content
        hac_signals = ["housing advisory", "hac", "mccauley", "yolles", "hildebrand", "matthew franklin", "danielle staude"]
        if not any(sig in page_text for sig in hac_signals) and "agendacenter" not in base_url.lower():
            time.sleep(1)
            continue

        # Collect links to agendas/minutes
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            combined = (text + " " + href).lower()
            if not any(kw in combined for kw in ["agenda", "minutes", "packet", "meeting", "housing advisory", "hac"]):
                continue
            full_url = href if href.startswith("http") else f"https://www.cityofmillvalley.org{href}"
            if full_url in found_urls:
                continue
            found_urls.add(full_url)
            date = _extract_date(text) or _extract_date(href)
            if date and date < since:
                continue
            items.append({
                "source": "Mill Valley Housing Advisory Committee (HAC)",
                "title": text,
                "url": full_url,
                "date": date,
                "type": "government_meeting",
                "content": text,
                "relevant": True,
            })

        # Grab inline text blocks mentioning HAC
        for elem in soup.find_all(["h2", "h3", "h4", "p", "li", "div"]):
            text = elem.get_text(separator=" ", strip=True)
            if len(text) < 20 or len(text) > 800:
                continue
            t = text.lower()
            if not any(sig in t for sig in hac_signals) and not _is_relevant(text):
                continue
            date = _extract_date(text)
            if date and date < since:
                continue
            items.append({
                "source": "Mill Valley Housing Advisory Committee (HAC)",
                "title": text[:120],
                "url": base_url,
                "date": date,
                "type": "government_notice",
                "content": text[:600],
                "relevant": True,
            })

        time.sleep(1)
        if items:
            break

    return items


def _scrape_affordable_housing_committee(since: datetime) -> list[dict]:
    """
    Scrape Mill Valley Affordable Housing Committee (MVAHC) content.
    This is a community/advocacy body focused on affordable housing in Mill Valley.
    """
    items = []
    urls_to_try = [
        "https://www.cityofmillvalley.org/government/boards-commissions/affordable-housing-committee",
        "https://www.cityofmillvalley.org/affordable-housing-committee",
        "https://www.cityofmillvalley.org/government/affordable-housing",
        "https://www.cityofmillvalley.org/AgendaCenter",
    ]

    ahc_signals = ["affordable housing committee", "mvahc", "affordable housing"]
    found_urls = set()

    for base_url in urls_to_try:
        resp = _get(base_url)
        if not resp:
            time.sleep(1)
            continue

        soup = BeautifulSoup(resp.content, "lxml")
        page_text = soup.get_text(" ", strip=True).lower()

        if not any(sig in page_text for sig in ahc_signals) and "agendacenter" not in base_url.lower():
            time.sleep(1)
            continue

        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            combined = (text + " " + href).lower()
            if not any(kw in combined for kw in ["agenda", "minutes", "packet", "meeting", "affordable housing"]):
                continue
            full_url = href if href.startswith("http") else f"https://www.cityofmillvalley.org{href}"
            if full_url in found_urls:
                continue
            found_urls.add(full_url)
            date = _extract_date(text) or _extract_date(href)
            if date and date < since:
                continue
            items.append({
                "source": "Mill Valley Affordable Housing Committee",
                "title": text,
                "url": full_url,
                "date": date,
                "type": "government_meeting",
                "content": text,
                "relevant": True,
            })

        for elem in soup.find_all(["h2", "h3", "h4", "p", "li"]):
            text = elem.get_text(separator=" ", strip=True)
            if len(text) < 20 or len(text) > 800:
                continue
            if not any(sig in text.lower() for sig in ahc_signals):
                continue
            date = _extract_date(text)
            if date and date < since:
                continue
            items.append({
                "source": "Mill Valley Affordable Housing Committee",
                "title": text[:120],
                "url": base_url,
                "date": date,
                "type": "government_notice",
                "content": text[:600],
                "relevant": True,
            })

        time.sleep(1)
        if items:
            break

    return items


def _scrape_city_news(since: datetime) -> list[dict]:
    """Scrape Mill Valley city news/announcements."""
    items = []
    urls_to_try = [
        "https://www.cityofmillvalley.org/CivicAlerts.aspx",
        "https://www.cityofmillvalley.org/news",
        "https://www.cityofmillvalley.org/government",
    ]

    for url in urls_to_try:
        resp = _get(url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.content, "lxml")
        for elem in soup.find_all(["article", "div", "li"], class_=re.compile(r"news|alert|post|item", re.I)):
            text = elem.get_text(separator=" ", strip=True)
            if len(text) < 30 or len(text) > 2000:
                continue
            if not _is_relevant(text):
                continue
            date = _extract_date(text)
            if date and date < since:
                continue
            link_tag = elem.find("a", href=True)
            url_item = link_tag["href"] if link_tag else url
            if url_item and not url_item.startswith("http"):
                url_item = f"https://www.cityofmillvalley.org{url_item}"
            items.append({
                "source": "Mill Valley City News",
                "title": text[:120],
                "url": url_item,
                "date": date,
                "type": "city_news",
                "content": text[:800],
                "relevant": True,
            })
        time.sleep(1)

    return items


def _scrape_marin_transit(since: datetime) -> list[dict]:
    """Scrape Marin Transit news for relevant updates."""
    items = []
    feed_url = "https://marintransit.org/feed"
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            text = f"{title} {summary}"
            if not _is_relevant(text):
                continue
            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            date = datetime(*pub[:6]) if pub else None
            if date and date < since:
                continue
            items.append({
                "source": "Marin Transit",
                "title": title,
                "url": entry.get("link", "https://marintransit.org"),
                "date": date,
                "type": "transit_news",
                "content": BeautifulSoup(summary, "lxml").get_text()[:600] if summary else title,
                "relevant": True,
            })
    except Exception as e:
        print(f"  [marin transit feed error] {e}")

    # Also try their news page directly
    resp = _get("https://marintransit.org/news")
    if resp:
        soup = BeautifulSoup(resp.content, "lxml")
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            href = link["href"]
            if not _is_relevant(text) or len(text) < 10:
                continue
            date = _extract_date(text)
            if date and date < since:
                continue
            full_url = href if href.startswith("http") else f"https://marintransit.org{href}"
            items.append({
                "source": "Marin Transit",
                "title": text[:120],
                "url": full_url,
                "date": date,
                "type": "transit_news",
                "content": text,
                "relevant": True,
            })

    return items


def _scrape_smart_train(since: datetime) -> list[dict]:
    """Scrape SMART train news for Marin/Sonoma rail updates."""
    items = []
    resp = _get("https://www.sonomamarintrain.org/news")
    if resp:
        soup = BeautifulSoup(resp.content, "lxml")
        for elem in soup.find_all(["article", "div", "li"], class_=re.compile(r"news|post|item|press", re.I)):
            text = elem.get_text(separator=" ", strip=True)
            if len(text) < 30 or len(text) > 1500:
                continue
            date = _extract_date(text)
            if date and date < since:
                continue
            link_tag = elem.find("a", href=True)
            url_item = link_tag["href"] if link_tag else "https://www.sonomamarintrain.org/news"
            if url_item and not url_item.startswith("http"):
                url_item = f"https://www.sonomamarintrain.org{url_item}"
            items.append({
                "source": "SMART Train",
                "title": text[:120],
                "url": url_item,
                "date": date,
                "type": "transit_news",
                "content": text[:600],
                "relevant": True,
            })

    return items
