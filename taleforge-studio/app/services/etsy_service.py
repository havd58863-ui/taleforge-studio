"""Etsy digital-download listing preparation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

ETSY_TAG_LIMIT = 13


@dataclass
class EtsyListing:
    title: str
    description: str
    tags: List[str]
    price: float
    format: str
    category: str
    audience: str
    thumbnail: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EtsyService:
    @staticmethod
    def validate(listing: EtsyListing) -> List[str]:
        warnings: List[str] = []
        if len(listing.title) > 140:
            warnings.append("Etsy title exceeds 140 characters")
        if len(listing.tags) > ETSY_TAG_LIMIT:
            warnings.append(f"Etsy allows max {ETSY_TAG_LIMIT} tags")
        for tag in listing.tags:
            if len(tag) > 20:
                warnings.append(f"tag '{tag}' exceeds 20 characters")
        return warnings

    @staticmethod
    def build_listing(product: Dict[str, Any]) -> EtsyListing:
        tags = [t.lower()[:20] for t in product.get(
            "tags",
            ["storybook", "children book", "kids gift", "printable book", "bedtime story"],
        )][:ETSY_TAG_LIMIT]
        return EtsyListing(
            title=product.get("title", "Children's Storybook")[:140],
            description=product.get(
                "description",
                "A premium children's storybook with original artwork and print-ready export.",
            ),
            tags=tags,
            price=float(product.get("price", 9.99)),
            format=product.get("format", "PDF"),
            category=product.get("category", "Children's Books"),
            audience=product.get("audience", "Children 4-8"),
            thumbnail=product.get("thumbnail", "cover.png"),
        )
