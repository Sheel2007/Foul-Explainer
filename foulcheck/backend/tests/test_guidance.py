import pytest

from foulcheck.decision.guard import build_citations
from foulcheck.decision.schema import CitationDraft
from foulcheck.laws.guidance import SOURCES, parse_source
from foulcheck.laws.retrieve import Retriever
from foulcheck.laws.embed import HashEmbedder
from foulcheck.laws.store import LawStore
from foulcheck.laws.tags import CONTACT_SEVERITY, observation_tags, tag_chunks
from foulcheck.video.schema import Observation
from tests.test_decision import draft as make_draft

PL_SFP = next(s for s in SOURCES if s.id == "PL-serious-foul-play")
UEFA_SFP = next(s for s in SOURCES if s.id == "UEFA-serious-foul-play")

# Shaped like the saved page text; the wording is made up.
PL_PAGE = """\
Matches
Serious foul play
09 Sep 2024

Made-up opening sentence about tackles that endanger an opponent's safety.

Considerations

- Speed of the made-up challenge
- Force of the made-up challenge and how
much control the player had

Contact

- Made-up contact on the foot is a caution
- Made-up full forceful contact on the ankle or above is a sending-off

Contents:
VAR
"""

UEFA_PAGE = """\
Red cards
Overview
Goal-scoring opportunity
Serious foul play
Violent conduct
Second yellow

Made-up summary of challenges that endanger the safety of an opponent.

What referees consider when making a decision
Was the made-up challenge fast and forceful?
0 seconds of 0 secondsVolume 0%
✅ When VAR should recommend a red card

A made-up challenge with the studs directed at the leg of an opponent.
Video 1 – Made-up caption for a clip of a challenge
Related topics
Our competitions
"""


def test_pl_page_splits_into_headed_sections():
    chunks = parse_source(PL_SFP, PL_PAGE, "test")
    assert [c.subtitle for c in chunks] == ["", "Considerations", "Contact"]
    assert all(c.kind == "guidance" and c.law == "PL" and c.url == PL_SFP.url for c in chunks)
    # wrapped bullet rejoined, navigation after "Contents" dropped
    assert "how much control the player had" in chunks[1].text
    assert "ankle or above" in chunks[2].text and "VAR" not in chunks[2].text
    assert chunks[2].reference() == "Premier League referee guidance · Serious foul play – Contact"


def test_uefa_page_drops_navigation_and_player_text():
    chunks = parse_source(UEFA_SFP, UEFA_PAGE, "test")
    subtitles = [c.subtitle for c in chunks]
    assert subtitles == ["", "What referees consider when making a decision", "When VAR should recommend a red card"]
    text = " ".join(c.text for c in chunks)
    assert "seconds" not in text and "Our competitions" not in text and "Goal-scoring" not in text
    assert "Video 1" in chunks[-1].text  # captions stay as body text, not headings


def _guidance():
    return parse_source(PL_SFP, PL_PAGE, "test") + parse_source(UEFA_SFP, UEFA_PAGE, "test")


def test_guidance_selectors_are_optional_until_a_publisher_is_fetched(synthetic_chunks):
    tag_chunks(synthetic_chunks)  # no guidance at all: fine
    with pytest.raises(ValueError, match="PL"):
        tag_chunks(synthetic_chunks + parse_source(PL_SFP, PL_PAGE.replace("Contact\n", "Impact\n"), "test"))


def test_any_contact_retrieves_point_of_contact_guidance(tmp_path, synthetic_chunks):
    chunks = tag_chunks(synthetic_chunks + _guidance())
    contact = next(c for c in chunks if c.id == "PL-serious-foul-play-3")
    assert CONTACT_SEVERITY in contact.tags and "serious_foul_play" in contact.tags

    embedder = HashEmbedder()
    retriever = Retriever(LawStore.build(tmp_path / "laws.sqlite", chunks, embedder), embedder)
    obs = Observation(challenge_type="standing tackle", contact={"made": True, "by": "A", "on": "B"})
    assert CONTACT_SEVERITY in observation_tags(obs)
    assert "PL-serious-foul-play-3" in [c.id for c in retriever.retrieve(obs)]


def test_guidance_citation_links_to_its_page(synthetic_chunks):
    chunk = next(c for c in _guidance() if c.subtitle == "Contact")
    draft = make_draft(citations=[CitationDraft(chunk_id=chunk.id, why="Point of contact.",
                                                quote="full forceful contact on the ankle or above")])
    [cit] = build_citations(draft, [chunk])
    assert cit.kind == "guidance" and cit.section == "PL"
    assert cit.source_url == PL_SFP.url
    assert cit.quote == "full forceful contact on the ankle or above"
