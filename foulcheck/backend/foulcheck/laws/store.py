"""Local vector store: chunks and their embeddings in one SQLite file via sqlite-vec."""

import json
import sqlite3
from pathlib import Path

import sqlite_vec

from foulcheck.laws.embed import Embedder
from foulcheck.laws.models import Chunk


def _connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


class LawStore:
    def __init__(self, path: Path | str):
        self.path = path
        self.conn = _connect(path)

    @classmethod
    def build(cls, path: Path | str, chunks: list[Chunk], embedder: Embedder) -> "LawStore":
        if isinstance(path, Path) and path.exists():
            path.unlink()
        store = cls(path)
        db = store.conn
        db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        db.execute("CREATE TABLE chunks (rowid INTEGER PRIMARY KEY, id TEXT UNIQUE, data TEXT)")
        db.execute(f"CREATE VIRTUAL TABLE vec USING vec0(embedding float[{embedder.dim}] distance_metric=cosine)")
        vectors = embedder.embed_documents([_embed_text(c) for c in chunks])
        for i, (c, v) in enumerate(zip(chunks, vectors), start=1):
            db.execute("INSERT INTO chunks VALUES (?, ?, ?)", (i, c.id, c.model_dump_json()))
            db.execute("INSERT INTO vec(rowid, embedding) VALUES (?, ?)", (i, sqlite_vec.serialize_float32(v)))
        db.executemany("INSERT INTO meta VALUES (?, ?)", [
            ("embedder", embedder.name), ("dim", str(embedder.dim)),
            ("edition", chunks[0].edition if chunks else ""),
        ])
        db.commit()
        return store

    def meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def all_chunks(self) -> list[Chunk]:
        rows = self.conn.execute("SELECT data FROM chunks ORDER BY rowid").fetchall()
        return [Chunk.model_validate(json.loads(r[0])) for r in rows]

    def search(self, query_vec: list[float], k: int = 8) -> list[tuple[Chunk, float]]:
        rows = self.conn.execute(
            "SELECT c.data, v.distance FROM vec v JOIN chunks c ON c.rowid = v.rowid "
            "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (sqlite_vec.serialize_float32(query_vec), k),
        ).fetchall()
        return [(Chunk.model_validate(json.loads(d)), dist) for d, dist in rows]


def _embed_text(c: Chunk) -> str:
    heading = " – ".join(x for x in (c.law_title, c.title, c.subtitle) if x)
    return f"{heading}\n{c.text}"
