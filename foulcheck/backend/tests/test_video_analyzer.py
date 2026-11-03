import subprocess
from pathlib import Path

import pytest

from foulcheck import config
from foulcheck.video import ffmpeg
from foulcheck.video.base import VideoAnalyzer
from foulcheck.video.frames import FrameSequenceAnalyzer
from foulcheck.video.gemini import GeminiAnalyzer
from foulcheck.video.schema import LocateResult, Observation, View

LOCATE = LocateResult(
    incident_found=True, incident="A slides at B.",
    views=[View(contact_time="00:01.0", kind="live", camera="wide", clarity="partial"),
           View(contact_time="00:03.0", kind="replay", slow_motion=True, camera="close", clarity="clear")],
    best_view=1,
)


@pytest.fixture(scope="session")
def clip(tmp_path_factory) -> Path:
    """A 5-second synthetic test video."""
    path = tmp_path_factory.mktemp("clip") / "test.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=5:size=320x180:rate=25",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")


class Scripted(VideoAnalyzer):
    name = "scripted"

    def __init__(self, locate: LocateResult, obs: Observation):
        super().__init__()
        self.loc, self.obs = locate, obs
        self.calls: list[tuple] = []

    def locate(self, path, duration):
        self.calls.append(("locate", round(duration, 1)))
        return self.loc

    def inspect(self, path, locate, view, start, end):
        self.calls.append(("inspect", view.kind, round(start, 2), round(end, 2)))
        return self.obs.model_copy(deep=True)


def test_ffmpeg_probe_and_frames(clip):
    assert ffmpeg.probe(clip)["duration"] == pytest.approx(5.0, abs=0.1)
    frames = ffmpeg.extract_frames(clip, 1.0, 2.0, fps=10, width=160)
    assert 9 <= len(frames) <= 11
    assert frames[0][0] == pytest.approx(1.0) and frames[1][0] == pytest.approx(1.1)
    assert frames[0][1][:2] == b"\xff\xd8"  # JPEG


def test_analyze_uses_best_view_window_and_caches(clip):
    a = Scripted(LOCATE, Observation(contact_time="00:03.1"))
    res = a.analyze(clip)
    assert res.window == (1.5, 4.5)
    assert a.calls == [("locate", 5.0), ("inspect", "replay", 1.5, 4.5)]
    assert res.observation.contact_time == "00:03.1" and not res.notes
    a.analyze(clip)
    assert len(a.calls) == 2  # second run served from cache
    a.analyze(clip, use_cache=False)
    assert len(a.calls) == 4


def test_window_clamped_to_clip(clip):
    loc = LOCATE.model_copy(update={"best_view": 0})
    loc.views[0] = View(contact_time="00:04.8", kind="live", camera="wide", clarity="clear")
    res = Scripted(loc, Observation(contact_time="00:04.7")).analyze(clip)
    assert res.window[0] == pytest.approx(3.3) and res.window[1] == pytest.approx(5.0, abs=0.05)


def test_relative_contact_time_is_shifted(clip):
    res = Scripted(LOCATE, Observation(contact_time="00:00.8")).analyze(clip)
    assert res.observation.contact_time == "00:02.3"
    assert "relative" in res.notes[0]


def test_out_of_window_contact_time_falls_back(clip):
    res = Scripted(LOCATE, Observation(contact_time="00:09.0")).analyze(clip)
    assert res.observation.contact_time == "00:03.0"
    assert "contact_time" in res.observation.uncertain_fields


def test_no_incident_skips_inspect(clip):
    a = Scripted(LocateResult(incident_found=False), Observation())
    res = a.analyze(clip)
    assert res.observation is None and res.window is None
    assert [c[0] for c in a.calls] == ["locate"]


class FakeGeminiClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.requests.append({"model": model, "contents": contents, "config": config})

        class R:
            text = self.replies.pop(0)
        return R()


def test_gemini_requests_static_low_then_high_fps(clip):
    obs = Observation(contact_time="00:03.0", summary="A slides at B at 00:03.0.")
    client = FakeGeminiClient([LOCATE.model_dump_json(), obs.model_dump_json()])
    res = GeminiAnalyzer("test-model", client=client).analyze(clip)
    assert res.observation.contact_time == "00:03.0"

    locate_req, inspect_req = client.requests
    loc_video = locate_req["contents"].parts[0]
    assert loc_video.video_metadata.fps == 2 and loc_video.video_metadata.start_offset is None
    assert loc_video.inline_data.mime_type == "video/mp4"
    assert loc_video.media_processing is None  # static mode
    assert locate_req["config"].response_json_schema["title"] == "LocateResult"

    ins_video = inspect_req["contents"].parts[0]
    assert ins_video.video_metadata.fps == 12
    assert (ins_video.video_metadata.start_offset, ins_video.video_metadata.end_offset) == ("1.50s", "4.50s")
    assert inspect_req["config"].media_resolution.name == "MEDIA_RESOLUTION_HIGH"
    assert "00:03.0" in inspect_req["contents"].parts[1].text
    assert "studs" in inspect_req["contents"].parts[1].text  # the challenge-mechanics question is asked
    assert "challenge" in inspect_req["config"].response_json_schema["properties"]


def test_gemini_repairs_ruling_words(clip):
    ruled = Observation(contact_time="00:03.0", summary="Obvious foul.")
    fixed = Observation(contact_time="00:03.0", summary="A slides at B.")
    client = FakeGeminiClient([LOCATE.model_dump_json(), ruled.model_dump_json(), fixed.model_dump_json()])
    res = GeminiAnalyzer("test-model", client=client).analyze(clip)
    assert res.observation.summary == "A slides at B."
    assert "ruling words" in client.requests[2]["contents"].parts[1].text


class FakeBackend:
    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def generate(self, frames, prompt, schema):
        self.seen.append((len(frames), frames[0][0], frames[-1][0], schema.__name__))
        return self.replies.pop(0)


def test_frame_sequence_analyzer_sends_low_then_high_rate_frames(clip):
    backend = FakeBackend([LOCATE.model_dump_json(), Observation(contact_time="00:03.0").model_dump_json()])
    res = FrameSequenceAnalyzer(backend, locate_width=160, inspect_width=160).analyze(clip)
    (n_loc, t0, _, s1), (n_ins, s_start, s_end, s2) = backend.seen
    assert s1 == "LocateResult" and 9 <= n_loc <= 11 and t0 == 0
    assert s2 == "Observation" and 34 <= n_ins <= 37
    assert s_start == pytest.approx(1.5) and s_end <= 4.5
    assert res.analyzer.startswith("frames-fake")


def test_locate_reused_when_inspect_fps_changes_and_timings_recorded(clip):
    a = Scripted(LOCATE, Observation(contact_time="00:03.0"))
    first = a.analyze(clip)
    assert first.timings["locate_cached"] is False and first.timings["locate_s"] >= 0
    b = Scripted(LOCATE, Observation(contact_time="00:03.0"))
    b.inspect_fps = 6
    second = b.analyze(clip)
    assert [c[0] for c in b.calls] == ["inspect"]  # locate came from cache
    assert second.timings["locate_cached"] is True and second.timings["inspect_cached"] is False
    assert second.timings["locate_s"] == first.timings["locate_s"]  # seconds survive in the sidecar


def test_gemini_thinking_level_sent_and_part_of_cache_name(clip):
    client = FakeGeminiClient([LOCATE.model_dump_json(), Observation(contact_time="00:03.0").model_dump_json()])
    a = GeminiAnalyzer("test-model", client=client, thinking="low")
    a.analyze(clip)
    assert a.name == "gemini-test-model-think-low"
    assert client.requests[0]["config"].thinking_config.thinking_level.name == "LOW"
    assert GeminiAnalyzer("m", client=client).name == "gemini-m"


def test_make_analyzer_uses_visitor_key_client():
    from foulcheck.decision.models import make_text_model
    from foulcheck.video import make_analyzer
    a = make_analyzer("gemini", "m", api_key="AIzaSyVisitorKey_0123456789abcdefghij")
    assert a._client is not None and a._client._api_client.api_key == "AIzaSyVisitorKey_0123456789abcdefghij"
    assert make_analyzer("gemini", "m")._client is None  # server key: built lazily from the env
    t = make_text_model("gemini", "m", api_key="AIzaSyVisitorKey_0123456789abcdefghij")
    assert t._client._api_client.api_key == "AIzaSyVisitorKey_0123456789abcdefghij"


def test_crop_box_is_16_9_grown_and_inside_frame():
    w, h, x, y = ffmpeg.crop_box(640, 360, [400, 450, 600, 550])
    assert abs(w / h - 16 / 9) < 0.02 and w >= 640 * 0.35
    assert 0 <= x and x + w <= 640 and 0 <= y and y + h <= 360
    # a box at the edge stays inside the frame
    w, h, x, y = ffmpeg.crop_box(640, 360, [900, 950, 1000, 1000])
    assert x + w <= 640 and y + h <= 360


def test_contact_box_validation_drops_bad_boxes():
    assert Observation(contact_box=[100, 200, 300, 400]).contact_box == [100, 200, 300, 400]
    assert Observation(contact_box=[300, 200, 100, 400]).contact_box is None
    assert Observation(contact_box=[0, 0, 2000, 10]).contact_box is None


def test_merge_closeup_overrides_boot_facts():
    from foulcheck.video.base import merge_closeup
    from foulcheck.video.schema import CloseUp
    obs = Observation(contact={"made": True, "body_part_used": "instep", "body_part_hit": "foot"},
                      challenge={"studs_showing": False, "lunge": True}, uncertain_fields=["challenge.studs_showing", "location"])
    close = CloseUp(challenge={"studs_showing": True, "leg_straight": True}, body_part_used="studs/sole",
                    boot_detail="Sole of the right boot leads into the ankle.")
    m = merge_closeup(obs, close)
    assert m.challenge.studs_showing is True and m.challenge.lunge is True and m.challenge.leg_straight is True
    assert m.contact.body_part_used == "studs/sole" and m.contact.body_part_hit == "foot"
    assert m.boot_detail.startswith("Sole") and m.uncertain_fields == ["location"]
    assert obs.challenge.studs_showing is False  # original untouched


def test_gemini_closeup_pass_sends_cropped_video_and_merges(clip):
    from foulcheck.video.schema import CloseUp
    obs = Observation(contact_time="00:03.0", contact={"made": True, "body_part_used": "foot"}, contact_box=[300, 300, 700, 700],
                      challenge={"studs_showing": False})
    close = CloseUp(challenge={"studs_showing": True}, body_part_used="studs/sole", boot_detail="Studs lead in.")
    client = FakeGeminiClient([LOCATE.model_dump_json(), obs.model_dump_json(), close.model_dump_json()])
    res = GeminiAnalyzer("test-model", client=client).analyze(clip)
    assert len(client.requests) == 3
    crop_part = client.requests[2]["contents"].parts[0]
    assert crop_part.inline_data.data != Path(clip).read_bytes() and crop_part.video_metadata.start_offset is None
    assert "close-up" in client.requests[2]["contents"].parts[1].text
    assert res.observation.challenge.studs_showing is True and res.observation.contact.body_part_used == "studs/sole"
    assert res.closeup.boot_detail == "Studs lead in." and "close-up" in res.notes[-1]


def test_closeup_failure_keeps_wide_shot_answers(clip):
    obs = Observation(contact_time="00:03.0", contact_box=[300, 300, 700, 700], challenge={"studs_showing": False})
    client = FakeGeminiClient([LOCATE.model_dump_json(), obs.model_dump_json(), "not json", "still not json"])
    res = GeminiAnalyzer("test-model", client=client).analyze(clip)
    assert res.observation.challenge.studs_showing is False and res.closeup is None
    assert "Close-up unavailable" in res.notes[-1]
