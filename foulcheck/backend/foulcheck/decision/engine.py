"""Decision engine: observation + retrieved Law chunks -> cited, confidence-rated ruling."""

import re
import time
from concurrent.futures import ThreadPoolExecutor

from foulcheck import llm
from foulcheck.config import laws_config
from foulcheck.decision import confidence, guard, prompts
from foulcheck.decision.models import TextModel, make_text_model
from foulcheck.decision.schema import Ruling, RulingDraft
from foulcheck.laws.models import Chunk
from foulcheck.video.schema import Observation, VideoAnalysis


# Passage IDs such as "[L12-1-p3]" or "(L12-4-cautions-unsporting-behaviour-p1)" mean nothing to a fan.
CHUNK_ID_REF = re.compile(r"\s*[\[(]\s*L\d+-[\w-]+(?:\s*[,;]\s*L\d+-[\w-]+)*\s*[\])]")


def strip_chunk_ids(text: str) -> str:
    return CHUNK_ID_REF.sub("", text)


class DecisionEngine:
    def __init__(self, model: TextModel | None = None, second_opinion: bool = True):
        self.model = model or make_text_model()
        self.second_opinion = second_opinion

    def _draft(self, obs: Observation, chunks: list[Chunk], context: str | None,
               sample: int = 0, fix: list[str] | None = None) -> RulingDraft:
        prompt = prompts.user_prompt(obs, chunks, context) + (prompts.repair_note(fix) if fix else "")
        request = {"model": self.model.name, "sample": sample, "chunk_ids": [c.id for c in chunks],
                   "system": prompts.SYSTEM, "prompt": prompt}

        def run(repair: str | None) -> str:
            text = prompt + (prompts.repair_note([repair]) if repair else "")
            return self.model.generate(prompts.SYSTEM, text, RulingDraft, sample)

        return llm.generate_json(f"decision-s{sample}{'-fix' if fix else ''}", RulingDraft, run, request=request)

    def decide(self, obs: Observation, chunks: list[Chunk], context: str | None = None,
               video: VideoAnalysis | None = None) -> Ruling:
        notes: list[str] = []
        started = time.monotonic()
        audit: dict = {"guard_errors": 0, "reran": False, "enforced": 0, "second_opinion": "off"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            main = pool.submit(self._draft, obs, chunks, context, 0)
            second = pool.submit(self._draft, obs, chunks, context, 1) if self.second_opinion else None
            draft = main.result()
            errors = guard.check(draft, chunks)
            audit["guard_errors"] = len(errors)
            if errors:
                notes.append(f"Citation guard rejected the first answer ({len(errors)} problem(s)); reran once.")
                audit["reran"] = True
                draft = self._draft(obs, chunks, context, 0, fix=errors)
                if guard.check(draft, chunks):
                    draft, fixes = guard.enforce(draft, chunks)
                    notes += fixes
                    audit["enforced"] = len(fixes)
            try:
                other = second.result() if second else None
            except (llm.ModelCallError, llm.ModelOutputError) as exc:
                other = None
                busy = "quota" if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc) else "busy or unavailable"
                notes.append(f"Second opinion unavailable (AI service {busy}), so confidence was not cross-checked.")
                audit["second_opinion"] = "unavailable"
        if other is not None:
            same = (other.verdict, other.restart, other.card) == (draft.verdict, draft.restart, draft.card)
            audit["second_opinion"] = "agree" if same else "disagree"
        audit["decision_s"] = round(time.monotonic() - started, 2)

        conf = confidence.assess(draft, obs, video, other)
        gray = list(draft.gray_areas)
        if other is not None and (other.verdict, other.restart, other.card) != (draft.verdict, draft.restart, draft.card):
            gray.append(f"A second reading of the same facts came out as {other.verdict.replace('_', ' ')}, "
                        f"{other.restart.replace('_', ' ')}, {other.card} card.")
        cfg = laws_config()
        return Ruling(
            verdict=draft.verdict, offence_type=draft.offence_type, restart=draft.restart, card=draft.card,
            confidence=conf, explanation=strip_chunk_ids(draft.explanation),
            citations=guard.build_citations(draft, chunks), gray_areas=[strip_chunk_ids(g) for g in gray], key_moment=draft.key_moment or obs.contact_time,
            edition=cfg.edition, edition_label=cfg.label, context_hint=context or None,
            used_user_context=draft.used_user_context, observation=obs, video=video, notes=notes, audit=audit,
        )
