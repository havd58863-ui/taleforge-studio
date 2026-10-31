"""Product metadata / listing copy generation."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ProductMetadata:
    product_id: str
    title: str
    subtitle: Optional[str]
    category: str
    age_group: str
    language: str
    format_type: str
    price: float
    currency: str = "USD"
    trim_size: str = "6x9"
    page_count: int = 24
    listing_title: str = ""
    listing_description: str = ""
    seo_keywords: List[str] = field(default_factory=list)
    cover_image: str = ""
    preview_image: str = ""
    digital_files: List[str] = field(default_factory=list)
    print_files: List[str] = field(default_factory=list)
    metadata_json: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["updated_at"] = self.updated_at.isoformat()
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class MetadataService:
    @staticmethod
    def build_listing_text(title: str, subtitle: str, category: str, age_group: str, language: str) -> str:
        subtitle_part = f" {subtitle}" if subtitle else ""
        return (
            f"{title}{subtitle_part} | {category} children's book | ages {age_group} | "
            f"{language.upper()} | beautifully illustrated storybook with premium page design"
        )

    @staticmethod
    def build_description(title: str, subtitle: str, age_group: str, page_count: int, language: str) -> str:
        subtitle_part = f"{subtitle}. " if subtitle else ""
        return (
            f"{title} — {subtitle_part}A gentle, beautifully illustrated story for children aged "
            f"{age_group}, designed for shared reading at bedtime or in the classroom.\n\n"
            f"• {page_count} premium illustration-ready pages\n"
            f"• Language: {language.upper()}\n"
            f"• Print-ready interior with bleed and safe-margin guides\n"
            f"• Warm, emotionally clear artwork that supports early literacy\n\n"
            f"Perfect as a gift, a read-aloud favourite, or a keepsake for a young reader."
        )

    @staticmethod
    def build_keywords(title: str, category: str, old_tags: Optional[List[str]] = None) -> List[str]:
        tags = [
            title.lower(),
            category.lower(),
            "children storybook",
            "storybook",
            "printable",
            "gift for kids",
            "family reading",
            "bedtime story",
        ]
        if old_tags:
            tags.extend(old_tags)
        seen: Dict[str, None] = {}
        for tag in tags:
            seen.setdefault(tag.strip(), None)
        return list(seen.keys())[:25]

    @staticmethod
    def create_metadata(
        product_id: str,
        title: str,
        subtitle: str = "",
        category: str = "Picture Book",
        age_group: str = "4-8",
        language: str = "en",
        format_type: str = "paperback",
        price: float = 0.0,
        trim_size: str = "6x9",
        page_count: int = 24,
        cover_image: str = "",
        preview_image: str = "",
        digital_files: Optional[List[str]] = None,
        print_files: Optional[List[str]] = None,
    ) -> ProductMetadata:
        listing_title = MetadataService.build_listing_text(title, subtitle, category, age_group, language)
        description = MetadataService.build_description(title, subtitle, age_group, page_count, language)
        keywords = MetadataService.build_keywords(title, category)

        metadata_json = {
            "product_id": product_id,
            "title": title,
            "subtitle": subtitle,
            "category": category,
            "age_group": age_group,
            "language": language,
            "format_type": format_type,
            "price": price,
            "currency": "USD",
            "trim_size": trim_size,
            "page_count": page_count,
            "cover_image": cover_image,
            "preview_image": preview_image,
            "digital_files": digital_files or [],
            "print_files": print_files or [],
            "seo_keywords": keywords,
        }

        return ProductMetadata(
            product_id=product_id,
            title=title,
            subtitle=subtitle,
            category=category,
            age_group=age_group,
            language=language,
            format_type=format_type,
            price=price,
            trim_size=trim_size,
            page_count=page_count,
            listing_title=listing_title,
            listing_description=description,
            seo_keywords=keywords,
            cover_image=cover_image,
            preview_image=preview_image,
            digital_files=digital_files or [],
            print_files=print_files or [],
            metadata_json=metadata_json,
        )
