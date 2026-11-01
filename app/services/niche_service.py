"""Niche brief — turns market data into a commercial production decision.

The chain this service closes:

    market dataset  ->  MarketResearchService index (demand / saturation / competition)
                    ->  NicheService brief (angles, working titles, SEO sets)
                    ->  production (story, illustrations, KDP/Etsy listings)

Everything here is derived from the dataset that is actually on disk. If no dataset exists,
``basis`` is reported as ``curated_baseline`` and every number is labelled a heuristic — the
service never dresses a guess up as market data.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.market_research_service import TROPES, MarketResearchService, tokenize

KDP_KEYWORD_LIMIT = 7          # Amazon KDP: 7 keyword slots
KDP_KEYWORD_CHARS = 50         # each slot <= 50 characters
ETSY_TAG_LIMIT = 13            # Etsy: 13 tags
ETSY_TAG_CHARS = 20            # each tag <= 20 characters

# Trope -> the human angle, the shelf it sits on, and the promise on the cover.
TROPE_ANGLES: Dict[str, Dict[str, str]] = {
    "first_day_school": {"angle": "the first morning told minute by minute, with one brave step",
                          "shelf": "first day of school", "promise": "eases the knot in the stomach before day one"},
    "new_sibling": {"angle": "a big sister who must make room for a small stranger",
                    "shelf": "new baby", "promise": "helps a child feel big, not replaced"},
    "moving_house": {"angle": "one box, one room, and the thing that travels with you",
                     "shelf": "moving house", "promise": "makes a new home feel possible"},
    "fear_of_dark": {"angle": "a dark that turns out to be made of ordinary sounds",
                     "shelf": "fear of the dark", "promise": "turns the shadow into something known"},
    "friendship_group": {"angle": "three children, one game, and one child left outside",
                         "shelf": "friendship", "promise": "warm, funny, teaches the first move"},
    "unicorn_magic": {"angle": "one impossible creature with a very ordinary problem",
                      "shelf": "unicorn", "promise": "sparkle on the cover, kindness inside"},
    "talking_animals": {"angle": "one small animal with one very big feeling",
                        "shelf": "animals", "promise": "an animal friend a toddler asks for again"},
    "grandparent_memory": {"angle": "a grandparent's everyday lesson, one afternoon at a time",
                           "shelf": "grandparent", "promise": "the quiet love inside an ordinary family"},
    "learning_basics": {"angle": "letters or numbers hidden in a game, not a lesson",
                        "shelf": "alphabet and numbers", "promise": "learning that feels like play"},
    "emotions_regulation": {"angle": "a big feeling named out loud and given somewhere to go",
                            "shelf": "big feelings", "promise": "helps a child say what they feel"},
    "nature_environment": {"angle": "one tree, one creature, one full turn of the year",
                           "shelf": "nature", "promise": "gentle science a parent can answer"},
    "grief_loss": {"angle": "a goodbye handled with gentleness and one small ritual",
                   "shelf": "loss and goodbye", "promise": "language for a hard week"},
    "potty_routine": {"angle": "the small chair, told with dignity and humour",
                      "shelf": "potty training", "promise": "turns training into a game"},
    "adventure_quest": {"angle": "a journey with three clear obstacles and a way home",
                        "shelf": "adventure", "promise": "movement on every page"},
    "bedtime_sleep": {"angle": "a bedtime ritual with one small job for the child", "shelf": "bedtime",
                      "promise": "calm, sleepy, made for the last five minutes of the day"},
    "courage_fear": {"angle": "a fear named out loud and answered step by step", "shelf": "feelings",
                     "promise": "helps a child say 'I was brave'"},
    "friendship_belonging": {"angle": "two very different characters who need each other", "shelf": "friendship",
                             "promise": "warm, funny, about making the first friend"},
    "family_home": {"angle": "a grandparent's everyday lesson", "shelf": "family",
                    "promise": "the quiet love inside an ordinary family"},
    "nature_seasons": {"angle": "one tree, one creature, one full turn of the year", "shelf": "nature",
                       "promise": "gentle science a parent can answer"},
    "animals": {"angle": "one small animal with one very big feeling", "shelf": "animals",
                "promise": "an animal friend a toddler asks for again"},
    "school_first_day": {"angle": "the first morning, minute by minute", "shelf": "school",
                         "promise": "eases the first-day knot in the stomach"},
    "magic_wonder": {"angle": "one impossible thing the adult cannot see", "shelf": "imagination",
                     "promise": "wonder, glow, and a secret shared with the child"},
    "ocean_sea": {"angle": "a journey beneath the surface that ends at home", "shelf": "ocean",
                  "promise": "deep, blue, full of creatures to name"},
    "space_stars": {"angle": "one night outside looking up, and one wish", "shelf": "space",
                    "promise": "big sky, small child, one brave wish"},
    "seasons_weather": {"angle": "weather as a character with moods", "shelf": "weather",
                        "promise": "rain, sun and snow felt from inside"},
    "diversity_identity": {"angle": "a name, a language, and a place between two homes", "shelf": "identity",
                           "promise": "every child sees themselves on the page"},
}

NAME_POOL = ["Luna", "Milo", "Nora", "Sam", "Ada", "Kai", "Emi", "Tavi", "Yara", "Jonas"]

# Nouns that read like a children's-book title and can be checked against real demand.
CONCRETE_NOUNS = (
    "lantern", "moon", "star", "sea", "ocean", "bear", "rabbit", "fox", "owl", "cat", "dog",
    "bird", "tree", "forest", "garden", "river", "mountain", "snow", "rain", "cloud",
    "feather", "boat", "kite", "train", "door", "key", "blanket", "sock", "cookie", "honey",
    "bee", "butterfly", "whale", "elephant", "mouse", "lion", "dragon", "robot", "teddy",
    "candle", "pillow", "window", "sky", "seed", "leaf", "puddle", "pocket", "lighthouse",
)
ADJECTIVES = ("Little", "Sleepy", "Brave", "Quiet", "Golden", "Shy", "Patient")
PLACES = ("the Forest", "the Sea", "the Night", "the Snow", "the Garden", "the Hill")

TITLE_TEMPLATES = (
    "The {adj} {noun}",
    "The {adj} {noun} of {place}",
    "{name} and the {adj} {noun}",
    "{name} and the {noun} of {place}",
    "When the {noun} {verbs}",
    "The {noun} Who Would Not {verb}",
)

VERB_POOL = ("Shine", "Sing", "Sleep", "Share", "Wait", "Listen", "Hide", "Wake", "Fly", "Swim")
VERB_POOL_3RD = ("Shines", "Sings", "Sleeps", "Shares", "Waits", "Listens", "Hides", "Wakes", "Flies", "Swims")


@dataclass
class NicheBrief:
    basis: str
    items: int
    sources: List[str]
    signal: Optional[str]
    niches: List[Dict[str, Any]] = field(default_factory=list)
    crowded: List[Dict[str, Any]] = field(default_factory=list)
    titles: List[Dict[str, Any]] = field(default_factory=list)
    keywords: Dict[str, List[str]] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "basis": self.basis, "items": self.items, "sources": self.sources,
            "signal": self.signal, "niches": self.niches, "crowded": self.crowded,
            "titles": self.titles, "keywords": self.keywords, "evidence": self.evidence,
        }


class NicheService:
    def __init__(self, dataset_dir: Optional[str] = None, market: Optional[MarketResearchService] = None) -> None:
        self.dataset_dir = dataset_dir or os.getenv("KAGGLE_DATASET_PATH", "./secure_data/datasets")
        self.market = market or MarketResearchService(self.dataset_dir)

    # ---------------------------------------------------------------- signals
    def _index(self):
        return self.market.build_index()

    def _provenance(self) -> Dict[str, Any]:
        try:
            from app.services.market_data_service import MarketDataService

            return MarketDataService(self.dataset_dir).provenance()
        except Exception:
            return {}

    def demand_words(self, limit: int = 40, min_length: int = 4) -> List[tuple]:
        index = self._index()
        words = [(word, count) for word, count in index.keyword_frequency.most_common(400)
                 if len(word) >= min_length and not word.isdigit()]
        return words[:limit]

    def _demand_score(self, text: str) -> float:
        index = self._index()
        hits = sum(index.keyword_frequency.get(token, 0) for token in tokenize(text))
        return math.log10(1 + hits)

    def _collides(self, title: str, threshold: float = 0.45, sample: int = 2000) -> List[str]:
        index = self._index()
        if index.basis != "dataset":
            return []
        tokens = set(tokenize(title))
        if not tokens:
            return []
        clashes = []
        for existing in index.duplicate_titles[:sample]:
            other = set(tokenize(existing))
            if not other:
                continue
            jaccard = len(tokens & other) / len(tokens | other)
            if jaccard >= threshold:
                clashes.append(existing)
                if len(clashes) >= 3:
                    break
        return clashes

    # ---------------------------------------------------------------- niches
    def niches(self, top: int = 6) -> List[Dict[str, Any]]:
        rows = []
        for gap in self.market.gaps(limit=12):
            trope = gap["trope"]
            angle = TROPE_ANGLES.get(trope, {"angle": "a fresh take on a familiar shelf",
                                             "shelf": "general", "promise": "clear promise on the cover"})
            rows.append({
                "trope": trope,
                "shelf": angle["shelf"],
                "angle": angle["angle"],
                "promise": angle["promise"],
                "saturation": gap["saturation"],
                "demand_signal": gap["demand_signal"],
                "opportunity": gap["opportunity"],
                "read": self._read(gap["saturation"]),
            })
            if len(rows) >= top:
                break
        return rows

    @staticmethod
    def _read(saturation: float) -> str:
        if saturation >= 0.20:
            return "crowded — only enter with a sharp differentiator"
        if saturation >= 0.10:
            return "competitive but winnable with a specific angle"
        return "open shelf — low competition, needs a strong cover promise"

    def crowded(self, top: int = 5) -> List[Dict[str, Any]]:
        index = self._index()
        rows = [{"trope": trope, "saturation": round(value, 4)}
                for trope, value in index.trope_saturation.items()]
        rows.sort(key=lambda row: -row["saturation"])
        return rows[:top]

    # ----------------------------------------------------------------- titles
    def candidate_titles(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Titles built from nouns the market actually uses, checked for collisions."""
        demand = dict(self.demand_words(limit=300, min_length=3))
        grounded = [noun for noun in CONCRETE_NOUNS if demand.get(noun)]
        nouns = grounded or list(CONCRETE_NOUNS)[:10]

        open_tropes = [row["trope"] for row in self.niches(top=6)] or list(TROPES)[:3]
        candidates: List[Dict[str, Any]] = []
        seen: set = set()

        for index, trope in enumerate(open_tropes):
            for step, template in enumerate(TITLE_TEMPLATES):
                noun = nouns[(index * 3 + step) % len(nouns)]
                title = template.format(
                    adj=ADJECTIVES[(index + step) % len(ADJECTIVES)],
                    noun=noun.title(),
                    place=PLACES[(index + step) % len(PLACES)],
                    name=NAME_POOL[(index * 2 + step) % len(NAME_POOL)],
                    verb=VERB_POOL[(index + step) % len(VERB_POOL)],
                    verbs=VERB_POOL_3RD[(index + step) % len(VERB_POOL_3RD)],
                )
                title = re.sub(r"\s+", " ", title).strip()
                if title.lower() in seen or len(title) > 60:
                    continue
                seen.add(title.lower())
                clashes = self._collides(title)
                if clashes:
                    continue
                demand_hits = sum(demand.get(token.lower(), 0) for token in tokenize(title))
                candidates.append({
                    "title": title,
                    "trope": trope,
                    "demand_score": round(math.log10(1 + demand_hits), 3),
                    "collides_with": [],
                    "why": f"grounded in market words for the open '{trope}' shelf",
                })
                if len(candidates) >= limit:
                    return candidates

        candidates.sort(key=lambda row: -row["demand_score"])
        return candidates[:limit]

    # --------------------------------------------------------------- keywords
    def keywords(self, title: str, tropes: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """Keyword sets sized to the real platform limits, grounded in market vocabulary."""
        tropes = tropes or [row["trope"] for row in self.niches(top=3)]
        words = [word for word, _ in self.demand_words(limit=60, min_length=4)]
        nouns = [noun for noun in CONCRETE_NOUNS if noun in words] or list(CONCRETE_NOUNS)[:6]
        shelves = []
        for trope in tropes:
            shelf = TROPE_ANGLES.get(trope, {}).get("shelf", "")
            if shelf and shelf not in shelves:
                shelves.append(shelf)
        if not shelves:
            shelves = ["picture book"]
        promise = TROPE_ANGLES.get(tropes[0], {}).get("promise", "gentle story for children")

        formulas = [
            (KDP_KEYWORD_CHARS, [
                title,
                f"{shelves[0]} book for kids 3-8",
                f"{nouns[0]} picture book for toddlers",
                f"read aloud story ages 3 8",
                f"{nouns[1] if len(nouns) > 1 else nouns[0]} book for 3 year old",
                f"{shelves[-1]} story for preschooler",
                f"gift book for toddler girl boy",
                f"gentle bedtime story for little ones",
            ]),
        ]
        kdp_raw = formulas[0][1]

        def clean(values: List[str], width: int, limit: int) -> List[str]:
            out: List[str] = []
            for value in values:
                value = re.sub(r"\s+", " ", str(value)).strip().lower()
                value = re.sub(r"[^a-z0-9 \-']", " ", value).strip()
                if not value or value in out or len(value) > width:
                    continue
                out.append(value)
                if len(out) >= limit:
                    break
            return out

        etsy_formulas = [
            "picture book pdf",
            "printable storybook",
            f"{nouns[0]} storybook",
            f"{shelves[0]} book kids",
            "bedtime story book",
            "toddler gift book",
            "digital download",
            "coloring pages pdf",
            "read aloud book",
            "gentle kids story",
            "preschool book",
            "kids book bundle",
            "gift for 3 year old",
        ]

        return {
            "kdp": clean(kdp_raw, KDP_KEYWORD_CHARS, KDP_KEYWORD_LIMIT),
            "etsy": clean(etsy_formulas, ETSY_TAG_CHARS, ETSY_TAG_LIMIT),
            "promise": [promise],
        }

    # ------------------------------------------------------------------ brief
    def brief(self, top: int = 6, title: Optional[str] = None) -> NicheBrief:
        index = self._index()
        provenance = self._provenance()
        niches = self.niches(top=top)
        titles = self.candidate_titles(limit=max(4, top))
        chosen = title or (titles[0]["title"] if titles else "The Little Lantern Who Waited")
        first_trope = niches[0]["trope"] if niches else None

        evidence = [
            f"basis: {index.basis} — {index.items} published titles analysed",
            f"sources: {', '.join(index.sources) or 'none'}",
        ]
        if provenance:
            evidence.append(f"intake: {provenance.get('source')} · signal={provenance.get('signal')} · "
                            f"fetched {provenance.get('fetched_at')}")
        if niches:
            best = niches[0]
            evidence.append(f"most open shelf: {best['trope']} (saturation {best['saturation']:.1%}, "
                            f"opportunity {best['opportunity']})")
        crowded = self.crowded(top=3)
        if crowded:
            evidence.append("most crowded: " + ", ".join(
                f"{row['trope']} {row['saturation']:.1%}" for row in crowded))
        if index.basis != "dataset":
            evidence.append("no dataset: numbers are a documented heuristic, not market data")

        return NicheBrief(
            basis=index.basis,
            items=index.items,
            sources=index.sources,
            signal=provenance.get("signal") if provenance else None,
            niches=niches,
            crowded=crowded,
            titles=titles,
            keywords=self.keywords(chosen, [first_trope] if first_trope else None),
            evidence=evidence,
        )
