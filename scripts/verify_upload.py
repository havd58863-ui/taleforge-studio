"""Prove that the repository is complete — locally or straight from GitHub.

    python scripts/verify_upload.py --path .                        # after git clone
    python scripts/verify_upload.py --path . --strict-books         # also require output/library
    GITHUB_TOKEN=ghp_... python scripts/verify_upload.py --remote havd58863-ui/taleforge-studio

Exit code 0 = complete, 1 = something is missing.

The expected shape is the source tree only (109 files): the five books in ``output/library``
are git-ignored by design, so they are reported separately instead of counting as missing.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Set

EXPECTED_CORE_TOTAL = 109

# Directories whose file count must match exactly.
EXPECTED_BY_DIR: Dict[str, int] = {
    "app": 55,
    "scripts": 15,
    "docs": 11,
    "assets": 7,
    "tests": 1,
    ".github": 1,
    "(root)": 19,
}

# Placeholder folders — reported, never used to fail the check (git keeps only their READMEs).
OPTIONAL_DIRS = ("output", "secure_data", "vector_store")

CRITICAL: List[str] = [
    ".env.example", ".gitignore", ".gitattributes", ".dockerignore",
    "Dockerfile", "docker-compose.yml", "Makefile", "LICENSE", "README.md", "SECURITY.md",
    "requirements.txt", "requirements-lite.txt", "requirements-dev.txt", "pytest.ini",
    "run_server.py", "wsgi.py", "api_app.py", "database.py", "README-private.md",
    ".github/workflows/ci.yml",
    "app/__init__.py", "app/config.py", "app/extensions.py", "app/models.py",
    "app/routes/api_routes.py", "app/content/library_texts.py",
    "app/services/story_director_service.py", "app/services/story_writer_service.py",
    "app/services/editorial_review_service.py", "app/services/market_research_service.py",
    "app/services/series_service.py", "app/services/language_policy.py",
    "app/services/image_prompt_compiler.py", "app/services/image_engine_service.py",
    "app/services/print_image_service.py", "app/services/bilingual_service.py",
    "app/services/llm_client.py", "app/services/render_service.py",
    "app/services/page_layout_service.py", "app/services/quality_service.py",
    "app/services/text_layout_service.py", "app/services/fonts.py",
    "app/services/book_structure_service.py", "app/services/line_art_service.py",
    "app/services/placeholder_art_service.py",
    "app/services/market_data_service.py", "app/services/niche_service.py",
    "scripts/market_brief.py", "docs/MARKET.md", "docs/examples/niche_brief.md",
    "scripts/produce_library.py", "scripts/write_book.py", "scripts/ideate.py",
    "scripts/generate_scenes.py", "scripts/print_prep.py", "scripts/produce_book.py",
    "scripts/preflight.py", "scripts/bench_writers.py", "scripts/smoke_test.py",
    "tests/test_app.py",
    "docs/MASTER_PLAN.md", "docs/TOOLCHAIN.md", "docs/N8N.md", "docs/UPLOAD_GUIDE.md",
    "docs/FIXES.md", "docs/QUALITY.md", "docs/STORY_PIPELINE.md", "docs/AUDIT.md",
    "assets/fonts/Andika-Regular.ttf", "assets/fonts/Andika-Bold.ttf",
    "assets/fonts/Amiri-Regular.ttf", "assets/fonts/Amiri-Bold.ttf",
    "assets/fonts/OFL-Andika.txt", "assets/fonts/OFL-Amiri.txt", "assets/fonts/README.txt",
]

FORBIDDEN = [".env", "instance/taleforge.db", "secure_data/datasets/books.csv"]


def _gitignored(name: str) -> bool:
    """Mirror .gitignore so a plain unzipped folder reports the same numbers as a clone."""
    if name == ".env" or name.endswith((".pyc", ".db", ".zip", ".log")):
        return True
    for prefix in ("output/", "secure_data/", "vector_store/"):
        if name.startswith(prefix) and not name.endswith("README.txt"):
            return True
    return False


def local_files(root: Path) -> Set[str]:
    try:
        result = subprocess.run(["git", "ls-files"], cwd=str(root), capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and result.stdout.strip():
            return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except Exception:
        pass
    skip = {"__pycache__", ".git", ".pytest_cache", ".venv", "node_modules", ".mypy_cache", "instance"}
    files: Set[str] = set()
    for path in root.rglob("*"):
        if any(part in skip for part in path.parts) or not path.is_file():
            continue
        name = str(path.relative_to(root)).replace("\\", "/")
        if _gitignored(name):
            continue
        files.add(name)
    return files


def remote_files(repo: str, token: str = "") -> Set[str]:
    headers = {"User-Agent": "taleforge-verify"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for branch in ("main", "master"):
        url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read())
            return {item["path"] for item in payload.get("tree", []) if item["type"] == "blob"}
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
    raise SystemExit(
        "GitHub returned 404 for this repository.\n"
        "Either it is private (add GITHUB_TOKEN and retry) or nothing was pushed yet."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify repository completeness")
    parser.add_argument("--path", default=".", help="local clone path")
    parser.add_argument("--remote", default="", help="owner/repo — check GitHub instead of disk")
    parser.add_argument("--strict-books", action="store_true", help="require output/library too")
    args = parser.parse_args()

    if args.remote:
        files = remote_files(args.remote, os.getenv("GITHUB_TOKEN", "").strip())
        source = f"github:{args.remote}"
    else:
        root = Path(args.path).resolve()
        if not root.exists():
            print(f"path not found: {root}")
            return 1
        files = local_files(root)
        source = str(root)

    print(f"source          : {source}")
    core = sum(1 for name in files if (name.split("/")[0] if "/" in name else "(root)") in EXPECTED_BY_DIR)
    print(f"files found     : {len(files)} total | {core} source files (expected {EXPECTED_CORE_TOTAL})\n")

    by_dir: Dict[str, int] = {}
    for name in files:
        parts = name.split("/")
        key = parts[0] if len(parts) > 1 else "(root)"
        by_dir[key] = by_dir.get(key, 0) + 1

    print(f"{'folder':14s} {'found':>6s} {'expected':>9s}  status")
    problems: List[str] = []
    for folder, expected in EXPECTED_BY_DIR.items():
        found = by_dir.get(folder, 0)
        ok = found == expected
        if not ok:
            problems.append(f"{folder}: {found}/{expected} files")
        print(f"{folder:14s} {found:6d} {expected:9d}  {'OK' if ok else 'DIFF'}")

    if core != EXPECTED_CORE_TOTAL:
        problems.append(f"source files: {core}/{EXPECTED_CORE_TOTAL}")

    optional = {folder: by_dir.get(folder, 0) for folder in OPTIONAL_DIRS}
    print("\nplaceholders    : " + ", ".join(f"{folder}={count}" for folder, count in optional.items())
          + "  (informational)")

    missing = [name for name in CRITICAL if name not in files]
    print(f"\ncritical files  : {len(CRITICAL) - len(missing)}/{len(CRITICAL)} present")
    for name in missing:
        print(f"  MISSING  {name}")
        problems.append(f"missing {name}")

    leaked = [
        name for name in files
        if name in FORBIDDEN or (name.startswith("secure_data/") and not name.endswith("README.txt"))
    ]
    if leaked:
        print("\nSECURITY: these must never be committed:")
        for name in leaked[:10]:
            print(f"  LEAK  {name}")
        problems.append("secret/private files committed")

    books = [name for name in files if name.startswith("output/library/") and name.endswith((".pdf", ".epub"))]
    print(f"library books   : {len(books)} in the repository "
          f"({'included' if books else 'not included — git-ignored by design'})")
    if args.strict_books and not books:
        problems.append("output/library missing (--strict-books)")

    print("\nverdict         :", "COMPLETE" if not problems else "INCOMPLETE")
    for problem in problems:
        print("  -", problem)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
