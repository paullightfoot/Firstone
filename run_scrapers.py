"""
ROC Tracker — Scraper Runner
Imports all scrapers, runs them, and saves results to the database.
"""
import logging
from datetime import datetime

from models import (
    db, Certification, Brand, Farm, Organization,
    BrandCertification, FarmCertification, OrgCertification, ScrapeLog
)

logger = logging.getLogger(__name__)

SCRAPER_MAP = {
    "ROC": "scrapers.roc.ROCScraper",
    "Regenefied": "scrapers.regenefied.RegenefiedScraper",
    "Regenagri": "scrapers.regenagri.RegenagriScraper",
    "Savory Land to Market": "scrapers.savory.SavoryScraper",
    "Demeter": "scrapers.demeter.DemeterScraper",
    "Real Organic Project": "scrapers.rop.ROPScraper",
    "A Greener World Certified Regenerative": "scrapers.agw.AGWScraper",
    "Certified Naturally Grown": "scrapers.cng.CNGScraper",
}


def _import_scraper(dotpath):
    module_path, class_name = dotpath.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def run_one_scraper(cert_short_name, app_context):
    with app_context:
        dot = SCRAPER_MAP.get(cert_short_name)
        if not dot:
            logger.error(f"No scraper registered for '{cert_short_name}'")
            return
        cls = _import_scraper(dot)
        _execute(cls(), cert_short_name)


def run_all_scrapers(app_context):
    with app_context:
        for cert_name, dot in SCRAPER_MAP.items():
            try:
                cls = _import_scraper(dot)
                _execute(cls(), cert_name)
            except Exception as e:
                logger.error(f"[Runner] Failed to run scraper for {cert_name}: {e}")
                _log(cert_name, "failed", 0, 0, 0, str(e))


def _execute(scraper, cert_short_name):
    cert = Certification.query.filter_by(short_name=cert_short_name).first()
    if not cert:
        logger.warning(f"[Runner] Certification '{cert_short_name}' not in DB — skipping.")
        return

    logger.info(f"[Runner] Running {cert_short_name} scraper…")
    start = datetime.utcnow()
    items_found = items_new = items_updated = 0
    error_msg = None

    try:
        results = scraper.scrape()
        items_found = len(results)

        for item in results:
            entity_type = item.get("entity_type", "brand")
            if entity_type == "brand":
                new, updated = _upsert_brand(item, cert)
            elif entity_type == "farm":
                new, updated = _upsert_farm(item, cert)
            elif entity_type == "organization":
                new, updated = _upsert_org(item, cert)
            else:
                continue
            items_new += new
            items_updated += updated

        db.session.commit()
        status = "success"
    except Exception as e:
        logger.error(f"[Runner] {cert_short_name} scraper error: {e}", exc_info=True)
        db.session.rollback()
        status = "failed"
        error_msg = str(e)[:500]

    _log(cert_short_name, status, items_found, items_new, items_updated, error_msg)
    elapsed = (datetime.utcnow() - start).seconds
    logger.info(f"[Runner] {cert_short_name}: {items_found} found, {items_new} new, {items_updated} updated ({elapsed}s)")


def _upsert_brand(item, cert):
    name = item["name"].strip()
    brand = Brand.query.filter(Brand.name.ilike(name)).first()
    new = 0
    updated = 0
    if not brand:
        brand = Brand(
            name=name,
            website=item.get("website"),
            description=item.get("description"),
            categories=item.get("categories"),
            is_organic_certified=item.get("is_organic_certified", False),
            organic_cert_notes=item.get("organic_cert_notes"),
            country=item.get("country", "USA"),
            notes=item.get("notes"),
        )
        db.session.add(brand)
        db.session.flush()
        new = 1
    else:
        _update_if_set(brand, item, ["website", "description", "categories", "country"])
        updated = 1

    _upsert_brand_cert(brand, cert, item)
    return new, updated


def _upsert_farm(item, cert):
    name = item["name"].strip()
    farm = Farm.query.filter(Farm.name.ilike(name)).first()
    new = 0
    updated = 0
    if not farm:
        farm = Farm(
            name=name,
            website=item.get("website"),
            description=item.get("description"),
            county=item.get("county"),
            state=item.get("state"),
            country=item.get("country", "USA"),
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            size_acres=item.get("size_acres"),
            categories=item.get("categories"),
            is_organic_certified=item.get("is_organic_certified", False),
            notes=item.get("notes"),
        )
        db.session.add(farm)
        db.session.flush()
        new = 1
    else:
        _update_if_set(farm, item, ["website", "description", "county", "state",
                                    "latitude", "longitude", "categories"])
        updated = 1

    _upsert_farm_cert(farm, cert, item)
    return new, updated


def _upsert_org(item, cert):
    name = item["name"].strip()
    org = Organization.query.filter(Organization.name.ilike(name)).first()
    new = 0
    updated = 0
    if not org:
        org = Organization(
            name=name,
            website=item.get("website"),
            org_type=item.get("org_type", "other"),
            description=item.get("description"),
            state=item.get("state"),
            country=item.get("country", "USA"),
            notes=item.get("notes"),
        )
        db.session.add(org)
        db.session.flush()
        new = 1
    else:
        _update_if_set(org, item, ["website", "description", "org_type", "state"])
        updated = 1

    _upsert_org_cert(org, cert, item)
    return new, updated


def _upsert_brand_cert(brand, cert, item):
    existing = BrandCertification.query.filter_by(
        brand_id=brand.id, certification_id=cert.id).first()
    if not existing:
        bc = BrandCertification(
            brand_id=brand.id,
            certification_id=cert.id,
            status="active",
            source_url=item.get("source_url"),
            raw_data=item.get("raw_data"),
        )
        db.session.add(bc)
    else:
        existing.status = "active"
        existing.date_scraped = datetime.utcnow()


def _upsert_farm_cert(farm, cert, item):
    existing = FarmCertification.query.filter_by(
        farm_id=farm.id, certification_id=cert.id).first()
    if not existing:
        fc = FarmCertification(
            farm_id=farm.id,
            certification_id=cert.id,
            status="active",
            source_url=item.get("source_url"),
            raw_data=item.get("raw_data"),
        )
        db.session.add(fc)
    else:
        existing.status = "active"
        existing.date_scraped = datetime.utcnow()


def _upsert_org_cert(org, cert, item):
    existing = OrgCertification.query.filter_by(
        org_id=org.id, certification_id=cert.id).first()
    if not existing:
        oc = OrgCertification(
            org_id=org.id,
            certification_id=cert.id,
            status="active",
            source_url=item.get("source_url"),
            raw_data=item.get("raw_data"),
        )
        db.session.add(oc)
    else:
        existing.status = "active"
        existing.date_scraped = datetime.utcnow()


def _update_if_set(obj, item, fields):
    for f in fields:
        val = item.get(f)
        if val is not None:
            setattr(obj, f, val)


def _log(scraper_name, status, found, new, updated, error=None):
    log = ScrapeLog(
        scraper_name=scraper_name,
        status=status,
        items_found=found,
        items_new=new,
        items_updated=updated,
        error_message=error,
    )
    db.session.add(log)
    db.session.commit()
