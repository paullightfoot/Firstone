"""
ROC Tracker — Regenefied Scraper
Registry: https://www.regenefied.com/our-producers/
"""
import logging
from .base import BaseScraper

logger = logging.getLogger(__name__)

REGISTRY_URL = "https://www.regenefied.com/our-producers/"
BRANDS_URL = "https://www.regenefied.com/our-brands/"


class RegenefiedScraper(BaseScraper):
    name = "Regenefied"
    registry_url = REGISTRY_URL

    def scrape(self):
        results = []
        for url, default_type in [(REGISTRY_URL, "farm"), (BRANDS_URL, "brand")]:
            results.extend(self._scrape_page(url, default_type))
        logger.info(f"[Regenefied] Found {len(results)} entries.")
        return results

    def _scrape_page(self, url, default_entity_type):
        results = []
        soup = self.get_soup(url)
        if soup is None:
            logger.warning(f"[Regenefied] Could not fetch {url}")
            return results

        # Regenefied typically shows producers as cards/tiles
        cards = (
            soup.select(".producer-card")
            or soup.select(".brand-card")
            or soup.select(".member-card")
            or soup.select(".et_pb_blurb")       # Divi builder blurb module
            or soup.select(".elementor-widget-image-box")
            or soup.select("article")
        )

        for card in cards:
            name_el = (
                card.select_one(".producer-name")
                or card.select_one("h3")
                or card.select_one("h4")
                or card.select_one(".et_pb_blurb_title")
            )
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            website_el = card.select_one("a[href]")
            website = website_el["href"] if website_el else None
            if website and website.startswith("/"):
                website = "https://www.regenefied.com" + website

            desc_el = card.select_one("p") or card.select_one(".description")
            description = desc_el.get_text(strip=True) if desc_el else None

            # Try to detect if it's a farm or brand from context
            entity_type = default_entity_type
            combined = (name + " " + (description or "")).lower()
            if any(w in combined for w in ("farm", "ranch", "grower", "acres", "soil")):
                entity_type = "farm"
            elif any(w in combined for w in ("brand", "company", "product", "food", "snack")):
                entity_type = "brand"

            results.append({
                "name": name,
                "entity_type": entity_type,
                "website": website,
                "description": description,
                "source_url": url,
                "raw_data": {"page": url},
            })

        if not results:
            # Try extracting from plain list items
            for li in soup.select("li"):
                a = li.select_one("a")
                if a and a.get_text(strip=True):
                    results.append({
                        "name": a.get_text(strip=True),
                        "entity_type": default_entity_type,
                        "website": a.get("href"),
                        "source_url": url,
                        "raw_data": {},
                    })

        return results
