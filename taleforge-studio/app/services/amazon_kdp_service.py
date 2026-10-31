"""Amazon KDP listing preparation."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

KDP_TRIM_SIZES = ["6x9", "8.5x8.5", "8x10", "8.25x8.25", "7.5x9.25"]


@dataclass
class KDPListing:
    title: str
    subtitle: str
    description: str
    keywords: List[str]
    category: str
    trim_size: str
    page_count: int
    age_range: str
    language: str
    price: float
    royalty_option: str = "60%"
    isbn_required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AmazonKDPService:
    @staticmethod
    def validate(product: Dict[str, Any]) -> List[str]:
        warnings: List[str] = []
        trim = product.get("trim_size", "6x9")
        if trim not in KDP_TRIM_SIZES:
            warnings.append(f"trim_size '{trim}' is not a standard KDP trim ({', '.join(KDP_TRIM_SIZES)})")
        if int(product.get("page_count", 0)) < 24:
            warnings.append("KDP requires at least 24 pages for a paperback")
        keywords = product.get("keywords", [])
        if len(keywords) > 7:
            warnings.append("KDP accepts a maximum of 7 keyword slots")
        if float(product.get("price", 0)) < 2.99:
            warnings.append("Price below 2.99 USD may trigger minimum-list-price issues for print")
        return warnings

    @staticmethod
    def build_listing(product: Dict[str, Any]) -> KDPListing:
        return KDPListing(
            title=product.get("title", "Untitled"),
            subtitle=product.get("subtitle", "A magical children's story"),
            description=product.get("description", "A beautifully illustrated storybook for children."),
            keywords=product.get("keywords", ["children storybook", "storybook", "gift for kids"])[:7],
            category=product.get("category", "Children's Books"),
            trim_size=product.get("trim_size", "6x9"),
            page_count=int(product.get("page_count", 24)),
            age_range=product.get("age_range", product.get("age_group", "4-8")),
            language=product.get("language", "en"),
            price=float(product.get("price", 12.99)),
        )
