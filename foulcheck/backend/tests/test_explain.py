import subprocess

import pytest

from foulcheck.decision.schema import Citation, Confidence, Ruling
from foulcheck.explain import panel
from foulcheck.explain.__main__ import main as explain_main
from foulcheck.explain.render import contact_moments, render_video
from foulcheck.video import ffmpeg
from foulcheck.video.schema import LocateResult, Observation, VideoAnalysis, View


def cite(quote="Reckless is when a player acts with disregard to the danger", highlight="acts with disregard"):
    return Citation(chunk_id="L12-1-p3", law="12", section="12.1", title="Direct free kick", page=115,
                    reference="Law 12.1", why="defines reckless", quote=quote, highlight=highlight, source_url="u")


def ruling(explanation="A slid in late and caught B's ankle.", citations=None, video=None, card="yellow"):
    return Ruling(verdict="foul", offence_type="reckless challenge", restart="direct_free_kick", card=card,
                  confidence=Confidence(model_score=0.8, score=0.8, level="High"), explanation=explanation,
                  citations=citations if citations is not None else [cite()], gray_areas=["Could be red."],
                  key_moment="00:01.5", edition="2026-27", edition_label="Laws of the Game 2026/27", video=video,
                  observation=video.observation if video else None)


def analysis():
    views = [View(contact_time="00:00.5", kind="live", camera="wide", clarity="partial"),
             View(contact_time="00:01.4", kind="replay", slow_motion=True, camera="close", clarity="clear")]
    return VideoAnalysis(clip="c.mp4", sha256="x", duration_s=2, analyzer="a",
                         locate=LocateResult(incident_found=True, views=views, best_view=1),
                         observation=Observation(contact_time="00:01.5"))


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    path = tmp_path_factory.mktemp("c") / "c.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=25",
                    "-f", "lavfi", "-i", "sine=duration=2", "-pix_fmt", "yuv420p", "-shortest", str(path)], check=True)
    return path


def test_spans_and_words_keep_highlight_inside_a_word():
    runs = panel.spans("“trips or attempts to trip”", "trips or attempts to trip")
    assert [r.marked for r in runs] == [False, True, False]
    ws = panel.words(runs)
    assert ws[0] == [("“", False), ("trips", True)] and ws[-1] == [("trip", True), ("”", False)]
    assert panel.spans("abc", "zzz")[0].text == "abc" and not panel.spans("abc", None)[0].marked


def test_wrap_respects_width():
    f = panel.font("regular", 20)
    lines = panel.wrap([panel.Run("word " * 60)], f, 300)
    assert len(lines) > 1
    for line in lines:
        assert sum(f.getlength("".join(p for p, _ in w)) for w in line) + f.getlength(" ") * (len(line) - 1) <= 300


def test_draw_panel_size_and_fits_long_content():
    img = panel.draw_panel(ruling(), 640, 720)
    assert img.size == (640, 720)
    long = ruling(explanation="Very long explanation sentence. " * 40, citations=[cite(quote="word " * 80)] * 4)
    assert panel.draw_panel(long, 640, 720).size == (640, 720)  # shrinks and truncates instead of overflowing


def test_contact_moments_uses_inspect_time_for_chosen_view():
    assert contact_moments(ruling(video=analysis())) == [(0.5, "live"), (1.5, "replay (slow motion)")]
    assert contact_moments(ruling()) == [(1.5, None)]


def test_render_video_composes_side_panel(clip, tmp_path):
    out = render_video(clip, ruling(video=analysis()), tmp_path / "out.mp4")
    info = ffmpeg.probe(out)
    assert (info["width"], info["height"]) == (1280 + 640, 720)  # 320x180 scaled to 720 high, plus the panel
    assert info["duration"] == pytest.approx(2.0, abs=0.15)
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)],
                             capture_output=True, text=True).stdout.split()
    assert streams == ["video", "audio"]


def test_cli_rerender_from_saved_ruling(clip, tmp_path):
    (tmp_path / "c_ruling.json").write_text(ruling(video=analysis()).model_dump_json())
    assert explain_main(["--rerender", "--out", str(tmp_path), str(clip)]) == 0
    assert (tmp_path / "c_explained.mp4").exists()
    assert explain_main(["--rerender", "--out", str(tmp_path / "missing"), str(clip)]) == 1
