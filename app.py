"""
ROC Tracker — Flask Web Application
"""
import logging
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

import config
from models import (
    db, Certification, Brand, Farm, Organization,
    BrandCertification, FarmCertification, OrgCertification,
    StandardsSnapshot, StandardsChange, StandardsAttributes,
    SalesTarget, ScrapeLog
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.secret_key = "roc-tracker-dev-secret-change-in-prod"

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _seed_certifications()

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route("/")
    def dashboard():
        roc = Certification.query.filter_by(is_roc=True).first()
        roc_id = roc.id if roc else None

        stats = {
            "roc_brands": (BrandCertification.query.filter_by(certification_id=roc_id, status="active").count()
                           if roc_id else 0),
            "roc_farms": (FarmCertification.query.filter_by(certification_id=roc_id, status="active").count()
                          if roc_id else 0),
            "roc_orgs": (OrgCertification.query.filter_by(certification_id=roc_id, status="active").count()
                         if roc_id else 0),
            "total_brands": Brand.query.count(),
            "total_farms": Farm.query.count(),
            "total_orgs": Organization.query.count(),
            "p1_targets": SalesTarget.query.filter_by(priority=1, dismissed=False).count(),
            "p2_targets": SalesTarget.query.filter_by(priority=2, dismissed=False).count(),
            "p3_targets": SalesTarget.query.filter_by(priority=3, dismissed=False).count(),
        }

        recent_changes = (StandardsChange.query
                          .filter(StandardsChange.change_date >= datetime.utcnow() - timedelta(days=30))
                          .order_by(StandardsChange.change_date.desc())
                          .limit(5).all())

        recent_logs = ScrapeLog.query.order_by(ScrapeLog.run_date.desc()).limit(10).all()
        return render_template("dashboard.html", stats=stats,
                               recent_changes=recent_changes, recent_logs=recent_logs)

    # ── ROC Lists ─────────────────────────────────────────────────────────────

    @app.route("/roc/brands")
    def roc_brands():
        roc = Certification.query.filter_by(is_roc=True).first()
        brands = []
        if roc:
            ids = {bc.brand_id for bc in BrandCertification.query.filter_by(
                certification_id=roc.id, status="active")}
            brands = Brand.query.filter(Brand.id.in_(ids)).order_by(Brand.name).all()
        return render_template("roc_brands.html", brands=brands, title="ROC Certified Brands")

    @app.route("/roc/farms")
    def roc_farms():
        roc = Certification.query.filter_by(is_roc=True).first()
        farms = []
        if roc:
            ids = {fc.farm_id for fc in FarmCertification.query.filter_by(
                certification_id=roc.id, status="active")}
            farms = Farm.query.filter(Farm.id.in_(ids)).order_by(Farm.state, Farm.name).all()
        return render_template("roc_farms.html", farms=farms, title="ROC Certified Farms")

    @app.route("/roc/orgs")
    def roc_orgs():
        roc = Certification.query.filter_by(is_roc=True).first()
        orgs = []
        if roc:
            ids = {oc.org_id for oc in OrgCertification.query.filter_by(
                certification_id=roc.id, status="active")}
            orgs = Organization.query.filter(Organization.id.in_(ids)).order_by(Organization.name).all()
        return render_template("roc_orgs.html", orgs=orgs, title="ROC Certified Organizations")

    # ── Other Certification Lists ─────────────────────────────────────────────

    @app.route("/other/brands")
    def other_brands():
        roc = Certification.query.filter_by(is_roc=True).first()
        roc_id = roc.id if roc else None
        other_certs = Certification.query.filter_by(is_roc=False).all()
        cert_data = []
        for cert in other_certs:
            ids = {bc.brand_id for bc in BrandCertification.query.filter_by(
                certification_id=cert.id, status="active")}
            brands = Brand.query.filter(Brand.id.in_(ids)).order_by(Brand.name).all()
            cert_data.append({"cert": cert, "brands": brands})
        return render_template("other_brands.html", cert_data=cert_data,
                               title="Brands — Other Regenerative Certifications")

    @app.route("/other/farms")
    def other_farms():
        other_certs = Certification.query.filter_by(is_roc=False).all()
        cert_data = []
        for cert in other_certs:
            ids = {fc.farm_id for fc in FarmCertification.query.filter_by(
                certification_id=cert.id, status="active")}
            farms = Farm.query.filter(Farm.id.in_(ids)).order_by(Farm.state, Farm.name).all()
            cert_data.append({"cert": cert, "farms": farms})
        return render_template("other_farms.html", cert_data=cert_data,
                               title="Farms — Other Regenerative Certifications")

    # ── Standards ─────────────────────────────────────────────────────────────

    @app.route("/standards")
    def standards():
        certs = Certification.query.all()
        attrs_map = {a.certification_id: a for a in StandardsAttributes.query.all()}
        recent_changes = (StandardsChange.query
                          .order_by(StandardsChange.change_date.desc())
                          .limit(20).all())
        return render_template("standards.html", certs=certs, attrs_map=attrs_map,
                               recent_changes=recent_changes, title="Standards Comparison")

    @app.route("/standards/<int:cert_id>/history")
    def standards_history(cert_id):
        cert = Certification.query.get_or_404(cert_id)
        snapshots = (StandardsSnapshot.query
                     .filter_by(certification_id=cert_id)
                     .order_by(StandardsSnapshot.date_captured.desc())
                     .all())
        changes = (StandardsChange.query
                   .filter_by(certification_id=cert_id)
                   .order_by(StandardsChange.change_date.desc())
                   .all())
        return render_template("standards_history.html", cert=cert,
                               snapshots=snapshots, changes=changes)

    # ── Sales Targets ─────────────────────────────────────────────────────────

    @app.route("/targets")
    def sales_targets():
        priority = request.args.get("priority", type=int)
        entity_type = request.args.get("type")
        q = SalesTarget.query.filter_by(dismissed=False)
        if priority:
            q = q.filter_by(priority=priority)
        if entity_type:
            q = q.filter_by(entity_type=entity_type)
        targets = q.order_by(SalesTarget.priority, SalesTarget.date_added.desc()).all()
        return render_template("sales_targets.html", targets=targets, title="Sales Targets")

    @app.route("/targets/<int:target_id>/dismiss", methods=["POST"])
    def dismiss_target(target_id):
        t = SalesTarget.query.get_or_404(target_id)
        t.dismissed = True
        db.session.commit()
        flash(f"Target dismissed.", "info")
        return redirect(url_for("sales_targets"))

    # ── Admin ─────────────────────────────────────────────────────────────────

    @app.route("/admin")
    def admin():
        certs = Certification.query.all()
        logs = ScrapeLog.query.order_by(ScrapeLog.run_date.desc()).limit(20).all()
        return render_template("admin.html", certs=certs, logs=logs, title="Admin")

    @app.route("/admin/scrape", methods=["POST"])
    def run_scrape():
        scraper_name = request.form.get("scraper", "all")
        flash(f"Scrape job '{scraper_name}' queued — check logs.", "success")
        # Import here to avoid circular import at module load time
        from run_scrapers import run_one_scraper, run_all_scrapers
        if scraper_name == "all":
            run_all_scrapers(app.app_context())
        else:
            run_one_scraper(scraper_name, app.app_context())
        return redirect(url_for("admin"))

    @app.route("/admin/check-standards", methods=["POST"])
    def check_standards():
        from scrapers.standards import StandardsMonitor, seed_standards_attributes
        seed_standards_attributes(app.app_context())
        monitor = StandardsMonitor()
        changes = monitor.monitor_all(app.app_context())
        flash(f"Standards check complete. {len(changes)} change(s) detected.", "success")
        return redirect(url_for("standards"))

    @app.route("/admin/run-targeting", methods=["POST"])
    def run_targeting_route():
        with app.app_context():
            from sales_targeting import run_targeting
            targets = run_targeting()
            flash(f"Targeting complete. {len(targets) if targets else 0} target(s) identified.", "success")
        return redirect(url_for("sales_targets"))

    @app.route("/admin/send-report", methods=["POST"])
    def send_report_now():
        with app.app_context():
            from reports.pdf_generator import generate_report
            from reports.email_sender import send_weekly_report
            pdf_path = generate_report(since=datetime.utcnow() - timedelta(days=7))
            success = send_weekly_report(pdf_path)
            if success:
                flash("Weekly report generated and sent successfully.", "success")
            else:
                flash("Report generated but email failed — check logs.", "warning")
        return redirect(url_for("admin"))

    @app.route("/admin/cert/add", methods=["GET", "POST"])
    def add_cert():
        if request.method == "POST":
            cert = Certification(
                name=request.form["name"],
                short_name=request.form["short_name"],
                website=request.form.get("website"),
                registry_url=request.form.get("registry_url"),
                standards_url=request.form.get("standards_url"),
                is_roc=bool(request.form.get("is_roc")),
            )
            db.session.add(cert)
            db.session.commit()
            flash(f"Certification '{cert.name}' added.", "success")
            return redirect(url_for("admin"))
        return render_template("add_cert.html", title="Add Certification")

    # ── Brand / Farm / Org detail & edit ─────────────────────────────────────

    @app.route("/brand/<int:brand_id>")
    def brand_detail(brand_id):
        brand = Brand.query.get_or_404(brand_id)
        return render_template("brand_detail.html", brand=brand)

    @app.route("/farm/<int:farm_id>")
    def farm_detail(farm_id):
        farm = Farm.query.get_or_404(farm_id)
        # Find farms in same county and state for community view
        county_peers, state_peers = [], []
        if farm.county and farm.state:
            county_peers = (Farm.query
                            .filter(Farm.county == farm.county,
                                    Farm.state == farm.state,
                                    Farm.id != farm.id)
                            .limit(10).all())
        if farm.state:
            state_peers = (Farm.query
                           .filter(Farm.state == farm.state, Farm.id != farm.id)
                           .filter(~Farm.id.in_([f.id for f in county_peers]))
                           .limit(10).all())
        return render_template("farm_detail.html", farm=farm,
                               county_peers=county_peers, state_peers=state_peers)

    # ── API endpoints (for AJAX / future use) ─────────────────────────────────

    @app.route("/api/stats")
    def api_stats():
        roc = Certification.query.filter_by(is_roc=True).first()
        roc_id = roc.id if roc else None
        return jsonify({
            "roc_brands": BrandCertification.query.filter_by(
                certification_id=roc_id, status="active").count() if roc_id else 0,
            "roc_farms": FarmCertification.query.filter_by(
                certification_id=roc_id, status="active").count() if roc_id else 0,
            "total_brands": Brand.query.count(),
            "total_farms": Farm.query.count(),
            "sales_targets": SalesTarget.query.filter_by(dismissed=False).count(),
        })

    return app


def _seed_certifications():
    """Insert the 8 certifications on first run if not already present."""
    certs = [
        dict(name="Regenerative Organic Certified", short_name="ROC",
             website="https://regenorganic.org",
             registry_url="https://regenorganic.org/roc-certified/",
             standards_url="https://regenorganic.org/roc-standard/",
             is_roc=True),
        dict(name="Regenefied", short_name="Regenefied",
             website="https://www.regenefied.com",
             registry_url="https://www.regenefied.com/our-producers/",
             standards_url="https://www.regenefied.com/standard/"),
        dict(name="Regenagri", short_name="Regenagri",
             website="https://regenagri.org",
             registry_url="https://regenagri.org/certified-operators/",
             standards_url="https://regenagri.org/standard/"),
        dict(name="Savory Land to Market", short_name="Savory Land to Market",
             website="https://savory.global",
             registry_url="https://savory.global/land-to-market/",
             standards_url="https://savory.global/eov/"),
        dict(name="Demeter", short_name="Demeter",
             website="https://www.demeter-usa.org",
             registry_url="https://www.demeter-usa.org/find-demeter/",
             standards_url="https://www.demeter-usa.org/about-demeter/demeter-standards.asp"),
        dict(name="Real Organic Project", short_name="Real Organic Project",
             website="https://www.realorganicproject.org",
             registry_url="https://www.realorganicproject.org/find-a-farm/",
             standards_url="https://www.realorganicproject.org/real-organic-project-standards/"),
        dict(name="A Greener World Certified Regenerative",
             short_name="A Greener World Certified Regenerative",
             website="https://agreenerworld.org",
             registry_url="https://agreenerworld.org/certifications/certified-regenerative/",
             standards_url="https://agreenerworld.org/certifications/certified-regenerative/standards/"),
        dict(name="Certified Naturally Grown", short_name="Certified Naturally Grown",
             website="https://www.naturallygrown.org",
             registry_url="https://www.naturallygrown.org/find-a-farm/",
             standards_url="https://www.naturallygrown.org/about-cng/standards/"),
    ]
    for c in certs:
        if not Certification.query.filter_by(short_name=c["short_name"]).first():
            db.session.add(Certification(**c))
    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5001)
