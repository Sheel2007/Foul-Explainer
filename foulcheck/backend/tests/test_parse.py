import pytest

from foulcheck.config import laws_config
from foulcheck.laws.parse import _is_prose, normalize, parse_laws
from tests.conftest import requires_pdf


def test_normalize_whitespace_quotes_and_control_chars():
    assert normalize("player’s  \t arm\x07 ,") == "player's arm,"
    assert normalize("•directly") == "• directly"


def test_is_prose_drops_table_fragments():
    assert not _is_prose("penalty is retaken penalty is retaken")
    assert _is_prose("A goal may be scored directly from a penalty kick.")
    assert _is_prose("It is an offence if a player: • deliberately touches the ball")


@pytest.fixture(scope="module")
def chunks():
    cfg = laws_config()
    return parse_laws(cfg.pdf_path, cfg.edition)


@pytest.mark.data
@requires_pdf
def test_ids_unique_and_edition_pinned(chunks):
    assert len({c.id for c in chunks}) == len(chunks)
    assert {c.edition for c in chunks} == {laws_config().edition}


@pytest.mark.data
@requires_pdf
def test_law12_structure(chunks):
    law12 = [c for c in chunks if c.law == "12"]
    assert {c.section for c in law12} >= {"12.1", "12.2", "12.4", "12.5"}
    assert all(115 <= c.page <= 129 for c in law12)
    defs = [c for c in law12 if "Reckless is when" in c.text]
    assert len(defs) == 1 and defs[0].section == "12.1" and defs[0].page == 115
    assert any(c.subtitle == "Handling the ball" for c in law12)
    assert any(c.subtitle.startswith("Denying a goal") for c in law12)
