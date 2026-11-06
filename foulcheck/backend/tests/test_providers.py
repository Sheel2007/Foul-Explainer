import json
from types import SimpleNamespace

import pytest

from foulcheck.api.jobs import friendly_error
from foulcheck.decision.models import ClaudeText, GeminiText, OpenAIText, make_text_model
from foulcheck.providers import detect_provider, models_for_key
from foulcheck.video.frames import ClaudeVision, FrameSequenceAnalyzer, GeminiVision, OpenAIVision
from foulcheck.video.gemini import GeminiAnalyzer
from foulcheck.video.schema import Observation


@pytest.mark.parametrize("key,provider", [
    ("AIzaSyExample0123456789", "gemini"),
    ("sk-ant-api03-example0123456789", "claude"),
    ("sk-proj-example0123456789", "openai"),
    ("sk-example0123456789", "openai"),
    ("gsk_unknown0123456789", None),
])
def test_detect_provider(key, provider):
    assert detect_provider(key) == provider


def test_each_key_gets_both_steps_on_its_own_provider():
    analyzer, text = models_for_key("AIzaSyExample0123456789")
    assert isinstance(analyzer, GeminiAnalyzer) and isinstance(text, GeminiText)
    analyzer, text = models_for_key("sk-ant-api03-example0123456789")
    assert isinstance(analyzer.backend, ClaudeVision) and isinstance(text, ClaudeText)
    assert analyzer.backend._client.api_key == text._client.api_key == "sk-ant-api03-example0123456789"
    analyzer, text = models_for_key("sk-proj-example0123456789")
    assert isinstance(analyzer.backend, OpenAIVision) and isinstance(text, OpenAIText)
    assert analyzer.backend._client.api_key == text._client.api_key == "sk-proj-example0123456789"
    assert text.model.startswith("gpt")  # not the Gemini decision model


def test_unknown_key_is_refused():
    with pytest.raises(ValueError):
        models_for_key("gsk_unknown0123456789")


class FakeChat:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])


def test_openai_vision_sends_frames_and_asks_for_the_schema():
    fake = FakeChat()
    assert OpenAIVision("m", client=fake).generate([(1.0, b"jpg")], "look", Observation) == "{}"
    call = fake.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    parts = call["messages"][0]["content"]
    assert any(p["type"] == "image_url" and p["image_url"]["url"].startswith("data:image/jpeg;base64,") for p in parts)
    assert "contact_box" in parts[-1]["text"]


def test_openai_text_puts_the_schema_in_the_system_message():
    fake = FakeChat()
    assert make_text_model("openai", "m", None).name == "m"
    assert OpenAIText("m", client=fake).generate("rules", "facts", Observation) == "{}"
    system = fake.calls[0]["messages"][0]
    assert system["role"] == "system" and "rules" in system["content"] and "contact_box" in system["content"]


def test_frame_analyzers_also_get_the_close_up():
    assert FrameSequenceAnalyzer(OpenAIVision("m", client=FakeChat())).supports_closeup
    assert FrameSequenceAnalyzer(GeminiVision("m", client=object())).name == "frames-gemini-m"


@pytest.mark.parametrize("text,expected", [
    ("Error code: 401 - {'type': 'authentication_error', 'message': 'invalid x-api-key'}", "rejected"),
    ("Error code: 401 - {'error': {'code': 'invalid_api_key'}}", "rejected"),
    ("API key not valid. API_KEY_INVALID", "rejected"),
    ("Error code: 429 - {'error': {'code': 'insufficient_quota'}}", "no credit"),
    ("Your credit balance is too low", "no credit"),
    ("Error code: 404 - {'error': {'code': 'model_not_found'}}", "can't use the model"),
    ("Error code: 529 - {'type': 'overloaded_error'}", "overloaded"),
])
def test_provider_errors_read_plainly(text, expected):
    assert expected in friendly_error(RuntimeError(text))
    assert json.dumps(friendly_error(RuntimeError(text)))
