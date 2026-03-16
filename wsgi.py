"""
WSGI entry point for gunicorn / Railway deployment.
The scheduler starts automatically when the app starts.
"""
from app import create_app
import scheduler

app = create_app()
scheduler.start(app)
