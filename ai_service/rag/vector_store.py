# ai-service/rag/vector_store.py
# Cần bổ sung: Chạy build_index() sau khi có dữ liệu sản phẩm thực tế
from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent.parent
INDEX_PATH = BASE_DIR / "product_index.faiss"
META_PATH = BASE_DIR / "product_index_meta.json"

model_embed = SentenceTransformer("all-MiniLM-L6-v2")


def build_index(products: list[dict]):
    """Offline: gọi 1 lần để build FAISS index"""
    texts = [f"{p['name']} {p['description']} {p['category']}" for p in products]
    embeddings = model_embed.encode(texts)
    index = faiss.IndexFlatL2(384)
    index.add(np.array(embeddings, dtype="float32"))
    faiss.write_index(index, str(INDEX_PATH))
    META_PATH.write_text(
        json.dumps(
            {
                "product_ids": [int(p.get("id", i)) for i, p in enumerate(products)],
                "count": len(products),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return index


def search(query: str, top_k: int = 5):
    index = faiss.read_index(str(INDEX_PATH))
    qvec = model_embed.encode([query])
    _, I = index.search(np.array(qvec, dtype="float32"), top_k)

    product_ids = None
    if META_PATH.exists():
        try:
            meta = json.loads(META_PATH.read_text(encoding="utf-8"))
            product_ids = meta.get("product_ids")
        except json.JSONDecodeError:
            product_ids = None

    result = []
    for idx in I[0].tolist():
        if idx < 0:
            continue
        if product_ids and 0 <= idx < len(product_ids):
            result.append(int(product_ids[idx]))
        else:
            result.append(int(idx))
    return result