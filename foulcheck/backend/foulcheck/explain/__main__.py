"""Make explained videos: the clip with the call, the key moment and the highlighted rule beside it.

Usage (from backend/):
  uv run python -m foulcheck.explain path/to/clip.mp4 [more clips...] [--context "..."]
  uv run python -m foulcheck.explain --rerender path/to/clip.mp4   # redraw from the saved ruling, no model calls
  uv run python -m foulcheck.explain --decision-model gemini-3-flash-preview clip.mp4  # when the default's quota is used up
  uv run python -m foulcheck.explain --video-model gemini-3.6-flash clip.mp4  # when the default video model is overloaded

Writes <out>/<name>_explained.mp4 and <out>/<name>_ruling.json (default out: foulcheck/explained/).
"""

import argparse
import sys
from pathlib import Path

from foulcheck import config
from foulcheck.decision.engine import DecisionEngine
from foulcheck.decision.models import make_text_model
from foulcheck.decision.schema import Ruling
from foulcheck.explain.render import explain_clip, render_video
from foulcheck.video import make_analyzer

DEFAULT_OUT = config.REPO_DIR / "explained"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m foulcheck.explain")
    ap.add_argument("clips", nargs="+", type=Path)
    ap.add_argument("--context", help="optional hint, e.g. 'this was in the penalty area'")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--rerender", action="store_true", help="reuse <name>_ruling.json instead of calling the models")
    ap.add_argument("--decision-model", help="decision model to use instead of the default (e.g. when its quota is used up)")
    ap.add_argument("--video-model", help="video model to use instead of the default (e.g. when it is overloaded)")
    args = ap.parse_args(argv)

    engine = DecisionEngine(make_text_model(model=args.decision_model)) if args.decision_model else None
    analyzer = make_analyzer(model=args.video_model) if args.video_model else None
    failures = 0
    for clip in args.clips:
        try:
            if args.rerender:
                ruling = Ruling.model_validate_json((args.out / f"{clip.stem}_ruling.json").read_text())
                video = render_video(clip, ruling, args.out / f"{clip.stem}_explained.mp4")
            else:
                ruling, video = explain_clip(clip, args.out, args.context, engine=engine, analyzer=analyzer,
                                             progress=lambda s: print(f"  {clip.name}: {s}", flush=True))
        except Exception as exc:  # keep going through a batch
            failures += 1
            print(f"{clip.name}: ERROR {exc}", file=sys.stderr)
            continue
        card = "" if ruling.card == "none" else f", {ruling.card} card"
        print(f"{clip.name}: {ruling.verdict.replace('_', ' ')}, {ruling.restart.replace('_', ' ')}{card} "
              f"({ruling.confidence.level} confidence) -> {video}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
