import json
import subprocess
import threading

import pytest
from fastapi.testclient import TestClient

from foulcheck import config
from foulcheck.api.app import create_app
from foulcheck.decision.schema import Confidence, Ruling


def fake_ruling() -> Ruling:
    return Ruling(verdict="foul", offence_type="reckless challenge", restart="direct_free_kick", card="yellow",
                  confidence=Confidence(model_score=0.8, score=0.8, level="High"), explanation="A slid in.",
                  citations=[], gray_areas=[], key_moment="00:03.8", edition="2026-27",
                  edition_label="Laws of the Game 2026/27")


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    path = tmp_path_factory.mktemp("v") / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x90:rate=10",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_SERVER_KEY", True)
    monkeypatch.setenv("GEMINI_API_KEY", "server-key-for-tests")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")


def make_client(runner, renderer=None):
    return TestClient(create_app(runner, renderer or (lambda *a: None)))


def upload(client, path, name="clip.mp4", context=None, key=None):
    with path.open("rb") as f:
        return client.post("/api/jobs", files={"file": (name, f, "video/mp4")},
                           data={"context": context} if context else {},
                           headers={"X-Gemini-Api-Key": key} if key else {})


def wait_done(client, job_id, on_event=None):
    events = []
    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        for line in resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                on_event and on_event(events[-1])
    return events


def test_upload_progress_result_and_upload_deleted(video):
    gate = threading.Event()
    seen = {}

    def runner(path, context, progress, api_key=None):
        seen.update(path=path, context=context, existed=path.exists())
        for stage in ("locate", "inspect", "rules"):
            progress(stage)
        assert gate.wait(5)
        return fake_ruling()

    client = make_client(runner)
    r = upload(client, video, context="  it was the last man  ")
    assert r.status_code == 202
    job = r.json()
    assert [s["label"] for s in job["stages"]] == ["Finding the key moment", "Looking closely", "Checking the Laws",
                                                   "Making the explained video"]
    events = wait_done(client, job["id"], lambda e: e["stage"] == "rules" and gate.set())
    assert events[-1]["status"] == "done" and events[-1]["has_result"]
    assert "rules" in [e["stage"] for e in events]
    result = client.get(f"/api/jobs/{job['id']}/result").json()
    assert result["verdict"] == "foul" and result["key_moment"] == "00:03.8"
    assert seen["existed"] and seen["context"] == "it was the last man"
    assert not seen["path"].exists()  # uploads are deleted after processing


def test_job_error_is_friendly(video):
    def runner(path, context, progress, api_key=None):
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")

    client = make_client(runner)
    job = upload(client, video).json()
    events = wait_done(client, job["id"])
    assert events[-1]["status"] == "error" and "quota" in events[-1]["error"]
    assert client.get(f"/api/jobs/{job['id']}/result").status_code == 409


def test_rejects_bad_type_non_video_and_long_clip(video, tmp_path, monkeypatch):
    client = make_client(lambda *a: fake_ruling())
    assert upload(client, video, name="clip.avi").status_code == 400
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"not a video")
    assert "could not be read" in upload(client, junk).json()["detail"]
    monkeypatch.setattr(config, "MAX_CLIP_SECONDS", 1)
    assert "limit is 1" in upload(client, video).json()["detail"]
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    assert upload(client, video).status_code == 413
    assert not any(config.UPLOAD_DIR.iterdir())


def test_unknown_job_404():
    client = make_client(lambda *a: fake_ruling())
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/jobs/nope/events").status_code == 404


def test_feedback_saved(video):
    client = make_client(lambda *a: fake_ruling())
    job = upload(client, video).json()
    wait_done(client, job["id"])
    r = client.post("/api/feedback", json={"job_id": job["id"], "rating": "down", "would_call": "no_foul",
                                           "would_card": "none", "comment": "ball first"})
    assert r.json() == {"ok": True}
    rec = json.loads(config.FEEDBACK_PATH.read_text().splitlines()[0])
    assert rec["would_call"] == "no_foul" and rec["ruling"]["card"] == "yellow" and rec["clip"] == "clip.mp4"
    assert client.post("/api/feedback", json={"job_id": job["id"], "rating": "meh"}).status_code == 422


def test_explained_video_rendered_and_served(video, tmp_path, monkeypatch):
    from foulcheck.video.schema import LocateResult, VideoAnalysis
    monkeypatch.setattr(config, "RENDER_DIR", tmp_path / "renders")
    seen = {}

    def runner(path, context, progress, api_key=None):
        r = fake_ruling()
        r.video = VideoAnalysis(clip="c", sha256="x", duration_s=2, analyzer="a", locate=LocateResult(incident_found=True))
        return r

    def renderer(path, ruling, out):
        seen["upload_exists"] = path.exists()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake mp4")
        return out

    client = make_client(runner, renderer)
    job = upload(client, video, name="my clip.mp4").json()
    events = wait_done(client, job["id"])
    assert events[-1]["status"] == "done" and events[-1]["has_video"]
    assert seen["upload_exists"]  # rendered before the upload is deleted
    resp = client.get(f"/api/jobs/{job['id']}/video")
    assert resp.content == b"fake mp4" and "my%20clip_explained.mp4" in resp.headers["content-disposition"]


def test_render_failure_keeps_ruling(video, tmp_path, monkeypatch):
    from foulcheck.video.schema import LocateResult, VideoAnalysis
    monkeypatch.setattr(config, "RENDER_DIR", tmp_path / "renders")

    def runner(path, context, progress, api_key=None):
        r = fake_ruling()
        r.video = VideoAnalysis(clip="c", sha256="x", duration_s=2, analyzer="a", locate=LocateResult(incident_found=True))
        return r

    def renderer(*a):
        raise RuntimeError("ffmpeg blew up")

    client = make_client(runner, renderer)
    job = upload(client, video).json()
    assert wait_done(client, job["id"])[-1]["status"] == "done"
    assert "could not be made" in client.get(f"/api/jobs/{job['id']}/result").json()["notes"][-1]
    assert client.get(f"/api/jobs/{job['id']}/video").status_code == 404


VISITOR_KEY = "AIzaSyVisitorKey_0123456789abcdefghij"


def test_visitor_key_reaches_runner_but_is_never_returned_or_logged(video, tmp_path):
    seen = {}

    def runner(path, context, progress, api_key=None):
        seen["key"] = api_key
        return fake_ruling()

    client = make_client(runner)
    job = upload(client, video, key=VISITOR_KEY).json()
    events = wait_done(client, job["id"])
    assert seen["key"] == VISITOR_KEY
    payloads = json.dumps(job) + json.dumps(events) + client.get(f"/api/jobs/{job['id']}/result").text
    assert VISITOR_KEY not in payloads
    assert not any(VISITOR_KEY in f.read_text() for f in config.LOGS_DIR.rglob("*") if f.is_file())


def test_key_masked_in_logged_errors(video):
    def runner(path, context, progress, api_key=None):
        raise RuntimeError(f"400 INVALID_ARGUMENT API key not valid: {api_key}")

    client = make_client(runner)
    job = upload(client, video, key=VISITOR_KEY).json()
    events = wait_done(client, job["id"])
    assert "API key was rejected" in events[-1]["error"]
    logged = " ".join(f.read_text() for f in config.LOGS_DIR.rglob("*.json"))
    assert "***" in logged and VISITOR_KEY not in logged


def test_key_required_when_server_key_not_allowed(video, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_SERVER_KEY", False)
    client = make_client(lambda *a: fake_ruling())
    assert client.get("/api/config").json()["server_key"] is False
    r = upload(client, video)
    assert r.status_code == 401 and "API key" in r.json()["detail"]
    assert upload(client, video, key="short").status_code == 400
    assert upload(client, video, key=VISITOR_KEY).status_code == 202


def test_config_reports_server_key(monkeypatch):
    client = make_client(lambda *a: fake_ruling())
    assert client.get("/api/config").json()["server_key"] is True
    monkeypatch.delenv("GEMINI_API_KEY")
    assert client.get("/api/config").json()["server_key"] is False
