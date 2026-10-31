"""Database models for TaleForge Studio."""
from __future__ import annotations

from datetime import datetime, timezone

from .extensions import db


def _utcnow() -> datetime:
    """Naive UTC timestamp (timezone-aware source, stored naive for SQLite/Postgres parity)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Story(db.Model):
    __tablename__ = "stories"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    premise = db.Column(db.Text)
    genre = db.Column(db.String(120))
    setting = db.Column(db.String(255))
    age_min = db.Column(db.Integer, default=4)
    age_max = db.Column(db.Integer, default=8)
    language = db.Column(db.String(20), default="en")
    created_at = db.Column(db.DateTime, default=_utcnow)

    characters = db.relationship("Character", backref="story", lazy=True, cascade="all, delete-orphan")
    scenes = db.relationship("Scene", backref="story", lazy=True, cascade="all, delete-orphan")
    products = db.relationship("Product", backref="story", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "premise": self.premise,
            "genre": self.genre,
            "setting": self.setting,
            "age_min": self.age_min,
            "age_max": self.age_max,
            "language": self.language,
            "characters": len(self.characters or []),
            "scenes": len(self.scenes or []),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Character(db.Model):
    __tablename__ = "characters"

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("stories.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(255))
    age = db.Column(db.Integer)
    personality = db.Column(db.Text)
    visual_summary = db.Column(db.Text)
    values = db.Column(db.Text)
    flaws = db.Column(db.Text)
    strengths = db.Column(db.Text)
    emotional_arc = db.Column(db.Text)
    consistency_token = db.Column(db.String(255))  # stable token injected into every prompt
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "personality": self.personality,
            "visual_summary": self.visual_summary,
            "consistency_token": self.consistency_token,
        }


class Scene(db.Model):
    __tablename__ = "scenes"

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("stories.id"), nullable=False)
    number = db.Column(db.Integer, default=1)
    title = db.Column(db.String(255))
    summary = db.Column(db.Text)
    page_type = db.Column(db.String(80))
    camera_angle = db.Column(db.String(80))
    mood = db.Column(db.String(80))
    lighting = db.Column(db.String(120))
    palette = db.Column(db.Text)
    prompt = db.Column(db.Text)
    negative_prompt = db.Column(db.Text)
    image_path = db.Column(db.String(255))
    print_ready = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "summary": self.summary,
            "page_type": self.page_type,
            "camera_angle": self.camera_angle,
            "mood": self.mood,
            "lighting": self.lighting,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "image_path": self.image_path,
            "print_ready": self.print_ready,
        }


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("stories.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    subtitle = db.Column(db.String(255))
    category = db.Column(db.String(120))
    age_group = db.Column(db.String(80))
    language = db.Column(db.String(30))
    format_type = db.Column(db.String(80))  # paperback / hardcover / ebook / coloring
    trim_size = db.Column(db.String(40), default="6x9")
    page_count = db.Column(db.Integer, default=24)
    listing_title = db.Column(db.String(255))
    listing_description = db.Column(db.Text)
    keywords = db.Column(db.Text)
    price = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default="USD")
    cover_image = db.Column(db.String(255))
    stock_status = db.Column(db.String(80), default="in_stock")
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "story_id": self.story_id,
            "title": self.title,
            "subtitle": self.subtitle,
            "category": self.category,
            "age_group": self.age_group,
            "language": self.language,
            "format_type": self.format_type,
            "trim_size": self.trim_size,
            "page_count": self.page_count,
            "price": self.price,
            "currency": self.currency,
            "cover_image": self.cover_image,
            "stock_status": self.stock_status,
        }


class ExportArtifact(db.Model):
    __tablename__ = "export_artifacts"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    artifact_type = db.Column(db.String(80), default="pdf")
    print_ready = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utcnow)


class VectorDocument(db.Model):
    __tablename__ = "vector_documents"

    id = db.Column(db.Integer, primary_key=True)
    doc_type = db.Column(db.String(80), default="story")
    title = db.Column(db.String(255))
    text = db.Column(db.Text)
    embedding_key = db.Column(db.String(255), unique=True)
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_utcnow)
