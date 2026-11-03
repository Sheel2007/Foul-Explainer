"""Draw the side panel shown next to the video: the call, the key moment, why, and the rule
text with the deciding words highlighted. Pure Pillow, so it needs no ffmpeg text filters."""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from foulcheck.decision.schema import Citation, Ruling

BG = (17, 20, 18)
TEXT = (236, 240, 237)
MUTED = (150, 162, 156)
LINE = (52, 60, 56)
PITCH = (34, 163, 85)
MARK_BG = (255, 212, 59)
MARK_TEXT = (20, 20, 20)
CARD = {"yellow": (250, 204, 21), "red": (220, 38, 38)}
LEVEL = {"High": (34, 163, 85), "Medium": (217, 139, 6), "Low": (220, 38, 38)}
CONTACT_BG = (220, 38, 38)

VERDICT = {"foul": "FOUL", "no_foul": "NO FOUL", "handball": "HANDBALL", "cannot_determine": "CANNOT TELL"}
PUBLISHER = {"PL": "Premier League", "UEFA": "UEFA"}
RESTART = {"direct_free_kick": "Direct free kick", "indirect_free_kick": "Indirect free kick",
           "penalty_kick": "Penalty kick", "play_on": "Play on", "unknown": "Restart unclear"}

FONT_FILES = {
    "regular": ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "bold": ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "italic": ["/System/Library/Fonts/Supplemental/Arial Italic.ttf", "/Library/Fonts/Arial Italic.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"],
}
BANNER_H = 64  # top strip with the app name


@lru_cache(maxsize=64)
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_FILES[weight]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


@dataclass
class Run:
    text: str
    marked: bool = False


def spans(text: str, highlight: str | None) -> list[Run]:
    """Split text into plain and highlighted runs (first occurrence of `highlight`)."""
    if not highlight:
        return [Run(text)]
    i = text.lower().find(highlight.lower())
    if i < 0:
        return [Run(text)]
    parts = [Run(text[:i]), Run(text[i:i + len(highlight)], True), Run(text[i + len(highlight):])]
    return [p for p in parts if p.text]


Word = list[tuple[str, bool]]  # pieces of one word; a highlight can start or end inside a word


def words(runs: list[Run]) -> list[Word]:
    """Split runs into words, keeping highlight boundaries that fall inside a word (e.g. 'challenges”')."""
    out: list[Word] = []
    glue = False  # does the next piece continue the previous word?
    for run in runs:
        for piece in re.findall(r"\s+|\S+", run.text):
            if piece.isspace():
                glue = False
            elif glue and out:
                out[-1].append((piece, run.marked))
            else:
                out.append([(piece, run.marked)])
                glue = True
    return out


def wrap(runs: list[Run], f: ImageFont.FreeTypeFont, width: int) -> list[list[Word]]:
    """Greedy word wrap."""
    lines: list[list[Word]] = [[]]
    used = 0.0
    space = f.getlength(" ")
    for word in words(runs):
        w = sum(f.getlength(p) for p, _ in word)
        if lines[-1] and used + space + w > width:
            lines.append([])
            used = 0.0
        used += (space if lines[-1] else 0) + w
        lines[-1].append(word)
    return [line for line in lines if line]


class Canvas:
    """Lays out blocks top to bottom; with draw=False it only measures."""

    def __init__(self, width: int, height: int, scale: float, draw: bool):
        self.w, self.h, self.s = width, height, scale
        self.pad = round(32 * scale)
        self.y = BANNER_H + round(8 * scale)
        self.img = Image.new("RGB", (width, height), BG) if draw else None
        self.d = ImageDraw.Draw(self.img) if draw else None

    def size(self, px: int) -> int:
        return max(10, round(px * self.s))

    def gap(self, px: int) -> None:
        self.y += round(px * self.s)

    def text(self, runs: list[Run] | str, weight: str = "regular", px: int = 20, color=TEXT,
             max_lines: int | None = None, indent: int = 0) -> None:
        f = font(weight, self.size(px))
        runs = [Run(runs)] if isinstance(runs, str) else runs
        lines = wrap(runs, f, self.w - 2 * self.pad - indent)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            piece, marked = lines[-1][-1][-1]
            lines[-1][-1][-1] = (piece.rstrip(".,;:") + "…", marked)
        ascent, descent = f.getmetrics()
        line_h = round((ascent + descent) * 1.3)
        space = f.getlength(" ")
        for line in lines:
            if self.d:
                x = self.pad + indent
                for i, word in enumerate(line):
                    for j, (piece, marked) in enumerate(word):
                        w = f.getlength(piece)
                        if marked:
                            # extend the box across the gap when the next word is highlighted too
                            joins = j == len(word) - 1 and i + 1 < len(line) and line[i + 1][0][1]
                            self.d.rectangle([x - 2, self.y - 2, x + w + (space if joins else 0) + 2,
                                              self.y + ascent + descent + 2], fill=MARK_BG)
                        self.d.text((x, self.y), piece, font=f, fill=MARK_TEXT if marked else color)
                        x += w
                    x += space
            self.y += line_h

    def rule(self) -> None:
        if self.d:
            self.d.line([self.pad, self.y, self.w - self.pad, self.y], fill=LINE, width=2)
        self.gap(16)

    def heading(self, label: str) -> None:
        self.text(label.upper(), "bold", 15, MUTED)
        self.gap(4)


def _verdict_block(c: Canvas, r: Ruling) -> None:
    top = c.y
    c.text(VERDICT[r.verdict], "bold", 60)
    sub = RESTART[r.restart] + ("" if r.card == "none" else f"  ·  {r.card.capitalize()} card")
    c.text(sub, "bold", 26)
    if r.offence_type:
        c.text(r.offence_type[:1].upper() + r.offence_type[1:], "regular", 20, MUTED)
    if c.d and r.card in CARD:
        cw, ch = c.size(46), c.size(64)
        x = c.w - c.pad - cw
        c.d.rounded_rectangle([x, top + 6, x + cw, top + 6 + ch], radius=c.size(6), fill=CARD[r.card])
    c.gap(10)
    # confidence pill + key moment
    f = font("bold", c.size(17))
    label = f"{r.confidence.level} confidence"
    if c.d:
        w = f.getlength(label)
        h = sum(f.getmetrics())
        c.d.rounded_rectangle([c.pad, c.y, c.pad + w + 24, c.y + h + 12], radius=(h + 12) // 2,
                              fill=LEVEL[r.confidence.level])
        c.d.text((c.pad + 12, c.y + 6), label, font=f, fill=(255, 255, 255))
        if r.key_moment:
            km = f"Key moment {r.key_moment}"
            fk = font("regular", c.size(18))
            c.d.text((c.pad + w + 40, c.y + 7), km, font=fk, fill=MUTED)
    c.y += sum(f.getmetrics()) + 12
    c.gap(18)


def _citation(c: Canvas, cit: Citation) -> None:
    if cit.kind == "guidance":
        title = f"{PUBLISHER.get(cit.section, cit.section)} referee guidance  {cit.title}"
    else:
        title = f"Law {cit.section}  {cit.title}" + (f" – {cit.subtitle}" if cit.subtitle else "")
    c.text(title, "bold", 18, PITCH, max_lines=2)
    c.gap(2)
    if cit.quote:
        c.text(spans(f"“{cit.quote}”", cit.highlight), "italic", 19, TEXT, max_lines=6, indent=0)
    else:
        c.text(cit.why, "regular", 18, MUTED, max_lines=3)
    c.gap(12)


def _layout(r: Ruling, c: Canvas, max_citations: int, show_gray: bool) -> None:
    _verdict_block(c, r)
    c.rule()
    c.heading("Why")
    c.text(r.explanation, "regular", 19, TEXT, max_lines=8)
    c.gap(14)
    c.rule()
    c.heading("The rule")
    for cit in r.citations[:max_citations]:
        _citation(c, cit)
    if show_gray and r.gray_areas:
        c.heading("A referee could also see")
        c.text(r.gray_areas[0], "regular", 17, MUTED, max_lines=3)


def _footer(c: Canvas, r: Ruling) -> int:
    text = f"{r.edition_label} © The IFAB."
    if any(c.kind == "guidance" for c in r.citations):
        text += " Guidance: " + ", ".join(sorted({PUBLISHER.get(c.section, c.section) for c in r.citations
                                                  if c.kind == "guidance"})) + "."
    text += " An explanation, not an official ruling."
    f = font("regular", c.size(14))
    lines = wrap([Run(text)], f, c.w - 2 * c.pad)
    h = len(lines) * round(sum(f.getmetrics()) * 1.3)
    if c.d:
        y = c.h - c.pad // 2 - h
        for line in lines:
            c.d.text((c.pad, y), " ".join("".join(p for p, _ in word) for word in line), font=f, fill=MUTED)
            y += round(sum(f.getmetrics()) * 1.3)
    return h


def draw_panel(r: Ruling, width: int = 640, height: int = 720) -> Image.Image:
    """Render the panel, shrinking text and dropping extras until everything fits."""
    attempts = [(s, n, g) for g in (True, False) for n in (3, 2) for s in (1.0, 0.92, 0.85, 0.78, 0.72)]
    for scale, n_cit, gray in attempts:
        probe = Canvas(width, height, scale, draw=False)
        _layout(r, probe, n_cit, gray)
        if probe.y + _footer(probe, r) + probe.pad <= height:
            break
    c = Canvas(width, height, scale, draw=True)
    _layout(r, c, n_cit, gray)
    _footer(c, r)
    # The top strip shows the app name.
    c.d.text((c.pad, (BANNER_H - sum(font("bold", 15).getmetrics())) // 2 + 4), "FOUL EXPLAINER",
             font=font("bold", 15), fill=MUTED)
    return c.img


def draw_contact_tag(detail: str | None = None) -> Image.Image:
    """Rounded red tag shown on the video itself while the contact is on screen, sized to its text."""
    f = font("bold", 34)
    label = "CONTACT" + (f"  ·  {detail}" if detail else "")
    pad_x, pad_y = 26, 14
    w = int(f.getlength(label)) + 2 * pad_x + 34  # room for the dot
    h = sum(f.getmetrics()) + 2 * pad_y
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=CONTACT_BG + (235,))
    r = 9
    d.ellipse([pad_x, h // 2 - r, pad_x + 2 * r, h // 2 + r], fill=(255, 255, 255))
    d.text((pad_x + 34, pad_y), label, font=f, fill=(255, 255, 255))
    return img
