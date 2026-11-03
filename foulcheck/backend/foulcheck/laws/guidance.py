"""Official referee guidance: how referees apply the Laws' terms (reckless, excessive force, DOGSO...).

The Laws of the Game state principles ("endangers the safety of an opponent"); the specifics a referee
uses (studs, point of contact, "ankle or above") are in guidance from the Premier League (PGMOL) and
UEFA. Pages are fetched once into data/guidance/<edition>/raw/ (gitignored), then chunked by heading
and indexed next to the Laws, clearly marked as guidance.

Usage (from backend/): uv run --extra fetch python -m foulcheck.laws.guidance fetch
"""

import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from foulcheck import config
from foulcheck.laws.models import Chunk
from foulcheck.laws.parse import normalize


@dataclass(frozen=True)
class Source:
    publisher: str  # "PL" or "UEFA"
    slug: str
    title: str
    url: str
    start: str  # first words of the guidance body, to cut away site navigation
    stop: tuple[str, ...]  # text that marks the end of the guidance body

    @property
    def id(self) -> str:
        return f"{self.publisher}-{self.slug}"


PUBLISHERS = {"PL": "Premier League", "UEFA": "UEFA"}
_PL_STOP = ("Contents", "Related", "Latest News", "PREMIER LEAGUE 20")
_UEFA_STOP = ("Related topics", "A decision standing after a check")
SOURCES = [
    Source("PL", "serious-foul-play", "Serious foul play", "https://www.premierleague.com/en/news/4079964", "Additional guidance", _PL_STOP),
    Source("PL", "high-foot", "High foot challenges", "https://www.premierleague.com/en/news/4079982", "Additional guidance", _PL_STOP),
    Source("PL", "holding", "Holding", "https://www.premierleague.com/en/news/4079609", "Additional guidance", _PL_STOP),
    Source("PL", "blocking", "Blocking", "https://www.premierleague.com/en/news/4079624", "Additional guidance", _PL_STOP),
    Source("PL", "handball", "Handball: interpretation", "https://www.premierleague.com/en/news/4079558", "Additional guidance", _PL_STOP),
    Source("PL", "dogso", "Denying a goal or an obvious goal-scoring opportunity", "https://www.premierleague.com/en/news/4079682", "Additional guidance", _PL_STOP),
    Source("PL", "violent-conduct", "Violent conduct", "https://www.premierleague.com/en/news/4079974", "Additional guidance", _PL_STOP),
    Source("UEFA", "serious-foul-play", "Serious foul play", "https://www.uefa.com/running-competitions/refereeing/clear-line/red-cards/serious-foul-play/", "Serious foul play covers", _UEFA_STOP),
    Source("UEFA", "dogso", "Denying a goal-scoring opportunity", "https://www.uefa.com/running-competitions/refereeing/clear-line/red-cards/dogso/", "", _UEFA_STOP),
    Source("UEFA", "violent-conduct", "Violent conduct", "https://www.uefa.com/running-competitions/refereeing/clear-line/red-cards/violent-conduct/", "", _UEFA_STOP),
    Source("UEFA", "second-yellow", "Second yellow card", "https://www.uefa.com/running-competitions/refereeing/clear-line/red-cards/second-yellow/", "", _UEFA_STOP),
]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def raw_dir() -> Path:
    return config.laws_config().data_dir / "guidance"


def fetch(sources: list[Source] = SOURCES) -> None:
    """Render each page in headless Chrome (UEFA blocks plain HTTP clients) and save its text."""
    from playwright.sync_api import sync_playwright

    out = raw_dir()
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(user_agent=UA, viewport={"width": 1280, "height": 1600})
        for s in sources:
            page.goto(s.url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            for label in ("Reject All", "Reject all", "Reject All Cookies", "Necessary only"):  # decline non-essential cookies
                button = page.get_by_role("button", name=label)
                if button.count():
                    button.first.click()
                    break
            for _ in range(5):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(800)
            # UEFA keeps the detailed criteria in collapsed accordions: open each one before reading.
            for heading in ("What referees consider", "When VAR should"):
                items = page.get_by_text(heading)
                for k in range(items.count()):
                    try:
                        items.nth(k).click(timeout=3000)
                        page.wait_for_timeout(400)
                    except Exception:
                        pass
            text = page.inner_text("body")
            (out / f"{s.id}.txt").write_text(text)
            (out / f"{s.id}.json").write_text(json.dumps({"url": s.url, "title": s.title, "fetched": time.strftime("%Y-%m-%d")}))
            print(f"{s.id}: {len(text)} chars")
        browser.close()


DATE_LINE = re.compile(r"^\d{1,2} [A-Z][a-z]{2} \d{4}$")
UEFA_NAV_LAST = "Second yellow"
MIN_WORDS = 6


def _body(source: Source, lines: list[str]) -> list[str]:
    """Cut away site navigation: the guidance body sits between a start marker and a stop marker."""
    start = 0
    if source.publisher == "PL":
        start = next((i + 1 for i, l in enumerate(lines) if DATE_LINE.match(l.strip())), 0)
    else:
        overview = next((i for i, l in enumerate(lines) if l.strip() == "Overview"), 0)
        start = next((i + 1 for i in range(overview, len(lines)) if lines[i].strip() == UEFA_NAV_LAST), overview)
    end = next((i for i in range(start, len(lines)) if lines[i].strip().startswith(source.stop)), len(lines))
    return lines[start:end]


PLAYER_JUNK = re.compile(r"\d+ seconds of \d+ seconds|Volume \d+%")


def _is_heading(line: str, nxt: str) -> bool:
    """Section headings are short title-case lines followed by a blank line (or UEFA's ✅/❌ markers)."""
    raw = line.strip()
    t = raw.lstrip("✅❌ ").strip()
    if not t or len(t) > 70 or "\t" in line or not t[0].isupper() or t.startswith("Video "):
        return False
    if t.endswith((".", ",", ":", ";", ")", "?")):
        return False
    return raw[0] in "✅❌" or nxt.strip() == "" or t.startswith("What referees consider")


def parse_source(source: Source, text: str, edition: str) -> list[Chunk]:
    lines = _body(source, text.splitlines())
    sections: list[tuple[str, list[str]]] = [("", [])]
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        item = line.strip()
        if not item or item == "Additional guidance" or PLAYER_JUNK.search(item):
            continue
        if _is_heading(line, nxt):
            sections.append((item.lstrip("✅❌ ").strip(), []))
        elif item[0].islower() and sections[-1][1]:
            sections[-1][1][-1] += " " + item  # a wrapped line continues the previous item
        else:
            item = "• " + item.lstrip("-").strip() if item.startswith("-") else item
            sections[-1][1].append(item.replace("\t", " / "))
    chunks = []
    for heading, body in sections:
        text_ = normalize(" ".join(body))
        if len(text_.split()) < MIN_WORDS:
            continue
        chunks.append(Chunk(
            id=f"{source.id}-{len(chunks) + 1}", law=source.publisher,
            law_title=f"{PUBLISHERS[source.publisher]} referee guidance", section=source.slug,
            title=source.title, subtitle=heading, page=0, edition=edition, text=text_,
            kind="guidance", url=source.url,
        ))
    return chunks


def parse_guidance(edition: str | None = None) -> list[Chunk]:
    """Chunks for every fetched page; empty if the guidance was never fetched."""
    edition = edition or config.laws_config().edition
    out = []
    for s in SOURCES:
        f = raw_dir() / f"{s.id}.txt"
        if f.exists():
            out += parse_source(s, f.read_text(), edition)
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        fetch()
    else:
        sys.exit(__doc__)
