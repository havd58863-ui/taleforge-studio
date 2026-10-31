"""End-to-end smoke test against the Flask test client (no server needed)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.config import TestingConfig  # noqa: E402

app = create_app(TestingConfig)
client = app.test_client()

CHECKS = [
    ("GET", "/", 200),
    ("GET", "/catalog", 200),
    ("GET", "/dashboard", 200),
    ("GET", "/story-demo", 200),
    ("GET", "/api/health", 200),
    ("GET", "/api/ideas", 200),
    ("GET", "/api/stories", 200),
    ("GET", "/api/summary", 200),
    ("GET", "/api/products", 200),
    ("GET", "/api/languages", 200),
    ("GET", "/admin/overview", 200),
    ("GET", "/api/search?q=forest", 200),
    ("GET", "/api/layout?trim_size=US_6_X_9", 200),
    ("GET", "/api/layout/trim-sizes", 200),
    ("GET", "/api/kaggle/status", 200),
    ("GET", "/api/nope", 404),
]

failures = 0
for method, path, expected in CHECKS:
    response = client.open(path, method=method)
    ok = response.status_code == expected
    print(f"{'PASS' if ok else 'FAIL'}  {method} {path} -> {response.status_code}")
    failures += 0 if ok else 1

posts = [
    ("/api/prompt", {"title": "Lantern Bloom", "summary": "Luna watches the forest lanterns bloom at sunrise."}),
    ("/api/metadata", {"title": "Luna and the Lantern Forest", "language": "en"}),
    ("/api/channels/kdp", {"title": "Luna and the Lantern Forest", "page_count": 32, "price": 12.99}),
    ("/api/channels/etsy", {"title": "Luna and the Lantern Forest", "price": 8.99}),
    ("/api/story/multilingual", {"languages": ["en", "de", "es"]}),
    ("/api/quality/evaluate", {"character_consistency": 93}),
    ("/api/layout", {"trim_size": "US_8_X_10", "page_types": ["single", "spread", "full_bleed"]}),
    ("/api/layout/cover", {"page_count": 120, "trim_size": "US_6_X_9"}),
    ("/api/text/fit", {"text": "Luna found a lantern in the whispering forest.", "width_mm": 90}),
    ("/api/render/wrap-cover", {"title": "Smoke Wrap", "page_count": 120, "back_blurb": "A blurb."}),
    ("/api/render/cover", {"title": "Smoke Test Cover"}),
    ("/api/pipeline/demo", {}),
]

for path, body in posts:
    response = client.post(path, json=body)
    ok = response.status_code in (200, 201)
    print(f"{'PASS' if ok else 'FAIL'}  POST {path} -> {response.status_code}")
    if not ok:
        print("      ", response.get_data(as_text=True)[:300])
        failures += 1

print("\nSMOKE TEST:", "ALL PASSED" if failures == 0 else f"{failures} FAILURE(S)")
sys.exit(1 if failures else 0)
