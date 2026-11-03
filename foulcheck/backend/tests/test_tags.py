import pytest

from foulcheck.laws.tags import DEFINITIONS, Sel, TAG_MAP, observation_tags, tag_chunks
from foulcheck.video.schema import Observation


def test_studs_tackle_signals_reckless_and_excessive_force():
    obs = Observation(challenge_type="sliding tackle", ball_played_first=False, speed_and_force="high",
                      contact={"made": True, "body_part_used": "studs/sole", "body_part_hit": "ankle"},
                      location="outside penalty area")
    tags = observation_tags(obs)
    assert tags[0] == DEFINITIONS
    assert {"direct_free_kick", "reckless", "excessive_force", "caution", "sending_off"} <= set(tags)
    assert "penalty_kick" not in tags


def test_handball_in_box_signals_penalty():
    obs = Observation(handball={"touched": True, "arm_position": "above shoulder"},
                      location="inside penalty area")
    tags = observation_tags(obs)
    assert {"handball", "penalty_kick"} <= set(tags)
    assert "excessive_force" not in tags


def test_no_contact_challenge_signals_indirect_offences():
    tags = observation_tags(Observation(challenge_type="high foot near head", contact={"made": False}))
    assert {"dangerous_play", "impeding"} <= set(tags)
    assert "direct_free_kick" not in tags


def test_unknown_location_pulls_both_restarts():
    tags = observation_tags(Observation(contact={"made": True}, challenge_type="trip"))
    assert {"penalty_kick", "free_kick"} <= set(tags)


def test_attack_toward_goal_signals_dogso_and_spa():
    tags = observation_tags(Observation(contact={"made": True}, attack_context="attacker through on goal, last defender"))
    assert {"dogso", "spa"} <= set(tags)


def test_tag_chunks_covers_every_tag(synthetic_chunks):
    tagged = tag_chunks(synthetic_chunks)
    all_tags = {t for c in tagged for t in c.tags}
    assert all_tags == set(TAG_MAP)
    field = next(c for c in tagged if c.id == "L1-1-p1")
    assert field.tags == []


def test_tag_chunks_fails_when_selector_misses(synthetic_chunks):
    without_defs = [c for c in synthetic_chunks if "reckless is when" not in c.text]
    with pytest.raises(ValueError, match="foul_definitions"):
        tag_chunks(without_defs)


def test_selector_subtitle_rules(synthetic_chunks):
    hb = next(c for c in synthetic_chunks if c.subtitle == "Handling the ball")
    assert Sel("12", "12.1", "Handling").matches(hb)
    assert not Sel("12", "12.1", "").matches(hb)
    assert not Sel("13", "12.1").matches(hb)


def test_studs_up_lunge_signals_serious_foul_play_even_when_body_part_is_vague():
    # clip 2's case: the video model wrote "foot", but the explicit fields say studs up, straight leg, lunge
    obs = Observation(challenge_type="sliding tackle", ball_played_first=True, speed_and_force="high",
                      contact={"made": True, "body_part_used": "foot", "body_part_hit": "ankle"},
                      challenge={"studs_showing": True, "leg_straight": True, "lunge": True, "follow_through": True},
                      location="outside penalty area")
    tags = observation_tags(obs)
    assert {"serious_foul_play", "excessive_force", "sending_off"} <= set(tags)
    assert "studs showing" in obs.describe() and "lunging" in obs.describe()


def test_ordinary_slide_does_not_raise_serious_foul_play():
    # clip 1's case: a straight-leg lunge seen from far away, studs unknown
    for force in ("medium", "high"):
        obs = Observation(challenge_type="sliding tackle", speed_and_force=force, contact={"made": True},
                          challenge={"studs_showing": None, "leg_straight": True, "lunge": True, "follow_through": True})
        tags = observation_tags(obs)
        assert "serious_foul_play" not in tags and "reckless" in tags
