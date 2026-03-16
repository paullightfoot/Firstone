"""
ROC Tracker — Real Organic Project Scraper
Registry: https://www.realorganicproject.org/find-a-farm/
They also expose farm data via a map (possibly a JSON endpoint).
"""
import logging
import json
from .base import BaseScraper

logger = logging.getLogger(__name__)

REGISTRY_URL = "https://www.realorganicproject.org/find-a-farm/"
# ROP often uses a Mapplic or Leaflet map with a JSON data source
JSON_CANDIDATES = [
    "https://www.realorganicproject.org/wp-content/uploads/farms.json",
    "https://www.realorganicproject.org/wp-json/rop/v1/farms",
]


class ROPScraper(BaseScraper):
    name = "Real Organic Project"
    registry_url = REGISTRY_URL

    def scrape(self):
        # First try JSON endpoints (faster and more reliable)
        for json_url in JSON_CANDIDATES:
            resp = self.get(json_url)
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    results = self._parse_json(data, json_url)
                    if results:
                        logger.info(f"[ROP] Got {len(results)} farms from JSON endpoint.")
                        return results
                except (json.JSONDecodeError, ValueError):
                    pass

        # Fallback: scrape HTML page
        return self._scrape_html()

    def _parse_json(self, data, source_url):
        results = []
        items = data if isinstance(data, list) else data.get("farms", data.get("data", []))
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("farm_name") or item.get("title")
            if not name:
                continue
            results.append({
                "name": name,
                "entity_type": "farm",
                "website": item.get("website") or item.get("url"),
                "description": item.get("description") or item.get("about"),
                "county": item.get("county"),
                "state": item.get("state") or item.get("province"),
                "country": item.get("country", "USA"),
                "latitude": item.get("lat") or item.get("latitude"),
                "longitude": item.get("lng") or item.get("longitude"),
                "is_organic_certified": True,   # ROP requires USDA Organic base
                "source_url": source_url,
                "raw_data": item,
            })
        return results

    def _scrape_html(self):
        results = []
        soup = self.get_soup(REGISTRY_URL)
        if soup is None:
            logger.error("[ROP] Could not fetch registry page.")
            return results

        # ROP farm finder may embed farm data in a <script> tag as JSON
        for script in soup.select("script"):
            if script.string and ("farms" in script.string or "markers" in script.string):
                text = script.string
                # Look for JSON array
                start = text.find("[{")
                end = text.rfind("}]")
                if start != -1 and end != -1:
                    try:
                        data = json.loads(text[start:end + 2])
                        parsed = self._parse_json(data, REGISTRY_URL)
                        if parsed:
                            logger.info(f"[ROP] Extracted {len(parsed)} farms from inline JSON.")
                            return parsed
                    except (json.JSONDecodeError, ValueError):
                        pass

        # Try HTML table or list
        rows = soup.select("table tbody tr")
        for row in rows:
            cells = row.select("td")
            if not cells:
                continue
            name = cells[0].get_text(strip=True)
            if not name:
                continue
            state = cells[1].get_text(strip=True) if len(cells) > 1 else None
            results.append({
                "name": name,
                "entity_type": "farm",
                "state": state,
                "is_organic_certified": True,
                "source_url": REGISTRY_URL,
                "raw_data": {},
            })

        logger.info(f"[ROP] Found {len(results)} entries via HTML.")
        return results
