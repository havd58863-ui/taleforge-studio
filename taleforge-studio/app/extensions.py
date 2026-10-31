"""Shared extensions (kept import-light so the app boots without infra)."""
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

try:  # redis is optional at boot time
    from redis import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore

db = SQLAlchemy()

_redis_client = None


def init_redis(app) -> None:
    """Create a lazily-connected Redis client. Never raises at startup."""
    global _redis_client
    if Redis is None:
        _redis_client = None
        return
    try:
        _redis_client = Redis.from_url(
            app.config.get("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:  # pragma: no cover
        _redis_client = None


def get_redis():
    return _redis_client


def redis_healthy() -> bool:
    if _redis_client is None:
        return False
    try:
        return bool(_redis_client.ping())
    except Exception:
        return False
