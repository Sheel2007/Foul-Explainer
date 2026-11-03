"""Eval harness: run every labelled clip through one or more configurations and score them.

Usage:
  uv run python -m foulcheck.eval                                   # default config, all clips
  uv run python -m foulcheck.eval --video model=gemini-3.5-flash-lite,i=6 --video model=gemini-3.8-flash
  uv run python -m foulcheck.eval --decision none                   # video-only (no decision calls)

--video takes comma-separated key=value pairs: kind (gemini|frames-gemini|frames-claude), model,
l (locate fps), i (inspect fps), think (minimal|low|medium|high). Video outputs are cached by
file hash and settings, so decision-prompt changes can be re-tested without new video calls.
Writes eval/results/<date>-<time>.csv and a matching .md summary.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

from foulcheck import config
from foulcheck.decision.engine import DecisionEngine
from foulcheck.decision.models import make_text_model
from foulcheck.eval.labels import load_label
from foulcheck.eval.metrics import row_for, summarize
from foulcheck.laws.retrieve import default_retriever
from foulcheck.video import VideoAnalyzer, make_analyzer
from foulcheck.video.__main__ import VIDEO_EXT

RESULTS_DIR = config.REPO_DIR / "eval" / "results"


def parse_video_spec(spec: str) -> tuple[str, VideoAnalyzer]:
    opts = dict(part.split("=", 1) for part in spec.split(",") if part)
    unknown = set(opts) - {"kind", "model", "l", "i", "think"}
    if unknown:
        raise SystemExit(f"unknown --video keys: {sorted(unknown)}")
    kw = {}
    if "l" in opts:
        kw["locate_fps"] = float(opts["l"])
    if "i" in opts:
        kw["inspect_fps"] = float(opts["i"])
    if "think" in opts:
        kw["thinking"] = opts["think"]
    analyzer = make_analyzer(opts.get("kind", "gemini"), opts.get("model"), **kw)
    return analyzer.cache_id, analyzer


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m foulcheck.eval")
    ap.add_argument("--video", action="append", default=[], help="video config; repeat to compare")
    ap.add_argument("--decision", default=config.DECISION_MODEL or "", help="decision model, or 'none'")
    ap.add_argument("--decision-provider", default=config.DECISION_PROVIDER)
    ap.add_argument("--no-second-opinion", action="store_true", help="one decision run per clip (halves calls)")
    ap.add_argument("--clips", nargs="*", type=Path)
    ap.add_argument("--no-cache", action="store_true", help="re-run video passes even if cached")
    args = ap.parse_args(argv)

    clips = args.clips or sorted(p for p in (config.REPO_DIR / "eval" / "clips").iterdir()
                                 if p.suffix.lower() in VIDEO_EXT)
    configs = [parse_video_spec(s) for s in (args.video or [""])]
    engine = None if args.decision == "none" else DecisionEngine(
        make_text_model(args.decision_provider, args.decision or None), second_opinion=not args.no_second_opinion)
    retriever = default_retriever() if engine else None

    rows: list[dict] = []
    for name, analyzer in configs:
        label_name = name + (f" + {engine.model.name}" if engine else " (video only)")
        for clip in clips:
            label = load_label(clip.name)
            video = ruling = video_error = decision_error = None
            # Failures are recorded and the run keeps going: a failed clip is a result too.
            try:
                video = analyzer.analyze(clip, use_cache=not args.no_cache)
            except Exception as exc:
                video_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            if engine and video is not None and video.observation is not None:
                try:
                    ruling = engine.decide(video.observation, retriever.retrieve(video.observation), None, video)
                except Exception as exc:
                    decision_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            row = row_for(label_name, clip.name, label, video, ruling, video_error, decision_error)
            rows.append(row)
            print(f"[{label_name}] {clip.name}: contact={row.get('contact_time', '-')} "
                  f"verdict={row.get('verdict', '-')} card={row.get('card', '-')} conf={row.get('confidence', '-')} "
                  f"total_s={row.get('total_s', '-')}"
                  + (f" VIDEO ERROR {video_error[:80]}" if video_error else "")
                  + (f" DECISION ERROR {decision_error[:80]}" if decision_error else ""), flush=True)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    csv_path = RESULTS_DIR / f"{stamp}.csv"
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    md_path = csv_path.with_suffix(".md")
    md_path.write_text(report(rows, stamp))
    print(f"\nWrote {csv_path}\nWrote {md_path}\n")
    print(md_path.read_text())
    return 0


def report(rows: list[dict], stamp: str) -> str:
    lines = [f"# Eval run {stamp}", ""]
    for name in dict.fromkeys(r["config"] for r in rows):
        sub = [r for r in rows if r["config"] == name]
        lines += [f"## {name}", "", "| Metric | Value | n | v1 target | Status | Note |", "|---|---|---|---|---|---|"]
        lines += [f"| {m.name} | {m.value} | {m.n} | {m.target} | {m.status} | {m.note} |" for m in summarize(sub)]
        cols = ["clip", "view_used", "contact_time", "contact_err_s", "verdict", "restart", "card", "confidence",
                "cited_sections", "guard_errors", "second_opinion", "locate_s", "inspect_s", "decision_s", "video_error",
                "decision_error"]
        cols = [c for c in cols if any(c in r for r in sub)]
        lines += ["", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        lines += ["| " + " | ".join(str(r.get(c, ""))[:60] for c in cols) + " |" for r in sub]
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
