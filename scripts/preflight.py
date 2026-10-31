"""Preflight — check a finished PDF before it goes to the printer.

    python scripts/preflight.py --pdf output/luna_and_the_lantern_forest_interior.pdf --trim US_6_X_9

Checks (no dependencies, pure Python + optional poppler/qpdf):

* page count and page geometry in mm (trim + bleed as configured)
* consistent page sizes across the document
* PDF/X output intent present? (most printers ask for PDF/X-1a)
* fonts embedded? (uses ``pdffonts`` when poppler is installed)
* images present and page size reachable at 300 dpi (heuristic report)

Exit code 0 = pass, 1 = problems found.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.page_layout_service import PageLayoutService  # noqa: E402

MM = 72 / 25.4


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF preflight")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--trim", default="US_6_X_9")
    parser.add_argument("--page-type", default="single")
    parser.add_argument("--bleed", type=float, default=3.0)
    args = parser.parse_args()

    path = Path(args.pdf)
    if not path.exists():
        print(f"missing file: {path}")
        return 1

    raw = path.read_bytes()
    layout = PageLayoutService.build_layout(trim_size=args.trim, page_type=args.page_type, bleed_mm=args.bleed)
    expected = layout.page_box_mm

    boxes = re.findall(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]", raw)
    pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    sizes = sorted({(round((float(b[2]) - float(b[0])) / MM, 2), round((float(b[3]) - float(b[1])) / MM, 2)) for b in boxes})

    problems = []
    print(f"file          : {path.name} ({len(raw) / 1024:.0f} KB)")
    print(f"pages         : {pages}")
    print(f"expected size : {expected[0]:.1f} x {expected[1]:.1f} mm ({args.trim}, {args.page_type}, bleed {args.bleed} mm)")

    if not sizes:
        problems.append("no /MediaBox found — the PDF may be malformed")
    else:
        for width, height in sizes:
            print(f"found size    : {width:.1f} x {height:.1f} mm")
            if abs(width - expected[0]) > 1.0 or abs(height - expected[1]) > 1.0:
                problems.append(f"page size {width}x{height} mm differs from {expected[0]:.1f}x{expected[1]:.1f} mm")
        if len(sizes) > 1:
            problems.append("pages have different sizes — a printer cannot impose this cleanly")

    output_intent = b"/OutputIntent" in raw
    print(f"output intent : {'present (PDF/X ready)' if output_intent else 'absent (plain PDF)'}")
    if not output_intent:
        problems.append("no output intent: add a PDF/X intent or tell the printer the target CMYK profile")

    pdffonts = shutil.which("pdffonts")
    if pdffonts:
        result = subprocess.run([pdffonts, str(path)], capture_output=True, text=True)
        lines = [line for line in result.stdout.splitlines()[2:] if line.strip()]
        not_embedded = [line for line in lines if re.search(r"\sno\s+(yes|no)\s", line)]
        print(f"fonts         : {len(lines)} found, {len(not_embedded)} not embedded")
        if not_embedded:
            problems.append(f"{len(not_embedded)} font(s) are not embedded")
    else:
        print("fonts         : install poppler-utils to verify embedding (apt install poppler-utils)")

    qpdf = shutil.which("qpdf")
    if qpdf:
        check = subprocess.run([qpdf, "--check", str(path)], capture_output=True, text=True)
        print(f"structure     : {'ok' if check.returncode == 0 else 'errors'}")
        if check.returncode != 0:
            problems.append("qpdf reports structural errors")
    else:
        print("structure     : install qpdf to verify the file structure")

    image_objects = len(re.findall(rb"/Subtype\s*/Image", raw))
    print(f"images        : {image_objects} placed (each must be >= {int(expected[0] * 300 / 25.4)} px wide at 300 dpi)")

    print("\nverdict       :", "PASS" if not problems else "PROBLEMS")
    for problem in problems:
        print("  -", problem)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
