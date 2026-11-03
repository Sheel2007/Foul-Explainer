from foulcheck.video.base import VideoAnalyzer


def make_analyzer(kind: str = "gemini", model: str | None = None, api_key: str | None = None, **kw) -> VideoAnalyzer:
    """Build an analyzer by name: 'gemini', 'frames-gemini' or 'frames-claude'.

    `api_key` is a Gemini key for this analyzer only (e.g. a visitor's); None uses the server's.
    """
    from foulcheck import config
    from foulcheck.clients import gemini_client
    from foulcheck.video.frames import ClaudeVision, FrameSequenceAnalyzer, GeminiVision
    from foulcheck.video.gemini import GeminiAnalyzer

    if kind == "gemini":
        return GeminiAnalyzer(model or config.GEMINI_MODEL, client=gemini_client(api_key) if api_key else None, **kw)
    if kind == "frames-gemini":
        return FrameSequenceAnalyzer(GeminiVision(model or config.GEMINI_MODEL, client=gemini_client(api_key) if api_key else None), **kw)
    if kind == "frames-claude":
        return FrameSequenceAnalyzer(ClaudeVision(model or config.CLAUDE_MODEL), **kw)
    raise ValueError(f"unknown analyzer {kind!r}")
