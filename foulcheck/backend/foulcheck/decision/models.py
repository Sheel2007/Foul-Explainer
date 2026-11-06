"""Text-only model backends for the decision step. They return raw JSON text."""

import json
import threading
from typing import Protocol, TypeVar

from pydantic import BaseModel

from foulcheck import config, llm
from foulcheck.clients import anthropic_client, gemini_client, openai_client

M = TypeVar("M", bound=BaseModel)


class TextModel(Protocol):
    name: str

    def generate(self, system: str, prompt: str, schema: type[M], sample: int = 0) -> str:
        """`sample` picks one of a few sampling settings so two runs are independent."""
        ...


class GeminiText:
    TEMPERATURES = (0.4, 1.0)

    def __init__(self, model: str | None = None, client=None):
        self.model = model or config.GEMINI_MODEL
        self.name = f"gemini-{self.model}"
        self._client = client
        self._lock = threading.Lock()  # the engine calls generate from two threads at once

    def generate(self, system: str, prompt: str, schema: type[M], sample: int = 0) -> str:
        from google import genai
        from google.genai import types

        with self._lock:
            if self._client is None:
                self._client = gemini_client()
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
                temperature=self.TEMPERATURES[sample % len(self.TEMPERATURES)],
            ),
        )
        return resp.text


class ClaudeText:
    """Claude no longer accepts temperature, so the two runs differ only by sampling."""

    def __init__(self, model: str | None = None, client=None):
        self.model = model or config.CLAUDE_MODEL
        self.name = self.model
        self._client = client
        self._lock = threading.Lock()

    def generate(self, system: str, prompt: str, schema: type[M], sample: int = 0) -> str:
        with self._lock:
            if self._client is None:
                self._client = anthropic_client()
        resp = self._client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"},
        )
        if resp.stop_reason == "refusal":
            raise llm.ModelCallError(f"{self.model} declined the request")
        return resp.parsed_output.model_dump_json()


class OpenAIText:
    """Asks for JSON and leaves checking it to llm.generate_json. The two runs differ only by sampling."""

    def __init__(self, model: str | None = None, client=None):
        self.model = model or config.OPENAI_MODEL
        self.name = self.model
        self._client = client
        self._lock = threading.Lock()

    def generate(self, system: str, prompt: str, schema: type[M], sample: int = 0) -> str:
        with self._lock:
            if self._client is None:
                self._client = openai_client()
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": f"{system}\n\nReply with JSON matching this schema:\n{json.dumps(schema.model_json_schema())}"},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content


def make_text_model(provider: str | None = None, model: str | None = None, api_key: str | None = None) -> TextModel:
    """`api_key` is that provider's key for this model only (e.g. a visitor's); None uses the server's."""
    provider = provider or config.DECISION_PROVIDER
    if provider == config.DECISION_PROVIDER:
        model = model or config.DECISION_MODEL  # DECISION_MODEL belongs to the configured provider only
    if provider == "gemini":
        return GeminiText(model or "gemini-3.6-flash", client=gemini_client(api_key) if api_key else None)
    if provider == "claude":
        return ClaudeText(model, client=anthropic_client(api_key) if api_key else None)
    if provider == "openai":
        return OpenAIText(model, client=openai_client(api_key) if api_key else None)
    raise ValueError(f"unknown decision provider {provider!r}")
