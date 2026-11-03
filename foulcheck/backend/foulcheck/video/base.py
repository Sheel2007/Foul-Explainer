"""VideoAnalyzer: the two-pass flow shared by every video backend.

Locate pass: whole clip, low fps -> when the contact happens, in which views, who is involved.
Inspect pass: ~1.5 s either side of the best view's contact, high fps -> structured observation.
Outputs are cached by file hash so re-runs (and the eval harness) don't pay twice.
"""

import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from foulcheck import config
from foulcheck.video import ffmpeg
from foulcheck.video.prompts import CLOSEUP_VERSION, INSPECT_VERSION, LOCATE_VERSION
from foulcheck.video.schema import CloseUp, LocateResult, Observation, VideoAnalysis, View, fmt_ts

VERDICT_WORDS = re.compile(
    r"\b(fouls?|fouled|fouling|reckless(ly)?|careless(ly)?|excessive force|offen[cs]es?|illegal(ly)?|"
    r"yellow card|red card|booked|booking|sent off|sending[- ]off|cautioned|free kick|penalty kick|"
    r"simulation|violent conduct|serious foul play|dogso)\b",
    re.IGNORECASE,
)


def verdict_words(model: Observation | LocateResult) -> list[str]:
    """Rule words in free-text fields. The video step must not make rulings."""
    found: list[str] = []

    def walk(v):
        if isinstance(v, str):
            found.extend(m.group(0) for m in VERDICT_WORDS.finditer(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(model.model_dump())
    return found


def check_neutral(model: Observation | LocateResult) -> None:
    words = verdict_words(model)
    if words:
        raise ValueError(f"uses ruling words {sorted(set(w.lower() for w in words))}; describe facts only")


class VideoAnalyzer(ABC):
    name: str = "base"
    supports_closeup = False  # analyzers that can look again at an enlarged crop of the contact
    CLOSEUP_HALF_WINDOW = 0.6

    def __init__(self, locate_fps: float = config.LOCATE_FPS, inspect_fps: float = config.INSPECT_FPS,
                 half_window: float = config.INSPECT_HALF_WINDOW):
        self.locate_fps = locate_fps
        self.inspect_fps = inspect_fps
        self.half_window = half_window

    @property
    def cache_id(self) -> str:
        return f"{self.name}-l{self.locate_fps}-i{self.inspect_fps}-w{self.half_window}"

    @abstractmethod
    def locate(self, path: Path, duration: float) -> LocateResult: ...

    @abstractmethod
    def inspect(self, path: Path, locate: LocateResult, view: View, start: float, end: float) -> Observation: ...

    def closeup(self, path: Path, obs: Observation, start: float, end: float) -> CloseUp:
        raise NotImplementedError

    @staticmethod
    def _cached(key: Path, use_cache: bool, schema, produce) -> tuple[object, float | None, bool]:
        """Returns (result, seconds the model call took, served from cache)."""
        meta = key.with_suffix(".meta.json")
        if use_cache and key.exists():
            seconds = json.loads(meta.read_text()).get("seconds") if meta.exists() else None
            return schema.model_validate_json(key.read_text()), seconds, True
        start = time.monotonic()
        result = produce()
        seconds = round(time.monotonic() - start, 2)
        key.parent.mkdir(parents=True, exist_ok=True)
        key.write_text(result.model_dump_json(indent=2))
        meta.write_text(json.dumps({"seconds": seconds, "at": time.time()}))
        return result, seconds, False

    def analyze(self, path: Path | str, use_cache: bool = True,
                progress: Callable[[str], None] | None = None) -> VideoAnalysis:
        report = progress or (lambda stage: None)
        path = Path(path)
        digest = ffmpeg.sha256(path)
        duration = ffmpeg.probe(path)["duration"]
        # Locate and inspect are keyed separately so changing inspect settings reuses the locate pass.
        cache = config.CACHE_DIR / "video" / digest[:16] / self.name

        report("locate")
        loc, loc_s, loc_hit = self._cached(cache / f"locate-{LOCATE_VERSION}-l{self.locate_fps}.json", use_cache,
                                           LocateResult, lambda: self.locate(path, duration))
        view = loc.chosen_view()
        result = VideoAnalysis(clip=path.name, sha256=digest, duration_s=duration, analyzer=self.cache_id,
                               locate=loc, timings={"locate_s": loc_s, "locate_cached": loc_hit})
        if not loc.incident_found or view is None:
            result.notes.append("No incident found in the clip.")
            return result

        t = min(max(view.contact_seconds, 0.0), duration)
        start, end = max(0.0, t - self.half_window), min(duration, t + self.half_window)
        result.window = (round(start, 2), round(end, 2))
        report("inspect")
        key = cache / f"inspect-{INSPECT_VERSION}-l{self.locate_fps}-i{self.inspect_fps}-{start:.2f}-{end:.2f}.json"
        obs, ins_s, ins_hit = self._cached(key, use_cache, Observation, lambda: self.inspect(path, loc, view, start, end))
        result.timings |= {"inspect_s": ins_s, "inspect_cached": ins_hit}
        obs = self._fix_contact_time(obs, start, end, view, result.notes)
        if self.supports_closeup and obs.contact_box and obs.contact_seconds is not None:
            c = obs.contact_seconds
            cs, ce = max(0.0, c - self.CLOSEUP_HALF_WINDOW), min(duration, c + self.CLOSEUP_HALF_WINDOW)
            box = "-".join(f"{v:.0f}" for v in obs.contact_box)
            ckey = cache / f"closeup-{CLOSEUP_VERSION}-{INSPECT_VERSION}-i{self.inspect_fps}-{cs:.2f}-{ce:.2f}-{box}.json"
            try:
                close, cl_s, cl_hit = self._cached(ckey, use_cache, CloseUp, lambda: self.closeup(path, obs, cs, ce))
                result.closeup = close
                result.timings |= {"closeup_s": cl_s, "closeup_cached": cl_hit}
                obs = merge_closeup(obs, close)
                result.notes.append("Boot details come from a close-up of the contact.")
            except Exception as exc:  # the close-up is an extra look; the wide-shot answers still stand
                result.notes.append(f"Close-up unavailable ({type(exc).__name__}); boot details are from the wide shot.")
        result.observation = obs
        return result

    @staticmethod
    def _fix_contact_time(obs: Observation, start: float, end: float, view: View, notes: list[str]) -> Observation:
        """Keep contact_time on the original timeline and inside the inspected window."""
        t = obs.contact_seconds
        slack = 0.3
        if t is not None and start - slack <= t <= end + slack:
            return obs
        if t is not None and t <= (end - start) + slack:
            # The model counted from the start of the window rather than the video.
            obs.contact_time = fmt_ts(start + t)
            notes.append("contact_time was relative to the inspect window; shifted onto the video timeline.")
            return obs
        notes.append(f"contact_time {obs.contact_time} fell outside the window; used the locate pass time.")
        obs.contact_time = view.contact_time
        if "contact_time" not in obs.uncertain_fields:
            obs.uncertain_fields.append("contact_time")
        return obs


def merge_closeup(obs: Observation, close: CloseUp) -> Observation:
    """The close-up has far more pixels on the boot, so its answers replace the wide-shot ones it gives."""
    merged = obs.model_copy(deep=True)
    for field in ("studs_showing", "leg_straight", "lunge", "follow_through"):
        value = getattr(close.challenge, field)
        if value is not None:
            setattr(merged.challenge, field, value)
    if close.body_part_used:
        merged.contact.body_part_used = close.body_part_used
    if close.body_part_hit:
        merged.contact.body_part_hit = close.body_part_hit
    if close.boot_detail:
        merged.boot_detail = close.boot_detail
    resolved = {"challenge." + f for f in ("studs_showing", "leg_straight", "lunge", "follow_through")
                if getattr(close.challenge, f) is not None}
    merged.uncertain_fields = [f for f in merged.uncertain_fields if f not in resolved]
    merged.uncertain_fields += [f for f in close.uncertain_fields if f not in merged.uncertain_fields]
    return merged
