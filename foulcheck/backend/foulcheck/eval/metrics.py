"""Per-clip rows and the summary table measured against the v1 targets in the build plan."""

from dataclasses import dataclass
from statistics import median

from foulcheck.decision.schema import Ruling
from foulcheck.eval.labels import Label
from foulcheck.video.base import verdict_words
from foulcheck.video.schema import VideoAnalysis

CONTACT_TOLERANCE_S = 0.3
KEY_UNCERTAIN = ("contact", "ball_played_first", "speed_and_force", "handball", "location")


def row_for(config_name: str, clip: str, label: Label, video: VideoAnalysis | None,
            ruling: Ruling | None, video_error: str | None = None, decision_error: str | None = None) -> dict:
    row: dict = {"config": config_name, "clip": clip,
                 "video_error": video_error or "", "decision_error": decision_error or ""}
    if video is not None:
        obs, view, t = video.observation, video.locate.chosen_view(), video.timings
        row |= {
            "incident_found": video.locate.incident_found,
            "views": len(video.locate.views),
            "view_used": f"{view.kind}{'-slow' if view.slow_motion else ''}" if view else "",
            "contact_time": obs.contact_time if obs else "",
            "locate_s": t.get("locate_s"), "inspect_s": t.get("inspect_s"),
            "video_cached": bool(t.get("locate_cached") and t.get("inspect_cached")),
            "uncertain_fields": ";".join(obs.uncertain_fields) if obs else "",
            "key_uncertain": bool(obs and any(f.split(".")[0] in KEY_UNCERTAIN for f in obs.uncertain_fields)),
            "view_clear": bool(view and view.clarity == "clear"),
            "location": obs.location if obs else "",
            "ruling_words_in_video": len(verdict_words(obs)) if obs else 0,
        }
        if obs and view and obs.contact_seconds is not None:
            row["view_shift_s"] = round(abs(obs.contact_seconds - view.contact_seconds), 2)
        if obs and obs.contact_seconds is not None and label.contact_times:
            err = min(abs(obs.contact_seconds - c) for c in label.contact_times)
            row |= {"contact_err_s": round(err, 2), "contact_ok": err <= CONTACT_TOLERANCE_S}
    if ruling is not None:
        cited = sorted({c.section for c in ruling.citations})
        a = ruling.audit
        row |= {
            "verdict": ruling.verdict, "restart": ruling.restart, "card": ruling.card,
            "confidence": ruling.confidence.level, "confidence_score": ruling.confidence.score,
            "cited_sections": ";".join(cited), "citations": len(ruling.citations),
            "quotes": sum(1 for c in ruling.citations if c.quote),
            "guard_errors": a.get("guard_errors"), "reran": a.get("reran"), "enforced": a.get("enforced"),
            "second_opinion": a.get("second_opinion"), "decision_s": a.get("decision_s"),
        }
        if label.has_ruling:
            row |= {"label_verdict": label.verdict, "label_card": label.card, "label_restart": label.restart,
                    "verdict_ok": ruling.verdict == label.verdict,
                    "card_ok": None if label.card is None else ruling.card == label.card,
                    "restart_ok": None if label.restart is None else ruling.restart == label.restart}
            if label.required_sections:
                hit = [s for s in label.required_sections if any(c == s or c.startswith(s + ".") for c in cited)]
                row["citation_recall"] = round(len(hit) / len(label.required_sections), 2)
        if label.difficulty:
            row["difficulty"] = label.difficulty
    parts = [row.get("locate_s"), row.get("inspect_s")] + ([row.get("decision_s")] if ruling else [])
    if video is not None and all(isinstance(x, (int, float)) for x in parts):
        row["total_s"] = round(sum(parts), 1)
    return row


@dataclass
class Metric:
    name: str
    value: str
    n: int
    target: str
    status: str  # "met", "missed", "not measurable"
    note: str = ""


def _rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def summarize(rows: list[dict]) -> list[Metric]:
    ok = [r for r in rows if not r["video_error"]]
    ruled = [r for r in ok if "verdict" in r]
    failed = [r for r in rows if r["decision_error"]]
    out: list[Metric] = []
    if failed:
        out.append(Metric("Decision runs failed", str(len(failed)), len(rows), "0", "missed",
                          f"First error: {failed[0]['decision_error'][:120]}"))

    def add(name, value, n, target, threshold, note="", higher_is_better=True):
        if value is None:
            out.append(Metric(name, "n/a", n, target, "not measurable", note))
        else:
            met = value >= threshold if higher_is_better else value <= threshold
            out.append(Metric(name, _pct(value) if threshold <= 1 else f"{value:.0f} s", n, target,
                              "met" if met else "missed", note))

    clear = [r for r in ruled if "verdict_ok" in r and r.get("difficulty") != "hard"]
    add("Verdict accuracy (clear cases)", _rate([r["verdict_ok"] for r in clear]), len(clear), ">= 75%", 0.75,
        "" if clear else "No clips have ruling labels yet.")
    carded = [r for r in ruled if r.get("card_ok") is not None]
    add("Card accuracy", _rate([r["card_ok"] for r in carded]), len(carded), ">= 60%", 0.60,
        "" if carded else "No clips have card labels yet.")
    restarted = [r for r in ruled if r.get("restart_ok") is not None]
    add("Restart accuracy", _rate([r["restart_ok"] for r in restarted]), len(restarted), "(extra) high", 0.8,
        "" if restarted else "No restart labels.")
    recall = [r["citation_recall"] for r in ruled if "citation_recall" in r]
    add("Citation recall", sum(recall) / len(recall) if recall else None, len(recall), ">= 90%", 0.90,
        "" if recall else "No clips list required_sections yet.")
    first_ok = _rate([r["guard_errors"] == 0 for r in ruled])
    out.append(Metric("Citation precision (shown quotes verbatim)", "100%" if ruled else "n/a", len(ruled), "100%",
                      "met" if ruled else "not measurable",
                      f"Enforced by the guard. First drafts passed the guard {_pct(first_ok)} of the time." if ruled else ""))
    hard = [r for r in ruled if r.get("difficulty") == "hard"]
    if hard:
        add("Honest uncertainty (hard clips)", _rate([r["confidence"] != "High" or r["verdict"] == "cannot_determine" for r in hard]),
            len(hard), "most hard clips", 0.5)
    else:
        shaky = [r for r in ruled if r.get("key_uncertain") or not r.get("view_clear")]
        proxy = _rate([r["confidence"] != "High" for r in shaky])
        note = "No difficulty labels."
        if shaky:
            note += (f" Proxy: {_pct(proxy)} of the {len(shaky)} clips where the video model was unsure of a key "
                     "fact or the view was unclear got Medium/Low.")
        out.append(Metric("Honest uncertainty (hard clips)", "n/a", 0, "most hard clips", "not measurable", note))
    fresh = [r["total_s"] for r in ruled if "total_s" in r]
    video_only = [r["total_s"] for r in ok if "total_s" in r and "verdict" not in r]
    if fresh:
        med = median(fresh)
        out.append(Metric("Latency (upload to verdict)", f"median {med:.0f} s, max {max(fresh):.0f} s", len(fresh),
                          "< 45 s", "met" if max(fresh) < 45 else "missed",
                          "Model time only (video passes + decision); excludes upload and retries."))
    elif video_only:
        med = median(video_only)
        out.append(Metric("Latency (upload to verdict)", f"video alone: median {med:.0f} s, max {max(video_only):.0f} s",
                          len(video_only), "< 45 s", "missed" if med >= 45 else "not measurable",
                          "No decision timings; the video passes alone already exceed the target." if med >= 45
                          else "No decision timings in this run."))
    else:
        out.append(Metric("Latency (upload to verdict)", "n/a", 0, "< 45 s", "not measurable", "No timings recorded."))
    contact = [r["contact_ok"] for r in ok if "contact_ok" in r]
    add("Contact time within 0.3 s (fact check)", _rate(contact), len(contact), "(extra) high", 0.8,
        "" if contact else "No contact_times labels.")
    add("Valid observation JSON", _rate([bool(r.get("contact_time")) for r in ok] + [False] * (len(rows) - len(ok))),
        len(rows), "(extra) 100%", 1.0)
    add("Locate and inspect agree on contact (<= 0.3 s)", _rate([r["view_shift_s"] <= 0.3 for r in ok if "view_shift_s" in r]),
        len([r for r in ok if "view_shift_s" in r]), "(extra) high", 0.8)
    return out
