"""
Scrape Mill Valley city government sources:
- City Council agendas and minutes (cityofmillvalley.org)
- Planning Commission agendas and minutes
- Housing Advisory Committee (HAC) meetings
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
]

TRANSIT_KEYWORDS = [
    "transit", "bus", "transportation", "bicycle", "bike", "pedestrian",
    "smart train", "ferry", "marin transit", "golden gate", "vision zero",
    "traffic", "parking", "complete streets", "walkable", "cycling",
    "mobility", "commute",
]

# Key committees to always track regardless of other keywords
COMMITTEE_KEYWORDS = [
    "housing advisory committee", "hac",
    "affordable housing committee", "mvahc",
    "mill valley affordable housing",
]

# Key people to track by name
KEY_PEOPLE = [
    "mccauley", "john mccauley",
    "urban carmel", "carmel",
    "jon yolles", "yolles",
    "greg hildebrand", "hildebrand",
    "matthew franklin",
    "patrick kelly",
    "danielle staude", "staude",
]

ALL_KEYWORDS = HOUSING_KEYWORDS + TRANSIT_KEYWORDS + COMMITTEE_KEYWORDS + KEY_PEOPLE


def scrape_mill_valley(since: datetime) -> list[dict]:
    """Scrape all Mill Valley government sources. Returns list of items."""
    items = []
    items.extend(_scrape_agenda_center(since))
    items.extend(_scrape_hac_meetings(since))
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
    """Check if text contains housing, transit, committee, or key people keywords."""
    t = text.lower()
    return any(kw in t for kw in ALL_KEYWORDS)


def _mentions_key_people(text: str) -> list[str]:
    """Return list of key people mentioned in the text."""
    t = text.lower()
    mentioned = []
    people_map = {
        "John McCauley": ["mccauley", "john mccauley"],
        "Urban Carmel": ["urban carmel"],
        "Jon Yolles": ["jon yolles", "yolles"],
        "Greg Hildebrand": ["hildebrand"],
        "Matthew Franklin": ["matthew franklin"],
        "Patrick Kelly": ["patrick kelly"],
        "Danielle Staude": ["danielle staude", "staude"],
    }
    for person, aliases in people_map.items():
        if any(alias in t for alias in aliases):
            mentioned.append(person)
    return mentioned


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

            people = _mentions_key_people(text)
            items.append({
                "source": "Mill Valley City Council / Planning Commission",
                "title": text,
                "url": full_url,
                "date": date,
                "type": "government_meeting",
                "content": text,
                "relevant": _is_relevant(text) or bool(people),
                "key_people_mentioned": people,
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


def _scrape_hac_meetings(since: datetime) -> list[dict]:
    """
    Scrape Housing Advisory Committee (HAC) and Mill Valley Affordable
    Housing Committee (MVAHC) meeting agendas and minutes.
    These are always included regardless of other keyword filters.
    """
    items = []

    # HAC and MVAHC likely live in the Agenda Center alongside other committees
    hac_urls = [
        "https://www.cityofmillvalley.org/AgendaCenter",
        "https://www.cityofmillvalley.org/government/housing-advisory-committee",
        "https://www.cityofmillvalley.org/1137/Housing-Advisory-Committee",
        "https://www.cityofmillvalley.org/government/boards-commissions/housing-advisory-committee",
        "https://www.cityofmillvalley.org/government/affordable-housing-committee",
        "https://www.cityofmillvalley.org/government/housing",
    ]

    hac_terms = [
        "housing advisory", "hac", "affordable housing committee",
        "mvahc", "mill valley affordable housing",
    ]

    found_urls = set()
    for url in hac_urls:
        resp = _get(url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.content, "lxml")

        # Look for any link or text mentioning HAC / affordable housing committee
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            href = link["href"]
            combined = (text + " " + href).lower()

            if not any(term in combined for term in hac_terms):
                continue
            if len(text) < 3:
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
                "type": "committee_meeting",
                "content": text,
                "relevant": True,
                "committee": "HAC",
            })

        # Also scan page text for HAC mentions with context
        full_page_text = soup.get_text(separator=" ")
        for match in re.finditer(
            r'.{0,200}(housing advisory committee|affordable housing committee|mvahc|\bHAC\b).{0,200}',
            full_page_text, re.IGNORECASE
        ):
            snippet = match.group(0).strip()
            if len(snippet) < 20:
                continue
            date = _extract_date(snippet)
            if date and date < since:
                continue
            items.append({
                "source": "Mill Valley City Website — HAC Reference",
                "title": snippet[:120],
                "url": url,
                "date": date,
                "type": "committee_mention",
                "content": snippet,
                "relevant": True,
                "committee": "HAC",
            })

        time.sleep(1)

    # De-duplicate by content
    seen = set()
    deduped = []
    for item in items:
        key = item["title"][:60]
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    if deduped:
        print(f"  [HAC] Found {len(deduped)} Housing Advisory Committee items")
    else:
        print(f"  [HAC] No HAC/MVAHC items found this period (committees may not have met)")

    return deduped


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
