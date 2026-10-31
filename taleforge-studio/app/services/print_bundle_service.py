"""Print bundle assembly (interior + cover + guides + manifest)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


class PrintBundleService:
    REQUIRED = ("interior", "cover")

    @staticmethod
    def create_print_bundle(
        product_name: str,
        source_files: List[str],
        output_dir: str,
        specs: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)

        copied: List[str] = []
        missing: List[str] = []
        for file_path in source_files:
            src = Path(file_path)
            if src.exists():
                dest = target / src.name
                shutil.copy2(src, dest)
                copied.append(str(dest))
            else:
                missing.append(str(src))

        manifest = {
            "product_name": product_name,
            "specs": specs or {
                "trim": "6x9 in",
                "bleed": "0.125 in (3 mm)",
                "safe_margin": "0.5 in (12 mm)",
                "color": "sRGB → printer profile at proofing",
                "resolution": "300 dpi",
            },
            "files": [Path(p).name for p in copied],
            "missing": missing,
            "status": "print_ready" if copied and not missing else "incomplete",
        }
        (target / "print_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest["output_dir"] = str(target)
        return manifest
