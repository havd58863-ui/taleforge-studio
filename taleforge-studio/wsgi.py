"""Production WSGI entrypoint (used by gunicorn in Docker)."""
from __future__ import annotations

import os

from app import create_app
from app.config import CONFIG_MAP

_CONFIG = CONFIG_MAP["production"] if os.getenv("APP_ENV") == "production" else CONFIG_MAP["development"]

app = create_app(_CONFIG)
