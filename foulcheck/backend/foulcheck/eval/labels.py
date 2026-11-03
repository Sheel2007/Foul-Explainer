"""Ground-truth labels: one JSON file per clip in eval/labels/<clip stem>.json.

Ruling labels (verdict, card, restart, required_sections, difficulty) must come from an official
or expert decision. Fact labels (contact_times) can be checked frame by frame.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from foulcheck import config
from foulcheck.decision.schema import Card, Restart, Verdict

LABEL_DIR = config.REPO_DIR / "eval" / "labels"


class Label(BaseModel):
    clip: str
    verdict: Verdict | None = None
    card: Card | None = None
    restart: Restart | None = None
    required_sections: list[str] = Field(default_factory=list, description="Law sections a correct answer must cite, e.g. ['12.1', '12.4'].")
    difficulty: Literal["clear", "hard"] | None = None
    ruling_source: str | None = Field(None, description="Where the ruling label came from, e.g. 'league review panel'.")
    contact_times: list[float] = Field(default_factory=list, description="Seconds where contact happens, one per view of the incident.")
    contact_source: str | None = None
    notes: str | None = None

    @property
    def has_ruling(self) -> bool:
        return self.verdict is not None


# label_dir defaults are resolved at call time so tests can point LABEL_DIR elsewhere.
def label_path(clip: str, label_dir: Path | None = None) -> Path:
    return (label_dir or LABEL_DIR) / f"{Path(clip).stem}.json"


def load_label(clip: str, label_dir: Path | None = None) -> Label:
    path = label_path(clip, label_dir)
    return Label.model_validate_json(path.read_text()) if path.exists() else Label(clip=clip)


def list_labels(label_dir: Path | None = None) -> list[Label]:
    return [Label.model_validate_json(p.read_text()) for p in sorted((label_dir or LABEL_DIR).glob("*.json"))]


def save_label(label: Label, label_dir: Path | None = None) -> Path:
    label_dir = label_dir or LABEL_DIR
    label_dir.mkdir(parents=True, exist_ok=True)
    path = label_path(label.clip, label_dir)
    path.write_text(label.model_dump_json(indent=2, exclude_defaults=False) + "\n")
    return path
