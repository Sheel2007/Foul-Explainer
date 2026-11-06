from foulcheck.video.base import VideoAnalyzer


def make_analyzer(kind: str = "gemini", model: str | None = None, api_key: str | None = None, **kw) -> VideoAnalyzer:
    """Build an analyzer by name: 'gemini', 'frames-gemini', 'frames-claude' or 'frames-openai'.

    `api_key` is that provider's key for this analyzer only (e.g. a visitor's); None uses the server's.
    """
    from foulcheck import config
    from foulcheck.clients import anthropic_client, gemini_client, openai_client
    from foulcheck.video.frames import ClaudeVision, FrameSequenceAnalyzer, GeminiVision, OpenAIVision
    from foulcheck.video.gemini import GeminiAnalyzer

    if kind == "gemini":
        return GeminiAnalyzer(model or config.GEMINI_MODEL, client=gemini_client(api_key) if api_key else None, **kw)
    if kind == "frames-gemini":
        return FrameSequenceAnalyzer(GeminiVision(model or config.GEMINI_MODEL, client=gemini_client(api_key) if api_key else None), **kw)
    if kind == "frames-claude":
        return FrameSequenceAnalyzer(ClaudeVision(model or config.CLAUDE_MODEL, client=anthropic_client(api_key) if api_key else None), **kw)
    if kind == "frames-openai":
        return FrameSequenceAnalyzer(OpenAIVision(model or config.OPENAI_MODEL, client=openai_client(api_key) if api_key else None), **kw)
    raise ValueError(f"unknown analyzer {kind!r}")
