"""Vector search with graceful degradation.

Backends, best first:
  1. faiss + sentence-transformers  (semantic, 384-dim MiniLM)
  2. numpy brute-force hashing embedder (no ML deps, good enough for demo search)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover
    SentenceTransformer = None

EMBED_DIM = 384
_TOKEN_RE = re.compile(r"[a-z0-9\u0600-\u06FF]+", re.UNICODE)


class VectorService:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.index_path = Path(os.getenv("VECTOR_DB_PATH", "./vector_store/faiss.index"))
        self.metadata_path = Path(os.getenv("VECTOR_METADATA_PATH", "./vector_store/metadata.json"))
        self.numpy_path = self.index_path.with_suffix(".npy")
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)

        self._model = None
        self.backend = "faiss" if (faiss is not None and SentenceTransformer is not None) else "numpy"

    # ---------- embeddings ----------
    def _load_model(self):
        if self._model is None and SentenceTransformer is not None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _hash_embed(self, texts: List[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), EMBED_DIM), dtype="float32")
        for row, text in enumerate(texts):
            for token in _TOKEN_RE.findall(text.lower()):
                digest = hashlib.md5(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % EMBED_DIM
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                matrix[row, idx] += sign
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if self.backend == "faiss":
            model = self._load_model()
            if model is not None:
                return np.asarray(model.encode(texts, convert_to_numpy=True), dtype="float32")
        return self._hash_embed(texts)

    # ---------- storage ----------
    def ensure_storage(self) -> None:
        if self.backend == "faiss" and self.index_path.exists():
            return
        if self.backend == "faiss":
            index = faiss.IndexFlatL2(EMBED_DIM)
            faiss.write_index(index, str(self.index_path))
        elif not self.numpy_path.exists():
            np.save(self.numpy_path, np.zeros((0, EMBED_DIM), dtype="float32"))
        if not self.metadata_path.exists():
            self.metadata_path.write_text("[]", encoding="utf-8")

    def _read_metadata(self) -> List[Dict[str, Any]]:
        self.ensure_storage()
        try:
            return json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_metadata(self, metadata: List[Dict[str, Any]]) -> None:
        self.metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        if not documents:
            return 0
        self.ensure_storage()
        metadata = self._read_metadata()
        embeddings = self.embed_texts([str(doc.get("text", "")) for doc in documents])

        if self.backend == "faiss":
            index = faiss.read_index(str(self.index_path))
            index.add(embeddings)
            faiss.write_index(index, str(self.index_path))
        else:
            existing = np.load(self.numpy_path) if self.numpy_path.exists() else np.zeros((0, EMBED_DIM), dtype="float32")
            np.save(self.numpy_path, np.vstack([existing, embeddings]))

        for doc in documents:
            metadata.append(
                {
                    "id": doc.get("id"),
                    "title": doc.get("title", ""),
                    "text": doc.get("text", ""),
                    "doc_type": doc.get("doc_type", "story"),
                }
            )
        self._write_metadata(metadata)
        return len(documents)

    # ---------- search ----------
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        metadata = self._read_metadata()
        if not metadata:
            return []
        query_vec = self.embed_texts([query])[0]

        if self.backend == "faiss" and self.index_path.exists():
            index = faiss.read_index(str(self.index_path))
            if index.ntotal == 0:
                return []
            distances, indices = index.search(query_vec.reshape(1, -1), min(top_k, index.ntotal))
            pairs = list(zip(distances[0], indices[0]))
        else:
            if not self.numpy_path.exists():
                return []
            matrix = np.load(self.numpy_path)
            if matrix.size == 0:
                return []
            scores = matrix @ query_vec
            order = np.argsort(-scores)[: min(top_k, matrix.shape[0])]
            pairs = [(float(1.0 - scores[i]), int(i)) for i in order]

        results = []
        for dist, idx in pairs:
            if idx < 0 or idx >= len(metadata):
                continue
            results.append({**metadata[idx], "distance": round(float(dist), 6)})
        return results

    def stats(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "documents": len(self._read_metadata()),
            "embedding_model": self.model_name if self.backend == "faiss" else "hashing-fallback",
        }


def ensure_vector_storage() -> None:
    VectorService().ensure_storage()


def seed_story_documents() -> int:
    """Index demo stories so /api/search returns something useful on a fresh clone."""
    from app.models import Story

    docs = [
        {"id": s.id, "title": s.title, "doc_type": "story", "text": f"{s.title}. {s.premise or ''} {s.setting or ''}"}
        for s in Story.query.all()
    ]
    return VectorService().add_documents(docs)
