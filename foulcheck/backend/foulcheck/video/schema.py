"""Observation schema: what the video model saw. Facts only, never rulings.

Field descriptions are sent to the model as part of the JSON schema, so they double as
instructions for each field.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TS_RE = re.compile(r"^(\d{1,2}):(\d{2}(?:\.\d+)?)$")


def parse_ts(ts: str) -> float:
    """'01:07.4' -> 67.4"""
    m = TS_RE.match(ts.strip())
    if not m:
        raise ValueError(f"timestamp {ts!r} is not MM:SS.s")
    return int(m.group(1)) * 60 + float(m.group(2))


def fmt_ts(seconds: float) -> str:
    """67.43 -> '01:07.4'"""
    seconds = max(0.0, seconds)
    minutes, rest = divmod(round(seconds, 1), 60)
    return f"{int(minutes):02d}:{rest:04.1f}"


def _check_ts(v: str | None) -> str | None:
    if v is not None:
        parse_ts(v)
    return v


class Player(BaseModel):
    id: str = Field(description="Short label used elsewhere in this answer, e.g. 'A', 'B'.")
    team: str | None = Field(None, description="Shirt colour, e.g. 'red', 'white'.")
    number: str | None = Field(None, description="Shirt number if readable, else null.")
    role: str | None = Field(None, description="e.g. 'defender', 'attacker', 'goalkeeper', or null.")


class Contact(BaseModel):
    made: bool | None = Field(None, description="Did the players physically touch? null if it cannot be seen.")
    by: str | None = Field(None, description="Player id who made the contact.")
    on: str | None = Field(None, description="Player id who received the contact.")
    body_part_used: str | None = Field(None, description="e.g. 'studs/sole', 'instep', 'knee', 'hand', 'arm', 'shoulder', 'body'.")
    body_part_hit: str | None = Field(None, description="e.g. 'ankle', 'shin', 'calf', 'thigh', 'foot', 'torso', 'head'.")


class ChallengeDetail(BaseModel):
    """How the challenging leg met the opponent. These details decide how dangerous a challenge was,
    so they are asked for explicitly instead of hoping a free-text field mentions them."""

    studs_showing: bool | None = Field(None, description="At contact, was the sole/studs of the challenging boot facing the opponent (studs up), rather than the side of the foot?")
    leg_straight: bool | None = Field(None, description="Was the contacting leg straight/locked at contact, rather than bent?")
    lunge: bool | None = Field(None, description="Did the challenger launch or lunge at the opponent, e.g. leaving the ground or sliding in with the leg fully extended?")
    follow_through: bool | None = Field(None, description="After any touch on the ball, did the challenging leg carry on into the opponent?")


class Handball(BaseModel):
    touched: bool | None = Field(None, description="Did the ball touch a player's hand or arm (below the armpit)?")
    arm_position: str | None = Field(None, description="Where the arm was, e.g. 'by the side', 'extended away from body', 'above shoulder'.")
    deliberate_movement: bool | None = Field(None, description="Did the hand/arm move towards the ball?")


class Observation(BaseModel):
    contact_time: str | None = Field(None, description="Moment of contact on the original video timeline, MM:SS.s.")
    players: list[Player] = Field(default_factory=list)
    contact: Contact = Field(default_factory=Contact)
    ball_played_first: bool | None = Field(None, description="Did the challenging player touch the ball before the contact?")
    challenge: ChallengeDetail = Field(default_factory=ChallengeDetail)
    boot_detail: str | None = Field(None, description="One sentence on what the challenging boot is doing at contact: sole/studs, side of the foot, laces or toe, and where it lands.")
    contact_box: list[float] | None = Field(None, description="Box around the challenging boot and the opponent's leg at the moment of contact, as [ymin, xmin, ymax, xmax] scaled 0-1000.")
    challenge_type: str | None = Field(None, description="e.g. 'sliding tackle', 'standing tackle', 'shoulder charge', 'trip', 'push', 'shirt pull', 'aerial challenge', 'block'.")
    speed_and_force: Literal["low", "medium", "high"] | None = Field(None, description="Speed and force of the challenging player at contact.")
    handball: Handball = Field(default_factory=Handball)
    location: str | None = Field(None, description="'inside penalty area', 'outside penalty area', 'on the penalty area line', or null if not visible.")
    attack_context: str | None = Field(None, description="Where play was heading: attacker direction, ball control, defenders between attacker and goal.")
    view_quality: str | None = Field(None, description="How clearly the contact is visible, and what blocks the view.")
    uncertain_fields: list[str] = Field(default_factory=list, description="Names of fields above that could not be seen clearly.")
    summary: str = Field("", description="2-4 plain sentences of what happens, with MM:SS.s timestamps. Facts only.")

    @field_validator("contact_time")
    @classmethod
    def _valid_ts(cls, v: str | None) -> str | None:
        return _check_ts(v)

    @field_validator("contact_box")
    @classmethod
    def _valid_box(cls, v: list[float] | None) -> list[float] | None:
        # A bad box only means no close-up, so drop it rather than fail the whole observation.
        if v is None or len(v) != 4 or not all(0 <= x <= 1000 for x in v) or v[0] >= v[2] or v[1] >= v[3]:
            return None
        return v

    @property
    def contact_seconds(self) -> float | None:
        return parse_ts(self.contact_time) if self.contact_time else None

    def describe(self) -> str:
        """Plain-text summary used as the vector search query."""
        c, h = self.contact, self.handball
        parts = [
            self.challenge_type,
            f"contact made with {c.body_part_used} on {c.body_part_hit}" if c.made else
            ("no contact" if c.made is False else None),
            {True: "ball played first", False: "ball not played"}.get(self.ball_played_first),
            f"{self.speed_and_force} speed and force" if self.speed_and_force else None,
            "studs showing" if self.challenge.studs_showing else None,
            "straight leg" if self.challenge.leg_straight else None,
            "lunging at the opponent" if self.challenge.lunge else None,
            "follows through after playing the ball" if self.challenge.follow_through else None,
            f"ball touched hand/arm, arm {h.arm_position}" if h.touched else None,
            "deliberate arm movement towards the ball" if h.deliberate_movement else None,
            self.location,
            self.attack_context,
        ]
        return ". ".join(p for p in parts if p)


class CloseUp(BaseModel):
    """Answers from a cropped, enlarged view of the contact: the boot-level detail the wide shot is too small for."""

    challenge: ChallengeDetail = Field(default_factory=ChallengeDetail)
    body_part_used: str | None = Field(None, description="Part of the boot or leg that made contact, e.g. 'studs/sole', 'instep', 'outside of foot', 'shin'.")
    body_part_hit: str | None = Field(None, description="Part of the opponent that was hit, e.g. 'ankle', 'shin', 'calf', 'foot'.")
    boot_detail: str = Field("", description="One sentence on what the challenging boot is doing at contact.")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields above that could not be seen clearly even in the close-up.")


class View(BaseModel):
    contact_time: str = Field(description="Moment of contact in this view, on the video timeline, MM:SS.s.")
    kind: Literal["live", "replay"]
    slow_motion: bool = False
    camera: str = Field(description="e.g. 'wide main camera', 'close-up from behind the goal', 'reverse angle'.")
    clarity: Literal["clear", "partial", "poor"] = Field(description="How clearly the contact itself can be seen.")

    @field_validator("contact_time")
    @classmethod
    def _valid_ts(cls, v: str) -> str:
        return _check_ts(v)

    @property
    def contact_seconds(self) -> float:
        return parse_ts(self.contact_time)


class LocateResult(BaseModel):
    incident_found: bool
    incident: str = Field("", description="One neutral sentence describing the incident.")
    views: list[View] = Field(default_factory=list, description="Every time the incident is shown: live first, then each replay.")
    best_view: int = Field(0, description="Index into views of the one that shows the contact most clearly.")
    players: list[Player] = Field(default_factory=list)

    def chosen_view(self) -> View | None:
        if not self.views:
            return None
        return self.views[self.best_view] if 0 <= self.best_view < len(self.views) else self.views[0]


class VideoAnalysis(BaseModel):
    clip: str
    sha256: str
    duration_s: float
    analyzer: str
    locate: LocateResult
    window: tuple[float, float] | None = None
    observation: Observation | None = None
    closeup: CloseUp | None = None
    notes: list[str] = Field(default_factory=list)
    timings: dict[str, float | bool | None] = Field(default_factory=dict)
