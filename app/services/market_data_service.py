"""Market data intake — real catalogue/bestseller rows into ``secure_data/datasets``.

Two providers, one output shape (a CSV/JSON the ``MarketResearchService`` already reads):

* **Kaggle** (primary, needs ``KAGGLE_USERNAME`` + ``KAGGLE_KEY``) — download bestseller and
  metadata datasets with the official API. This is the strongest signal: real sales ranks,
  categories and review counts.
* **Open Library** (public, no credentials) — the Open Library catalogue API. Thousands of
  published children's titles with subjects, first publication year and edition counts.
  It is catalogue data, not sales data, so it is labelled as such in the provenance file.

Whatever the provider, every intake writes ``provenance.json`` so the analysis can never
pretend a heuristic is market data:

    {"source": "openlibrary", "url": "...", "fetched_at": "...Z", "rows": 4000,
     "signal": "catalogue", "note": "..."}
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

USER_AGENT = "TaleForgeStudio/1.0 (children's book market research; contact: owner)"

# Children's-book datasets on Kaggle worth downloading (slug, why).
DEFAULT_KAGGLE_DATASETS: List[Dict[str, str]] = [
    {"ref": "sootersaalu/amazon-top-50-bestselling-books-2009-2019",
     "why": "Amazon top-50 bestsellers by year: the closest public proxy for 'what sells'"},
    {"ref": "dylanjcastillo/7k-books-with-metadata",
     "why": "7k books with category, rating and description text — broad demand baseline"},
    {"ref": "thedevastator/books-sales-and-ratings",
     "why": "sales and ratings, useful for price/quality positioning"},
]

# Subjects used when we fall back to the public catalogue.
DEFAULT_SUBJECTS: List[str] = [
    "picture_books", "children's_fiction", "bedtime", "juvenile_fiction",
    "friendship", "animals", "family", "fantasy", "bedtime_stories", "adventure",
]
SUBJECT_URL = "https://openlibrary.org/subjects/{subject}.json?limit={limit}&offset={offset}"


@dataclass
class IntakeResult:
    provider: str
    files: List[str] = field(default_factory=list)
    rows: int = 0
    signal: str = "catalogue"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"provider": self.provider, "files": self.files, "rows": self.rows,
                "signal": self.signal, "notes": self.notes}


class MarketDataService:
    """Fill ``secure_data/datasets`` from Kaggle (primary) or Open Library (public)."""

    def __init__(self, dataset_dir: Optional[str] = None) -> None:
        self.dataset_dir = Path(
            dataset_dir or os.getenv("KAGGLE_DATASET_PATH", "./secure_data/datasets")
        )

    # ---------------------------------------------------------------- provenance
    @property
    def provenance_path(self) -> Path:
        return self.dataset_dir / "provenance.json"

    def provenance(self) -> Dict[str, Any]:
        if not self.provenance_path.exists():
            return {}
        try:
            return json.loads(self.provenance_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_provenance(self, result: IntakeResult, extra: Optional[Dict[str, Any]] = None) -> None:
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "source": result.provider,
            "signal": result.signal,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "rows": result.rows,
            "files": result.files,
            "notes": result.notes,
        }
        payload.update(extra or {})
        self.provenance_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------- kaggle
    def kaggle_ready(self) -> bool:
        try:
            from app.services.kaggle_service import KaggleService

            return bool(KaggleService().configured())
        except Exception:
            return False

    def sync_from_kaggle(self, refs: Optional[Iterable[str]] = None) -> IntakeResult:
        """Download bestseller/metadata datasets with the official Kaggle API."""
        from app.services.kaggle_service import KaggleService

        service = KaggleService()
        if not service.configured():
            raise RuntimeError(
                "Kaggle is not configured: set KAGGLE_USERNAME and KAGGLE_KEY "
                "(from kaggle.json) — or use provider='openlibrary' for public catalogue data"
            )

        wanted = list(refs or [d["ref"] for d in DEFAULT_KAGGLE_DATASETS])
        result = IntakeResult(provider="kaggle", signal="bestsellers")
        for ref in wanted:
            try:
                downloaded = service.download_dataset(ref, unzip=True)
                files = downloaded.get("files") or []
                result.files.extend(files)
                result.rows += int(downloaded.get("rows", 0) or 0)
                result.notes.append(f"{ref}: {len(files)} file(s)")
            except Exception as exc:  # one bad dataset must not stop the rest
                result.notes.append(f"{ref}: failed ({type(exc).__name__}: {exc})")

        self._write_provenance(result, {"datasets": wanted,
                                       "license_note": "respect each Kaggle dataset's licence"})
        return result

    # -------------------------------------------------------------- openlibrary
    @staticmethod
    def _http_json(url: str, timeout: int = 45, retries: int = 3) -> Dict[str, Any]:
        last: Optional[Exception] = None
        for attempt in range(retries):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=timeout) as handle:
                    return json.load(handle)
            except Exception as exc:
                last = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"request failed: {url} ({last})")

    def fetch_openlibrary(self, subjects: Optional[Iterable[str]] = None, pages: int = 4,
                          limit: int = 100, delay: float = 0.4) -> IntakeResult:
        """Pull published children's titles from the public Open Library catalogue."""
        subjects = list(subjects or DEFAULT_SUBJECTS)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

        rows: List[Dict[str, Any]] = []
        seen: set = set()
        used: List[str] = []
        for subject in subjects:
            for page in range(max(1, pages)):
                url = SUBJECT_URL.format(subject=urllib.parse.quote(subject), limit=limit,
                                         offset=page * limit)
                try:
                    payload = self._http_json(url)
                except Exception as exc:
                    used.append(f"{subject} p{page + 1}: failed ({exc})")
                    break
                works = payload.get("works") or []
                if not works:
                    break
                for work in works:
                    title = str(work.get("title", "") or "").strip()
                    if not title or title.lower() in seen:
                        continue
                    seen.add(title.lower())
                    authors = "; ".join(
                        str(a.get("name", "")).strip() for a in (work.get("authors") or [])
                        if a.get("name")
                    )
                    subject_tags = [str(s).strip() for s in (work.get("subject") or [])][:8]
                    year = work.get("first_publish_year") or ""
                    editions = work.get("edition_count") or ""
                    rows.append({
                        "title": title,
                        "description": ", ".join(subject_tags) or f"children's book {year}".strip(),
                        "category": subject_tags[0] if subject_tags else subject.replace("_", " "),
                        "year": year,
                        "editions": editions,
                        "author": authors,
                        "subject_source": subject,
                    })
                used.append(f"{subject} p{page + 1}: {len(works)}")
                time.sleep(delay)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        target = self.dataset_dir / f"openlibrary_children_{stamp}.csv"
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["title", "description", "category",
                                                        "year", "editions", "author", "subject_source"])
            writer.writeheader()
            writer.writerows(rows)

        result = IntakeResult(provider="openlibrary", files=[str(target)], rows=len(rows),
                              signal="catalogue", notes=used[:24])
        self._write_provenance(result, {
            "url_template": SUBJECT_URL,
            "subjects": subjects,
            "signal_note": "Open Library is a catalogue (titles, subjects, editions) — not sales data. "
                           "Use Kaggle bestsellers for sales ranking.",
            "license_note": "Open Library data is published under CC0 for bibliographic records.",
        })
        return result

    # ---------------------------------------------------------------- dispatcher
    def sync(self, provider: str = "auto", refs: Optional[Iterable[str]] = None) -> IntakeResult:
        provider = (provider or "auto").lower()
        if provider == "kaggle":
            return self.sync_from_kaggle(refs)
        if provider == "openlibrary":
            return self.fetch_openlibrary()
        if provider == "auto":
            if self.kaggle_ready():
                return self.sync_from_kaggle(refs)
            result = self.fetch_openlibrary()
            result.notes.insert(0, "Kaggle not configured — used the public Open Library catalogue instead")
            return result
        raise ValueError(f"unknown provider: {provider} (kaggle | openlibrary | auto)")

    # ------------------------------------------------------------------- status
    def status(self) -> Dict[str, Any]:
        files = sorted(p.name for p in self.dataset_dir.glob("*") if p.is_file()
                       and p.suffix.lower() in {".csv", ".json", ".jsonl"})
        return {
            "dataset_dir": str(self.dataset_dir),
            "kaggle_configured": self.kaggle_ready(),
            "files": files,
            "provenance": self.provenance(),
        }
