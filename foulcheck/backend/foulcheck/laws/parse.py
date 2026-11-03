"""Parse the Laws PDF into structured chunks: Law -> section -> sub-heading -> paragraph.

The PDF is laid out as double-page spreads, so each PDF page is split into a left and
right book page. The running footer ("Laws of the Game 2026/27 | Law 12 | Fouls and
Misconduct") says which Law a page belongs to; pages without a footer inherit it.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from foulcheck.laws.models import Chunk

FOOTER_Y = 555  # page numbers and running footers sit below this line
BODY_SIZE = (8.5, 9.6)  # body text and in-text headings are 9-9.2pt
PARA_GAP = 16  # body lines are 13pt apart; paragraphs are separated by ~19.5pt
HEADING_LIFT = 12  # headings are drawn a few points below the first body line next to them

FOOTER_RE = re.compile(r"Laws of the Game [\d/]+\s*\|\s*Law (\d+)\s*\|\s*(.+)")
OTHER_FOOTER_RE = re.compile(r"Laws of the Game [\d/]+\s*\|")
SECTION_RE = re.compile(r"^(\d+)\.\s+(.+)$")


@dataclass
class Line:
    y: float
    x: float
    text: str
    kind: str  # "section", "subheading", "body"


@dataclass
class HalfPage:
    page: int
    law: str | None
    law_title: str
    lines: list[Line]


@dataclass
class Paragraph:
    law: str
    law_title: str
    section: str
    title: str
    subtitle: str
    page: int
    parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return normalize(" ".join(self.parts))


def normalize(text: str) -> str:
    """Canonical whitespace and punctuation, shared with the citation guard."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text.replace(" ", " "))
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"•(?=\S)", "• ", text)
    return text.strip()


def pdf_page(book_page: int) -> int:
    """The PDF holds two book pages per sheet: book pages 114-115 are PDF page 58."""
    return book_page // 2 + 1


def _classify(spans: list[dict]) -> str | None:
    main = max(spans, key=lambda s: len(s["text"].strip()))
    size, font = main["size"], main["font"]
    if not (BODY_SIZE[0] <= size <= BODY_SIZE[1]):
        return None
    text = "".join(s["text"] for s in spans).strip()
    if "ExtraBold" in font:
        return "section" if SECTION_RE.match(text) else None
    if "Bold" in font and "Black" not in font:
        return "subheading"
    return "body"


def _read_halves(pdf_path: Path) -> list[HalfPage]:
    doc = pymupdf.open(pdf_path)
    halves: list[HalfPage] = []
    law, law_title = None, ""
    for pdf_page in doc:
        mid = pdf_page.rect.width / 2
        sides: dict[str, dict] = {"L": {"rows": {}, "page": None, "footer": None},
                                  "R": {"rows": {}, "page": None, "footer": None}}
        for block in pdf_page.get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                x0, y0 = ln["bbox"][0], ln["bbox"][1]
                side = sides["L" if x0 < mid else "R"]
                text = "".join(s["text"] for s in spans).strip()
                if y0 > FOOTER_Y:
                    if text.isdigit():
                        side["page"] = int(text)
                    else:
                        side["footer"] = text
                    continue
                kind = _classify(spans)
                if kind is None:
                    continue
                # Bullet glyphs and their text can arrive as separate lines on one row.
                key = round(y0)
                row = side["rows"].setdefault(key, [])
                row.append((x0, text, kind))
        for name in ("L", "R"):
            side = sides[name]
            footer = side["footer"]
            if footer:
                m = FOOTER_RE.search(footer)
                if m:
                    law, law_title = m.group(1), m.group(2).strip()
                elif OTHER_FOOTER_RE.search(footer):
                    law, law_title = None, ""
            lines = []
            for y, parts in side["rows"].items():
                parts.sort()
                kinds = {k for _, _, k in parts}
                kind = "section" if "section" in kinds else "subheading" if kinds == {"subheading"} else "body"
                text = " ".join(t for _, t, _ in parts)
                lift = HEADING_LIFT if kind != "body" else 0
                lines.append(Line(y=y - lift, x=parts[0][0], text=text, kind=kind))
            lines.sort(key=lambda l: (l.y, l.x))
            if side["page"] is not None:
                halves.append(HalfPage(side["page"], law, law_title, lines))
    halves.sort(key=lambda h: h.page)
    return halves


def _paragraphs(halves: list[HalfPage]) -> list[Paragraph]:
    paras: list[Paragraph] = []
    cur: Paragraph | None = None
    law = section = title = subtitle = ""
    law_title = ""

    def flush():
        nonlocal cur
        if cur and cur.text:
            paras.append(cur)
        cur = None

    for half in halves:
        if half.law is None:
            flush()
            law = ""
            continue
        if half.law != law:
            flush()
            law, law_title = half.law, half.law_title
            section, title, subtitle = "", "", ""
        prev_y = None
        for line in half.lines:
            if line.kind == "section":
                flush()
                m = SECTION_RE.match(line.text)
                section, title, subtitle = f"{law}.{m.group(1)}", normalize(m.group(2)), ""
                prev_y = None
                continue
            if line.kind == "subheading":
                flush()
                subtitle = normalize(line.text)
                prev_y = None
                continue
            new_para = cur is None
            if cur is not None and (prev_y is None or line.y - prev_y > PARA_GAP):
                # A page break or a wide gap starts a new paragraph unless the text reads as
                # a continuation (mid-sentence, or the next item of a bullet list).
                new_para = not _continues(cur, line.text)
            if new_para:
                flush()
                cur = Paragraph(law, law_title, section, title, subtitle, half.page)
            cur.parts.append(line.text)
            prev_y = line.y
    flush()
    return paras


CONNECTIVES = ("by", "or", "and", "to", "of", "the", "a", "with", "if", "when")


def _continues(cur: Paragraph, text: str) -> bool:
    last = cur.parts[-1].rstrip()
    last_word = last.rsplit(" ", 1)[-1].lower()
    if last.endswith(":") or last_word in CONNECTIVES or text[:1].islower():
        return True
    return text.startswith("•") and any("•" in part for part in cur.parts)


def _slug(text: str, limit: int = 5) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    stop = {"the", "a", "an", "of", "and", "or", "to", "in", "for", "with", "by", "on"}
    return "-".join([w for w in words if w not in stop][:limit])


def _is_prose(text: str) -> bool:
    """Diagram labels and table cells come through as short fragments with no sentence end."""
    return "•" in text or text.rstrip().endswith((".", ":", ")")) or len(text.split()) >= 15


def parse_laws(pdf_path: Path, edition: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    counts: dict[str, int] = {}
    for p in _paragraphs(_read_halves(pdf_path)):
        if not _is_prose(p.text):
            continue
        sec = p.section.split(".")[1] if p.section else "0"
        base = f"L{p.law}-{sec}"
        if p.subtitle:
            base += f"-{_slug(p.subtitle)}"
        counts[base] = counts.get(base, 0) + 1
        chunks.append(Chunk(
            id=f"{base}-p{counts[base]}",
            law=p.law,
            law_title=normalize(p.law_title),
            section=p.section,
            title=p.title,
            subtitle=p.subtitle,
            page=p.page,
            edition=edition,
            text=p.text,
        ))
    return chunks
