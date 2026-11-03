"""Model API clients. A per-request API key (from a visitor) overrides the server's .env key."""

from foulcheck import config


def gemini_client(api_key: str | None = None):
    from google import genai
    from google.genai import types

    kw = {"api_key": api_key} if api_key else {}  # without a key the SDK reads GEMINI_API_KEY from the env
    return genai.Client(http_options=types.HttpOptions(timeout=config.MODEL_TIMEOUT_S * 1000), **kw)
