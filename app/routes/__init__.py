"""Blueprint registration."""
from __future__ import annotations

from .admin_routes import admin_bp
from .api_routes import api_bp
from .public_routes import public_bp


def register_blueprints(app) -> None:
    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")
