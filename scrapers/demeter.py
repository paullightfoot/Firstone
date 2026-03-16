"""
ROC Tracker — Demeter Biodynamic Scraper
Registry: https://www.demeter-usa.org/find-demeter/
Also: https://www.demeter.net/  (international)
"""
import logging
from .base import BaseScraper

logger = logging.getLogger(__name__)

REGISTRY_URL = "https://www.demeter-usa.org/find-demeter/"
PRODUCER_URL = "https://www.demeter-usa.org/find-demeter/certified-producers.asp"
BRAND_URL = "https://www.demeter-usa.org/find-demeter/certified-brands.asp"


class DemeterScraper(BaseScraper):
    name = "Demeter"
    registry_url = REGISTRY_URL

    def scrape(self):
        results = []
        for url, default_type in [(PRODUCER_URL, "farm"), (BRAND_URL, "brand")]:
            results.extend(self._scrape_page(url, default_type))
        logger.info(f"[Demeter] Found {len(results)} entries.")
        return results

    def _scrape_page(self, url, default_entity_type):
        results = []
        soup = self.get_soup(url)
        if soup is None:
            logger.warning(f"[Demeter] Could not fetch {url}")
            return results

        # Demeter-USA uses a classic table layout for producers/brands
        # Try table rows
        rows = soup.select("table tr")
        if rows:
            headers = []
            for i, row in enumerate(rows):
                cells = row.select("th, td")
                if i == 0:
                    headers = [c.get_text(strip=True).lower() for c in cells]
                    continue
                if not cells:
                    continue
                name = cells[0].get_text(strip=True)
                if not name or name.lower() in ("name", "producer", "brand"):
                    continue

                row_data = {h: cells[j].get_text(strip=True) if j < len(cells) else ""
                            for j, h in enumerate(headers)}

                state = row_data.get("state") or row_data.get("location") or None
                county = row_data.get("county") or None
                website_el = cells[0].select_one("a") or (cells[-1].select_one("a") if cells else None)
                website = website_el["href"] if website_el else None

                entity_type = default_entity_type
                type_col = row_data.get("type") or row_data.get("category") or ""
                if any(w in type_col.lower() for w in ("farm", "ranch", "estate")):
                    entity_type = "farm"
                elif any(w in type_col.lower() for w in ("brand", "product")):
                    entity_type = "brand"

                results.append({
                    "name": name,
                    "entity_type": entity_type,
                    "website": website,
                    "state": state,
                    "county": county,
                    "source_url": url,
                    "raw_data": row_data,
                })
        else:
            # Try list / card layout
            items = (
                soup.select(".producer-listing")
                or soup.select(".certified-member")
                or soup.select("li.member")
                or soup.select("article")
            )
            for item in items:
                name_el = item.select_one("h2, h3, h4, strong, .name")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name:
                    continue
                website_el = item.select_one("a[href]")
                website = website_el["href"] if website_el else None
                loc_el = item.select_one(".location, .state, address")
                state = loc_el.get_text(strip=True) if loc_el else None

                results.append({
                    "name": name,
                    "entity_type": default_entity_type,
                    "website": website,
                    "state": state,
                    "source_url": url,
                    "raw_data": {},
                })
        return results
