"""Slow integration test: real Gemini call on a real clip. Run with: uv run pytest -m slow"""

import os

import pytest

from foulcheck import config
from foulcheck.video.gemini import GeminiAnalyzer

CLIP = config.REPO_DIR / "eval" / "clips" / "2.mp4"


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY") or not CLIP.exists(), reason="needs GEMINI_API_KEY and a clip")
def test_gemini_real_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    res = GeminiAnalyzer().analyze(CLIP)
    assert res.locate.incident_found and res.observation is not None
    start, end = res.window
    assert start - 0.3 <= res.observation.contact_seconds <= end + 0.3
