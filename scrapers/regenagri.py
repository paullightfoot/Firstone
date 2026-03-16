"""
ROC Tracker — Regenagri Scraper
Registry: https://regenagri.org/certified-operators/
"""
import logging
from .base import BaseScraper

logger = logging.getLogger(__name__)

REGISTRY_URL = "https://regenagri.org/certified-operators/"


class RegenagriScraper(BaseScraper):
    name = "Regenagri"
    registry_url = REGISTRY_URL

    def scrape(self):
        results = []
        soup = self.get_soup(REGISTRY_URL)
        if soup is None:
            logger.error("[Regenagri] Could not fetch registry page.")
            return results

        # Regenagri displays operators in a table or card layout
        # Try table rows first
        rows = soup.select("table tbody tr")
        if rows:
            for row in rows:
                cells = row.select("td")
                if not cells:
                    continue
                name = cells[0].get_text(strip=True)
                if not name:
                    continue
                country = cells[1].get_text(strip=True) if len(cells) > 1 else None
                type_text = cells[2].get_text(strip=True).lower() if len(cells) > 2 else ""
                entity_type = self._detect_type(type_text, name)
                link = cells[0].select_one("a")
                website = link["href"] if link else None

                results.append({
                    "name": name,
                    "entity_type": entity_type,
                    "website": website,
                    "country": country or "Unknown",
                    "source_url": REGISTRY_URL,
                    "raw_data": {"type_text": type_text},
                })
        else:
            # Try card layout
            cards = (
                soup.select(".operator-card")
                or soup.select(".certified-item")
                or soup.select(".elementor-post")
                or soup.select("article")
            )
            for card in cards:
                name_el = card.select_one("h2, h3, h4, .title")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name:
                    continue
                desc_el = card.select_one("p")
                description = desc_el.get_text(strip=True) if desc_el else None
                entity_type = self._detect_type(description or "", name)
                website_el = card.select_one("a[href]")
                website = website_el["href"] if website_el else None

                results.append({
                    "name": name,
                    "entity_type": entity_type,
                    "website": website,
                    "description": description,
                    "source_url": REGISTRY_URL,
                    "raw_data": {},
                })

        logger.info(f"[Regenagri] Found {len(results)} entries.")
        return results

    def _detect_type(self, text, name=""):
        text = (text + " " + name).lower()
        if any(w in text for w in ("farm", "ranch", "grower", "agricultural", "crop", "livestock")):
            return "farm"
        if any(w in text for w in ("processor", "manufacturer", "handler", "distributor")):
            return "organization"
        return "brand"
