"""Export bundles for print and digital channels."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExportService:
    def __init__(self, root_dir: str = "./output") -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_bundle(
        self,
        product_name: str,
        files: List[str],
        export_dir: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        slug = product_name.lower().replace(" ", "_")
        target = Path(export_dir) if export_dir else self.root_dir / f"{slug}_final_export"
        target.mkdir(parents=True, exist_ok=True)

        copied: List[str] = []
        missing: List[str] = []
        for path in files:
            src = Path(path)
            if src.exists():
                dest = target / src.name
                shutil.copy2(src, dest)
                copied.append(str(dest))
            else:
                missing.append(str(src))

        if metadata is not None:
            meta_path = target / "metadata.json"
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            copied.append(str(meta_path))

        manifest = {
            "product_name": product_name,
            "files": [Path(p).name for p in copied],
            "missing": missing,
            "status": "ready" if copied and not missing else "incomplete",
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return str(target)

    def zip_bundle(self, bundle_dir: str, zip_path: Optional[str] = None) -> str:
        bundle = Path(bundle_dir)
        target = Path(zip_path) if zip_path else bundle.with_suffix(".zip")
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(bundle.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(bundle))
        return str(target)
