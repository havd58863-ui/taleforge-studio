"""Admin dashboard and ops endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template

from app.models import Character, Product, Story
from app.services.idea_service import IdeaService
from app.services.quality_service import QualityService
from app.services.story_service import StoryService
from app.services.vector_service import VectorService

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
def admin_home():
    StoryService().seed_demo()
    stories = Story.query.all()
    products = Product.query.all()
    return render_template(
        "dashboard.html",
        stories=stories,
        products=products,
        ready_for_export=sum(1 for p in products if p.stock_status == "in_stock"),
        admin=True,
    )


@admin_bp.route("/overview")
def admin_overview():
    quality = QualityService().evaluate()
    return jsonify(
        {
            "stories": Story.query.count(),
            "products": Product.query.count(),
            "characters": Character.query.count(),
            "vector": VectorService().stats(),
            "quality_gate": quality.to_dict(),
            "top_idea": IdeaService().ranked_candidates()[0],
            "status": "ready",
        }
    )
