"""
ROC Tracker — Standards Change Monitor
Fetches each certification's standards page, hashes the content,
and records a change event when it differs from the last snapshot.
"""
import hashlib
import difflib
import logging
from datetime import datetime

from models import db, Certification, StandardsSnapshot, StandardsChange, StandardsAttributes
from config import STANDARDS_ATTRIBUTES
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Standards pages to monitor for each certification short_name
STANDARDS_PAGES = {
    "ROC": [
        "https://regenorganic.org/wp-content/uploads/2023/05/ROC-Standard-V3.0.pdf",
        "https://regenorganic.org/roc-standard/",
    ],
    "Regenefied": [
        "https://www.regenefied.com/standard/",
        "https://www.regenefied.com/our-standard/",
    ],
    "Regenagri": [
        "https://regenagri.org/standard/",
        "https://regenagri.org/the-standard/",
    ],
    "Savory Land to Market": [
        "https://savory.global/eov/",
        "https://savory.global/land-to-market/eov-methodology/",
    ],
    "Demeter": [
        "https://www.demeter-usa.org/downloads/Demeter-Farm-Standard.pdf",
        "https://www.demeter-usa.org/about-demeter/demeter-standards.asp",
    ],
    "Real Organic Project": [
        "https://www.realorganicproject.org/real-organic-project-standards/",
        "https://www.realorganicproject.org/about/our-standards/",
    ],
    "A Greener World Certified Regenerative": [
        "https://agreenerworld.org/certifications/certified-regenerative/standards/",
        "https://agreenerworld.org/wp-content/uploads/AGW-Certified-Regenerative-Standards.pdf",
    ],
    "Certified Naturally Grown": [
        "https://www.naturallygrown.org/about-cng/standards/",
        "https://www.naturallygrown.org/standards/",
    ],
}


class StandardsMonitor(BaseScraper):
    name = "standards_monitor"

    def monitor_all(self, app_context):
        """Run inside Flask app context."""
        with app_context:
            certs = Certification.query.all()
            changes_found = []
            for cert in certs:
                urls = STANDARDS_PAGES.get(cert.short_name, [])
                if cert.standards_url and cert.standards_url not in urls:
                    urls.insert(0, cert.standards_url)
                for url in urls:
                    changed = self._check_url(cert, url)
                    if changed:
                        changes_found.append(changed)
                        break   # One successful check per cert is enough
            logger.info(f"[Standards] Monitor complete. {len(changes_found)} change(s) detected.")
            return changes_found

    def _check_url(self, cert, url):
        """Fetch URL, compare hash, record change if different. Returns change dict or None."""
        resp = self.get(url)
        if resp is None:
            logger.warning(f"[Standards] Could not fetch {url} for {cert.short_name}")
            return None

        content = self._extract_text(resp)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Get last snapshot
        last = (StandardsSnapshot.query
                .filter_by(certification_id=cert.id)
                .order_by(StandardsSnapshot.date_captured.desc())
                .first())

        if last and last.content_hash == content_hash:
            logger.info(f"[Standards] No change for {cert.short_name}")
            return None

        # Save new snapshot
        new_snap = StandardsSnapshot(
            certification_id=cert.id,
            content_hash=content_hash,
            content_text=content[:50000],   # cap stored text at 50 KB
            source_url=url,
            date_captured=datetime.utcnow(),
        )
        db.session.add(new_snap)
        db.session.flush()

        if last:
            diff = self._make_diff(last.content_text or "", content)
            synth_fert_changed = self._mentions_synth_fert(diff)
            synth_pest_changed = self._mentions_synth_pest(diff)
            change = StandardsChange(
                certification_id=cert.id,
                change_date=datetime.utcnow(),
                previous_snapshot_id=last.id,
                new_snapshot_id=new_snap.id,
                diff_summary=diff[:5000],
                synthetic_fertilizer_changed=synth_fert_changed,
                synthetic_pesticide_changed=synth_pest_changed,
            )
            db.session.add(change)
            db.session.commit()
            logger.info(f"[Standards] Change recorded for {cert.short_name}")
            return {
                "cert": cert.short_name,
                "url": url,
                "synth_fert": synth_fert_changed,
                "synth_pest": synth_pest_changed,
                "diff": diff[:1000],
            }
        else:
            # First snapshot — no diff
            db.session.commit()
            logger.info(f"[Standards] First snapshot saved for {cert.short_name}")
            return None

    def _extract_text(self, resp):
        """Extract meaningful text from an HTTP response (HTML or plain text)."""
        ct = resp.headers.get("Content-Type", "")
        if "html" in ct:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            # Remove nav, header, footer noise
            for el in soup.select("nav, header, footer, script, style, .menu, .nav"):
                el.decompose()
            return soup.get_text(separator="\n", strip=True)
        return resp.text

    def _make_diff(self, old_text, new_text):
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        diff = difflib.unified_diff(old_lines, new_lines, lineterm="", n=3)
        return "\n".join(list(diff)[:500])

    def _mentions_synth_fert(self, text):
        keywords = ["synthetic fertilizer", "synthetic nitrogen", "chemical fertilizer",
                    "prohibited fertilizer", "fertilizer prohibition"]
        return any(kw in text.lower() for kw in keywords)

    def _mentions_synth_pest(self, text):
        keywords = ["synthetic pesticide", "synthetic herbicide", "petrochemical pesticide",
                    "prohibited pesticide", "pesticide prohibition", "herbicide prohibition"]
        return any(kw in text.lower() for kw in keywords)


def seed_standards_attributes(app_context):
    """Populate StandardsAttributes from config for all known certifications."""
    with app_context:
        certs = Certification.query.all()
        for cert in certs:
            attrs_data = STANDARDS_ATTRIBUTES.get(cert.short_name)
            if not attrs_data:
                continue
            existing = StandardsAttributes.query.filter_by(certification_id=cert.id).first()
            if existing:
                continue
            attrs = StandardsAttributes(
                certification_id=cert.id,
                prohibits_synthetic_fertilizers=attrs_data.get("prohibits_synthetic_fertilizers"),
                prohibits_synthetic_pesticides=attrs_data.get("prohibits_synthetic_pesticides"),
                prohibits_gmos=attrs_data.get("prohibits_gmos"),
                requires_soil_testing=attrs_data.get("requires_soil_testing"),
                covers_livestock=attrs_data.get("covers_livestock"),
                third_party_verified=attrs_data.get("third_party_verified"),
                requires_organic_base=attrs_data.get("requires_organic_base"),
                has_social_fairness=attrs_data.get("has_social_fairness"),
                notes=attrs_data.get("notes"),
                last_updated=datetime.utcnow(),
            )
            db.session.add(attrs)
        db.session.commit()
        logger.info("[Standards] Attributes seeded.")
