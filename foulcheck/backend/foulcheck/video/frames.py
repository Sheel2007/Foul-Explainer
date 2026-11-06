"""Model-agnostic fallback: ffmpeg pulls frames, any vision model reads them as an image sequence."""

import base64
import json
import tempfile
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from foulcheck import config, llm
from foulcheck.clients import anthropic_client, gemini_client, openai_client
from foulcheck.video import ffmpeg, prompts
from foulcheck.video.base import VideoAnalyzer, check_neutral
from foulcheck.video.schema import CloseUp, LocateResult, Observation, View, fmt_ts

M = TypeVar("M", bound=BaseModel)
Frames = list[tuple[float, bytes]]

FRAMES_INTRO = ("The video is given as a sequence of still frames. Each frame is preceded by its "
                "timestamp on the original video timeline.")


class VisionBackend(Protocol):
    name: str

    def generate(self, frames: Frames, prompt: str, schema: type[M]) -> str: ...


class GeminiVision:
    def __init__(self, model: str = config.GEMINI_MODEL, client=None):
        self.model = model
        self.name = f"gemini-{model}"
        self._client = client

    def generate(self, frames: Frames, prompt: str, schema: type[M]) -> str:
        from google import genai
        from google.genai import types

        if self._client is None:
            self._client = gemini_client()
        parts = [types.Part(text=FRAMES_INTRO)]
        for t, jpg in frames:
            parts += [types.Part(text=f"[{fmt_ts(t)}]"), types.Part.from_bytes(data=jpg, mime_type="image/jpeg")]
        parts.append(types.Part(text=prompt))
        resp = self._client.models.generate_content(
            model=self.model,
            contents=types.Content(role="user", parts=parts),
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               response_json_schema=schema.model_json_schema()),
        )
        return resp.text


class ClaudeVision:
    def __init__(self, model: str = config.CLAUDE_MODEL, client=None):
        self.model = model
        self.name = model
        self._client = client

    def generate(self, frames: Frames, prompt: str, schema: type[M]) -> str:
        import anthropic

        if self._client is None:
            self._client = anthropic_client()
        content: list[dict] = [{"type": "text", "text": FRAMES_INTRO}]
        for t, jpg in frames:
            content += [
                {"type": "text", "text": f"[{fmt_ts(t)}]"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": base64.standard_b64encode(jpg).decode()}},
            ]
        content.append({"type": "text", "text": prompt})
        resp = self._client.messages.parse(
            model=self.model,
            max_tokens=16000,
            messages=[{"role": "user", "content": content}],
            output_format=schema,
            # On a safety decline, let the API re-run the request on a suitable fallback model.
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"},
        )
        if resp.stop_reason == "refusal":
            raise llm.ModelCallError(f"{self.model} declined the request")
        return resp.parsed_output.model_dump_json()


class OpenAIVision:
    def __init__(self, model: str = config.OPENAI_MODEL, client=None):
        self.model = model
        self.name = model
        self._client = client

    def generate(self, frames: Frames, prompt: str, schema: type[M]) -> str:
        if self._client is None:
            self._client = openai_client()
        content: list[dict] = [{"type": "text", "text": FRAMES_INTRO}]
        for t, jpg in frames:
            url = f"data:image/jpeg;base64,{base64.standard_b64encode(jpg).decode()}"
            content += [{"type": "text", "text": f"[{fmt_ts(t)}]"},
                        {"type": "image_url", "image_url": {"url": url, "detail": "high"}}]
        content.append({"type": "text", "text": f"{prompt}\n\nReply with JSON matching this schema:\n{json.dumps(schema.model_json_schema())}"})
        resp = self._client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": content}],
                                                    response_format={"type": "json_object"})
        return resp.choices[0].message.content


class FrameSequenceAnalyzer(VideoAnalyzer):
    supports_closeup = True

    def __init__(self, backend: VisionBackend, locate_width: int = 512, inspect_width: int = 960, **kw):
        super().__init__(**kw)
        self.backend = backend
        self.name = f"frames-{backend.name}"
        self.locate_width = locate_width
        self.inspect_width = inspect_width

    def _generate(self, label: str, schema: type[M], frames: Frames, prompt: str, clip: str) -> M:
        request = {"backend": self.backend.name, "clip": clip, "prompt": prompt, "frames": len(frames),
                   "span": [fmt_ts(frames[0][0]), fmt_ts(frames[-1][0])] if frames else None}

        def run(repair: str | None) -> str:
            text = prompt + (prompts.repair_note(repair) if repair else "")
            return self.backend.generate(frames, text, schema)

        return llm.generate_json(label, schema, run, request=request, check=check_neutral)

    def locate(self, path: Path, duration: float) -> LocateResult:
        frames = ffmpeg.extract_frames(path, 0.0, duration, self.locate_fps, self.locate_width)
        return self._generate("frames-locate", LocateResult, frames, prompts.LOCATE, path.name)

    def inspect(self, path: Path, locate: LocateResult, view: View, start: float, end: float) -> Observation:
        frames = ffmpeg.extract_frames(path, start, end, self.inspect_fps, self.inspect_width)
        return self._generate("frames-inspect", Observation, frames,
                              prompts.inspect(locate, view, start, end), path.name)

    def closeup(self, path: Path, obs: Observation, start: float, end: float) -> CloseUp:
        with tempfile.TemporaryDirectory() as tmp:
            crop = ffmpeg.crop_clip(path, start, end, obs.contact_box, Path(tmp) / "closeup.mp4")
            frames = ffmpeg.extract_frames(crop, 0.0, end - start, self.inspect_fps, self.inspect_width)
        return self._generate("frames-closeup", CloseUp, frames, prompts.closeup(obs), path.name)
