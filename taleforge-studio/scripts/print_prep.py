"""Stage 4 — make an illustration press-ready and prove it with the quality gate.

    python scripts/print_prep.py --image art.png --trim US_6_X_9 --page-type full_bleed
    python scripts/print_prep.py --image art.png --cmyk --icc /path/ISOcoated_v2.icc
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.page_layout_service import PageLayoutService  # noqa: E402
from app.services.print_image_service import PrintImageService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Print preparation + gate")
    parser.add_argument("--image", required=True)
    parser.add_argument("--trim", default="US_6_X_9")
    parser.add_argument("--page-type", default="full_bleed")
    parser.add_argument("--mode", default="cover", choices=["cover", "contain"])
    parser.add_argument("--cmyk", action="store_true")
    parser.add_argument("--icc")
    parser.add_argument("--out")
    args = parser.parse_args()

    create_app()
    layout = PageLayoutService.build_layout(trim_size=args.trim, page_type=args.page_type)
    result = PrintImageService().prepare(
        args.image, layout, args.out, mode=args.mode, cmyk=args.cmyk, icc_profile=args.icc
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
