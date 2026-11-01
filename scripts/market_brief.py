"""Market brief CLI — data first, then decisions.

    python scripts/market_brief.py --fetch auto        # Kaggle if configured, else public catalogue
    python scripts/market_brief.py --fetch kaggle      # bestseller datasets (needs KAGGLE_USERNAME/KEY)
    python scripts/market_brief.py --fetch openlibrary # public catalogue only
    python scripts/market_brief.py                     # analyse what is already on disk

Writes:
    output/market/market_report.json   full evidence (demand, saturation, gaps, titles, SEO)
    output/market/niche_brief.md       the one-page decision sheet
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.market_data_service import MarketDataService  # noqa: E402
from app.services.market_research_service import MarketResearchService  # noqa: E402
from app.services.niche_service import NicheService  # noqa: E402


def render_markdown(brief: dict, provenance: dict) -> str:
    lines = ["# Niche brief — from real data, not guesses", ""]
    lines.append(f"**basis:** `{brief['basis']}` · **titles analysed:** {brief['items']}")
    if provenance:
        lines.append(f"**intake:** {provenance.get('source')} · signal={provenance.get('signal')} · "
                     f"fetched {provenance.get('fetched_at')}")
    lines.append("")
    lines.append("## Where the shelf is open")
    lines.append("")
    lines.append("| trope | shelf | saturation | demand signal | opportunity | read |")
    lines.append("|---|---|---|---|---|---|")
    for row in brief["niches"]:
        lines.append(f"| `{row['trope']}` | {row['shelf']} | {row['saturation']:.1%} | "
                     f"{row['demand_signal']} | {row['opportunity']} | {row['read']} |")
    lines.append("")
    lines.append("## Where it is crowded (avoid unless you have an angle)")
    lines.append("")
    for row in brief["crowded"]:
        lines.append(f"- `{row['trope']}` — {row['saturation']:.1%} of the sampled market")
    lines.append("")
    lines.append("## Working titles (checked against the market for collisions)")
    lines.append("")
    for row in brief["titles"]:
        lines.append(f"- **{row['title']}** — {row['why']} (demand {row['demand_score']})")
    lines.append("")
    lines.append("## SEO sets")
    lines.append("")
    lines.append("**Amazon KDP keywords (7 slots, ≤50 chars):**")
    for keyword in brief["keywords"].get("kdp", []):
        lines.append(f"- {keyword}  _({len(keyword)} chars)_")
    lines.append("")
    lines.append("**Etsy tags (13 tags, ≤20 chars):**")
    lines.append("- " + ", ".join(f"`{tag}`" for tag in brief["keywords"].get("etsy", [])))
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    for item in brief["evidence"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Market brief from real data")
    parser.add_argument("--fetch", choices=("auto", "kaggle", "openlibrary"), default=None,
                        help="download data first (otherwise analyse what is on disk)")
    parser.add_argument("--top", type=int, default=6)
    parser.add_argument("--title", default=None, help="score your own working title instead")
    parser.add_argument("--out", default=None)
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        dataset_dir = app.config.get("KAGGLE_DATASET_PATH", "./secure_data/datasets")
        intake = None
        if args.fetch:
            try:
                result = MarketDataService(dataset_dir).sync(provider=args.fetch)
                intake = result.to_dict()
                print(f"intake: {result.provider} → {result.rows} rows " +
                      (f"({len(result.files)} file(s))" if result.files else ""))
                for note in result.notes[:5]:
                    print("   ", note)
            except Exception as exc:
                print(f"intake failed: {type(exc).__name__}: {exc}")
                return 1

        market = MarketResearchService(dataset_dir).reload()
        brief = NicheService(dataset_dir, market).brief(top=args.top, title=args.title).to_dict()
        provenance = MarketDataService(dataset_dir).provenance()

        out_dir = Path(args.out or (Path(app.config["OUTPUT_DIR"]) / "market"))
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {"brief": brief, "intake": intake, "provenance": provenance}
        (out_dir / "market_report.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "niche_brief.md").write_text(render_markdown(brief, provenance), encoding="utf-8")

        if args.json:
            print(json.dumps(brief, ensure_ascii=False, indent=2))
        else:
            print(f"basis: {brief['basis']} | titles analysed: {brief['items']}")
            print("open shelves:", ", ".join(f"{r['trope']} ({r['saturation']:.1%})" for r in brief["niches"][:4]))
            print("crowded    :", ", ".join(f"{r['trope']} ({r['saturation']:.1%})" for r in brief["crowded"][:3]))
            print("titles     :", " | ".join(r["title"] for r in brief["titles"][:3]))
            print(f"written    : {out_dir / 'market_report.json'}")
            print(f"             {out_dir / 'niche_brief.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
