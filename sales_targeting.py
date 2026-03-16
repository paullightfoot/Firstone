"""
ROC Tracker — Sales Targeting Engine

Identifies high-priority targets for ROC certification sales:

Priority 1 (highest):
  - Organic brand in a category where a ROC brand already exists
    (role-model effect — e.g., organic rice brand when Lotus/Lundberg are ROC)

Priority 2:
  - Any organic brand not yet ROC certified (easier transition)
  - Farm certified for another regen cert in a county with a ROC farm (peer influence)

Priority 3:
  - Brand certified for another regen standard (Regenefied, Regenagri, etc.)
  - Organic farm near a ROC-certified farm (state-level if no county match)
"""

import logging
from datetime import datetime

from models import db, Brand, Farm, BrandCertification, FarmCertification, \
    Certification, SalesTarget

logger = logging.getLogger(__name__)


def run_targeting():
    """
    Main entry point. Run inside Flask app context.
    Clears non-dismissed targets and rebuilds from current data.
    """
    # Clear auto-generated targets (keep manually added ones)
    SalesTarget.query.filter(SalesTarget.dismissed == False).delete()
    db.session.commit()

    roc_cert = Certification.query.filter_by(is_roc=True).first()
    if not roc_cert:
        logger.warning("[Targeting] ROC certification not found in database.")
        return

    targets = []
    targets.extend(_brand_targets(roc_cert))
    targets.extend(_farm_targets(roc_cert))

    for t in targets:
        db.session.add(t)
    db.session.commit()
    logger.info(f"[Targeting] Created {len(targets)} sales targets.")
    return targets


# ── Brand targeting ──────────────────────────────────────────────────────────

def _brand_targets(roc_cert):
    targets = []

    # All ROC brands and their categories
    roc_brand_ids = {
        bc.brand_id for bc in BrandCertification.query.filter_by(
            certification_id=roc_cert.id, status="active"
        ).all()
    }

    # Build category → ROC brand mapping
    roc_brands_by_category = {}   # category_str -> [Brand]
    for brand in Brand.query.filter(Brand.id.in_(roc_brand_ids)).all():
        for cat in (brand.categories or []):
            roc_brands_by_category.setdefault(cat, []).append(brand)

    # All non-ROC brands
    non_roc_brands = Brand.query.filter(Brand.id.notin_(roc_brand_ids)).all()

    for brand in non_roc_brands:
        brand_cats = brand.categories or []

        # Find overlap with ROC categories
        matching_cats = [c for c in brand_cats if c in roc_brands_by_category]

        if brand.is_organic_certified and matching_cats:
            # Priority 1: organic brand in same category as existing ROC brand
            for cat in matching_cats:
                roc_role_models = roc_brands_by_category[cat]
                role_model_names = ", ".join(b.name for b in roc_role_models[:3])
                t = SalesTarget(
                    entity_type="brand",
                    brand_id=brand.id,
                    priority=1,
                    opportunity_type="organic_same_category",
                    related_roc_brand_id=roc_role_models[0].id,
                    reason=(
                        f"{brand.name} is an organic brand in {cat}. "
                        f"ROC role model(s) in this category: {role_model_names}. "
                        f"High likelihood of interest — they can point to peers who made the transition."
                    ),
                    date_added=datetime.utcnow(),
                )
                targets.append(t)
                break   # one target per brand

        elif brand.is_organic_certified:
            # Priority 2: organic brand not in a ROC category yet
            t = SalesTarget(
                entity_type="brand",
                brand_id=brand.id,
                priority=2,
                opportunity_type="organic_brand",
                reason=(
                    f"{brand.name} is organic certified. Transition to ROC is "
                    f"significantly easier than a conventional→ROC path."
                ),
                date_added=datetime.utcnow(),
            )
            targets.append(t)

        else:
            # Priority 3: non-organic brand with another regen cert
            other_certs = [
                bc for bc in brand.certifications
                if bc.status == "active" and bc.certification_id != roc_cert.id
            ]
            if other_certs:
                cert_names = ", ".join(bc.certification.short_name for bc in other_certs)
                t = SalesTarget(
                    entity_type="brand",
                    brand_id=brand.id,
                    priority=3,
                    opportunity_type="other_regen_cert",
                    reason=(
                        f"{brand.name} holds {cert_names} certification. "
                        f"Already committed to regenerative — ROC is a meaningful upgrade."
                    ),
                    date_added=datetime.utcnow(),
                )
                targets.append(t)

    return targets


# ── Farm targeting ───────────────────────────────────────────────────────────

def _farm_targets(roc_cert):
    targets = []

    roc_farm_ids = {
        fc.farm_id for fc in FarmCertification.query.filter_by(
            certification_id=roc_cert.id, status="active"
        ).all()
    }

    # Build county → ROC farms and state → ROC farms maps
    roc_farms_by_county = {}   # "county|state" -> [Farm]
    roc_farms_by_state = {}    # state -> [Farm]
    for farm in Farm.query.filter(Farm.id.in_(roc_farm_ids)).all():
        if farm.state:
            roc_farms_by_state.setdefault(farm.state.strip().lower(), []).append(farm)
        if farm.county and farm.state:
            key = f"{farm.county.strip().lower()}|{farm.state.strip().lower()}"
            roc_farms_by_county.setdefault(key, []).append(farm)

    non_roc_farms = Farm.query.filter(Farm.id.notin_(roc_farm_ids)).all()

    for farm in non_roc_farms:
        county_key = None
        if farm.county and farm.state:
            county_key = f"{farm.county.strip().lower()}|{farm.state.strip().lower()}"
        state_key = farm.state.strip().lower() if farm.state else None

        # Check for other regen certs
        other_certs = [
            fc for fc in farm.certifications
            if fc.status == "active" and fc.certification_id != roc_cert.id
        ]

        # County-level match (highest priority for farms)
        if county_key and county_key in roc_farms_by_county:
            roc_neighbors = roc_farms_by_county[county_key]
            neighbor_names = ", ".join(f.name for f in roc_neighbors[:2])
            priority = 1 if farm.is_organic_certified else 2
            cert_note = ""
            if other_certs:
                cert_names = ", ".join(fc.certification.short_name for fc in other_certs)
                cert_note = f" Also holds: {cert_names}."

            t = SalesTarget(
                entity_type="farm",
                farm_id=farm.id,
                priority=priority,
                opportunity_type="organic_near_roc_farm",
                related_roc_farm_id=roc_neighbors[0].id,
                reason=(
                    f"{farm.name} is in {farm.county}, {farm.state} — same county as "
                    f"ROC-certified farm(s): {neighbor_names}.{cert_note} "
                    f"Geographic peer influence is a strong conversion signal."
                ),
                date_added=datetime.utcnow(),
            )
            targets.append(t)

        elif state_key and state_key in roc_farms_by_state:
            roc_neighbors = roc_farms_by_state[state_key]
            neighbor_names = ", ".join(f.name for f in roc_neighbors[:2])
            priority = 2 if farm.is_organic_certified else 3
            t = SalesTarget(
                entity_type="farm",
                farm_id=farm.id,
                priority=priority,
                opportunity_type="organic_near_roc_farm",
                related_roc_farm_id=roc_neighbors[0].id,
                reason=(
                    f"{farm.name} is in {farm.state}, same state as ROC-certified "
                    f"farm(s): {neighbor_names}. "
                    f"State-level community connection — potential for peer referrals."
                ),
                date_added=datetime.utcnow(),
            )
            targets.append(t)

        elif other_certs:
            cert_names = ", ".join(fc.certification.short_name for fc in other_certs)
            t = SalesTarget(
                entity_type="farm",
                farm_id=farm.id,
                priority=3,
                opportunity_type="other_regen_cert",
                reason=(
                    f"{farm.name} holds {cert_names}. Already engaged with regenerative "
                    f"agriculture — ROC would be a natural next step."
                ),
                date_added=datetime.utcnow(),
            )
            targets.append(t)

    return targets
