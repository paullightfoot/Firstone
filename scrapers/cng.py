"""
ROC Tracker — Certified Naturally Grown Scraper
Farmer directory: https://www.naturallygrown.org/find-a-farm/
They expose a JSON endpoint via their farmer search API.
"""
import logging
import json
from .base import BaseScraper

logger = logging.getLogger(__name__)

REGISTRY_URL = "https://www.naturallygrown.org/find-a-farm/"
API_URL = "https://www.naturallygrown.org/wp-json/cng/v1/farms"
# Fallback search form endpoint
SEARCH_URL = "https://www.naturallygrown.org/find-a-farm/?search=&state=&type=plants"


class CNGScraper(BaseScraper):
    name = "Certified Naturally Grown"
    registry_url = REGISTRY_URL

    def scrape(self):
        # Try REST API first
        resp = self.get(API_URL, params={"per_page": 1000})
        if resp and resp.status_code == 200:
            try:
                data = resp.json()
                results = self._parse_api(data)
                if results:
                    logger.info(f"[CNG] Got {len(results)} farms from API.")
                    return results
            except (json.JSONDecodeError, ValueError):
                pass

        # Try fetching the HTML page and look for embedded JSON
        return self._scrape_html()

    def _parse_api(self, data):
        results = []
        items = data if isinstance(data, list) else data.get("farms", data.get("results", []))
        for item in items:
            if not isinstance(item, dict):
                continue
            name = (item.get("title") or {}).get("rendered") or item.get("name") or item.get("farm_name")
            if not name:
                continue
            meta = item.get("meta", item.get("acf", item))
            state = meta.get("state") or meta.get("province") or item.get("state")
            county = meta.get("county") or item.get("county")
            results.append({
                "name": name,
                "entity_type": "farm",
                "website": meta.get("website") or meta.get("url") or item.get("link"),
                "description": meta.get("description") or meta.get("about"),
                "county": county,
                "state": state,
                "country": meta.get("country", "USA"),
                "categories": [meta["type"]] if meta.get("type") else None,
                "is_organic_certified": False,   # CNG is not USDA Organic
                "source_url": REGISTRY_URL,
                "raw_data": meta,
            })
        return results

    def _scrape_html(self):
        results = []
        soup = self.get_soup(SEARCH_URL)
        if soup is None:
            logger.error("[CNG] Could not fetch registry page.")
            return results

        # Check for inline JSON in script tags
        for script in soup.select("script"):
            if script.string and ("farms" in script.string or "cng" in script.string.lower()):
                text = script.string
                start = text.find("[{")
                end = text.rfind("}]")
                if start != -1 and end != -1:
                    try:
                        data = json.loads(text[start:end + 2])
                        parsed = self._parse_api(data)
                        if parsed:
                            logger.info(f"[CNG] Extracted {len(parsed)} farms from inline JSON.")
                            return parsed
                    except (json.JSONDecodeError, ValueError):
                        pass

        # HTML table/list fallback
        rows = soup.select("table tbody tr") or soup.select(".farm-result, .member-listing")
        for row in rows:
            cells = row.select("td") or [row]
            if not cells:
                continue
            name_el = cells[0].select_one("a, strong") or cells[0]
            name = name_el.get_text(strip=True)
            if not name:
                continue
            state = cells[2].get_text(strip=True) if len(cells) > 2 else None
            county = cells[1].get_text(strip=True) if len(cells) > 1 else None
            link = cells[0].select_one("a")
            website = link["href"] if link else None

            results.append({
                "name": name,
                "entity_type": "farm",
                "website": website,
                "county": county,
                "state": state,
                "source_url": REGISTRY_URL,
                "raw_data": {},
            })

        logger.info(f"[CNG] Found {len(results)} entries via HTML.")
        return results
