"""32-page picture-book structure, the way a publisher builds it.

A 24-page story does **not** fill a 32-page book. The remaining eight pages are the
front and back matter every trade picture book carries:

    p1  half-title        p2  title page      p3  copyright      p4  dedication
    p5–p28  the story (24 pages, some of them double-page spreads)
    p29 the end           p30 about the author  p31 the series  p32 colophon

The service also decides **which story pages become double-page spreads**: spreads are
expensive real estate, so they are reserved for the two emotional peaks (climax and the
final image) and never used for dialogue pages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

FRONT_KINDS = ("half_title", "title_page", "copyright", "dedication")
BACK_KINDS = ("the_end", "about_author", "series_page", "colophon")


@dataclass
class BookPage:
    page: int
    kind: str                    # half_title | story | the_end | …
    page_type: str               # full_bleed | front_matter
    text: str = ""
    text_secondary: str = ""
    scene: str = ""
    spread: str = ""             # "" | "left" | "right"
    beat: str = ""
    language: str = "en"
    language_secondary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page": self.page, "kind": self.kind, "page_type": self.page_type,
            "text": self.text, "text_secondary": self.text_secondary, "scene": self.scene,
            "spread": self.spread, "beat": self.beat,
            "language": self.language, "language_secondary": self.language_secondary,
        }


@dataclass
class BookStructure:
    title: str
    pages: List[BookPage] = field(default_factory=list)
    story_pages: int = 24
    spread_pairs: List[tuple] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "page_count": self.page_count,
            "story_pages": self.story_pages,
            "spread_pairs": self.spread_pairs,
            "warnings": self.warnings,
            "pages": [page.to_dict() for page in self.pages],
        }


class BookStructureService:
    SPREAD_ANCHORS = (0.58, 0.92)   # relative positions inside the story arc: climax, finale

    def build(
        self,
        title: str,
        story: List[str],
        language: str = "en",
        subtitle: str = "",
        author: str = "TaleForge Studio",
        dedication: str = "",
        isbn_placeholder: str = "978-0-00-000000-0",
        year: str = "2026",
        allow_spreads: bool = True,
        story_secondary: Optional[List[str]] = None,
        language_secondary: str = "",
        beats: Optional[List[str]] = None,
    ) -> BookStructure:
        if len(story) != 24:
            raise ValueError(f"a trade picture book needs exactly 24 story pages, got {len(story)}")

        warnings: List[str] = []
        spread_starts: List[int] = []
        if allow_spreads:
            for anchor in self.SPREAD_ANCHORS:
                index = int(round(anchor * (len(story) - 1)))
                index -= index % 2  # a spread starts on an odd story page (left page of the pair)
                if 0 <= index < len(story) - 1 and index not in spread_starts:
                    spread_starts.append(index)
        spread_starts.sort()

        pages: List[BookPage] = []
        page_no = 1

        front_text = {
            "half_title": title,
            "title_page": f"{title}\n{subtitle}" if subtitle else title,
            "copyright": (
                f"Text and illustrations © {year} {author}. All rights reserved.\n"
                f"First edition {year}. Printed by the publisher.\n"
                f"ISBN {isbn_placeholder}\n"
                "No part of this book may be reproduced without written permission."
            ),
            "dedication": dedication or "For every small reader who leaves the gate open.",
        }
        for kind in FRONT_KINDS:
            pages.append(BookPage(page=page_no, kind=kind, page_type="front_matter",
                                  text=front_text[kind], language=language))
            page_no += 1

        story_start_page = page_no
        for index, text in enumerate(story):
            is_spread = index in spread_starts
            if is_spread:
                side = "left"
            elif index - 1 in spread_starts:
                side = "right"
            else:
                side = ""
            pages.append(
                BookPage(
                    page=page_no, kind="story", page_type="full_bleed", text=text,
                    text_secondary=(story_secondary[index] if story_secondary else ""),
                    scene=text, spread=side,
                    beat=(beats[index] if beats and index < len(beats) else ""),
                    language=language, language_secondary=language_secondary,
                )
            )
            page_no += 1

        back_text = {
            "the_end": "The End",
            "about_author": f"{author} writes picture books about small children making brave, kind choices.",
            "series_page": (
                "More Luna stories:\n"
                "Luna and the River of Stars\n"
                "Luna and the Winter Lantern\n"
                "Luna and the Long Way Home"
            ),
            "colophon": (
                "Set in Andika, designed for emerging readers.\n"
                "Printed on 118 gsm matte paper, 6 × 9 in, 300 dpi.\n"
                "Illustrations created for this edition."
            ),
        }
        for kind in BACK_KINDS:
            pages.append(BookPage(page=page_no, kind=kind, page_type="front_matter",
                                  text=back_text[kind], language=language))
            page_no += 1

        if page_no - 1 != 32:
            warnings.append(f"page count is {page_no - 1}, expected 32")

        return BookStructure(
            title=title, pages=pages, story_pages=len(story),
            spread_pairs=[(story_start_page + start, story_start_page + start + 1) for start in spread_starts],
            warnings=warnings,
        )

    @staticmethod
    def story_only(structure: BookStructure) -> List[BookPage]:
        return [page for page in structure.pages if page.kind == "story"]
