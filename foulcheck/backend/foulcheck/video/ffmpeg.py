"""Thin wrappers over ffprobe/ffmpeg for durations, hashes, and frame extraction."""

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"duration": float(data["format"]["duration"]),
            "width": video.get("width"), "height": video.get("height")}


def extract_frames(path: Path, start: float, end: float, fps: float, width: int = 768) -> list[tuple[float, bytes]]:
    """JPEG frames between start and end at `fps`, each with its time on the original timeline."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(path),
             "-vf", f"fps={fps},scale={width}:-2", "-q:v", "3", f"{tmp}/%05d.jpg"],
            check=True,
        )
        files = sorted(Path(tmp).glob("*.jpg"))
        return [(start + i / fps, f.read_bytes()) for i, f in enumerate(files)]


def crop_box(width: int, height: int, box: list[float], grow: float = 1.8, min_frac: float = 0.35) -> tuple[int, int, int, int]:
    """Pixel crop (w, h, x, y) around a 0-1000 box, grown for context and kept 16:9 inside the frame."""
    ymin, xmin, ymax, xmax = (v / 1000 for v in box)
    cx, cy = (xmin + xmax) / 2 * width, (ymin + ymax) / 2 * height
    w = max((xmax - xmin) * width * grow, (ymax - ymin) * height * grow * 16 / 9, width * min_frac)
    w = min(w, width)
    h = min(w * 9 / 16, height)
    w = h * 16 / 9
    x = min(max(cx - w / 2, 0), width - w)
    y = min(max(cy - h / 2, 0), height - h)
    even = lambda v: int(v) // 2 * 2  # noqa: E731
    return even(w), even(h), even(x), even(y)


def crop_clip(path: Path, start: float, end: float, box: list[float], out: Path, out_width: int = 1280) -> Path:
    """Cut [start, end] and enlarge the region around `box` (for a close-up look at the contact)."""
    info = probe(path)
    w, h, x, y = crop_box(info["width"], info["height"], box)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(path),
         "-vf", f"crop={w}:{h}:{x}:{y},scale={out_width}:-2:flags=lanczos", "-an",
         "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )
    return out
