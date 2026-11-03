"""Slow integration test: real decision model on a fixed observation. Run with: uv run pytest -m slow"""

import os

import pytest

from foulcheck.decision.engine import DecisionEngine
from foulcheck.laws.retrieve import default_retriever
from foulcheck.video.schema import Observation
from tests.conftest import requires_store


@pytest.mark.slow
@requires_store
@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY")
def test_real_decision_on_studs_tackle():
    obs = Observation(
        contact_time="00:07.4", challenge_type="sliding tackle", ball_played_first=False, speed_and_force="high",
        contact={"made": True, "by": "A", "on": "B", "body_part_used": "studs/sole", "body_part_hit": "ankle"},
        location="outside penalty area", view_quality="clear", summary="At 00:07.4 A slides in studs-first on B's ankle.",
    )
    chunks = default_retriever().retrieve(obs)
    r = DecisionEngine().decide(obs, chunks)
    assert r.verdict == "foul" and r.restart == "direct_free_kick" and r.card in ("yellow", "red")
    assert r.citations and all(c.chunk_id in {ch.id for ch in chunks} for c in r.citations)
