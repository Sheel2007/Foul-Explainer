"""Build the rulebook knowledge base: download -> parse -> tag -> embed -> store.

Usage: uv run python -m foulcheck.laws.build
"""

from foulcheck.config import laws_config
from foulcheck.laws.download import download
from foulcheck.laws.embed import FastEmbedEmbedder
from foulcheck.laws.guidance import parse_guidance
from foulcheck.laws.parse import parse_laws
from foulcheck.laws.store import LawStore
from foulcheck.laws.tags import tag_chunks


def build() -> None:
    cfg = laws_config()
    download()
    guidance = parse_guidance(cfg.edition)
    chunks = tag_chunks(parse_laws(cfg.pdf_path, cfg.edition) + guidance)
    with cfg.chunks_path.open("w") as f:
        for c in chunks:
            f.write(c.model_dump_json() + "\n")
    print(f"Parsed {len(chunks)} chunks ({sum(1 for c in chunks if c.law == '12')} from Law 12, "
          f"{len(guidance)} referee guidance) -> {cfg.chunks_path}")
    embedder = FastEmbedEmbedder()
    LawStore.build(cfg.db_path, chunks, embedder)
    print(f"Embedded with {embedder.name} (dim {embedder.dim}) -> {cfg.db_path}")


if __name__ == "__main__":
    build()
