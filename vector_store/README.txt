FAISS / numpy vector storage directory. Keep this internal only.

Files created at runtime:
  faiss.index     FAISS flat L2 index (when faiss + sentence-transformers are installed)
  faiss.npy       numpy fallback index (hashed embeddings) when ML deps are absent
  metadata.json   document metadata aligned with index rows
