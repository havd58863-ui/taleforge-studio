"""TaleForge Studio — application factory."""
from __future__ import annotations

import os

from flask import Flask, jsonify

from .config import Config
from .extensions import db, init_redis


def create_app(config_object=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    _ensure_directories(app.config)

    db.init_app(app)
    init_redis(app)

    from .routes import register_blueprints

    register_blueprints(app)
    register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app


def _ensure_directories(config) -> None:
    keys = (
        "OUTPUT_DIR",
        "PRIVATE_DATA_DIR",
        "LORA_DIR",
        "REFERENCE_DIR",
        "DATASET_DIR",
        "GENERATED_DIR",
    )
    for key in keys:
        path = config.get(key)
        if path:
            os.makedirs(path, exist_ok=True)


def register_error_handlers(app: Flask) -> None:
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        """Preserve the original status code (404, 405, 413 ...) as JSON."""
        return (
            jsonify(
                {
                    "error": error.name.lower().replace(" ", "_"),
                    "status": error.code,
                    "message": error.description,
                }
            ),
            error.code,
        )

    @app.errorhandler(Exception)
    def unhandled(error):  # pragma: no cover - defensive
        db.session.rollback()
        app.logger.exception("Unhandled error: %s", error)
        return jsonify({"error": "internal_server_error", "message": str(error)}), 500
