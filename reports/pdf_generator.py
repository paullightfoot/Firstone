"""
ROC Tracker — PDF Report Generator (ReportLab)
Produces a weekly PDF covering:
  1. Cover + executive summary
  2. ROC certified brands, farms, orgs
  3. Other certifications overview
  4. Standards comparison table (highlighting synthetic input prohibitions)
  5. Standards changes detected this week
  6. Top sales targets
"""
import os
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from models import (
    Brand, Farm, Organization, BrandCertification, FarmCertification,
    OrgCertification, Certification, StandardsChange, StandardsAttributes,
    SalesTarget
)

# ── Colors ───────────────────────────────────────────────────────────────────
C_GREEN       = colors.HexColor("#2e7d32")
C_GREEN_LIGHT = colors.HexColor("#e8f5e9")
C_RED         = colors.HexColor("#dc2626")
C_RED_LIGHT   = colors.HexColor("#fef2f2")
C_AMBER       = colors.HexColor("#f59e0b")
C_GRAY        = colors.HexColor("#f5f5f5")
C_DARK_GRAY   = colors.HexColor("#555555")
C_WHITE       = colors.white
C_BLACK       = colors.black

OUTPUT_DIR = "reports_output"
PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


def _styles():
    base = getSampleStyleSheet()
    extra = {
        "cover_title": ParagraphStyle("cover_title", fontSize=26, textColor=C_GREEN,
                                       spaceAfter=6, alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "cover_sub":   ParagraphStyle("cover_sub", fontSize=13, textColor=C_DARK_GRAY,
                                       alignment=TA_CENTER, spaceAfter=20),
        "section":     ParagraphStyle("section", fontSize=14, textColor=C_WHITE,
                                       fontName="Helvetica-Bold", backColor=C_GREEN,
                                       spaceBefore=12, spaceAfter=6, leftIndent=6, borderPadding=4),
        "subsection":  ParagraphStyle("subsection", fontSize=11, textColor=C_GREEN,
                                       fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4),
        "body":        ParagraphStyle("body", fontSize=9, leading=13, spaceAfter=4),
        "small":       ParagraphStyle("small", fontSize=8, textColor=C_DARK_GRAY, leading=11),
        "kv_key":      ParagraphStyle("kv_key", fontSize=9, fontName="Helvetica-Bold"),
        "note":        ParagraphStyle("note", fontSize=8, textColor=C_DARK_GRAY,
                                       leading=11, spaceAfter=6),
    }
    return base, extra


def _yn(val):
    """Return (text, bg_color) for a Yes/No/Unknown value."""
    if val is True:
        return "✓ YES", C_GREEN_LIGHT
    if val is False:
        return "✗ NO", C_RED_LIGHT
    return "?", C_GRAY


def _table_style(header_rows=1, alt_color=True):
    style = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), C_GREEN),
        ("TEXTCOLOR",  (0, 0), (-1, header_rows - 1), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, header_rows), (-1, -1),
         [C_GRAY, C_WHITE] if alt_color else [C_WHITE]),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]
    return TableStyle(style)


def generate_report(since: datetime = None) -> str:
    """Generate the weekly PDF. Returns the file path."""
    if since is None:
        since = datetime.utcnow() - timedelta(days=7)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"roc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    base_styles, s = _styles()
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph("ROC Tracker Weekly Report", s["cover_title"]))
    period_str = f"{since.strftime('%B %d')} – {datetime.now().strftime('%B %d, %Y')}"
    story.append(Paragraph(f"Week of {period_str}", s["cover_sub"]))
    story.append(HRFlowable(width="100%", color=C_GREEN, thickness=1.5))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "This report covers new entries, changes to certification lists, "
        "updates to regenerative standards, and updated sales targets for "
        "the Regenerative Organic Alliance (ROA). Prepared for board member use.",
        s["body"]))
    story.append(PageBreak())

    # ── Summary ───────────────────────────────────────────────────────────────
    story.extend(_build_summary(since, s))

    # ── ROC Lists ─────────────────────────────────────────────────────────────
    story.extend(_build_roc_lists(s))

    # ── Other Certifications ──────────────────────────────────────────────────
    story.extend(_build_other_certs(s))

    # ── Standards Comparison ──────────────────────────────────────────────────
    story.append(PageBreak())
    story.extend(_build_standards_comparison(s))

    # ── Standards Changes ─────────────────────────────────────────────────────
    story.extend(_build_standards_changes(since, s))

    # ── Sales Targets ─────────────────────────────────────────────────────────
    story.append(PageBreak())
    story.extend(_build_sales_targets(s))

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN + 5 * mm, bottomMargin=MARGIN,
        title="ROC Tracker Weekly Report",
        author="Regenerative Organic Alliance",
    )

    def _header_footer(canvas, doc):
        canvas.saveState()
        # Header bar
        canvas.setFillColor(C_GREEN)
        canvas.rect(0, PAGE_H - 14 * mm, PAGE_W, 14 * mm, fill=1, stroke=0)
        canvas.setFillColor(C_WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawCentredString(PAGE_W / 2, PAGE_H - 8 * mm,
                                  "Regenerative Organic Alliance — ROC Tracker Weekly Report")
        # Footer
        canvas.setFillColor(C_DARK_GRAY)
        canvas.setFont("Helvetica", 7)
        canvas.drawCentredString(
            PAGE_W / 2, 8 * mm,
            f"ROC Tracker  ·  Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  Page {doc.page}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return filepath


# ── Section builders ──────────────────────────────────────────────────────────

def _build_summary(since, s):
    items = []
    items.append(Paragraph("1. Executive Summary", s["section"]))
    items.append(Spacer(1, 3 * mm))

    roc = Certification.query.filter_by(is_roc=True).first()
    roc_id = roc.id if roc else None

    def ct(model, **kwargs):
        return model.query.filter_by(**kwargs).count()

    rows = [
        ["Metric", "Count"],
        ["ROC Certified Brands", ct(BrandCertification, certification_id=roc_id, status="active") if roc_id else 0],
        ["ROC Certified Farms",  ct(FarmCertification,  certification_id=roc_id, status="active") if roc_id else 0],
        ["ROC Certified Organizations", ct(OrgCertification, certification_id=roc_id, status="active") if roc_id else 0],
        ["Total Brands Tracked (all certs)", Brand.query.count()],
        ["Total Farms Tracked (all certs)",  Farm.query.count()],
        ["Priority-1 Sales Targets", SalesTarget.query.filter_by(priority=1, dismissed=False).count()],
        ["Priority-2 Sales Targets", SalesTarget.query.filter_by(priority=2, dismissed=False).count()],
        ["Standards Changes This Week",
         StandardsChange.query.filter(StandardsChange.change_date >= since).count()],
    ]
    t = Table(rows, colWidths=[110 * mm, 30 * mm])
    t.setStyle(_table_style())
    items.append(t)
    items.append(Spacer(1, 5 * mm))
    return items


def _build_roc_lists(s):
    items = []
    items.append(Paragraph("2. ROC Certified Entities", s["section"]))

    roc = Certification.query.filter_by(is_roc=True).first()
    if not roc:
        items.append(Paragraph("ROC certification not found.", s["body"]))
        return items

    # Brands
    items.append(Paragraph("2a. Brands", s["subsection"]))
    bc_ids = {bc.brand_id for bc in BrandCertification.query.filter_by(
        certification_id=roc.id, status="active")}
    brands = Brand.query.filter(Brand.id.in_(bc_ids)).order_by(Brand.name).all()
    if brands:
        rows = [["Brand", "Categories", "Organic?", "Country"]]
        for b in brands:
            cats = ", ".join((b.categories or [])[:3])
            rows.append([b.name[:45], cats[:30], "Yes" if b.is_organic_certified else "No",
                         b.country or "USA"])
        t = Table(rows, colWidths=[65 * mm, 60 * mm, 20 * mm, 20 * mm])
        t.setStyle(_table_style())
        items.append(t)
    else:
        items.append(Paragraph("No ROC certified brands yet.", s["small"]))

    items.append(Spacer(1, 4 * mm))

    # Farms
    items.append(Paragraph("2b. Farms", s["subsection"]))
    fc_ids = {fc.farm_id for fc in FarmCertification.query.filter_by(
        certification_id=roc.id, status="active")}
    farms = Farm.query.filter(Farm.id.in_(fc_ids)).order_by(Farm.state, Farm.name).all()
    if farms:
        rows = [["Farm", "County", "State", "Products", "Org?"]]
        for f in farms:
            cats = ", ".join((f.categories or [])[:2])
            rows.append([f.name[:40], f.county or "", f.state or "",
                         cats[:25], "Y" if f.is_organic_certified else "N"])
        t = Table(rows, colWidths=[55 * mm, 30 * mm, 22 * mm, 40 * mm, 8 * mm])
        t.setStyle(_table_style())
        items.append(t)
    else:
        items.append(Paragraph("No ROC certified farms yet.", s["small"]))

    items.append(Spacer(1, 4 * mm))

    # Orgs
    items.append(Paragraph("2c. Processors & Distributors", s["subsection"]))
    oc_ids = {oc.org_id for oc in OrgCertification.query.filter_by(
        certification_id=roc.id, status="active")}
    orgs = Organization.query.filter(Organization.id.in_(oc_ids)).order_by(Organization.name).all()
    if orgs:
        rows = [["Name", "Type", "State"]]
        for o in orgs:
            rows.append([o.name[:55], o.org_type or "", o.state or ""])
        t = Table(rows, colWidths=[90 * mm, 50 * mm, 25 * mm])
        t.setStyle(_table_style())
        items.append(t)
    else:
        items.append(Paragraph("No ROC certified organizations yet.", s["small"]))

    return items


def _build_other_certs(s):
    items = []
    items.append(Spacer(1, 5 * mm))
    items.append(Paragraph("3. Other Regenerative Certifications", s["section"]))
    other_certs = Certification.query.filter_by(is_roc=False).all()
    rows = [["Certification", "Brands", "Farms", "Website"]]
    for cert in other_certs:
        bc = BrandCertification.query.filter_by(certification_id=cert.id, status="active").count()
        fc = FarmCertification.query.filter_by(certification_id=cert.id, status="active").count()
        rows.append([cert.name[:50], str(bc), str(fc), (cert.website or "")[:40]])
    t = Table(rows, colWidths=[80 * mm, 15 * mm, 15 * mm, 55 * mm])
    t.setStyle(_table_style())
    items.append(t)
    return items


def _build_standards_comparison(s):
    items = []
    items.append(Paragraph("4. Standards Comparison", s["section"]))
    items.append(Spacer(1, 2 * mm))
    items.append(Paragraph(
        "Green (✓ YES) = requirement met. Red (✗ NO) = not required. "
        "ROA's primary interest: columns 2 & 3 — prohibition of synthetic fertilizers "
        "and petrochemical-based pesticides/herbicides.",
        s["body"]))
    items.append(Spacer(1, 3 * mm))

    certs = Certification.query.all()
    attrs_map = {a.certification_id: a for a in StandardsAttributes.query.all()}

    headers = ["Certification", "Synth\nFert", "Synth\nPest", "GMOs",
               "Soil\nTest", "Livestock", "3rd\nParty", "Org\nBase", "Social"]
    col_w = [50*mm, 16*mm, 16*mm, 14*mm, 14*mm, 18*mm, 14*mm, 14*mm, 14*mm]

    data = [headers]
    styles_cells = []

    row_idx = 1
    for cert in certs:
        attrs = attrs_map.get(cert.id)
        row = [cert.short_name[:28]]
        if attrs:
            for val in [
                attrs.prohibits_synthetic_fertilizers,
                attrs.prohibits_synthetic_pesticides,
                attrs.prohibits_gmos,
                attrs.requires_soil_testing,
                attrs.covers_livestock,
                attrs.third_party_verified,
                attrs.requires_organic_base,
                attrs.has_social_fairness,
            ]:
                text, bg = _yn(val)
                col = len(row)
                styles_cells.append(("BACKGROUND", (col, row_idx), (col, row_idx), bg))
                if val is True:
                    styles_cells.append(("TEXTCOLOR", (col, row_idx), (col, row_idx), C_GREEN))
                elif val is False:
                    styles_cells.append(("TEXTCOLOR", (col, row_idx), (col, row_idx), C_RED))
                row.append(text)
        else:
            row.extend(["—"] * 8)

        if cert.is_roc:
            styles_cells.append(("FONTNAME", (0, row_idx), (0, row_idx), "Helvetica-Bold"))

        data.append(row)
        row_idx += 1

    t = Table(data, colWidths=col_w)
    base_style = _table_style()
    for sc in styles_cells:
        base_style.add(*sc)
    t.setStyle(base_style)
    items.append(t)
    items.append(Spacer(1, 5 * mm))

    # Notes
    items.append(Paragraph("Standards Notes:", s["subsection"]))
    for cert in certs:
        attrs = attrs_map.get(cert.id)
        if attrs and attrs.notes:
            items.append(Paragraph(f"<b>{cert.short_name}:</b> {attrs.notes}", s["note"]))

    return items


def _build_standards_changes(since, s):
    items = []
    items.append(Spacer(1, 5 * mm))
    items.append(Paragraph("5. Standards Changes This Week", s["section"]))
    changes = (StandardsChange.query
               .filter(StandardsChange.change_date >= since)
               .order_by(StandardsChange.change_date.desc()).all())
    if not changes:
        items.append(Paragraph("No standards changes detected this week.", s["body"]))
        return items

    for chg in changes:
        cert = chg.certification
        items.append(Paragraph(cert.name if cert else "Unknown", s["subsection"]))
        items.append(Paragraph(f"Detected: {chg.change_date.strftime('%Y-%m-%d %H:%M UTC')}", s["small"]))
        if chg.synthetic_fertilizer_changed:
            items.append(Paragraph("⚠ Synthetic fertilizer language may have changed.", s["body"]))
        if chg.synthetic_pesticide_changed:
            items.append(Paragraph("⚠ Synthetic pesticide/herbicide language may have changed.", s["body"]))
        if chg.diff_summary:
            snippet = chg.diff_summary[:400]
            items.append(Paragraph(f"<font name='Courier' size='7'>{snippet}</font>", s["small"]))
        items.append(Spacer(1, 3 * mm))

    return items


def _build_sales_targets(s):
    items = []
    items.append(Paragraph("6. Top Sales Targets", s["section"]))
    items.append(Spacer(1, 2 * mm))
    items.append(Paragraph(
        "Priority 1 = organic brand in a category where a ROC brand already exists. "
        "Priority 2 = organic brand, or farm near ROC farm. "
        "Priority 3 = holds another regenerative certification.",
        s["body"]))
    items.append(Spacer(1, 3 * mm))

    for priority, label in [
        (1, "Priority 1 — Organic Brand in ROC Category (Top Conversion Candidates)"),
        (2, "Priority 2 — Organic / Near ROC Farm"),
        (3, "Priority 3 — Other Regen Cert"),
    ]:
        targets = (SalesTarget.query
                   .filter_by(priority=priority, dismissed=False)
                   .limit(25).all())
        if not targets:
            continue
        items.append(Paragraph(label, s["subsection"]))
        rows = [["Name", "Type", "Reason"]]
        for t in targets:
            if t.entity_type == "brand" and t.brand:
                name = t.brand.name
            elif t.entity_type == "farm" and t.farm:
                name = t.farm.name
            else:
                name = "Unknown"
            reason = (t.reason or "")[:100]
            rows.append([name[:40], t.entity_type, reason])
        tbl = Table(rows, colWidths=[50 * mm, 18 * mm, 97 * mm])
        tbl.setStyle(_table_style())
        items.append(tbl)
        items.append(Spacer(1, 4 * mm))

    return items
