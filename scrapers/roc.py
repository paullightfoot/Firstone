"""
ROC Tracker — Regenerative Organic Certified Registry Scraper
Registry: https://regenorganic.org/roc-certified/
"""
import logging
import re
from .base import BaseScraper

logger = logging.getLogger(__name__)

REGISTRY_URL = "https://regenorganic.org/roc-certified/"
# ROC also exposes a WP REST endpoint for their directory plugin
WP_API_URL = "https://regenorganic.org/wp-json/wp/v2/"


class ROCScraper(BaseScraper):
    name = "ROC"
    registry_url = REGISTRY_URL

    def scrape(self):
        results = []

        # Try fetching the page and looking for structured directory data
        soup = self.get_soup(REGISTRY_URL)
        if soup is None:
            logger.error("[ROC] Could not fetch registry page.")
            return results

        # ROC uses a Business Directory or similar WP plugin — look for entries
        # Each certified entity is typically in a card/tile with name, type, location
        entries = (
            soup.select(".bdir-item")          # Business Directory plugin
            or soup.select(".wpbdp-listing")   # WP Business Directory plugin
            or soup.select(".directory-item")
            or soup.select("article.certified-entity")
            or soup.select(".roc-certified-item")
            or soup.select(".elementor-post")
        )

        if entries:
            for entry in entries:
                result = self._parse_card(entry)
                if result:
                    results.append(result)
        else:
            # Fallback: look for any links that appear to be listing pages
            logger.info("[ROC] No structured directory cards found; trying link extraction.")
            results = self._scrape_by_links(soup)

        logger.info(f"[ROC] Found {len(results)} entries.")
        return results

    def _parse_card(self, entry):
        name_el = (
            entry.select_one(".bdir-title")
            or entry.select_one(".listing-title")
            or entry.select_one("h2")
            or entry.select_one("h3")
            or entry.select_one(".entry-title")
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        website_el = entry.select_one("a[href]")
        website = website_el["href"] if website_el else None

        # Category / type — ROC certifies brands, farms, and handlers
        entity_type = "brand"  # default; refine below
        type_el = (
            entry.select_one(".bdir-category")
            or entry.select_one(".listing-category")
            or entry.select_one(".cert-type")
        )
        if type_el:
            type_text = type_el.get_text(strip=True).lower()
            if any(w in type_text for w in ("farm", "ranch", "grower", "producer")):
                entity_type = "farm"
            elif any(w in type_text for w in ("processor", "handler", "distributor", "manufacturer")):
                entity_type = "organization"

        # Location
        loc_el = entry.select_one(".bdir-address") or entry.select_one(".location")
        county, state = None, None
        if loc_el:
            loc_text = loc_el.get_text(strip=True)
            parts = [p.strip() for p in loc_text.split(",")]
            if len(parts) >= 2:
                county = parts[-2]
                state = parts[-1]

        return {
            "name": name,
            "entity_type": entity_type,
            "website": website,
            "county": county,
            "state": state,
            "source_url": REGISTRY_URL,
            "raw_data": {"html": str(entry)[:500]},
        }

    def _scrape_by_links(self, soup):
        """Last resort: collect all internal listing links and scrape each."""
        results = []
        seen = set()
        for a in soup.select("a[href]"):
            href = a["href"]
            text = a.get_text(strip=True)
            # Skip nav/footer links
            if not text or len(text) < 3 or href in seen:
                continue
            if "regenorganic.org" in href and any(
                kw in href.lower() for kw in ("brand", "farm", "producer", "certified")
            ):
                seen.add(href)
                results.append({
                    "name": text,
                    "entity_type": "brand",
                    "website": None,
                    "source_url": href,
                    "raw_data": {"discovered_url": href},
                })
        return results
