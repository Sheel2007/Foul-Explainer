"""Which company a visitor's API key belongs to, and the models to use with it."""

from foulcheck.decision.models import TextModel, make_text_model
from foulcheck.video import VideoAnalyzer, make_analyzer

# Longest prefix first: Anthropic and OpenAI keys both start with "sk-".
PREFIXES = (("sk-ant-", "claude"), ("AIza", "gemini"), ("sk-", "openai"))
ANALYZERS = {"gemini": "gemini", "claude": "frames-claude", "openai": "frames-openai"}


def detect_provider(api_key: str) -> str | None:
    return next((provider for prefix, provider in PREFIXES if api_key.startswith(prefix)), None)


def models_for_key(api_key: str) -> tuple[VideoAnalyzer, TextModel]:
    """Both pipeline steps on the key's provider, with clients for this key only."""
    provider = detect_provider(api_key)
    if provider is None:
        raise ValueError("unrecognised API key")
    return make_analyzer(ANALYZERS[provider], api_key=api_key), make_text_model(provider, api_key=api_key)
