"""Stage 2 — write the manuscript and put it through the editorial gate.

    python scripts/write_book.py --demo
    python scripts/write_book.py --idea-json idea.json --pages 32 --out output/book.json

Uses an LLM when LLM_* is configured; otherwise runs the deterministic scaffold
(clearly labelled in the output) so the factory stays usable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.editorial_review_service import EditorialReviewService  # noqa: E402
from app.services.llm_client import get_llm  # noqa: E402
from app.services.series_service import SeriesService  # noqa: E402
from app.services.story_director_service import StoryDirectorService  # noqa: E402
from app.services.story_writer_service import StoryWriterService  # noqa: E402

DEMO_IDEA = {
    "title": "Luna and the Lantern Forest",
    "premise": "A curious child learns that courage is choosing kindness even when she is afraid.",
    "setting": "Whispering forest at dawn",
    "world": "A magical forest where lanterns bloom like tiny stars",
    "central_conflict": "Luna must find her friend before dawn closes the forest paths",
    "lesson_value": "True courage is choosing kindness even when fear is strong",
    "age_min": 4,
    "age_max": 8,
}
DEMO_CHARACTERS = [
    {"name": "Luna", "role": "young explorer",
     "consistency_token": "[luna_ref: soft oval face, curly brown hair, forest green dress, small brass lantern]"},
    {"name": "Pip", "role": "lantern spirit companion",
     "consistency_token": "[pip_ref: palm-sized glowing creature, amber light, translucent wings]"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a picture-book manuscript")
    parser.add_argument("--idea-json")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--pages", type=int, default=None)
    parser.add_argument("--out", default="output/book.json")
    parser.add_argument("--no-llm", action="store_true", help="force the offline scaffold")
    parser.add_argument("--llm-review", action="store_true", help="add the LLM craft critique")
    args = parser.parse_args()

    create_app()
    idea = json.loads(Path(args.idea_json).read_text(encoding="utf-8")) if args.idea_json else DEMO_IDEA
    characters = idea.get("characters") or DEMO_CHARACTERS

    series = SeriesService().assess(idea, characters).to_dict()
    brief = StoryDirectorService().build_brief(
        idea, idea.get("age_min", 4), idea.get("age_max", 8),
        page_count=args.pages, format_hint=series["decision"],
    )

    llm = get_llm()
    print(f"writer mode  : {'LLM (' + str(llm.model) + ')' if (llm.available and not args.no_llm) else 'offline scaffold'}")
    written = StoryWriterService(llm).write(brief, idea, characters, use_llm=not args.no_llm)

    report = EditorialReviewService(llm).review(written["pages"], brief, use_llm=args.llm_review)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({**written, "review": report.to_dict(), "series": series}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"pages        : {len(written['pages'])} | mode: {written['mode']}")
    print(f"editorial    : {report.score} ({'PASS' if report.passed else 'FAIL'}) "
          f"| errors {len([f for f in report.findings if f.severity == 'error'])}"
          f" | warnings {len([f for f in report.findings if f.severity == 'warning'])}")
    for finding in [f for f in report.findings if f.severity == "error"][:8]:
        print(f"   ERROR p{finding.page}: {finding.message}")
    print(f"saved        : {out}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
