"""FastAPI backend: upload a clip, follow the job's progress, fetch the ruling, leave feedback.

Run: uv run uvicorn foulcheck.api.app:app --port 8000
"""

import json
import os
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from foulcheck import config
from foulcheck.api.jobs import JobStore, Renderer, Runner
from foulcheck.decision.schema import Ruling
from foulcheck.video import ffmpeg

ALLOWED = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".m4v": "video/mp4"}
SSE_KEEPALIVE_S = 15


class Feedback(BaseModel):
    job_id: str
    rating: Literal["up", "down"]
    would_call: Literal["foul", "no_foul", "handball", "not_sure"] | None = None
    would_card: Literal["none", "yellow", "red"] | None = None
    comment: str | None = Field(None, max_length=1000)


def default_runner() -> Runner:
    from foulcheck.decision.engine import DecisionEngine
    from foulcheck.pipeline import analyze_clip
    from foulcheck.video import make_analyzer

    from foulcheck.decision.models import make_text_model

    shared = None  # built lazily; uses the server's .env key

    def run(path, context, progress, api_key=None) -> Ruling:
        nonlocal shared
        if api_key:  # a visitor's key: fresh clients for this job only
            analyzer, engine = make_analyzer(api_key=api_key), DecisionEngine(make_text_model(api_key=api_key))
        else:
            shared = shared or (make_analyzer(), DecisionEngine())
            analyzer, engine = shared
        return analyze_clip(path, context, analyzer=analyzer, engine=engine, progress=progress)

    return run


def server_key_available() -> bool:
    return config.ALLOW_SERVER_KEY and bool(os.environ.get("GEMINI_API_KEY"))


def default_renderer() -> Renderer:
    from foulcheck.explain.render import render_video

    return lambda clip, ruling, out: render_video(clip, ruling, out, audio=False)  # the site serves silent video


def create_app(runner: Runner | None = None, renderer: Renderer | None = None) -> FastAPI:
    app = FastAPI(title="Foul Explainer API")
    app.add_middleware(CORSMiddleware, allow_origins=config.FRONTEND_ORIGINS,
                       allow_methods=["*"], allow_headers=["*"])
    store = JobStore(runner or default_runner(), renderer if renderer is not None else default_renderer(),
                     config.RENDER_DIR)
    app.state.store = store

    @app.get("/api/config")
    def public_config():
        """What the page needs to know before an upload: whether a visitor must bring a key."""
        return {"server_key": server_key_available(), "edition": config.laws_config().label}

    @app.get("/api/health")
    def health():
        return {"ok": True, "edition": config.laws_config().label}

    @app.post("/api/jobs", status_code=202)
    def create_job(file: UploadFile = File(...), context: str | None = Form(None),
                   x_gemini_api_key: str | None = Header(None)):
        api_key = (x_gemini_api_key or "").strip() or None
        if api_key is None and not server_key_available():
            raise HTTPException(401, "Add your Gemini API key to run the analysis.")
        if api_key is not None and (len(api_key) < 20 or len(api_key) > 200 or any(ch.isspace() for ch in api_key)):
            raise HTTPException(400, "That doesn't look like a Gemini API key.")
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED:
            raise HTTPException(400, "Upload an MP4, MOV or WebM video.")
        config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
        size = 0
        with dest.open("wb") as out:
            while chunk := file.file.read(1 << 20):
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(413, "Clip is larger than 100 MB.")
                out.write(chunk)
        try:
            duration = ffmpeg.probe(dest)["duration"]
        except (subprocess.CalledProcessError, KeyError, ValueError):
            dest.unlink(missing_ok=True)
            raise HTTPException(400, "That file could not be read as a video.")
        if duration > config.MAX_CLIP_SECONDS:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, f"Clip is {duration:.0f} seconds long; the limit is {config.MAX_CLIP_SECONDS}.")
        context = (context or "").strip()[:500] or None
        job = store.submit(dest, file.filename or dest.name, context, api_key)
        return job.public()

    def _job(job_id: str):
        job = store.get(job_id)
        if job is None:
            raise HTTPException(404, "No such job.")
        return job

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str):
        return _job(job_id).public()

    @app.get("/api/jobs/{job_id}/result", response_model=Ruling)
    def job_result(job_id: str):
        job = _job(job_id)
        if job.status == "error":
            raise HTTPException(409, job.error)
        if job.ruling is None:
            raise HTTPException(425, "Still working.")
        return job.ruling

    @app.get("/api/jobs/{job_id}/video")
    def job_video(job_id: str):
        job = _job(job_id)
        if job.video_path is None or not job.video_path.exists():
            raise HTTPException(404, "No explained video for this job.")
        stem = Path(job.clip_name).stem or "clip"
        return FileResponse(job.video_path, media_type="video/mp4", filename=f"{stem}_explained.mp4")

    @app.get("/api/jobs/{job_id}/events")
    def job_events(job_id: str):
        job = _job(job_id)

        def stream() -> Iterator[str]:
            current = job.model_copy()
            while True:
                yield f"event: status\ndata: {json.dumps(current.public(), default=str)}\n\n"
                if current.status in ("done", "error"):
                    return
                version = current.version
                current = store.wait_for_change(job_id, version, SSE_KEEPALIVE_S)
                if current.version == version:
                    yield ": keepalive\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/feedback")
    def feedback(fb: Feedback):
        job = _job(fb.job_id)
        r = job.ruling
        record = fb.model_dump() | {
            "at": time.time(), "clip": job.clip_name,
            "sha256": r.video.sha256 if r and r.video else None,
            "ruling": {"verdict": r.verdict, "restart": r.restart, "card": r.card,
                       "confidence": r.confidence.level} if r else None,
        }
        config.FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.FEEDBACK_PATH.open("a") as f:
            f.write(json.dumps(record) + "\n")
        return {"ok": True}

    return app


app = create_app()
