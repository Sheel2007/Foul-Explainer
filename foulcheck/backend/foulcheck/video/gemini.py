"""Gemini native video: sends the clip itself, with custom fps and start/end offsets (static mode)."""

import tempfile
import time
from pathlib import Path

from google import genai
from google.genai import types

from foulcheck import config, llm
from foulcheck.clients import gemini_client
from foulcheck.video import prompts
from foulcheck.video.base import VideoAnalyzer, check_neutral
from foulcheck.video import ffmpeg
from foulcheck.video.schema import CloseUp, LocateResult, Observation, View

INLINE_LIMIT = 20 * 1024 * 1024  # larger clips go through the Files API


class GeminiAnalyzer(VideoAnalyzer):
    supports_closeup = True

    def __init__(self, model: str = config.GEMINI_MODEL, client: genai.Client | None = None,
                 thinking: str | None = None, **kw):
        super().__init__(**kw)
        self.model = model
        self.thinking = thinking  # "minimal" | "low" | "medium" | "high"; None = model default
        self.name = f"gemini-{model}" + (f"-think-{thinking}" if thinking else "")
        self._client = client
        self._uploads: dict[Path, types.File] = {}

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            self._client = gemini_client()
        return self._client

    def _video_part(self, path: Path, meta: types.VideoMetadata) -> types.Part:
        # media_processing is left unset: static mode is the default and the only mode that
        # honours fps and clipping. Agentic mode is meant for long videos.
        if path.stat().st_size <= INLINE_LIMIT:
            return types.Part(inline_data=types.Blob(data=path.read_bytes(), mime_type="video/mp4"),
                              video_metadata=meta)
        f = self._upload(path)
        return types.Part(file_data=types.FileData(file_uri=f.uri, mime_type=f.mime_type), video_metadata=meta)

    def _upload(self, path: Path) -> types.File:
        if path not in self._uploads:
            f = self.client.files.upload(file=path)
            while f.state and f.state.name == "PROCESSING":
                time.sleep(2)
                f = self.client.files.get(name=f.name)
            if f.state and f.state.name != "ACTIVE":
                raise llm.ModelCallError(f"Gemini file upload for {path.name} ended in state {f.state.name}")
            self._uploads[path] = f
        return self._uploads[path]

    def _generate(self, label: str, schema, prompt: str, path: Path, meta: types.VideoMetadata,
                  resolution: types.MediaResolution | None, check) -> object:
        request = {
            "model": self.model, "clip": path.name, "prompt": prompt,
            "video_metadata": meta.model_dump(exclude_none=True),
            "media_resolution": resolution.name if resolution else None, "thinking": self.thinking,
        }

        def run(repair: str | None) -> str:
            text = prompt + (prompts.repair_note(repair) if repair else "")
            resp = self.client.models.generate_content(
                model=self.model,
                contents=types.Content(role="user", parts=[self._video_part(path, meta), types.Part(text=text)]),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=schema.model_json_schema(),
                    media_resolution=resolution,
                    thinking_config=types.ThinkingConfig(thinking_level=self.thinking.upper()) if self.thinking else None,
                ),
            )
            return resp.text

        return llm.generate_json(label, schema, run, request=request, check=check)

    def locate(self, path: Path, duration: float) -> LocateResult:
        meta = types.VideoMetadata(fps=self.locate_fps)
        return self._generate("gemini-locate", LocateResult, prompts.LOCATE, path, meta, None, check_neutral)

    def inspect(self, path: Path, locate: LocateResult, view: View, start: float, end: float) -> Observation:
        meta = types.VideoMetadata(start_offset=f"{start:.2f}s", end_offset=f"{end:.2f}s", fps=self.inspect_fps)
        return self._generate("gemini-inspect", Observation, prompts.inspect(locate, view, start, end), path, meta,
                              types.MediaResolution.MEDIA_RESOLUTION_HIGH, check_neutral)

    def closeup(self, path: Path, obs: Observation, start: float, end: float) -> CloseUp:
        with tempfile.TemporaryDirectory() as tmp:
            crop = ffmpeg.crop_clip(path, start, end, obs.contact_box, Path(tmp) / "closeup.mp4")
            meta = types.VideoMetadata(fps=self.inspect_fps)
            return self._generate("gemini-closeup", CloseUp, prompts.closeup(obs), crop, meta,
                                  types.MediaResolution.MEDIA_RESOLUTION_HIGH, check_neutral)
