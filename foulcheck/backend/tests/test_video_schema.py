import pytest
from pydantic import ValidationError

from foulcheck.video.base import check_neutral, verdict_words
from foulcheck.video.schema import LocateResult, Observation, View, fmt_ts, parse_ts


def test_timestamps_roundtrip():
    assert parse_ts("01:07.4") == pytest.approx(67.4)
    assert parse_ts("00:03") == 3
    assert fmt_ts(67.43) == "01:07.4"
    assert fmt_ts(59.97) == "01:00.0"
    with pytest.raises(ValueError):
        parse_ts("7.4s")


def test_observation_rejects_bad_timestamp_and_force():
    with pytest.raises(ValidationError):
        Observation(contact_time="seven seconds")
    with pytest.raises(ValidationError):
        Observation(speed_and_force="extreme")


def test_plan_example_observation_validates():
    obs = Observation.model_validate({
        "contact_time": "00:07.4",
        "players": [{"id": "A", "team": "red", "number": "4", "role": "defender"}],
        "contact": {"made": True, "by": "A", "on": "B", "body_part_used": "studs/sole", "body_part_hit": "ankle"},
        "ball_played_first": False, "challenge_type": "sliding tackle", "speed_and_force": "high",
        "handball": {"touched": False, "arm_position": None, "deliberate_movement": None},
        "location": "outside penalty area", "attack_context": "attacker running toward goal, one defender behind",
        "view_quality": "contact partly blocked by another player", "uncertain_fields": ["ball_played_first"],
    })
    assert obs.contact_seconds == pytest.approx(7.4)


def test_neutral_check_flags_ruling_words_only():
    ok = Observation(summary="At 00:03.8 A slides in inside the penalty area; the goalkeeper dives.",
                     location="inside penalty area")
    check_neutral(ok)
    bad = Observation(summary="A clear foul, reckless and worth a yellow card.")
    assert {w.lower() for w in verdict_words(bad)} == {"foul", "reckless", "yellow card"}
    with pytest.raises(ValueError, match="ruling words"):
        check_neutral(bad)


def test_chosen_view_falls_back_on_bad_index():
    v = View(contact_time="00:01.0", kind="live", camera="wide", clarity="clear")
    assert LocateResult(incident_found=True, views=[v], best_view=5).chosen_view() is v
    assert LocateResult(incident_found=False).chosen_view() is None
