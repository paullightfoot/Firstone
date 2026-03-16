"""
ROC Tracker — Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Email
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "paul.lightfoot@gmail.com")
RECIPIENT_EMAILS = [e.strip() for e in os.environ.get("RECIPIENT_EMAIL", "paul.lightfoot@gmail.com").split(",")]

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///roc_tracker.db")

# Scraping
SCRAPE_TIMEOUT = 30       # seconds per request
SCRAPE_DELAY = 2          # seconds between requests
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Scheduling
WEEKLY_REPORT_DAY = "mon"       # Day of week to send report
WEEKLY_REPORT_HOUR = 7          # Hour (24h, Pacific time)
WEEKLY_REPORT_MINUTE = 0

# Geographic proximity for farm community detection
FARM_COMMUNITY_LEVELS = ["county", "state"]   # in priority order

# Product category taxonomy
CATEGORIES = [
    "Grains & Rice",
    "Coffee & Tea",
    "Produce & Vegetables",
    "Fruits",
    "Meat & Poultry",
    "Dairy",
    "Sweeteners & Honey",
    "Oils & Fats",
    "Snacks & Packaged Foods",
    "Beverages",
    "Personal Care & Beauty",
    "Fiber & Textiles",
    "Feed & Forage",
    "Herbs & Spices",
    "Legumes & Pulses",
    "Other",
]

# Known standards attributes (seed data for comparison report).
# Updated manually or via standards monitor when official docs change.
STANDARDS_ATTRIBUTES = {
    "ROC": {
        "prohibits_synthetic_fertilizers": True,
        "prohibits_synthetic_pesticides": True,
        "prohibits_gmos": True,
        "requires_soil_testing": True,
        "covers_livestock": True,
        "third_party_verified": True,
        "requires_organic_base": True,  # Requires USDA Organic as foundation
        "has_social_fairness": True,
        "notes": (
            "ROC requires USDA Organic as a baseline (which prohibits synthetic "
            "fertilizers and petrochemical pesticides/herbicides). Adds requirements "
            "for soil health, animal welfare, and social fairness."
        ),
    },
    "Regenefied": {
        "prohibits_synthetic_fertilizers": False,
        "prohibits_synthetic_pesticides": False,
        "prohibits_gmos": False,
        "requires_soil_testing": True,
        "covers_livestock": True,
        "third_party_verified": True,
        "requires_organic_base": False,
        "has_social_fairness": False,
        "notes": (
            "Regenefied is practice-based and outcome-oriented. It does NOT require "
            "prohibition of synthetic inputs. Focuses on regenerative practices and "
            "measurable soil/ecosystem outcomes."
        ),
    },
    "Regenagri": {
        "prohibits_synthetic_fertilizers": False,
        "prohibits_synthetic_pesticides": False,
        "prohibits_gmos": False,
        "requires_soil_testing": True,
        "covers_livestock": True,
        "third_party_verified": True,
        "requires_organic_base": False,
        "has_social_fairness": False,
        "notes": (
            "Regenagri uses a scoring system based on regenerative practices. "
            "Does NOT prohibit synthetic fertilizers or pesticides. "
            "Widely used in conventional agriculture transitioning toward regenerative."
        ),
    },
    "Savory Land to Market": {
        "prohibits_synthetic_fertilizers": False,
        "prohibits_synthetic_pesticides": False,
        "prohibits_gmos": False,
        "requires_soil_testing": False,
        "covers_livestock": True,
        "third_party_verified": True,
        "requires_organic_base": False,
        "has_social_fairness": False,
        "notes": (
            "Savory's EOV (Ecological Outcome Verification) focuses on land and "
            "ecosystem outcomes, primarily for grasslands and livestock. "
            "Does NOT prohibit synthetic inputs. Outcome-based verification."
        ),
    },
    "Demeter": {
        "prohibits_synthetic_fertilizers": True,
        "prohibits_synthetic_pesticides": True,
        "prohibits_gmos": True,
        "requires_soil_testing": False,
        "covers_livestock": True,
        "third_party_verified": True,
        "requires_organic_base": True,  # Requires organic certification
        "has_social_fairness": False,
        "notes": (
            "Demeter Biodynamic certification requires USDA Organic as a baseline "
            "and adds biodynamic practices. Prohibits synthetic fertilizers and "
            "petrochemical pesticides. One of the most rigorous standards available."
        ),
    },
    "Real Organic Project": {
        "prohibits_synthetic_fertilizers": True,
        "prohibits_synthetic_pesticides": True,
        "prohibits_gmos": True,
        "requires_soil_testing": False,
        "covers_livestock": True,
        "third_party_verified": True,
        "requires_organic_base": True,  # Add-on to USDA Organic
        "has_social_fairness": False,
        "notes": (
            "ROP is an add-on to USDA Organic that requires soil-grown produce "
            "(prohibits hydroponics) and pasture-raised animals. Inherits USDA Organic "
            "prohibition on synthetic fertilizers and petrochemical pesticides."
        ),
    },
    "A Greener World Certified Regenerative": {
        "prohibits_synthetic_fertilizers": False,
        "prohibits_synthetic_pesticides": False,
        "prohibits_gmos": False,
        "requires_soil_testing": True,
        "covers_livestock": True,
        "third_party_verified": True,
        "requires_organic_base": False,
        "has_social_fairness": True,
        "notes": (
            "AGW Certified Regenerative is practice-based. Does NOT prohibit "
            "synthetic fertilizers or petrochemical pesticides. Includes animal welfare "
            "and some social standards. Designed to be accessible to conventional farms."
        ),
    },
    "Certified Naturally Grown": {
        "prohibits_synthetic_fertilizers": True,
        "prohibits_synthetic_pesticides": True,
        "prohibits_gmos": True,
        "requires_soil_testing": False,
        "covers_livestock": True,
        "third_party_verified": False,  # Peer-reviewed, not third-party
        "requires_organic_base": False,
        "has_social_fairness": False,
        "notes": (
            "CNG uses peer-review verification (not third-party certified). "
            "Standards are similar to USDA Organic — prohibits synthetic fertilizers "
            "and petrochemical pesticides. Designed as an accessible alternative to "
            "USDA Organic certification for small and direct-market farms."
        ),
    },
}
