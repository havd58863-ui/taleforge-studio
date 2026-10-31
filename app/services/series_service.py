"""Series assessment — is this idea one book, a trilogy, or an open brand?

Publishers buy a *property*, not a title. This service scores the seven things that make
a children's-book property extendable, then returns an explicit decision with reasons.
Deterministic, no model required (market demand is added when a dataset is present).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DIMENSIONS = {
    "recurring_cast": 20,      # a companion the child can meet again
    "world_rules": 20,         # a world with a rule that can break later
    "episodic_engine": 15,     # each book = one new problem in the same world
    "brand_symbol": 15,        # an object/motif that reads on a shelf or thumbnail
    "age_ladder": 10,          # can grow 0-3 -> 4-8 -> 6-9 with the same brand
    "visual_variety": 10,      # enough distinct locations for 6 covers
    "market_series_demand": 10,
}

COMPANION_WORDS = ("friend", "companion", "spirit", "creature", "sibling", "pet", "guide", "helper")
WORLD_RULE_WORDS = ("rule", "only", "every", "when the", "must", "never", "curse", "season", "lantern", "portal")
EPISODIC_WORDS = ("must", "each", "again", "new", "solve", "find", "return", "help")
BRAND_WORDS = ("lantern", "wish", "map", "key", "bell", "star", "seed", "shell", "crown", "feather")


@dataclass
class SeriesAssessment:
    score: float
    decision: str
    recommended_books: int
    dimensions: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    next_book_hooks: List[str] = field(default_factory=list)
    brand_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "decision": self.decision,
            "recommended_books": self.recommended_books,
            "dimensions": {k: round(v, 1) for k, v in self.dimensions.items()},
            "reasons": self.reasons,
            "next_book_hooks": self.next_book_hooks,
            "brand_rules": self.brand_rules,
        }


class SeriesService:
    def assess(
        self,
        idea: Dict[str, Any],
        characters: Optional[List[Dict[str, Any]]] = None,
        market: Optional[Dict[str, Any]] = None,
    ) -> SeriesAssessment:
        characters = characters or []
        blob = " ".join(
            str(idea.get(key, "")) for key in
            ("title", "premise", "world", "setting", "central_conflict", "emotional_core")
        ).lower()

        scores: Dict[str, float] = {}
        reasons: List[str] = []

        # 1) recurring cast
        companions = [
            c for c in characters
            if any(word in str(c.get("role", "")).lower() for word in COMPANION_WORDS)
        ]
        if companions == [] and any(word in blob for word in COMPANION_WORDS):
            companions = ["implied companion"]
        scores["recurring_cast"] = 20 if len(companions) else 6
        reasons.append(
            f"recurring cast: {len(companions)} ongoing character(s) — a series needs at least one constant"
            if companions else "no recurring companion: every sequel would need a new cast"
        )

        # 2) world rules
        rule_hits = sum(1 for word in WORLD_RULE_WORDS if word in blob)
        scores["world_rules"] = min(20, 5 + rule_hits * 4)
        reasons.append(f"world rules detected: {rule_hits} (rules can be broken in later books)")

        # 3) episodic engine
        episode_hits = sum(1 for word in EPISODIC_WORDS if word in blob)
        scores["episodic_engine"] = min(15, 4 + episode_hits * 2.5)
        reasons.append(f"episodic engine signals: {episode_hits}")

        # 4) brand symbol
        symbol = next((word for word in BRAND_WORDS if word in blob), None)
        scores["brand_symbol"] = 15 if symbol else 5
        reasons.append(f"brand symbol: {symbol or 'none — pick one object to own the shelf'}")

        # 5) age ladder
        age_span = 0
        try:
            age_span = int(idea.get("age_max", 8)) - int(idea.get("age_min", 4))
        except Exception:
            pass
        scores["age_ladder"] = 10 if age_span >= 3 else 6
        reasons.append(f"age span: {age_span} years (wider span = easier ladder to a younger/older line)")

        # 6) visual variety
        places = {word for word in (
            "forest", "river", "castle", "village", "mountain", "sea", "garden", "school", "city", "sky"
        ) if word in blob}
        scores["visual_variety"] = min(10, 3 + len(places) * 2)
        reasons.append(f"distinct locations available for covers: {len(places) or 1}")

        # 7) market series demand
        market_bonus = 5.0
        if market and market.get("basis") == "dataset":
            market_bonus = 4.0 + min(6.0, market.get("demand", 0) * 6)
            reasons.append("market dataset used for series demand")
        else:
            reasons.append("no market dataset — series demand uses the neutral baseline")
        scores["market_series_demand"] = round(market_bonus, 1)

        total = round(sum(scores.values()), 2)

        if total >= 75:
            decision, books = "open_series", 6
        elif total >= 60:
            decision, books = "trilogy", 3
        elif total >= 45:
            decision, books = "sequel_optional", 2
        else:
            decision, books = "single_book", 1

        hooks = [
            f"Book 2 — a new {symbol or 'object'} appears and breaks the same world rule in a new place",
            "Book 3 — the companion needs help for the first time; the child becomes the helper",
            "Book 4 — a second child enters the world and must learn the same lesson differently",
        ]
        brand_rules = [
            "same protagonist name and companion in every book",
            "same object or colour motif on every cover (shelf recognition in 3 seconds)",
            "same trim size, page count and price point across the series",
            "each book solves a different emotional problem — never the same lesson twice",
        ]

        return SeriesAssessment(
            score=total,
            decision=decision,
            recommended_books=books,
            dimensions=scores,
            reasons=reasons,
            next_book_hooks=hooks[:3],
            brand_rules=brand_rules,
        )
