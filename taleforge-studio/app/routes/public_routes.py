"""Public storefront and demo pages."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request

from app.models import Product, Story
from app.services.idea_service import IdeaService
from app.services.story_service import StoryService
from app.services.vector_service import VectorService

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    story = StoryService().seed_demo()
    idea_service = IdeaService()
    idea = idea_service.generate_candidates()[0]
    scores = idea_service.score_idea(idea)
    return render_template("home.html", story=story, scores=scores, app_name=current_app.config["APP_NAME"])


@public_bp.route("/catalog")
def catalog_page():
    StoryService().seed_demo()
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("catalog.html", products=products)


@public_bp.route("/dashboard")
def dashboard_page():
    StoryService().seed_demo()
    stories = Story.query.all()
    products = Product.query.all()
    ready = sum(1 for p in products if p.stock_status == "in_stock")
    return render_template(
        "dashboard.html", stories=stories, products=products, ready_for_export=ready
    )


@public_bp.route("/story-demo")
def story_demo_page():
    story = StoryService().seed_demo()
    return render_template("story_demo.html", story=story)


@public_bp.route("/api/summary")
def api_summary():
    story = StoryService().seed_demo()
    return jsonify(
        {
            "title": story.title,
            "premise": story.premise,
            "genre": story.genre,
            "characters": [c.to_dict() for c in story.characters],
            "scenes": [s.to_dict() for s in story.scenes],
            "status": "ready_for_production",
        }
    )


@public_bp.route("/api/search")
def search_vector_docs():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"items": [], "query": query})
    results = VectorService().search(query, top_k=5)
    return jsonify({"items": results, "query": query})
