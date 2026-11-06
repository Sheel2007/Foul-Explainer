import threading

import pytest

from foulcheck import config
from foulcheck.decision import confidence, guard, prompts
from foulcheck.decision.engine import DecisionEngine
from foulcheck.decision.schema import CitationDraft, RulingDraft
from foulcheck.laws.embed import HashEmbedder
from foulcheck.laws.retrieve import Retriever
from foulcheck.laws.store import LawStore
from foulcheck.laws.tags import tag_chunks
from foulcheck.pipeline import analyze_clip
from foulcheck.video.schema import ChallengeDetail, LocateResult, Observation, VideoAnalysis, View
from tests.conftest import make_chunk

CHUNKS = [
    make_chunk("L12-1-p3", "12", "12.1", "• Reckless is when a player acts with disregard to the danger to an opponent and must be cautioned"),
    make_chunk("L12-4-p4", "12", "12.4", "The yellow card communicates a caution and the red card communicates a sending-off."),
    make_chunk("L14-0-p1", "14", "", "A penalty kick is awarded if a player commits a direct free kick offence inside their penalty area."),
    make_chunk("L14-1-p8", "14", "14.1", "The ball is in play when it is kicked and clearly moves."),
]
CHUNKS[2].tags = ["penalty_kick"]
OBS = Observation(contact_time="00:03.8", contact={"made": True}, challenge_type="sliding tackle",
                  location="outside penalty area", view_quality="clear, slow-motion replay", summary="A slides at B.")


def draft(**kw) -> RulingDraft:
    base = dict(verdict="foul", offence_type="reckless challenge", restart="direct_free_kick", card="yellow",
                confidence=0.8, explanation="A slid in late and caught B's ankle.",
                citations=[CitationDraft(chunk_id="L12-1-p3", why="defines reckless",
                                         quote="Reckless is when a player acts with disregard"),
                           CitationDraft(chunk_id="L12-4-p4", why="yellow card means a caution")],
                gray_areas=[], key_moment="00:03.8")
    base.update(kw)
    return RulingDraft(**base)


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")


# --- prompts -----------------------------------------------------------------

def test_prompt_has_no_law_text_of_its_own():
    for phrase in ("Reckless is when", "disregard to the danger", "communicates a caution"):
        assert phrase not in prompts.SYSTEM
    p = prompts.user_prompt(OBS, CHUNKS, "it was the last man")
    assert "[L12-1-p3] Law 12.1" in p and "it was the last man" in p
    assert "(none)" in prompts.user_prompt(OBS, CHUNKS, "  ")


# --- citation guard ----------------------------------------------------------

def test_guard_accepts_verbatim_quote_with_whitespace_and_case_noise():
    d = draft(citations=[CitationDraft(chunk_id="L12-1-p3", why="w", quote="reckless is when a  player acts with disregard."),
                         CitationDraft(chunk_id="L12-4-p4", why="w")])
    assert guard.check(d, CHUNKS) == []


def test_guard_flags_unknown_id_paraphrased_quote_and_missing_citations():
    d = draft(citations=[CitationDraft(chunk_id="L99-1-p1", why="w"),
                         CitationDraft(chunk_id="L12-1-p3", why="w", quote="Reckless means dangerous play")])
    errors = guard.check(d, CHUNKS)
    assert len(errors) == 3 and "L99-1-p1" in errors[0] and "word for word" in errors[1]
    assert "yellow card" in errors[2] and "L12-4-p4" in errors[2]
    assert guard.check(draft(citations=[]), CHUNKS)
    assert guard.check(draft(verdict="cannot_determine", restart="unknown", card="none", citations=[]), CHUNKS) == []


def test_guard_checks_quotes_inside_explanation():
    ok = draft(explanation='The Laws say "The yellow card communicates a caution" here.')
    bad = draft(explanation='The Laws say "a reckless tackle is always a booking" here.')
    assert guard.check(ok, CHUNKS) == []
    assert "Explanation quotes" in guard.check(bad, CHUNKS)[0]


def test_enforce_keeps_section_refs_only():
    d = draft(citations=[CitationDraft(chunk_id="L99", why="w"),
                         CitationDraft(chunk_id="L12-1-p3", why="w", quote="made up words here")],
              explanation='It is "a reckless tackle is always a booking" by law.')
    fixed, notes = guard.enforce(d, CHUNKS)
    assert [c.chunk_id for c in fixed.citations] == ["L12-1-p3", "L12-4-p4"] and fixed.citations[0].quote is None
    assert '"' not in fixed.explanation and len(notes) == 4 and "yellow card" in notes[-1]
    assert guard.check(fixed, CHUNKS) == []


def test_guard_requires_restart_and_card_grounding():
    pen = draft(restart="penalty_kick", card="none")
    errors = guard.check(pen, CHUNKS)
    assert len(errors) == 1 and "penalty kick" in errors[0] and "L14-0-p1" in errors[0]
    fixed, notes = guard.enforce(pen, CHUNKS)
    assert fixed.citations[-1].chunk_id == "L14-0-p1" and guard.check(fixed, CHUNKS) == []
    # nothing to cite -> no requirement
    assert guard.check(draft(restart="indirect_free_kick", card="none"), CHUNKS) == []
    assert guard.check(draft(verdict="cannot_determine", restart="unknown", card="red", citations=[]), CHUNKS) == []


def test_guard_allows_long_verbatim_quotes():
    long_chunk = make_chunk("L12-9-p1", "12", "12.1", " ".join(f"w{i}" for i in range(60)))
    d = draft(citations=[CitationDraft(chunk_id="L12-9-p1", why="w", quote=long_chunk.text),
                         CitationDraft(chunk_id="L12-4-p4", why="w")])
    assert guard.check(d, CHUNKS + [long_chunk]) == []


def test_build_citations_enriches_and_links_pdf_page():
    d = draft(citations=[CitationDraft(chunk_id="L12-1-p3", why="w", quote="Reckless is when"),
                         CitationDraft(chunk_id="L12-1-p3", why="dup")])
    (c,) = guard.build_citations(d, CHUNKS)
    assert c.reference.startswith("Law 12.1") and c.quote == "Reckless is when"
    assert c.source_url.endswith("#page=1")  # synthetic chunks sit on book page 1


# --- confidence --------------------------------------------------------------

def test_confidence_levels_and_penalties():
    assert confidence.assess(draft(), OBS).level == "High"
    unsure = OBS.model_copy(update={"uncertain_fields": ["ball_played_first", "contact.body_part_hit", "players[0].number"]})
    c = confidence.assess(draft(), unsure)
    assert c.score == pytest.approx(0.64) and c.level == "Medium"
    assert "ball_played_first" in c.adjustments[0] and "players" not in c.adjustments[0]


def test_confidence_disagreement_view_and_location_checks():
    poor = OBS.model_copy(update={"view_quality": "contact partly blocked"})
    c = confidence.assess(draft(restart="penalty_kick"), poor, second=draft(card="red"))
    assert c.score == pytest.approx(0.8 - 0.1 - 0.1 - 0.2) and c.level == "Low"
    assert any("second independent run" in a and "card (yellow vs red)" in a for a in c.adjustments)


def test_red_card_resting_on_a_video_reading_loses_confidence():
    studs = OBS.model_copy(update={"challenge": ChallengeDetail(studs_showing=True), "speed_and_force": "high"})
    c = confidence.assess(draft(card="red", confidence=0.95), studs, second=draft(card="red"))
    assert c.score == pytest.approx(0.70) and c.level == "Medium"
    assert any("studs showing and high force" in a for a in c.adjustments)


def test_other_calls_are_not_marked_as_hinging_on_a_reading():
    studs = OBS.model_copy(update={"challenge": ChallengeDetail(studs_showing=True)})
    assert confidence.red_card_hinges("yellow", studs) == []  # not a red card
    assert confidence.red_card_hinges("red", OBS.model_copy(update={"speed_and_force": "low"})) == []  # no such reading
    no_contact = Observation(contact={"made": False}, challenge=ChallengeDetail(studs_showing=True))
    assert confidence.red_card_hinges("red", no_contact) == []


def test_engine_names_the_reading_a_red_card_depends_on():
    studs = OBS.model_copy(update={"challenge": ChallengeDetail(studs_showing=True)})
    fake = FakeText({0: [draft(card="red").model_dump_json()]})
    ruling = DecisionEngine(fake, second_opinion=False).decide(studs, CHUNKS)
    assert any("depends on studs showing" in g for g in ruling.gray_areas)


def test_confidence_capped_for_cannot_determine():
    c = confidence.assess(draft(verdict="cannot_determine", restart="unknown", card="none", confidence=0.9), OBS)
    assert c.score <= 0.4 and c.level == "Low"


# --- engine ------------------------------------------------------------------

class FakeText:
    name = "fake"

    def __init__(self, by_sample):
        self.by_sample = {k: list(v) for k, v in by_sample.items()}
        self.prompts = []
        self.lock = threading.Lock()

    def generate(self, system, prompt, schema, sample=0):
        with self.lock:
            self.prompts.append((sample, prompt))
            return self.by_sample[sample].pop(0)


def test_engine_clean_run_with_agreeing_second_opinion():
    fake = FakeText({0: [draft().model_dump_json()], 1: [draft(confidence=0.7).model_dump_json()]})
    r = DecisionEngine(fake).decide(OBS, CHUNKS, None)
    assert (r.verdict, r.card, r.confidence.level) == ("foul", "yellow", "High")
    assert r.citations[0].quote == "Reckless is when a player acts with disregard"
    assert r.notes == [] and r.observation == OBS
    assert r.audit["guard_errors"] == 0 and r.audit["second_opinion"] == "agree" and r.audit["decision_s"] >= 0


def test_engine_reruns_once_then_falls_back_to_section_refs():
    bad = draft(citations=[CitationDraft(chunk_id="L12-1-p3", why="w", quote="invented rule text")])
    fake = FakeText({0: [bad.model_dump_json(), bad.model_dump_json()], 1: [draft().model_dump_json()]})
    r = DecisionEngine(fake).decide(OBS, CHUNKS, None)
    fix_prompts = [p for s, p in fake.prompts if s == 0][1]
    assert "rejected" in fix_prompts and "invented rule text" in fix_prompts
    assert r.citations[0].quote is None and r.citations[0].chunk_id == "L12-1-p3"
    assert any("reran once" in n for n in r.notes) and any("unverified quote" in n for n in r.notes)
    assert r.audit["reran"] and r.audit["enforced"] >= 1


def test_engine_disagreement_adds_gray_area():
    fake = FakeText({0: [draft().model_dump_json()], 1: [draft(card="red", offence_type="excessive force").model_dump_json()]})
    r = DecisionEngine(fake).decide(OBS, CHUNKS, None)
    assert r.confidence.score == pytest.approx(0.6)
    assert "second reading" in r.gray_areas[-1] and "red card" in r.gray_areas[-1]


def test_engine_survives_failed_second_opinion():
    fake = FakeText({0: [draft().model_dump_json()], 1: ["not json", "still not json"]})
    r = DecisionEngine(fake).decide(OBS, CHUNKS, None)
    assert r.verdict == "foul" and r.notes[0].startswith("Second opinion unavailable (AI service")


# --- pipeline ----------------------------------------------------------------

class FakeAnalyzer:
    def __init__(self, obs):
        self.obs = obs

    def analyze(self, path, use_cache=True, progress=None):
        for stage in ("locate", "inspect") if self.obs else ("locate",):
            progress and progress(stage)
        loc = LocateResult(incident_found=self.obs is not None, incident="A slides at B.",
                           views=[View(contact_time="00:03.8", kind="replay", camera="close", clarity="clear")] if self.obs else [])
        return VideoAnalysis(clip=str(path), sha256="x", duration_s=7, analyzer="fake", locate=loc,
                             window=(2.3, 5.3) if self.obs else None, observation=self.obs)


def test_analyze_clip_end_to_end(tmp_path, synthetic_chunks):
    store = LawStore.build(tmp_path / "s.sqlite", tag_chunks(synthetic_chunks), HashEmbedder())
    retriever = Retriever(store, HashEmbedder())
    good = draft(citations=[CitationDraft(chunk_id="L12-1-p3", why="defines reckless", quote="reckless is when"),
                            CitationDraft(chunk_id="L12-4-p1", why="yellow card")])
    fake = FakeText({0: [good.model_dump_json()], 1: [good.model_dump_json()]})
    r = analyze_clip("clip.mp4", "it was outside the box", analyzer=FakeAnalyzer(OBS),
                     engine=DecisionEngine(fake), retriever=retriever)
    assert r.verdict == "foul" and r.context_hint == "it was outside the box"
    assert r.edition == config.laws_config().edition and r.video.locate.incident_found
    prompt = fake.prompts[0][1]
    assert "[L12-1-p3]" in prompt and "it was outside the box" in prompt


def test_analyze_clip_no_incident_skips_decision():
    r = analyze_clip("clip.mp4", analyzer=FakeAnalyzer(None), engine=DecisionEngine(FakeText({})), retriever=object())
    assert r.verdict == "cannot_determine" and r.confidence.level == "Low" and r.citations == []


def test_guard_accepts_elided_quotes_in_order_only():
    chunk = make_chunk("L12-1-p1", "12", "12.1", "A direct free kick is awarded if a player commits any of the following "
                       "offences: • charges • jumps at • tackles or challenges • trips or attempts to trip")
    ok = ("A direct free kick is awarded if a player commits ... • tackles or challenges",
          "any of the following offences: • tackles or challenges",  # skipped list items, no ellipsis
          "following offences: • charges • trips or attempts to trip",
          "any of the following offences: […] trips or attempts to trip", "jumps at [...] tackles or challenges")
    for q in ok:
        assert guard._is_verbatim(q, [chunk]), q
    bad = ("tackles or challenges ... jumps at",  # out of order
           "A direct free kick ... tackles hard",  # a piece is not in the text
           "free ... tackles or challenges",  # one-word piece could match anywhere
           "• trips or attempts to trip • charges")  # bullets out of order
    for q in bad:
        assert not guard._is_verbatim(q, [chunk]), q


def test_highlight_uses_model_phrase_only_when_inside_quote():
    quote = "Reckless is when a player acts with disregard"
    ok = draft(citations=[CitationDraft(chunk_id="L12-1-p3", why="w", quote=quote, highlight="acts with disregard")])
    assert guard.build_citations(ok, CHUNKS)[0].highlight == "acts with disregard"
    # a highlight that isn't in the quote falls back to a term the ruling relies on (offence_type "reckless challenge")
    bad = draft(citations=[CitationDraft(chunk_id="L12-1-p3", why="w", quote=quote, highlight="made up words")])
    assert guard.build_citations(bad, CHUNKS)[0].highlight == "Reckless"
    none = draft(citations=[CitationDraft(chunk_id="L12-4-p4", why="w")])
    assert guard.build_citations(none, CHUNKS)[0].highlight is None


def test_chunk_ids_stripped_from_fan_facing_text():
    from foulcheck.decision.engine import strip_chunk_ids
    text = "A tripped B [L12-1-p1]. Careless (L12-1-p3, L12-4-cautions-unsporting-behaviour-p1), so no card."
    assert strip_chunk_ids(text) == "A tripped B. Careless, so no card."
    assert strip_chunk_ids("Law 12.1 [see text]") == "Law 12.1 [see text]"
