"""Local development server."""
from __future__ import annotations

import os

from app import create_app
from app.config import CONFIG_MAP

app = create_app(CONFIG_MAP.get(os.getenv("APP_ENV", "development"), CONFIG_MAP["development"]))

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", True), host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
