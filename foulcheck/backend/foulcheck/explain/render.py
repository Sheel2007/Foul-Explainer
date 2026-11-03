"""Compose the explained video: the original clip with the explanation panel beside it.

The panel sits to the right of the video so it never covers play. A red CONTACT tag appears on the
video, top left, each time the contact is shown (live and in every replay).
"""

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from foulcheck.decision.schema import Ruling
from foulcheck.explain.panel import draw_contact_tag, draw_panel
from foulcheck.video import ffmpeg
from foulcheck.video.schema import parse_ts

OUTPUT_HEIGHT = 720
PANEL_WIDTH = 640
CONTACT_BEFORE_S = 0.25
CONTACT_AFTER_S = 1.6  # long enough to read the tag
TAG_MARGIN = 28


def contact_moments(r: Ruling) -> list[tuple[float, str | None]]:
    """Every moment the contact is on screen, with a label for the banner. Uses each view from the
    locate pass, with the chosen view replaced by the more precise inspect-pass time."""
    if r.video and r.video.locate.views:
        chosen = r.video.locate.chosen_view()
        moments = []
        for v in r.video.locate.views:
            t = v.contact_seconds
            if v is chosen and r.observation and r.observation.contact_seconds is not None:
                t = r.observation.contact_seconds
            label = ("replay" if v.kind == "replay" else "live") + (" (slow motion)" if v.slow_motion else "")
            moments.append((t, label))
        return sorted(moments)
    return [(parse_ts(r.key_moment), None)] if r.key_moment else []


def render_video(clip: Path | str, ruling: Ruling, out: Path | str, panel: bool = True, audio: bool = True) -> Path:
    """With panel=False only the CONTACT tags are drawn (the website shows the explanation beside the video).
    audio=False drops the sound track (everything the website serves is silent)."""
    clip, out = Path(clip), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = ffmpeg.probe(clip)["duration"]
    moments = contact_moments(ruling)
    with tempfile.TemporaryDirectory() as tmp:
        inputs = ["-i", str(clip)]
        if panel:
            panel_png = Path(tmp) / "panel.png"
            draw_panel(ruling, PANEL_WIDTH, OUTPUT_HEIGHT).save(panel_png)
            inputs += ["-loop", "1", "-i", str(panel_png)]
            graph = [f"[0:v]scale=-2:{OUTPUT_HEIGHT},setsar=1[v]", "[v][1:v]hstack=inputs=2[s0]"]
        else:
            graph = [f"[0:v]scale=-2:{OUTPUT_HEIGHT},setsar=1[s0]"]
        first_tag = 2 if panel else 1  # input index of the first tag image
        for i, (t, label) in enumerate(moments):
            tag = Path(tmp) / f"tag{i}.png"
            draw_contact_tag(label).save(tag)
            inputs += ["-loop", "1", "-i", str(tag)]
            window = f"between(t,{max(0.0, t - CONTACT_BEFORE_S):.2f},{t + CONTACT_AFTER_S:.2f})"
            graph.append(f"[s{i}][{first_tag + i}:v]overlay=x={TAG_MARGIN}:y={TAG_MARGIN}:enable='{window}'[s{i + 1}]")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph),
             "-map", f"[s{len(moments)}]", *(["-map", "0:a?"] if audio else ["-an"]), "-t", f"{duration:.3f}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-movflags", "+faststart", str(out)],
            check=True,
        )
    return out


def explain_clip(clip: Path | str, out_dir: Path | str, context: str | None = None,
                 progress: Callable[[str], None] | None = None, **pipeline_kw) -> tuple[Ruling, Path]:
    """Upload-to-video in one call: judge the clip, then write <stem>_explained.mp4 and <stem>_ruling.json."""
    from foulcheck.pipeline import analyze_clip

    clip, out_dir = Path(clip), Path(out_dir)
    ruling = analyze_clip(clip, context, progress=progress, **pipeline_kw)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{clip.stem}_ruling.json").write_text(ruling.model_dump_json(indent=2))
    if progress:
        progress("render")
    return ruling, render_video(clip, ruling, out_dir / f"{clip.stem}_explained.mp4")
