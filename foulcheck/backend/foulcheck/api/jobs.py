"""In-memory job store and background runner. One job = one uploaded clip being judged."""

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from foulcheck import config, llm
from foulcheck.decision.schema import Ruling
from foulcheck.pipeline import STAGES

Runner = Callable[[Path, str | None, Callable[[str], None], str | None], Ruling]  # (clip, context, progress, api_key)
Renderer = Callable[[Path, Ruling, Path], Path]


class Stage(BaseModel):
    key: str
    label: str


class Job(BaseModel):
    id: str
    status: Literal["queued", "running", "done", "error"] = "queued"
    stage: str | None = None
    stages: list[Stage] = Field(default_factory=lambda: [Stage(key=k, label=v) for k, v in STAGES.items()])
    error: str | None = None
    clip_name: str
    context: str | None = None
    created_at: float = Field(default_factory=time.time)
    finished_at: float | None = None
    version: int = 0
    ruling: Ruling | None = None
    video_path: Path | None = None

    def public(self) -> dict:
        """Status without the (large) ruling or server paths."""
        return self.model_dump(exclude={"ruling", "video_path"}) | {
            "has_result": self.ruling is not None, "has_video": self.video_path is not None}


def friendly_error(exc: Exception) -> str:
    text = str(exc)
    if any(s in text for s in ("API_KEY_INVALID", "API key not valid", "PERMISSION_DENIED", "authentication_error",
                               "invalid_api_key", "Incorrect API key", "invalid x-api-key")):
        return "Your API key was rejected. Check it and try again."
    if "credit balance" in text or "insufficient_quota" in text:
        return "That API key's account has no credit left. Add some with that provider and try again."
    if "model_not_found" in text or "not_found_error" in text:
        return "That API key can't use the model this tool needs. Try a key from another provider."
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        return "The AI service is out of quota right now. Please try again later."
    if "UNAVAILABLE" in text or "503" in text or "overloaded_error" in text or "529" in text:
        return "The AI service is overloaded right now. Please try again in a few minutes."
    if isinstance(exc, llm.ModelOutputError):
        return "The model returned an answer we could not validate. Please try again."
    return "Something went wrong while analysing the clip."


class JobStore:
    def __init__(self, runner: Runner, renderer: Renderer | None = None, render_dir: Path | None = None,
                 workers: int = 2):
        self.runner = runner
        self.renderer = renderer
        self.render_dir = render_dir
        self.jobs: dict[str, Job] = {}
        self.cond = threading.Condition()
        self.pool = ThreadPoolExecutor(max_workers=workers)

    def get(self, job_id: str) -> Job | None:
        with self.cond:
            return self.jobs.get(job_id)

    def _update(self, job_id: str, **changes) -> None:
        with self.cond:
            job = self.jobs[job_id]
            for k, v in changes.items():
                setattr(job, k, v)
            job.version += 1
            self.cond.notify_all()

    def submit(self, path: Path, clip_name: str, context: str | None, api_key: str | None = None) -> Job:
        """`api_key` is passed straight to the runner and never stored on the job or written anywhere."""
        self.clean_renders()
        job = Job(id=uuid.uuid4().hex[:12], clip_name=clip_name, context=context)
        with self.cond:
            self.jobs[job.id] = job
        self.pool.submit(self._run, job.id, path, context, api_key)
        return job

    def _run(self, job_id: str, path: Path, context: str | None, api_key: str | None = None) -> None:
        self._update(job_id, status="running")
        try:
            def progress(stage: str) -> None:
                self._update(job_id, stage=stage)

            ruling = self.runner(path, context, progress, api_key)
            video = self._render(job_id, path, ruling, progress)
            self._update(job_id, status="done", stage=None, ruling=ruling, video_path=video, finished_at=time.time())
        except Exception as exc:
            self._update(job_id, status="error", error=friendly_error(exc), finished_at=time.time())
            detail = f"{type(exc).__name__}: {exc}"
            if api_key:
                detail = detail.replace(api_key, "***")  # never let a key reach the logs
            llm._log({"label": "job-error", "job": job_id, "error": detail})
        finally:
            path.unlink(missing_ok=True)  # never keep uploaded clips

    def _render(self, job_id: str, path: Path, ruling: Ruling, progress) -> Path | None:
        """The explained video is a bonus: if it fails, the job still succeeds with the ruling."""
        if self.renderer is None or self.render_dir is None or ruling.video is None:
            return None
        progress("render")
        try:
            return self.renderer(path, ruling, self.render_dir / f"{job_id}.mp4")
        except Exception as exc:
            ruling.notes.append("The explained video could not be made.")
            llm._log({"label": "render-error", "job": job_id, "error": f"{type(exc).__name__}: {exc}"})
            return None

    def clean_renders(self) -> None:
        if self.render_dir is None or not self.render_dir.exists():
            return
        cutoff = time.time() - config.RENDER_TTL_S
        for f in self.render_dir.glob("*.mp4"):
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)

    def wait_for_change(self, job_id: str, seen_version: int, timeout: float) -> Job | None:
        with self.cond:
            self.cond.wait_for(lambda: self.jobs[job_id].version != seen_version, timeout=timeout)
            return self.jobs[job_id].model_copy()
