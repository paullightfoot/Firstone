"""
ROC Tracker — Base Scraper
"""
import time
import logging
import requests
from bs4 import BeautifulSoup
import config

logger = logging.getLogger(__name__)


class BaseScraper:
    name = "base"
    registry_url = ""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def get(self, url, **kwargs):
        """Fetch a URL with retry logic."""
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=config.SCRAPE_TIMEOUT, **kwargs)
                resp.raise_for_status()
                time.sleep(config.SCRAPE_DELAY)
                return resp
            except requests.RequestException as e:
                logger.warning(f"[{self.name}] attempt {attempt+1} failed for {url}: {e}")
                if attempt < 2:
                    time.sleep(config.SCRAPE_DELAY * (attempt + 1))
        return None

    def get_soup(self, url, **kwargs):
        resp = self.get(url, **kwargs)
        if resp is None:
            return None
        return BeautifulSoup(resp.text, "lxml")

    def scrape(self):
        """
        Return a list of dicts. Each dict must have at minimum:
          - 'name': str
          - 'entity_type': 'brand' | 'farm' | 'organization'
        Optional keys: website, description, county, state, country,
                       categories, certified_date, source_url, raw_data,
                       is_organic_certified, org_type
        """
        raise NotImplementedError
