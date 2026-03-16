"""
ROC Tracker — Savory Institute Land to Market Scraper
Registry: https://savory.global/land-to-market/
Brand partners: https://savory.global/land-to-market/#brands
"""
import logging
from .base import BaseScraper

logger = logging.getLogger(__name__)

REGISTRY_URL = "https://savory.global/land-to-market/"
BRANDS_URL = "https://savory.global/land-to-market/"
EOV_PRODUCERS_URL = "https://savory.global/eov-producers/"


class SavoryScraper(BaseScraper):
    name = "Savory Land to Market"
    registry_url = REGISTRY_URL

    def scrape(self):
        results = []
        for url in [REGISTRY_URL, EOV_PRODUCERS_URL]:
            results.extend(self._scrape_page(url))
        # Deduplicate by name
        seen = set()
        deduped = []
        for r in results:
            if r["name"] not in seen:
                seen.add(r["name"])
                deduped.append(r)
        logger.info(f"[Savory] Found {len(deduped)} unique entries.")
        return deduped

    def _scrape_page(self, url):
        results = []
        soup = self.get_soup(url)
        if soup is None:
            logger.warning(f"[Savory] Could not fetch {url}")
            return results

        # Savory site is built with WordPress/Elementor
        # Brand partners are typically logos with links
        brand_logos = soup.select(".brand-logo, .partner-logo, .logo-item")
        for logo in brand_logos:
            a = logo.select_one("a[href]") or logo.parent
            img = logo.select_one("img")
            name = None
            if img:
                name = img.get("alt") or img.get("title")
            if not name and a:
                name = a.get_text(strip=True)
            if not name:
                continue
            website = a["href"] if hasattr(a, "__getitem__") else None
            results.append({
                "name": name,
                "entity_type": "brand",
                "website": website,
                "source_url": url,
                "raw_data": {"type": "brand_partner"},
            })

        # EOV-verified producers (farms)
        producer_cards = (
            soup.select(".producer-card")
            or soup.select(".eov-producer")
            or soup.select(".member-item")
            or soup.select("article.post")
        )
        for card in producer_cards:
            name_el = card.select_one("h2, h3, h4, .title, .name")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name:
                continue
            loc_el = card.select_one(".location, .region, .country")
            location = loc_el.get_text(strip=True) if loc_el else None
            state, county = None, None
            if location:
                parts = [p.strip() for p in location.split(",")]
                if len(parts) >= 2:
                    state = parts[-1]
                    county = parts[-2]

            website_el = card.select_one("a[href]")
            website = website_el["href"] if website_el else None
            results.append({
                "name": name,
                "entity_type": "farm",
                "website": website,
                "county": county,
                "state": state,
                "source_url": url,
                "raw_data": {"type": "eov_producer"},
            })

        # Generic fallback — extract any named links from content area
        if not results:
            content = soup.select_one("main, .page-content, #content, .entry-content")
            if content:
                for a in content.select("a[href]"):
                    text = a.get_text(strip=True)
                    if len(text) > 3 and not any(
                        skip in a["href"].lower()
                        for skip in ("savory.global", "#", "mailto", "tel")
                    ):
                        results.append({
                            "name": text,
                            "entity_type": "brand",
                            "website": a["href"],
                            "source_url": url,
                            "raw_data": {},
                        })
        return results
