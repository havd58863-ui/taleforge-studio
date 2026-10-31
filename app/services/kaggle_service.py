"""Kaggle research-dataset integration.

Credentials (in priority order):
  1. ``KAGGLE_USERNAME`` + ``KAGGLE_KEY`` environment variables
     (put them in GitHub Secrets / your server env — never in the repo)
  2. an existing ``~/.kaggle/kaggle.json`` or ``$KAGGLE_CONFIG_DIR/kaggle.json``

Nothing here runs at import time, so the platform boots without Kaggle installed
and without credentials.
"""
from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class KaggleService:
    def __init__(self) -> None:
        self.username = os.getenv("KAGGLE_USERNAME", "").strip()
        self.key = os.getenv("KAGGLE_KEY", "").strip()
        self.datasets_dir = Path(os.getenv("KAGGLE_DATASET_PATH", "./secure_data/datasets"))
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir = Path(os.getenv("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle"))

    # ---------------------------------------------------------------- status
    @property
    def credentials_file(self) -> Path:
        return self.config_dir / "kaggle.json"

    def has_env_credentials(self) -> bool:
        return bool(self.username and self.key)

    def has_file_credentials(self) -> bool:
        return self.credentials_file.exists()

    def configured(self) -> bool:
        """True when the kaggle package is installed and credentials exist."""
        if not (self.has_env_credentials() or self.has_file_credentials()):
            return False
        try:
            import kaggle  # noqa: F401
        except Exception:
            return False
        return True

    def status(self) -> Dict[str, Any]:
        try:
            import kaggle  # noqa: F401

            installed = True
        except Exception:
            installed = False
        return {
            "package_installed": installed,
            "credentials_from_env": self.has_env_credentials(),
            "credentials_from_file": self.has_file_credentials(),
            "configured": self.configured(),
            "datasets_dir": str(self.datasets_dir),
            "datasets_dir_writable": os.access(self.datasets_dir, os.W_OK),
            "hint": (
                "Set KAGGLE_USERNAME and KAGGLE_KEY as repository secrets, "
                "or drop kaggle.json into ~/.kaggle/"
            ),
        }

    # ------------------------------------------------------------ credentials
    def build_kaggle_config(self) -> str:
        """Write the credentials file with 0600 permissions and return its path."""
        if not self.has_env_credentials():
            if self.has_file_credentials():
                self._harden_permissions()
                return str(self.credentials_file)
            raise RuntimeError(
                "Kaggle credentials are not configured. Set KAGGLE_USERNAME and KAGGLE_KEY."
            )

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.credentials_file.write_text(
            json.dumps({"username": self.username, "key": self.key}, indent=2),
            encoding="utf-8",
        )
        self._harden_permissions()
        return str(self.credentials_file)

    def _harden_permissions(self) -> None:
        try:
            self.credentials_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except Exception:  # pragma: no cover - e.g. exotic filesystems
            pass

    def _client(self):
        if not self.configured():
            raise RuntimeError(
                "Kaggle is not ready: install the 'kaggle' package and set "
                "KAGGLE_USERNAME / KAGGLE_KEY (or provide ~/.kaggle/kaggle.json)."
            )
        self.build_kaggle_config()
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()
        return api

    # --------------------------------------------------------------- datasets
    def search_datasets(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        api = self._client()
        results = api.dataset_list(search=query, page=1, sort_by="hottest")[:limit]
        items = []
        for item in results:
            items.append(
                {
                    "ref": getattr(item, "ref", None) or f"{item.ref}",
                    "title": getattr(item, "title", ""),
                    "size": getattr(item, "totalBytes", None),
                    "last_updated": str(getattr(item, "lastUpdated", "")),
                    "download_count": getattr(item, "downloadCount", None),
                    "url": f"https://www.kaggle.com/datasets/{getattr(item, 'ref', '')}",
                }
            )
        return items

    def download_dataset(self, dataset_ref: str, unzip: bool = True) -> Dict[str, Any]:
        """Download a dataset and write a manifest so the data is traceable."""
        if not dataset_ref or "/" not in dataset_ref:
            raise ValueError("dataset_ref must look like 'owner/dataset-name'")

        api = self._client()
        target = self.datasets_dir / dataset_ref.replace("/", "__")
        target.mkdir(parents=True, exist_ok=True)

        api.dataset_download_files(dataset_ref, path=str(target), unzip=unzip, quiet=False)

        files = [p for p in target.rglob("*") if p.is_file()]
        manifest = {
            "dataset": dataset_ref,
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "unzipped": unzip,
            "file_count": len(files),
            "total_bytes": sum(p.stat().st_size for p in files),
            "files": [str(p.relative_to(target)) for p in files][:200],
            "target": str(target),
            "notice": "Research/reference data only — never commit this folder.",
        }
        (target / "_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest

    def list_local(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for manifest_path in sorted(self.datasets_dir.glob("*/_manifest.json")):
            try:
                items.append(json.loads(manifest_path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return items
