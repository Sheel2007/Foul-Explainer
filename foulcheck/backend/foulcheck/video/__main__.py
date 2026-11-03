"""Run the video step on clips and print observations.

Usage: uv run python -m foulcheck.video [CLIP ...] [--analyzer gemini|frames-gemini|frames-claude]
With no clips, runs every video in eval/clips/.
"""

import argparse
import sys
from pathlib import Path

from foulcheck import config
from foulcheck.video import make_analyzer

VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m foulcheck.video")
    ap.add_argument("clips", nargs="*", type=Path)
    ap.add_argument("--analyzer", default="gemini")
    ap.add_argument("--model")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--json", action="store_true", help="print full JSON for each clip")
    args = ap.parse_args(argv)

    clips = args.clips or sorted(p for p in (config.REPO_DIR / "eval" / "clips").iterdir()
                                 if p.suffix.lower() in VIDEO_EXT)
    analyzer = make_analyzer(args.analyzer, args.model)
    failures = 0
    for clip in clips:
        try:
            res = analyzer.analyze(clip, use_cache=not args.no_cache)
        except Exception as exc:  # report and keep going through the batch
            failures += 1
            print(f"{clip.name}: ERROR {exc}", file=sys.stderr)
            continue
        if args.json:
            print(res.model_dump_json(indent=2))
            continue
        obs, loc = res.observation, res.locate
        views = ", ".join(f"{v.kind}{'(slow)' if v.slow_motion else ''}@{v.contact_time}/{v.clarity}"
                          for v in loc.views)
        print(f"\n== {clip.name} ({res.duration_s:.1f}s) via {res.analyzer}")
        print(f"   incident: {loc.incident}")
        print(f"   views: {views or '-'}  best={loc.best_view}  window={res.window}")
        if obs:
            print(f"   contact_time={obs.contact_time} challenge={obs.challenge_type} "
                  f"contact={obs.contact.made} {obs.contact.body_part_used}->{obs.contact.body_part_hit} "
                  f"ball_first={obs.ball_played_first} force={obs.speed_and_force} "
                  f"handball={obs.handball.touched} location={obs.location}")
            print(f"   uncertain={obs.uncertain_fields}")
            print(f"   summary: {obs.summary}")
        for n in res.notes:
            print(f"   note: {n}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
