"""Judge clips end to end and print the ruling.

Usage: uv run python -m foulcheck [CLIP ...] [--context "it was inside the box"] [--json]
With no clips, runs every video in eval/clips/.
"""

import argparse
import sys
import textwrap
from pathlib import Path

from foulcheck import config
from foulcheck.decision.engine import DecisionEngine
from foulcheck.decision.models import make_text_model
from foulcheck.decision.schema import Ruling
from foulcheck.pipeline import analyze_clip
from foulcheck.video import make_analyzer
from foulcheck.video.__main__ import VIDEO_EXT

LABELS = {"foul": "FOUL", "no_foul": "NO FOUL", "handball": "HANDBALL", "cannot_determine": "CANNOT TELL"}


def render(r: Ruling, clip: str) -> str:
    wrap = lambda s, ind="   ": textwrap.fill(s, 100, initial_indent=ind, subsequent_indent=ind)
    restart = r.restart.replace("_", " ")
    card = "" if r.card == "none" else f", {r.card.upper()} CARD"
    offence = f" ({r.offence_type})" if r.offence_type else ""
    lines = [
        f"\n== {clip}",
        f"   {LABELS[r.verdict]}: {restart}{card}{offence}",
        f"   Confidence: {r.confidence.level} ({r.confidence.score:.2f}, model said {r.confidence.model_score:.2f})",
        f"   Key moment: {r.key_moment or '-'}",
    ]
    if r.observation:
        lines += ["   What the model saw:", wrap(r.observation.summary, "     ")]
    lines += ["   Why:", wrap(r.explanation, "     "), "   The rule:"]
    for c in r.citations:
        lines.append(f"     - {c.reference} [{c.chunk_id}]: {c.why}")
        if c.quote:
            lines.append(wrap(f'"{c.quote}"', "         "))
    if r.gray_areas:
        lines.append("   A referee could also see it this way:")
        lines += [wrap(f"- {g}", "     ") for g in r.gray_areas]
    for a in r.confidence.adjustments:
        lines.append(f"   confidence {a}")
    for n in r.notes:
        lines.append(f"   note: {n}")
    lines.append(f"   ({r.edition_label}. {r.disclaimer})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m foulcheck")
    ap.add_argument("clips", nargs="*", type=Path)
    ap.add_argument("--context", help="optional hint, e.g. 'this was in the penalty area'")
    ap.add_argument("--analyzer", default="gemini")
    ap.add_argument("--video-model")
    ap.add_argument("--decision-provider")
    ap.add_argument("--decision-model")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    clips = args.clips or sorted(p for p in (config.REPO_DIR / "eval" / "clips").iterdir()
                                 if p.suffix.lower() in VIDEO_EXT)
    analyzer = make_analyzer(args.analyzer, args.video_model)
    engine = DecisionEngine(make_text_model(args.decision_provider, args.decision_model))
    failures = 0
    for clip in clips:
        try:
            ruling = analyze_clip(clip, args.context, analyzer=analyzer, engine=engine, use_cache=not args.no_cache)
        except Exception as exc:  # report and keep going through the batch
            failures += 1
            print(f"{clip.name}: ERROR {exc}", file=sys.stderr)
            continue
        print(ruling.model_dump_json(indent=2) if args.json else render(ruling, clip.name))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
