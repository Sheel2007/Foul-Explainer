from typing import Literal

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """One rule idea from the Laws, with enough metadata to cite it."""

    id: str
    law: str  # "12", or "Glossary"
    law_title: str
    section: str  # "12.1", or "" for a Law's preamble
    title: str  # section title, e.g. "Direct free kick"
    subtitle: str = ""  # sub-heading inside the section, e.g. "Handling the ball"
    page: int  # printed page number in the book
    edition: str
    text: str
    tags: list[str] = Field(default_factory=list)
    kind: Literal["law", "guidance"] = "law"  # guidance = official referee guidance on applying the Laws
    url: str = ""  # source page, for guidance

    def reference(self) -> str:
        if self.kind == "guidance":
            return f"{self.law_title} · {self.title}" + (f" – {self.subtitle}" if self.subtitle else "")
        where = f"Law {self.section}" if self.section else f"Law {self.law}"
        name = " – ".join(x for x in (self.title or self.law_title, self.subtitle) if x)
        return f"{where} {name} (p. {self.page})"
