"""Citation guard: the model may only cite chunks it was given, and quotes must match exactly."""

import re

from foulcheck.config import laws_config
from foulcheck.decision.schema import Citation, CitationDraft, RulingDraft
from foulcheck.laws.models import Chunk
from foulcheck.laws.parse import normalize, pdf_page

# Quoted passages in the explanation: at least four words between double quotes.
QUOTED = re.compile(r"[\"“]([^\"“”]{12,}?)[\"”]")

# Which part of the Laws a restart or card must be grounded in: (law, section or None, tag or None).
# A penalty needs the passage that awards it (tag "penalty_kick"), not any Law 14 procedure text.
RESTART_SOURCE = {"penalty_kick": ("14", None, "penalty_kick"), "direct_free_kick": ("12", "12.1", None),
                  "indirect_free_kick": ("12", "12.2", None)}
CARD_SOURCE = ("12", "12.4", None)
# Preferred chunks when the engine has to add a grounding citation itself.
PREFERRED_TAG = {"penalty_kick": "penalty_kick", "direct_free_kick": "direct_free_kick",
                 "indirect_free_kick": "dangerous_play", "yellow": "caution", "red": "sending_off"}


def missing_grounds(draft: RulingDraft, chunks: list[Chunk]) -> list[tuple[str, str, list[Chunk]]]:
    """Restart/card decisions with no supporting citation: (key, description, candidate chunks)."""
    if draft.verdict == "cannot_determine":
        return []
    cited = {c.chunk_id for c in draft.citations}
    needs = []
    if draft.restart in RESTART_SOURCE:
        needs.append((draft.restart, f"the restart ({draft.restart.replace('_', ' ')})", RESTART_SOURCE[draft.restart]))
    if draft.card in ("yellow", "red"):
        needs.append((draft.card, f"the {draft.card} card", CARD_SOURCE))
    out = []
    for key, what, (law, section, tag) in needs:
        candidates = [c for c in chunks if c.law == law and (section is None or c.section == section)
                      and (tag is None or tag in c.tags)]
        if candidates and not cited.intersection(c.id for c in candidates):
            pref = PREFERRED_TAG.get(key)
            candidates.sort(key=lambda c: pref not in c.tags)
            out.append((key, what, candidates))
    return out


# "...", "…" or "[...]" mark words left out of a quote.
ELISION = re.compile(r"\s*(?:\[\s*(?:\.\.\.|…)\s*\]|\.\.\.|…)\s*")


def _segments(quote: str) -> list[list[str]]:
    """Pieces split at elisions, each split again at list bullets (quoting a list may skip items)."""
    pieces = []
    for piece in ELISION.split(quote):
        items = [normalize(i).strip(" .,;:").lower() for i in piece.split("•")]
        if items := [i for i in items if i]:
            pieces.append(items)
    return pieces


def _is_verbatim(quote: str, chunks: list[Chunk]) -> bool:
    """Every piece must appear word for word, in order, in one chunk.

    Pieces cut by an explicit "..." must be at least two words, so a stray word can't match anywhere.
    """
    pieces = _segments(quote)
    if not pieces or (len(pieces) > 1 and any(len(" ".join(p).split()) < 2 for p in pieces)):
        return False
    parts = [item for piece in pieces for item in piece]
    for c in chunks:
        text, pos = normalize(c.text).lower(), 0
        for part in parts:
            pos = text.find(part, pos)
            if pos < 0:
                break
            pos += len(part)
        else:
            return True
    return False


def check(draft: RulingDraft, chunks: list[Chunk]) -> list[str]:
    """Problems that justify one rerun of the decision step. Empty list = clean."""
    by_id = {c.id: c for c in chunks}
    errors: list[str] = []
    if not draft.citations and draft.verdict != "cannot_determine":
        errors.append("No citations. Cite the passages the decision rests on.")
    for cit in draft.citations:
        if cit.chunk_id not in by_id:
            errors.append(f"Citation {cit.chunk_id!r} is not one of the provided passage IDs.")
        elif cit.quote and not _is_verbatim(cit.quote, [by_id[cit.chunk_id]]):
            errors.append(f"Quote for {cit.chunk_id} is not word for word from that passage: {cit.quote!r}")
    for m in QUOTED.finditer(draft.explanation):
        if len(m.group(1).split()) >= 4 and not _is_verbatim(m.group(1), chunks):
            errors.append(f"Explanation quotes text that is not in the provided passages: {m.group(1)!r}")
    for _, what, candidates in missing_grounds(draft, chunks):
        errors.append(f"No citation supports {what}. Cite one of: {', '.join(c.id for c in candidates[:4])}.")
    return errors


def enforce(draft: RulingDraft, chunks: list[Chunk]) -> tuple[RulingDraft, list[str]]:
    """Last resort after the rerun: drop unknown citations and bad quotes, keep section refs."""
    by_id = {c.id: c for c in chunks}
    notes: list[str] = []
    kept = []
    for cit in draft.citations:
        if cit.chunk_id not in by_id:
            notes.append(f"Dropped citation to unknown passage {cit.chunk_id}.")
            continue
        if cit.quote and not _is_verbatim(cit.quote, [by_id[cit.chunk_id]]):
            notes.append(f"Removed an unverified quote from {cit.chunk_id}; showing the section reference only.")
            cit = cit.model_copy(update={"quote": None})
        kept.append(cit)
    explanation = draft.explanation
    for m in QUOTED.finditer(draft.explanation):
        if len(m.group(1).split()) >= 4 and not _is_verbatim(m.group(1), chunks):
            explanation = explanation.replace(m.group(0), m.group(1))
            notes.append("Removed quotation marks from paraphrased rule text in the explanation.")
    fixed = draft.model_copy(update={"citations": kept, "explanation": explanation})
    added = []
    for _, what, candidates in missing_grounds(fixed, chunks):
        added.append(CitationDraft(chunk_id=candidates[0].id, why=f"Sets {what}."))
        notes.append(f"Added a citation to {candidates[0].id} for {what}.")
    return fixed.model_copy(update={"citations": kept + added}), notes


# Terms worth emphasising when the model gives no usable highlight, keyed by what the ruling says.
HIGHLIGHT_TERMS = {
    "careless": ["careless"], "reckless": ["reckless", "cautioned"], "excessive": ["excessive force", "sent off"],
    "serious": ["serious foul play"], "violent": ["violent conduct"], "handball": ["hand/arm", "handball"],
    "trip": ["trips or attempts to trip"], "tackl": ["tackles or challenges"], "push": ["pushes"],
    "hold": ["holds an opponent"], "charg": ["charges"], "kick": ["kicks or attempts to kick"],
    "promising attack": ["promising attack"], "goal-scoring": ["obvious goal-scoring opportunity"],
    "penalty_kick": ["penalty kick is awarded"], "direct_free_kick": ["direct free kick"],
    "indirect_free_kick": ["indirect free kick"], "yellow": ["caution", "yellow card", "cautioned"],
    "red": ["sending-off", "sent off", "red card"],
}


def _highlight(quote: str, cit: CitationDraft, draft: RulingDraft) -> str | None:
    """The model's highlight if it is really inside the quote, else key terms the ruling relies on."""
    if cit.highlight:
        h = normalize(cit.highlight).strip(" .,;:")
        if h and h.lower() in quote.lower():
            start = quote.lower().index(h.lower())
            return quote[start:start + len(h)]
    signals = " ".join(x for x in (draft.offence_type, draft.restart, draft.card, draft.explanation) if x).lower()
    for key, terms in HIGHLIGHT_TERMS.items():
        if key in signals:
            for term in terms:
                i = quote.lower().find(term)
                if i >= 0:
                    return quote[i:i + len(term)]
    return None


def build_citations(draft: RulingDraft, chunks: list[Chunk]) -> list[Citation]:
    cfg = laws_config()
    by_id = {c.id: c for c in chunks}
    out, seen = [], set()
    for cit in draft.citations:
        c = by_id.get(cit.chunk_id)
        if c is None or c.id in seen:
            continue
        seen.add(c.id)
        quote = normalize(cit.quote) if cit.quote and _is_verbatim(cit.quote, [c]) else None
        out.append(Citation(
            chunk_id=c.id, law=c.law, section=c.law if c.kind == "guidance" else (c.section or c.law),
            title=c.title or c.law_title,
            subtitle=c.subtitle, page=c.page, reference=c.reference(), why=cit.why, quote=quote,
            highlight=_highlight(quote, cit, draft) if quote else None,
            source_url=c.url if c.kind == "guidance" else f"{cfg.pdf_url}#page={pdf_page(c.page)}",
            kind=c.kind,
        ))
    return out
