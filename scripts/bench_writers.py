"""A/B the writer models on the same brief — decide with numbers, not opinions.

    # two local models
    python scripts/bench_writers.py --target gemma4:12b --target qwen3:14b --provider ollama

    # local vs Hugging Face (needs HF_TOKEN in .env, never in git)
    python scripts/bench_writers.py --provider huggingface \
        --target Qwen/Qwen2.5-72B-Instruct --target meta-llama/Llama-3.3-70B-Instruct

Each model writes the same StoryBrief; the deterministic editorial gate scores it.
The score is not taste — it is budget, reading level, refrain discipline, safety and arc
coverage. Read the best manuscript aloud before you trust the winner.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.editorial_review_service import EditorialReviewService  # noqa: E402
from app.services.llm_client import LLMClient  # noqa: E402
from app.services.story_director_service import StoryDirectorService  # noqa: E402
from app.services.story_writer_service import StoryWriterService  # noqa: E402

IDEA = {
    "title": "Luna and the Lantern Forest",
    "setting": "A forest of lanterns at dusk",
    "world": "A forest where every path is lit by a shared lantern",
    "central_conflict": "Luna must give her own light to fill a dark lantern",
    "lesson_value": "Courage is choosing to share",
}
CHARACTERS = [
    {"name": "Luna", "role": "young explorer",
     "consistency_token": "[luna_ref: soft oval face, curly brown hair, green dress, brass lantern]"},
    {"name": "Pip", "role": "lantern spirit companion",
     "consistency_token": "[pip_ref: palm-sized amber glow, translucent wings]"},
]

DEFAULT_BASE_URLS = {
    "ollama": "http://127.0.0.1:11434/v1",
    "huggingface": "https://router.huggingface.co/v1",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark writer models on one brief")
    parser.add_argument("--target", action="append", required=True, help="model id (repeatable)")
    parser.add_argument("--provider", default="ollama", help="ollama | huggingface | openai_compatible")
    parser.add_argument("--base-url", default="", help="override the provider default")
    parser.add_argument("--language", default="en", choices=["en", "de", "es"])
    parser.add_argument("--pages", type=int, default=24)
    parser.add_argument("--out", default="output/writer_benchmark.json")
    args = parser.parse_args()

    base_url = args.base_url or DEFAULT_BASE_URLS.get(args.provider, "")
    brief = StoryDirectorService().build_brief(IDEA, 3, 8, page_count=args.pages, language=args.language)
    results = []

    for model in args.target:
        os.environ.update({
            "LLM_PROVIDER": args.provider,
            "LLM_BASE_URL": base_url,
            "LLM_MODEL": model,
            "LLM_API_KEY": os.getenv("LLM_API_KEY") or os.getenv("HF_TOKEN") or ("ollama" if args.provider == "ollama" else ""),
        })
        client = LLMClient()
        started = time.time()
        try:
            if not client.available:
                raise RuntimeError("client not configured (missing key/base url)")
            written = StoryWriterService(client).write(brief, IDEA, CHARACTERS, use_llm=True)
            report = EditorialReviewService(client).review(written["pages"], brief, use_llm=True)
            row = {
                "model": model,
                "mode": written["mode"],
                "editorial_score": report.score,
                "passed": report.passed,
                "errors": [f.message for f in report.findings if f.severity == "error"][:6],
                "warnings": len([f for f in report.findings if f.severity == "warning"]),
                "words_total": report.metrics.get("total_words"),
                "reading_grade": report.metrics.get("reading_grade"),
                "craft_notes": report.craft_notes[:3],
                "seconds": round(time.time() - started, 1),
            }
        except Exception as exc:
            row = {"model": model, "error": str(exc), "seconds": round(time.time() - started, 1)}
        results.append(row)
        status = row.get("editorial_score", "ERR")
        print(f"{model:45s} score={status} passed={row.get('passed')} {row.get('seconds')}s "
              f"{row.get('error', '')}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"brief": brief.to_dict(), "results": results}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nsaved: {out}")
    print("reminder: read the winning manuscript aloud. A gate pass is necessary, not sufficient.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
