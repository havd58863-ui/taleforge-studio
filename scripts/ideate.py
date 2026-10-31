"""Stage 1 — decide WHAT to publish (and whether it is one book or a series).

    python scripts/ideate.py --demo
    python scripts/ideate.py --idea-json idea.json
    python scripts/ideate.py --demo --datasets secure_data/datasets
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.market_research_service import MarketResearchService  # noqa: E402
from app.services.series_service import SeriesService  # noqa: E402
from app.services.story_director_service import StoryDirectorService  # noqa: E402

DEMO_IDEA = {
    "title": "Luna and the Lantern Forest",
    "premise": "A curious child learns that courage is choosing kindness even when she is afraid.",
    "setting": "Whispering forest at dawn",
    "world": "A magical forest where lanterns bloom like tiny stars and light must be shared",
    "central_conflict": "Luna must find her friend before dawn closes the forest paths",
    "emotional_core": "Bravery, empathy, belonging",
    "lesson_value": "True courage is choosing kindness even when fear is strong",
    "genre": "fantasy",
    "age_min": 4,
    "age_max": 8,
}
DEMO_CHARACTERS = [
    {"name": "Luna", "role": "young explorer"},
    {"name": "Pip", "role": "lantern spirit companion"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Market + series + brief decision")
    parser.add_argument("--idea-json", help="path to a JSON file with the idea")
    parser.add_argument("--demo", action="store_true", help="use the built-in demo idea")
    parser.add_argument("--datasets", help="folder with market CSV/JSON exports")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    args = parser.parse_args()

    create_app()
    idea = json.loads(Path(args.idea_json).read_text(encoding="utf-8")) if args.idea_json else DEMO_IDEA
    market_service = MarketResearchService(args.datasets)

    market = market_service.analyze_idea(idea)
    series = SeriesService().assess(idea, DEMO_CHARACTERS, market).to_dict()
    brief = StoryDirectorService().build_brief(
        idea, idea.get("age_min", 4), idea.get("age_max", 8),
        format_hint=series["decision"],
    )

    payload = {
        "idea": idea,
        "market": market,
        "series": series,
        "brief": brief.to_dict(),
        "gaps": market_service.gaps(5),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"\n=== {idea['title']} ===")
    print(f"market score : {market['market_score']}  ({market['verdict']}, confidence {market['confidence']})")
    for line in market["evidence"]:
        print("   -", line)
    print(f"\nformat       : {series['decision'].upper()} ({series['recommended_books']} book(s), score {series['score']})")
    for line in series["reasons"]:
        print("   -", line)
    print(f"\nbrief        : {brief.page_count} pages, {brief.words_per_page[0]}-{brief.words_per_page[1]} words/page,"
          f" ~{brief.total_word_budget} words, refrain: \"{brief.refrain}\"")
    print("problems     :", StoryDirectorService.validate_brief(brief) or "none")
    print("\nmarket gaps (high demand, low saturation):")
    for gap in payload["gaps"]:
        print(f"   - {gap['trope']}: saturation {gap['saturation']:.0%}, demand signal {gap['demand_signal']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
