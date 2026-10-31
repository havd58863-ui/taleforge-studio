"""Kaggle helper: check credentials, search datasets, download research data.

Usage:
    python scripts/kaggle_sync.py --status
    python scripts/kaggle_sync.py --search "children book illustration"
    python scripts/kaggle_sync.py --download owner/dataset-name

Credentials come from KAGGLE_USERNAME / KAGGLE_KEY (env or GitHub Secrets)
or from ~/.kaggle/kaggle.json. Nothing is ever written into the repository.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.kaggle_service import KaggleService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Kaggle research-data helper")
    parser.add_argument("--status", action="store_true", help="show credential/package status")
    parser.add_argument("--search", metavar="QUERY", help="search public datasets")
    parser.add_argument("--download", metavar="OWNER/DATASET", help="download a dataset")
    parser.add_argument("--no-unzip", action="store_true", help="keep the archive as-is")
    parser.add_argument("--list", action="store_true", help="list datasets already downloaded")
    args = parser.parse_args()

    create_app()  # loads .env and prepares folders
    service = KaggleService()

    if args.status or not any([args.search, args.download, args.list]):
        print(json.dumps(service.status(), indent=2, ensure_ascii=False))
        return 0

    if args.list:
        print(json.dumps(service.list_local(), indent=2, ensure_ascii=False))
        return 0

    if args.search:
        try:
            items = service.search_datasets(args.search)
        except Exception as exc:
            print(f"search failed: {exc}", file=sys.stderr)
            return 1
        for item in items:
            print(f"- {item['ref']}: {item['title']}  ({item['url']})")
        return 0

    if args.download:
        try:
            manifest = service.download_dataset(args.download, unzip=not args.no_unzip)
        except Exception as exc:
            print(f"download failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
