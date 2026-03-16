"""
ROC Tracker — Database Models
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Certification(db.Model):
    __tablename__ = "certifications"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    short_name = db.Column(db.String(50), nullable=False, unique=True)
    website = db.Column(db.String(500))
    registry_url = db.Column(db.String(500))
    standards_url = db.Column(db.String(500))
    is_roc = db.Column(db.Boolean, default=False)  # True only for ROC itself
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    brand_certs = db.relationship("BrandCertification", backref="certification", lazy=True)
    farm_certs = db.relationship("FarmCertification", backref="certification", lazy=True)
    org_certs = db.relationship("OrgCertification", backref="certification", lazy=True)
    standards_snapshots = db.relationship("StandardsSnapshot", backref="certification", lazy=True)
    standards_changes = db.relationship("StandardsChange", backref="certification",
                                        foreign_keys="StandardsChange.certification_id", lazy=True)
    standards_attrs = db.relationship("StandardsAttributes", backref="certification",
                                      uselist=False, lazy=True)

    def __repr__(self):
        return f"<Certification {self.short_name}>"


class Brand(db.Model):
    __tablename__ = "brands"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    website = db.Column(db.String(500))
    description = db.Column(db.Text)
    categories = db.Column(db.JSON)           # list of category strings
    is_organic_certified = db.Column(db.Boolean, default=False)
    organic_cert_notes = db.Column(db.Text)
    country = db.Column(db.String(100), default="USA")
    notes = db.Column(db.Text)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    certifications = db.relationship("BrandCertification", backref="brand", lazy=True)
    sales_targets = db.relationship("SalesTarget", backref="brand",
                                    foreign_keys="SalesTarget.brand_id", lazy=True)

    def roc_certified(self):
        return any(bc.certification.is_roc and bc.status == "active"
                   for bc in self.certifications if bc.certification)

    def active_certs(self):
        return [bc for bc in self.certifications if bc.status == "active"]

    def __repr__(self):
        return f"<Brand {self.name}>"


class BrandCertification(db.Model):
    __tablename__ = "brand_certifications"
    id = db.Column(db.Integer, primary_key=True)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    certification_id = db.Column(db.Integer, db.ForeignKey("certifications.id"), nullable=False)
    status = db.Column(db.String(50), default="active")   # active, expired, pending
    certified_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    source_url = db.Column(db.String(500))
    raw_data = db.Column(db.JSON)
    date_scraped = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("brand_id", "certification_id", name="uq_brand_cert"),
    )


class Farm(db.Model):
    __tablename__ = "farms"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    website = db.Column(db.String(500))
    description = db.Column(db.Text)
    county = db.Column(db.String(100))
    state = db.Column(db.String(100))
    country = db.Column(db.String(100), default="USA")
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    size_acres = db.Column(db.Float)
    categories = db.Column(db.JSON)    # crops / products
    is_organic_certified = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    certifications = db.relationship("FarmCertification", backref="farm", lazy=True)
    sales_targets = db.relationship("SalesTarget", backref="farm",
                                    foreign_keys="SalesTarget.farm_id", lazy=True)

    def roc_certified(self):
        return any(fc.certification.is_roc and fc.status == "active"
                   for fc in self.certifications if fc.certification)

    def active_certs(self):
        return [fc for fc in self.certifications if fc.status == "active"]

    def __repr__(self):
        return f"<Farm {self.name}>"


class FarmCertification(db.Model):
    __tablename__ = "farm_certifications"
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=False)
    certification_id = db.Column(db.Integer, db.ForeignKey("certifications.id"), nullable=False)
    status = db.Column(db.String(50), default="active")
    certified_date = db.Column(db.Date)
    source_url = db.Column(db.String(500))
    raw_data = db.Column(db.JSON)
    date_scraped = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("farm_id", "certification_id", name="uq_farm_cert"),
    )


class Organization(db.Model):
    """Processors, distributors, retailers, and other certified facilities."""
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    website = db.Column(db.String(500))
    org_type = db.Column(db.String(100))    # processor, distributor, retailer, handler, other
    description = db.Column(db.Text)
    county = db.Column(db.String(100))
    state = db.Column(db.String(100))
    country = db.Column(db.String(100), default="USA")
    notes = db.Column(db.Text)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    certifications = db.relationship("OrgCertification", backref="organization", lazy=True)

    def __repr__(self):
        return f"<Organization {self.name}>"


class OrgCertification(db.Model):
    __tablename__ = "org_certifications"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    certification_id = db.Column(db.Integer, db.ForeignKey("certifications.id"), nullable=False)
    status = db.Column(db.String(50), default="active")
    certified_date = db.Column(db.Date)
    source_url = db.Column(db.String(500))
    raw_data = db.Column(db.JSON)
    date_scraped = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("org_id", "certification_id", name="uq_org_cert"),
    )


class StandardsSnapshot(db.Model):
    """Point-in-time capture of a certification's standards document."""
    __tablename__ = "standards_snapshots"
    id = db.Column(db.Integer, primary_key=True)
    certification_id = db.Column(db.Integer, db.ForeignKey("certifications.id"), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    content_text = db.Column(db.Text)
    source_url = db.Column(db.String(500))
    date_captured = db.Column(db.DateTime, default=datetime.utcnow)
    version_label = db.Column(db.String(100))   # e.g. "v1.2" or "2024-01"

    def __repr__(self):
        return f"<StandardsSnapshot cert={self.certification_id} {self.date_captured}>"


class StandardsChange(db.Model):
    """Recorded change between two standards snapshots."""
    __tablename__ = "standards_changes"
    id = db.Column(db.Integer, primary_key=True)
    certification_id = db.Column(db.Integer, db.ForeignKey("certifications.id"), nullable=False)
    change_date = db.Column(db.DateTime, default=datetime.utcnow)
    previous_snapshot_id = db.Column(db.Integer, db.ForeignKey("standards_snapshots.id"))
    new_snapshot_id = db.Column(db.Integer, db.ForeignKey("standards_snapshots.id"))
    diff_summary = db.Column(db.Text)   # unified diff or plain summary
    synthetic_fertilizer_changed = db.Column(db.Boolean, default=False)
    synthetic_pesticide_changed = db.Column(db.Boolean, default=False)

    previous_snapshot = db.relationship("StandardsSnapshot",
                                         foreign_keys=[previous_snapshot_id])
    new_snapshot = db.relationship("StandardsSnapshot",
                                    foreign_keys=[new_snapshot_id])


class StandardsAttributes(db.Model):
    """Human-readable attributes of each certification's standards, for comparison."""
    __tablename__ = "standards_attributes"
    id = db.Column(db.Integer, primary_key=True)
    certification_id = db.Column(db.Integer, db.ForeignKey("certifications.id"),
                                  nullable=False, unique=True)
    prohibits_synthetic_fertilizers = db.Column(db.Boolean)
    prohibits_synthetic_pesticides = db.Column(db.Boolean)
    prohibits_gmos = db.Column(db.Boolean)
    requires_soil_testing = db.Column(db.Boolean)
    covers_livestock = db.Column(db.Boolean)
    third_party_verified = db.Column(db.Boolean)
    requires_organic_base = db.Column(db.Boolean)
    has_social_fairness = db.Column(db.Boolean)
    notes = db.Column(db.Text)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


class SalesTarget(db.Model):
    """Brands or farms identified as priority ROC sales targets."""
    __tablename__ = "sales_targets"
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(20), nullable=False)   # 'brand' or 'farm'
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=True)
    priority = db.Column(db.Integer, default=3)    # 1=highest, 2=high, 3=medium
    reason = db.Column(db.Text)
    opportunity_type = db.Column(db.String(100))
    # organic_same_category | organic_near_roc_farm | other_regen_cert | organic_brand
    related_roc_brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=True)
    related_roc_farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=True)
    notes = db.Column(db.Text)
    dismissed = db.Column(db.Boolean, default=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    related_roc_brand = db.relationship("Brand", foreign_keys=[related_roc_brand_id])
    related_roc_farm = db.relationship("Farm", foreign_keys=[related_roc_farm_id])


class ScrapeLog(db.Model):
    """Audit log of every scraper run."""
    __tablename__ = "scrape_logs"
    id = db.Column(db.Integer, primary_key=True)
    scraper_name = db.Column(db.String(100))
    run_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20))    # success, partial, failed
    items_found = db.Column(db.Integer, default=0)
    items_new = db.Column(db.Integer, default=0)
    items_updated = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
