"""Confidence: start from the model's own number, then apply simple, explainable penalties."""

import re

from foulcheck.decision.schema import Confidence, Level, RulingDraft
from foulcheck.video.schema import Observation, VideoAnalysis

# Facts a Law 12 decision usually turns on. Uncertainty here matters more than elsewhere.
KEY_FIELDS = ("contact", "ball_played_first", "speed_and_force", "handball", "location", "challenge_type")
POOR_VIEW = re.compile(r"\b(poor|blocked|obscured|unclear|partial(ly)?|hidden|blurr?y|far away|distant)\b", re.I)

PER_KEY_FIELD = 0.08
MAX_FIELD_PENALTY = 0.24
POOR_VIEW_PENALTY = 0.10
DISAGREEMENT_PENALTY = 0.20
CONTEXT_PENALTY = 0.05
LOCATION_MISMATCH_PENALTY = 0.10
HINGE_PENALTY = 0.25


def level(score: float) -> Level:
    return "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"


def red_card_hinges(card: str, obs: Observation | None) -> list[str]:
    """Video readings a red card rests on. Both decision runs read the same facts, so their agreement
    cannot catch a misread boot or force: these need their own doubt, even when no field was marked unsure."""
    if card != "red" or obs is None or not obs.contact.made:
        return []
    used = (obs.contact.body_part_used or "").lower()
    facts = []
    if obs.challenge.studs_showing or "stud" in used or "sole" in used:
        facts.append("studs showing")
    if obs.speed_and_force == "high":
        facts.append("high force")
    return facts


def hinge_note(facts: list[str]) -> str:
    return f"red card depends on {' and '.join(facts)}, read from the video alone"


def hinge_gray_area(facts: list[str]) -> str:
    return (f"This red card depends on {' and '.join(facts)}, read from the video alone. "
            "If that reading is wrong, the card would probably be lower.")


def assess(draft: RulingDraft, obs: Observation | None, video: VideoAnalysis | None = None,
           second: RulingDraft | None = None) -> Confidence:
    score = draft.confidence
    notes: list[str] = []

    def penalize(amount: float, why: str) -> None:
        nonlocal score
        score -= amount
        notes.append(f"-{amount:.2f}: {why}")

    if obs is not None:
        key = sorted({f for f in obs.uncertain_fields if f.split(".")[0].split("[")[0] in KEY_FIELDS})
        if key:
            penalize(min(MAX_FIELD_PENALTY, PER_KEY_FIELD * len(key)), f"video model unsure of {', '.join(key)}")
        view = video.locate.chosen_view() if video else None
        if (obs.view_quality and POOR_VIEW.search(obs.view_quality)) or (view and view.clarity != "clear"):
            penalize(POOR_VIEW_PENALTY, "contact not clearly visible")
        loc = (obs.location or "").lower()
        inside = "penalty area" in loc and "outside" not in loc and "line" not in loc
        if draft.restart == "penalty_kick" and not inside:
            penalize(LOCATION_MISMATCH_PENALTY,
                     "penalty kick awarded but the video did not clearly place the contact inside the penalty area")
        if draft.restart == "direct_free_kick" and inside:
            penalize(LOCATION_MISMATCH_PENALTY, "direct free kick awarded although the contact was seen inside the penalty area")
    hinges = red_card_hinges(draft.card, obs)
    if hinges:
        penalize(HINGE_PENALTY, hinge_note(hinges))
    if draft.used_user_context:
        penalize(CONTEXT_PENALTY, "decision relies on the user's context hint")
    if second is not None:
        diffs = [f for f in ("verdict", "restart", "card") if getattr(draft, f) != getattr(second, f)]
        if diffs:
            penalize(DISAGREEMENT_PENALTY, "a second independent run disagreed on " + ", ".join(
                f"{f} ({getattr(draft, f)} vs {getattr(second, f)})" for f in diffs))
    if draft.verdict == "cannot_determine":
        score = min(score, 0.4)
        notes.append("capped: the decision could not be determined")

    score = round(max(0.0, min(1.0, score)), 2)
    return Confidence(model_score=draft.confidence, score=score, level=level(score), adjustments=notes)
