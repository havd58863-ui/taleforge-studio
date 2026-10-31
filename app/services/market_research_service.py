"""Market research — evidence-based idea selection, not guesswork.

It reads whatever children's-book market data you drop into ``secure_data/datasets``
(any CSV/JSON/JSONL with titles, descriptions, categories, ratings or review counts —
for example a Kaggle "children's books bestsellers" or "Goodreads" export) and builds an
index of:

* **demand**      — how often your theme words appear in real published titles/blurbs
* **saturation**  — how crowded a trope is (e.g. "bedtime", "unicorn", "first day of school")
* **competition** — near-duplicate titles to yours
* **gap**         — high demand + low saturation combinations worth writing

No scraping and no live marketplace calls (they break store terms); you supply a dataset,
the service gives you a defensible score with the evidence attached.

Without any dataset the service still runs, but it says so: ``basis = "curated_baseline"``
and the numbers are a documented heuristic, never presented as market data.
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "my", "his",
    "her", "its", "their", "is", "are", "was", "were", "be", "been", "as", "at", "by",
    "from", "that", "this", "it", "he", "she", "they", "we", "you", "i", "not", "no",
    "book", "books", "story", "stories", "children", "childrens", "kids", "kid", "tale",
    "tales", "series", "volume", "edition", "picture", "board",
}

# Trope patterns a children's-book market actually saturates on.
TROPES: Dict[str, Tuple[str, ...]] = {
    "bedtime_sleep": ("bedtime", "sleep", "goodnight", "night night", "dream"),
    "first_day_school": ("first day", "school", "teacher", "classroom", "kindergarten"),
    "new_sibling": ("new baby", "new sibling", "brother", "sister", "big sister", "big brother"),
    "moving_house": ("moving", "new house", "new home", "new town"),
    "fear_of_dark": ("afraid of the dark", "dark", "monster under", "night light", "brave"),
    "friendship_group": ("friends", "friendship", "together", "team", "share"),
    "unicorn_magic": ("unicorn", "fairy", "magic", "princess", "mermaid", "dragon"),
    "talking_animals": ("bear", "rabbit", "fox", "owl", "mouse", "elephant", "lion", "cat", "dog"),
    "grandparent_memory": ("grandma", "grandpa", "grandmother", "grandfather", "memory"),
    "learning_basics": ("alphabet", "abc", "numbers", "counting", "colors", "shapes", "opposites"),
    "emotions_regulation": ("angry", "worry", "anxious", "calm", "feelings", "mindful", "breathing"),
    "nature_environment": ("ocean", "forest", "garden", "seed", "tree", "planet", "earth"),
    "grief_loss": ("loss", "grief", "goodbye", "remembering"),
    "potty_routine": ("potty", "diaper", "bath", "teeth", "getting dressed"),
    "adventure_quest": ("adventure", "quest", "journey", "treasure", "explorer", "map"),
}

# Used only when no dataset is present. Order-of-magnitude shape, not market truth.
BASELINE_SATURATION = {
    "bedtime_sleep": 0.18,
    "first_day_school": 0.11,
    "new_sibling": 0.08,
    "moving_house": 0.05,
    "fear_of_dark": 0.10,
    "friendship_group": 0.14,
    "unicorn_magic": 0.16,
    "talking_animals": 0.20,
    "grandparent_memory": 0.06,
    "learning_basics": 0.15,
    "emotions_regulation": 0.09,
    "nature_environment": 0.07,
    "grief_loss": 0.03,
    "potty_routine": 0.06,
    "adventure_quest": 0.12,
}

# Demand shape used with the curated baseline (no dataset). Relative, not absolute.
BASELINE_DEMAND = {
    "bedtime_sleep": 100, "first_day_school": 78, "new_sibling": 62, "moving_house": 44,
    "fear_of_dark": 71, "friendship_group": 88, "unicorn_magic": 95, "talking_animals": 92,
    "grandparent_memory": 51, "learning_basics": 74, "emotions_regulation": 66,
    "nature_environment": 58, "grief_loss": 31, "potty_routine": 40, "adventure_quest": 83,
}

COLUMN_HINTS = {
    "title": ("title", "name", "book", "product"),
    "description": ("description", "blurb", "summary", "synopsis", "review_text", "text"),
    "category": ("category", "genre", "subject", "bisac", "shelf"),
    "rating": ("rating", "stars", "average_rating", "score"),
    "reviews": ("reviews", "ratings_count", "review_count", "num_reviews", "votes"),
    "price": ("price", "list_price", "cost"),
    "age": ("age", "age_range", "reading_age"),
}


@dataclass
class MarketIndex:
    items: int = 0
    basis: str = "curated_baseline"
    sources: List[str] = field(default_factory=list)
    trope_saturation: Dict[str, float] = field(default_factory=dict)
    keyword_frequency: Counter = field(default_factory=Counter)
    duplicate_titles: List[str] = field(default_factory=list)
    median_rating: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": self.items,
            "basis": self.basis,
            "sources": self.sources,
            "trope_saturation": {k: round(v, 4) for k, v in sorted(self.trope_saturation.items(), key=lambda kv: -kv[1])},
            "top_keywords": dict(self.keyword_frequency.most_common(30)),
            "median_rating": self.median_rating,
        }


def tokenize(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z']+", (text or "").lower()) if w not in STOPWORDS and len(w) > 2]


class MarketResearchService:
    def __init__(self, dataset_dir: Optional[str] = None) -> None:
        self.dataset_dir = Path(
            dataset_dir or __import__("os").getenv("KAGGLE_DATASET_PATH", "./secure_data/datasets")
        )
        self._index: Optional[MarketIndex] = None

    # ------------------------------------------------------------- data access
    def dataset_files(self) -> List[Path]:
        if not self.dataset_dir.exists():
            return []
        files: List[Path] = []
        for pattern in ("*.csv", "*.json", "*.jsonl"):
            files.extend(self.dataset_dir.rglob(pattern))
        return sorted(files)

    @staticmethod
    def _map_columns(fieldnames: Iterable[str]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        lowered = {name.lower().strip(): name for name in fieldnames if name}
        for key, hints in COLUMN_HINTS.items():
            for hint in hints:
                for low, original in lowered.items():
                    if hint in low:
                        mapping.setdefault(key, original)
                        break
                if key in mapping:
                    break
        return mapping

    def _iter_records(self, path: Path) -> Iterable[Dict[str, Any]]:
        suffix = path.suffix.lower()
        try:
            if suffix == ".csv":
                with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
                    sample = handle.read(8192)
                    handle.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                    except Exception:
                        dialect = csv.excel
                    reader = csv.DictReader(handle, dialect=dialect)
                    mapping = self._map_columns(reader.fieldnames or [])
                    for row in reader:
                        yield {key: row.get(col, "") for key, col in mapping.items()}
            elif suffix == ".jsonl":
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        try:
                            record = json.loads(line)
                        except Exception:
                            continue
                        if isinstance(record, dict):
                            mapping = self._map_columns(record.keys())
                            yield {key: record.get(col, "") for key, col in mapping.items()}
            else:
                data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                rows = data if isinstance(data, list) else data.get("items") or data.get("data") or []
                for record in rows:
                    if isinstance(record, dict):
                        mapping = self._map_columns(record.keys())
                        yield {key: record.get(col, "") for key, col in mapping.items()}
        except Exception:
            return

    # ------------------------------------------------------------------- index
    def build_index(self, max_items: Optional[int] = None) -> MarketIndex:
        if self._index is not None:
            return self._index

        files = self.dataset_files()
        if not files:
            self._index = MarketIndex(
                items=0,
                basis="curated_baseline",
                trope_saturation=dict(BASELINE_SATURATION),
            )
            return self._index

        keywords: Counter = Counter()
        trope_hits: Counter = Counter()
        ratings: List[float] = []
        titles_lower: List[str] = []
        sources: List[str] = []
        count = 0

        for path in files:
            rows = 0
            for record in self._iter_records(path):
                if max_items and count >= max_items:
                    break
                title = str(record.get("title", "") or "")
                description = str(record.get("description", "") or "")
                category = str(record.get("category", "") or "")
                blob = f"{title} {description} {category}".lower()
                if not blob.strip():
                    continue

                count += 1
                rows += 1
                titles_lower.append(title.lower())

                for token in tokenize(blob):
                    keywords[token] += 1
                for trope, patterns in TROPES.items():
                    if any(pattern in blob for pattern in patterns):
                        trope_hits[trope] += 1

                try:
                    rating_value = float(str(record.get("rating", "")).strip())
                    if 0 < rating_value <= 5:
                        ratings.append(rating_value)
                except Exception:
                    pass
            if rows:
                sources.append(f"{path.name} ({rows})")

        if count == 0:
            self._index = MarketIndex(items=0, basis="curated_baseline", trope_saturation=dict(BASELINE_SATURATION))
            return self._index

        saturation = {trope: trope_hits.get(trope, 0) / count for trope in TROPES}
        ratings.sort()
        self._index = MarketIndex(
            items=count,
            basis="dataset",
            sources=sources,
            trope_saturation=saturation,
            keyword_frequency=keywords,
            duplicate_titles=titles_lower[:5000],
            median_rating=ratings[len(ratings) // 2] if ratings else None,
        )
        return self._index

    # ----------------------------------------------------------------- scoring
    @staticmethod
    def _idea_tropes(idea: Dict[str, Any]) -> List[str]:
        blob = " ".join(
            str(idea.get(key, "")) for key in ("title", "premise", "setting", "world",
                                               "central_conflict", "emotional_core",
                                               "lesson_value", "genre")
        ).lower()
        return [trope for trope, patterns in TROPES.items() if any(p in blob for p in patterns)]

    def analyze_idea(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        index = self.build_index()
        tropes = self._idea_tropes(idea)

        saturations = [index.trope_saturation.get(t, 0.0) for t in tropes] or [0.0]
        average_saturation = sum(saturations) / len(saturations)
        worst_trope = max(tropes, key=lambda t: index.trope_saturation.get(t, 0.0)) if tropes else None

        idea_tokens = set(tokenize(" ".join(
            str(idea.get(k, "")) for k in ("title", "premise", "world", "setting")
        )))
        top_market_tokens = {token for token, _ in index.keyword_frequency.most_common(200)}
        if index.basis == "dataset":
            novelty = 1.0 - (len(idea_tokens & top_market_tokens) / max(1, len(idea_tokens)))
        else:
            novelty = 0.6  # neutral: cannot measure novelty without market text

        demand_hits = sum(index.keyword_frequency.get(t, 0) for t in idea_tokens)
        demand = min(1.0, math.log10(1 + demand_hits) / 4) if index.basis == "dataset" else 0.5

        # competition: near-duplicate titles (jaccard on tokens)
        idea_title_tokens = set(tokenize(str(idea.get("title", ""))))
        competitors: List[str] = []
        if index.basis == "dataset" and idea_title_tokens:
            for title in index.duplicate_titles:
                title_tokens = set(tokenize(title))
                if not title_tokens:
                    continue
                jaccard = len(idea_title_tokens & title_tokens) / len(idea_title_tokens | title_tokens)
                if jaccard >= 0.45:
                    competitors.append(title)
        competition = min(1.0, len(competitors) / 20)

        differentiation = round(max(0.0, novelty * (1 - average_saturation) * 1.15), 4)
        market_score = round(
            100 * (0.42 * (1 - average_saturation) + 0.33 * differentiation + 0.25 * (demand - competition / 2 + 0.5)),
            2,
        )
        market_score = max(0.0, min(100.0, market_score))

        evidence: List[str] = [
            f"basis: {index.basis} ({index.items} sampled titles)" if index.basis == "dataset"
            else "no dataset supplied — using the curated baseline (heuristic, not market data)",
            f"matched tropes: {', '.join(tropes) or 'none recognised'}",
        ]
        if worst_trope:
            evidence.append(
                f"'{worst_trope}' appears in {index.trope_saturation.get(worst_trope, 0):.1%} of the sampled market"
            )
        if index.basis == "dataset":
            evidence.append(f"title-token novelty vs the market's top 200 words: {novelty:.0%}")
        else:
            evidence.append("title novelty not measurable without a dataset (neutral 0.60 assumed)")
        if competitors:
            evidence.append(f"{len(competitors)} near-duplicate title(s): {', '.join(competitors[:3])}")

        confidence = "high" if index.basis == "dataset" else "low"
        if confidence == "low":
            # Without real market data we refuse to certify anything above 65.
            market_score = min(market_score, 65.0)
            evidence.append("confidence low: supply a market dataset in secure_data/datasets to certify demand")

        verdict = (
            "green_light" if market_score >= 70
            else "needs_differentiation" if market_score >= 50
            else "crowded_avoid"
        )

        return {
            "market_score": market_score,
            "verdict": verdict,
            "tropes": tropes,
            "average_saturation": round(average_saturation, 4),
            "differentiation": differentiation,
            "demand": round(demand, 4),
            "competition": round(competition, 4),
            "competitors": competitors[:5],
            "evidence": evidence,
            "basis": index.basis,
            "confidence": confidence,
        }

    # ------------------------------------------------------------- gap hunting
    def gaps(self, limit: int = 5) -> List[Dict[str, Any]]:
        """High demand + low saturation tropes — where an original book can win."""
        index = self.build_index()
        demand_by_trope: Counter = Counter()
        if index.basis == "dataset":
            for trope, patterns in TROPES.items():
                demand_by_trope[trope] = sum(
                    index.keyword_frequency.get(word, 0) for pattern in patterns for word in pattern.split()
                )
        else:
            for trope, value in BASELINE_DEMAND.items():
                demand_by_trope[trope] = value

        rows = []
        for trope, saturation in index.trope_saturation.items():
            demand = demand_by_trope.get(trope, 0)
            if demand <= 0:
                continue
            opportunity = round(demand / (1 + saturation * 12), 2)
            rows.append({
                "trope": trope,
                "saturation": round(saturation, 4),
                "demand_signal": demand,
                "opportunity": opportunity,
            })
        rows.sort(key=lambda row: -row["opportunity"])
        return rows[:limit]

    def summary(self) -> Dict[str, Any]:
        index = self.build_index()
        return {
            "index": index.to_dict(),
            "gaps": self.gaps(),
            "recommended_kaggle_searches": [
                "childrens books bestsellers",
                "amazon children book reviews",
                "goodreads children literature",
                "picture book metadata bisac",
            ],
        }
