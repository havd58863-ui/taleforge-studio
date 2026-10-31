"""Digital e-book export (plain text + EPUB 3)."""
from __future__ import annotations

import html
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

XML_DECL = '<?xml version="1.0" encoding="utf-8"?>'


class EbookService:
    @staticmethod
    def create_ebook_from_text(title: str, paragraphs: List[str], output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{title}\n\n" + "\n\n".join(paragraphs), encoding="utf-8")
        return str(output)

    @staticmethod
    def create_epub(
        title: str,
        paragraphs: List[str],
        output_path: str,
        author: str = "TaleForge Studio",
        language: str = "en",
        cover_image: Optional[str] = None,
    ) -> str:
        """Minimal, valid EPUB 3 package (mimetype stored uncompressed, as required)."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        book_id = str(uuid.uuid4())
        direction = "rtl" if language == "ar" else "ltr"
        safe_title = html.escape(title)
        modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        body = "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)

        chapter = "\n".join(
            [
                XML_DECL,
                "<!DOCTYPE html>",
                f'<html xmlns="http://www.w3.org/1999/xhtml" lang="{language}" dir="{direction}">',
                f"<head><title>{safe_title}</title><meta charset=\"utf-8\"/></head>",
                f"<body><h1>{safe_title}</h1>{body}</body></html>",
            ]
        )

        nav = "\n".join(
            [
                XML_DECL,
                '<html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops" '
                f'lang="{language}" dir="{direction}">',
                f"<head><title>{safe_title}</title></head><body>",
                '<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>',
                '<li><a href="chapter1.xhtml">Chapter 1</a></li>',
                "</ol></nav></body></html>",
            ]
        )

        manifest_items = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>',
        ]
        if cover_image and Path(cover_image).exists():
            manifest_items.append(
                f'<item id="cover" href="{Path(cover_image).name}" media-type="image/jpeg"/>'
            )

        opf = "\n".join(
            [
                XML_DECL,
                '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
                'unique-identifier="bookid">',
                '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">',
                f'<dc:identifier id="bookid">urn:uuid:{book_id}</dc:identifier>',
                f"<dc:title>{safe_title}</dc:title>",
                f"<dc:creator>{html.escape(author)}</dc:creator>",
                f"<dc:language>{language}</dc:language>",
                f'<meta property="dcterms:modified">{modified}</meta>',
                "</metadata>",
                "<manifest>" + "".join(manifest_items) + "</manifest>",
                '<spine><itemref idref="ch1"/></spine>',
                "</package>",
            ]
        )

        container = "\n".join(
            [
                XML_DECL,
                '<container version="1.0" '
                'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">',
                "<rootfiles>",
                '<rootfile full-path="OEBPS/content.opf" '
                'media-type="application/oebps-package+xml"/>',
                "</rootfiles></container>",
            ]
        )

        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            archive.writestr("META-INF/container.xml", container)
            archive.writestr("OEBPS/content.opf", opf)
            archive.writestr("OEBPS/nav.xhtml", nav)
            archive.writestr("OEBPS/chapter1.xhtml", chapter)
            if cover_image and Path(cover_image).exists():
                archive.write(cover_image, f"OEBPS/{Path(cover_image).name}")
        return str(output)
