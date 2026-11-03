"""Hybrid retrieval: tag-map lookup from the observation, then vector search, merged and capped."""

from functools import lru_cache

from foulcheck.config import laws_config
from foulcheck.laws.embed import Embedder, FastEmbedEmbedder
from foulcheck.laws.models import Chunk
from foulcheck.laws.store import LawStore
from foulcheck.laws.tags import CONTACT_SEVERITY, DEFINITIONS, TAG_PRIORITY, observation_tags
from foulcheck.video.schema import Observation

MAX_CHUNKS = 10
VECTOR_K = 8
# v1 judges under Law 12, with its free kick and penalty restarts, plus referee guidance on it
VECTOR_LAWS = {"12", "13", "14", "PL", "UEFA"}
MIN_VECTOR_SLOTS = 2  # keep room for chunks the tag map did not anticipate
# Tags whose best chunks are always included when the observation raises them (tag -> how many):
# the base terms, the passage that decides a penalty, the guidance on which point of contact
# makes a tackle reckless or serious foul play, and the serious-foul-play passages a studs-up
# lunge must be judged against.
MANDATORY_TAGS = {DEFINITIONS: 1, "penalty_kick": 1, CONTACT_SEVERITY: 1, "serious_foul_play": 4}


class Retriever:
    def __init__(self, store: LawStore, embedder: Embedder):
        self.store = store
        self.embedder = embedder
        self.chunks = store.all_chunks()

    def rule_lookup(self, tags: list[str]) -> list[Chunk]:
        """Chunks tagged with any observation tag, best matches first."""
        wanted = set(tags)

        def rank(c: Chunk):
            hits = wanted.intersection(c.tags)
            first = min(TAG_PRIORITY.index(t) for t in hits)
            return (DEFINITIONS not in hits, -len(hits), first)

        return sorted((c for c in self.chunks if wanted.intersection(c.tags)), key=rank)

    def vector_lookup(self, text: str, k: int = VECTOR_K) -> list[Chunk]:
        if not text:
            return []
        hits = self.store.search(self.embedder.embed_query(text), k * 5)
        return [c for c, _ in hits if c.law in VECTOR_LAWS][:k]

    def retrieve(self, obs: Observation, context: str | None = None,
                 limit: int = MAX_CHUNKS) -> list[Chunk]:
        tags = observation_tags(obs)
        rules = self.rule_lookup(tags)
        query = ". ".join(x for x in (obs.describe(), context) if x)
        vectors = self.vector_lookup(query)

        picked: list[Chunk] = []

        def add(c: Chunk) -> None:
            if len(picked) < limit and c.id not in {p.id for p in picked}:
                picked.append(c)

        for tag, count in MANDATORY_TAGS.items():
            if tag in tags:
                for c in [c for c in rules if tag in c.tags][:count]:
                    add(c)
        for c in rules[: limit - MIN_VECTOR_SLOTS]:
            add(c)
        for c in vectors:
            add(c)
        for c in rules:
            add(c)
        return picked


@lru_cache(maxsize=1)
def default_retriever() -> Retriever:
    cfg = laws_config()
    if not cfg.db_path.exists():
        raise FileNotFoundError(f"No Laws store at {cfg.db_path}. Run: python -m foulcheck.laws.build")
    store = LawStore(cfg.db_path)
    return Retriever(store, FastEmbedEmbedder(store.meta("embedder")))


def retrieve(observation: Observation, context: str | None = None) -> list[Chunk]:
    return default_retriever().retrieve(observation, context)
