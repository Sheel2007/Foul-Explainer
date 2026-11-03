"""End to end: clip -> video observations -> retrieved Laws -> cited ruling."""

from collections.abc import Callable
from pathlib import Path

from foulcheck.config import laws_config
from foulcheck.decision.engine import DecisionEngine
from foulcheck.decision.schema import Confidence, Ruling
from foulcheck.laws.retrieve import Retriever, default_retriever
from foulcheck.video import VideoAnalyzer, make_analyzer

# Progress stages reported to the UI, in order.
STAGES = {"locate": "Finding the key moment", "inspect": "Looking closely", "rules": "Checking the Laws",
          "render": "Making the explained video"}


def analyze_clip(path: Path | str, context: str | None = None, *, analyzer: VideoAnalyzer | None = None,
                 engine: DecisionEngine | None = None, retriever: Retriever | None = None,
                 use_cache: bool = True, progress: Callable[[str], None] | None = None) -> Ruling:
    analyzer = analyzer or make_analyzer()
    video = analyzer.analyze(path, use_cache=use_cache, progress=progress)
    if video.observation is None:
        cfg = laws_config()
        return Ruling(
            verdict="cannot_determine", offence_type=None, restart="unknown", card="none",
            confidence=Confidence(model_score=0, score=0, level="Low", adjustments=["no incident found"]),
            explanation="The video model could not find a challenge or a ball-to-arm contact in this clip, "
                        "so there is nothing to judge. Try a shorter clip centred on the incident.",
            citations=[], gray_areas=[], key_moment=None, edition=cfg.edition, edition_label=cfg.label,
            context_hint=context or None, video=video, notes=list(video.notes),
        )
    if progress:
        progress("rules")
    chunks = (retriever or default_retriever()).retrieve(video.observation, context)
    ruling = (engine or DecisionEngine()).decide(video.observation, chunks, context, video)
    ruling.notes = list(video.notes) + ruling.notes
    return ruling
