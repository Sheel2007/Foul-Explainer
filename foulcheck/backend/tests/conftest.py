import pytest

from foulcheck.config import laws_config
from foulcheck.laws.models import Chunk


def make_chunk(id: str, law: str, section: str, text: str, subtitle: str = "", title: str = "") -> Chunk:
    return Chunk(id=id, law=law, law_title="Fouls and Misconduct", section=section, title=title,
                 subtitle=subtitle, page=1, edition="test", text=text)


@pytest.fixture
def synthetic_chunks() -> list[Chunk]:
    """Minimal stand-ins for the Law 12 structure the tag map expects. Not real Law text."""
    return [
        make_chunk("L12-1-p1", "12", "12.1", "offences in a manner careless, reckless or using excessive force: trips"),
        make_chunk("L12-1-p2", "12", "12.1", "if an offence involves contact it is a direct free kick."),
        make_chunk("L12-1-p3", "12", "12.1", "careless is when ... reckless is when ... excessive force is when ..."),
        make_chunk("L12-1-p4", "12", "12.1", "list: a handball offence, holds an opponent"),
        make_chunk("L12-1-hb-p1", "12", "12.1", "handball arm boundary", subtitle="Handling the ball"),
        make_chunk("L12-2-p1", "12", "12.2", "plays in a dangerous manner, impedes the progress"),
        make_chunk("L12-2-dp-p1", "12", "12.2", "dangerous play meaning", subtitle="Playing in a dangerous manner"),
        make_chunk("L12-2-imp-p1", "12", "12.2", "impeding meaning", subtitle="Impeding the progress"),
        make_chunk("L12-4-p1", "12", "12.4", "the yellow card communicates a caution"),
        make_chunk("L12-4-sh-p1", "12", "12.4", "show card", subtitle="Delaying the restart of play to show a card"),
        make_chunk("L12-4-adv-p1", "12", "12.4", "advantage text", subtitle="Advantage"),
        make_chunk("L12-4-co-p1", "12", "12.4", "a player is cautioned if", subtitle="Cautionable offences"),
        make_chunk("L12-4-ub-p1", "12", "12.4", "unsporting behaviour list", subtitle="Cautions for unsporting behaviour"),
        make_chunk("L12-4-so-p1", "12", "12.4", "is sent off: obvious goal-scoring", subtitle="Sending-off offences"),
        make_chunk("L12-4-dg-p1", "12", "12.4", "dogso: holding, pulling, pushing", subtitle="Denying a goal or an obvious goal-scoring opportunity (DOGSO)"),
        make_chunk("L12-4-sfp-p1", "12", "12.4", "serious foul play tackle", subtitle="Serious foul play"),
        make_chunk("L12-4-vc-p1", "12", "12.4", "violent conduct", subtitle="Violent conduct"),
        make_chunk("L12-5-p1", "12", "12.5", "a physical offence restarts"),
        make_chunk("L13-1-p1", "13", "13.1", "free kicks are awarded to the opposing team"),
        make_chunk("L14-0-p1", "14", "", "a penalty kick is awarded if"),
        make_chunk("L1-1-p1", "1", "1.1", "the field surface must be green"),
    ]


requires_store = pytest.mark.skipif(not laws_config().db_path.exists(), reason="Laws store not built")
requires_pdf = pytest.mark.skipif(not laws_config().pdf_path.exists(), reason="Laws PDF not downloaded")
