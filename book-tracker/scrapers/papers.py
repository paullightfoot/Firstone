"""
Search academic databases for papers relevant to The American Farmland System.

Sources:
- Semantic Scholar API (free, no key required)
- arXiv API (free, no key required)
- CrossRef API (free, no key required)
"""

import re
import requests
from datetime import datetime


SEARCH_QUERIES = [
    # Core thesis
    "US cropland allocation food fuel feed",
    "corn ethanol land use food security",
    # Fertilizer
    "synthetic nitrogen fertilizer greenhouse gas emissions agriculture",
    "Haber-Bosch natural gas fertilizer climate",
    "nitrogen runoff dead zone Gulf Mexico agriculture",
    # Industrial livestock
    "CAFO concentrated animal feeding operations environmental impact",
    "industrial livestock climate greenhouse gas",
    "feedlot beef environmental cost externalities",
    # Corporate concentration
    "agricultural market concentration oligopoly food system",
    "seed industry consolidation Monsanto Bayer Syngenta",
    # Subsidies
    "US farm subsidies crop insurance allocation equity",
    "Farm Bill commodity crop subsidy reform",
    # Regenerative / organic
    "regenerative agriculture soil carbon sequestration economics",
    "organic farming profitability yield comparison conventional",
    "cover crops soil health economic returns",
    "adaptive multi-paddock grazing land productivity",
    # Environmental
    "agricultural biodiversity loss pollinator decline",
    "farmland bird species decline industrial agriculture",
    "soil degradation conventional agriculture",
    # Health
    "diet-related mortality United States food system",
    "ultra-processed food chronic disease burden",
    "soil health nutrient density food quality",
    # Rural
    "rural community decline farm consolidation depopulation",
    "farm income inequality small farms large farms",
    # Market failure
    "organic food demand supply gap market failure",
    "agricultural policy market distortion free market",
    # Solutions
    "Denmark nitrogen fertilizer reduction policy",
    "regenerative organic agriculture case study commercial scale",
    "grass-fed beef omega 3 nutritional comparison feedlot",
]


def _parse_semantic_scholar_date(pub_date_str: str | None) -> datetime | None:
    if not pub_date_str:
        return None
    try:
        # Can be "2024", "2024-03", or "2024-03-15"
        parts = pub_date_str.split("-")
        if len(parts) == 1:
            return datetime(int(parts[0]), 1, 1)
        elif len(parts) == 2:
            return datetime(int(parts[0]), int(parts[1]), 1)
        else:
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return None


def _search_semantic_scholar(query: str, since: datetime) -> list[dict]:
    items = []
    try:
        resp = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": query,
                "fields": "title,abstract,authors,year,publicationDate,url,externalIds,openAccessPdf",
                "limit": 5,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        for paper in resp.json().get("data", []):
            title = paper.get("title", "")
            abstract = paper.get("abstract", "") or ""
            pub_date = _parse_semantic_scholar_date(paper.get("publicationDate"))

            if not pub_date:
                year = paper.get("year")
                if year:
                    pub_date = datetime(year, 1, 1)

            if pub_date and pub_date < since:
                continue

            # Build URL — prefer open access PDF, else semantic scholar page
            url = paper.get("url", "")
            pdf_info = paper.get("openAccessPdf")
            if pdf_info and pdf_info.get("url"):
                url = pdf_info["url"]

            if not url:
                paper_id = paper.get("paperId", "")
                url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""

            authors = paper.get("authors", [])
            author_str = ", ".join(a.get("name", "") for a in authors[:3])
            if len(authors) > 3:
                author_str += " et al."

            content = f"{title}."
            if author_str:
                content += f" By {author_str}."
            if abstract:
                content += f" {abstract[:800]}"

            items.append({
                "source": "Semantic Scholar",
                "source_category": "academic",
                "source_lean": "neutral",
                "title": title,
                "url": url,
                "date": pub_date,
                "content_type": "paper",
                "content": content,
            })

    except Exception as e:
        print(f"    [Semantic Scholar err] '{query[:40]}...': {e}")

    return items


def _search_arxiv(query: str, since: datetime) -> list[dict]:
    """Search arXiv for recent preprints (mainly food/ag/environment)."""
    items = []
    try:
        import xml.etree.ElementTree as ET

        # arXiv categories relevant to this book
        search_query = f"all:{query.replace(' ', '+')}"
        resp = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": search_query,
                "max_results": 5,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(resp.content)

        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
            abstract = (entry.findtext("atom:summary", "", ns) or "").strip()
            published_str = entry.findtext("atom:published", "", ns) or ""
            url = ""
            for link in entry.findall("atom:link", ns):
                if link.get("type") == "text/html":
                    url = link.get("href", "")
            if not url:
                url = entry.findtext("atom:id", "", ns) or ""

            pub_date = None
            if published_str:
                try:
                    pub_date = datetime.fromisoformat(published_str[:10])
                except Exception:
                    pass

            if pub_date and pub_date < since:
                continue

            if not title:
                continue

            items.append({
                "source": "arXiv",
                "source_category": "academic",
                "source_lean": "neutral",
                "title": title,
                "url": url,
                "date": pub_date,
                "content_type": "paper",
                "content": f"{title}. {abstract[:800]}" if abstract else title,
            })

    except Exception as e:
        print(f"    [arXiv err] '{query[:40]}...': {e}")

    return items


def scrape_papers(since: datetime) -> list[dict]:
    """Search academic databases for relevant papers."""
    all_items = []
    seen_titles = set()

    # Use first 12 queries to stay within rate limits
    for query in SEARCH_QUERIES[:12]:
        for item in _search_semantic_scholar(query, since):
            title_key = item["title"].lower().strip()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                all_items.append(item)

    # arXiv for preprints — use first 6 queries
    for query in SEARCH_QUERIES[:6]:
        for item in _search_arxiv(query, since):
            title_key = item["title"].lower().strip()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                all_items.append(item)

    print(f"    [academic] {len(all_items)} unique papers found")
    return all_items
