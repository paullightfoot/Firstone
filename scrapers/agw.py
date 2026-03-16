"""
ROC Tracker — A Greener World (AGW) Certified Regenerative Scraper
Registry: https://agreenerworld.org/certifications/certified-regenerative/
Products: https://agreenerworld.org/certifications/certified-regenerative/certified-products/
"""
import logging
from .base import BaseScraper

logger = logging.getLogger(__name__)

REGISTRY_URL = "https://agreenerworld.org/certifications/certified-regenerative/"
PRODUCTS_URL = "https://agreenerworld.org/certifications/certified-regenerative/certified-products/"
FARMS_URL = "https://agreenerworld.org/certifications/certified-regenerative/certified-farms/"


class AGWScraper(BaseScraper):
    name = "A Greener World Certified Regenerative"
    registry_url = REGISTRY_URL

    def scrape(self):
        results = []
        for url, default_type in [(PRODUCTS_URL, "brand"), (FARMS_URL, "farm")]:
            results.extend(self._scrape_page(url, default_type))
        # Also try the main registry page
        if not results:
            results.extend(self._scrape_page(REGISTRY_URL, "brand"))
        logger.info(f"[AGW] Found {len(results)} entries.")
        return results

    def _scrape_page(self, url, default_entity_type):
        results = []
        soup = self.get_soup(url)
        if soup is None:
            logger.warning(f"[AGW] Could not fetch {url}")
            return results

        # AGW uses WordPress — look for product/farm listings
        cards = (
            soup.select(".product-card")
            or soup.select(".farm-card")
            or soup.select(".certified-product")
            or soup.select(".member-card")
            or soup.select(".wp-block-post")
            or soup.select("article.post")
            or soup.select(".elementor-post")
        )

        for card in cards:
            name_el = (
                card.select_one("h2, h3, h4")
                or card.select_one(".product-name, .farm-name, .title")
            )
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            desc_el = card.select_one("p, .description, .excerpt")
            description = desc_el.get_text(strip=True) if desc_el else None

            link_el = card.select_one("a[href]")
            website = link_el["href"] if link_el else None

            # Try to detect state from description
            state = None
            if description:
                # Simple US state detection
                import re
                state_match = re.search(
                    r'\b(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|'
                    r'Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|'
                    r'Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|'
                    r'Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|'
                    r'New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|'
                    r'Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|'
                    r'Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|'
                    r'AK|AL|AR|AZ|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|'
                    r'ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|'
                    r'TN|TX|UT|VA|VT|WA|WI|WV|WY)\b',
                    description
                )
                if state_match:
                    state = state_match.group(0)

            results.append({
                "name": name,
                "entity_type": default_entity_type,
                "website": website,
                "description": description,
                "state": state,
                "source_url": url,
                "raw_data": {"page": url},
            })

        # Fallback: extract from links
        if not results:
            content = soup.select_one("main, .entry-content, #content")
            if content:
                for a in content.select("a[href]"):
                    text = a.get_text(strip=True)
                    if (len(text) > 3
                            and "agreenerworld" not in a["href"]
                            and not a["href"].startswith("#")):
                        results.append({
                            "name": text,
                            "entity_type": default_entity_type,
                            "website": a["href"],
                            "source_url": url,
                            "raw_data": {},
                        })
        return results
