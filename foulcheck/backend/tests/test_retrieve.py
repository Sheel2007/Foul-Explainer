import pytest

from foulcheck.laws.embed import HashEmbedder
from foulcheck.laws.retrieve import MAX_CHUNKS, Retriever, default_retriever
from foulcheck.laws.store import LawStore
from foulcheck.laws.tags import tag_chunks
from foulcheck.video.schema import ChallengeDetail, Observation
from tests.conftest import requires_store

STUDS_TACKLE = Observation(
    challenge_type="sliding tackle",
    contact={"made": True, "by": "A", "on": "B", "body_part_used": "studs/sole", "body_part_hit": "ankle"},
    ball_played_first=False,
    speed_and_force="high",
    location="outside penalty area",
)


@pytest.fixture
def retriever(tmp_path, synthetic_chunks):
    embedder = HashEmbedder()
    store = LawStore.build(tmp_path / "laws.sqlite", tag_chunks(synthetic_chunks), embedder)
    return Retriever(store, embedder)


def test_store_roundtrip(retriever, synthetic_chunks):
    assert [c.id for c in retriever.chunks] == [c.id for c in synthetic_chunks]
    assert retriever.store.meta("embedder") == "hash-256"


def test_vector_search_finds_lexical_match(retriever):
    hits = retriever.store.search(retriever.embedder.embed_query("serious foul play tackle"), k=3)
    assert hits[0][0].id == "L12-4-sfp-p1"


def test_definitions_always_first_and_capped(retriever):
    for obs in (STUDS_TACKLE, Observation(), Observation(handball={"touched": True})):
        got = retriever.retrieve(obs)
        assert got[0].id == "L12-1-p3"
        assert len(got) <= MAX_CHUNKS
        assert len({c.id for c in got}) == len(got)


def test_vector_hits_outside_v1_laws_are_dropped(retriever):
    got = retriever.retrieve(Observation(), context="field surface must be green")
    assert "L1-1-p1" not in [c.id for c in got]


@pytest.mark.data
@requires_store
def test_phase1_done_when_studs_tackle_returns_reckless_and_excessive_force():
    """Phase 1 check: sliding tackle, studs on ankle, ball not played."""
    chunks = default_retriever().retrieve(STUDS_TACKLE)
    texts = " ".join(c.text for c in chunks)
    assert "Reckless is when" in texts
    assert "Using excessive force is when" in texts
    assert any(c.subtitle == "Serious foul play" for c in chunks)
    assert all(c.law in {"12", "13", "14"} or c.kind == "guidance" for c in chunks)


def test_penalty_passage_always_retrieved_inside_the_box(retriever):
    obs = STUDS_TACKLE.model_copy(update={"location": "inside penalty area",
                                          "attack_context": "attacker running towards goal"})
    got = [c.id for c in retriever.retrieve(obs)]
    assert got[:2] == ["L12-1-p3", "L14-0-p1"]


@pytest.mark.data
@requires_store
def test_real_store_penalty_award_passage_for_box_trip():
    obs = Observation(challenge_type="trip", contact={"made": True, "body_part_used": "leg", "body_part_hit": "shin"},
                      ball_played_first=False, speed_and_force="medium", location="inside penalty area",
                      attack_context="attacker dribbling into the penalty area")
    texts = [c.text for c in default_retriever().retrieve(obs)]
    assert any("penalty kick is awarded if" in t for t in texts)


def test_serious_foul_play_passages_guaranteed_for_studs_up_lunge(retriever):
    obs = STUDS_TACKLE.model_copy(update={"challenge": ChallengeDetail(studs_showing=True, lunge=True, leg_straight=True)})
    got = [c.id for c in retriever.retrieve(obs)]
    assert "L12-4-sfp-p1" in got[:3]


@pytest.mark.data
@requires_store
def test_real_store_studs_up_lunge_gets_both_serious_foul_play_passages():
    obs = STUDS_TACKLE.model_copy(update={"challenge": ChallengeDetail(studs_showing=True, lunge=True, leg_straight=True)})
    subs = [c.subtitle for c in default_retriever().retrieve(obs)]
    assert subs.count("Serious foul play") == 2
