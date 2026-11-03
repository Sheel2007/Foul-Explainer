"""Ruling schemas. RulingDraft is what the decision model returns; Ruling is what the app shows."""

from typing import Literal

from pydantic import BaseModel, Field

from foulcheck.video.schema import Observation, VideoAnalysis

Verdict = Literal["foul", "no_foul", "handball", "cannot_determine"]
Restart = Literal["direct_free_kick", "indirect_free_kick", "penalty_kick", "play_on", "unknown"]
Card = Literal["none", "yellow", "red"]
Level = Literal["High", "Medium", "Low"]


class CitationDraft(BaseModel):
    chunk_id: str = Field(description="ID of one of the Law passages provided. Never invent IDs.")
    why: str = Field(description="One sentence: what this passage establishes for this decision.")
    quote: str | None = Field(None, description="Optional short passage (under 30 words) copied character for character from that chunk.")
    highlight: str | None = Field(None, description="The few words inside your quote that decide this case, copied exactly from the quote.")


class RulingDraft(BaseModel):
    verdict: Verdict
    offence_type: str | None = Field(None, description="e.g. 'reckless challenge', 'careless trip', 'holding', 'deliberate handball'; null if no offence.")
    restart: Restart
    card: Card
    confidence: float = Field(ge=0, le=1, description="How sure you are of verdict, restart and card together.")
    explanation: str = Field(description="3-5 plain sentences for a fan. Each claim tied to an observation or a cited passage.")
    citations: list[CitationDraft]
    gray_areas: list[str] = Field(default_factory=list, description="What a referee could reasonably see differently, and why.")
    key_moment: str | None = Field(None, description="MM:SS.s of the decisive moment, from the observation.")
    used_user_context: bool = Field(False, description="True if the user's context hint affected the decision.")


class Citation(BaseModel):
    chunk_id: str
    law: str
    section: str
    title: str
    subtitle: str = ""
    page: int
    reference: str
    why: str
    quote: str | None = None  # only kept when found word for word in the Laws
    highlight: str | None = None  # words inside `quote` to emphasise; always a substring of quote
    source_url: str
    kind: Literal["law", "guidance"] = "law"  # guidance = Premier League / UEFA referee guidance


class Confidence(BaseModel):
    model_score: float
    score: float
    level: Level
    adjustments: list[str] = Field(default_factory=list)


class Ruling(BaseModel):
    verdict: Verdict
    offence_type: str | None
    restart: Restart
    card: Card
    confidence: Confidence
    explanation: str
    citations: list[Citation]
    gray_areas: list[str]
    key_moment: str | None
    edition: str
    edition_label: str
    context_hint: str | None = None
    used_user_context: bool = False
    observation: Observation | None = None
    video: VideoAnalysis | None = None
    notes: list[str] = Field(default_factory=list)
    audit: dict[str, int | float | str | bool | None] = Field(default_factory=dict)
    disclaimer: str = "An explanation of how the Laws of the Game apply to what the model saw, not an official ruling."
