#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def _norm(v: List[float]) -> List[float]:
    mag = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / mag for x in v]


class HashedEmbedder:
    def __init__(self, dims: int = 256) -> None:
        self.dims = dims

    def embed(self, text: str) -> List[float]:
        v = [0.0] * self.dims
        for tok in (text or "").lower().split():
            h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dims
            sign = -1.0 if (h >> 8) & 1 else 1.0
            v[idx] += sign
        return _norm(v)


@dataclass
class MemoryItem:
    id: str
    text: str
    source: str
    task_type: str
    ts: float
    meta: Dict[str, Any]


class QdrantMemoryStore:
    def __init__(self, collection: str = "bhairav_memory") -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        path = os.environ.get("BHAIRAV_QDRANT_PATH", "memory/qdrant_data")
        url = os.environ.get("BHAIRAV_QDRANT_URL", "").strip()
        self.client = QdrantClient(url=url) if url else QdrantClient(path=path)
        self.collection = collection
        self.embedder = HashedEmbedder()

        if not self.client.collection_exists(collection_name=self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.embedder.dims, distance=Distance.COSINE),
            )

    def upsert(self, item: MemoryItem) -> None:
        from qdrant_client.models import PointStruct

        vec = self.embedder.embed(item.text)
        point_id = int(hashlib.sha1(item.id.encode("utf-8")).hexdigest()[:15], 16)
        payload = {
            "external_id": item.id,
            "text": item.text,
            "source": item.source,
            "task_type": item.task_type,
            "ts": item.ts,
            **item.meta,
        }
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=point_id, vector=vec, payload=payload)],
        )

    def search(self, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
        vec = self.embedder.embed(query)
        points: List[Any]
        if hasattr(self.client, "query_points"):
            result = self.client.query_points(collection_name=self.collection, query=vec, limit=top_k)
            points = list(getattr(result, "points", []) or [])
        else:
            points = list(self.client.search(collection_name=self.collection, query_vector=vec, limit=top_k))
        return [{"id": str(r.id), "score": float(r.score), **(r.payload or {})} for r in points]


class PgVectorMemoryStore:
    def __init__(self) -> None:
        import psycopg

        dsn = os.environ.get("BHAIRAV_PG_DSN", "postgresql://localhost/postgres")
        self.conn = psycopg.connect(dsn)
        self.embedder = HashedEmbedder()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bhairav_memory (
                    id TEXT PRIMARY KEY,
                    embedding VECTOR(256),
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    ts DOUBLE PRECISION NOT NULL,
                    meta JSONB NOT NULL DEFAULT '{}'::jsonb
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS bhairav_memory_embedding_idx ON bhairav_memory USING ivfflat (embedding vector_cosine_ops)"
            )
        self.conn.commit()

    def upsert(self, item: MemoryItem) -> None:
        emb = self.embedder.embed(item.text)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bhairav_memory (id, embedding, text, source, task_type, ts, meta)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET embedding = EXCLUDED.embedding,
                    text = EXCLUDED.text,
                    source = EXCLUDED.source,
                    task_type = EXCLUDED.task_type,
                    ts = EXCLUDED.ts,
                    meta = EXCLUDED.meta
                """,
                (item.id, emb, item.text, item.source, item.task_type, item.ts, json.dumps(item.meta)),
            )
        self.conn.commit()

    def search(self, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
        emb = self.embedder.embed(query)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, text, source, task_type, ts, meta, 1 - (embedding <=> %s::vector) AS score
                FROM bhairav_memory
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (emb, emb, top_k),
            )
            rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for rid, text, source, task_type, ts, meta, score in rows:
            d = {"id": rid, "text": text, "source": source, "task_type": task_type, "ts": ts, "score": float(score)}
            d.update(meta or {})
            out.append(d)
        return out


def get_store() -> Any:
    backend = os.environ.get("BHAIRAV_VECTOR_BACKEND", "qdrant").strip().lower()
    if backend == "pgvector":
        return PgVectorMemoryStore()
    return QdrantMemoryStore()


if __name__ == "__main__":
    store = get_store()
    item = MemoryItem(
        id=f"smoke-{int(time.time())}",
        text="MSV clarification blocked run due to low confidence and conflict.",
        source="smoke-test",
        task_type="ops",
        ts=time.time(),
        meta={"fingerprint": "smoke-msv"},
    )
    store.upsert(item)
    print(store.search("clarification and confidence", top_k=3))
