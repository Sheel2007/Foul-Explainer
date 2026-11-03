import csv

import pytest

from foulcheck import config
from foulcheck.decision.schema import Citation, Confidence, Ruling
from foulcheck.eval import labels as labels_mod
from foulcheck.eval.__main__ import main as eval_main, parse_video_spec, report
from foulcheck.eval.label import main as label_main
from foulcheck.eval.labels import Label, load_label
from foulcheck.eval.metrics import row_for, summarize
from foulcheck.video.schema import LocateResult, Observation, VideoAnalysis, View


def video(contact="00:03.9", uncertain=(), clarity="clear", loc_s=10.0, ins_s=12.0):
    v = View(contact_time="00:03.8", kind="replay", slow_motion=True, camera="close", clarity=clarity)
    return VideoAnalysis(clip="2.mp4", sha256="x", duration_s=7, analyzer="cfg",
                         locate=LocateResult(incident_found=True, views=[v]), window=(2.3, 5.3),
                         observation=Observation(contact_time=contact, uncertain_fields=list(uncertain)),
                         timings={"locate_s": loc_s, "inspect_s": ins_s, "locate_cached": True, "inspect_cached": True})


def ruling(verdict="foul", card="yellow", level="High", sections=("12.1", "12.4"), guard_errors=0, decision_s=8.0):
    cites = [Citation(chunk_id=f"c{i}", law="12", section=s, title="t", page=1, reference="r", why="w", source_url="u")
             for i, s in enumerate(sections)]
    return Ruling(verdict=verdict, offence_type=None, restart="direct_free_kick", card=card,
                  confidence=Confidence(model_score=0.8, score=0.8, level=level), explanation="e",
                  citations=cites, gray_areas=[], key_moment=None, edition="e", edition_label="E",
                  audit={"guard_errors": guard_errors, "reran": False, "enforced": 0,
                         "second_opinion": "agree", "decision_s": decision_s})


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(labels_mod, "LABEL_DIR", tmp_path / "labels")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")


def test_row_scores_against_labels():
    label = Label(clip="2.mp4", verdict="foul", card="red", required_sections=["12.1", "12.4", "14"],
                  difficulty="clear", contact_times=[1.3, 3.85])
    row = row_for("cfg", "2.mp4", label, video(), ruling())
    assert row["verdict_ok"] and row["card_ok"] is False
    assert row["citation_recall"] == pytest.approx(0.67)
    assert row["contact_err_s"] == pytest.approx(0.05) and row["contact_ok"]
    assert row["total_s"] == 30.0 and row["video_cached"]


def test_row_without_labels_or_ruling():
    row = row_for("cfg", "2.mp4", Label(clip="2.mp4"), video(), None)
    assert "verdict_ok" not in row and "contact_ok" not in row and row["total_s"] == 22.0
    err = row_for("cfg", "2.mp4", Label(clip="2.mp4"), None, None, "boom")
    assert err["video_error"] == "boom" and "total_s" not in err
    dec = row_for("cfg", "2.mp4", Label(clip="2.mp4"), video(), None, decision_error="quota")
    assert dec["decision_error"] == "quota" and dec["contact_time"] == "00:03.9" and dec["view_shift_s"] == 0.1


def test_summary_targets_and_unmeasurable_metrics():
    lab = Label(clip="a", verdict="foul", card="yellow", required_sections=["12.1"], difficulty="clear", contact_times=[3.9])
    rows = [row_for("cfg", "a", lab, video(), ruling()),
            row_for("cfg", "b", Label(clip="b"), video(uncertain=["ball_played_first"]), ruling(level="Medium", guard_errors=2)),
            row_for("cfg", "c", Label(clip="c"), None, None, "boom"),
            row_for("cfg", "d", Label(clip="d"), video(), None, decision_error="429 quota")]
    m = {x.name: x for x in summarize(rows)}
    assert m["Verdict accuracy (clear cases)"].status == "met" and m["Verdict accuracy (clear cases)"].n == 1
    assert m["Card accuracy"].value == "100%"
    assert m["Citation recall"].status == "met"
    assert "50%" in m["Citation precision (shown quotes verbatim)"].note
    assert m["Honest uncertainty (hard clips)"].status == "not measurable" and "100%" in m["Honest uncertainty (hard clips)"].note
    assert m["Latency (upload to verdict)"].status == "met"  # 30 s per clip
    slow = summarize([row_for("cfg", "a", lab, video(loc_s=50), ruling())])
    assert {x.name: x for x in slow}["Latency (upload to verdict)"].status == "missed"
    assert m["Valid observation JSON"].value == "75%"  # decision failures don't count against the video step
    assert m["Decision runs failed"].value == "1" and "429" in m["Decision runs failed"].note


def test_summary_with_no_labels_says_why():
    m = {x.name: x for x in summarize([row_for("cfg", "a", Label(clip="a"), video(), ruling())])}
    assert m["Verdict accuracy (clear cases)"].status == "not measurable"
    assert "No clips have ruling labels" in m["Verdict accuracy (clear cases)"].note


def test_parse_video_spec():
    name, a = parse_video_spec("model=gemini-x,l=1,i=6,think=low")
    assert (a.locate_fps, a.inspect_fps, a.thinking) == (1.0, 6.0, "low") and name == "gemini-gemini-x-think-low-l1.0-i6.0-w1.5"
    with pytest.raises(SystemExit):
        parse_video_spec("fps=3")


def test_label_cli_roundtrip():
    label_main(["2.mp4", "--verdict", "foul", "--card", "yellow", "--sections", "12.1, 12.4", "--contact", "1.3,3.85"])
    label_main(["2.mp4", "--difficulty", "hard"])
    lb = load_label("2.mp4")
    assert labels_mod.label_path("2.mp4").parent == labels_mod.LABEL_DIR != config.REPO_DIR / "eval" / "labels"
    assert (lb.verdict, lb.card, lb.required_sections, lb.contact_times, lb.difficulty) == \
        ("foul", "yellow", ["12.1", "12.4"], [1.3, 3.85], "hard")


def test_eval_cli_video_only(tmp_path, monkeypatch):
    import foulcheck.eval.__main__ as ev

    class Fake:
        cache_id = "fake-cfg"

        def analyze(self, clip, use_cache=True):
            return video()

    monkeypatch.setattr(ev, "parse_video_spec", lambda spec: ("fake-cfg", Fake()))
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path / "results")
    clip = tmp_path / "2.mp4"
    clip.write_bytes(b"")
    assert eval_main(["--decision", "none", "--clips", str(clip)]) == 0
    (csv_file,) = (tmp_path / "results").glob("*.csv")
    rows = list(csv.DictReader(csv_file.open()))
    assert rows[0]["config"] == "fake-cfg (video only)" and rows[0]["contact_time"] == "00:03.9"
    md = csv_file.with_suffix(".md").read_text()
    assert "| Latency (upload to verdict) |" in md and "not measurable" in md
