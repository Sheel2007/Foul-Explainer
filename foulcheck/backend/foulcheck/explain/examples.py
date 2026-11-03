"""Export the explained test clips for the website's homepage.

Renders each test clip with only its CONTACT tags (the site shows the explanation beside the video)
plus a poster frame into frontend/public/examples/, and writes frontend/data/examples.json with each
clip's facts, ruling and confidence breakdown next to its answer-key label. Needs the saved rulings in
explained/ and the raw clips in eval/clips/; makes no model calls.

Usage (from backend/): uv run python -m foulcheck.explain.examples
"""

import json
import subprocess
import sys
from pathlib import Path

from foulcheck import config
from foulcheck.decision.schema import Ruling
from foulcheck.eval.labels import load_label
from foulcheck.explain.render import render_video
from foulcheck.video import ffmpeg

EXPLAINED = config.REPO_DIR / "explained"
CLIPS = config.REPO_DIR / "eval" / "clips"
FRONTEND = config.REPO_DIR / "frontend"
STORY_ID = "2"  # the clip the homepage's scroll story and pipeline diagram walk through
STRIP_FRAMES = 8  # thumbnails in the pipeline diagram's film strip
TITLES = {
    "1": "Youth league · sliding challenge",
    "2": "England v Mexico · slide on the touchline",
    "3": "Arsenal · sliding tackle in midfield",
    "4": "Youth league · trip near the box",
    "5": "Anderlecht v Oostende · trip in the box",
}


def _frame(source: Path, at: float, out: Path, vf: str) -> str:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(source), "-frames:v", "1",
                    "-vf", vf, "-q:v", "3", str(out)], check=True)
    return f"/examples/{out.parent.name}/{out.name}" if out.parent.name != "examples" else f"/examples/{out.name}"


def story_assets(source: Path, r: Ruling, out_public: Path, stem: str) -> dict:
    """The raw clip (no tags: the page draws its own) and stills for the pipeline diagram."""
    clip = out_public / f"{stem}_story.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-an", "-c:v", "libx264", "-crf", "22",
                    "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(clip)], check=True)
    info = ffmpeg.probe(source)
    dur = info["duration"]
    o = r.observation
    at = o.contact_seconds if o and o.contact_seconds is not None else dur / 2
    strip = [{"src": _frame(source, dur * (i + 0.5) / STRIP_FRAMES, out_public / f"{stem}_strip{i}.jpg", "scale=240:-2"),
              "seconds": round(dur * (i + 0.5) / STRIP_FRAMES, 2)} for i in range(STRIP_FRAMES)]
    contact = _frame(source, at, out_public / f"{stem}_contact.jpg", "scale=640:-2")
    closeup = None
    if o and o.contact_box:
        w, h, x, y = ffmpeg.crop_box(info["width"], info["height"], o.contact_box)
        closeup = _frame(source, at, out_public / f"{stem}_closeup.jpg", f"crop={w}:{h}:{x}:{y},scale=640:-2:flags=lanczos")
    return {"video": f"/examples/{clip.name}", "duration": dur, "strip": strip, "contact": contact, "closeup": closeup}


def export(out_public: Path = FRONTEND / "public" / "examples", out_json: Path = FRONTEND / "data" / "examples.json") -> list[dict]:
    out_public.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    examples = []
    for old in out_public.glob("*_explained.mp4"):
        old.unlink()  # earlier exports shipped the video with the panel burned in
    for ruling_file in sorted(EXPLAINED.glob("*_ruling.json")):
        stem = ruling_file.name.removesuffix("_ruling.json")
        source = CLIPS / f"{stem}.mp4"
        if not source.exists():
            continue
        r = Ruling.model_validate_json(ruling_file.read_text())
        video = render_video(source, r, out_public / f"{stem}_clip.mp4", panel=False, audio=False)
        poster = out_public / f"{stem}_poster.jpg"
        at = r.observation.contact_seconds if r.observation and r.observation.contact_seconds else 0
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(source), "-frames:v", "1",
                        "-vf", "scale=640:360:force_original_aspect_ratio=increase,crop=640:360", "-q:v", "3", str(poster)], check=True)
        label = load_label(f"{stem}.mp4")
        o = r.observation
        locate = r.video.locate if r.video else None
        chosen = locate.chosen_view() if locate else None
        story = story_assets(source, r, out_public, stem) if stem == STORY_ID else None
        examples.append({
            "id": stem,
            "title": TITLES.get(stem, f"Clip {stem}"),
            "video": f"/examples/{video.name}",
            "poster": f"/examples/{poster.name}",
            "ai": {
                "verdict": r.verdict, "restart": r.restart, "card": r.card, "offence_type": r.offence_type,
                "confidence": r.confidence.level, "explanation": r.explanation, "key_moment": r.key_moment,
                "confidence_detail": {"model_score": r.confidence.model_score, "score": r.confidence.score,
                                      "adjustments": r.confidence.adjustments},
                "gray_areas": r.gray_areas,
                "uncertain_fields": o.uncertain_fields if o else [],
                "citations": [{"section": c.section, "title": c.title, "quote": c.quote, "highlight": c.highlight,
                               "source_url": c.source_url, "kind": c.kind} for c in r.citations],
            },
            "facts": {
                "challenge_type": o.challenge_type, "body_part_used": o.contact.body_part_used,
                "body_part_hit": o.contact.body_part_hit, "ball_played_first": o.ball_played_first,
                "speed_and_force": o.speed_and_force, "location": o.location, "boot_detail": o.boot_detail,
                "studs_showing": o.challenge.studs_showing, "leg_straight": o.challenge.leg_straight,
                "lunge": o.challenge.lunge, "follow_through": o.challenge.follow_through,
            } if o else None,
            "story": story,
            "moment": {
                "contact_seconds": o.contact_seconds if o else None,
                "contact_box": o.contact_box if o else None,
                "views": [{"seconds": v.contact_seconds, "kind": v.kind, "slow_motion": v.slow_motion,
                           "camera": v.camera, "clarity": v.clarity, "chosen": v is chosen}
                          for v in (locate.views if locate else [])],
                "closeup": r.video.closeup is not None if r.video else False,
                "audit": r.audit,
            },
            "label": {"verdict": label.verdict, "restart": label.restart, "card": label.card} if label.has_ruling else None,
        })
    out_json.write_text(json.dumps(examples, indent=2) + "\n")
    (out_public / "bg-loop.mp4").unlink(missing_ok=True)  # the old hero background, no longer used
    return examples


if __name__ == "__main__":
    rows = export()
    for e in rows:
        lab = e["label"] or {}
        print(f"{e['id']}: AI {e['ai']['verdict']}/{e['ai']['restart']}/{e['ai']['card']}  "
              f"label {lab.get('verdict')}/{lab.get('restart')}/{lab.get('card')}")
    print(f"Exported {len(rows)} examples", file=sys.stderr)
