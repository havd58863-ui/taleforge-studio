"""Configuration for TaleForge Studio."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


class Config:
    # --- Core ---
    APP_NAME = _env("APP_NAME", "TaleForge Studio")
    APP_ENV = _env("APP_ENV", "development")
    SECRET_KEY = _env("SECRET_KEY", "dev-secret-key")
    PORT = int(_env("PORT", "5000"))
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 64 * 1024 * 1024  # 64 MB upload cap

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = _env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'taleforge.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Redis ---
    REDIS_URL = _env("REDIS_URL", "redis://localhost:6379/0")

    # --- MinIO / S3 ---
    MINIO_ENDPOINT = _env("MINIO_ENDPOINT", "")
    MINIO_ACCESS_KEY = _env("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY = _env("MINIO_SECRET_KEY", "")
    MINIO_BUCKET = _env("MINIO_BUCKET", "taleforge")

    # --- Kaggle research integration ---
    KAGGLE_USERNAME = _env("KAGGLE_USERNAME", "")
    KAGGLE_KEY = _env("KAGGLE_KEY", "")
    KAGGLE_DATASET_PATH = _env("KAGGLE_DATASET_PATH", str(BASE_DIR / "secure_data" / "datasets"))

    # --- Vector search ---
    EMBEDDING_MODEL = _env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    VECTOR_DB_PATH = _env("VECTOR_DB_PATH", str(BASE_DIR / "vector_store" / "faiss.index"))
    VECTOR_METADATA_PATH = _env("VECTOR_METADATA_PATH", str(BASE_DIR / "vector_store" / "metadata.json"))

    # --- Private content ---
    PRIVATE_DATA_DIR = _env("PRIVATE_DATA_DIR", str(BASE_DIR / "secure_data"))
    LORA_DIR = _env("LORA_DIR", str(BASE_DIR / "secure_data" / "loras"))
    REFERENCE_DIR = _env("REFERENCE_DIR", str(BASE_DIR / "secure_data" / "references"))
    DATASET_DIR = _env("DATASET_DIR", str(BASE_DIR / "secure_data" / "datasets"))
    GENERATED_DIR = _env("GENERATED_DIR", str(BASE_DIR / "secure_data" / "generated"))

    # --- Output ---
    OUTPUT_DIR = _env("OUTPUT_DIR", str(BASE_DIR / "output"))

    # Product language scope: English, German, Spanish (see language_policy.py)
    OUTPUT_LANGUAGES = _env("OUTPUT_LANGUAGES", "en,de,es")
    ALLOW_EXTRA_LANGUAGES = _env("ALLOW_EXTRA_LANGUAGES", "0")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}

app_config = DevelopmentConfig()
