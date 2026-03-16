"""
WSGI entry point for gunicorn / Railway deployment.
The scheduler starts automatically when the app starts.
"""
import os

# Ensure the database directory exists before SQLAlchemy tries to create the DB.
# On Railway this is /data (mounted volume). Locally it's the app directory.
_db_url = os.environ.get("DATABASE_URL", "sqlite:///roc_tracker.db")
if _db_url.startswith("sqlite:////"):
    _db_path = _db_url.replace("sqlite:////", "/")
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)

from app import create_app
import scheduler

app = create_app()
scheduler.start(app)
